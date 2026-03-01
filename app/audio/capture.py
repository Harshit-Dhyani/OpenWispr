from __future__ import annotations

import logging
import queue
import threading
import time
import wave
from collections.abc import Callable
from pathlib import Path

import numpy as np

from app.audio.devices import resolve_capture_device
from app.core.models import DeviceProbeResult

logger = logging.getLogger(__name__)


class LoopbackAudioSource:
    def __init__(
        self,
        *,
        device_id: str | None,
        sample_rate: int,
        channels: int,
        block_size: int,
        max_queue_items: int,
    ) -> None:
        self.device_id = device_id
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = block_size
        self.queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=max_queue_items)
        self.level_rms = 0.0
        self.dropped_frames = 0
        self.on_error: Callable[[Exception], None] | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        logger.debug(
            "LoopbackAudioSource initialized",
            extra={
                "device_id": device_id,
                "sample_rate": sample_rate,
                "channels": channels,
                "block_size": block_size,
                "max_queue_items": max_queue_items,
            },
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="audio-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        logger.debug(
            "Audio capture stopping",
            extra={
                "device_id": self.device_id,
                "thread_alive": self._thread.is_alive() if self._thread else False,
                "dropped_frames": self.dropped_frames,
                "final_level_rms": self.level_rms,
            },
        )
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
            logger.debug(
                "Audio capture thread joined",
                extra={
                    "device_id": self.device_id,
                    "thread_alive": self._thread.is_alive(),
                },
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

        try:
            device, resolved_name = resolve_capture_device(self.device_id)
            logger.debug(
                "Audio device resolved",
                extra={
                    "device_id": self.device_id,
                    "resolved_name": resolved_name,
                    "sample_rate": self.sample_rate,
                    "channels": self.channels,
                    "block_size": self.block_size,
                },
            )
            with device.recorder(
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=self.block_size,
            ) as recorder:
                logger.debug(
                    "Audio recorder initialized",
                    extra={
                        "device_id": self.device_id,
                        "resolved_name": resolved_name,
                    },
                )
                consecutive_errors = 0
                max_consecutive_errors = 5

                while not self._stop_event.is_set():
                    try:
                        data = recorder.record(numframes=self.block_size)
                        if data is None or (hasattr(data, "size") and data.size == 0):
                            consecutive_errors += 1
                            logger.debug(
                                "Empty audio frame received",
                                extra={
                                    "device_id": self.device_id,
                                    "consecutive_errors": consecutive_errors,
                                    "max_consecutive_errors": max_consecutive_errors,
                                },
                            )
                            if consecutive_errors >= max_consecutive_errors:
                                device_error = RuntimeError(
                                    f"Audio device '{resolved_name or self.device_id}' stopped providing data. "
                                    "The device may have been disconnected or is no longer available."
                                )
                                logger.debug(
                                    "Max consecutive errors reached, triggering error callback",
                                    extra={
                                        "device_id": self.device_id,
                                        "consecutive_errors": consecutive_errors,
                                        "error": str(device_error),
                                    },
                                )
                                if self.on_error:
                                    self.on_error(device_error)
                                self._stop_event.set()
                                break
                            continue

                        consecutive_errors = 0
                        mono = self._to_mono(data)
                        mono_safe = np.clip(mono.astype(np.float32, copy=False), -1.0, 1.0)
                        self.level_rms = float(np.sqrt(np.mean(np.square(mono_safe)) + 1e-12))

                        now = time.monotonic()
                        frames_since_last_log += 1

                        try:
                            self.queue.put(mono, timeout=0.2)
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
                                "consecutive_errors": consecutive_errors,
                                "error": str(record_exc),
                                "error_type": type(record_exc).__name__,
                            },
                        )
                        if consecutive_errors >= max_consecutive_errors:
                            device_error = RuntimeError(
                                f"Audio device '{resolved_name or self.device_id}' failed: {record_exc}. "
                                "The device may have been disconnected or is no longer available."
                            )
                            logger.debug(
                                "Max consecutive errors reached, triggering error callback",
                                extra={
                                    "device_id": self.device_id,
                                    "consecutive_errors": consecutive_errors,
                                    "error": str(device_error),
                                },
                            )
                            if self.on_error:
                                self.on_error(device_error)
                            self._stop_event.set()
                            break
        except Exception as exc:
            device_error = RuntimeError(
                f"Audio capture failed for device '{self.device_id}': {exc}. "
                "Please check the device is connected and not in use by another application."
            )
            logger.debug(
                "Audio capture initialization failed",
                extra={
                    "device_id": self.device_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            if self.on_error:
                self.on_error(device_error)

    @staticmethod
    def _to_mono(data: np.ndarray) -> np.ndarray:
        if data.ndim == 1:
            return data.astype(np.float32, copy=False)
        if data.shape[1] == 1:
            return data[:, 0].astype(np.float32, copy=False)

        channels = np.clip(data.astype(np.float32, copy=False), -1.0, 1.0)
        channel_energy = np.sqrt(np.mean(np.square(channels), axis=0) + 1e-12)
        strongest = float(np.max(channel_energy))
        if strongest <= 1e-6:
            return channels.mean(axis=1).astype(np.float32, copy=False)

        active_indices = np.flatnonzero(channel_energy >= strongest * 0.35)
        if active_indices.size == 0:
            active_indices = np.array([int(np.argmax(channel_energy))])
        if active_indices.size > 2:
            active_indices = np.argsort(channel_energy)[-2:]

        selected = channels[:, active_indices]
        mono = selected.mean(axis=1)
        peak = float(np.max(np.abs(mono)))
        if peak > 1.0:
            mono = mono / peak
        return mono.astype(np.float32, copy=False)

    @classmethod
    def probe_device(
        cls,
        device_id: str | None,
        sample_rate: int,
        channels: int,
        duration: float,
        output_dir: Path,
    ) -> DeviceProbeResult:
        logger.debug(
            "Device probe starting",
            extra={
                "device_id": device_id,
                "sample_rate": sample_rate,
                "channels": channels,
                "duration": duration,
                "output_dir": str(output_dir),
            },
        )

        block_size = 1024
        num_blocks = int((duration * sample_rate) / block_size)
        actual_duration = (num_blocks * block_size) / sample_rate

        try:
            device, resolved_name = resolve_capture_device(device_id)
            logger.debug(
                "Device resolved for probe",
                extra={
                    "device_id": device_id,
                    "resolved_name": resolved_name,
                },
            )
        except Exception as exc:
            logger.debug(
                "Device probe failed - could not resolve device",
                extra={
                    "device_id": device_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            raise

        frames: list[np.ndarray] = []
        dropped_frames = 0
        rms_values: list[float] = []
        peak_values: list[float] = []
        channel_energies: list[np.ndarray] = []

        try:
            with device.recorder(
                samplerate=sample_rate,
                channels=channels,
                blocksize=block_size,
            ) as recorder:
                logger.debug(
                    "Probe recorder initialized",
                    extra={
                        "device_id": device_id,
                        "block_size": block_size,
                        "num_blocks": num_blocks,
                    },
                )
                for block_idx in range(num_blocks):
                    data = recorder.record(numframes=block_size)
                    if data is None or data.size == 0:
                        dropped_frames += 1
                        logger.debug(
                            "Probe frame dropped",
                            extra={
                                "device_id": device_id,
                                "block_idx": block_idx,
                                "dropped_frames": dropped_frames,
                            },
                        )
                        continue
                    frames.append(data.copy())
                    mono = cls._to_mono(data)
                    mono_safe = np.clip(mono.astype(np.float32, copy=False), -1.0, 1.0)
                    rms = float(np.sqrt(np.mean(np.square(mono_safe)) + 1e-12))
                    peak = float(np.max(np.abs(mono)))
                    rms_values.append(rms)
                    peak_values.append(peak)
                    if data.ndim > 1 and data.shape[1] > 1:
                        ch_data = np.clip(data.astype(np.float32, copy=False), -1.0, 1.0)
                        energy = np.sqrt(np.mean(np.square(ch_data), axis=0) + 1e-12)
                        channel_energies.append(energy)

                logger.debug(
                    "Probe recording complete",
                    extra={
                        "device_id": device_id,
                        "captured_frames": len(frames),
                        "dropped_frames": dropped_frames,
                        "total_blocks": num_blocks,
                    },
                )
        except Exception as exc:
            logger.debug(
                "Probe recording failed",
                extra={
                    "device_id": device_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            raise

        if not frames:
            rms_mean = 0.0
            rms_peak = 0.0
            has_signal = False
            dominant_channels = []
            logger.debug(
                "Probe completed - no frames captured",
                extra={
                    "device_id": device_id,
                    "dropped_frames": dropped_frames,
                },
            )
        else:
            rms_mean = float(np.mean(rms_values)) if rms_values else 0.0
            rms_peak = float(np.max(peak_values)) if peak_values else 0.0
            has_signal = rms_mean > 1e-4

            if channel_energies:
                avg_energy = np.mean(channel_energies, axis=0)
                strongest = float(np.max(avg_energy))
                if strongest > 1e-6:
                    threshold = strongest * 0.35
                    dominant_channels = [int(i) for i in np.flatnonzero(avg_energy >= threshold)]
                else:
                    dominant_channels = []
            else:
                dominant_channels = []

            logger.debug(
                "Probe stats calculated",
                extra={
                    "device_id": device_id,
                    "rms_mean": rms_mean,
                    "rms_peak": rms_peak,
                    "has_signal": has_signal,
                    "dominant_channels": dominant_channels,
                    "rms_values_count": len(rms_values),
                },
            )

        all_audio = np.concatenate(frames) if frames else np.zeros((0,), dtype=np.float32)
        if all_audio.ndim == 1:
            all_audio = all_audio.reshape(-1, 1)

        wav_path = output_dir / f"probe_{device_id or 'default'}_{int(time.time())}.wav"
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(wav_path), "wb") as wav_file:
            wav_file.setnchannels(all_audio.shape[1] if all_audio.ndim > 1 else 1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            audio_int16 = (all_audio * 32767).astype(np.int16)
            wav_file.writeframes(audio_int16.tobytes())

        result = DeviceProbeResult(
            sample_rate=sample_rate,
            channels=channels,
            duration=actual_duration,
            rms_mean=rms_mean,
            rms_peak=rms_peak,
            has_signal=has_signal,
            dominant_channels=dominant_channels,
            dropped_frames=dropped_frames,
            wav_path=wav_path,
        )

        logger.debug(
            "Device probe completed successfully",
            extra={
                "device_id": device_id,
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


class MeterSmoother:
    def __init__(self, decay: float) -> None:
        self.decay = decay
        self.value = 0.0
        self.updated_at = time.monotonic()

    def update(self, new_value: float) -> float:
        now = time.monotonic()
        elapsed = max(now - self.updated_at, 0.0)
        self.updated_at = now
        weight = self.decay ** max(elapsed * 10.0, 1.0)
        self.value = max(new_value, self.value * weight)
        return self.value
