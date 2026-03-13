from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.constants import (
    AppConstants,
    AudioConstants,
    AutoOptimizationConstants,
    ModelConstants,
    PerformanceConstants,
    ServerConstants,
    SessionConstants,
    VADConstants,
)
from app.core.modes import (
    ModeSettings,
    SystemModeDefaults,
    TranscriptionMode,
    WisprModeDefaults,
    get_mode_defaults,
)

logger = logging.getLogger(__name__)

__all__ = [
    "AppSettings",
    "ModeConfig",
    "SettingsContainer",
    "LIVE_MODE_PROFILES",
    "resolve_live_profile",
    "create_default_mode_configs",
    "default_download_root",
    "is_legacy_download_root",
]


def default_download_root() -> Path:
    if sys.platform == "win32":
        base = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / AppConstants.APP_NAME / "models"


def is_legacy_download_root(value: Any) -> bool:
    if value is None:
        return False
    normalized = str(value).strip().replace("\\", "/").rstrip("/")
    return normalized in {"models", "./models"}



class ModeConfig(BaseModel):
    """Configuration container for a single transcription mode.

    This class extends ModeConfiguration with additional runtime
    configuration and WebSocket sync capabilities.
    """

    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    mode: TranscriptionMode
    settings: ModeSettings
    display_name: str = ""
    description: str = ""
    is_active: bool = False

    # WebSocket sync metadata
    last_synced_at: float = 0.0
    sync_version: int = 1
    pending_changes: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data: Any):
        """Initialize with mode-specific defaults if not provided."""
        mode = data.get("mode")
        if isinstance(mode, str):
            mode = TranscriptionMode(mode.lower())
            data["mode"] = mode

        # Apply mode-specific defaults if settings not provided
        if "settings" not in data and mode is not None:
            data["settings"] = get_mode_defaults(mode)

        super().__init__(**data)

        # Set display metadata
        if not self.display_name:
            self.display_name = self.mode.display_name
        if not self.description:
            self.description = self.mode.description

    def update_settings(self, updates: dict[str, Any]) -> None:
        """Update settings with validation.

        Args:
            updates: Dictionary of setting updates
        """
        current = self.settings.to_dict()
        current.update(updates)
        self.settings = ModeSettings.from_dict(current)
        self.sync_version += 1
        logger.debug("Updated %s settings to version %d", self.mode.value, self.sync_version)

    def reset_to_defaults(self) -> None:
        """Reset settings to mode-specific defaults."""
        self.settings = get_mode_defaults(self.mode)
        self.sync_version += 1
        self.pending_changes.clear()
        logger.info("Reset %s settings to defaults", self.mode.value)

    def mark_synced(self, timestamp: float) -> None:
        """Mark settings as successfully synced.

        Args:
            timestamp: Sync completion timestamp
        """
        self.last_synced_at = timestamp
        self.pending_changes.clear()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "mode": self.mode.value,
            "settings": self.settings.to_dict(),
            "display_name": self.display_name,
            "description": self.description,
            "is_active": self.is_active,
            "sync_version": self.sync_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModeConfig:
        """Create from dictionary with validation."""
        mode = data.get("mode", "wispr")
        settings_data = data.get("settings", {})

        return cls(
            mode=TranscriptionMode(mode) if isinstance(mode, str) else mode,
            settings=ModeSettings.from_dict(settings_data),
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            is_active=data.get("is_active", False),
            sync_version=data.get("sync_version", 1),
        )


