"""Optimized Voice Activity Detection with mode-specific settings.

This module provides production-grade VAD with:
- Mode-specific thresholds (Hotkey vs System)
- Adaptive thresholding based on ambient noise
- Hysteresis to prevent rapid on/off switching
- Pre/post speech padding
- Numba-optimized processing for real-time performance
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Try to import numba for optimization
try:
    from numba import jit, prange

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

    # Create no-op decorator for when numba is not available
    def jit(*args, **kwargs):
        def wrapper(func):
            return func

        return wrapper if args and callable(args[0]) else wrapper

    prange = range


class VADMode(Enum):
    """VAD operating modes."""

    HOTKEY = auto()  # Very sensitive, fast response
    SYSTEM = auto()  # Balanced, stable detection


class VADState(Enum):
    """Voice activity states."""

    SILENCE = auto()
    SPEECH = auto()
    TRANSITION = auto()


@dataclass
class VADConfig:
    """VAD configuration for a specific mode.

    Attributes:
        threshold_db: Energy threshold in dB for speech detection
        min_silence_ms: Minimum silence duration to end speech
        speech_pad_ms: Padding added before/after speech
        hysteresis_ms: Time delay to prevent rapid switching
        min_speech_ms: Minimum speech duration to consider valid
        adaptive_alpha: Smoothing factor for noise adaptation (0-1)
        noise_floor_db: Minimum noise floor in dB
        peak_hold_ms: Duration to hold peak level
    """

    threshold_db: float = -40.0
    min_silence_ms: int = 300
    speech_pad_ms: int = 200
    hysteresis_ms: float = 100.0
    min_speech_ms: int = 150
    adaptive_alpha: float = 0.95
    noise_floor_db: float = -60.0
    peak_hold_ms: int = 50

    # Mode-specific defaults
    @classmethod
    def hotkey_mode(cls) -> VADConfig:
        """Configuration optimized for hotkey-triggered dictation."""
        return cls(
            threshold_db=-35.0,  # Very sensitive
            min_silence_ms=200,  # Fast end detection
            speech_pad_ms=100,  # Minimal padding for low latency
            hysteresis_ms=50.0,  # Quick transitions
            min_speech_ms=100,  # Capture short utterances
            adaptive_alpha=0.90,  # Faster adaptation
            noise_floor_db=-55.0,
            peak_hold_ms=30,
        )

    @classmethod
    def system_mode(cls) -> VADConfig:
        """Configuration optimized for system audio capture."""
        return cls(
            threshold_db=-40.0,  # Balanced sensitivity
            min_silence_ms=500,  # Longer silence for stability
            speech_pad_ms=200,  # Standard padding
            hysteresis_ms=150.0,  # Stable transitions
            min_speech_ms=250,  # Filter out short noises
            adaptive_alpha=0.97,  # Slower, more stable adaptation
            noise_floor_db=-60.0,
            peak_hold_ms=100,
        )


@dataclass
class SpeechSegment:
    """Detected speech segment with metadata."""

    start_sample: int
    end_sample: int
    audio: NDArray[np.float32]
    confidence: float = 0.0
    padding_ms: int = 0

    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds."""
        return (self.end_sample - self.start_sample) / 16.0  # Assuming 16kHz

    @property
    def start_ms(self) -> float:
        """Start time in milliseconds."""
        return self.start_sample / 16.0

    @property
    def end_ms(self) -> float:
        """End time in milliseconds."""
        return self.end_sample / 16.0


