"""Ultra-low-latency audio chunking with voice activity detection.

Provides real-time audio stream processing with:
- 200ms base chunks for low-latency transcription
- 50ms overlap for continuity between chunks
- Voice activity detection at the chunk level
- Early emission when speech is detected
- Adaptive chunk sizing based on speech density
- Zero-copy buffer management for efficiency
"""

from __future__ import annotations

import enum
import logging
import time
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


class VADState(enum.Enum):
    """Voice activity detection states."""

    SILENCE = "silence"
    SPEECH = "speech"
    TRANSITION = "transition"


@dataclass(slots=True)
class ChunkConfig:
    """Configuration for fast chunking parameters.

    Attributes:
        base_chunk_ms: Base chunk duration in milliseconds (default: 200ms)
        overlap_ms: Overlap duration in milliseconds (default: 50ms)
        min_chunk_ms: Minimum chunk size for adaptive mode (default: 100ms)
        max_chunk_ms: Maximum chunk size for adaptive mode (default: 400ms)
        vad_threshold_db: VAD energy threshold in dB (default: -40)
        vad_hysteresis_ms: Hysteresis time to avoid rapid switching (default: 100ms)
        sample_rate: Audio sample rate in Hz (default: 16000)
    """

    base_chunk_ms: float = 200.0
    overlap_ms: float = 50.0
    min_chunk_ms: float = 100.0
    max_chunk_ms: float = 400.0
    vad_threshold_db: float = -35.0  # More sensitive, faster trigger
    vad_hysteresis_ms: float = 100.0
    sample_rate: int = 16000

    @property
    def base_samples(self) -> int:
        """Base chunk size in samples."""
        return int(self.sample_rate * self.base_chunk_ms / 1000)

    @property
    def overlap_samples(self) -> int:
        """Overlap size in samples."""
        return int(self.sample_rate * self.overlap_ms / 1000)

    @property
    def step_samples(self) -> int:
        """Step size between chunks in samples."""
        return self.base_samples - self.overlap_samples

    @property
    def min_samples(self) -> int:
        """Minimum chunk size in samples."""
        return int(self.sample_rate * self.min_chunk_ms / 1000)

    @property
    def max_samples(self) -> int:
        """Maximum chunk size in samples."""
        return int(self.sample_rate * self.max_chunk_ms / 1000)


@dataclass(slots=True)
class AudioChunk:
    """Audio chunk with metadata for real-time processing.

    Attributes:
        samples: Audio samples as float32 numpy array
        start_time: Chunk start time relative to stream start (seconds)
        end_time: Chunk end time relative to stream start (seconds)
        vad_state: Voice activity detection state
        energy_db: Chunk energy in dB
        is_early_emission: Whether this was emitted early due to speech
        overlap_samples: Number of overlap samples from previous chunk
    """

    samples: np.ndarray = field(repr=False)
    start_time: float = 0.0
    end_time: float = 0.0
    vad_state: VADState = VADState.SILENCE
    energy_db: float = -np.inf
    is_early_emission: bool = False
    overlap_samples: int = 0

    # Aliases for backward compatibility with original AudioChunk
    @property
    def started_at(self) -> float:
        return self.start_time

    @property
    def ended_at(self) -> float:
        return self.end_time

    @property
    def duration(self) -> float:
        """Chunk duration in seconds."""
        return self.end_time - self.start_time

    @property
    def sample_count(self) -> int:
        """Number of samples in chunk."""
        return len(self.samples)

    @property
    def has_speech(self) -> bool:
        """Whether chunk contains detected speech."""
        return self.vad_state == VADState.SPEECH


