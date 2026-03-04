from __future__ import annotations

import time
from typing import Any

import numpy as np

from app.audio.backends.base import (
    AudioBackend,
    AudioBackendError,
    BackendAttempt,
    resample_audio,
    sanitize_audio,
    to_mono,
)
from app.core.models import DeviceProbeResult
from app.audio.devices import candidate_channel_counts, resolve_capture_device_candidates


class SoundcardBackend(AudioBackend):
    backend_name = "soundcard"

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
        self._recorder_context: Any = None
        self._recorder: Any = None
        self._running = False
        self.attempts: list[BackendAttempt] = []

    def start(self) -> None:
        fallback_rates = [48000, 44100, 16000]
        sample_rates_to_try = [self.sample_rate] + [
            r for r in fallback_rates if r != self.sample_rate
        ]
        last_exc: Exception | None = None

        for device, candidate_name in resolve_capture_device_candidates(self.device_id):
            device_channels = getattr(device, "channels", None)
            for channel_count in candidate_channel_counts(self.channels, device_channels):
                for rate in sample_rates_to_try:
                    recorder_context = None
                    try:
                        recorder_context = device.recorder(
                            samplerate=rate,
                            channels=channel_count,
                            blocksize=self.block_size,
                        )
                        recorder = recorder_context.__enter__()
                        self._recorder_context = recorder_context
                        self._recorder = recorder
                        self.resolved_name = candidate_name
                        self.runtime_sample_rate = rate
                        self.runtime_channels = channel_count
                        self._running = True
                        return
                    except (AssertionError, OSError, RuntimeError) as exc:
                        if recorder_context is not None:
                            try:
                                recorder_context.__exit__(type(exc), exc, exc.__traceback__)
                            except Exception:
                                pass
                        last_exc = exc
                        self.attempts.append(
                            BackendAttempt(
                                backend=self.backend_name,
                                device_name=candidate_name,
                                sample_rate=rate,
                                channels=channel_count,
                                error_type=type(exc).__name__,
                                error=str(exc),
                            )
                        )

        raise AudioBackendError(
            backend=self.backend_name,
            attempts=self.attempts,
            message=(f"No compatible capture path could be opened for device '{self.device_id}'."),
        ) from last_exc

    def stop(self) -> None:
        if self._recorder_context is not None:
            try:
                self._recorder_context.__exit__(None, None, None)
            finally:
                self._recorder_context = None
                self._recorder = None
        self._running = False

    def read(self, timeout: float = 0.25) -> np.ndarray | None:
        if self._recorder is None:
            return None
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            data = self._recorder.record(numframes=self.block_size)
            if data is None or (hasattr(data, "size") and data.size == 0):
                continue
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
