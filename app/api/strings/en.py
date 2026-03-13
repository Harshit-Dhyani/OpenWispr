from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _ErrorStrings:
    service_not_ready: str = "Service not ready"
    hotkey_service_not_ready: str = "Hotkey service not ready"
    unknown_model_category: str = "Unknown model category"
    unsupported_refinement_mode: str = "Unsupported refinement mode"
    save_settings_failed: str = "Failed to save settings"


@dataclass(frozen=True)
class _MessageStrings:
    settings_saved: str = "Settings saved successfully"
    settings_reset: str = "Settings reset to defaults"
    hotkey_inject_ready: str = "Text ready for injection (handled by Electron)"
    hotkey_started: str = "Hotkey session started"
    hotkey_config_updated: str = "Hotkey configuration updated"


@dataclass(frozen=True)
class _ApiStrings:
    errors: _ErrorStrings = _ErrorStrings()
    messages: _MessageStrings = _MessageStrings()


API_STRINGS = _ApiStrings()