class ZeroCopyBuffer:
    """Ring buffer with zero-copy operations for audio streaming.

    Implements a circular buffer that minimizes memory allocations by
    reusing internal storage and providing views instead of copies.
    """

    __slots__ = ("_buffer", "_capacity", "_write_pos", "_read_pos", "_size", "_temp", "_empty")

    def __init__(self, capacity: int) -> None:
        """Initialize buffer with given capacity.

        Args:
            capacity: Maximum number of samples to store
        """
        self._capacity = capacity
        self._buffer = np.empty(capacity, dtype=np.float32)
        self._write_pos = 0
        self._read_pos = 0
        self._size = 0
        self._temp = np.empty(capacity, dtype=np.float32)
        self._empty = np.array([], dtype=np.float32)

    @property
    def capacity(self) -> int:
        """Buffer capacity in samples."""
        return self._capacity

    @property
    def available(self) -> int:
        """Number of samples available for reading."""
        return self._size

    def push(self, samples: np.ndarray) -> None:
        """Push samples into buffer (overwrites oldest if full).

        Args:
            samples: Audio samples to append (float32 array)
        """
        n = len(samples)
        if n > self._capacity:
            samples = samples[-self._capacity :]
            n = self._capacity

        end_pos = self._write_pos + n
        if end_pos <= self._capacity:
            self._buffer[self._write_pos : end_pos] = samples
        else:
            first_part = self._capacity - self._write_pos
            self._buffer[self._write_pos :] = samples[:first_part]
            self._buffer[: end_pos - self._capacity] = samples[first_part:]

        self._write_pos = end_pos % self._capacity
        self._size = min(self._size + n, self._capacity)

        if self._size == self._capacity:
            self._read_pos = self._write_pos

    def peek(self, count: int) -> np.ndarray:
        """View samples without removing them.

        Args:
            count: Number of samples to view

        Returns:
            View into buffer (uses temp buffer for wraparound)
        """
        count = min(count, self._size)
        if count == 0:
            return self._empty

        end_pos = self._read_pos + count
        if end_pos <= self._capacity:
            return self._buffer[self._read_pos : end_pos]

        first_part = self._capacity - self._read_pos
        self._temp[:first_part] = self._buffer[self._read_pos :]
        self._temp[first_part:count] = self._buffer[: end_pos - self._capacity]
        return self._temp[:count]

    def pop(self, count: int) -> np.ndarray:
        """Remove and return samples from buffer.

        Args:
            count: Number of samples to remove

        Returns:
            Removed samples
        """
        result = self.peek(count)
        self._read_pos = (self._read_pos + len(result)) % self._capacity
        self._size -= len(result)
        return result

    def clear(self) -> None:
        """Clear buffer contents."""
        self._write_pos = 0
        self._read_pos = 0
        self._size = 0