class SettingsContainer(BaseModel):
    """Container for all mode configurations.

    Manages both Hotkey and System mode configurations with
    thread-safe access patterns.
    """

    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    wispr: ModeConfig = Field(default_factory=lambda: ModeConfig(mode=TranscriptionMode.WISPR))
    system: ModeConfig = Field(default_factory=lambda: ModeConfig(mode=TranscriptionMode.SYSTEM))
    active_mode: TranscriptionMode = TranscriptionMode.SYSTEM

    def __init__(self, **data: Any):
        """Initialize with proper mode configurations."""
        if "wispr" in data and isinstance(data["wispr"], dict):
            data["wispr"] = ModeConfig.from_dict(data["wispr"])
        if "system" in data and isinstance(data["system"], dict):
            data["system"] = ModeConfig.from_dict(data["system"])
        if "active_mode" in data and isinstance(data["active_mode"], str):
            data["active_mode"] = TranscriptionMode(data["active_mode"].lower())

        super().__init__(**data)

    @field_validator("active_mode")
    @classmethod
    def validate_active_mode(cls, v: TranscriptionMode) -> TranscriptionMode:
        """Validate active mode is one of the supported modes."""
        if v not in (TranscriptionMode.WISPR, TranscriptionMode.SYSTEM):
            raise ValueError(f"Invalid active mode: {v}")
        return v

    def get_mode_config(self, mode: TranscriptionMode | str | None = None) -> ModeConfig:
        """Get configuration for a specific mode.

        Args:
            mode: Mode to get config for (defaults to active_mode)

        Returns:
            ModeConfig for the specified mode
        """
        if mode is None:
            mode = self.active_mode

        if isinstance(mode, str):
            mode = TranscriptionMode(mode.lower())

        if mode == TranscriptionMode.WISPR:
            return self.wispr
        elif mode == TranscriptionMode.SYSTEM:
            return self.system
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def get_active_config(self) -> ModeConfig:
        """Get configuration for the currently active mode."""
        return self.get_mode_config(self.active_mode)

    def set_active_mode(self, mode: TranscriptionMode | str) -> None:
        """Set the active transcription mode.

        Args:
            mode: Mode to activate
        """
        if isinstance(mode, str):
            mode = TranscriptionMode(mode.lower())

        # Deactivate current mode
        current = self.get_mode_config(self.active_mode)
        current.is_active = False

        # Activate new mode
        self.active_mode = mode
        new_config = self.get_mode_config(mode)
        new_config.is_active = True

        logger.info("Switched active mode to %s", mode.value)

    def update_mode_settings(self, mode: TranscriptionMode | str, updates: dict[str, Any]) -> None:
        """Update settings for a specific mode.

        Args:
            mode: Mode to update
            updates: Dictionary of setting updates
        """
        config = self.get_mode_config(mode)
        config.update_settings(updates)

    def reset_mode_to_defaults(self, mode: TranscriptionMode | str) -> None:
        """Reset a specific mode to its defaults.

        Args:
            mode: Mode to reset
        """
        config = self.get_mode_config(mode)
        config.reset_to_defaults()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "wispr": self.wispr.to_dict(),
            "system": self.system.to_dict(),
            "active_mode": self.active_mode.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SettingsContainer:
        """Create from dictionary with validation."""
        return cls(
            wispr=data.get("wispr", {}),
            system=data.get("system", {}),
            active_mode=data.get("active_mode", "system"),
        )


