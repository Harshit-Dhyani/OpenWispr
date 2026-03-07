"""Comprehensive pytest configuration for OpenWispr backend testing.

This module provides fixtures for:
- Audio pipeline testing
- Mock models and devices
- Test settings configurations
- Performance benchmarking
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import threading
import time
import uuid
from collections.abc import AsyncGenerator, Callable, Generator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import numpy as np
import pytest
import pytest_asyncio

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# ============================================================================
# Path Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def test_data_dir(project_root: Path) -> Path:
    """Return the test data directory."""
    data_dir = project_root / "tests" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def mock_settings_file(temp_dir: Path) -> Path:
    """Create a mock settings file."""
    settings_path = temp_dir / "user_settings.json"
    settings_data = {
        "general": {
            "defaultSessionTitle": "Test Session",
            "defaultLanguage": "en",
            "exportDirectory": str(temp_dir),
            "autoSaveInterval": 30,
            "showNotifications": True,
            "minimizeToTray": False,
            "startupWithSystem": False,
            "theme": "system",
        },
        "transcription": {
            "model_name": "tiny",
            "default_asr_model_id": "whisper-tiny",
            "refinement_mode": "off",
            "compute_type": "int8",
            "chunk_duration": 5.0,
            "overlap_ratio": 0.15,
            "vad_enabled": True,
            "vad_threshold_db": -40.0,
            "vad_min_silence_ms": 300,
            "vad_speech_pad_ms": 200,
            "confidence_threshold": 0.5,
            "enable_filler_filter": True,
            "enable_hallucination_filter": True,
            "min_segment_length": 0.5,
            "max_workers": 2,
            "use_parallel_processing": False,
            "preload_model": False,
            "hotkey_optimized": False,
            "beam_size": 5,
            "best_of": 5,
            "patience": 1.0,
            "temperature": 0.0,
        },
        "refiner": {
            "selected_model_id": "none",
            "runtime_enabled": False,
            "engine_preference": "cpu",
        },
        "audio": {
            "captureMode": "system",
            "defaultDeviceId": "default",
            "backend": "sounddevice",
            "audio_backend": "sounddevice",
            "sampleRate": 16000,
            "vadEnabled": True,
            "vadThresholdDb": -40.0,
            "noiseFiltering": True,
            "echoCancellation": False,
            "autoGainControl": True,
        },
        "hotkey": {
            "enabled": True,
            "key_combination": "Ctrl+Shift+R",
            "hold_mode": False,
            "auto_inject": True,
            "language": "auto",
            "device_id": "default",
            "finish_mode_default": "clipboard",
            "show_floating_window": True,
            "floating_window_position": "cursor",
            "record_on_start": False,
            "stop_on_release": False,
            "copy_to_clipboard": True,
        },
        "advanced": {
            "debugMode": True,
            "logLevel": "DEBUG",
            "enableMetrics": True,
            "maxLogFiles": 10,
            "experimentalStem": False,
            "experimentalGpuAccel": False,
        },
        "modes": {
            "wispr": {
                "model_name": "tiny",
                "beam_size": 1,
                "best_of": 1,
                "vad_threshold": -35.0,
                "chunk_duration": 0.5,
                "overlap_ratio": 0.1,
                "compute_type": "int8",
                "vad_enabled": True,
                "hotkey_optimized": True,
            },
            "system": {
                "model_name": "base",
                "beam_size": 5,
                "best_of": 5,
                "vad_threshold": -40.0,
                "chunk_duration": 5.0,
                "overlap_ratio": 0.15,
                "compute_type": "int8",
                "vad_enabled": True,
                "hotkey_optimized": False,
            },
            "active_mode": "system",
        },
        "version": 3,
    }
    settings_path.write_text(json.dumps(settings_data, indent=2))
    return settings_path


# ============================================================================
# Event Loop Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for async tests."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[Mock, None]:
    """Provide an async HTTP client mock."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {}))
    client.post = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {}))
    client.close = AsyncMock()
    yield client


# ============================================================================
# Audio Fixtures
# ============================================================================


@pytest.fixture
def sample_rate() -> int:
    """Default sample rate for tests."""
    return 16000


@pytest.fixture
def mock_audio_data(sample_rate: int) -> np.ndarray:
    """Generate mock audio data (1 second of silence)."""
    return np.zeros(sample_rate, dtype=np.float32)