@dataclass
class VADMetrics:
    """VAD performance metrics."""

    total_samples: int = 0
    speech_samples: int = 0
    silence_samples: int = 0
    transitions: int = 0
    avg_processing_time_ms: float = 0.0
    peak_level_db: float = -np.inf
    noise_floor_db: float = -np.inf
    current_threshold_db: float = -40.0
    adaptive_offset_db: float = 0.0

    processing_times: deque[float] = field(default_factory=lambda: deque(maxlen=100))

    def add_processing_time(self, ms: float) -> None:
        """Add a processing time sample."""
        self.processing_times.append(ms)
        self.avg_processing_time_ms = sum(self.processing_times) / len(self.processing_times)

    @property
    def speech_ratio(self) -> float:
        """Ratio of speech to total audio."""
        if self.total_samples == 0:
            return 0.0
        return self.speech_samples / self.total_samples

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "total_samples": self.total_samples,
            "speech_samples": self.speech_samples,
            "silence_samples": self.silence_samples,
            "transitions": self.transitions,
            "avg_processing_time_ms": round(self.avg_processing_time_ms, 3),
            "peak_level_db": round(self.peak_level_db, 2),
            "noise_floor_db": round(self.noise_floor_db, 2),
            "current_threshold_db": round(self.current_threshold_db, 2),
            "adaptive_offset_db": round(self.adaptive_offset_db, 2),
            "speech_ratio": round(self.speech_ratio, 3),
        }


# ============================================
# Numba-optimized core functions
# ============================================
if NUMBA_AVAILABLE:

    @jit(nopython=True, cache=True, fastmath=True)
    def _compute_energy_numba(audio: NDArray[np.float32]) -> float:
        """Compute RMS energy with Numba optimization."""
        n = audio.shape[0]
        if n == 0:
            return 0.0

        sum_sq = 0.0
        for i in prange(n):
            sum_sq += audio[i] * audio[i]

        return np.sqrt(sum_sq / n)

    @jit(nopython=True, cache=True, fastmath=True)
    def _compute_energy_batch_numba(
        audio: NDArray[np.float32],
        frame_size: int,
    ) -> NDArray[np.float32]:
        """Compute energy for multiple frames."""
        num_frames = len(audio) // frame_size
        energies = np.empty(num_frames, dtype=np.float32)

        for i in prange(num_frames):
            start = i * frame_size
            end = start + frame_size
            frame = audio[start:end]

            sum_sq = 0.0
            for j in range(frame_size):
                sum_sq += frame[j] * frame[j]

            energies[i] = np.sqrt(sum_sq / frame_size)

        return energies

    @jit(nopython=True, cache=True, fastmath=True)
    def _db_to_linear_numba(db: float) -> float:
        """Convert dB to linear amplitude."""
        return 10.0 ** (db / 20.0)

    @jit(nopython=True, cache=True, fastmath=True)
    def _linear_to_db_numba(linear: float) -> float:
        """Convert linear amplitude to dB."""
        if linear <= 0:
            return -100.0
        return 20.0 * np.log10(linear)
else:

    def _compute_energy_numba(audio: NDArray[np.float32]) -> float:
        """Fallback energy computation without Numba."""
        if len(audio) == 0:
            return 0.0
        return np.sqrt(np.mean(audio * audio))

    def _compute_energy_batch_numba(
        audio: NDArray[np.float32],
        frame_size: int,
    ) -> NDArray[np.float32]:
        """Fallback batch energy computation."""
        num_frames = len(audio) // frame_size
        energies = np.empty(num_frames, dtype=np.float32)

        for i in range(num_frames):
            start = i * frame_size
            end = start + frame_size
            frame = audio[start:end]
            energies[i] = np.sqrt(np.mean(frame * frame))

        return energies

    def _db_to_linear_numba(db: float) -> float:
        """Convert dB to linear amplitude."""
        return 10.0 ** (db / 20.0)

    def _linear_to_db_numba(linear: float) -> float:
        """Convert linear amplitude to dB."""
        if linear <= 1e-10:
            return -100.0
        return 20.0 * np.log10(linear)


