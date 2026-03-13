"""Backward compatibility shim - SettingsManager moved to app.core.settings.manager."""

from app.core.settings.manager import SettingsManager, SettingsState

__all__ = ["SettingsManager", "SettingsState"]
