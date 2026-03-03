"""Unit tests for the audio pipeline components.

Tests cover:
- System pipeline functionality
- Audio buffer management
- Silence detection
- Device initialization and cleanup
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

from app.audio.system_pipeline import (
    RingBuffer,
    SilenceDetector,
    SystemPipeline,
    SystemPipelineConfig,
)


class TestSilenceDetector:
    """Tests for the SilenceDetector class."""

    def test_init(self, sample_rate: int) -> None:
        """Test silence detector initialization."""
        detector = SilenceDetector(
            threshold_db=-40.0,
            silence_duration_ms=1000.0,
            sample_rate=sample_rate,
        )

        assert detector.threshold_linear == pytest.approx(10 ** (-40.0 / 20.0), rel=1e-6)
        assert detector.silence_samples == sample_rate  # 1 second at 16kHz
        assert detector._silence_counter == 0
        assert not detector._in_silence

    def test_process_silence(self, sample_rate: int, mock_audio_data: np.ndarray) -> None:
        """Test processing silent audio."""
        detector = SilenceDetector(
            threshold_db=-40.0,
            silence_duration_ms=1000.0,
            sample_rate=sample_rate,
        )

        is_silent, duration = detector.process(mock_audio_data)

        assert is_silent is True
        assert duration > 0
        assert detector._in_silence is True

    def test_process_speech(self, sample_rate: int, mock_speech_audio: np.ndarray) -> None:
        """Test processing speech audio."""
        detector = SilenceDetector(
            threshold_db=-40.0,
            silence_duration_ms=1000.0,
            sample_rate=sample_rate,
        )

        is_silent, duration = detector.process(mock_speech_audio)

        assert is_silent is False
        assert duration == 0.0
        assert detector._in_silence is False

    def test_silence_boundary_detection(self, sample_rate: int) -> None:
        """Test detection of silence boundaries."""
        detector = SilenceDetector(
            threshold_db=-40.0,
            silence_duration_ms=100.0,  # 100ms for faster test
            sample_rate=sample_rate,
        )

        # Generate 200ms of silence
        silent_audio = np.zeros(int(sample_rate * 0.2), dtype=np.float32)

        assert not detector.is_silence_boundary()

        detector.process(silent_audio)

        assert detector.is_silence_boundary() is True

    def test_reset(self, sample_rate: int, mock_audio_data: np.ndarray) -> None:
        """Test detector reset functionality."""
        detector = SilenceDetector(
            threshold_db=-40.0,
            silence_duration_ms=1000.0,
            sample_rate=sample_rate,
        )

        detector.process(mock_audio_data)
        assert detector._in_silence is True

        detector.reset()

        assert detector._silence_counter == 0
        assert not detector._in_silence
        assert detector._silence_start == 0


class TestRingBuffer:
    """Tests for the RingBuffer class."""

    @pytest.mark.asyncio
    async def test_init(self) -> None:
        """Test ring buffer initialization."""
        buffer = RingBuffer(capacity=8, buffer_size=160)

        assert buffer.capacity == 8
        assert buffer.buffer_size == 160
        assert buffer.is_empty is True
        assert buffer.is_full is False
        assert buffer.available == 0

    @pytest.mark.asyncio
    async def test_write_and_read(self) -> None:
        """Test writing and reading from ring buffer."""
        buffer = RingBuffer(capacity=4, buffer_size=160)
        data = np.ones(160, dtype=np.float32)

        # Write data
        result = await buffer.write(data)
        assert result is True
        assert buffer.available == 1

        # Read data
        read_data = await buffer.read()
        assert read_data is not None
        assert len(read_data) == 160
        assert np.allclose(read_data, data)
        assert buffer.is_empty is True

    @pytest.mark.asyncio
    async def test_buffer_full(self) -> None:
        """Test behavior when buffer is full."""
        buffer = RingBuffer(capacity=2, buffer_size=160)
        data = np.ones(160, dtype=np.float32)

        # Fill buffer
        await buffer.write(data)
        await buffer.write(data)

        assert buffer.is_full is True

        # Try to write to full buffer
        result = await buffer.write(data)
        assert result is False

    @pytest.mark.asyncio
    async def test_variable_size_data(self) -> None:
        """Test handling of variable size audio data."""
        buffer = RingBuffer(capacity=4, buffer_size=160)

        # Write smaller data (should be padded)
        small_data = np.ones(100, dtype=np.float32)
        await buffer.write(small_data)

        read_data = await buffer.read()
        assert read_data is not None
        assert len(read_data) == 160  # Padded to buffer_size

        # Write larger data (should be truncated)
        large_data = np.ones(200, dtype=np.float32)
        await buffer.write(large_data)

        read_data = await buffer.read()
        assert read_data is not None
        assert len(read_data) == 160  # Truncated to buffer_size

    @pytest.mark.asyncio
    async def test_peek_all(self) -> None:
        """Test peeking at all buffered data."""
        buffer = RingBuffer(capacity=4, buffer_size=160)

        data1 = np.ones(160, dtype=np.float32)
        data2 = np.ones(160, dtype=np.float32) * 2

        await buffer.write(data1)
        await buffer.write(data2)

        all_data = await buffer.peek_all()
        assert len(all_data) == 2
        assert np.allclose(all_data[0], data1)
        assert np.allclose(all_data[1], data2)

        # Data should still be in buffer
        assert buffer.available == 2

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        """Test clearing the buffer."""
        buffer = RingBuffer(capacity=4, buffer_size=160)
        data = np.ones(160, dtype=np.float32)

        await buffer.write(data)
        await buffer.write(data)
        assert buffer.available == 2

        await buffer.clear()

        assert buffer.is_empty is True
        assert buffer.available == 0


class TestSystemPipelineConfig:
    """Tests for SystemPipelineConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = SystemPipelineConfig()

        assert config.buffer_duration_ms == 500.0
        assert config.buffer_count == 8
        assert config.segment_on_silence is True
        assert config.silence_duration_ms == 1000.0
        assert config.min_segment_duration_ms == 500.0
        assert config.max_segment_duration_ms == 30000.0
        assert config.vad_threshold_db == -40.0
        assert config.mix_to_mono is True

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = SystemPipelineConfig(
            buffer_duration_ms=250.0,
            buffer_count=16,
            segment_on_silence=False,
            silence_duration_ms=500.0,
        )

        assert config.buffer_duration_ms == 250.0
        assert config.buffer_count == 16
        assert config.segment_on_silence is False
        assert config.silence_duration_ms == 500.0


