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

from app.config.settings import (
    SETTINGS_REGISTRY,
    get_setting,
    get_category_defaults,
    get_all_defaults,
    FAKE_SETTINGS,
    CURRENT_SETTINGS_VERSION,
)
from app.core.settings_migrations import migrate_to_current, needs_migration
from app.core.settings_validator import SettingsValidator, ValidationResult

logger = logging.getLogger(__name__)

__all__ = [
    "GeneralSettings",
    "TranscriptionSettings",
    "RefinerSettings",
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
    """General application settings."""

    defaultSessionTitle: str = field(
        default_factory=lambda: get_setting("defaultSessionTitle").default
    )
    defaultLanguage: str = field(default_factory=lambda: get_setting("defaultLanguage").default)
    exportDirectory: str = field(default_factory=lambda: get_setting("exportDirectory").default)
    autoSaveInterval: int = field(default_factory=lambda: get_setting("autoSaveInterval").default)
    showNotifications: bool = field(
        default_factory=lambda: get_setting("showNotifications").default
    )
    minimizeToTray: bool = field(default_factory=lambda: get_setting("minimizeToTray").default)
    startupWithSystem: bool = field(
        default_factory=lambda: get_setting("startupWithSystem").default
    )
    theme: str = field(default_factory=lambda: get_setting("theme").default)


@dataclass
class TranscriptionSettings:
    """Transcription-related settings."""

    model_name: str = field(default_factory=lambda: get_setting("model_name").default)
    default_asr_model_id: str = field(
        default_factory=lambda: get_setting("default_asr_model_id").default
    )
    refinement_mode: str = field(default_factory=lambda: get_setting("refinement_mode").default)
    compute_type: str = field(default_factory=lambda: get_setting("compute_type").default)
    chunk_duration: float = field(default_factory=lambda: get_setting("chunk_duration").default)
    overlap_ratio: float = field(default_factory=lambda: get_setting("overlap_ratio").default)
    vad_enabled: bool = field(default_factory=lambda: get_setting("vad_enabled").default)
    vad_threshold_db: float = field(default_factory=lambda: get_setting("vad_threshold_db").default)
    vad_min_silence_ms: int = field(
        default_factory=lambda: get_setting("vad_min_silence_ms").default
    )
    vad_speech_pad_ms: int = field(default_factory=lambda: get_setting("vad_speech_pad_ms").default)
    confidence_threshold: float = field(
        default_factory=lambda: get_setting("confidence_threshold").default
    )
    enable_filler_filter: bool = field(
        default_factory=lambda: get_setting("enable_filler_filter").default
    )
    enable_hallucination_filter: bool = field(
        default_factory=lambda: get_setting("enable_hallucination_filter").default
    )
    min_segment_length: float = field(
        default_factory=lambda: get_setting("min_segment_length").default
    )
    max_workers: int = field(default_factory=lambda: get_setting("max_workers").default)
    use_parallel_processing: bool = field(
        default_factory=lambda: get_setting("use_parallel_processing").default
    )
    preload_model: bool = field(default_factory=lambda: get_setting("preload_model").default)
    hotkey_optimized: bool = field(default_factory=lambda: get_setting("hotkey_optimized").default)
    beam_size: int = field(default_factory=lambda: get_setting("beam_size").default)
    best_of: int = field(default_factory=lambda: get_setting("best_of").default)
    patience: float = field(default_factory=lambda: get_setting("patience").default)
    temperature: float = field(default_factory=lambda: get_setting("temperature").default)


@dataclass
class AudioSettings:
    """Audio capture settings."""

    captureMode: str = field(default_factory=lambda: get_setting("captureMode").default)
    defaultDeviceId: str = field(default_factory=lambda: get_setting("defaultDeviceId").default)
    backend: str = field(default_factory=lambda: get_setting("backend").default)
    audio_backend: str = field(default_factory=lambda: get_setting("audio_backend").default)
    sampleRate: int = field(default_factory=lambda: get_setting("sampleRate").default)
    vadEnabled: bool = field(default_factory=lambda: get_setting("vadEnabled").default)
    vadThresholdDb: float = field(default_factory=lambda: get_setting("vadThresholdDb").default)
    noiseFiltering: bool = field(default_factory=lambda: get_setting("noiseFiltering").default)
    echoCancellation: bool = field(default_factory=lambda: get_setting("echoCancellation").default)
    autoGainControl: bool = field(default_factory=lambda: get_setting("autoGainControl").default)


@dataclass
class RefinerSettings:
    """LLM refiner settings."""

    selected_model_id: str = field(default_factory=lambda: get_setting("selected_model_id").default)
    runtime_enabled: bool = field(default_factory=lambda: get_setting("runtime_enabled").default)
    engine_preference: str = field(default_factory=lambda: get_setting("engine_preference").default)


@dataclass
class HotkeySettings:
    """Global hotkey settings."""

    enabled: bool = field(default_factory=lambda: get_setting("enabled").default)
    key_combination: str = field(default_factory=lambda: get_setting("key_combination").default)
    hold_mode: bool = field(default_factory=lambda: get_setting("hold_mode").default)
    auto_inject: bool = field(default_factory=lambda: get_setting("auto_inject").default)
    language: str = field(default_factory=lambda: get_setting("language").default)
    device_id: str = field(default_factory=lambda: get_setting("device_id").default)
    finish_mode_default: str = field(
        default_factory=lambda: get_setting("finish_mode_default").default
    )
    show_floating_window: bool = field(
        default_factory=lambda: get_setting("show_floating_window").default
    )
    floating_window_position: str = field(
        default_factory=lambda: get_setting("floating_window_position").default
    )
    record_on_start: bool = field(default_factory=lambda: get_setting("record_on_start").default)
    stop_on_release: bool = field(default_factory=lambda: get_setting("stop_on_release").default)
    copy_to_clipboard: bool = field(
        default_factory=lambda: get_setting("copy_to_clipboard").default
    )


@dataclass
class AdvancedSettings:
    """Advanced settings."""

    debugMode: bool = field(default_factory=lambda: get_setting("debugMode").default)
    logLevel: str = field(default_factory=lambda: get_setting("logLevel").default)
    enableMetrics: bool = field(default_factory=lambda: get_setting("enableMetrics").default)
    maxLogFiles: int = field(default_factory=lambda: get_setting("maxLogFiles").default)
    experimentalStem: bool = field(default_factory=lambda: get_setting("experimentalStem").default)
    experimentalGpuAccel: bool = field(
        default_factory=lambda: get_setting("experimentalGpuAccel").default
    )


@dataclass
class SettingsState:
    """Complete application settings state."""

    general: GeneralSettings = field(default_factory=GeneralSettings)
    transcription: TranscriptionSettings = field(default_factory=TranscriptionSettings)
    refiner: RefinerSettings = field(default_factory=RefinerSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    hotkey: HotkeySettings = field(default_factory=HotkeySettings)
    advanced: AdvancedSettings = field(default_factory=AdvancedSettings)
    version: int = CURRENT_SETTINGS_VERSION


# Default settings instance
DEFAULT_SETTINGS_STATE = SettingsState()


class SettingsManager:
    """Manages persistent storage of user settings."""

    SETTINGS_FILENAME = "user_settings.json"
    CURRENT_VERSION = CURRENT_SETTINGS_VERSION

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
        self._validator = SettingsValidator(strict=False)
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

            # Migrate if needed using the new migration system
            if needs_migration(data):
                data = migrate_to_current(data)

            # Parse settings
            self._settings = SettingsState(
                general=GeneralSettings(**data.get("general", {})),
                transcription=TranscriptionSettings(**data.get("transcription", {})),
                refiner=RefinerSettings(**data.get("refiner", {})),
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

    def validate(self) -> ValidationResult:
        """Validate current settings.

        Returns:
            ValidationResult with any errors or warnings
        """
        settings_dict = self.get_settings_dict()
        return self._validator.validate(settings_dict, check_unknown=True)

    def validate_category(self, category: str, updates: dict[str, Any]) -> ValidationResult:
        """Validate settings for a category.

        Args:
            category: Category name
            updates: Settings to validate

        Returns:
            ValidationResult with any errors or warnings
        """
        return self._validator.validate_category(category, updates, check_unknown=True)

    def get_setting_definition(self, name: str):
        """Get the definition for a setting.

        Args:
            name: Setting name

        Returns:
            SettingDefinition for the setting
        """
        return get_setting(name)

    def get_category_settings_metadata(self, category: str) -> dict[str, Any]:
        """Get metadata for all settings in a category.

        Args:
            category: Category name

        Returns:
            Dictionary of setting names to their metadata
        """
        from app.config.settings import get_settings_by_category

        return {
            name: {
                "type": defn.type,
                "default": defn.default,
                "label": defn.label,
                "description": defn.description,
                "options": defn.options,
                "min": defn.min,
                "max": defn.max,
                "step": defn.step,
                "suffix": defn.suffix,
                "is_fake": defn.is_fake,
                "is_advanced": defn.is_advanced,
            }
            for name, defn in get_settings_by_category(category).items()
        }

    def is_fake_setting(self, name: str) -> bool:
        """Check if a setting is fake/not implemented.

        Args:
            name: Setting name

        Returns:
            True if the setting is fake
        """
        return name in FAKE_SETTINGS

    def import_settings(self, data: dict[str, Any]) -> bool:
        """Import settings from a dictionary (e.g., from file upload)."""
        try:
            # Validate required categories
            required = ["general", "transcription", "refiner", "audio", "hotkey", "advanced"]
            for cat in required:
                if cat not in data:
                    data[cat] = {}

            # Run validation before import
            validation = self._validator.validate(data, check_unknown=True)
            if not validation.is_valid:
                logger.warning("Settings import validation failed: %s", validation.errors)
                return False

            self._settings = SettingsState(
                general=GeneralSettings(**data.get("general", {})),
                transcription=TranscriptionSettings(**data.get("transcription", {})),
                refiner=RefinerSettings(**data.get("refiner", {})),
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
