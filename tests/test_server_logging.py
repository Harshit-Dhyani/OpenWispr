from __future__ import annotations

import sys
from types import SimpleNamespace

sys.modules.setdefault(
    "soundcard",
    SimpleNamespace(
        all_speakers=lambda: [],
        all_microphones=lambda include_loopback=True: [],
        default_microphone=lambda: None,
    ),
)
sys.modules.setdefault("faster_whisper", SimpleNamespace(WhisperModel=object))

from app.api.server import _resolve_log_level_from_settings_payload


def test_resolve_log_level_prefers_configured_log_level_over_debug_mode() -> None:
    payload = {"advanced": {"debugMode": True, "logLevel": "INFO"}}

    assert _resolve_log_level_from_settings_payload(payload) == "INFO"


def test_resolve_log_level_accepts_debug_when_requested() -> None:
    payload = {"advanced": {"debugMode": False, "logLevel": "DEBUG"}}

    assert _resolve_log_level_from_settings_payload(payload) == "DEBUG"


def test_resolve_log_level_falls_back_to_info_for_invalid_values() -> None:
    payload = {"advanced": {"debugMode": True, "logLevel": "LOUD"}}

    assert _resolve_log_level_from_settings_payload(payload) == "INFO"
