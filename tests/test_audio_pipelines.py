"""Unit tests for the dual audio pipeline system.

Tests cover:
- Pipeline base class functionality
- Wispr pipeline (hotkey/mic mode)
- System pipeline (loopback mode)
- Pipeline factory
- Pipeline manager
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

# Mock soundcard before importing pipeline modules
sys.modules["soundcard"] = MagicMock()
sys.modules["pyaudio"] = MagicMock()

# Import pipeline components
from app.audio.pipeline_base import (
    AudioPipeline,
    PipelineConfig,
    PipelineHealth,
    PipelineMode,
    PipelineState,
)
from app.audio.pipeline_factory import (
    PipelineManager,
    PipelineType,
    _detect_pipeline_type,
    create_pipeline,
)
from app.audio.system_pipeline import (
    RingBuffer,
    SilenceDetector,
    SystemPipeline,
    SystemPipelineConfig,
)
from app.audio.wispr_pipeline import (
    StreamingVAD,
    WisprPipeline,
    WisprPipelineConfig,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_audio() -> np.ndarray:
    """Generate sample audio data."""
    np.random.seed(42)
    return np.random.randn(800).astype(np.float32) * 0.1


@pytest.fixture
def loud_audio() -> np.ndarray:
    """Generate loud audio (speech-like)."""
    t = np.linspace(0, 0.05, 800)  # 50ms at 16kHz
    return np.sin(2 * np.pi * 440 * t).astype(np.float32) * 0.5


@pytest.fixture
def quiet_audio() -> np.ndarray:
    """Generate quiet audio (silence-like)."""
    return np.random.randn(800).astype(np.float32) * 0.001


@pytest.fixture
def mock_backend() -> MagicMock:
    """Create a mock audio backend."""
    backend = MagicMock()
    backend.backend_name = "MockBackend"
    backend.runtime_sample_rate = 16000
    backend.runtime_channels = 1
    return backend


@pytest.fixture
def base_config() -> PipelineConfig:
    """Create a base pipeline config."""
    return PipelineConfig(
        device_id="test-device",
        sample_rate=16000,
        channels=1,
        max_buffer_size=16000 * 5,
    )


@pytest.fixture
def wispr_config() -> WisprPipelineConfig:
    """Create a Wispr pipeline config."""
    return WisprPipelineConfig(
        device_id="test-mic",
        sample_rate=16000,
        channels=1,
        frame_duration_ms=50.0,
        pre_buffer_duration_ms=200.0,
    )


@pytest.fixture
def system_config() -> SystemPipelineConfig:
    """Create a System pipeline config."""
    return SystemPipelineConfig(
        device_id="test-loopback",
        sample_rate=16000,
        channels=2,
        buffer_duration_ms=500.0,
        buffer_count=8,
    )


# ============================================================================
# Pipeline Base Tests
# ============================================================================


class TestPipelineBase:
    """Test the AudioPipeline base class."""

    @pytest.mark.asyncio
    async def test_initial_state(self, base_config: PipelineConfig) -> None:
        """Test pipeline starts in IDLE state."""

        class TestPipeline(AudioPipeline):
            def _get_mode(self) -> PipelineMode:
                return PipelineMode.WISPR

            async def _initialize_device(self) -> None:
                pass

            async def _capture_loop(self) -> None:
                pass

            async def _cleanup_device(self) -> None:
                pass

            def probe_device(self, *, duration: float, output_dir: Path) -> Any:
                return MagicMock()

        pipeline = TestPipeline(base_config)
        assert pipeline.state == PipelineState.IDLE
        assert not pipeline.is_running
        assert not pipeline.is_paused
        assert not pipeline.is_stopped

    @pytest.mark.asyncio
    async def test_state_transitions(self, base_config: PipelineConfig) -> None:
        """Test state transitions work correctly."""
        state_changes: list[tuple[PipelineState, PipelineState]] = []

        class TestPipeline(AudioPipeline):
            def _get_mode(self) -> PipelineMode:
                return PipelineMode.WISPR

            async def _initialize_device(self) -> None:
                pass

            async def _capture_loop(self) -> None:
                await asyncio.sleep(0.1)

            async def _cleanup_device(self) -> None:
                pass

            def probe_device(self, *, duration: float, output_dir: Path) -> Any:
                return MagicMock()

        config = PipelineConfig(
            device_id="test",
            sample_rate=16000,
            on_state_change=lambda old, new: state_changes.append((old, new)),
        )

        pipeline = TestPipeline(config)

        with patch.object(pipeline, "_initialize_device", new=AsyncMock()):
            with patch.object(pipeline, "_cleanup_device", new=AsyncMock()):
                await pipeline.start()
                assert pipeline.state == PipelineState.RUNNING

                await pipeline.pause()
                assert pipeline.state == PipelineState.PAUSED

                await pipeline.resume()
                assert pipeline.state == PipelineState.RUNNING

                await pipeline.stop()
                assert pipeline.state == PipelineState.STOPPED

    @pytest.mark.asyncio
    async def test_health_metrics(self, base_config: PipelineConfig) -> None:
        """Test health metrics are tracked."""
        health_updates: list[PipelineHealth] = []

        class TestPipeline(AudioPipeline):
            def _get_mode(self) -> PipelineMode:
                return PipelineMode.WISPR

            async def _initialize_device(self) -> None:
                pass

            async def _capture_loop(self) -> None:
                await asyncio.sleep(0.05)

            async def _cleanup_device(self) -> None:
                pass

            def probe_device(self, *, duration: float, output_dir: Path) -> Any:
                return MagicMock()

        config = PipelineConfig(
            device_id="test",
            sample_rate=16000,
            on_health_update=lambda h: health_updates.append(h),
            health_report_interval_ms=50.0,
        )

        pipeline = TestPipeline(config)

        with patch.object(pipeline, "_initialize_device", new=AsyncMock()):
            with patch.object(pipeline, "_cleanup_device", new=AsyncMock()):
                await pipeline.start()
                await asyncio.sleep(0.1)
                await pipeline.stop()

                # Check that health updates were received
                assert len(health_updates) >= 1
                # Verify health has correct structure
                for health in health_updates:
                    assert isinstance(health.state, PipelineState)
                    assert hasattr(health, "frames_captured")
                    assert hasattr(health, "current_rms")


# ============================================================================
# Wispr Pipeline Tests
# ============================================================================


class TestWisprPipeline:
    """Test the Wispr (hotkey/mic) pipeline."""

    def test_mode(self, wispr_config: WisprPipelineConfig) -> None:
        """Test Wispr pipeline returns correct mode."""
        with patch("app.audio.wispr_pipeline.open_audio_backend"):
            pipeline = WisprPipeline(wispr_config)
            assert pipeline._get_mode() == PipelineMode.WISPR

    def test_frame_size_calculation(self, wispr_config: WisprPipelineConfig) -> None:
        """Test frame size is calculated correctly."""
        with patch("app.audio.wispr_pipeline.open_audio_backend"):
            pipeline = WisprPipeline(wispr_config)
            # 50ms at 16kHz = 800 samples
            assert pipeline.frame_size == 800
            # 200ms pre-buffer = 4 frames
            assert pipeline.pre_buffer_frames == 4

    @pytest.mark.asyncio
    async def test_initialize_device(
        self, wispr_config: WisprPipelineConfig, mock_backend: MagicMock
    ) -> None:
        """Test device initialization."""
        mock_selection = MagicMock()
        mock_selection.backend = mock_backend

        with patch("app.audio.wispr_pipeline.open_audio_backend", return_value=mock_selection):
            pipeline = WisprPipeline(wispr_config)

            # Mock the executor
            loop = asyncio.get_event_loop()
            loop.run_in_executor = AsyncMock(return_value=mock_selection)

            await pipeline._initialize_device()
            assert pipeline._backend == mock_backend


class TestStreamingVAD:
    """Test the Streaming VAD component."""

    def test_speech_detection(self, loud_audio: np.ndarray) -> None:
        """Test VAD detects speech correctly."""
        vad = StreamingVAD(
            threshold_db=-40.0,
            hysteresis_ms=100.0,
            min_silence_ms=300.0,
            sample_rate=16000,
        )

        # Quiet first (simulate silence)
        quiet = np.random.randn(800).astype(np.float32) * 0.001
        is_speech, is_start = vad.process(quiet)
        assert not is_speech
        assert not is_start

        # Loud (simulate speech start)
        is_speech, is_start = vad.process(loud_audio)
        # May need multiple frames due to hysteresis
        for _ in range(3):
            is_speech, is_start = vad.process(loud_audio)

        assert is_speech

    def test_speech_end_detection(self, loud_audio: np.ndarray, quiet_audio: np.ndarray) -> None:
        """Test VAD detects speech end correctly."""
        vad = StreamingVAD(
            threshold_db=-40.0,
            hysteresis_ms=50.0,
            min_silence_ms=50.0,
            sample_rate=16000,
        )

        # Start speech
        for _ in range(3):
            vad.process(loud_audio)

        # Silence
        for _ in range(5):
            is_speech, _ = vad.process(quiet_audio)

        assert not is_speech


# ============================================================================
# System Pipeline Tests
# ============================================================================


class TestSystemPipeline:
    """Test the System (loopback) pipeline."""

    def test_mode(self, system_config: SystemPipelineConfig) -> None:
        """Test System pipeline returns correct mode."""
        with patch("app.audio.system_pipeline.open_audio_backend"):
            pipeline = SystemPipeline(system_config)
            assert pipeline._get_mode() == PipelineMode.SYSTEM

    def test_buffer_configuration(self, system_config: SystemPipelineConfig) -> None:
        """Test buffer configuration."""
        with patch("app.audio.system_pipeline.open_audio_backend"):
            pipeline = SystemPipeline(system_config)
            # 500ms at 16kHz = 8000 samples
            assert pipeline.buffer_size == 8000

    @pytest.mark.asyncio
    async def test_ring_buffer(self) -> None:
        """Test RingBuffer operations."""
        buffer = RingBuffer(capacity=4, buffer_size=100)

        # Write data
        data1 = np.ones(100, dtype=np.float32)
        assert await buffer.write(data1)

        data2 = np.ones(100, dtype=np.float32) * 2
        assert await buffer.write(data2)

        # Read data
        result = await buffer.read()
        assert np.allclose(result, data1)

        result = await buffer.read()
        assert np.allclose(result, data2)

        # Buffer empty
        assert await buffer.read() is None

    @pytest.mark.asyncio
    async def test_ring_buffer_full(self) -> None:
        """Test RingBuffer handles full condition."""
        buffer = RingBuffer(capacity=2, buffer_size=100)

        assert await buffer.write(np.ones(100))
        assert await buffer.write(np.ones(100))

        # Buffer full
        assert not await buffer.write(np.ones(100))


class TestSilenceDetector:
    """Test the Silence Detector component."""

    def test_silence_detection(self, quiet_audio: np.ndarray) -> None:
        """Test silence detection."""
        detector = SilenceDetector(
            threshold_db=-40.0,
            silence_duration_ms=100.0,
            sample_rate=16000,
        )

        is_silence, duration = detector.process(quiet_audio)
        assert is_silence

    def test_speech_detection(self, loud_audio: np.ndarray) -> None:
        """Test non-silence (speech) detection."""
        detector = SilenceDetector(
            threshold_db=-40.0,
            silence_duration_ms=100.0,
            sample_rate=16000,
        )

        is_silence, duration = detector.process(loud_audio)
        assert not is_silence

    def test_silence_boundary(self) -> None:
        """Test silence boundary detection."""
        detector = SilenceDetector(
            threshold_db=-40.0,
            silence_duration_ms=50.0,  # Short for test
            sample_rate=16000,
        )

        # Quiet frames
        quiet = np.random.randn(800).astype(np.float32) * 0.001

        assert not detector.is_silence_boundary()

        # Add enough quiet frames
        for _ in range(5):
            detector.process(quiet)

        assert detector.is_silence_boundary()


# ============================================================================
# Pipeline Factory Tests
# ============================================================================


class TestPipelineFactory:
    """Test the pipeline factory."""

    def test_create_wispr_pipeline(self) -> None:
        """Test creating a Wispr pipeline."""
        with patch("app.audio.pipeline_factory._create_wispr_pipeline") as mock_create:
            mock_pipeline = MagicMock()
            mock_pipeline._get_mode.return_value = PipelineMode.WISPR
            mock_create.return_value = mock_pipeline

            pipeline = create_pipeline(
                PipelineType.WISPR,
                device_id="test-mic",
                sample_rate=16000,
            )

            assert pipeline == mock_pipeline
            mock_create.assert_called_once()

    def test_create_system_pipeline(self) -> None:
        """Test creating a System pipeline."""
        with patch("app.audio.pipeline_factory._create_system_pipeline") as mock_create:
            mock_pipeline = MagicMock()
            mock_pipeline._get_mode.return_value = PipelineMode.SYSTEM
            mock_create.return_value = mock_pipeline

            pipeline = create_pipeline(
                PipelineType.SYSTEM,
                device_id="test-loopback",
                sample_rate=16000,
            )

            assert pipeline == mock_pipeline
            mock_create.assert_called_once()

    def test_create_pipeline_string_type(self) -> None:
        """Test creating pipeline with string type."""
        with patch("app.audio.pipeline_factory._create_wispr_pipeline") as mock_create:
            mock_pipeline = MagicMock()
            mock_create.return_value = mock_pipeline

            pipeline = create_pipeline("wispr", device_id="test")
            assert pipeline == mock_pipeline

    def test_create_pipeline_invalid_type(self) -> None:
        """Test creating pipeline with invalid type raises error."""
        with pytest.raises(ValueError, match="Invalid pipeline type"):
            create_pipeline("invalid_type", device_id="test")


class TestPipelineTypeDetection:
    """Test automatic pipeline type detection."""

    def test_detect_loopback_device(self) -> None:
        """Test detection of loopback devices."""
        loopback_devices = [
            "Stereo Mix (Realtek)",
            "What U Hear",
            "CABLE Output",
            "Virtual Audio Cable",
            "WASAPI Loopback",
        ]

        for device in loopback_devices:
            result = _detect_pipeline_type(device)
            assert result == PipelineType.SYSTEM, f"Failed for {device}"

    def test_detect_microphone_device(self) -> None:
        """Test detection of microphone devices."""
        mic_devices = [
            "Microphone (Realtek)",
            "USB Microphone",
            "Headset Microphone",
            "Webcam Mic",
            "Built-in Microphone",
        ]

        for device in mic_devices:
            result = _detect_pipeline_type(device)
            assert result == PipelineType.WISPR, f"Failed for {device}"

    def test_detect_default_device(self) -> None:
        """Test detection with no device specified."""
        result = _detect_pipeline_type(None)
        assert result == PipelineType.WISPR


# ============================================================================
# Pipeline Manager Tests
# ============================================================================


class TestPipelineManager:
    """Test the Pipeline Manager."""

    @pytest.mark.asyncio
    async def test_create_pipeline(self) -> None:
        """Test creating a managed pipeline."""
        manager = PipelineManager()

        with patch("app.audio.pipeline_factory.create_pipeline") as mock_create:
            mock_pipeline = MagicMock()
            mock_pipeline._get_mode.return_value = PipelineMode.WISPR
            mock_pipeline.state = PipelineState.IDLE
            mock_pipeline.is_running = False
            mock_pipeline.is_paused = False
            mock_pipeline.health = PipelineHealth()
            mock_create.return_value = mock_pipeline

            pipeline = manager.create("test-1", PipelineType.WISPR, device_id="mic")

            assert pipeline == mock_pipeline
            assert "test-1" in manager.list_pipelines()

    def test_create_duplicate_pipeline(self) -> None:
        """Test creating duplicate pipeline raises error."""
        manager = PipelineManager()

        with patch("app.audio.pipeline_factory.create_pipeline") as mock_create:
            mock_pipeline = MagicMock()
            mock_pipeline._get_mode.return_value = PipelineMode.WISPR
            mock_create.return_value = mock_pipeline

            manager.create("test-1", PipelineType.WISPR)

            with pytest.raises(ValueError, match="already exists"):
                manager.create("test-1", PipelineType.WISPR)

    def test_get_pipeline_info(self) -> None:
        """Test getting pipeline information."""
        manager = PipelineManager()

        with patch("app.audio.pipeline_factory.create_pipeline") as mock_create:
            mock_pipeline = MagicMock()
            mock_pipeline._get_mode.return_value = PipelineMode.WISPR
            mock_pipeline.state = PipelineState.RUNNING
            mock_pipeline.is_running = True
            mock_pipeline.is_paused = False
            mock_pipeline.health = PipelineHealth(state=PipelineState.RUNNING)
            mock_create.return_value = mock_pipeline

            manager.create("test-1", PipelineType.WISPR, device_id="mic")
            info = manager.get_pipeline_info("test-1")

            assert info["id"] == "test-1"
            assert info["mode"] == "wispr"
            assert info["state"] == "RUNNING"

    @pytest.mark.asyncio
    async def test_start_stop_pipeline(self) -> None:
        """Test starting and stopping a pipeline."""
        manager = PipelineManager()

        mock_pipeline = MagicMock()
        mock_pipeline._get_mode.return_value = PipelineMode.WISPR
        mock_pipeline.start = AsyncMock()
        mock_pipeline.stop = AsyncMock()

        with patch("app.audio.pipeline_factory.create_pipeline", return_value=mock_pipeline):
            manager.create("test-1", PipelineType.WISPR)

            await manager.start("test-1")
            mock_pipeline.start.assert_called_once()

            await manager.stop("test-1")
            mock_pipeline.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_all_pipelines(self) -> None:
        """Test stopping all pipelines."""
        manager = PipelineManager()

        mock_pipeline1 = MagicMock()
        mock_pipeline1._get_mode.return_value = PipelineMode.WISPR
        mock_pipeline1.stop = AsyncMock()

        mock_pipeline2 = MagicMock()
        mock_pipeline2._get_mode.return_value = PipelineMode.SYSTEM
        mock_pipeline2.stop = AsyncMock()

        with patch(
            "app.audio.pipeline_factory.create_pipeline",
            side_effect=[mock_pipeline1, mock_pipeline2],
        ):
            manager.create("test-1", PipelineType.WISPR)
            manager.create("test-2", PipelineType.SYSTEM)

            await manager.stop_all()

            mock_pipeline1.stop.assert_called_once()
            mock_pipeline2.stop.assert_called_once()

    def test_remove_pipeline(self) -> None:
        """Test removing a pipeline from management."""
        manager = PipelineManager()

        with patch("app.audio.pipeline_factory.create_pipeline") as mock_create:
            mock_pipeline = MagicMock()
            mock_pipeline._get_mode.return_value = PipelineMode.WISPR
            mock_pipeline.is_running = False
            mock_create.return_value = mock_pipeline

            manager.create("test-1", PipelineType.WISPR)
            assert "test-1" in manager.list_pipelines()

            manager.remove("test-1")
            assert "test-1" not in manager.list_pipelines()

    def test_get_nonexistent_pipeline(self) -> None:
        """Test getting a nonexistent pipeline raises error."""
        manager = PipelineManager()

        with pytest.raises(KeyError, match="not found"):
            manager.get_pipeline_info("nonexistent")


# ============================================================================
# Integration Tests
# ============================================================================


class TestPipelineIntegration:
    """Integration tests for the pipeline system."""

    @pytest.mark.asyncio
    async def test_full_pipeline_lifecycle(self) -> None:
        """Test complete pipeline lifecycle."""
        manager = PipelineManager()

        mock_pipeline = MagicMock()
        mock_pipeline._get_mode.return_value = PipelineMode.WISPR
        mock_pipeline.start = AsyncMock()
        mock_pipeline.pause = AsyncMock()
        mock_pipeline.resume = AsyncMock()
        mock_pipeline.stop = AsyncMock()
        mock_pipeline.read = AsyncMock(return_value=np.ones(800))
        mock_pipeline.get_health.return_value = PipelineHealth()
        mock_pipeline.is_running = True
        mock_pipeline.is_paused = False
        mock_pipeline.state = PipelineState.RUNNING

        with patch("app.audio.pipeline_factory.create_pipeline", return_value=mock_pipeline):
            # Create
            pipeline = manager.create("lifecycle-test", PipelineType.WISPR)

            # Start
            await manager.start("lifecycle-test")

            # Pause
            await manager.pause("lifecycle-test")

            # Resume
            await manager.resume("lifecycle-test")

            # Read
            audio = await manager.read("lifecycle-test")
            assert audio is not None

            # Stop
            await manager.stop("lifecycle-test")

            # Remove
            manager.remove("lifecycle-test")

    def test_health_serialization(self) -> None:
        """Test health metrics can be serialized."""
        health = PipelineHealth(
            state=PipelineState.RUNNING,
            frames_captured=1000,
            frames_dropped=10,
            current_rms=0.5,
        )

        data = health.to_dict()

        assert data["state"] == "RUNNING"
        assert data["frames_captured"] == 1000
        assert data["frames_dropped"] == 10
        assert "current_rms" in data
