"""Unit tests for the transcription engine (STT).

Tests cover:
- WhisperTranscriber initialization
- Model loading and GPU/CPU fallback
- Audio chunk submission
- Queue management and backpressure
- Error handling
"""

from __future__ import annotations

import threading
import time
from queue import Full, Queue
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

from app.stt.engine import (
    WhisperTranscriber,
    SubmitStatus,
    confidence_proxy,
    _should_fallback_to_cpu,
)
from app.stt.chunker import AudioChunk
from app.core.error_handler import ErrorCategory, ErrorSeverity, ModelError


class TestSubmitStatus:
    """Tests for SubmitStatus dataclass."""

    def test_submit_status_creation(self) -> None:
        """Test SubmitStatus creation."""
        status = SubmitStatus(
            accepted=True,
            queue_depth=5,
            dropped_chunks=0,
            backpressure_state="normal",
            estimated_backlog_seconds=2.5,
            max_queue_size=20,
        )

        assert status.accepted is True
        assert status.queue_depth == 5
        assert status.dropped_chunks == 0
        assert status.backpressure_state == "normal"
        assert status.estimated_backlog_seconds == 2.5
        assert status.max_queue_size == 20


class TestWhisperTranscriberInit:
    """Tests for WhisperTranscriber initialization."""

    def test_default_initialization(self) -> None:
        """Test transcriber initialization with default parameters."""
        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="/tmp/models",
            device="cpu",
            compute_type="int8",
            beam_size=5,
            best_of=5,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=10,
        )

        assert transcriber.model_name == "tiny"
        assert transcriber.device == "cpu"
        assert transcriber.compute_type == "int8"
        assert transcriber.beam_size == 5
        assert transcriber.vad_filter is True
        assert transcriber.language_mode == "en"
        assert transcriber.execution_mode == "auto"
        assert transcriber._max_queue_items == 10
        assert transcriber._model is None

    def test_auto_language_warning(self) -> None:
        """Test warning for auto language detection."""
        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="/tmp/models",
            device="cpu",
            compute_type="int8",
            beam_size=5,
            best_of=5,
            temperature=0.0,
            vad_filter=True,
            language_mode="auto",
            execution_mode="auto",
            max_queue_items=10,
        )

        assert transcriber._warning is not None
        assert "auto" in transcriber._warning.lower()

    def test_callback_registration(self) -> None:
        """Test callback registration."""
        transcriber = WhisperTranscriber(
            model_name="tiny",
            download_root="/tmp/models",
            device="cpu",
            compute_type="int8",
            beam_size=5,
            best_of=5,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=10,
        )

        segment_callback = Mock()
        error_callback = Mock()
        health_callback = Mock()

        transcriber.add_segment_callback(segment_callback)
        transcriber.add_error_callback(error_callback)
        transcriber.add_health_callback(health_callback)

        assert segment_callback in transcriber._segment_callbacks
        assert error_callback in transcriber._error_callbacks
        assert health_callback in transcriber._health_callbacks


class TestWhisperTranscriberQueue:
    """Tests for queue management."""

    @pytest.fixture
    def transcriber(self) -> WhisperTranscriber:
        """Create a test transcriber."""
        return WhisperTranscriber(
            model_name="tiny",
            download_root="/tmp/models",
            device="cpu",
            compute_type="int8",
            beam_size=5,
            best_of=5,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=2,
        )

    def test_submit_success(self, transcriber: WhisperTranscriber) -> None:
        """Test successful chunk submission."""
        chunk = AudioChunk(
            started_at=0.0,
            samples=np.zeros(16000, dtype=np.float32),
            duration=1.0,
        )

        result = transcriber.submit(chunk)

        assert result is True
        assert transcriber._queue.qsize() == 1
        assert transcriber._backpressure_state == "normal"

    def test_submit_when_stopped(self, transcriber: WhisperTranscriber) -> None:
        """Test submission when transcriber is stopped."""
        transcriber._stop.set()

        chunk = AudioChunk(
            started_at=0.0,
            samples=np.zeros(16000, dtype=np.float32),
            duration=1.0,
        )

        result = transcriber.submit(chunk)

        assert result is False

    def test_queue_backpressure(self, transcriber: WhisperTranscriber) -> None:
        """Test queue backpressure handling."""
        # Fill the queue
        chunk = AudioChunk(
            started_at=0.0,
            samples=np.zeros(16000, dtype=np.float32),
            duration=1.0,
        )

        transcriber.submit(chunk)
        transcriber.submit(chunk)

        # Third submission should trigger backpressure
        result = transcriber.submit(chunk)

        # Should still succeed due to eviction
        assert result is True
        assert transcriber._backpressure_state == "dropping_oldest"
        assert transcriber._dropped_chunks > 0