class NoiseProfiler:
    """Profiles ambient noise for adaptive thresholding."""

    def __init__(
        self,
        window_size: int = 50,
        alpha: float = 0.95,
        noise_floor_db: float = -60.0,
    ):
        self.window_size = window_size
        self.alpha = alpha
        self.noise_floor_db = noise_floor_db

        self.energy_history: deque[float] = deque(maxlen=window_size)
        self.noise_estimate_db = noise_floor_db
        self.peak_estimate_db = noise_floor_db
        self.snr_estimate_db = 0.0

    def update(self, energy_db: float, is_speech: bool = False) -> float:
        """Update noise profile with new energy reading.

        Args:
            energy_db: Current energy level in dB
            is_speech: Whether this frame contains speech

        Returns:
            Adaptive threshold offset in dB
        """
        # Only update noise estimate during silence
        if not is_speech:
            self.energy_history.append(energy_db)

            # Update noise estimate with exponential smoothing
            self.noise_estimate_db = (
                self.alpha * self.noise_estimate_db + (1 - self.alpha) * energy_db
            )

            # Clamp to floor
            self.noise_estimate_db = max(self.noise_estimate_db, self.noise_floor_db)

        # Update peak estimate (decays slowly, rises quickly)
        if energy_db > self.peak_estimate_db:
            self.peak_estimate_db = energy_db
        else:
            self.peak_estimate_db = 0.99 * self.peak_estimate_db + 0.01 * energy_db

        # Calculate SNR
        self.snr_estimate_db = self.peak_estimate_db - self.noise_estimate_db

        # Return adaptive offset (higher noise = higher threshold)
        return self._calculate_offset()

    def _calculate_offset(self) -> float:
        """Calculate adaptive threshold offset based on noise level."""
        # Base offset increases with noise level
        noise_above_floor = self.noise_estimate_db - self.noise_floor_db

        # Non-linear scaling: more offset for noisier environments
        if noise_above_floor < 10:
            offset = 0.0
        elif noise_above_floor < 20:
            offset = 2.0
        elif noise_above_floor < 30:
            offset = 5.0
        else:
            offset = 8.0

        return offset

    def get_stats(self) -> dict:
        """Get current noise profile statistics."""
        return {
            "noise_estimate_db": round(self.noise_estimate_db, 2),
            "peak_estimate_db": round(self.peak_estimate_db, 2),
            "snr_estimate_db": round(self.snr_estimate_db, 2),
            "history_samples": len(self.energy_history),
        }

    def reset(self) -> None:
        """Reset noise profile."""
        self.energy_history.clear()
        self.noise_estimate_db = self.noise_floor_db
        self.peak_estimate_db = self.noise_floor_db
        self.snr_estimate_db = 0.0