class TestSystemPipeline:
    """Tests for the SystemPipeline class."""

    def test_init(self) -> None:
        """Test pipeline initialization."""
        config = SystemPipelineConfig(
            sample_rate=16000,
            buffer_duration_ms=500.0,
            buffer_count=8,
        )
        pipeline = SystemPipeline(config)

        assert pipeline.system_config == config
        assert pipeline.buffer_size == 8000  # 16000 * 0.5
        assert pipeline._ring_buffer.capacity == 8
        assert pipeline._silence_detector is not None

    def test_get_mode(self) -> None:
        """Test pipeline mode is SYSTEM."""
        config = SystemPipelineConfig()
        pipeline = SystemPipeline(config)

        mode = pipeline._get_mode()
        assert mode.name == "SYSTEM"

    @pytest.mark.asyncio
    async def test_emit_segment(self) -> None:
        """Test segment emission."""
        config = SystemPipelineConfig(sample_rate=16000)
        pipeline = SystemPipeline(config)

        # Add audio to current segment
        audio_data = np.ones(16000, dtype=np.float32)
        pipeline._current_segment = [audio_data]

        # Mock the output queue
        pipeline._output_queue = AsyncMock()
        pipeline._output_queue.put = AsyncMock()

        await pipeline._emit_segment(reason="test")

        # Verify segment was emitted
        pipeline._output_queue.put.assert_called_once()
        assert len(pipeline._current_segment) == 0

    def test_get_session_stats(self) -> None:
        """Test session statistics retrieval."""
        config = SystemPipelineConfig()
        pipeline = SystemPipeline(config)

        pipeline._total_audio_duration = 10.5
        pipeline._segments_emitted = 5
        pipeline._silence_boundaries = 3

        stats = pipeline.get_session_stats()

        assert stats["total_audio_seconds"] == 10.5
        assert stats["segments_emitted"] == 5
        assert stats["silence_boundaries"] == 3
        assert stats["buffer_size"] == pipeline.buffer_size

    def test_calculate_rms(self) -> None:
        """Test RMS calculation."""
        config = SystemPipelineConfig()
        pipeline = SystemPipeline(config)

        # Test with silence
        silent_audio = np.zeros(16000, dtype=np.float32)
        rms = pipeline._calculate_rms(silent_audio)
        assert rms == pytest.approx(0.0, abs=1e-6)

        # Test with sine wave
        t = np.linspace(0, 1, 16000, dtype=np.float32)
        sine_audio = np.sin(2 * np.pi * 440 * t)
        rms = pipeline._calculate_rms(sine_audio)
        expected_rms = np.sqrt(np.mean(sine_audio**2))
        assert rms == pytest.approx(expected_rms, rel=1e-6)
