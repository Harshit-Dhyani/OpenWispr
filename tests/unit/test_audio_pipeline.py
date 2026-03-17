"""Unit tests for audio pipeline components.

Tests cover:
- Pipeline factory creation
- Pipeline state management
- Audio capture and buffering
- Device switching
- Error recovery
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.unit

from app.audio.pipeline_base import AudioPipeline, PipelineConfig, PipelineHealth, PipelineState


class MockAudioPipeline(AudioPipeline):
    """Mock implementation of AudioPipeline for testing."""

    def __init__(self, config: PipelineConfig) -> None:
        super().__init__(config)
        self._mode = Mock()
        self._mode.value = "test"
        self.initialized = False
        self.captured_frames: list[np.ndarray] = []

    def _get_mode(self) -> Mock:
        return self._mode

    async def _initialize_device(self) -> None:
        self.initialized = True

    async def _capture_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                await asyncio.sleep(0.01)
                continue

            # Simulate capturing audio
            frame = np.zeros(512, dtype=np.float32)
            self.captured_frames.append(frame)
            self._health.frames_captured += 1

            try:
                self._output_queue.put_nowait(frame)
            except asyncio.QueueFull:
                self._health.frames_dropped += 1

            await asyncio.sleep(0.01)

    async def _cleanup_device(self) -> None:
        self.initialized = False

    def probe_device(self, *, duration: float, output_dir: Path) -> Mock:
        result = Mock()
        result.success = True
        result.peak_rms = 0.5
        return result


@pytest.fixture
def pipeline_config() -> PipelineConfig:
    """Create a test pipeline configuration."""
    return PipelineConfig(
        device_id="test-device",
        sample_rate=16000,
        channels=1,
        max_buffer_size=16000 * 5,
        health_report_interval_ms=100.0,
        max_consecutive_errors=3,
    )


@pytest.fixture
def mock_pipeline(pipeline_config: PipelineConfig) -> MockAudioPipeline:
    """Create a mock audio pipeline."""
    return MockAudioPipeline(pipeline_config)


class TestPipelineConfig:
    """Tests for PipelineConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = PipelineConfig()

        assert config.device_id is None
        assert config.sample_rate == 16000
        assert config.channels == 1
        assert config.max_buffer_size == 16000 * 5
        assert config.health_report_interval_ms == 1000.0
        assert config.max_consecutive_errors == 5

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = PipelineConfig(
            device_id="custom-device",
            sample_rate=48000,
            channels=2,
            max_buffer_size=48000 * 10,
        )

        assert config.device_id == "custom-device"
        assert config.sample_rate == 48000
        assert config.channels == 2
        assert config.max_buffer_size == 48000 * 10


class TestPipelineHealth:
    """Tests for PipelineHealth metrics."""

    def test_default_health(self) -> None:
        """Test default health state."""
        health = PipelineHealth()

        assert health.state == PipelineState.IDLE
        assert health.frames_captured == 0
        assert health.frames_dropped == 0
        assert health.buffer_underruns == 0
        assert health.buffer_overruns == 0
        assert health.device_errors == 0
        assert health.device_reconnects == 0
        assert health.average_latency_ms == 0.0
        assert health.current_rms == 0.0
        assert health.peak_rms == 0.0
        assert health.is_speech_active is False

    def test_health_to_dict(self) -> None:
        """Test health serialization to dict."""
        health = PipelineHealth(
            state=PipelineState.RUNNING,
            frames_captured=1000,
            frames_dropped=10,
            current_rms=0.123456,
            peak_rms=0.987654,
        )

        data = health.to_dict()

        assert data["state"] == "RUNNING"
        assert data["frames_captured"] == 1000
        assert data["frames_dropped"] == 10
        assert isinstance(data["current_rms"], float)
        assert isinstance(data["peak_rms"], float)


class TestAudioPipelineState:
    """Tests for pipeline state management."""

    @pytest.mark.asyncio
    async def test_initial_state(self, mock_pipeline: MockAudioPipeline) -> None:
        """Test initial pipeline state."""
        assert mock_pipeline.state == PipelineState.IDLE
        assert not mock_pipeline.is_running
        assert not mock_pipeline.is_paused
        assert not mock_pipeline.is_stopped

    @pytest.mark.asyncio
    async def test_start_transition(self, mock_pipeline: MockAudioPipeline) -> None:
        """Test starting the pipeline."""
        await mock_pipeline.start()

        assert mock_pipeline.state == PipelineState.RUNNING
        assert mock_pipeline.is_running
        assert mock_pipeline.initialized

        await mock_pipeline.stop()

    @pytest.mark.asyncio
    async def test_stop_transition(self, mock_pipeline: MockAudioPipeline) -> None:
        """Test stopping the pipeline."""
        await mock_pipeline.start()
        await mock_pipeline.stop()

        assert mock_pipeline.state == PipelineState.STOPPED
        assert mock_pipeline.is_stopped
        assert not mock_pipeline.initialized

    @pytest.mark.asyncio
    async def test_pause_resume(self, mock_pipeline: MockAudioPipeline) -> None:
        """Test pause and resume functionality."""
        await mock_pipeline.start()

        await mock_pipeline.pause()
        assert mock_pipeline.state == PipelineState.PAUSED
        assert mock_pipeline.is_paused

        await mock_pipeline.resume()
        assert mock_pipeline.state == PipelineState.RUNNING
        assert not mock_pipeline.is_paused

        await mock_pipeline.stop()

    @pytest.mark.asyncio
    async def test_invalid_state_transitions(self, mock_pipeline: MockAudioPipeline) -> None:
        """Test invalid state transitions raise errors."""
        # Cannot pause when not running
        with pytest.raises(RuntimeError, match="Cannot pause from state"):
            await mock_pipeline.pause()

        await mock_pipeline.start()

        # Cannot resume when not paused
        with pytest.raises(RuntimeError, match="Cannot resume from state"):
            await mock_pipeline.resume()

        await mock_pipeline.stop()

        # Cannot start when already stopped (need to reset)
        # Note: This depends on implementation - may or may not be allowed