class TestWhisperTranscriberModelLoading:
    """Tests for model loading functionality."""

    @pytest.fixture
    def transcriber(self) -> WhisperTranscriber:
        """Create a test transcriber."""
        return WhisperTranscriber(
            model_name="tiny",
            download_root="/tmp/models",
            device="auto",
            compute_type="float16",
            beam_size=5,
            best_of=5,
            temperature=0.0,
            vad_filter=True,
            language_mode="en",
            execution_mode="auto",
            max_queue_items=10,
        )

    @patch("app.stt.engine.WhisperModel")
    def test_load_model_cpu_only(
        self, mock_model_class: Mock, transcriber: WhisperTranscriber
    ) -> None:
        """Test loading model in CPU-only mode."""
        transcriber.execution_mode = "cpu_only"
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model

        model = transcriber._load_model()

        assert model is mock_model
        assert transcriber._gpu_mode == "cpu/int8"
        assert transcriber._runtime_device == "cpu"
        mock_model_class.assert_called_once()
        call_kwargs = mock_model_class.call_args[1]
        assert call_kwargs["device"] == "cpu"
        assert call_kwargs["compute_type"] == "int8"

    @patch("app.stt.engine.WhisperModel")
    @patch("app.stt.engine.torch")
    def test_load_model_gpu_available(
        self, mock_torch: Mock, mock_model_class: Mock, transcriber: WhisperTranscriber
    ) -> None:
        """Test loading model when GPU is available."""
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_properties.return_value.total_memory = 8 * (1024**3)
        mock_torch.cuda.memory_reserved.return_value = 1 * (1024**3)

        mock_model = MagicMock()
        mock_model_class.return_value = mock_model

        # Mock warmup to succeed
        with patch.object(transcriber, "_warmup_gpu", return_value=True):
            model = transcriber._load_model()

        assert model is mock_model
        assert transcriber._gpu_mode == "cuda/float16"

    @patch("app.stt.engine.WhisperModel")
    @patch("app.stt.engine.torch")
    def test_load_model_gpu_oom_fallback(
        self, mock_torch: Mock, mock_model_class: Mock, transcriber: WhisperTranscriber
    ) -> None:
        """Test fallback to CPU when GPU OOM."""
        mock_torch.cuda.is_available.return_value = True
        # Simulate low GPU memory
        mock_torch.cuda.get_device_properties.return_value.total_memory = 2 * (1024**3)
        mock_torch.cuda.memory_reserved.return_value = 1.9 * (1024**3)

        mock_model = MagicMock()
        mock_model_class.return_value = mock_model

        model = transcriber._load_model()

        assert model is mock_model
        assert transcriber._gpu_mode == "cpu/int8"
        assert transcriber._runtime_device == "cpu"

    @patch("app.stt.engine.WhisperModel")
    def test_load_model_caching(
        self, mock_model_class: Mock, transcriber: WhisperTranscriber
    ) -> None:
        """Test model caching - second load should return cached model."""
        transcriber.execution_mode = "cpu_only"
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model

        # First load
        model1 = transcriber._load_model()
        # Second load - should return cached
        model2 = transcriber._load_model()

        assert model1 is model2
        # Model should only be created once
        mock_model_class.assert_called_once()


class TestConfidenceProxy:
    """Tests for confidence_proxy function."""

    def test_confidence_with_all_metrics(self) -> None:
        """Test confidence calculation with all metrics."""
        mock_segment = MagicMock()
        mock_segment.avg_logprob = -0.3
        mock_segment.no_speech_prob = 0.1
        mock_segment.compression_ratio = 1.5

        confidence = confidence_proxy(mock_segment)

        assert 0.0 <= confidence <= 1.0

    def test_confidence_with_no_metrics(self) -> None:
        """Test confidence calculation with no metrics."""
        mock_segment = MagicMock()
        mock_segment.avg_logprob = None
        mock_segment.no_speech_prob = None
        mock_segment.compression_ratio = None

        confidence = confidence_proxy(mock_segment)

        assert confidence >= 0.0

    def test_confidence_bounds(self) -> None:
        """Test confidence stays within bounds."""
        mock_segment = MagicMock()
        mock_segment.avg_logprob = -1.0  # Very low
        mock_segment.no_speech_prob = 1.0  # High no-speech probability
        mock_segment.compression_ratio = 10.0  # High compression

        confidence = confidence_proxy(mock_segment)

        assert 0.0 <= confidence <= 1.0


class TestShouldFallbackToCPU:
    """Tests for _should_fallback_to_cpu function."""

    def test_cuda_runtime_error(self) -> None:
        """Test detection of CUDA runtime errors."""
        exc = RuntimeError("CUDA runtime error: out of memory")
        assert _should_fallback_to_cpu(exc) is True

    def test_cublas_error(self) -> None:
        """Test detection of cuBLAS errors."""
        exc = RuntimeError("cublas64_12.dll not found")
        assert _should_fallback_to_cpu(exc) is True

    def test_no_fallback_error(self) -> None:
        """Test that non-GPU errors don't trigger fallback."""
        exc = RuntimeError("Some other error")
        assert _should_fallback_to_cpu(exc) is False

    def test_case_insensitive(self) -> None:
        """Test case-insensitive matching."""
        exc = RuntimeError("CUDA OUT OF MEMORY")
        assert _should_fallback_to_cpu(exc) is True