class OptimizedVAD:
    """Production-grade Voice Activity Detection.

    Features:
    - Mode-specific optimized configurations
    - Adaptive thresholding based on ambient noise
    - Hysteresis to prevent rapid on/off switching
    - Pre/post speech padding with configurable duration
    - Numba-optimized processing for real-time performance
    - Comprehensive metrics and profiling
    """

    def __init__(
        self,
        mode: VADMode = VADMode.SYSTEM,
        sample_rate: int = 16000,
        config: VADConfig | None = None,
        enable_adaptive: bool = True,
        callback: Callable[[VADState], None] | None = None,
    ):
        self.mode = mode
        self.sample_rate = sample_rate
        self.config = config or self._get_default_config()
        self.enable_adaptive = enable_adaptive
        self.callback = callback

        # State tracking
        self.state = VADState.SILENCE
        self.state_time_ms = 0.0
        self.last_transition_time = 0.0

        # Speech detection state
        self.speech_start_sample = 0
        self.speech_end_sample = 0
        self.pending_segment: SpeechSegment | None = None

        # Audio buffer for padding
        self.pre_buffer: deque[NDArray[np.float32]] = deque(
            maxlen=self._samples_from_ms(self.config.speech_pad_ms * 2)
        )
        self.post_buffer_ms = 0.0

        # Adaptive components
        self.noise_profiler = (
            NoiseProfiler(
                alpha=self.config.adaptive_alpha,
                noise_floor_db=self.config.noise_floor_db,
            )
            if enable_adaptive
            else None
        )

        self.current_threshold_db = self.config.threshold_db
        self.peak_hold_counter = 0

        # Metrics
        self.metrics = VADMetrics()
        self.metrics.current_threshold_db = self.current_threshold_db

        # Cache for frame size calculations
        self._frame_size_ms = 20  # 20ms frames
        self._frame_size_samples = int(sample_rate * self._frame_size_ms / 1000)

        logger.info(
            "Initialized OptimizedVAD (mode=%s, threshold=%.1fdB, numba=%s)",
            mode.name,
            self.config.threshold_db,
            NUMBA_AVAILABLE,
        )

    def _get_default_config(self) -> VADConfig:
        """Get default configuration for current mode."""
        if self.mode == VADMode.HOTKEY:
            return VADConfig.hotkey_mode()
        return VADConfig.system_mode()

    def _samples_from_ms(self, ms: float) -> int:
        """Convert milliseconds to samples."""
        return int(self.sample_rate * ms / 1000)

    def _ms_from_samples(self, samples: int) -> float:
        """Convert samples to milliseconds."""
        return samples * 1000.0 / self.sample_rate

    def process_frame(
        self,
        audio: NDArray[np.float32],
    ) -> tuple[VADState, SpeechSegment | None]:
        """Process a single audio frame.

        Args:
            audio: Audio frame (any length, typically 20ms)

        Returns:
            Tuple of (current_state, completed_segment)
            completed_segment is None if no segment completed
        """
        start_time = time.perf_counter()

        # Compute energy
        energy = _compute_energy_numba(audio)
        energy_db = _linear_to_db_numba(energy)

        # Update metrics
        self.metrics.total_samples += len(audio)
        self.metrics.peak_level_db = max(self.metrics.peak_level_db, energy_db)

        # Update adaptive threshold if enabled
        if self.enable_adaptive and self.noise_profiler:
            adaptive_offset = self.noise_profiler.update(energy_db, self.state == VADState.SPEECH)
            self.current_threshold_db = self.config.threshold_db + adaptive_offset
            self.metrics.adaptive_offset_db = adaptive_offset
            self.metrics.noise_floor_db = self.noise_profiler.noise_estimate_db

        self.metrics.current_threshold_db = self.current_threshold_db

        # Determine if speech is present with hysteresis
        is_speech = self._detect_speech(energy_db)

        # State machine
        segment = self._update_state(is_speech, audio)

        # Update processing time
        processing_time = (time.perf_counter() - start_time) * 1000
        self.metrics.add_processing_time(processing_time)

        return self.state, segment

    def _detect_speech(self, energy_db: float) -> bool:
        """Detect speech with hysteresis and peak hold."""
        # Peak hold logic
        if energy_db > self.current_threshold_db:
            self.peak_hold_counter = self._samples_from_ms(self.config.peak_hold_ms)
            return True

        if self.peak_hold_counter > 0:
            self.peak_hold_counter -= self._frame_size_samples
            return True

        return False

    def _update_state(
        self,
        is_speech: bool,
        audio: NDArray[np.float32],
    ) -> SpeechSegment | None:
        """Update VAD state machine."""
        current_time = time.perf_counter() * 1000
        segment: SpeechSegment | None = None

        # State transitions
        if self.state == VADState.SILENCE:
            if is_speech:
                # Transition to speech
                self._transition_to(VADState.SPEECH, current_time)
                self.speech_start_sample = self.metrics.total_samples - len(audio)

                # Include pre-buffer
                self.pre_buffer.append(audio)

        elif self.state == VADState.SPEECH:
            if not is_speech:
                # Check if silence duration exceeds threshold
                silence_duration = current_time - self.last_transition_time

                if silence_duration >= self.config.min_silence_ms:
                    # End speech segment
                    self.speech_end_sample = self.metrics.total_samples

                    # Create segment with padding
                    segment = self._create_segment()

                    self._transition_to(VADState.SILENCE, current_time)
            else:
                # Reset transition timer while speech continues
                self.last_transition_time = current_time

        # Update buffers
        if self.state == VADState.SPEECH:
            self.pre_buffer.append(audio)
            self.metrics.speech_samples += len(audio)
        else:
            self.metrics.silence_samples += len(audio)

        return segment

    def _transition_to(self, new_state: VADState, current_time: float) -> None:
        """Handle state transition with hysteresis check."""
        if new_state == self.state:
            return

        # Check hysteresis
        time_since_last = current_time - self.last_transition_time
        if time_since_last < self.config.hysteresis_ms:
            return

        self.state = new_state
        self.last_transition_time = current_time
        self.metrics.transitions += 1

        if self.callback:
            self.callback(new_state)

        logger.debug("VAD state: %s", new_state.name)

    def _create_segment(self) -> SpeechSegment:
        """Create speech segment from buffered audio."""
        # Concatenate pre-buffer
        if len(self.pre_buffer) > 0:
            audio = np.concatenate(list(self.pre_buffer))
        else:
            audio = np.array([], dtype=np.float32)

        # Calculate confidence based on SNR
        confidence = self._calculate_confidence()

        segment = SpeechSegment(
            start_sample=self.speech_start_sample,
            end_sample=self.speech_end_sample,
            audio=audio.copy(),
            confidence=confidence,
            padding_ms=self.config.speech_pad_ms,
        )

        # Clear buffer
        self.pre_buffer.clear()

        return segment

    def _calculate_confidence(self) -> float:
        """Calculate segment confidence based on audio quality."""
        if not self.noise_profiler:
            return 0.8  # Default confidence without adaptive

        snr = self.noise_profiler.snr_estimate_db

        # Map SNR to confidence (empirical mapping)
        if snr > 30:
            return 0.95
        elif snr > 20:
            return 0.90
        elif snr > 15:
            return 0.85
        elif snr > 10:
            return 0.75
        elif snr > 5:
            return 0.60
        else:
            return 0.45

    def process_stream(
        self,
        audio_stream: NDArray[np.float32],
        frame_size_ms: int = 20,
    ) -> list[SpeechSegment]:
        """Process a complete audio stream.

        Args:
            audio_stream: Complete audio to process
            frame_size_ms: Frame size in milliseconds

        Returns:
            List of detected speech segments
        """
        frame_size = self._samples_from_ms(frame_size_ms)
        segments: list[SpeechSegment] = []

        # Process in frames
        num_frames = len(audio_stream) // frame_size

        for i in range(num_frames):
            start = i * frame_size
            end = start + frame_size
            frame = audio_stream[start:end]

            state, segment = self.process_frame(frame)

            if segment is not None:
                segments.append(segment)

        # Handle any remaining speech at end
        if self.state == VADState.SPEECH:
            self.speech_end_sample = self.metrics.total_samples
            segment = self._create_segment()
            if segment.duration_ms >= self.config.min_speech_ms:
                segments.append(segment)

        return segments

    def reset(self) -> None:
        """Reset VAD state."""
        self.state = VADState.SILENCE
        self.state_time_ms = 0.0
        self.last_transition_time = 0.0
        self.speech_start_sample = 0
        self.speech_end_sample = 0
        self.pre_buffer.clear()
        self.peak_hold_counter = 0

        if self.noise_profiler:
            self.noise_profiler.reset()

        self.metrics = VADMetrics()
        self.metrics.current_threshold_db = self.current_threshold_db

        logger.debug("VAD reset")

    def get_metrics(self) -> VADMetrics:
        """Get current VAD metrics."""
        return self.metrics

    def set_mode(self, mode: VADMode) -> None:
        """Change VAD mode dynamically."""
        self.mode = mode
        self.config = self._get_default_config()
        self.current_threshold_db = self.config.threshold_db
        self.metrics.current_threshold_db = self.current_threshold_db

        logger.info("VAD mode changed to %s", mode.name)