class TestAudioPipelineCapture:
    """Tests for audio capture functionality."""

    @pytest.mark.asyncio
    async def test_capture_frames(self, mock_pipeline: MockAudioPipeline) -> None:
        """Test that frames are captured."""
        await mock_pipeline.start()

        # Wait for some frames to be captured
        await asyncio.sleep(0.1)

        await mock_pipeline.stop()

        assert len(mock_pipeline.captured_frames) > 0
        assert mock_pipeline.health.frames_captured > 0

    @pytest.mark.asyncio
    async def test_read_audio(self, mock_pipeline: MockAudioPipeline) -> None:
        """Test reading audio from output queue."""
        await mock_pipeline.start()

        # Wait for a frame
        await asyncio.sleep(0.05)

        frame = await mock_pipeline.read(timeout=0.5)

        await mock_pipeline.stop()

        assert frame is not None
        assert isinstance(frame, np.ndarray)

    @pytest.mark.asyncio
    async def test_read_timeout(self, mock_pipeline: MockAudioPipeline) -> None:
        """Test read timeout when no data available."""
        # Don't start the pipeline
        frame = await mock_pipeline.read(timeout=0.1)
        assert frame is None


class TestAudioPipelineHealth:
    """Tests for health monitoring."""

    @pytest.mark.asyncio
    async def test_health_updates(self, mock_pipeline: MockAudioPipeline) -> None:
        """Test health metrics are updated during capture."""
        await mock_pipeline.start()
        await asyncio.sleep(0.1)
        await mock_pipeline.stop()

        health = mock_pipeline.get_health()
        assert health.frames_captured > 0

    @pytest.mark.asyncio
    async def test_latency_tracking(self, mock_pipeline: MockAudioPipeline) -> None:
        """Test latency tracking."""
        mock_pipeline._latency_window.append(10.0)
        mock_pipeline._latency_window.append(20.0)

        mock_pipeline._update_health_metrics()

        assert mock_pipeline.health.average_latency_ms == 15.0

    def test_rms_calculation(self, mock_pipeline: MockAudioPipeline) -> None:
        """Test RMS calculation."""
        # Create audio with known RMS
        audio = np.ones(1000, dtype=np.float32) * 0.5

        rms = mock_pipeline._calculate_rms(audio)

        assert rms == pytest.approx(0.5, abs=0.01)
        assert mock_pipeline.health.current_rms == pytest.approx(0.5, abs=0.01)


class TestAudioPipelineRecovery:
    """Tests for error recovery."""

    @pytest.mark.asyncio
    async def test_error_recovery(self) -> None:
        """Test automatic error recovery."""
        error_count = 0

        class FailingPipeline(MockAudioPipeline):
            async def _capture_loop(self) -> None:
                nonlocal error_count
                if error_count < 2:
                    error_count += 1
                    raise RuntimeError(f"Simulated error {error_count}")
                # Succeed after 2 failures
                await super()._capture_loop()

        config = PipelineConfig(max_consecutive_errors=5)
        pipeline = FailingPipeline(config)

        await pipeline.start()
        await asyncio.sleep(0.1)
        await pipeline.stop()

        assert error_count == 2
        assert pipeline.health.device_errors == 2
        assert pipeline.health.device_reconnects > 0

    @pytest.mark.asyncio
    async def test_max_errors_exceeded(self) -> None:
        """Test pipeline stops after max errors exceeded."""

        class AlwaysFailingPipeline(MockAudioPipeline):
            async def _capture_loop(self) -> None:
                raise RuntimeError("Always fails")

        config = PipelineConfig(max_consecutive_errors=2)
        pipeline = AlwaysFailingPipeline(config)

        await pipeline.start()
        await asyncio.sleep(0.2)

        assert pipeline.state == PipelineState.ERROR


