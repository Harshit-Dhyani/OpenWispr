from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

from app.audio.backends.base import (
    AudioBackend,
    AudioBackendError,
    BackendAttempt,
    resample_audio,
    sanitize_audio,
    to_mono,
)
from app.core.models import DeviceProbeResult


def _normalize_name(name: str) -> str:
    return " ".join(
        "".join(character.lower() if character.isalnum() else " " for character in name).split()
    )


class PyAudioWasapiBackend(AudioBackend):
    backend_name = "pyaudio"

    def __init__(
        self,
        *,
        device_id: str | None,
        sample_rate: int,
        channels: int,
        block_size: int,
        name_hints: list[str] | None = None,
    ) -> None:
        super().__init__(
            device_id=device_id,
            sample_rate=sample_rate,
            channels=channels,
            block_size=block_size,
            name_hints=name_hints,
        )
        self._pa: Any = None
        self._stream: Any = None
        self._format: Any = None
        self._dtype = np.float32
        self._running = False
        self.attempts: list[BackendAttempt] = []

    def _iter_device_infos(self) -> list[dict[str, Any]]:
        device_infos: list[dict[str, Any]] = []
        count = self._pa.get_device_count()
        for index in range(count):
            info = dict(self._pa.get_device_info_by_index(index))
            info["index"] = index
            device_infos.append(info)
        return device_infos

    def _rank_device_infos(self, device_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        hints = [_normalize_name(name) for name in self.name_hints if name]
        ranked: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
        for info in device_infos:
            name = str(info.get("name", ""))
            normalized = _normalize_name(name)
            is_loopback = "loopback" in normalized
            is_virtual_cable = "vb audio" in normalized or "cable" in normalized
            exact_hint = any(hint == normalized for hint in hints)
            partial_hint = any(
                hint and (hint in normalized or normalized in hint) for hint in hints
            )
            ranked.append(
                (
                    (
                        0 if exact_hint else 1,
                        0 if partial_hint else 1,
                        0 if is_virtual_cable else 1,
                        0 if is_loopback else 1,
                        normalized,
                    ),
                    info,
                )
            )
        ranked.sort(key=lambda item: item[0])
        return [info for _, info in ranked]

    def start(self) -> None:
        try:
            import pyaudiowpatch as pyaudio  # type: ignore[import-not-found]
        except Exception as exc:
            raise AudioBackendError(
                backend=self.backend_name,
                message="PyAudioWPatch is not installed or could not be imported.",
            ) from exc

        self._pa = pyaudio.PyAudio()
        try:
            formats = [
                (pyaudio.paFloat32, np.float32),
                (pyaudio.paInt16, np.int16),
            ]

            device_infos = self._rank_device_infos(self._iter_device_infos())
            fallback_rates = [48000, 44100, 16000]
            last_exc: Exception | None = None

            for info in device_infos:
                device_name = str(info.get("name", "Unknown"))
                max_input_channels = int(info.get("maxInputChannels", 0) or 0)
                if max_input_channels <= 0:
                    continue

                default_rate = int(
                    float(info.get("defaultSampleRate", self.sample_rate) or self.sample_rate)
                )
                sample_rates_to_try = []
                for rate in (self.sample_rate, default_rate, *fallback_rates):
                    if rate not in sample_rates_to_try:
                        sample_rates_to_try.append(rate)

                for channel_count in (self.channels, 2, 1, max_input_channels):
                    if channel_count <= 0 or channel_count > max_input_channels:
                        continue
                    for rate in sample_rates_to_try:
                        for stream_format, dtype in formats:
                            try:
                                self._stream = self._pa.open(
                                    format=stream_format,
                                    channels=channel_count,
                                    rate=rate,
                                    input=True,
                                    output=False,
                                    input_device_index=int(info["index"]),
                                    frames_per_buffer=self.block_size,
                                    start=True,
                                )
                                self._format = stream_format
                                self._dtype = dtype
                                self.resolved_name = device_name
                                self.runtime_sample_rate = rate
                                self.runtime_channels = channel_count
                                self._running = True
                                return
                            except Exception as exc:
                                last_exc = exc
                                self.attempts.append(
                                    BackendAttempt(
                                        backend=self.backend_name,
                                        device_name=device_name,
                                        sample_rate=rate,
                                        channels=channel_count,
                                        error_type=type(exc).__name__,
                                        error=str(exc),
                                    )
                                )

            raise AudioBackendError(
                backend=self.backend_name,
                attempts=self.attempts,
                message=f"No compatible PyAudio/WASAPI capture path could be opened for '{self.device_id}'.",
            ) from last_exc
        except Exception as init_exc:
            logger.warning("PyAudio/WASAPI stream initialization failed: %s", init_exc)
            if self._stream is not None:
                try:
                    self._stream.close()
                except Exception as close_exc:
                    logger.warning("Failed to close PyAudio stream during cleanup: %s", close_exc)
                self._stream = None
            if self._pa is not None:
                try:
                    self._pa.terminate()
                except Exception as term_exc:
                    logger.warning(
                        "Failed to terminate PyAudio instance during cleanup: %s", term_exc
                    )
                self._pa = None
            raise

    def stop(self) -> None:
        if self._stream is not None:
            try:
                if self._stream.is_active():
                    self._stream.stop_stream()
            finally:
                self._stream.close()
                self._stream = None
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None
        self._running = False

    def read(self, timeout: float = 0.25) -> np.ndarray | None:
        if self._stream is None:
            return None

        start = time.monotonic()
        while time.monotonic() - start < timeout:
            available = 0
            try:
                available = int(self._stream.get_read_available())
            except Exception as exc:
                logger.warning("Failed to get available frames from PyAudio stream: %s", exc)
                available = self.block_size

            frames_to_read = max(1, min(self.block_size, available or self.block_size))
            try:
                raw = self._stream.read(frames_to_read, exception_on_overflow=False)
                expected_bytes = frames_to_read * (2 if self._dtype == np.int16 else 4)
                if len(raw) < expected_bytes:
                    logger.warning(
                        "Audio buffer overflow detected: "
                        f"expected={frames_to_read} frames ({expected_bytes} bytes), "
                        f"got={len(raw) // (2 if self._dtype == np.int16 else 4)} frames ({len(raw)} bytes)"
                    )
            except Exception as exc:
                logger.warning(f"Audio stream read error: {exc}")
                continue
            if not raw:
                continue

            array = np.frombuffer(raw, dtype=self._dtype)
            if self.runtime_channels > 1 and array.size >= self.runtime_channels:
                frames = array.size // self.runtime_channels
                array = array[: frames * self.runtime_channels].reshape(
                    frames, self.runtime_channels
                )

            if self._dtype == np.int16:
                data = array.astype(np.float32) / 32768.0
            else:
                data = array.astype(np.float32, copy=False)

            mono = to_mono(data)
            if self.runtime_sample_rate != self.sample_rate:
                mono = resample_audio(
                    mono,
                    source_rate=self.runtime_sample_rate,
                    target_rate=self.sample_rate,
                )
            return mono
        return None

    def probe(self, *, duration: float, output_dir) -> DeviceProbeResult:
        if output_dir is None:
            raise ValueError("output_dir must not be None")
        started_here = False
        if not self.is_running:
            self.start()
            started_here = True

        frames: list[np.ndarray] = []
        dropped_frames = 0
        end_time = time.monotonic() + max(duration, 0.25)

        try:
            while time.monotonic() < end_time:
                block = self.read(timeout=0.25)
                if block is None or block.size == 0:
                    dropped_frames += 1
                    continue
                frames.append(sanitize_audio(block))
        finally:
            if started_here:
                self.stop()

        if frames:
            audio = np.concatenate(frames).astype(np.float32, copy=False)
            rms_mean = float(np.sqrt(np.mean(np.square(audio)) + 1e-12))
            rms_peak = float(np.max(np.abs(audio)))
            has_signal = rms_mean > 1e-4
        else:
            audio = np.zeros((0,), dtype=np.float32)
            rms_mean = 0.0
            rms_peak = 0.0
            has_signal = False

        wav_path = self.build_probe_wav(
            output_dir=output_dir,
            device_id=self.device_id,
            audio=audio,
            sample_rate=self.sample_rate,
        )

        return DeviceProbeResult(
            backend=self.backend_name,
            sample_rate=self.sample_rate,
            channels=self.runtime_channels,
            duration=float(audio.size / max(self.sample_rate, 1)),
            rms_mean=rms_mean,
            rms_peak=rms_peak,
            has_signal=has_signal,
            dominant_channels=list(range(min(self.runtime_channels, 2))) if has_signal else [],
            dropped_frames=dropped_frames,
            wav_path=wav_path,
        )

    @property
    def is_running(self) -> bool:
        return self._running
