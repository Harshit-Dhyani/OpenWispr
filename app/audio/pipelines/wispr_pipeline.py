"""Wispr Pipeline - Optimized for hotkey/mic capture.

Low-latency pipeline optimized for real-time dictation with:
- 50ms frame capture for minimal latency
- Streaming VAD with early emission
- Pre-buffer for capturing speech start
- Target <200ms first-word latency
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
from app.config.constants import VADConstants

if TYPE_CHECKING:
    from app.audio.backends.base import AudioBackend
    from app.core.models import DeviceProbeResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WisprPipelineConfig(PipelineConfig):
    """Configuration for Wispr (hotkey/mic) pipeline.

    Optimized for low-latency dictation with aggressive buffering
    and early emission strategies.
    """

    # Frame timing - 50ms for low latency
    frame_duration_ms: float = 50.0

    # Pre-buffer: capture audio before speech is detected
    pre_buffer_duration_ms: float = 200.0  # 200ms pre-buffer

    # VAD settings
    vad_threshold_db: float = VADConstants.DEFAULT_THRESHOLD_DB
    vad_hysteresis_ms: float = VADConstants.DEFAULT_HYSTERESIS_MS
    min_silence_ms: float = VADConstants.DEFAULT_MIN_SILENCE_MS
    speech_pad_ms: float = VADConstants.DEFAULT_SPEECH_PAD_MS

    # Early emission settings
    early_emission_frames: int = 2  # Emit after 2 speech frames
    max_emission_latency_ms: float = 150.0

    # Latency target
    target_first_word_latency_ms: float = 200.0

    # Ring buffer capacity (in frames)
    ring_buffer_capacity: int = 100


class StreamingVAD:
    """Streaming Voice Activity Detection with early emission.

    Provides real-time VAD decisions optimized for low-latency capture.
    """

    def __init__(
        self,
        *,
        threshold_db: float,
        hysteresis_ms: float,
        min_silence_ms: float,
        sample_rate: int,
    ) -> None:
        self.threshold_linear = 10 ** (threshold_db / 20.0)
        self.hysteresis_samples = int(hysteresis_ms * sample_rate / 1000)
        self.min_silence_samples = int(min_silence_ms * sample_rate / 1000)
        self.sample_rate = sample_rate

        self._is_speech = False
        self._hysteresis_counter = 0
        self._silence_counter = 0
        self._speech_start_sample = 0
        self._total_samples = 0

    def process(self, audio: np.ndarray) -> tuple[bool, bool]:
        """Process audio frame and return (is_speech, is_speech_start).

        Returns:
            Tuple of (is_currently_speech, is_this_frame_speech_start)
        """
        frame_energy = np.sqrt(np.mean(np.square(audio)) + 1e-12)
        is_above_threshold = frame_energy > self.threshold_linear

        is_speech_start = False

        if not self._is_speech:
            # Not currently in speech - check for start
            if is_above_threshold:
                self._hysteresis_counter += len(audio)
                if self._hysteresis_counter >= self.hysteresis_samples:
                    self._is_speech = True
                    self._speech_start_sample = self._total_samples
                    is_speech_start = True
                    self._hysteresis_counter = 0
                    self._silence_counter = 0
            else:
                self._hysteresis_counter = max(0, self._hysteresis_counter - len(audio) // 2)
        else:
            # Currently in speech - check for end
            if not is_above_threshold:
                self._silence_counter += len(audio)
                if self._silence_counter >= self.min_silence_samples:
                    self._is_speech = False
                    self._silence_counter = 0
                    self._hysteresis_counter = 0
            else:
                self._silence_counter = max(0, self._silence_counter - len(audio) // 2)

        self._total_samples += len(audio)
        return self._is_speech, is_speech_start

    def reset(self) -> None:
        """Reset VAD state."""
        self._is_speech = False
        self._hysteresis_counter = 0
        self._silence_counter = 0
        self._speech_start_sample = 0


class WisprPipeline(AudioPipeline):
    """Low-latency audio pipeline optimized for hotkey/mic dictation.

    Features:
    - 50ms frame capture for minimal latency
    - Pre-buffer to capture speech start
    - Streaming VAD with early emission
    - Target <200ms first-word latency
    - Microphone-only input
    """

    def __init__(self, config: WisprPipelineConfig) -> None:
        super().__init__(config)
        self.wispr_config = config

        self.frame_size = int(config.sample_rate * config.frame_duration_ms / 1000.0)
        self.pre_buffer_frames = int(config.pre_buffer_duration_ms / config.frame_duration_ms)

        # Voice activity detection for speech activation
        self._vad = StreamingVAD(
            threshold_db=config.vad_threshold_db,
            hysteresis_ms=config.vad_hysteresis_ms,
            min_silence_ms=config.min_silence_ms,
            sample_rate=config.sample_rate,
        )

        self._pre_buffer: list[np.ndarray] = []
        self._pre_buffer_lock = asyncio.Lock()

        # Pending audio for emission
        self._pending_audio: list[np.ndarray] = []
        self._pending_audio_lock = asyncio.Lock()

        # Audio emission state
        self._speech_frame_count = 0
        self._last_emission_time = 0.0

        # Backend
        self._backend: AudioBackend | None = None

        # Latency tracking
        self._first_speech_time: float | None = None
        self._first_emission_time: float | None = None

    def _get_mode(self) -> PipelineMode:
        return PipelineMode.WISPR

    async def _initialize_device(self) -> None:
        """Initialize microphone audio backend."""
        logger.debug("Initializing Wispr pipeline device")

        # Use microphone device (different from system loopback)
        device_id = self._current_device_id

        # Open backend in sync context
        loop = asyncio.get_event_loop()
        selection = await loop.run_in_executor(
            None,
            lambda: open_audio_backend(
                device_id=device_id,
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
                block_size=self.frame_size,
                preferred_backend="auto",
            ),
        )

        self._backend = selection.backend
        self._backend.start()

        # Reset state
        self._vad.reset()
        self._pre_buffer.clear()
        self._pending_audio.clear()
        self._speech_frame_count = 0
        self._first_speech_time = None
        self._first_emission_time = None

        logger.info(
            "Wispr pipeline device initialized",
            extra={
                "device_id": device_id,
                "backend": self._backend.backend_name,
                "frame_size": self.frame_size,
                "frame_duration_ms": self.wispr_config.frame_duration_ms,
            },
        )

    async def _cleanup_device(self) -> None:
        """Cleanup microphone backend."""
        if self._backend is not None:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._backend.stop)
                logger.debug("Wispr backend stopped")
            except Exception as exc:
                logger.warning(f"Error stopping Wispr backend: {exc}")
            finally:
                self._backend = None

    async def _capture_loop(self) -> None:
        """Low-latency capture loop with VAD and early emission."""
        if self._backend is None:
            raise RuntimeError("Backend not initialized")

        loop = asyncio.get_event_loop()
        consecutive_empty = 0
        max_consecutive_empty = 10

        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                await self._wait_while_paused()
                continue

            frame_start_time = time.monotonic()

            # Read audio frame (sync operation in executor)
            try:
                data = await loop.run_in_executor(None, lambda: self._backend.read(timeout=0.1))
            except Exception as exc:
                logger.error(f"Backend read error: {exc}")
                raise

            if data is None or data.size == 0:
                consecutive_empty += 1
                if consecutive_empty >= max_consecutive_empty:
                    raise RuntimeError("Device stopped providing data")
                await asyncio.sleep(0.001)
                continue

            consecutive_empty = 0

            audio = to_mono(data)
            audio = sanitize_audio(audio)

            self._health.frames_captured += 1
            rms = self._calculate_rms(audio)

            # VAD processing
            is_speech, is_speech_start = self._vad.process(audio)

            if is_speech_start:
                self._health.is_speech_active = True
                if self._first_speech_time is None:
                    self._first_speech_time = time.monotonic()
                    logger.debug("Speech detected")
            elif not is_speech and self._health.is_speech_active:
                self._health.is_speech_active = False
                logger.debug("Speech ended")

            # Handle pre-buffering
            async with self._pre_buffer_lock:
                self._pre_buffer.append(audio)
                if len(self._pre_buffer) > self.pre_buffer_frames:
                    self._pre_buffer.pop(0)

            # Build output frame
            if is_speech:
                self._speech_frame_count += 1

                # On speech start, prepend pre-buffer
                if is_speech_start:
                    async with self._pre_buffer_lock:
                        async with self._pending_audio_lock:
                            self._pending_audio.extend(self._pre_buffer)
                        self._pre_buffer.clear()

                async with self._pending_audio_lock:
                    self._pending_audio.append(audio)

                # Early emission check
                should_emit = (
                    self._speech_frame_count >= self.wispr_config.early_emission_frames
                    or time.monotonic() - self._last_emission_time > 0.5
                )

                async with self._pending_audio_lock:
                    has_pending = bool(self._pending_audio)
                    should_emit = should_emit and has_pending

                if should_emit:
                    await self._emit_audio()
            else:
                # Not speech - emit any pending audio
                async with self._pending_audio_lock:
                    has_pending = self._pending_audio

                if has_pending:
                    await self._emit_audio()
                self._speech_frame_count = 0

            # Track latency
            frame_latency = (time.monotonic() - frame_start_time) * 1000
            self._record_latency(frame_latency)

            # Small yield to allow other tasks
            await asyncio.sleep(0)

    async def _emit_audio(self) -> None:
        """Emit accumulated audio to output queue."""
        async with self._pending_audio_lock:
            if not self._pending_audio:
                return

            # Concatenate pending audio
            combined = np.concatenate(self._pending_audio)
            self._pending_audio.clear()

        # Track first emission latency
        if self._first_speech_time is not None and self._first_emission_time is None:
            self._first_emission_time = time.monotonic()
            first_word_latency = (self._first_emission_time - self._first_speech_time) * 1000
            logger.info(
                f"First-word latency: {first_word_latency:.1f}ms",
                extra={"latency_ms": first_word_latency},
            )

            if first_word_latency > self.wispr_config.target_first_word_latency_ms:
                self._health.last_warning = (
                    f"First-word latency {first_word_latency:.1f}ms exceeds target "
                    f"({self.wispr_config.target_first_word_latency_ms}ms)"
                )

        # Add to output queue (non-blocking)
        try:
            self._output_queue.put_nowait(combined)
            self._last_emission_time = time.monotonic()
        except asyncio.QueueFull:
            self._health.frames_dropped += 1
            self._health.buffer_overruns += 1
            logger.warning("Output queue full, dropping audio frame")

    def probe_device(self, *, duration: float, output_dir: Path) -> DeviceProbeResult:
        """Probe microphone device."""
        if self._backend is None:
            raise RuntimeError("Backend not initialized")

        return self._backend.probe(duration=duration, output_dir=output_dir)

    def get_latency_metrics(self) -> dict[str, Any]:
        """Get latency metrics for this session."""
        return {
            "target_first_word_latency_ms": self.wispr_config.target_first_word_latency_ms,
            "frame_duration_ms": self.wispr_config.frame_duration_ms,
            "pre_buffer_duration_ms": self.wispr_config.pre_buffer_duration_ms,
            "actual_first_word_latency_ms": (
                (self._first_emission_time - self._first_speech_time) * 1000
                if self._first_emission_time and self._first_speech_time
                else None
            ),
            "average_frame_latency_ms": self._health.average_latency_ms,
        }