@pytest.fixture
def mock_speech_audio(sample_rate: int) -> np.ndarray:
    """Generate mock speech-like audio data."""
    # Create audio with varying amplitude to simulate speech
    t = np.linspace(0, 1, sample_rate, dtype=np.float32)
    # Fundamental frequency around 150Hz (typical voice)
    fundamental = np.sin(2 * np.pi * 150 * t)
    # Add harmonics
    harmonic2 = 0.5 * np.sin(2 * np.pi * 300 * t)
    harmonic3 = 0.25 * np.sin(2 * np.pi * 450 * t)
    # Modulate amplitude to simulate syllables
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 4 * t)
    audio = envelope * (fundamental + harmonic2 + harmonic3)
    # Normalize
    audio = audio / np.max(np.abs(audio)) * 0.3
    return audio.astype(np.float32)


@pytest.fixture
def mock_noisy_audio(sample_rate: int) -> np.ndarray:
    """Generate mock noisy audio data."""
    # White noise
    noise = np.random.normal(0, 0.01, sample_rate).astype(np.float32)
    return noise


@pytest.fixture
def mock_audio_chunk(sample_rate: int) -> np.ndarray:
    """Generate a small audio chunk (100ms)."""
    return np.zeros(int(sample_rate * 0.1), dtype=np.float32)


@pytest.fixture
def mock_audio_devices() -> list[dict[str, Any]]:
    """Mock audio device list."""
    return [
        {
            "id": "device-1",
            "name": "Test Microphone",
            "is_input": True,
            "is_output": False,
            "is_loopback": False,
            "supports_loopback": False,
            "sample_rates": [16000, 44100, 48000],
            "channels": 2,
        },
        {
            "id": "device-2",
            "name": "Test Speaker",
            "is_input": False,
            "is_output": True,
            "is_loopback": True,
            "supports_loopback": True,
            "sample_rates": [16000, 44100, 48000],
            "channels": 2,
        },
        {
            "id": "default",
            "name": "Default Device",
            "is_input": True,
            "is_output": False,
            "is_loopback": False,
            "supports_loopback": False,
            "sample_rates": [16000],
            "channels": 1,
        },
    ]


# ============================================================================
# Mock Device Fixtures
# ============================================================================


@pytest.fixture
def mock_sounddevice() -> Generator[Mock, None, None]:
    """Mock sounddevice module."""
    with patch("app.audio.devices.sd") as mock_sd:
        mock_sd.query_devices.return_value = [
            {"name": "Test Mic", "index": 0, "max_input_channels": 2},
            {"name": "Test Speaker", "index": 1, "max_output_channels": 2},
        ]
        mock_sd.default.device = [0, 1]
        yield mock_sd


@pytest.fixture
def mock_soundcard() -> Generator[Mock, None, None]:
    """Mock soundcard module."""
    with patch("app.audio.devices.sc") as mock_sc:
        mock_mic = MagicMock()
        mock_mic.id = "test-mic-id"
        mock_mic.name = "Test Microphone"
        mock_mic.isloopback = False
        mock_mic.channels = 2

        mock_speaker = MagicMock()
        mock_speaker.id = "test-speaker-id"
        mock_speaker.name = "Test Speaker"
        mock_speaker.isloopback = True
        mock_speaker.channels = 2

        mock_sc.all_microphones.return_value = [mock_mic]
        mock_sc.all_speakers.return_value = [mock_speaker]
        yield mock_sc


@pytest.fixture
def mock_pyaudio() -> Generator[Mock, None, None]:
    """Mock PyAudio module."""
    with patch("app.audio.devices.pyaudio") as mock_pa:
        mock_instance = MagicMock()
        mock_pa.PyAudio.return_value = mock_instance

        mock_device_info = {
            "index": 0,
            "name": "Test Device",
            "maxInputChannels": 2,
            "maxOutputChannels": 0,
            "defaultSampleRate": 16000,
        }
        mock_instance.get_device_count.return_value = 1
        mock_instance.get_device_info_by_index.return_value = mock_device_info
        yield mock_pa


@pytest.fixture
def mock_recorder() -> Generator[MagicMock, None, None]:
    """Mock audio recorder for testing."""
    with patch("app.audio.capture.resolve_capture_device") as mock_resolve:
        mock_device = MagicMock()
        mock_recorder_ctx = MagicMock()
        mock_recorder = MagicMock()
        mock_recorder_ctx.__enter__ = MagicMock(return_value=mock_recorder)
        mock_recorder_ctx.__exit__ = MagicMock(return_value=None)
        mock_device.recorder.return_value = mock_recorder_ctx
        mock_resolve.return_value = (mock_device, "test-device")
        yield mock_recorder


# ============================================================================
# Model Fixtures
# ============================================================================


