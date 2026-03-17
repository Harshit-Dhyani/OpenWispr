"""Settings migrations with clean version-based system.

This module provides a simple, sequential migration system for settings.
Each migration is a function that transforms settings from version N to N+1.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.config.settings import CURRENT_SETTINGS_VERSION, get_category_defaults

logger = logging.getLogger(__name__)


# ============================================
# Migration Functions
# ============================================
def _v0_to_v1(settings: dict[str, Any]) -> dict[str, Any]:
    """Migration from pre-versioned settings to v1."""
    # Initialize with defaults for any missing categories
    result = {
        "general": {**get_category_defaults("general"), **settings.get("general", {})},
        "transcription": {
            **get_category_defaults("transcription"),
            **settings.get("transcription", {}),
        },
        "refiner": {**get_category_defaults("refiner"), **settings.get("refiner", {})},
        "audio": {**get_category_defaults("audio"), **settings.get("audio", {})},
        "hotkey": {**get_category_defaults("hotkey"), **settings.get("hotkey", {})},
        "advanced": {**get_category_defaults("advanced"), **settings.get("advanced", {})},
    }
    return result


def _v1_to_v2(settings: dict[str, Any]) -> dict[str, Any]:
    """Migration from v1 to v2.

    - Adds default_asr_model_id mapping from model_name
    - Adds refinement_mode and refiner settings
    """
    result = dict(settings)

    transcription = dict(result.get("transcription", {}))
    refiner = dict(result.get("refiner", {}))

    # Map model_name to default_asr_model_id
    model_name = transcription.get("model_name", "medium")
    model_id_map = {
        "tiny": "whisper-tiny",
        "base": "whisper-small",
        "small": "whisper-small",
        "medium": "whisper-medium",
        "large-v3": "whisper-large-v3",
        "turbo": "whisper-turbo",
    }
    transcription["default_asr_model_id"] = model_id_map.get(model_name, "whisper-medium")

    # Add refinement settings
    transcription.setdefault("refinement_mode", "off")
    transcription.setdefault("refinement_profile", "clean_dictation")
    refiner.setdefault("selected_model_id", "qwen2.5-3b-instruct")
    refiner.setdefault("runtime_enabled", True)
    refiner.setdefault("engine_preference", "llamacpp")

    result["transcription"] = transcription
    result["refiner"] = refiner
    return result


def _v2_to_v3(settings: dict[str, Any]) -> dict[str, Any]:
    """Migration from v2 to v3.

    - Adds hotkey settings
    - Adds VAD settings
    """
    result = dict(settings)

    hotkey = dict(result.get("hotkey", {}))
    transcription = dict(result.get("transcription", {}))

    # Ensure all hotkey settings exist
    hotkey_defaults = get_category_defaults("hotkey")
    for key, value in hotkey_defaults.items():
        hotkey.setdefault(key, value)

    # Move VAD settings to transcription if they only exist in audio
    audio = result.get("audio", {})
    if "vad_enabled" in audio and "vad_enabled" not in transcription:
        transcription["vad_enabled"] = audio["vad_enabled"]
    if "vad_threshold_db" in audio and "vad_threshold_db" not in transcription:
        transcription["vad_threshold_db"] = audio["vad_threshold_db"]

    result["hotkey"] = hotkey
    result["transcription"] = transcription
    return result


def _v3_to_v4(settings: dict[str, Any]) -> dict[str, Any]:
    """Migration from v3 to v4.

    - Renames backend to audio_backend in audio settings
    - Removes duplicate VAD settings from audio
    """
    result = dict(settings)

    audio = dict(result.get("audio", {}))

    # Rename backend to audio_backend
    if "backend" in audio and "audio_backend" not in audio:
        audio["audio_backend"] = audio.pop("backend")
    else:
        audio.setdefault("audio_backend", "auto")

    # Remove duplicate VAD settings (now only in transcription)
    audio.pop("vadEnabled", None)
    audio.pop("vadThresholdDb", None)

    result["audio"] = audio
    return result


def _v4_to_v5(settings: dict[str, Any]) -> dict[str, Any]:
    """Migration from v4 to v5.

    - Adds coach settings defaults and built-in prompt templates
    """
    result = dict(settings)
    coach = dict(result.get("coach", {}))
    for key, value in get_category_defaults("coach").items():
        coach.setdefault(key, value)
    result["coach"] = coach
    return result


def _v5_to_v6(settings: dict[str, Any]) -> dict[str, Any]:
    """Migration from v5 to v6.

    - Migrates whisper-turbo to whisper-medium (turbo was disabled by default)
    - Adds microphone_asr_model_id and system_asr_model_id defaults
    """
    result = dict(settings)

    transcription = dict(result.get("transcription", {}))

    # Migrate whisper-turbo to whisper-medium
    turbo_to_medium = "whisper-medium"
    model_keys_to_migrate = [
        "default_asr_model_id",
        "microphone_asr_model_id",
        "system_asr_model_id",
    ]
    for key in model_keys_to_migrate:
        if transcription.get(key) == "whisper-turbo":
            transcription[key] = turbo_to_medium

    # Ensure new model ID fields exist
    transcription.setdefault("microphone_asr_model_id", "whisper-medium")
    transcription.setdefault("system_asr_model_id", "whisper-medium")

    result["transcription"] = transcription
    return result


def _v6_to_v7(settings: dict[str, Any]) -> dict[str, Any]:
    """Migration from v6 to v7.

    - Migrates whisper-medium to whisper-turbo (turbo is now the recommended default)
    - Faster and still accurate
    """
    result = dict(settings)

    transcription = dict(result.get("transcription", {}))

    # Migrate whisper-medium to whisper-turbo for faster performance
    medium_to_turbo = "whisper-turbo"
    model_keys = [
        "default_asr_model_id",
        "microphone_asr_model_id",
        "system_asr_model_id",
    ]
    for key in model_keys:
        if transcription.get(key) == "whisper-medium":
            transcription[key] = medium_to_turbo

    result["transcription"] = transcription
    return result


# ============================================
# Migration Registry
# ============================================
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    1: _v0_to_v1,
    2: _v1_to_v2,
    3: _v2_to_v3,
    4: _v3_to_v4,
    5: _v4_to_v5,
    6: _v5_to_v6,
    7: _v6_to_v7,
}


def migrate(
    settings: dict[str, Any],
    from_version: int,
    to_version: int = CURRENT_SETTINGS_VERSION,
) -> dict[str, Any]:
    """Migrate settings from one version to another.

    Args:
        settings: Settings dictionary to migrate
        from_version: Current version of settings
        to_version: Target version (defaults to current)

    Returns:
        Migrated settings dictionary
    """
    if from_version >= to_version:
        return settings

    result = dict(settings)

    for version in range(from_version, to_version):
        migration_fn = MIGRATIONS.get(version + 1)
        if migration_fn:
            logger.debug(f"Migrating settings from v{version} to v{version + 1}")
            result = migration_fn(result)
        else:
            logger.warning(f"No migration found from v{version} to v{version + 1}")

    result["version"] = to_version
    return result


def needs_migration(settings: dict[str, Any]) -> bool:
    """Check if settings need migration.

    Args:
        settings: Settings dictionary

    Returns:
        True if migration is needed
    """
    version = settings.get("version", 0)
    return version < CURRENT_SETTINGS_VERSION


def get_settings_version(settings: dict[str, Any]) -> int:
    """Get the version of settings.

    Args:
        settings: Settings dictionary

    Returns:
        Version number (0 if not specified)
    """
    return settings.get("version", 0)


def migrate_to_current(settings: dict[str, Any]) -> dict[str, Any]:
    """Migrate settings to the current version.

    Args:
        settings: Settings dictionary

    Returns:
        Settings migrated to current version
    """
    from_version = get_settings_version(settings)
    return migrate(settings, from_version, CURRENT_SETTINGS_VERSION)