class AppSettings(BaseSettings):
    """Application-wide settings with mode support.

    This class extends the base application settings with the new
    mode-specific configuration system while maintaining backward
    compatibility.
    """

    model_config = SettingsConfigDict(
        env_prefix="TRANSCRIPTA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Basic application settings
    app_name: str = AppConstants.APP_NAME
    host: str = ServerConstants.DEFAULT_HOST
    port: int = ServerConstants.DEFAULT_PORT
    sample_rate: int = AudioConstants.DEFAULT_SAMPLE_RATE
    channels: int = AudioConstants.DEFAULT_CHANNELS
    chunk_seconds: float = AudioConstants.DEFAULT_CHUNK_SECONDS
    overlap_seconds: float = AudioConstants.DEFAULT_OVERLAP_SECONDS
    capture_block_seconds: float = AudioConstants.DEFAULT_BLOCK_SECONDS
    meter_decay: float = AudioConstants.DEFAULT_METER_DECAY
    export_root: Path = Field(
        default_factory=lambda: Path.cwd() / SessionConstants.DEFAULT_EXPORT_ROOT
    )
    log_level: str = ServerConstants.DEFAULT_LOG_LEVEL
    default_model: str = ModelConstants.DEFAULT_MODEL_NAME
    device: str = PerformanceConstants.DEFAULT_EXECUTION_MODE
    audio_backend: str = AudioConstants.DEFAULT_BACKEND
    compute_type: str = ModelConstants.DEFAULT_COMPUTE_TYPE
    default_language: str = "auto"
    default_live_mode: str = PerformanceConstants.DEFAULT_LIVE_MODE
    default_execution_mode: str = PerformanceConstants.DEFAULT_EXECUTION_MODE

    # Auto-optimization settings
    auto_optimize: bool = AutoOptimizationConstants.DEFAULT_ENABLED
    optimization_mode: str = AutoOptimizationConstants.DEFAULT_MODE

    # Advanced audio settings (auto-populated)
    chunk_duration: float = AudioConstants.DEFAULT_CHUNK_SECONDS
    overlap_ratio: float = (
        AudioConstants.DEFAULT_OVERLAP_SECONDS / AudioConstants.DEFAULT_CHUNK_SECONDS
    )
    vad_threshold_db: float = VADConstants.DEFAULT_THRESHOLD_DB
    vad_min_silence_ms: int = VADConstants.DEFAULT_MIN_SILENCE_MS

    # Advanced quality settings
    confidence_threshold: float = ModelConstants.DEFAULT_CONFIDENCE_THRESHOLD
    enable_filler_filter: bool = VADConstants.DEFAULT_FILTER_ENABLED
    enable_hallucination_filter: bool = True
    min_segment_length: float = ModelConstants.MIN_SEGMENT_LENGTH

    # Ultra-low latency settings
    vad_filter: bool = VADConstants.DEFAULT_FILTER_ENABLED
    condition_on_previous_text: bool = True
    compression_ratio_threshold: float | None = None
    vad_speech_pad_ms: int = VADConstants.DEFAULT_SPEECH_PAD_MS
    beam_size: int = ModelConstants.DEFAULT_BEAM_SIZE
    best_of: int = ModelConstants.DEFAULT_BEST_OF
    temperature: float = ModelConstants.DEFAULT_TEMPERATURE
    download_root: Path = Field(default_factory=default_download_root)
    max_queue_items: int = AudioConstants.MAX_QUEUE_ITEMS
    output_refresh_seconds: float = PerformanceConstants.OUTPUT_REFRESH_SECONDS
    capture_device_id: str | None = None

    # Mode-specific settings container (new)
    mode_settings: SettingsContainer = Field(default_factory=SettingsContainer)

    @field_validator("download_root", mode="before")
    @classmethod
    def upgrade_legacy_download_root(cls, value: Any) -> Any:
        if is_legacy_download_root(value):
            resolved = default_download_root()
            logger.info("Upgrading legacy download_root %r to %s", value, resolved)
            return resolved
        return value

    def get_active_mode_config(self) -> ModeConfig:
        """Get configuration for the currently active mode."""
        return self.mode_settings.get_active_config()

    def get_mode_settings(self, mode: TranscriptionMode | str | None = None) -> ModeSettings:
        """Get settings for a specific mode.

        Args:
            mode: Mode to get settings for (defaults to active)

        Returns:
            ModeSettings for the specified mode
        """
        config = self.mode_settings.get_mode_config(mode)
        return config.settings

    def apply_mode_settings(self, mode: TranscriptionMode | str | None = None) -> None:
        """Apply mode-specific settings to the global configuration.

        This updates the legacy settings fields to match the active mode.

        Args:
            mode: Mode to apply (defaults to active)
        """
        settings = self.get_mode_settings(mode)

        # Update legacy settings to match mode
        self.default_model = settings.model_name
        self.chunk_duration = settings.chunk_duration
        self.overlap_ratio = settings.overlap_ratio
        self.compute_type = settings.compute_type
        self.vad_threshold_db = settings.vad_threshold
        self.vad_min_silence_ms = settings.vad_min_silence_ms
        self.vad_speech_pad_ms = settings.vad_speech_pad_ms
        self.confidence_threshold = settings.confidence_threshold
        self.beam_size = settings.beam_size
        self.best_of = settings.best_of
        self.temperature = settings.temperature

        logger.debug("Applied %s settings to global config", mode or self.mode_settings.active_mode)


# Re-export from constants for backward compatibility
LIVE_MODE_PROFILES: dict[str, dict[str, float]] = {
    "ultra": {"chunk_seconds": 0.1, "overlap_seconds": 0.02},  # 100ms - fastest
    "realtime": {"chunk_seconds": 0.2, "overlap_seconds": 0.04},  # 200ms - fast
    "low_latency": {"chunk_seconds": 0.5, "overlap_seconds": 0.1},  # 500ms
    "balanced": {"chunk_seconds": 1.0, "overlap_seconds": 0.2},  # 1s - default
    "high_accuracy": {"chunk_seconds": 2.0, "overlap_seconds": 0.4},  # 2s
}


def resolve_live_profile(mode: str, settings: AppSettings) -> dict[str, float]:
    """Resolve live profile settings for a given mode."""
    profile = LIVE_MODE_PROFILES.get(mode)
    if profile is None:
        return {
            "chunk_seconds": settings.chunk_seconds,
            "overlap_seconds": settings.overlap_seconds,
        }
    return dict(profile)


def create_default_mode_configs() -> SettingsContainer:
    """Create default mode configurations.

    Returns:
        SettingsContainer with default Hotkey and System configs
    """
    return SettingsContainer(
        wispr=ModeConfig(
            mode=TranscriptionMode.WISPR,
            settings=WisprModeDefaults.to_settings(),
            display_name=TranscriptionMode.WISPR.display_name,
            description=TranscriptionMode.WISPR.description,
        ),
        system=ModeConfig(
            mode=TranscriptionMode.SYSTEM,
            settings=SystemModeDefaults.to_settings(),
            display_name=TranscriptionMode.SYSTEM.display_name,
            description=TranscriptionMode.SYSTEM.description,
            is_active=True,
        ),
        active_mode=TranscriptionMode.SYSTEM,
    )