@pytest.fixture
def mock_whisper_model() -> Generator[Mock, None, None]:
    """Mock WhisperModel for testing."""
    with patch("app.stt.engine.WhisperModel") as mock_model_class:
        mock_model = MagicMock()

        # Mock segments return value
        mock_segment = MagicMock()
        mock_segment.text = "Test transcription"
        mock_segment.start = 0.0
        mock_segment.end = 2.0
        mock_segment.avg_logprob = -0.5
        mock_segment.no_speech_prob = 0.1
        mock_segment.compression_ratio = 1.0

        mock_info = MagicMock()
        mock_info.language = "en"

        mock_model.transcribe.return_value = ([mock_segment], mock_info)
        mock_model_class.return_value = mock_model
        yield mock_model


@pytest.fixture
def mock_whisper_segments() -> list[MagicMock]:
    """Create mock whisper segments for testing."""
    segments = []
    for i in range(3):
        seg = MagicMock()
        seg.text = f"Test segment {i + 1}"
        seg.start = float(i * 2)
        seg.end = float((i + 1) * 2)
        seg.avg_logprob = -0.3 - (i * 0.1)
        seg.no_speech_prob = 0.05
        seg.compression_ratio = 1.2
        segments.append(seg)
    return segments


@pytest.fixture
def mock_torch() -> Generator[Mock, None, None]:
    """Mock torch module."""
    with patch("app.stt.engine.torch") as mock_torch:
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_properties.return_value.total_memory = 8 * (1024**3)  # 8GB
        mock_torch.cuda.memory_reserved.return_value = 1 * (1024**3)  # 1GB reserved
        mock_torch.cuda.empty_cache = MagicMock()
        mock_torch.cuda.synchronize = MagicMock()
        yield mock_torch


@pytest.fixture
def mock_torch_cpu() -> Generator[Mock, None, None]:
    """Mock torch module with CPU-only."""
    with patch("app.stt.engine.torch") as mock_torch:
        mock_torch.cuda.is_available.return_value = False
        yield mock_torch


@pytest.fixture
def mock_torch_oom() -> Generator[Mock, None, None]:
    """Mock torch module that simulates out of memory."""
    with patch("app.stt.engine.torch") as mock_torch:
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_properties.return_value.total_memory = 2 * (1024**3)  # 2GB
        mock_torch.cuda.memory_reserved.return_value = 1.9 * (1024**3)  # Almost full
        yield mock_torch


# ============================================================================
# Settings Fixtures
# ============================================================================


@pytest.fixture
def test_settings() -> dict[str, Any]:
    """Provide test settings configuration."""
    return {
        "general": {
            "defaultSessionTitle": "Test Session",
            "defaultLanguage": "en",
            "exportDirectory": "./test_output",
            "autoSaveInterval": 30,
            "showNotifications": True,
            "minimizeToTray": False,
            "startupWithSystem": False,
            "theme": "system",
        },
        "transcription": {
            "model_name": "tiny",
            "default_asr_model_id": "whisper-tiny",
            "refinement_mode": "off",
            "compute_type": "int8",
            "chunk_duration": 5.0,
            "overlap_ratio": 0.15,
            "vad_enabled": True,
            "vad_threshold_db": -40.0,
            "vad_min_silence_ms": 300,
            "vad_speech_pad_ms": 200,
            "confidence_threshold": 0.5,
            "enable_filler_filter": True,
            "enable_hallucination_filter": True,
            "min_segment_length": 0.5,
            "max_workers": 2,
            "use_parallel_processing": False,
            "preload_model": False,
            "hotkey_optimized": False,
            "beam_size": 5,
            "best_of": 5,
            "patience": 1.0,
            "temperature": 0.0,
        },
        "refiner": {
            "selected_model_id": "none",
            "runtime_enabled": False,
            "engine_preference": "cpu",
        },
        "audio": {
            "captureMode": "system",
            "defaultDeviceId": "default",
            "backend": "sounddevice",
            "audio_backend": "sounddevice",
            "sampleRate": 16000,
            "vadEnabled": True,
            "vadThresholdDb": -40.0,
            "noiseFiltering": True,
            "echoCancellation": False,
            "autoGainControl": True,
        },
        "hotkey": {
            "enabled": True,
            "key_combination": "Ctrl+Shift+R",
            "hold_mode": False,
            "auto_inject": True,
            "language": "auto",
            "device_id": "default",
            "finish_mode_default": "clipboard",
            "show_floating_window": True,
            "floating_window_position": "cursor",
            "record_on_start": False,
            "stop_on_release": False,
            "copy_to_clipboard": True,
        },
        "advanced": {
            "debugMode": True,
            "logLevel": "DEBUG",
            "enableMetrics": True,
            "maxLogFiles": 10,
            "experimentalStem": False,
            "experimentalGpuAccel": False,
        },
        "modes": {
            "wispr": {
                "model_name": "tiny",
                "beam_size": 1,
                "best_of": 1,
                "vad_threshold": -35.0,
                "chunk_duration": 0.5,
                "overlap_ratio": 0.1,
                "compute_type": "int8",
                "vad_enabled": True,
                "hotkey_optimized": True,
            },
            "system": {
                "model_name": "base",
                "beam_size": 5,
                "best_of": 5,
                "vad_threshold": -40.0,
                "chunk_duration": 5.0,
                "overlap_ratio": 0.15,
                "compute_type": "int8",
                "vad_enabled": True,
                "hotkey_optimized": False,
            },
            "active_mode": "system",
        },
        "version": 3,
    }