class VoiceActivityDetector:
    """Real-time voice activity detection for audio chunks.

    Uses energy-based detection with hysteresis to avoid rapid switching
    and provides onset/offset detection for speech segments.
    """

    __slots__ = (
        "_threshold_db",
        "_hysteresis_samples",
        "_state",
        "_speech_counter",
        "_silence_counter",
        "_sample_rate",
        "_last_transition_time",
        "_log10_scale",
    )

    def __init__(
        self,
        threshold_db: float = -40.0,
        hysteresis_ms: float = 100.0,
        sample_rate: int = 16000,
    ) -> None:
        """Initialize VAD with configuration.

        Args:
            threshold_db: Energy threshold in dB
            hysteresis_ms: Hysteresis time in milliseconds
            sample_rate: Audio sample rate
        """
        self._threshold_db = threshold_db
        self._hysteresis_samples = int(sample_rate * hysteresis_ms / 1000)
        self._sample_rate = sample_rate
        self._state = VADState.SILENCE
        self._speech_counter = 0
        self._silence_counter = 0
        self._last_transition_time = 0.0
        self._log10_scale = 1.0 / np.log(10)

    def compute_energy(self, samples: np.ndarray) -> float:
        """Compute RMS energy in dB.

        Args:
            samples: Audio samples

        Returns:
            Energy in dB (negative infinity for silence)
        """
        return self._compute_energy_fast(samples)

    def compute_energy_fast(self, samples: np.ndarray) -> float:
        """Fast energy computation using float32 directly.

        Args:
            samples: Audio samples (must be float32)

        Returns:
            Energy in dB (negative infinity for silence)
        """
        return self._compute_energy_fast(samples)

    def _compute_energy_fast(self, samples: np.ndarray) -> float:
        """Ultra-fast energy computation using precomputed log scale."""
        n = len(samples)
        if n == 0:
            return -100.0
        rms_sq = np.dot(samples, samples) / n
        if rms_sq <= 1e-10:
            return -100.0
        return np.log(rms_sq) * 10.0 * self._log10_scale

    def compute_energy_fast_precheck(self, samples: np.ndarray, rms_sq: float) -> float:
        """Ultra-fast energy with pre-computed squared sum.

        Args:
            samples: Audio samples (must be float32)
            rms_sq: Pre-computed sum(samples^2) / n

        Returns:
            Energy in dB (negative infinity for silence)
        """
        if rms_sq <= 1e-10:
            return -100.0
        return np.log(rms_sq) * 10.0 * self._log10_scale

    def process(self, samples: np.ndarray, timestamp: float) -> VADState:
        """Process chunk and return current VAD state.

        Args:
            samples: Audio samples
            timestamp: Current timestamp for tracking

        Returns:
            Current VAD state
        """
        n = len(samples)
        if n == 0:
            return self._state
        rms_sq = np.dot(samples, samples) / n
        if rms_sq <= 1e-10:
            energy = -100.0
        else:
            energy = np.log(rms_sq) * 10.0 * self._log10_scale
        is_speech = energy > self._threshold_db

        if self._state == VADState.SILENCE:
            if is_speech:
                self._speech_counter += n
                if self._speech_counter >= self._hysteresis_samples:
                    self._state = VADState.SPEECH
                    self._last_transition_time = timestamp
                    self._speech_counter = 0
            else:
                self._speech_counter = max(0, self._speech_counter - n // 2)
        else:
            if not is_speech:
                self._silence_counter += n
                if self._silence_counter >= self._hysteresis_samples:
                    self._state = VADState.SILENCE
                    self._last_transition_time = timestamp
                    self._silence_counter = 0
            else:
                self._silence_counter = max(0, self._silence_counter - n // 2)

        return self._state

    @property
    def state(self) -> VADState:
        """Current VAD state."""
        return self._state

    def reset(self) -> None:
        """Reset VAD state."""
        self._state = VADState.SILENCE
        self._speech_counter = 0
        self._silence_counter = 0
        self._last_transition_time = 0.0


class FastChunker:
    """Ultra-low-latency audio chunker with VAD and adaptive sizing.

    Implements sliding window chunking with 200ms base chunks and 50ms overlap.
    Features voice activity detection, early emission on speech detection,
    and adaptive chunk sizing based on speech density for optimal latency.

    Example:
        >>> config = ChunkConfig(base_chunk_ms=200, overlap_ms=50)
        >>> chunker = FastChunker(config)
        >>>
        >>> # Push audio samples
        >>> audio = np.random.randn(3200).astype(np.float32)  # 200ms @ 16kHz
        >>> chunks = chunker.push(audio, time.monotonic())
        >>>
        >>> for chunk in chunks:
        ...     if chunk.has_speech:
        ...         process_speech(chunk.samples)
    """

    __slots__ = (
        "_config",
        "_buffer",
        "_vad",
        "_overlap_buffer",
        "_stream_start_time",
        "_next_chunk_time",
        "_adaptive_size",
        "_speech_density_window",
        "_initialized",
        "_chunk_output",
    )

    def __init__(
        self,
        config: ChunkConfig | None = None,
        *,
        sample_rate: int | None = None,
        chunk_duration: float | None = None,
        overlap_ratio: float = 0.1,
    ) -> None:
        """Initialize fast chunker.

        Args:
            config: Chunking configuration (uses defaults if None)
            sample_rate: Audio sample rate in Hz (for backward compatibility)
            chunk_duration: Chunk duration in seconds (for backward compatibility)
            overlap_ratio: Overlap ratio between chunks (for backward compatibility)
        """
        if config is not None:
            self._config = config
        else:
            base_chunk_ms = (chunk_duration * 1000) if chunk_duration else 200.0
            overlap_ms = base_chunk_ms * overlap_ratio
            effective_sample_rate = sample_rate or 16000
            if effective_sample_rate <= 0:
                raise ValueError(f"sample_rate must be positive, got {effective_sample_rate}")
            self._config = ChunkConfig(
                sample_rate=effective_sample_rate,
                base_chunk_ms=base_chunk_ms,
                overlap_ms=overlap_ms,
            )

        buffer_capacity = int(self._config.max_samples * 1.5)
        self._buffer = ZeroCopyBuffer(buffer_capacity)

        self._overlap_buffer = np.empty(self._config.overlap_samples, dtype=np.float32)

        self._vad = VoiceActivityDetector(
            threshold_db=self._config.vad_threshold_db,
            hysteresis_ms=self._config.vad_hysteresis_ms,
            sample_rate=self._config.sample_rate,
        )

        self._stream_start_time: float | None = None
        self._next_chunk_time: float = 0.0

        self._adaptive_size = self._config.base_samples
        self._speech_density_window = deque[float](maxlen=10)

        self._initialized = False

        self._chunk_output = np.empty(
            self._config.max_samples + self._config.overlap_samples, dtype=np.float32
        )

    def push(
        self,
        samples: np.ndarray,
        timestamp: float | None = None,
    ) -> list[AudioChunk]:
        """Push audio samples and return ready chunks.

        Processes incoming audio through the chunking pipeline:
        1. Buffers incoming samples
        2. Runs VAD on available audio
        3. Emits chunks based on size and speech detection
        4. Applies adaptive sizing for speech-dense regions

        Args:
            samples: Audio samples as float32 numpy array
            timestamp: Current timestamp (uses time.monotonic() if None)

        Returns:
            List of audio chunks ready for processing
        """
        if timestamp is None:
            timestamp = time.monotonic()

        samples = np.asarray(samples, dtype=np.float32)

        if not self._initialized:
            self._stream_start_time = timestamp
            self._next_chunk_time = 0.0
            self._initialized = True

        # Validate sample rate
        if self._config.sample_rate <= 0 or self._config.sample_rate > 192000:
            raise ValueError(
                f"sample_rate must be between 1 and 192000 Hz, got {self._config.sample_rate}"
            )

        # Push to buffer
        self._buffer.push(samples)

        # Process chunks
        return self._process_available(timestamp)

    def _process_available(self, timestamp: float) -> list[AudioChunk]:
        """Process available buffered audio into chunks."""
        chunks: list[AudioChunk] = []
        sample_rate = self._config.sample_rate
        if sample_rate <= 0:
            logger.error("Invalid sample_rate: %s", sample_rate)
            return chunks

        step_size = self._config.base_samples - self._config.overlap_samples
        overlap_samples = self._config.overlap_samples
        min_samples = self._config.min_samples
        vad_compute_energy = self._vad.compute_energy_fast

        while self._buffer.available >= self._adaptive_size:
            self._update_adaptive_size()
            chunk_size = self._adaptive_size

            prospective = self._buffer.peek(chunk_size)
            vad_state = self._vad.process(prospective, timestamp)

            emit_early = vad_state == VADState.SPEECH and len(prospective) >= min_samples

            if emit_early or len(prospective) >= self._adaptive_size:
                chunk_samples = self._buffer.pop(chunk_size)

                if overlap_samples > 0 and len(self._overlap_buffer) > 0:
                    chunk_output_len = len(self._chunk_output)
                    copy_len = min(overlap_samples, chunk_output_len)
                    self._chunk_output[:copy_len] = self._overlap_buffer[:copy_len]
                    remaining = chunk_output_len - copy_len
                    if remaining > 0:
                        self._chunk_output[copy_len : copy_len + len(chunk_samples)] = (
                            chunk_samples[:remaining]
                        )
                    actual_size = copy_len + min(len(chunk_samples), remaining)
                    final_samples = self._chunk_output[:actual_size].copy()
                    if len(prospective) >= overlap_samples:
                        self._overlap_buffer[:] = prospective[-overlap_samples:]
                else:
                    final_samples = chunk_samples

                chunk_start = self._next_chunk_time
                chunk_duration = len(final_samples) / sample_rate
                chunk_end = chunk_start + chunk_duration

                chunk = AudioChunk(
                    samples=final_samples,
                    start_time=chunk_start,
                    end_time=chunk_end,
                    vad_state=vad_state,
                    energy_db=vad_compute_energy(prospective),
                    is_early_emission=emit_early,
                    overlap_samples=overlap_samples
                    if overlap_samples > 0 and len(self._overlap_buffer) > 0
                    else 0,
                )
                chunks.append(chunk)

                self._next_chunk_time += step_size / sample_rate
                self._speech_density_window.append(1.0 if vad_state == VADState.SPEECH else 0.0)
            else:
                break

        return chunks

    def _update_adaptive_size(self) -> None:
        """Update adaptive chunk size based on recent speech density."""
        if len(self._speech_density_window) < 3:
            self._adaptive_size = self._config.base_samples
            return

        density = sum(self._speech_density_window) / len(self._speech_density_window)

        if density > 0.7:
            # High speech density - use smaller chunks for responsiveness
            self._adaptive_size = max(
                self._config.min_samples,
                int(self._config.base_samples * 0.75),
            )
        elif density < 0.2:
            # Low speech density - use larger chunks for efficiency
            self._adaptive_size = min(
                self._config.max_samples,
                int(self._config.base_samples * 1.25),
            )
        else:
            self._adaptive_size = self._config.base_samples

    def flush(self) -> list[AudioChunk]:
        """Flush remaining buffered audio into final chunks.

        Returns:
            List of any remaining audio chunks
        """
        chunks: list[AudioChunk] = []

        if self._buffer.available > 0:
            samples = self._buffer.pop(self._buffer.available)

            if len(self._overlap_buffer) > 0:
                samples = np.concatenate([self._overlap_buffer, samples])

            chunk_start = self._next_chunk_time
            chunk_duration = len(samples) / self._config.sample_rate
            chunk_end = chunk_start + chunk_duration

            vad_state = self._vad.process(samples, time.monotonic())

            chunk = AudioChunk(
                samples=samples,
                start_time=chunk_start,
                end_time=chunk_end,
                vad_state=vad_state,
                energy_db=self._vad.compute_energy(samples),
                is_early_emission=False,
                overlap_samples=len(self._overlap_buffer),
            )
            chunks.append(chunk)

        self._buffer.clear()
        self._overlap_buffer.fill(0)
        return chunks

    def reset(self) -> None:
        """Reset chunker state for new stream."""
        self._buffer.clear()
        self._overlap_buffer.fill(0)
        self._vad.reset()
        self._stream_start_time = None
        self._next_chunk_time = 0.0
        self._adaptive_size = self._config.base_samples
        self._speech_density_window.clear()
        self._initialized = False

    @property
    def config(self) -> ChunkConfig:
        """Current chunk configuration."""
        return self._config

    @property
    def buffered_samples(self) -> int:
        """Number of samples currently buffered."""
        return self._buffer.available

    @property
    def buffered_ms(self) -> float:
        """Buffered audio duration in milliseconds."""
        if self._config.sample_rate == 0:
            return 0.0
        return self._buffer.available / self._config.sample_rate * 1000

    @property
    def vad_state(self) -> VADState:
        """Current voice activity detection state."""
        return self._vad.state


class StreamingChunkIterator:
    """Iterator wrapper for streaming chunk processing.

    Provides async-compatible chunk iteration with configurable buffering.
    """

    __slots__ = ("_chunker", "_queue", "_max_queue_size")

    def __init__(
        self,
        chunker: FastChunker,
        max_queue_size: int = 100,
    ) -> None:
        """Initialize streaming iterator.

        Args:
            chunker: FastChunker instance
            max_queue_size: Maximum chunks to queue
        """
        self._chunker = chunker
        self._max_queue_size = max_queue_size
        self._queue: deque[AudioChunk] = deque(maxlen=max_queue_size)

    def push(self, samples: np.ndarray, timestamp: float | None = None) -> None:
        """Push audio and queue chunks."""
        chunks = self._chunker.push(samples, timestamp)
        for chunk in chunks:
            self._queue.append(chunk)

    def __iter__(self) -> Iterator[AudioChunk]:
        """Yield available chunks."""
        while self._queue:
            yield self._queue.popleft()

    def get_nowait(self) -> AudioChunk | None:
        """Get next chunk if available.

        Returns:
            Next chunk or None if queue is empty
        """
        return self._queue.popleft() if self._queue else None

    def flush(self) -> list[AudioChunk]:
        """Flush remaining chunks."""
        final_chunks = self._chunker.flush()
        for chunk in final_chunks:
            self._queue.append(chunk)
        return list(self._queue)


def create_default_chunker(sample_rate: int = 16000) -> FastChunker:
    """Create a FastChunker with default settings.

    Args:
        sample_rate: Audio sample rate (default: 16000 Hz)

    Returns:
        Configured FastChunker instance
    """
    config = ChunkConfig(
        base_chunk_ms=200.0,
        overlap_ms=50.0,
        min_chunk_ms=100.0,
        max_chunk_ms=400.0,
        vad_threshold_db=-40.0,
        vad_hysteresis_ms=100.0,
        sample_rate=sample_rate,
    )
    return FastChunker(config)


def compute_chunk_timing(
    chunk: AudioChunk,
    stream_start: float,
) -> tuple[float, float]:
    """Compute absolute timing for a chunk.

    Args:
        chunk: Audio chunk
        stream_start: Stream start timestamp

    Returns:
        Tuple of (absolute_start, absolute_end) in seconds
    """
    return (stream_start + chunk.start_time, stream_start + chunk.end_time)
