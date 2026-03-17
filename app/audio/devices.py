"""Re-exports audio device utilities from app.audio.devices.devices.

Canonical source is app.audio.devices.devices.
"""

from __future__ import annotations

from app.audio.devices.devices import (
    candidate_channel_counts,
    list_audio_devices,
    resolve_capture_device,
    resolve_capture_device_candidates,
    resolve_capture_name_hints,
)

__all__ = [
    "candidate_channel_counts",
    "list_audio_devices",
    "resolve_capture_device",
    "resolve_capture_device_candidates",
    "resolve_capture_name_hints",
]
