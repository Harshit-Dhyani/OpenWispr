"""Centralized settings definition.

Single source of truth for all settings. This module defines all application
settings with their metadata, validation rules, and defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional

from app.core.constants import (
    AudioConstants,
    ModelConstants,
    PerformanceConstants,
    RefinerConstants,
    SessionConstants,
    UIConstants,
    VADConstants,
)


@dataclass(frozen=True)
class SettingDefinition:
    """Definition of a single setting with metadata and validation rules."""

    name: str
    category: str
    type: Literal["string", "number", "boolean", "enum", "range"]
    default: Any
    label: str
    description: str
    options: Optional[list] = None
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    suffix: Optional[str] = None
    is_fake: bool = False
    is_advanced: bool = False
    validation_fn: Optional[Callable[[Any], tuple[bool, str]]] = None


# ============================================
# FAKE/Not Implemented Settings Registry
# ============================================
FAKE_SETTINGS = frozenset(
    {
        # General
        "showNotifications",
        "minimizeToTray",
        "startupWithSystem",
        # Audio
        "noiseFiltering",
        "echoCancellation",
        "autoGainControl",
        # Transcription (performance-related)
        "max_workers",
        "use_parallel_processing",
        "preload_model",
        "patience",
        # Advanced
        "experimentalStem",
        "experimentalGpuAccel",
    }
)


# ============================================
# Settings Registry - Single Source of Truth
# ============================================
SETTINGS_REGISTRY: dict[str, SettingDefinition] = {
    # ============================================
    # General Settings
    # ============================================
    "defaultSessionTitle": SettingDefinition(
        name="defaultSessionTitle",
        category="general",
        type="string",
        default=SessionConstants.DEFAULT_SESSION_TITLE,
        label="Default Session Title",
        description="Default title for new transcription sessions",
    ),
    "defaultLanguage": SettingDefinition(
        name="defaultLanguage",
        category="general",
        type="string",
        default=UIConstants.DEFAULT_LANGUAGE,
        label="Default Language",
        description="Primary language for transcription",
    ),
    "exportDirectory": SettingDefinition(
        name="exportDirectory",
        category="general",
        type="string",
        default="",
        label="Export Directory",
        description="Default location for exported transcripts",
    ),
    "autoSaveInterval": SettingDefinition(
        name="autoSaveInterval",
        category="general",
        type="range",
        default=UIConstants.AUTO_SAVE_INTERVAL_SECONDS,
        label="Auto-save Interval",
        description="How often to save session progress (seconds)",
        min=10,
        max=300,
        step=10,
        suffix="s",
    ),
    "showNotifications": SettingDefinition(
        name="showNotifications",
        category="general",
        type="boolean",
        default=True,
        label="Show Notifications",
        description="Display desktop notifications for events",
        is_fake=True,
    ),
    "minimizeToTray": SettingDefinition(
        name="minimizeToTray",
        category="general",
        type="boolean",
        default=True,
        label="Minimize to Tray",
        description="Keep running in system tray when closed",
        is_fake=True,
    ),
    "startupWithSystem": SettingDefinition(
        name="startupWithSystem",
        category="general",
        type="boolean",
        default=False,
        label="Start with System",
        description="Launch automatically on Windows startup",
        is_fake=True,
    ),
    "theme": SettingDefinition(
        name="theme",
        category="general",
        type="enum",
        default=UIConstants.DEFAULT_THEME,
        label="Theme",
        description="Application color theme",
        options=["light", "dark", "cyber", "dracula"],
    ),
    # ============================================
    # Transcription Settings
    # ============================================
    "model_name": SettingDefinition(
        name="model_name",
        category="transcription",
        type="enum",
        default=ModelConstants.DEFAULT_MODEL_NAME,
        label="Model",
        description="Whisper model size - larger is more accurate but slower",
        options=["tiny", "base", "small", "medium", "large-v3"],
    ),
    "default_asr_model_id": SettingDefinition(
        name="default_asr_model_id",
        category="transcription",
        type="string",
        default="whisper-medium",
        label="Default ASR Model ID",
        description="Catalog ID for the default ASR model",
    ),
    "microphone_asr_model_id": SettingDefinition(
        name="microphone_asr_model_id",
        category="transcription",
        type="string",
        default="whisper-medium",
        label="Microphone ASR Model ID",
        description="Catalog ID for the default microphone transcription model",
    ),
    "system_asr_model_id": SettingDefinition(
        name="system_asr_model_id",
        category="transcription",
        type="string",
        default="whisper-medium",
        label="System Audio ASR Model ID",
        description="Catalog ID for the default system-audio transcription model",
    ),
    "refinement_mode": SettingDefinition(
        name="refinement_mode",
        category="transcription",
        type="enum",
        default=RefinerConstants.DEFAULT_REFINEMENT_MODE,
        label="Refinement Mode",
        description="Post-processing mode for transcript refinement",
        options=["off", "strict", "polished"],
    ),
    "compute_type": SettingDefinition(
        name="compute_type",
        category="transcription",
        type="enum",
        default=ModelConstants.DEFAULT_COMPUTE_TYPE,
        label="Compute Type",
        description="Precision mode - float16 for quality, int8 for speed",
        options=["float16", "int8", "int8_float16"],
    ),
    "chunk_duration": SettingDefinition(
        name="chunk_duration",
        category="transcription",
        type="range",
        default=AudioConstants.DEFAULT_CHUNK_SECONDS,
        label="Chunk Duration",
        description="Audio chunk size in seconds",
        min=0.5,
        max=5.0,
        step=0.1,
        suffix="s",
    ),
    "overlap_ratio": SettingDefinition(
        name="overlap_ratio",
        category="transcription",
        type="range",
        default=AudioConstants.DEFAULT_OVERLAP_SECONDS / AudioConstants.DEFAULT_CHUNK_SECONDS,
        label="Overlap Ratio",
        description="Audio overlap between chunks",
        min=0,
        max=0.5,
        step=0.05,
    ),
    "vad_enabled": SettingDefinition(
        name="vad_enabled",
        category="transcription",
        type="boolean",
        default=VADConstants.DEFAULT_FILTER_ENABLED,
        label="Enable VAD",
        description="Voice Activity Detection",
    ),
    "vad_threshold_db": SettingDefinition(
        name="vad_threshold_db",
        category="transcription",
        type="range",
        default=VADConstants.DEFAULT_THRESHOLD_DB,
        label="VAD Threshold",
        description="Energy threshold for speech detection",
        min=-60,
        max=-20,
        step=1,
        suffix="dB",
    ),
    "vad_min_silence_ms": SettingDefinition(
        name="vad_min_silence_ms",
        category="transcription",
        type="range",
        default=200,
        label="VAD Min Silence",
        description="Minimum silence duration to consider end of speech",
        min=0,
        max=5000,
        step=50,
        suffix="ms",
    ),
    "vad_speech_pad_ms": SettingDefinition(
        name="vad_speech_pad_ms",
        category="transcription",
        type="range",
        default=200,
        label="VAD Speech Padding",
        description="Padding added to speech segments",
        min=0,
        max=1000,
        step=50,
        suffix="ms",
    ),
    "confidence_threshold": SettingDefinition(
        name="confidence_threshold",
        category="transcription",
        type="range",
        default=ModelConstants.DEFAULT_CONFIDENCE_THRESHOLD,
        label="Confidence Threshold",
        description="Minimum confidence for transcript segments",
        min=0,
        max=1,
        step=0.05,
    ),
    "enable_filler_filter": SettingDefinition(
        name="enable_filler_filter",
        category="transcription",
        type="boolean",
        default=True,
        label="Filter Filler Words",
        description="Remove um, uh, etc.",
    ),
    "enable_hallucination_filter": SettingDefinition(
        name="enable_hallucination_filter",
        category="transcription",
        type="boolean",
        default=True,
        label="Filter Hallucinations",
        description="Remove likely incorrect segments",
    ),
    "min_segment_length": SettingDefinition(
        name="min_segment_length",
        category="transcription",
        type="range",
        default=ModelConstants.MIN_SEGMENT_LENGTH,
        label="Min Segment Length",
        description="Minimum duration for transcript segments",
        min=0.1,
        max=2.0,
        step=0.1,
        suffix="s",
    ),
    "max_workers": SettingDefinition(
        name="max_workers",
        category="transcription",
        type="range",
        default=PerformanceConstants.DEFAULT_MAX_WORKERS,
        label="Max Workers",
        description="Number of parallel processing workers",
        min=1,
        max=16,
        step=1,
        is_fake=True,
    ),
    "use_parallel_processing": SettingDefinition(
        name="use_parallel_processing",
        category="transcription",
        type="boolean",
        default=True,
        label="Parallel Processing",
        description="Use multiple workers for faster transcription",
        is_fake=True,
    ),
    "preload_model": SettingDefinition(
        name="preload_model",
        category="transcription",
        type="boolean",
        default=True,
        label="Preload Model",
        description="Keep model loaded in memory",
        is_fake=True,
    ),
    "hotkey_optimized": SettingDefinition(
        name="hotkey_optimized",
        category="transcription",
        type="boolean",
        default=False,
        label="Hotkey Optimized",
        description="Optimize for quick hotkey-triggered sessions",
    ),
    "beam_size": SettingDefinition(
        name="beam_size",
        category="transcription",
        type="number",
        default=ModelConstants.DEFAULT_BEAM_SIZE,
        label="Beam Size",
        description="Beam search width",
        min=1,
        max=20,
    ),
    "best_of": SettingDefinition(
        name="best_of",
        category="transcription",
        type="number",
        default=ModelConstants.DEFAULT_BEST_OF,
        label="Best Of",
        description="Number of candidates to consider",
        min=1,
        max=20,
    ),
    "patience": SettingDefinition(
        name="patience",
        category="transcription",
        type="number",
        default=ModelConstants.DEFAULT_PATIENCE,
        label="Patience",
        description="Beam search patience factor",
        min=0.1,
        max=5.0,
        step=0.1,
        is_fake=True,
    ),
    "temperature": SettingDefinition(
        name="temperature",
        category="transcription",
        type="range",
        default=ModelConstants.DEFAULT_TEMPERATURE,
        label="Temperature",
        description="Sampling temperature",
        min=0,
        max=1,
        step=0.1,
    ),
    # ============================================
    # Refiner Settings
    # ============================================
    "selected_model_id": SettingDefinition(
        name="selected_model_id",
        category="refiner",
        type="string",
        default=RefinerConstants.DEFAULT_MODEL_ID,
        label="Selected Model ID",
        description="LLM model for transcript refinement",
    ),
    "runtime_enabled": SettingDefinition(
        name="runtime_enabled",
        category="refiner",
        type="boolean",
        default=False,
        label="Runtime Enabled",
        description="Enable runtime LLM refinement",
    ),
    "cleanup_instructions": SettingDefinition(
        name="cleanup_instructions",
        category="refiner",
        type="string",
        default="",
        label="Cleanup Instructions",
        description="Optional additional instructions for the final refiner pass",
    ),
    "engine_preference": SettingDefinition(
        name="engine_preference",
        category="refiner",
        type="enum",
        default=RefinerConstants.DEFAULT_ENGINE_PREFERENCE,
        label="Engine Preference",
        description="Preferred LLM inference engine",
        options=["llamacpp", "ollama"],
    ),
    # ============================================
    # Audio Settings
    # ============================================
    "captureMode": SettingDefinition(
        name="captureMode",
        category="audio",
        type="enum",
        default="microphone",
        label="Capture Mode",
        description="Choose between microphone dictation and system-audio capture",
        options=["system", "microphone"],
    ),
    "default_capture_source": SettingDefinition(
        name="default_capture_source",
        category="audio",
        type="enum",
        default="microphone",
        label="Default Capture Source",
        description="Capture source selected when the app starts and for hotkey dictation",
        options=["system", "microphone"],
    ),
    "defaultDeviceId": SettingDefinition(
        name="defaultDeviceId",
        category="audio",
        type="string",
        default=AudioConstants.DEFAULT_CAPTURE_DEVICE_ID,
        label="Default Audio Device",
        description="Primary device for the selected capture mode",
    ),
    "backend": SettingDefinition(
        name="backend",
        category="audio",
        type="enum",
        default=AudioConstants.DEFAULT_BACKEND,
        label="Audio Backend",
        description="Low-level Windows capture backend",
        options=["auto", "pyaudio", "soundcard"],
    ),
    "audio_backend": SettingDefinition(
        name="audio_backend",
        category="audio",
        type="enum",
        default=AudioConstants.DEFAULT_BACKEND,
        label="Audio Backend",
        description="Low-level Windows capture backend",
        options=["auto", "pyaudio", "soundcard"],
    ),
    "sampleRate": SettingDefinition(
        name="sampleRate",
        category="audio",
        type="enum",
        default=AudioConstants.DEFAULT_SAMPLE_RATE,
        label="Sample Rate",
        description="Audio sample rate - 16kHz recommended for Whisper",
        options=[8000, 16000, 22050, 44100, 48000],
    ),
    "vadEnabled": SettingDefinition(
        name="vadEnabled",
        category="audio",
        type="boolean",
        default=VADConstants.DEFAULT_FILTER_ENABLED,
        label="Enable VAD",
        description="Voice Activity Detection (audio capture)",
    ),
    "vadThresholdDb": SettingDefinition(
        name="vadThresholdDb",
        category="audio",
        type="range",
        default=VADConstants.DEFAULT_THRESHOLD_DB,
        label="VAD Threshold",
        description="Energy threshold for speech detection",
        min=-60,
        max=-20,
        step=1,
        suffix="dB",
    ),
    "noiseFiltering": SettingDefinition(
        name="noiseFiltering",
        category="audio",
        type="boolean",
        default=True,
        label="Noise Filtering",
        description="Reduce background noise",
        is_fake=True,
    ),
    "echoCancellation": SettingDefinition(
        name="echoCancellation",
        category="audio",
        type="boolean",
        default=True,
        label="Echo Cancellation",
        description="Remove echo from speakers",
        is_fake=True,
    ),
    "autoGainControl": SettingDefinition(
        name="autoGainControl",
        category="audio",
        type="boolean",
        default=True,
        label="Auto Gain Control",
        description="Automatically adjust input volume",
        is_fake=True,
    ),
    # ============================================
    # Hotkey Settings
    # ============================================
    "enabled": SettingDefinition(
        name="enabled",
        category="hotkey",
        type="boolean",
        default=False,
        label="Enable Global Hotkey",
        description="Activate transcription from anywhere",
    ),
    "key_combination": SettingDefinition(
        name="key_combination",
        category="hotkey",
        type="string",
        default=UIConstants.DEFAULT_HOTKEY,
        label="Key Combination",
        description="Press the button to record a new hotkey",
    ),
    "hold_mode": SettingDefinition(
        name="hold_mode",
        category="hotkey",
        type="boolean",
        default=False,
        label="Hold Mode",
        description="Record while holding the hotkey",
    ),
    "auto_inject": SettingDefinition(
        name="auto_inject",
        category="hotkey",
        type="boolean",
        default=True,
        label="Auto-inject Text",
        description="Type transcription into active window",
    ),
    "language": SettingDefinition(
        name="language",
        category="hotkey",
        type="string",
        default=UIConstants.DEFAULT_LANGUAGE,
        label="Dictation Language",
        description="Default language for hotkey dictation",
    ),
    "device_id": SettingDefinition(
        name="device_id",
        category="hotkey",
        type="string",
        default=AudioConstants.DEFAULT_CAPTURE_DEVICE_ID,
        label="Dictation Microphone",
        description="Microphone used for quick dictation",
    ),
    "finish_mode_default": SettingDefinition(
        name="finish_mode_default",
        category="hotkey",
        type="enum",
        default="finish_and_paste",
        label="Default Finish Action",
        description="What happens when dictation stops from the hotkey toggle",
        options=["finish", "finish_and_paste"],
    ),
    "show_floating_window": SettingDefinition(
        name="show_floating_window",
        category="hotkey",
        type="boolean",
        default=True,
        label="Show Floating Window",
        description="Display overlay during transcription",
    ),
    "floating_window_position": SettingDefinition(
        name="floating_window_position",
        category="hotkey",
        type="enum",
        default="bottom-right",
        label="Floating Window Position",
        description="Where to show the transcription overlay",
        options=["top-left", "top-right", "bottom-left", "bottom-right", "center"],
    ),
    "record_on_start": SettingDefinition(
        name="record_on_start",
        category="hotkey",
        type="boolean",
        default=False,
        label="Record on Start",
        description="Begin recording when hotkey is activated",
    ),
    "stop_on_release": SettingDefinition(
        name="stop_on_release",
        category="hotkey",
        type="boolean",
        default=False,
        label="Stop on Release",
        description="End recording when hotkey is released",
    ),
    "copy_to_clipboard": SettingDefinition(
        name="copy_to_clipboard",
        category="hotkey",
        type="boolean",
        default=True,
        label="Copy to Clipboard",
        description="Automatically copy transcription",
    ),
    # ============================================
    # Advanced Settings
    # ============================================
    "debugMode": SettingDefinition(
        name="debugMode",
        category="advanced",
        type="boolean",
        default=False,
        label="Debug Mode",
        description="Enable verbose logging and diagnostics",
    ),
    "logLevel": SettingDefinition(
        name="logLevel",
        category="advanced",
        type="enum",
        default="INFO",
        label="Log Level",
        description="Minimum severity for log messages",
        options=["DEBUG", "INFO", "WARN", "ERROR"],
    ),
    "enableMetrics": SettingDefinition(
        name="enableMetrics",
        category="advanced",
        type="boolean",
        default=True,
        label="Enable Metrics",
        description="Collect and report performance metrics",
    ),
    "maxLogFiles": SettingDefinition(
        name="maxLogFiles",
        category="advanced",
        type="number",
        default=UIConstants.MAX_LOG_FILES,
        label="Max Log Files",
        description="Number of log files to retain",
        min=1,
        max=100,
    ),
    "experimentalStem": SettingDefinition(
        name="experimentalStem",
        category="advanced",
        type="boolean",
        default=False,
        label="Enhanced STEM Detection",
        description="Advanced formula and equation recognition",
        is_fake=True,
    ),
    "experimentalGpuAccel": SettingDefinition(
        name="experimentalGpuAccel",
        category="advanced",
        type="boolean",
        default=True,
        label="GPU Acceleration",
        description="Use GPU for pre-processing when available",
        is_fake=True,
    ),
}


# ============================================
# Registry Access Functions
# ============================================
def get_setting(name: str) -> SettingDefinition:
    """Get setting definition by name.

    Args:
        name: Setting name/key

    Returns:
        SettingDefinition for the setting

    Raises:
        KeyError: If setting not found
    """
    if name not in SETTINGS_REGISTRY:
        raise KeyError(f"Unknown setting: {name}")
    return SETTINGS_REGISTRY[name]


def get_settings_by_category(category: str) -> dict[str, SettingDefinition]:
    """Get all settings in a category.

    Args:
        category: Category name (e.g., 'general', 'transcription')

    Returns:
        Dictionary of setting names to definitions
    """
    return {name: defn for name, defn in SETTINGS_REGISTRY.items() if defn.category == category}


def get_all_categories() -> set[str]:
    """Get all unique category names."""
    return {defn.category for defn in SETTINGS_REGISTRY.values()}


def get_fake_settings() -> dict[str, list[str]]:
    """Get all fake settings organized by category.

    Returns:
        Dictionary mapping category names to lists of fake setting names
    """
    result: dict[str, list[str]] = {}
    for name in FAKE_SETTINGS:
        if name in SETTINGS_REGISTRY:
            category = SETTINGS_REGISTRY[name].category
            if category not in result:
                result[category] = []
            result[category].append(name)
    return result


# ============================================
# Validation Functions
# ============================================
def validate_setting(name: str, value: Any) -> tuple[bool, str]:
    """Validate a setting value against its definition.

    Args:
        name: Setting name
        value: Value to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if name not in SETTINGS_REGISTRY:
        return False, f"Unknown setting: {name}"

    defn = SETTINGS_REGISTRY[name]

    # Type validation
    if defn.type == "boolean":
        if not isinstance(value, bool):
            return False, f"Expected boolean, got {type(value).__name__}"

    elif defn.type == "string":
        if not isinstance(value, str):
            return False, f"Expected string, got {type(value).__name__}"

    elif defn.type in ("number", "range"):
        if not isinstance(value, (int, float)):
            return False, f"Expected number, got {type(value).__name__}"

    elif defn.type == "enum":
        if defn.options is not None and value not in defn.options:
            return False, f"Invalid value. Must be one of: {defn.options}"

    # Range validation
    if defn.min is not None:
        if isinstance(value, (int, float)) and value < defn.min:
            return False, f"Value must be >= {defn.min}"

    if defn.max is not None:
        if isinstance(value, (int, float)) and value > defn.max:
            return False, f"Value must be <= {defn.max}"

    # Custom validation
    if defn.validation_fn is not None:
        return defn.validation_fn(value)

    return True, ""


