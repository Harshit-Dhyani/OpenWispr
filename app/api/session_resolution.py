from __future__ import annotations

from typing import Literal

from app.audio.devices import list_audio_devices
from app.core.settings.manager import get_settings_manager


def resolve_capture_source_setting(
    capture_source: Literal["microphone", "system"] | None,
) -> Literal["microphone", "system"]:
    if capture_source in {"microphone", "system"}:
        return capture_source
    settings = get_settings_manager().get_settings()
    return "system" if settings.audio.default_capture_source == "system" else "microphone"


def resolve_input_device_for_source(
    capture_source: Literal["microphone", "system"] | None,
    device_id: str | None,
) -> str | None:
    source = resolve_capture_source_setting(capture_source)
    normalized_device_id = device_id if device_id not in {None, "", "default"} else None
    devices = list_audio_devices()

    if source == "system":
        loopback_devices = [
            device for device in devices if device.is_loopback or device.supports_loopback
        ]
        if not loopback_devices:
            return normalized_device_id
        if normalized_device_id:
            selected = next(
                (device for device in loopback_devices if device.id == normalized_device_id),
                None,
            )
            if selected is not None:
                return selected.id
        settings = get_settings_manager().get_settings()
        preferred_id = settings.audio.defaultDeviceId
        selected = next((device for device in loopback_devices if device.id == preferred_id), None)
        return selected.id if selected is not None else loopback_devices[0].id

    microphones = [
        device
        for device in devices
        if device.is_input and not (device.is_loopback or device.supports_loopback)
    ]
    if not microphones:
        return normalized_device_id
    if normalized_device_id:
        selected = next((device for device in microphones if device.id == normalized_device_id), None)
        if selected is not None:
            return selected.id
    return microphones[0].id

