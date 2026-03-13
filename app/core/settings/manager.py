"""Persistent settings management for OpenWispr with mode support.

This module handles loading, saving, and migrating user settings
with support for mode-specific configurations (Hotkey and System modes).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.config.coach_prompts import get_default_coach_templates
from app.config.settings import (
    CURRENT_SETTINGS_VERSION,
    FAKE_SETTINGS,
    get_setting,
)
from app.core.model_catalog import MODEL_CATALOG_BY_ID
from app.core.modes import (
    ModeSettings,
    SystemModeDefaults,
    TranscriptionMode,
    WisprModeDefaults,
)
from app.core.settings.config import ModeConfig, SettingsContainer, create_default_mode_configs
from app.core.settings.migrations import migrate_to_current, needs_migration
from app.core.settings.validator import SettingsValidator, ValidationResult

logger = logging.getLogger(__name__)


RUNTIME_TO_CATALOG_MODEL = {
    "tiny": "whisper-tiny",
    "base": "whisper-small",
    "small": "whisper-small",
    "medium": "whisper-medium",
    "large-v3": "whisper-large-v3",
    "turbo": "whisper-turbo",
}


def _normalize_asr_model_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate in MODEL_CATALOG_BY_ID:
        return candidate
    return RUNTIME_TO_CATALOG_MODEL.get(candidate)


def _normalize_capture_source(value: Any) -> str:
    if value == "system":
        return "system"
    return "microphone"


def _normalize_settings_payload(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    transcription = dict(normalized.get("transcription", {}) or {})
    audio = dict(normalized.get("audio", {}) or {})
    hotkey = dict(normalized.get("hotkey", {}) or {})

    legacy_hotkey_model = hotkey.pop("model_name", None)
    default_capture_source = _normalize_capture_source(
        audio.get("default_capture_source") or audio.get("captureMode")
    )
    audio["default_capture_source"] = default_capture_source
    audio.setdefault("captureMode", default_capture_source)
    hotkey["capture_source"] = _normalize_capture_source(
        hotkey.get("capture_source") or default_capture_source
    )
    microphone_hotkey = hotkey.get("microphone_key_combination") or hotkey.get("key_combination")
    hotkey["microphone_key_combination"] = (
        str(microphone_hotkey).strip()
        if microphone_hotkey
        else get_setting("key_combination").default
    )
    system_hotkey = hotkey.get("system_key_combination")
    hotkey["system_key_combination"] = (
        str(system_hotkey).strip() if system_hotkey else "CommandOrControl+Shift+Y"
    )

    fallback_model_id = (
        _normalize_asr_model_id(transcription.get("default_asr_model_id"))
        or _normalize_asr_model_id(transcription.get("model_name"))
        or _normalize_asr_model_id(legacy_hotkey_model)
        or get_setting("default_asr_model_id").default
    )
    transcription["default_asr_model_id"] = fallback_model_id
    transcription["microphone_asr_model_id"] = (
        _normalize_asr_model_id(transcription.get("microphone_asr_model_id"))
        or _normalize_asr_model_id(legacy_hotkey_model)
        or fallback_model_id
    )
    transcription["system_asr_model_id"] = (
        _normalize_asr_model_id(transcription.get("system_asr_model_id")) or fallback_model_id
    )

    normalized["transcription"] = transcription
    normalized["audio"] = audio
    normalized["hotkey"] = hotkey
    return normalized


def _build_coach_settings(raw: dict[str, Any] | None) -> CoachSettings:
    payload = dict(raw or {})
    overrides = payload.get("coach_overrides", {}) or {}
    templates = payload.get("coach_prompt_templates", get_default_coach_templates())
    return CoachSettings(
        **{
            **payload,
            "coach_overrides": CoachPromptOverrides(**overrides),
            "coach_prompt_templates": [
                CoachPromptTemplateSettings(**template) for template in templates
            ],
        }
    )


__all__ = [
    "GeneralSettings",
    "TranscriptionSettings",
    "RefinerSettings",
    "AudioSettings",
    "HotkeySettings",
    "CoachSettings",
    "HistorySettings",
    "DictionarySettings",
    "SnippetsSettings",
    "StyleSettings",
    "AdvancedSettings",
    "ModeSpecificSettings",
    "SettingsState",
    "DEFAULT_SETTINGS_STATE",
    "SettingsManager",
    "get_settings_manager",
    "reset_settings_manager",
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
    microphone_asr_model_id: str = field(
        default_factory=lambda: get_setting("microphone_asr_model_id").default
    )
    system_asr_model_id: str = field(
        default_factory=lambda: get_setting("system_asr_model_id").default
    )
    refinement_mode: str = field(default_factory=lambda: get_setting("refinement_mode").default)
    refinement_profile: str = field(
        default_factory=lambda: get_setting("refinement_profile").default
    )
    transcription_mode: str = field(
        default_factory=lambda: get_setting("transcription_mode").default
    )
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
    default_capture_source: str = field(
        default_factory=lambda: get_setting("default_capture_source").default
    )
    defaultDeviceId: str = field(default_factory=lambda: get_setting("defaultDeviceId").default)
    backend: str = field(default_factory=lambda: get_setting("backend").default)
    audio_backend: str = field(default_factory=lambda: get_setting("audio_backend").default)
    sampleRate: int = field(default_factory=lambda: get_setting("sampleRate").default)
    vadEnabled: bool = field(default_factory=lambda: get_setting("vadEnabled").default)
    vadThresholdDb: float = field(default_factory=lambda: get_setting("vadThresholdDb").default)
    noiseFiltering: bool = field(default_factory=lambda: get_setting("noiseFiltering").default)
    echoCancellation: bool = field(default_factory=lambda: get_setting("echoCancellation").default)
    autoGainControl: bool = field(default_factory=lambda: get_setting("autoGainControl").default)
    mute_openwispr_audio_during_dictation: bool = field(
        default_factory=lambda: get_setting("mute_openwispr_audio_during_dictation").default
    )


@dataclass
class RefinerSettings:
    """LLM refiner settings."""

    selected_model_id: str = field(default_factory=lambda: get_setting("selected_model_id").default)
    runtime_enabled: bool = field(default_factory=lambda: get_setting("runtime_enabled").default)
    cleanup_instructions: str = field(
        default_factory=lambda: get_setting("cleanup_instructions").default
    )
    engine_preference: str = field(default_factory=lambda: get_setting("engine_preference").default)
    refiner_provider_base_url: str = field(
        default_factory=lambda: get_setting("refiner_provider_base_url").default
    )


@dataclass
class HotkeySettings:
    """Global hotkey settings."""

    enabled: bool = field(default_factory=lambda: get_setting("enabled").default)
    key_combination: str = field(default_factory=lambda: get_setting("key_combination").default)
    microphone_key_combination: str = field(
        default_factory=lambda: get_setting("microphone_key_combination").default
    )
    system_key_combination: str = field(
        default_factory=lambda: get_setting("system_key_combination").default
    )
    hold_mode: bool = field(default_factory=lambda: get_setting("hold_mode").default)
    auto_inject: bool = field(default_factory=lambda: get_setting("auto_inject").default)
    language: str = field(default_factory=lambda: get_setting("language").default)
    device_id: str = field(default_factory=lambda: get_setting("device_id").default)
    capture_source: str = field(default_factory=lambda: get_setting("capture_source").default)
    finish_mode_default: str = field(
        default_factory=lambda: get_setting("finish_mode_default").default
    )
    enable_refiner_on_stop: bool = field(
        default_factory=lambda: get_setting("enable_refiner_on_stop").default
    )
    save_debug_wav: bool = field(default_factory=lambda: get_setting("save_debug_wav").default)
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
class CoachPromptOverrides:
    """Stable prompt override values for the English Coach."""

    tone: str = field(default_factory=lambda: get_setting("coach_overrides").default["tone"])
    aggressiveness: str = field(
        default_factory=lambda: get_setting("coach_overrides").default["aggressiveness"]
    )
    filler_removal: bool = field(
        default_factory=lambda: get_setting("coach_overrides").default["filler_removal"]
    )
    keep_slang: bool = field(
        default_factory=lambda: get_setting("coach_overrides").default["keep_slang"]
    )
    target_style: str = field(
        default_factory=lambda: get_setting("coach_overrides").default["target_style"]
    )


@dataclass
class CoachPromptTemplateSettings:
    """Editable coach prompt template."""

    id: str
    name: str
    version: int
    system: str
    user_template: str
    enabled: bool = True
    built_in: bool = False


@dataclass
class CoachSettings:
    """English Coach settings."""

    coach_enabled: bool = field(default_factory=lambda: get_setting("coach_enabled").default)
    coach_show_live_hints: bool = field(
        default_factory=lambda: get_setting("coach_show_live_hints").default
    )
    coach_detail_level: str = field(
        default_factory=lambda: get_setting("coach_detail_level").default
    )
    copy_polished_by_default: bool = field(
        default_factory=lambda: get_setting("copy_polished_by_default").default
    )
    show_diff_view: bool = field(default_factory=lambda: get_setting("show_diff_view").default)
    coach_template_id_mic: str = field(
        default_factory=lambda: get_setting("coach_template_id_mic").default
    )
    coach_template_id_system: str = field(
        default_factory=lambda: get_setting("coach_template_id_system").default
    )
    coach_prompt_custom_enabled: bool = field(
        default_factory=lambda: get_setting("coach_prompt_custom_enabled").default
    )
    coach_prompt_custom_text: str = field(
        default_factory=lambda: get_setting("coach_prompt_custom_text").default
    )
    coach_overrides: CoachPromptOverrides = field(default_factory=CoachPromptOverrides)
    privacy_mode: str = field(default_factory=lambda: get_setting("privacy_mode").default)
    coach_provider_base_url: str = field(
        default_factory=lambda: get_setting("coach_provider_base_url").default
    )
    show_floating_coach_result: bool = field(
        default_factory=lambda: get_setting("show_floating_coach_result").default
    )
    coach_runtime_enabled: bool = field(
        default_factory=lambda: get_setting("coach_runtime_enabled").default
    )
    coach_selected_model_id: str = field(
        default_factory=lambda: get_setting("coach_selected_model_id").default
    )
    coach_prompt_templates: list[CoachPromptTemplateSettings] = field(
        default_factory=lambda: [
            CoachPromptTemplateSettings(**template) for template in get_default_coach_templates()
        ]
    )


@dataclass
class HistorySettings:
    """Transcript history settings."""

    retention_days: int = field(default_factory=lambda: get_setting("retention_days").default)
    persist_audio: bool = field(default_factory=lambda: get_setting("persist_audio").default)
    allow_retry: bool = field(default_factory=lambda: get_setting("allow_retry").default)
    default_analytics_range_days: int | str = field(
        default_factory=lambda: get_setting("default_analytics_range_days").default
    )


@dataclass
class DictionarySettings:
    """Dictionary pipeline settings."""

    dictionary_enabled: bool = field(
        default_factory=lambda: get_setting("dictionary_enabled").default
    )


@dataclass
class SnippetsSettings:
    """Snippet pipeline settings."""

    snippets_enabled: bool = field(default_factory=lambda: get_setting("snippets_enabled").default)
    snippets_quick_insert: bool = field(
        default_factory=lambda: get_setting("snippets_quick_insert").default
    )


@dataclass
class StyleSettings:
    """Style pipeline settings."""

    style_default_profile: str = field(
        default_factory=lambda: get_setting("style_default_profile").default
    )
    style_apply_enabled: bool = field(
        default_factory=lambda: get_setting("style_apply_enabled").default
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
class ModeSpecificSettings:
    """Mode-specific settings container for backward compatibility.

    This dataclass provides a legacy-compatible interface to the new
    mode-specific settings system.
    """

    wispr: dict[str, Any] = field(default_factory=lambda: WisprModeDefaults.to_dict())
    system: dict[str, Any] = field(default_factory=lambda: SystemModeDefaults.to_dict())
    active_mode: str = "system"

    def to_container(self) -> SettingsContainer:
        """Convert to new SettingsContainer format."""
        return SettingsContainer(
            wispr=ModeConfig.from_dict(
                {"mode": "wispr", "settings": self.wispr, "is_active": self.active_mode == "wispr"}
            ),
            system=ModeConfig.from_dict(
                {
                    "mode": "system",
                    "settings": self.system,
                    "is_active": self.active_mode == "system",
                }
            ),
            active_mode=TranscriptionMode(self.active_mode),
        )

    @classmethod
    def from_container(cls, container: SettingsContainer) -> ModeSpecificSettings:
        """Create from SettingsContainer."""
        return cls(
            wispr=container.wispr.settings.to_dict(),
            system=container.system.settings.to_dict(),
            active_mode=container.active_mode.value,
        )


@dataclass
class SettingsState:
    """Complete application settings state with mode support."""

    general: GeneralSettings = field(default_factory=GeneralSettings)
    transcription: TranscriptionSettings = field(default_factory=TranscriptionSettings)
    refiner: RefinerSettings = field(default_factory=RefinerSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    hotkey: HotkeySettings = field(default_factory=HotkeySettings)
    coach: CoachSettings = field(default_factory=CoachSettings)
    history: HistorySettings = field(default_factory=HistorySettings)
    dictionary: DictionarySettings = field(default_factory=DictionarySettings)
    snippets: SnippetsSettings = field(default_factory=SnippetsSettings)
    style: StyleSettings = field(default_factory=StyleSettings)
    advanced: AdvancedSettings = field(default_factory=AdvancedSettings)
    modes: ModeSpecificSettings = field(default_factory=ModeSpecificSettings)
    version: int = CURRENT_SETTINGS_VERSION


# Default settings instance
DEFAULT_SETTINGS_STATE = SettingsState()


class SettingsManager:
    """Manages persistent storage of user settings with mode support.

    This manager provides thread-safe access to settings with support for:
    - Mode-specific configurations (Hotkey and System modes)
    - WebSocket synchronization
    - Backward compatibility with legacy settings
    - Automatic migration from old formats
    """

    SETTINGS_FILENAME = "user_settings.json"
    CURRENT_VERSION = CURRENT_SETTINGS_VERSION

    def __init__(self, settings_dir: Path | None = None) -> None:
        """Initialize the settings manager.

        Args:
            settings_dir: Directory to store settings file. Defaults to user data directory.
        """
        if settings_dir is None:
            # Use platform-appropriate user data directory
            if sys.platform == "win32":
                base = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming"))
            elif sys.platform == "darwin":
                base = Path.home() / "Library" / "Application Support"
            else:
                base = Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
            # Use OpenWispr subdirectory
            settings_dir = base / "OpenWispr"

        settings_dir = Path(settings_dir)
        settings_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = settings_dir / self.SETTINGS_FILENAME

        self._settings: SettingsState = DEFAULT_SETTINGS_STATE
        self._mode_container: SettingsContainer = create_default_mode_configs()
        self._validator = SettingsValidator(strict=False)
        self._lock = threading.RLock()
        self._sync_callbacks: list[callable] = []
        self._last_sync: float = 0.0

        self._load()

    def _load(self) -> None:
        """Load settings from disk or create with defaults."""
        if not self.settings_path.exists():
            logger.info("Settings file not found, creating with defaults: %s", self.settings_path)
            self._settings = DEFAULT_SETTINGS_STATE
            self._mode_container = create_default_mode_configs()
            self._save()
            return

        try:
            with open(self.settings_path, encoding="utf-8") as f:
                data = json.load(f)

            # Migrate if needed
            if needs_migration(data):
                data = migrate_to_current(data)
            data = _normalize_settings_payload(data)

            # Parse legacy settings
            self._settings = SettingsState(
                general=GeneralSettings(**data.get("general", {})),
                transcription=TranscriptionSettings(**data.get("transcription", {})),
                refiner=RefinerSettings(**data.get("refiner", {})),
                audio=AudioSettings(**data.get("audio", {})),
                hotkey=HotkeySettings(**data.get("hotkey", {})),
                coach=_build_coach_settings(data.get("coach")),
                history=HistorySettings(**data.get("history", {})),
                dictionary=DictionarySettings(**data.get("dictionary", {})),
                snippets=SnippetsSettings(**data.get("snippets", {})),
                style=StyleSettings(**data.get("style", {})),
                advanced=AdvancedSettings(**data.get("advanced", {})),
                version=data.get("version", self.CURRENT_VERSION),
            )

            # Parse mode-specific settings (new format)
            if "modes" in data:
                mode_data = data["modes"]
                self._mode_container = ModeSpecificSettings(
                    wispr=mode_data.get("wispr", WisprModeDefaults.to_dict()),
                    system=mode_data.get("system", SystemModeDefaults.to_dict()),
                    active_mode=mode_data.get("active_mode", "system"),
                ).to_container()
            else:
                # Migrate from legacy transcription settings
                self._migrate_legacy_mode_settings()

            logger.debug("Settings loaded from %s", self.settings_path)

        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Failed to load settings (%s), using defaults", exc)
            self._settings = DEFAULT_SETTINGS_STATE
            self._mode_container = create_default_mode_configs()
            self._save()

    def _migrate_legacy_mode_settings(self) -> None:
        """Migrate legacy settings to mode-specific format."""
        trans = self._settings.transcription

        # Create mode configs from legacy settings
        wispr_settings = ModeSettings(
            model_name="tiny" if trans.hotkey_optimized else trans.model_name,
            beam_size=1,
            best_of=1,
            vad_threshold=trans.vad_threshold_db,
            chunk_duration=0.5,
            overlap_ratio=0.1,
            compute_type="int8",
            vad_enabled=trans.vad_enabled,
            hotkey_optimized=True,
        )

        system_settings = ModeSettings(
            model_name=trans.model_name,
            beam_size=trans.beam_size,
            best_of=trans.best_of,
            vad_threshold=trans.vad_threshold_db,
            chunk_duration=trans.chunk_duration,
            overlap_ratio=trans.overlap_ratio,
            compute_type=trans.compute_type,
            vad_enabled=trans.vad_enabled,
            hotkey_optimized=False,
        )

        self._mode_container = SettingsContainer(
            wispr=ModeConfig(
                mode=TranscriptionMode.WISPR,
                settings=wispr_settings,
                display_name=TranscriptionMode.WISPR.display_name,
            ),
            system=ModeConfig(
                mode=TranscriptionMode.SYSTEM,
                settings=system_settings,
                display_name=TranscriptionMode.SYSTEM.display_name,
                is_active=True,
            ),
            active_mode=TranscriptionMode.SYSTEM,
        )

        logger.info("Migrated legacy settings to mode-specific format")

    def _save(self) -> None:
        """Save current settings to disk."""
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)

            # Update modes from container
            self._settings.modes = ModeSpecificSettings.from_container(self._mode_container)

            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self._settings), f, indent=2)
            logger.debug("Settings saved to %s", self.settings_path)
        except (OSError, TypeError) as exc:
            logger.error("Failed to save settings: %s", exc)

    # ============================================
    # Thread-safe Settings Access
    # ============================================
    def get_settings(self) -> SettingsState:
        """Get current settings (thread-safe)."""
        with self._lock:
            return self._settings

    def get_mode_container(self) -> SettingsContainer:
        """Get mode settings container (thread-safe)."""
        with self._lock:
            return self._mode_container

    def get_mode_config(self, mode: TranscriptionMode | str | None = None) -> ModeConfig:
        """Get configuration for a specific mode.

        Args:
            mode: Mode to get config for (defaults to active)

        Returns:
            ModeConfig for the specified mode
        """
        with self._lock:
            return self._mode_container.get_mode_config(mode)

    def get_active_mode(self) -> TranscriptionMode:
        """Get currently active transcription mode."""
        with self._lock:
            return self._mode_container.active_mode

    def set_active_mode(self, mode: TranscriptionMode | str) -> None:
        """Set the active transcription mode.

        Args:
            mode: Mode to activate
        """
        with self._lock:
            self._mode_container.set_active_mode(mode)
            self._save()
            self._notify_sync(
                "mode_change", {"active_mode": self._mode_container.active_mode.value}
            )

    def update_mode_settings(
        self, mode: TranscriptionMode | str, updates: dict[str, Any]
    ) -> ValidationResult:
        """Update settings for a specific mode with validation.

        Args:
            mode: Mode to update
            updates: Dictionary of setting updates

        Returns:
            ValidationResult with any errors
        """
        with self._lock:
            # Validate updates
            errors = []
            for key, value in updates.items():
                if not hasattr(ModeSettings, key):
                    errors.append(f"{key}: Unknown setting")

            if errors:
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=[],
                    settings=self.get_settings_dict(),
                )

            # Apply updates
            self._mode_container.update_mode_settings(mode, updates)
            self._save()

            # Notify sync listeners
            self._notify_sync(
                "mode_settings_update",
                {
                    "mode": mode.value if isinstance(mode, TranscriptionMode) else mode,
                    "updates": updates,
                },
            )

            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                settings=self.get_settings_dict(),
            )

    def reset_mode_to_defaults(self, mode: TranscriptionMode | str) -> None:
        """Reset a specific mode to its defaults.

        Args:
            mode: Mode to reset
        """
        with self._lock:
            self._mode_container.reset_mode_to_defaults(mode)
            self._save()
            self._notify_sync(
                "mode_reset", {"mode": mode.value if isinstance(mode, TranscriptionMode) else mode}
            )

    def update_settings(self, settings: SettingsState) -> None:
        """Update settings and save to disk (thread-safe)."""
        with self._lock:
            self._settings = settings
            self._save()
            self._notify_sync("settings_update", self.get_settings_dict())

    def update_partial(self, category: str, updates: dict[str, Any]) -> None:
        """Update a specific category of settings."""
        with self._lock:
            if hasattr(self._settings, category):
                category_obj = getattr(self._settings, category)
                for key, value in updates.items():
                    if hasattr(category_obj, key):
                        setattr(category_obj, key, value)
                self._save()
                logger.debug("Updated settings category '%s': %s", category, updates)
                self._notify_sync("partial_update", {"category": category, "updates": updates})
            else:
                logger.warning("Unknown settings category: %s", category)

    def reset_to_defaults(self) -> SettingsState:
        """Reset all settings to defaults."""
        with self._lock:
            self._settings = DEFAULT_SETTINGS_STATE
            self._mode_container = create_default_mode_configs()
            self._save()
            logger.info("Settings reset to defaults")
            self._notify_sync("reset", self.get_settings_dict())
            return self._settings

    # ============================================
    # WebSocket Sync Support
    # ============================================
    def register_sync_callback(self, callback: callable) -> None:
        """Register a callback for settings synchronization.

        Args:
            callback: Function to call when settings change.
                     Signature: callback(event_type: str, data: dict) -> None
        """
        self._sync_callbacks.append(callback)
        logger.debug("Registered sync callback: %s", callback.__name__)

    def unregister_sync_callback(self, callback: callable) -> None:
        """Unregister a sync callback."""
        if callback in self._sync_callbacks:
            self._sync_callbacks.remove(callback)
            logger.debug("Unregistered sync callback: %s", callback.__name__)

    def _notify_sync(self, event_type: str, data: dict[str, Any]) -> None:
        """Notify all sync callbacks of a settings change."""
        self._last_sync = time.time()
        for callback in self._sync_callbacks:
            try:
                callback(event_type, data)
            except Exception as exc:
                logger.error("Sync callback error: %s", exc)

    def get_last_sync_time(self) -> float:
        """Get timestamp of last settings sync."""
        return self._last_sync

    def get_settings_for_sync(self) -> dict[str, Any]:
        """Get complete settings dict for WebSocket synchronization."""
        with self._lock:
            return {
                "legacy": self.get_settings_dict(),
                "modes": self._mode_container.to_dict(),
                "version": self.CURRENT_VERSION,
                "timestamp": time.time(),
            }

    def apply_sync_update(self, sync_data: dict[str, Any]) -> bool:
        """Apply settings update from WebSocket sync.

        Args:
            sync_data: Settings data from remote source

        Returns:
            True if update was applied successfully
        """
        try:
            with self._lock:
                if "modes" in sync_data:
                    self._mode_container = SettingsContainer.from_dict(sync_data["modes"])

                if "legacy" in sync_data:
                    legacy = _normalize_settings_payload(sync_data["legacy"])
                    self._settings = SettingsState(
                        general=GeneralSettings(**legacy.get("general", {})),
                        transcription=TranscriptionSettings(**legacy.get("transcription", {})),
                        refiner=RefinerSettings(**legacy.get("refiner", {})),
                        audio=AudioSettings(**legacy.get("audio", {})),
                        hotkey=HotkeySettings(**legacy.get("hotkey", {})),
                        coach=_build_coach_settings(legacy.get("coach")),
                        history=HistorySettings(**legacy.get("history", {})),
                        dictionary=DictionarySettings(**legacy.get("dictionary", {})),
                        snippets=SnippetsSettings(**legacy.get("snippets", {})),
                        style=StyleSettings(**legacy.get("style", {})),
                        advanced=AdvancedSettings(**legacy.get("advanced", {})),
                        version=legacy.get("version", self.CURRENT_VERSION),
                    )

                self._save()
                logger.info("Applied sync update")
                return True

        except (TypeError, ValueError) as exc:
            logger.error("Failed to apply sync update: %s", exc)
            return False

    # ============================================
    # Legacy Compatibility
    # ============================================
    def get_settings_dict(self) -> dict[str, Any]:
        """Get settings as a dictionary for API responses."""
        with self._lock:
            return asdict(self._settings)

    def validate(self) -> ValidationResult:
        """Validate current settings."""
        with self._lock:
            settings_dict = self.get_settings_dict()
            return self._validator.validate(settings_dict, check_unknown=True)

    def validate_category(self, category: str, updates: dict[str, Any]) -> ValidationResult:
        """Validate settings for a category."""
        with self._lock:
            return self._validator.validate_category(category, updates, check_unknown=True)

    def get_setting_definition(self, name: str):
        """Get the definition for a setting."""
        return get_setting(name)

    def get_category_settings_metadata(self, category: str) -> dict[str, Any]:
        """Get metadata for all settings in a category."""
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
        """Check if a setting is fake/not implemented."""
        return name in FAKE_SETTINGS

    def import_settings(self, data: dict[str, Any]) -> bool:
        """Import settings from a dictionary (e.g., from file upload)."""
        try:
            with self._lock:
                # Validate required categories
                required = [
                    "general",
                    "transcription",
                    "refiner",
                    "audio",
                    "hotkey",
                    "coach",
                    "history",
                    "dictionary",
                    "snippets",
                    "style",
                    "advanced",
                ]
                for cat in required:
                    if cat not in data:
                        data[cat] = {}

                data = _normalize_settings_payload(data)

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
                    coach=_build_coach_settings(data.get("coach")),
                    history=HistorySettings(**data.get("history", {})),
                    dictionary=DictionarySettings(**data.get("dictionary", {})),
                    snippets=SnippetsSettings(**data.get("snippets", {})),
                    style=StyleSettings(**data.get("style", {})),
                    advanced=AdvancedSettings(**data.get("advanced", {})),
                    version=data.get("version", self.CURRENT_VERSION),
                )

                # Import mode settings if present
                if "modes" in data:
                    self._mode_container = ModeSpecificSettings(
                        wispr=data["modes"].get("wispr", WisprModeDefaults.to_dict()),
                        system=data["modes"].get("system", SystemModeDefaults.to_dict()),
                        active_mode=data["modes"].get("active_mode", "system"),
                    ).to_container()

                self._save()
                logger.info("Settings imported successfully")
                self._notify_sync("import", self.get_settings_dict())
                return True

        except (TypeError, ValueError) as exc:
            logger.error("Failed to import settings: %s", exc)
            return False


# Global settings manager instance
_settings_manager: SettingsManager | None = None
_settings_lock = threading.Lock()


def get_settings_manager() -> SettingsManager:
    """Get or create the global settings manager instance (thread-safe)."""
    global _settings_manager
    if _settings_manager is None:
        with _settings_lock:
            if _settings_manager is None:
                _settings_manager = SettingsManager()
    return _settings_manager


def reset_settings_manager() -> None:
    """Reset the global settings manager (for testing)."""
    global _settings_manager
    with _settings_lock:
        _settings_manager = None
