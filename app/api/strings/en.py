"""English string constants for API error messages and notifications.

This module provides centralized string constants for user-facing messages
in the API. Strings are organized into categories:

Error Strings:
- service_not_ready: Backend service not initialized
- hotkey_service_not_ready: Hotkey transcription service not ready
- unknown_model_category: Invalid model category requested
- unsupported_refinement_mode: Invalid refinement mode specified
- save_settings_failed: Settings persistence failed

Message Strings:
- settings_saved: Settings saved successfully confirmation
- settings_reset: Settings reset to defaults confirmation
- hotkey_inject_ready: Text ready for injection (Electron handles)
- hotkey_started: Hotkey session started notification
- hotkey_config_updated: Hotkey configuration updated confirmation

Usage:
    from app.api.strings.en import API_STRINGS
    
    raise HTTPException(400, detail=API_STRINGS.errors.save_settings_failed)

This centralized approach ensures consistent messaging across the API
and simplifies localization efforts in the future.
"""

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
