from __future__ import annotations

from typing import Any

import soundcard as sc

from app.core.models import AudioDeviceInfo


def _device_id(device: Any) -> str:
    return getattr(device, "id", None) or getattr(device, "name", "unknown")


def list_audio_devices() -> list[AudioDeviceInfo]:
    devices: list[AudioDeviceInfo] = []

    try:
        for speaker in sc.all_speakers():
            devices.append(
                AudioDeviceInfo(
                    id=_device_id(speaker),
                    name=f"{getattr(speaker, 'name', 'Speaker')} (WASAPI loopback)",
                    kind="speaker",
                    is_loopback=True,
                    channels=getattr(speaker, "channels", None),
                )
            )
    except Exception:
        pass

    try:
        for microphone in sc.all_microphones(include_loopback=True):
            name = getattr(microphone, "name", "Microphone")
            lowered = name.lower()
            devices.append(
                AudioDeviceInfo(
                    id=_device_id(microphone),
                    name=name,
                    kind="microphone",
                    is_loopback=("loopback" in lowered or "vb-audio" in lowered or "cable" in lowered),
                    channels=getattr(microphone, "channels", None),
                )
            )
    except Exception:
        pass

    deduped: dict[str, AudioDeviceInfo] = {}
    for device in devices:
        current = deduped.get(device.id)
        if current is None:
            deduped[device.id] = device
            continue
        if device.is_loopback and not current.is_loopback:
            deduped[device.id] = device
            continue
        if current.kind != "speaker" and device.kind == "speaker":
            deduped[device.id] = device
    return sorted(deduped.values(), key=lambda item: (not item.is_loopback, item.name.lower()))


def resolve_capture_device(device_id: str | None) -> tuple[Any, bool]:
    loopback_microphones = list(sc.all_microphones(include_loopback=True))

    if not device_id:
        default_speaker = sc.default_speaker()
        default_id = _device_id(default_speaker)
        for microphone in loopback_microphones:
            if getattr(microphone, "isloopback", False) and _device_id(microphone) == default_id:
                return microphone, True
        return loopback_microphones[0], True

    for microphone in loopback_microphones:
        if _device_id(microphone) == device_id:
            return microphone, bool(getattr(microphone, "isloopback", False))

    for speaker in sc.all_speakers():
        if _device_id(speaker) == device_id:
            for microphone in loopback_microphones:
                if getattr(microphone, "isloopback", False) and _device_id(microphone) == device_id:
                    return microphone, True

    return resolve_capture_device(None)