class SpeechSegmenter:
    """Segments audio into clean speech boundaries.

    Features:
    - Intelligent boundary detection
    - Overlap handling
    - Minimum duration filtering
    - Confidence-based filtering
    """

    def __init__(
        self,
        min_duration_ms: float = 150.0,
        max_duration_ms: float = 30000.0,
        confidence_threshold: float = 0.5,
        merge_gap_ms: float = 200.0,
    ):
        self.min_duration_ms = min_duration_ms
        self.max_duration_ms = max_duration_ms
        self.confidence_threshold = confidence_threshold
        self.merge_gap_ms = merge_gap_ms

        self.pending_segments: list[SpeechSegment] = []

    def add_segment(self, segment: SpeechSegment) -> list[SpeechSegment]:
        """Add a segment and return completed segments.

        Args:
            segment: New speech segment

        Returns:
            List of finalized segments
        """
        self.pending_segments.append(segment)
        return self._process_pending()

    def _process_pending(self) -> list[SpeechSegment]:
        """Process pending segments and return finalized ones."""
        if len(self.pending_segments) < 2:
            return []

        finalized: list[SpeechSegment] = []
        merged: list[SpeechSegment] = []

        # Sort by start time
        sorted_segments = sorted(self.pending_segments, key=lambda s: s.start_sample)

        # Merge close segments
        current = sorted_segments[0]
        for next_seg in sorted_segments[1:]:
            gap_ms = self._gap_ms(current, next_seg)

            if gap_ms <= self.merge_gap_ms:
                # Merge segments
                current = self._merge_segments(current, next_seg)
            else:
                if self._is_valid_segment(current):
                    finalized.append(current)
                current = next_seg

        if self._is_valid_segment(current):
            finalized.append(current)

        self.pending_segments = []
        return finalized

    def _gap_ms(self, seg1: SpeechSegment, seg2: SpeechSegment) -> float:
        """Calculate gap between segments in ms."""
        gap_samples = seg2.start_sample - seg1.end_sample
        return gap_samples * 1000.0 / 16000  # Assuming 16kHz

    def _merge_segments(
        self,
        seg1: SpeechSegment,
        seg2: SpeechSegment,
    ) -> SpeechSegment:
        """Merge two segments."""
        # Concatenate audio with gap
        gap_samples = seg2.start_sample - seg1.end_sample
        if gap_samples > 0:
            gap_audio = np.zeros(gap_samples, dtype=np.float32)
            merged_audio = np.concatenate([seg1.audio, gap_audio, seg2.audio])
        else:
            merged_audio = np.concatenate([seg1.audio, seg2.audio])

        # Weighted confidence average
        duration1 = seg1.end_sample - seg1.start_sample
        duration2 = seg2.end_sample - seg2.start_sample
        total = duration1 + duration2

        if total > 0:
            merged_confidence = (seg1.confidence * duration1 + seg2.confidence * duration2) / total
        else:
            merged_confidence = min(seg1.confidence, seg2.confidence)

        return SpeechSegment(
            start_sample=seg1.start_sample,
            end_sample=seg2.end_sample,
            audio=merged_audio,
            confidence=merged_confidence,
            padding_ms=max(seg1.padding_ms, seg2.padding_ms),
        )

    def _is_valid_segment(self, segment: SpeechSegment) -> bool:
        """Check if segment meets criteria."""
        if segment.duration_ms < self.min_duration_ms:
            return False
        if segment.duration_ms > self.max_duration_ms:
            return False
        if segment.confidence < self.confidence_threshold:
            return False
        return True

    def finalize(self) -> list[SpeechSegment]:
        """Finalize all pending segments."""
        segments = self._process_pending()
        self.pending_segments = []
        return segments

    def reset(self) -> None:
        """Reset segmenter state."""
        self.pending_segments = []


# ============================================
# Convenience functions
# ============================================
def create_vad(
    mode: str | VADMode = "system",
    **kwargs,
) -> OptimizedVAD:
    """Create VAD instance with mode-specific defaults.

    Args:
        mode: "hotkey", "system", or VADMode enum
        **kwargs: Additional arguments passed to OptimizedVAD

    Returns:
        Configured OptimizedVAD instance
    """
    if isinstance(mode, str):
        mode = VADMode.HOTKEY if mode.lower() == "hotkey" else VADMode.SYSTEM

    return OptimizedVAD(mode=mode, **kwargs)


def detect_speech_regions(
    audio: NDArray[np.float32],
    sample_rate: int = 16000,
    mode: str = "system",
) -> list[tuple[int, int]]:
    """Detect speech regions in audio.

    Args:
        audio: Audio array
        sample_rate: Sample rate in Hz
        mode: VAD mode ("hotkey" or "system")

    Returns:
        List of (start_sample, end_sample) tuples
    """
    vad = create_vad(mode=mode, sample_rate=sample_rate)
    segments = vad.process_stream(audio)

    return [(seg.start_sample, seg.end_sample) for seg in segments]
