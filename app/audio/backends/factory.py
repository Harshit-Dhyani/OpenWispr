from __future__ import annotations

from dataclasses import dataclass, field

from app.audio.backends.base import AudioBackend, AudioBackendError
from app.audio.backends.pyaudio_wasapi import PyAudioWasapiBackend
from app.audio.backends.soundcard_backend import SoundcardBackend
from app.audio.devices import resolve_capture_name_hints


@dataclass(slots=True)
class AudioBackendSelection:
    backend: AudioBackend
    failed_backends: list[str] = field(default_factory=list)
    failed_details: list[str] = field(default_factory=list)


def _backend_classes(preferred_backend: str) -> list[type[AudioBackend]]:
    normalized = preferred_backend.lower()
    if normalized == "pyaudio":
        return [PyAudioWasapiBackend]
    if normalized == "soundcard":
        return [SoundcardBackend]
    return [PyAudioWasapiBackend, SoundcardBackend]


def open_audio_backend(
    *,
    device_id: str | None,
    sample_rate: int,
    channels: int,
    block_size: int,
    preferred_backend: str = "auto",
) -> AudioBackendSelection:
    failed_backends: list[str] = []
    failed_details: list[str] = []
    last_error: Exception | None = None
    name_hints = resolve_capture_name_hints(device_id)

    for backend_class in _backend_classes(preferred_backend):
        backend = backend_class(
            device_id=device_id,
            sample_rate=sample_rate,
            channels=channels,
            block_size=block_size,
            name_hints=name_hints,
        )
        try:
            backend.start()
            return AudioBackendSelection(
                backend=backend,
                failed_backends=failed_backends,
                failed_details=failed_details,
            )
        except Exception as exc:
            try:
                backend.stop()
            except Exception as stop_exc:
                failed_details.append(f"{backend.backend_name} stop failed: {stop_exc}")
            last_error = exc
            failed_backends.append(backend.backend_name)
            failed_details.append(str(exc))

    detail_text = "\n".join(f"  - {detail}" for detail in failed_details)
    raise RuntimeError(
        "No compatible audio backend could be opened.\n"
        f"Tried backends: {', '.join(failed_backends) or 'none'}\n"
        f"{detail_text}"
    ) from last_error
