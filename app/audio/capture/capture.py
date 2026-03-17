"""Audio capture module for system loopback and microphone input.

Provides LoopbackAudioSource class for capturing system audio via
WASAPI loopback or alternative audio backends. Handles device discovery,
audio backend selection, level metering, and frame dropping.

This module is the canonical location for audio capture. Legacy imports
from app.audio.capture are redirected here with deprecation warnings.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from app.audio.backends import AudioBackendError, open_audio_backend
from app.audio.backends.base import sanitize_audio
from app.audio.devices import resolve_capture_device
from app.core.models import DeviceProbeResult

logger = logging.getLogger(__name__)


class LoopbackAudioSource:
    """Captures system audio via loopback (WASAPI) or microphone input.

    Thread-safe audio source that runs a background capture thread, pushes
    audio frames to a bounded queue, and provides level metering. Supports
    automatic backend fallback and device discovery.

    Lifecycle:
        1. Create instance with desired audio parameters
        2. Call start() to begin capture thread
        3. Call read() to retrieve audio frames (blocks up to timeout)
        4. Call stop() to terminate capture (blocks up to 3s)

    Thread Safety:
        - All public methods are thread-safe via internal locking
        - Single producer (capture thread) -> single consumer pattern

    Error Handling:
        - Backend errors trigger on_error callback if set
        - Dropped frames are tracked in dropped_frames counter
        - Queue full causes oldest frame drop with logged warning
    """

    def __init__(
        self,
        *,
        device_id: str | None,
        sample_rate: int,
        channels: int,
        block_size: int,
        max_queue_items: int,
        audio_backend: str = "auto",
    ) -> None:
        self.device_id = device_id
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = block_size
        self.audio_backend_preference = audio_backend
        self.backend_name: str | None = None
        self.backend_fallbacks: list[str] = []
        self.queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=max_queue_items)
        self.level_rms = 0.0
        self.dropped_frames = 0
        self.on_error: Callable[[Exception], None] | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._thread_lock = threading.Lock()
        logger.debug(
            "AudioSource initialized",
            extra={
                "device_id": device_id,
                "sample_rate": sample_rate,
                "channels": channels,
                "block_size": block_size,
                "max_queue_items": max_queue_items,
                "audio_backend": audio_backend,
            },
        )

    def start(self) -> None:
        with self._thread_lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name="audio-capture", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._thread_lock:
            logger.debug(
                "Audio capture stopping",
                extra={
                    "device_id": self.device_id,
                    "thread_alive": self._thread.is_alive() if self._thread else False,
                    "dropped_frames": self.dropped_frames,
                    "final_level_rms": self.level_rms,
                    "audio_backend": self.backend_name,
                },
            )
            self._stop_event.set()
            if self._thread:
                self._thread.join(timeout=3)
                if self._thread.is_alive():
                    logger.warning(
                        "Audio capture thread did not terminate within timeout",
                        extra={"device_id": self.device_id},
                    )
                else:
                    logger.debug(
                        "Audio capture thread joined successfully",
                        extra={"device_id": self.device_id},
                    )

    def read(self, timeout: float = 0.25) -> np.ndarray | None:
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _run(self) -> None:
        last_stats_log_time = 0.0
        stats_log_interval = 2.0
        frames_since_last_log = 0
        last_logged_dropped_frames = 0
        backend = None

        try:
            selection = open_audio_backend(
                device_id=self.device_id,
                sample_rate=self.sample_rate,
                channels=self.channels,
                block_size=self.block_size,
                preferred_backend=self.audio_backend_preference,
            )
            backend = selection.backend
            self.backend_name = backend.backend_name
            self.backend_fallbacks = list(selection.failed_backends)
            backend.start()
            logger.debug(
                "Audio backend opened",
                extra={
                    "device_id": self.device_id,
                    "audio_backend": self.backend_name,
                    "runtime_sample_rate": backend.runtime_sample_rate,
                    "runtime_channels": backend.runtime_channels,
                    "fallbacks": self.backend_fallbacks,
                },
            )

            consecutive_errors = 0
            max_consecutive_errors = 5

            while not self._stop_event.is_set():
                try:
                    data = backend.read(timeout=0.25)
                    if data is None or data.size == 0:
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            device_error = RuntimeError(
                                f"Audio device '{self.device_id or 'default'}' stopped providing data."
                            )
                            if self.on_error:
                                self.on_error(device_error)
                            self._stop_event.set()
                            break
                        continue

                    consecutive_errors = 0
                    mono_safe = sanitize_audio(data)
                    self.level_rms = float(np.sqrt(np.mean(np.square(mono_safe)) + 1e-12))

                    now = time.monotonic()
                    frames_since_last_log += 1

                    try:
                        self.queue.put(mono_safe, timeout=0.2)
                    except queue.Full:
                        self.dropped_frames += 1

                    if (
                        now - last_stats_log_time >= stats_log_interval
                        or self.dropped_frames != last_logged_dropped_frames
                    ):
                        logger.debug(
                            "Audio capture stats",
                            extra={
                                "device_id": self.device_id,
                                "audio_backend": self.backend_name,
                                "runtime_sample_rate": backend.runtime_sample_rate,
                                "output_sample_rate": self.sample_rate,
                                "queue_size": self.queue.qsize(),
                                "queue_maxsize": self.queue.maxsize,
                                "level_rms": self.level_rms,
                                "frames_processed": frames_since_last_log,
                                "dropped_frames": self.dropped_frames,
                            },
                        )
                        last_stats_log_time = now
                        frames_since_last_log = 0
                        last_logged_dropped_frames = self.dropped_frames
                except Exception as record_exc:
                    consecutive_errors += 1
                    logger.debug(
                        "Audio record exception",
                        extra={
                            "device_id": self.device_id,
                            "audio_backend": self.backend_name,
                            "consecutive_errors": consecutive_errors,
                            "error": str(record_exc),
                            "error_type": type(record_exc).__name__,
                        },
                    )
                    if consecutive_errors >= max_consecutive_errors:
                        device_error = RuntimeError(
                            f"Audio device '{self.device_id or 'default'}' failed: {record_exc}."
                        )
                        if self.on_error:
                            self.on_error(device_error)
                        self._stop_event.set()
                        break
        except Exception as exc:
            fallback_name = None
            try:
                _, fallback_name = resolve_capture_device(self.device_id)
            except Exception as resolve_exc:
                logger.debug(f"Failed to resolve fallback device: {resolve_exc}")
                fallback_name = None
            failure_details = ""
            if isinstance(exc, AudioBackendError):
                self.backend_name = exc.backend_name
                self.backend_fallbacks = [attempt.backend_name for attempt in exc.attempts]
                failure_details = exc.describe_attempts()
            device_error = RuntimeError(
                f"Audio capture failed for device '{self.device_id}': {exc}."
                + (f"\n{failure_details}" if failure_details else "")
                + (
                    f" Suggested fallback: '{fallback_name}'."
                    if fallback_name and fallback_name != self.device_id
                    else ""
                )
                + " Please choose a loopback or VB-Cable device that can be opened."
            )
            logger.debug(
                "Audio capture initialization failed",
                extra={
                    "device_id": self.device_id,
                    "audio_backend": self.backend_name,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "fallbacks": self.backend_fallbacks,
                },
            )
            if self.on_error:
                self.on_error(device_error)
        finally:
            if backend is not None:
                try:
                    backend.stop()
                except Exception as stop_exc:
                    logger.warning(
                        "Audio backend stop failed",
                        extra={
                            "device_id": self.device_id,
                            "audio_backend": self.backend_name,
                            "error": str(stop_exc),
                            "error_type": type(stop_exc).__name__,
                        },
                    )

    @classmethod
    def probe_device(
        cls,
        device_id: str | None,
        sample_rate: int,
        channels: int,
        duration: float,
        output_dir: Path,
        audio_backend: str = "auto",
    ) -> DeviceProbeResult:
        logger.debug(
            "Device probe starting",
            extra={
                "device_id": device_id,
                "sample_rate": sample_rate,
                "channels": channels,
                "duration": duration,
                "output_dir": str(output_dir),
                "audio_backend": audio_backend,
            },
        )
        selection = open_audio_backend(
            device_id=device_id,
            sample_rate=sample_rate,
            channels=channels,
            block_size=1024,
            preferred_backend=audio_backend,
        )
        backend = selection.backend
        try:
            result = backend.probe(duration=duration, output_dir=output_dir)
            logger.debug(
                "Device probe completed successfully",
                extra={
                    "device_id": device_id,
                    "audio_backend": result.backend,
                    "sample_rate": result.sample_rate,
                    "channels": result.channels,
                    "duration": result.duration,
                    "rms_mean": result.rms_mean,
                    "rms_peak": result.rms_peak,
                    "has_signal": result.has_signal,
                    "dominant_channels": result.dominant_channels,
                    "dropped_frames": result.dropped_frames,
                    "wav_path": str(result.wav_path),
                },
            )
            return result
        finally:
            try:
                backend.stop()
            except Exception as stop_exc:
                logger.warning(
                    "Probe backend stop failed",
                    extra={
                        "device_id": device_id,
                        "audio_backend": backend.backend_name
                        if hasattr(backend, "backend_name")
                        else None,
                        "error": str(stop_exc),
                        "error_type": type(stop_exc).__name__,
                    },
                )


class MeterSmoother:
    def __init__(self, decay: float) -> None:
        self.decay = decay
        self.value = 0.0
        self.updated_at = time.monotonic()

    def update(self, new_value: float) -> float:
        now = time.monotonic()
        elapsed = max(now - self.updated_at, 0.0)
        self.updated_at = now
        decay_factor = np.exp(-elapsed / max(self.decay, 1e-6))
        self.value = max(float(new_value), self.value * float(decay_factor))
        return self.value
