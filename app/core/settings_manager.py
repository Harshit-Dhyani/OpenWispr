"""Persistent settings management for Transcripta.

This module handles loading, saving, and migrating user settings
to a JSON file in the application directory.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "GeneralSettings",
    "TranscriptionSettings",
    "AudioSettings",
    "HotkeySettings",
    "AdvancedSettings",
    "SettingsState",
    "DEFAULT_SETTINGS_STATE",
    "SettingsManager",
    "get_settings_manager",
]


@dataclass
class GeneralSettings:
    defaultSessionTitle: str = "New Session"
    defaultLanguage: str = "auto"
    exportDirectory: str = ""
    autoSaveInterval: int = 30
    showNotifications: bool = True
    minimizeToTray: bool = True
    startupWithSystem: bool = False
    theme: str = "light"


@dataclass
class TranscriptionSettings:
    model_name: str = "medium"
    compute_type: str = "float16"
    chunk_duration: float = 1.6
    overlap_ratio: float = 0.2
    vad_enabled: bool = True
    vad_threshold_db: float = -40.0
    confidence_threshold: float = 0.6
    enable_filler_filter: bool = True
    enable_hallucination_filter: bool = True
    min_segment_length: float = 0.5
    max_workers: int = 4
    use_parallel_processing: bool = True
    preload_model: bool = True
    hotkey_optimized: bool = False
    beam_size: int = 5
    best_of: int = 5
    patience: float = 1.0
    temperature: float = 0.0


@dataclass
class AudioSettings:
    defaultDeviceId: str = "default"
    sampleRate: int = 16000
    vadEnabled: bool = True
    vadThresholdDb: float = -40.0
    noiseFiltering: bool = True
    echoCancellation: bool = True
    autoGainControl: bool = True


@dataclass
class HotkeySettings:
    enabled: bool = True
    key_combination: str = "Ctrl+Shift+T"
    hold_mode: bool = False
    auto_inject: bool = True
    show_floating_window: bool = True
    floating_window_position: str = "bottom-right"
    record_on_start: bool = True
    stop_on_release: bool = False
    copy_to_clipboard: bool = True


@dataclass
class AdvancedSettings:
    debugMode: bool = False
    logLevel: str = "INFO"
    enableMetrics: bool = True
    maxLogFiles: int = 10
    experimentalStem: bool = False
    experimentalGpuAccel: bool = True


@dataclass
class SettingsState:
    general: GeneralSettings = field(default_factory=GeneralSettings)
    transcription: TranscriptionSettings = field(default_factory=TranscriptionSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    hotkey: HotkeySettings = field(default_factory=HotkeySettings)
    advanced: AdvancedSettings = field(default_factory=AdvancedSettings)
    version: int = 1


# Default settings instance
DEFAULT_SETTINGS_STATE = SettingsState()


class SettingsManager:
    """Manages persistent storage of user settings."""

    SETTINGS_FILENAME = "user_settings.json"
    CURRENT_VERSION = 1

    def __init__(self, settings_dir: Path | None = None) -> None:
        """Initialize the settings manager.

        Args:
            settings_dir: Directory to store settings file. Defaults to app directory.
        """
        if settings_dir is None:
            # Store in app directory (where the app package is located)
            app_dir = Path(__file__).parent.parent.parent
            self.settings_path = app_dir / self.SETTINGS_FILENAME
        else:
            self.settings_path = settings_dir / self.SETTINGS_FILENAME

        self._settings: SettingsState = DEFAULT_SETTINGS_STATE
        self._load()

    def _load(self) -> None:
        """Load settings from disk or create with defaults."""
        if not self.settings_path.exists():
            logger.info("Settings file not found, creating with defaults: %s", self.settings_path)
            self._settings = DEFAULT_SETTINGS_STATE
            self._save()
            return

        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Migrate if needed
            data = self._migrate(data)

            # Parse settings
            self._settings = SettingsState(
                general=GeneralSettings(**data.get("general", {})),
                transcription=TranscriptionSettings(**data.get("transcription", {})),
                audio=AudioSettings(**data.get("audio", {})),
                hotkey=HotkeySettings(**data.get("hotkey", {})),
                advanced=AdvancedSettings(**data.get("advanced", {})),
                version=data.get("version", self.CURRENT_VERSION),
            )
            logger.debug("Settings loaded from %s", self.settings_path)

        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Failed to load settings (%s), using defaults", exc)
            self._settings = DEFAULT_SETTINGS_STATE
            self._save()

    def _save(self) -> None:
        """Save current settings to disk."""
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self._settings), f, indent=2)
            logger.debug("Settings saved to %s", self.settings_path)
        except (OSError, TypeError) as exc:
            logger.error("Failed to save settings: %s", exc)

    def _migrate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Migrate settings from older versions."""
        version = data.get("version", 0)

        if version < 1:
            # Migration from pre-versioned settings (if any)
            pass

        data["version"] = self.CURRENT_VERSION
        return data

    def get_settings(self) -> SettingsState:
        """Get current settings."""
        return self._settings

    def update_settings(self, settings: SettingsState) -> None:
        """Update settings and save to disk."""
        self._settings = settings
        self._save()

    def update_partial(self, category: str, updates: dict[str, Any]) -> None:
        """Update a specific category of settings."""
        if hasattr(self._settings, category):
            category_obj = getattr(self._settings, category)
            for key, value in updates.items():
                if hasattr(category_obj, key):
                    setattr(category_obj, key, value)
            self._save()
            logger.debug("Updated settings category '%s': %s", category, updates)
        else:
            logger.warning("Unknown settings category: %s", category)

    def reset_to_defaults(self) -> SettingsState:
        """Reset all settings to defaults."""
        self._settings = DEFAULT_SETTINGS_STATE
        self._save()
        logger.info("Settings reset to defaults")
        return self._settings

    def get_settings_dict(self) -> dict[str, Any]:
        """Get settings as a dictionary for API responses."""
        return asdict(self._settings)

    def import_settings(self, data: dict[str, Any]) -> bool:
        """Import settings from a dictionary (e.g., from file upload)."""
        try:
            # Validate required categories
            required = ["general", "transcription", "audio", "hotkey", "advanced"]
            for cat in required:
                if cat not in data:
                    data[cat] = {}

            self._settings = SettingsState(
                general=GeneralSettings(**data.get("general", {})),
                transcription=TranscriptionSettings(**data.get("transcription", {})),
                audio=AudioSettings(**data.get("audio", {})),
                hotkey=HotkeySettings(**data.get("hotkey", {})),
                advanced=AdvancedSettings(**data.get("advanced", {})),
                version=data.get("version", self.CURRENT_VERSION),
            )
            self._save()
            logger.info("Settings imported successfully")
            return True
        except (TypeError, ValueError) as exc:
            logger.error("Failed to import settings: %s", exc)
            return False


# Global settings manager instance
_settings_manager: SettingsManager | None = None


def get_settings_manager() -> SettingsManager:
    """Get or create the global settings manager instance."""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