def validate_category_settings(category: str, settings: dict[str, Any]) -> list[str]:
    """Validate all settings in a category.

    Args:
        category: Category name
        settings: Dictionary of setting names to values

    Returns:
        List of validation error messages
    """
    errors = []
    category_settings = get_settings_by_category(category)

    for name, value in settings.items():
        if name not in category_settings:
            errors.append(f"{name}: Unknown setting for category '{category}'")
            continue

        valid, error = validate_setting(name, value)
        if not valid:
            errors.append(f"{name}: {error}")

    return errors


def get_setting_default(name: str) -> Any:
    """Get the default value for a setting.

    Args:
        name: Setting name

    Returns:
        Default value

    Raises:
        KeyError: If setting not found
    """
    return get_setting(name).default


def get_category_defaults(category: str) -> dict[str, Any]:
    """Get all default values for a category.

    Args:
        category: Category name

    Returns:
        Dictionary of setting names to default values
    """
    return {name: defn.default for name, defn in get_settings_by_category(category).items()}


def get_all_defaults() -> dict[str, dict[str, Any]]:
    """Get all default values organized by category.

    Returns:
        Nested dictionary of category -> setting -> default value
    """
    result: dict[str, dict[str, Any]] = {}
    for name, defn in SETTINGS_REGISTRY.items():
        if defn.category not in result:
            result[defn.category] = {}
        result[defn.category][name] = defn.default
    return result


# ============================================
# Settings Version
# ============================================
CURRENT_SETTINGS_VERSION = UIConstants.SETTINGS_VERSION


def get_settings_version() -> int:
    """Get the current settings version."""
    return CURRENT_SETTINGS_VERSION
