"""System Pipeline - Optimized for system audio capture.

Buffer-based pipeline optimized for long-running sessions with:
- Loopback audio capture
- Larger buffers for stability
- Automatic silence detection for segmentation
- Multi-channel support with mixing to mono
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from app.audio.backends.base import sanitize_audio, to_mono
from app.audio.backends.factory import open_audio_backend
from app.audio.pipelines.pipeline_base import (
    AudioPipeline,
    PipelineConfig,
    PipelineMode,
)

if TYPE_CHECKING:
    from app.audio.backends.base import AudioBackend
    from app.core.models import DeviceProbeResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SystemPipelineConfig(PipelineConfig):
    """Configuration for System audio pipeline.

    Optimized for long-running sessions with stability and
    automatic segmentation.
    """

    # Buffer settings - larger for stability
    buffer_duration_ms: float = 500.0  # 500ms buffers
    buffer_count: int = 8  # Number of buffers in ring

    # Segmentation settings
    segment_on_silence: bool = True
    silence_duration_ms: float = 1000.0  # 1 second silence = segment boundary
    min_segment_duration_ms: float = 500.0  # Min 500ms per segment
    max_segment_duration_ms: float = 30000.0  # Max 30s per segment

    # VAD for speech detection (not segmentation)
    vad_threshold_db: float = -40.0

    # Multi-channel support
    mix_to_mono: bool = True
    channel_selection: str = "auto"  # auto, strongest, mix

    # Long-running session settings
    auto_recover: bool = True
    stats_log_interval_seconds: float = 10.0

    # Device settings
    preferred_backend: str = "auto"


class SilenceDetector:
    """Detects silence for automatic segmentation.

    Tracks audio levels over time to identify segment boundaries
    based on sustained silence periods.
    """

    def __init__(
        self,
        *,
        threshold_db: float,
        silence_duration_ms: float,
        sample_rate: int,
    ) -> None:
        self.threshold_linear = 10 ** (threshold_db / 20.0)
        self.silence_samples = int(silence_duration_ms * sample_rate / 1000)
        self.sample_rate = sample_rate

        self._silence_counter = 0
        self._in_silence = False
        self._silence_start = 0
        self._total_samples = 0

    def process(self, audio: np.ndarray) -> tuple[bool, float]:
        """Process audio and detect silence.

        Returns:
            Tuple of (is_silence, silence_duration_seconds)
        """
        frame_energy = np.sqrt(np.mean(np.square(audio)) + 1e-12)
        is_silent = frame_energy < self.threshold_linear

        if is_silent:
            if not self._in_silence:
                self._in_silence = True
                self._silence_start = self._total_samples
            self._silence_counter += len(audio)
        else:
            self._in_silence = False
            self._silence_counter = 0

        self._total_samples += len(audio)

        silence_duration = self._silence_counter / self.sample_rate
        return is_silent, silence_duration

    def is_silence_boundary(self) -> bool:
        """Check if current silence qualifies as a segment boundary."""
        return self._silence_counter >= self.silence_samples

    def reset(self) -> None:
        """Reset silence detection state."""
        self._silence_counter = 0
        self._in_silence = False
        self._silence_start = 0


class RingBuffer:
    """Fixed-size ring buffer for audio data.

    Provides zero-copy operations where possible for efficient
    audio buffering in long-running sessions.
    """

    def __init__(self, capacity: int, buffer_size: int) -> None:
        self.capacity = capacity
        self.buffer_size = buffer_size
        self._buffers: list[np.ndarray] = [
            np.zeros(buffer_size, dtype=np.float32) for _ in range(capacity)
        ]
        self._write_idx = 0
        self._read_idx = 0
        self._count = 0
        self._lock = asyncio.Lock()

    async def write(self, data: np.ndarray) -> bool:
        """Write data to ring buffer.

        Returns:
            True if successful, False if buffer is full
        """
        if len(data) != self.buffer_size:
            # Handle variable size by padding or truncating
            if len(data) < self.buffer_size:
                data = np.pad(data, (0, self.buffer_size - len(data)))
            else:
                data = data[: self.buffer_size]

        async with self._lock:
            if self._count >= self.capacity:
                return False

            self._buffers[self._write_idx] = data.copy()
            self._write_idx = (self._write_idx + 1) % self.capacity
            self._count += 1
            return True

    async def read(self) -> np.ndarray | None:
        """Read data from ring buffer.

        Returns:
            Audio data or None if buffer is empty
        """
        async with self._lock:
            if self._count == 0:
                return None

            data = self._buffers[self._read_idx]
            self._read_idx = (self._read_idx + 1) % self.capacity
            self._count -= 1
            return data

    async def peek_all(self) -> list[np.ndarray]:
        """Peek at all buffered data without removing."""
        async with self._lock:
            if self._count == 0:
                return []

            result = []
            idx = self._read_idx
            for _ in range(self._count):
                result.append(self._buffers[idx])
                idx = (idx + 1) % self.capacity
            return result

    async def clear(self) -> None:
        """Clear all data from buffer."""
        async with self._lock:
            self._write_idx = 0
            self._read_idx = 0
            self._count = 0

    @property
    def is_full(self) -> bool:
        return self._count >= self.capacity

    @property
    def is_empty(self) -> bool:
        return self._count == 0

    @property
    def available(self) -> int:
        return self._count


class SystemPipeline(AudioPipeline):
    """Buffer-based audio pipeline optimized for system audio capture.

    Features:
    - Loopback audio capture
    - Larger ring buffers for stability
    - Automatic silence detection for segmentation
    - Multi-channel support (mix to mono)
    - Designed for long-running sessions
    """

    def __init__(self, config: SystemPipelineConfig) -> None:
        super().__init__(config)
        self.system_config = config

        # Calculate buffer parameters
        self.buffer_size = int(config.sample_rate * config.buffer_duration_ms / 1000.0)

        # Ring buffer for zero-copy audio storage
        self._ring_buffer = RingBuffer(
            capacity=config.buffer_count,
            buffer_size=self.buffer_size,
        )

        # Silence detector for segmentation
        self._silence_detector = SilenceDetector(
            threshold_db=config.vad_threshold_db,
            silence_duration_ms=config.silence_duration_ms,
            sample_rate=config.sample_rate,
        )

        # Segment building
        self._current_segment: list[np.ndarray] = []
        self._segment_start_time = 0.0
        self._total_audio_duration = 0.0

        # Backend
        self._backend: AudioBackend | None = None

        # Stats tracking
        self._last_stats_time = 0.0
        self._segments_emitted = 0
        self._silence_boundaries = 0

    def _get_mode(self) -> PipelineMode:
        return PipelineMode.SYSTEM

    async def _initialize_device(self) -> None:
        """Initialize loopback audio backend."""
        logger.debug("Initializing System pipeline device")

        device_id = self._current_device_id

        # Open backend in sync context
        loop = asyncio.get_event_loop()
        selection = await loop.run_in_executor(
            None,
            lambda: open_audio_backend(
                device_id=device_id,
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
                block_size=self.buffer_size,
                preferred_backend=self.system_config.preferred_backend,
            ),
        )

        self._backend = selection.backend
        self._backend.start()

        # Reset state
        await self._ring_buffer.clear()
        self._silence_detector.reset()
        self._current_segment.clear()
        self._segment_start_time = time.monotonic()
        self._total_audio_duration = 0.0
        self._segments_emitted = 0
        self._silence_boundaries = 0

        logger.info(
            "System pipeline device initialized",
            extra={
                "device_id": device_id,
                "backend": self._backend.backend_name,
                "buffer_size": self.buffer_size,
                "buffer_duration_ms": self.system_config.buffer_duration_ms,
                "buffer_count": self.system_config.buffer_count,
            },
        )

    async def _cleanup_device(self) -> None:
        """Cleanup loopback backend."""
        if self._backend is not None:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._backend.stop)
                logger.debug("System backend stopped")
            except Exception as exc:
                logger.warning(f"Error stopping System backend: {exc}")
            finally:
                self._backend = None

    async def _capture_loop(self) -> None:
        """Buffer-based capture loop with segmentation."""
        if self._backend is None:
            raise RuntimeError("Backend not initialized")

        loop = asyncio.get_event_loop()
        consecutive_empty = 0
        max_consecutive_empty = 20

        while not self._stop_event.is_set():
            # Check pause state
            if self._pause_event.is_set():
                await self._wait_while_paused()
                continue

            # Read audio buffer (sync operation in executor)
            try:
                data = await loop.run_in_executor(None, lambda: self._backend.read(timeout=0.5))
            except Exception as exc:
                logger.error(f"Backend read error: {exc}")
                raise

            if data is None or data.size == 0:
                consecutive_empty += 1
                if consecutive_empty >= max_consecutive_empty:
                    raise RuntimeError("Device stopped providing data")
                await asyncio.sleep(0.01)
                continue

            consecutive_empty = 0

            # Process audio
            if self.system_config.mix_to_mono:
                audio = to_mono(data)
            else:
                audio = sanitize_audio(data)
                if audio.ndim > 1:
                    audio = audio[:, 0]  # Take first channel

            # Update health metrics
            self._health.frames_captured += 1
            rms = self._calculate_rms(audio)
            self._health.is_speech_active = rms > 10 ** (self.system_config.vad_threshold_db / 20.0)

            # Write to ring buffer
            if not await self._ring_buffer.write(audio):
                self._health.buffer_overruns += 1
                logger.warning("Ring buffer overrun, dropping audio")

            # Silence detection for segmentation
            is_silence, silence_duration = self._silence_detector.process(audio)

            # Add to current segment
            self._current_segment.append(audio)
            segment_duration = len(self._current_segment) * self.system_config.buffer_duration_ms

            # Check for segment emission conditions
            should_emit = False
            emit_reason = ""

            if (
                self.system_config.segment_on_silence
                and self._silence_detector.is_silence_boundary()
            ):
                if segment_duration >= self.system_config.min_segment_duration_ms:
                    should_emit = True
                    emit_reason = "silence_boundary"
                    self._silence_boundaries += 1

            if segment_duration >= self.system_config.max_segment_duration_ms:
                should_emit = True
                emit_reason = "max_duration"

            if should_emit:
                await self._emit_segment(reason=emit_reason)
                self._silence_detector.reset()

            # Log stats periodically
            await self._maybe_log_stats()

            # Small yield
            await asyncio.sleep(0)

        # Emit final segment on stop
        if self._current_segment:
            await self._emit_segment(reason="shutdown")

    async def _emit_segment(self, reason: str) -> None:
        """Emit accumulated audio segment to output queue."""
        if not self._current_segment:
            return

        # Concatenate segment
        combined = np.concatenate(self._current_segment)
        self._current_segment.clear()

        segment_duration_ms = len(combined) / self.config.sample_rate * 1000
        self._total_audio_duration += segment_duration_ms / 1000.0

        logger.debug(
            f"Emitting audio segment ({reason})",
            extra={
                "duration_ms": segment_duration_ms,
                "samples": len(combined),
                "reason": reason,
            },
        )

        # Add to output queue (with timeout to prevent blocking)
        try:
            await asyncio.wait_for(self._output_queue.put(combined), timeout=0.5)
            self._segments_emitted += 1
            self._segment_start_time = time.monotonic()
        except TimeoutError:
            self._health.frames_dropped += len(combined) // self.buffer_size
            self._health.buffer_overruns += 1
            logger.warning("Output queue full, dropping segment")

    async def _maybe_log_stats(self) -> None:
        """Log statistics periodically."""
        now = time.monotonic()
        if now - self._last_stats_time >= self.system_config.stats_log_interval_seconds:
            self._last_stats_time = now

            ring_stats = {
                "available": self._ring_buffer.available,
                "capacity": self._ring_buffer.capacity,
            }

            logger.info(
                "System pipeline stats",
                extra={
                    "session_duration_seconds": now - self._segment_start_time,
                    "total_audio_seconds": self._total_audio_duration,
                    "segments_emitted": self._segments_emitted,
                    "silence_boundaries": self._silence_boundaries,
                    "ring_buffer": ring_stats,
                    "frames_captured": self._health.frames_captured,
                    "frames_dropped": self._health.frames_dropped,
                    "buffer_overruns": self._health.buffer_overruns,
                },
            )

    def probe_device(self, *, duration: float, output_dir: Path) -> DeviceProbeResult:
        """Probe system audio device."""
        if self._backend is None:
            raise RuntimeError("Backend not initialized")

        return self._backend.probe(duration=duration, output_dir=output_dir)

    def get_session_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        return {
            "total_audio_seconds": self._total_audio_duration,
            "segments_emitted": self._segments_emitted,
            "silence_boundaries": self._silence_boundaries,
            "buffer_size": self.buffer_size,
            "buffer_duration_ms": self.system_config.buffer_duration_ms,
        }
