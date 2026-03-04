"""Unit tests for the VAD (Voice Activity Detection) system.

Tests cover:
- VAD configuration
- State machine transitions
- Speech segment detection
- Adaptive thresholding
- Performance metrics
"""

from __future__ import annotations

import time
from unittest.mock import Mock

import numpy as np
import pytest

from app.audio.vad_optimized import (
    VADMode,
    VADState,
    VADConfig,
    SpeechSegment,
    VADMetrics,
    OptimizedVAD,
    NoiseProfiler,
    SpeechSegmenter,
    create_vad,
    detect_speech_regions,
)


class TestVADConfig:
    """Tests for VADConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = VADConfig()

        assert config.threshold_db == -40.0
        assert config.min_silence_ms == 300
        assert config.speech_pad_ms == 200
        assert config.hysteresis_ms == 100.0
        assert config.min_speech_ms == 150
        assert config.adaptive_alpha == 0.95

    def test_hotkey_mode(self) -> None:
        """Test hotkey mode configuration."""
        config = VADConfig.hotkey_mode()

        assert config.threshold_db == -35.0  # More sensitive
        assert config.min_silence_ms == 200  # Faster end detection
        assert config.speech_pad_ms == 100  # Minimal padding
        assert config.hysteresis_ms == 50.0  # Quick transitions
        assert config.min_speech_ms == 100  # Capture short utterances

    def test_system_mode(self) -> None:
        """Test system mode configuration."""
        config = VADConfig.system_mode()

        assert config.threshold_db == -40.0  # Balanced
        assert config.min_silence_ms == 500  # Longer silence
        assert config.speech_pad_ms == 200  # Standard padding
        assert config.hysteresis_ms == 150.0  # Stable transitions
        assert config.min_speech_ms == 250  # Filter short noises


class TestSpeechSegment:
    """Tests for SpeechSegment dataclass."""

    def test_segment_properties(self) -> None:
        """Test speech segment properties."""
        audio = np.ones(16000, dtype=np.float32)  # 1 second at 16kHz
        segment = SpeechSegment(
            start_sample=0,
            end_sample=16000,
            audio=audio,
            confidence=0.85,
            padding_ms=100,
        )

        assert segment.duration_ms == pytest.approx(1000.0, abs=1.0)
        assert segment.start_ms == 0.0
        assert segment.end_ms == pytest.approx(1000.0, abs=1.0)


class TestVADMetrics:
    """Tests for VADMetrics."""

    def test_default_values(self) -> None:
        """Test default metric values."""
        metrics = VADMetrics()

        assert metrics.total_samples == 0
        assert metrics.speech_samples == 0
        assert metrics.silence_samples == 0
        assert metrics.transitions == 0
        assert metrics.avg_processing_time_ms == 0.0

    def test_speech_ratio(self) -> None:
        """Test speech ratio calculation."""
        metrics = VADMetrics()
        metrics.total_samples = 16000
        metrics.speech_samples = 8000
        metrics.silence_samples = 8000

        assert metrics.speech_ratio == 0.5

    def test_speech_ratio_empty(self) -> None:
        """Test speech ratio when no samples."""
        metrics = VADMetrics()
        assert metrics.speech_ratio == 0.0

    def test_add_processing_time(self) -> None:
        """Test adding processing time samples."""
        metrics = VADMetrics()

        metrics.add_processing_time(0.5)
        metrics.add_processing_time(1.5)

        assert metrics.avg_processing_time_ms == 1.0

    def test_to_dict(self) -> None:
        """Test metrics serialization."""
        metrics = VADMetrics()
        metrics.total_samples = 16000
        metrics.speech_samples = 8000
        metrics.transitions = 2

        data = metrics.to_dict()

        assert data["total_samples"] == 16000
        assert data["speech_samples"] == 8000
        assert data["transitions"] == 2
        assert "speech_ratio" in data


class TestNoiseProfiler:
    """Tests for NoiseProfiler."""

    def test_init(self) -> None:
        """Test noise profiler initialization."""
        profiler = NoiseProfiler()

        assert profiler.window_size == 50
        assert profiler.alpha == 0.95
        assert profiler.noise_floor_db == -60.0

    def test_update_during_silence(self) -> None:
        """Test update during silence."""
        profiler = NoiseProfiler()

        # Update with silence energy
        offset = profiler.update(-50.0, is_speech=False)

        # Noise estimate should update
        assert profiler.noise_estimate_db > -60.0
        assert len(profiler.energy_history) == 1

    def test_update_during_speech(self) -> None:
        """Test update during speech."""
        profiler = NoiseProfiler()

        # Set initial noise estimate
        profiler.noise_estimate_db = -50.0

        # Update during speech - noise estimate should not change much
        offset = profiler.update(-30.0, is_speech=True)

        # Noise estimate should remain similar
        assert profiler.noise_estimate_db == pytest.approx(-50.0, abs=1.0)

    def test_peak_estimate_decay(self) -> None:
        """Test peak estimate decay."""
        profiler = NoiseProfiler()

        # Set high peak
        profiler.peak_estimate_db = -20.0

        # Update with lower energy
        profiler.update(-50.0, is_speech=False)

        # Peak should decay
        assert profiler.peak_estimate_db < -20.0

    def test_get_stats(self) -> None:
        """Test statistics retrieval."""
        profiler = NoiseProfiler()
        profiler.update(-50.0, is_speech=False)

        stats = profiler.get_stats()

        assert "noise_estimate_db" in stats
        assert "peak_estimate_db" in stats
        assert "snr_estimate_db" in stats
        assert "history_samples" in stats

    def test_reset(self) -> None:
        """Test profiler reset."""
        profiler = NoiseProfiler()
        profiler.update(-50.0, is_speech=False)

        profiler.reset()

        assert len(profiler.energy_history) == 0
        assert profiler.noise_estimate_db == profiler.noise_floor_db


class TestOptimizedVAD:
    """Tests for OptimizedVAD."""

    def test_init_defaults(self) -> None:
        """Test VAD initialization with defaults."""
        vad = OptimizedVAD()

        assert vad.mode == VADMode.SYSTEM
        assert vad.sample_rate == 16000
        assert vad.config is not None
        assert vad.state == VADState.SILENCE
        assert vad.metrics is not None

    def test_init_hotkey_mode(self) -> None:
        """Test VAD initialization in hotkey mode."""
        vad = OptimizedVAD(mode=VADMode.HOTKEY)

        assert vad.mode == VADMode.HOTKEY
        assert vad.config.threshold_db == -35.0

    def test_init_custom_config(self) -> None:
        """Test VAD initialization with custom config."""
        custom_config = VADConfig(threshold_db=-30.0)
        vad = OptimizedVAD(config=custom_config)

        assert vad.config.threshold_db == -30.0

    def test_process_frame_silence(self, mock_audio_data: np.ndarray) -> None:
        """Test processing silent frame."""
        vad = OptimizedVAD()

        state, segment = vad.process_frame(mock_audio_data)

        assert state == VADState.SILENCE
        assert segment is None
        assert vad.metrics.total_samples == len(mock_audio_data)

    def test_process_frame_speech_detection(self, sample_rate: int) -> None:
        """Test speech detection."""
        vad = OptimizedVAD(sample_rate=sample_rate, enable_adaptive=False)

        # Create loud audio
        loud_audio = np.ones(sample_rate, dtype=np.float32) * 0.5

        state, segment = vad.process_frame(loud_audio)

        # Should detect speech
        assert state == VADState.SPEECH

    def test_reset(self, mock_audio_data: np.ndarray) -> None:
        """Test VAD reset."""
        vad = OptimizedVAD()

        # Process some audio
        vad.process_frame(mock_audio_data)
        assert vad.metrics.total_samples > 0

        # Reset
        vad.reset()

        assert vad.state == VADState.SILENCE
        assert vad.metrics.total_samples == 0

    def test_set_mode(self) -> None:
        """Test mode switching."""
        vad = OptimizedVAD(mode=VADMode.SYSTEM)
        assert vad.mode == VADMode.SYSTEM
        assert vad.config.threshold_db == -40.0

        vad.set_mode(VADMode.HOTKEY)

        assert vad.mode == VADMode.HOTKEY
        assert vad.config.threshold_db == -35.0

    def test_get_metrics(self) -> None:
        """Test metrics retrieval."""
        vad = OptimizedVAD()

        metrics = vad.get_metrics()

        assert isinstance(metrics, VADMetrics)


class TestSpeechSegmenter:
    """Tests for SpeechSegmenter."""

    def test_init(self) -> None:
        """Test segmenter initialization."""
        segmenter = SpeechSegmenter()

        assert segmenter.min_duration_ms == 150.0
        assert segmenter.max_duration_ms == 30000.0
        assert segmenter.confidence_threshold == 0.5
        assert segmenter.merge_gap_ms == 200.0

    def test_add_valid_segment(self) -> None:
        """Test adding a valid segment."""
        segmenter = SpeechSegmenter()

        audio = np.ones(16000, dtype=np.float32)  # 1 second
        segment = SpeechSegment(
            start_sample=0,
            end_sample=16000,
            audio=audio,
            confidence=0.8,
        )

        result = segmenter.add_segment(segment)

        # First segment should not finalize any segments
        assert len(result) == 0
        assert len(segmenter.pending_segments) == 1

    def test_finalize_segments(self) -> None:
        """Test finalizing segments."""
        segmenter = SpeechSegmenter()

        # Add a valid segment
        audio = np.ones(16000, dtype=np.float32)
        segment = SpeechSegment(
            start_sample=0,
            end_sample=16000,
            audio=audio,
            confidence=0.8,
        )
        segmenter.add_segment(segment)

        # Finalize
        finalized = segmenter.finalize()

        assert len(finalized) == 1
        assert len(segmenter.pending_segments) == 0

    def test_filter_short_segments(self) -> None:
        """Test filtering of short segments."""
        segmenter = SpeechSegmenter(min_duration_ms=500.0)

        # Add a short segment (100ms)
        audio = np.ones(1600, dtype=np.float32)
        segment = SpeechSegment(
            start_sample=0,
            end_sample=1600,
            audio=audio,
            confidence=0.8,
        )
        segmenter.add_segment(segment)

        # Finalize
        finalized = segmenter.finalize()

        # Should be filtered out
        assert len(finalized) == 0

    def test_filter_low_confidence(self) -> None:
        """Test filtering of low confidence segments."""
        segmenter = SpeechSegmenter(confidence_threshold=0.5)

        # Add a low confidence segment
        audio = np.ones(16000, dtype=np.float32)
        segment = SpeechSegment(
            start_sample=0,
            end_sample=16000,
            audio=audio,
            confidence=0.3,  # Below threshold
        )
        segmenter.add_segment(segment)

        # Finalize
        finalized = segmenter.finalize()

        # Should be filtered out
        assert len(finalized) == 0

    def test_reset(self) -> None:
        """Test segmenter reset."""
        segmenter = SpeechSegmenter()

        audio = np.ones(16000, dtype=np.float32)
        segment = SpeechSegment(
            start_sample=0,
            end_sample=16000,
            audio=audio,
            confidence=0.8,
        )
        segmenter.add_segment(segment)

        segmenter.reset()

        assert len(segmenter.pending_segments) == 0

    def test_finalize_single_pending_segment(self) -> None:
        """Finalize should not drop the last valid pending segment."""
        segmenter = SpeechSegmenter()
        segment = SpeechSegment(
            start_sample=0,
            end_sample=16000,
            audio=np.ones(16000, dtype=np.float32),
            confidence=0.8,
        )
        segmenter.add_segment(segment)

        finalized = segmenter.finalize()

        assert len(finalized) == 1
        assert finalized[0].confidence == pytest.approx(0.8)

    def test_hysteresis_block_does_not_mutate_speech_start_or_buffer(self) -> None:
        """Blocked transitions should not overwrite speech bookkeeping."""
        vad = OptimizedVAD(
            mode=VADMode.HOTKEY,
            config=VADConfig.hotkey_mode(),
            enable_adaptive=False,
        )
        vad.last_transition_time = time.perf_counter() * 1000
        frame = np.ones(vad._frame_size_samples, dtype=np.float32) * 0.5

        state, segment = vad.process_frame(frame)

        assert state == VADState.SILENCE
        assert segment is None
        assert vad.speech_start_sample == 0
        assert len(vad.pre_buffer) == 0


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_vad_system_mode(self) -> None:
        """Test creating VAD in system mode."""
        vad = create_vad("system")

        assert isinstance(vad, OptimizedVAD)
        assert vad.mode == VADMode.SYSTEM

    def test_create_vad_hotkey_mode(self) -> None:
        """Test creating VAD in hotkey mode."""
        vad = create_vad("hotkey")

        assert isinstance(vad, OptimizedVAD)
        assert vad.mode == VADMode.HOTKEY

    def test_detect_speech_regions(self) -> None:
        """Test speech region detection."""
        # Create audio with speech regions
        audio = np.zeros(16000 * 3, dtype=np.float32)  # 3 seconds
        # Add loud region
        audio[8000:16000] = 0.5  # 0.5s - 1s

        regions = detect_speech_regions(audio, sample_rate=16000, mode="system")

        assert isinstance(regions, list)
        # May or may not detect depending on threshold

    def test_detect_speech_regions_empty(self) -> None:
        """Test speech region detection with silence."""
        audio = np.zeros(16000, dtype=np.float32)

        regions = detect_speech_regions(audio, sample_rate=16000)

        assert regions == []


class TestVADRegressionGuards:
    """Regression guards for recent VAD fixes."""

    def test_first_successful_speech_transition_buffers_audio_once(self) -> None:
        """First accepted speech frame should only be buffered once."""
        config = VADConfig.hotkey_mode()
        config.hysteresis_ms = 0.0
        vad = OptimizedVAD(config=config)

        audio = np.ones(1600, dtype=np.float32) * 0.5

        state, segment = vad.process_frame(audio)

        assert segment is None
        assert state == VADState.SPEECH
        assert len(vad.pre_buffer) == 1
        np.testing.assert_array_equal(vad.pre_buffer[0], audio)
        assert vad.metrics.speech_samples == len(audio)