class TestAudioPipelineCallbacks:
    """Tests for pipeline callbacks."""

    @pytest.mark.asyncio
    async def test_state_change_callback(self) -> None:
        """Test state change callback is invoked."""
        state_changes: list[tuple[PipelineState, PipelineState]] = []

        def on_state_change(old: PipelineState, new: PipelineState) -> None:
            state_changes.append((old, new))

        config = PipelineConfig(on_state_change=on_state_change)
        pipeline = MockAudioPipeline(config)

        await pipeline.start()
        await pipeline.stop()

        assert len(state_changes) >= 2
        assert state_changes[0] == (PipelineState.IDLE, PipelineState.INITIALIZING)
        assert state_changes[-1][1] == PipelineState.STOPPED

    @pytest.mark.asyncio
    async def test_health_callback(self) -> None:
        """Test health update callback."""
        health_updates: list[PipelineHealth] = []

        def on_health_update(health: PipelineHealth) -> None:
            health_updates.append(health)

        config = PipelineConfig(
            on_health_update=on_health_update,
            health_report_interval_ms=50.0,
        )
        pipeline = MockAudioPipeline(config)

        await pipeline.start()
        await asyncio.sleep(0.15)
        await pipeline.stop()

        assert len(health_updates) >= 1

    @pytest.mark.asyncio
    async def test_error_callback(self) -> None:
        """Test error callback is invoked."""
        errors: list[Exception] = []

        def on_error(exc: Exception) -> None:
            errors.append(exc)

        class FailingPipeline(MockAudioPipeline):
            async def _capture_loop(self) -> None:
                raise RuntimeError("Test error")

        config = PipelineConfig(
            on_error=on_error,
            max_consecutive_errors=1,
        )
        pipeline = FailingPipeline(config)

        await pipeline.start()
        await asyncio.sleep(0.1)

        assert len(errors) == 1
        assert str(errors[0]) == "Test error"


class TestPipelineFactory:
    """Tests for pipeline factory."""

    @patch("app.audio.pipeline_factory.WisprPipeline")
    @patch("app.audio.pipeline_factory.SystemPipeline")
    def test_create_wispr_pipeline(self, mock_system: Mock, mock_wispr: Mock) -> None:
        """Test creating Wispr pipeline."""
        from app.audio.pipeline_factory import create_pipeline

        mock_instance = Mock()
        mock_wispr.return_value = mock_instance

        config = {"mode": "wispr", "device_id": "test"}
        pipeline = create_pipeline(config)

        mock_wispr.assert_called_once()
        assert pipeline == mock_instance

    @patch("app.audio.pipeline_factory.WisprPipeline")
    @patch("app.audio.pipeline_factory.SystemPipeline")
    def test_create_system_pipeline(self, mock_system: Mock, mock_wispr: Mock) -> None:
        """Test creating System pipeline."""
        from app.audio.pipeline_factory import create_pipeline

        mock_instance = Mock()
        mock_system.return_value = mock_instance

        config = {"mode": "system", "device_id": "test"}
        pipeline = create_pipeline(config)

        mock_system.assert_called_once()
        assert pipeline == mock_instance

    @patch("app.audio.pipeline_factory.WisprPipeline")
    @patch("app.audio.pipeline_factory.SystemPipeline")
    def test_create_pipeline_default_mode(self, mock_system: Mock, mock_wispr: Mock) -> None:
        """Test pipeline factory defaults to system mode."""
        from app.audio.pipeline_factory import create_pipeline

        mock_instance = Mock()
        mock_system.return_value = mock_instance

        config = {"device_id": "test"}  # No mode specified
        pipeline = create_pipeline(config)

        mock_system.assert_called_once()


class TestAudioProcessing:
    """Tests for audio processing utilities."""

    def test_resample_audio(self) -> None:
        """Test audio resampling."""
        from app.audio.audio_processing import resample_audio

        # Create 1 second of 16kHz audio
        audio_16k = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 16000))

        # Resample to 8kHz
        audio_8k = resample_audio(audio_16k, 16000, 8000)

        assert len(audio_8k) == 8000

    def test_normalize_audio(self) -> None:
        """Test audio normalization."""
        from app.audio.audio_processing import normalize_audio

        audio = np.array([0.0, 0.5, 1.0, 0.5, 0.0], dtype=np.float32)

        normalized = normalize_audio(audio, target_db=-20)

        # Peak should be at target_db
        assert np.max(normalized) <= 10 ** (-20 / 20)

    def test_apply_gain(self) -> None:
        """Test applying gain to audio."""
        from app.audio.audio_processing import apply_gain

        audio = np.ones(100, dtype=np.float32) * 0.5

        gained = apply_gain(audio, 6.0)  # +6dB

        # 6dB gain doubles the amplitude
        assert np.mean(gained) == pytest.approx(1.0, abs=0.01)

    def test_trim_silence(self) -> None:
        """Test silence trimming."""
        from app.audio.audio_processing import trim_silence

        # Create audio with silence at start and end
        silence = np.zeros(1000, dtype=np.float32)
        signal = np.ones(1000, dtype=np.float32) * 0.5
        audio = np.concatenate([silence, signal, silence])

        trimmed = trim_silence(audio, threshold_db=-40)

        assert len(trimmed) < len(audio)
        assert len(trimmed) >= len(signal)