@pytest.fixture
def mock_settings_manager(
    temp_dir: Path, test_settings: dict[str, Any]
) -> Generator[Mock, None, None]:
    """Mock settings manager with test configuration."""
    with patch("app.core.settings_manager.SettingsManager") as mock_manager_class:
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        # Configure mock to return test settings
        mock_manager.get_settings_dict.return_value = test_settings
        mock_manager.get_settings.return_value = MagicMock(
            general=MagicMock(**test_settings["general"]),
            transcription=MagicMock(**test_settings["transcription"]),
            refiner=MagicMock(**test_settings["refiner"]),
            audio=MagicMock(**test_settings["audio"]),
            hotkey=MagicMock(**test_settings["hotkey"]),
            advanced=MagicMock(**test_settings["advanced"]),
        )

        # Mock file operations
        settings_file = temp_dir / "user_settings.json"
        settings_file.write_text(json.dumps(test_settings))
        mock_manager.settings_path = settings_file

        yield mock_manager


# ============================================================================
# Session Fixtures
# ============================================================================


@pytest.fixture
def sample_segment() -> dict[str, Any]:
    """Provide sample segment data."""
    return {
        "id": "seg-001",
        "start": 0.0,
        "end": 5.0,
        "text": "Test transcript segment",
        "display_text": "Test transcript segment",
        "language": "en",
        "confidence": 0.85,
        "review_flag": False,
        "suppressed": False,
        "suppression_reasons": [],
        "quality_label": "good",
        "script_mismatch": False,
    }


@pytest.fixture
def sample_session_state() -> dict[str, Any]:
    """Provide sample session state."""
    return {
        "session_id": f"test-session-{uuid.uuid4().hex[:8]}",
        "title": "Test Session",
        "status": "running",
        "model_name": "tiny",
        "language_mode": "en",
        "live_mode": "balanced",
        "execution_mode": "auto",
        "device_id": "default",
        "segments": [],
        "suppressed_segments": [],
        "formulas": [],
        "needs_review": [],
        "documents": [],
        "health": {
            "audio_stream_active": True,
            "gpu_mode": "cpu/int8",
            "execution_mode": "auto",
            "model_runtime_device": "cpu",
            "queue_depth": 0,
            "dropped_stt_chunks": 0,
            "stt_backpressure_state": "normal",
            "dropped_frames": 0,
            "audio_backend": "sounddevice",
            "audio_backend_fallbacks": [],
            "estimated_backlog_seconds": 0.0,
        },
    }


@pytest.fixture
def mock_session_writer(temp_dir: Path) -> Generator[Mock, None, None]:
    """Mock session writer."""
    with patch("app.storage.session_writer.SessionWriter") as mock_writer_class:
        mock_writer = MagicMock()
        mock_writer_class.return_value = mock_writer
        mock_writer.output_dir = temp_dir
        yield mock_writer


# ============================================================================
# API Fixtures
# ============================================================================


@pytest.fixture
def mock_fastapi_app() -> Mock:
    """Create a mock FastAPI application."""
    mock_app = Mock()
    mock_app.routes = []
    return mock_app


