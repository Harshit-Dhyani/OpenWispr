from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.core.models import DeviceProbeResult


@dataclass(slots=True)
class BackendAttempt:
    backend: str
    device_name: str
    sample_rate: int
    channels: int
    error_type: str
    error: str

    @property
    def backend_name(self) -> str:
        return self.backend


@dataclass(slots=True)
class AudioBackendError(RuntimeError):
    backend: str
    attempts: list[BackendAttempt] = field(default_factory=list)
    message: str = ""

    def __post_init__(self) -> None:
        if not self.message:
            details = self.describe_attempts()
            self.message = details or f"{self.backend} backend failed"
        RuntimeError.__init__(self, self.message)

    @property
    def backend_name(self) -> str:
        return self.backend

    def describe_attempts(self) -> str:
        return "\n".join(
            f"  - [{attempt.backend}] {attempt.device_name} @ {attempt.sample_rate}Hz, "
            f"{attempt.channels}ch: {attempt.error_type}: {attempt.error}"
            for attempt in self.attempts
        )


def sanitize_audio(samples: np.ndarray) -> np.ndarray:
    return np.nan_to_num(
        np.clip(samples.astype(np.float32, copy=False), -1.0, 1.0),
        nan=0.0,
        posinf=1.0,
        neginf=-1.0,
    )


def to_mono(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        return sanitize_audio(data)

    if data.shape[1] == 1:
        return sanitize_audio(data[:, 0])

    channels = sanitize_audio(data)
    channel_energy = np.sqrt(np.mean(np.square(channels), axis=0) + 1e-12)
    strongest = float(np.max(channel_energy))
    if strongest <= 1e-6:
        return sanitize_audio(channels.mean(axis=1))

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
    return sanitize_audio(mono)


def resample_audio(
    samples: np.ndarray,
    *,
    source_rate: int,
    target_rate: int,
) -> np.ndarray:
    safe_samples = sanitize_audio(samples)
    if source_rate <= 0 or target_rate <= 0 or source_rate == target_rate:
        return safe_samples
    if safe_samples.size <= 1:
        return safe_samples

    target_length = max(1, int(round(safe_samples.size * target_rate / source_rate)))
    source_positions = np.linspace(0.0, safe_samples.size - 1, num=safe_samples.size)
    target_positions = np.linspace(0.0, safe_samples.size - 1, num=target_length)
    return sanitize_audio(np.interp(target_positions, source_positions, safe_samples))


class AudioBackend(ABC):
    backend_name: str
    resolved_name: str | None
    runtime_sample_rate: int
    runtime_channels: int

    def __init__(
        self,
        *,
        device_id: str | None,
        sample_rate: int,
        channels: int,
        block_size: int,
        name_hints: list[str] | None = None,
    ) -> None:
        self.device_id = device_id
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = block_size
        self.name_hints = name_hints or []
        self.resolved_name = None
        self.runtime_sample_rate = sample_rate
        self.runtime_channels = channels

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def read(self, timeout: float = 0.25) -> np.ndarray | None:
        pass

    @abstractmethod
    def probe(self, *, duration: float, output_dir: Path) -> DeviceProbeResult:
        pass

    @property
    @abstractmethod
    def is_running(self) -> bool:
        pass

    @staticmethod
    def build_probe_wav(
        *,
        output_dir: Path,
        device_id: str | None,
        audio: np.ndarray,
        sample_rate: int,
    ) -> Path:
        import time
        import wave

        wav_path = output_dir / f"probe_{device_id or 'default'}_{int(time.time())}.wav"
        wav_path.parent.mkdir(parents=True, exist_ok=True)

        all_audio = audio
        if all_audio.ndim == 1:
            all_audio = all_audio.reshape(-1, 1)

        with wave.open(str(wav_path), "wb") as wav_file:
            wav_file.setnchannels(all_audio.shape[1] if all_audio.ndim > 1 else 1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            audio_int16 = (np.clip(sanitize_audio(all_audio), -1.0, 1.0) * 32767).astype(np.int16)
            wav_file.writeframes(audio_int16.tobytes())
        return wav_path