@pytest.fixture
def mock_websocket() -> AsyncMock:
    """Create a mock WebSocket connection."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock(return_value={"action": "ping"})
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Create a mock async HTTP client."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {}))
    client.post = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {}))
    client.close = AsyncMock()
    return client


# ============================================================================
# Error Handler Fixtures
# ============================================================================


@pytest.fixture
def mock_error_handler() -> Generator[Mock, None, None]:
    """Mock error handler."""
    with patch("app.core.error_handler.get_error_handler") as mock_get_handler:
        mock_handler = MagicMock()
        mock_get_handler.return_value = mock_handler
        yield mock_handler


@pytest.fixture
def mock_user_notifier() -> Generator[Mock, None, None]:
    """Mock user notifier."""
    with patch("app.core.error_handler.UserNotifier") as mock_notifier_class:
        mock_notifier = MagicMock()
        mock_notifier_class.return_value = mock_notifier
        yield mock_notifier


# ============================================================================
# Performance Fixtures
# ============================================================================


@dataclass
class PerformanceMetrics:
    """Container for performance test metrics."""

    operation_name: str
    start_time: float = field(default_factory=time.perf_counter)
    end_time: float = 0.0
    memory_before: int = 0
    memory_after: int = 0
    iterations: int = 1

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000

    @property
    def memory_delta_mb(self) -> float:
        return (self.memory_after - self.memory_before) / (1024 * 1024)

    @property
    def throughput_per_second(self) -> float:
        if self.duration_ms <= 0:
            return 0.0
        return self.iterations / (self.duration_ms / 1000)


@pytest.fixture
def performance_tracker() -> Callable[[str, int], PerformanceMetrics]:
    """Factory fixture for tracking performance metrics."""
    import psutil

    def create_tracker(operation_name: str, iterations: int = 1) -> PerformanceMetrics:
        process = psutil.Process()
        metrics = PerformanceMetrics(
            operation_name=operation_name,
            memory_before=process.memory_info().rss,
            iterations=iterations,
        )
        return metrics

    return create_tracker


@pytest.fixture
def benchmark_config() -> dict[str, Any]:
    """Configuration for performance benchmarks."""
    return {
        "latency_threshold_ms": 100,  # Max acceptable latency for real-time ops
        "throughput_min_chunks_per_sec": 10,  # Min chunks processed per second
        "memory_growth_max_mb": 100,  # Max memory growth during test
        "concurrency_max_workers": 4,  # Max concurrent workers for load tests
        "warmup_iterations": 5,  # Iterations to warm up before measuring
        "measurement_iterations": 10,  # Iterations for actual measurement
    }


# ============================================================================
# VAD Fixtures
# ============================================================================


@pytest.fixture
def mock_vad_config() -> dict[str, Any]:
    """Mock VAD configuration."""
    return {
        "threshold_db": -40.0,
        "min_silence_ms": 300,
        "speech_pad_ms": 200,
        "hysteresis_ms": 100.0,
        "min_speech_ms": 150,
        "adaptive_alpha": 0.95,
        "noise_floor_db": -60.0,
        "peak_hold_ms": 50,
    }


@pytest.fixture
def mock_vad() -> Generator[Mock, None, None]:
    """Mock VAD instance."""
    with patch("app.audio.vad_optimized.OptimizedVAD") as mock_vad_class:
        mock_vad = MagicMock()
        mock_vad.process_frame.return_value = (MagicMock(), None)
        mock_vad.process_stream.return_value = []
        mock_vad.get_metrics.return_value = MagicMock(
            total_samples=16000,
            speech_samples=8000,
            silence_samples=8000,
            transitions=2,
            avg_processing_time_ms=0.1,
            speech_ratio=0.5,
        )
        mock_vad_class.return_value = mock_vad
        yield mock_vad


# ============================================================================
# Cleanup Fixture
# ============================================================================


@pytest.fixture(autouse=True)
def cleanup_temp_files(temp_dir: Path) -> Generator[None, None, None]:
    """Automatically clean up temporary files after each test."""
    yield
    # Cleanup happens automatically via tmp_path fixture


@pytest.fixture(autouse=True)
def reset_singletons() -> Generator[None, None, None]:
    """Reset singleton instances before each test."""
    # Reset any singletons that might persist between tests
    with patch("app.core.settings_manager._settings_manager", None):
        with patch("app.core.error_handler._default_handler", None):
            yield


# ============================================================================
# Test Helpers
# ============================================================================


class AsyncContextManagerMock:
    """Helper for mocking async context managers."""

    def __init__(self, return_value: Any = None):
        self.return_value = return_value

    async def __aenter__(self) -> Any:
        return self.return_value

    async def __aexit__(self, *args: Any) -> None:
        pass


@pytest.fixture
def async_context_manager_mock() -> Callable[[Any], AsyncContextManagerMock]:
    """Factory for creating async context manager mocks."""
    return AsyncContextManagerMock


T = TypeVar("T")


@pytest.fixture
def async_iterator_mock() -> Callable[[list[T]], AsyncMock]:
    """Factory for creating async iterator mocks."""

    def create_mock(items: list[T]) -> AsyncMock:
        mock = AsyncMock()
        mock.__aiter__ = AsyncMock(return_value=mock)
        mock.__anext__ = AsyncMock(side_effect=items + [StopAsyncIteration])
        return mock

    return create_mock
