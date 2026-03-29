from __future__ import annotations

import json

import pytest

from app.config.settings import CURRENT_SETTINGS_VERSION, get_category_defaults
from app.core.settings.migrations import (
    get_settings_version,
    migrate,
    migrate_to_current,
    needs_migration,
)


def test_settings_migration_from_legacy_format():
    """Test migration from legacy settings format (version 0)."""
    legacy_settings = {
        "general": {},
        "transcription": {},
        "refiner": {},
        "audio": {},
        "hotkey": {},
        "advanced": {},
    }

    migrated = migrate_to_current(legacy_settings)

    assert migrated["version"] == CURRENT_SETTINGS_VERSION
    assert "general" in migrated
    assert "transcription" in migrated
    assert "audio" in migrated


def test_settings_migration_v0_to_v1():
    """Test migration from v0 to v1."""
    settings_v0 = {
        "general": {"theme": "dark"},
        "transcription": {},
    }

    migrated = migrate(settings_v0, 0, 1)

    assert migrated["version"] == 1
    assert "general" in migrated
    assert "transcription" in migrated
    assert "refiner" in migrated
    assert "audio" in migrated
    assert "hotkey" in migrated
    assert "advanced" in migrated


def test_settings_migration_v1_to_v2_model_name_mapping():
    """Test that legacy model_name is mapped to default_asr_model_id in v1->v2."""
    settings_v1 = {
        "version": 1,
        "transcription": {"model_name": "medium"},
    }

    migrated = migrate(settings_v1, 1, 2)

    assert migrated["version"] == 2
    assert migrated["transcription"]["default_asr_model_id"] == "whisper-medium"
    assert migrated["transcription"]["refinement_mode"] == "off"
    assert "refiner" in migrated


def test_settings_migration_v1_to_v2_refiner_defaults():
    """Test that refiner defaults are added in v1->v2 migration."""
    settings_v1 = {
        "version": 1,
        "transcription": {"model_name": "large-v3"},
    }

    migrated = migrate(settings_v1, 1, 2)

    assert migrated["refiner"]["selected_model_id"] == "qwen2.5-3b-instruct"
    assert migrated["refiner"]["runtime_enabled"] is True
    assert migrated["refiner"]["engine_preference"] == "llamacpp"


def test_settings_migration_v2_to_v3_hotkey_defaults():
    """Test that hotkey defaults are added in v2->v3 migration."""
    settings_v2 = {
        "version": 2,
        "transcription": {"model_name": "small"},
    }

    migrated = migrate(settings_v2, 2, 3)

    assert migrated["version"] == 3
    hotkey_defaults = get_category_defaults("hotkey")
    for key, value in hotkey_defaults.items():
        assert migrated["hotkey"].get(key) == value


def test_settings_migration_v2_to_v3_vad_migration():
    """Test that VAD settings are migrated from audio to transcription in v2->v3."""
    settings_v2 = {
        "version": 2,
        "audio": {"vad_enabled": True, "vad_threshold_db": -40},
    }

    migrated = migrate(settings_v2, 2, 3)

    assert migrated["transcription"]["vad_enabled"] is True
    assert migrated["transcription"]["vad_threshold_db"] == -40


def test_settings_migration_v3_to_v4_audio_backend_rename():
    """Test that backend is renamed to audio_backend in v3->v4 migration."""
    settings_v3 = {
        "version": 3,
        "audio": {"backend": "pyaudio"},
    }

    migrated = migrate(settings_v3, 3, 4)

    assert migrated["version"] == 4
    assert migrated["audio"]["audio_backend"] == "pyaudio"
    assert "backend" not in migrated["audio"]


def test_settings_migration_v3_to_v4_vad_cleanup():
    """Test that duplicate VAD settings are removed in v3->v4 migration."""
    settings_v3 = {
        "version": 3,
        "audio": {"vadEnabled": True, "vadThresholdDb": -35},
    }

    migrated = migrate(settings_v3, 3, 4)

    assert "vadEnabled" not in migrated["audio"]
    assert "vadThresholdDb" not in migrated["audio"]


def test_settings_migration_v4_to_v5_coach_defaults():
    """Test that coach defaults are added in v4->v5 migration."""
    settings_v4 = {
        "version": 4,
    }

    migrated = migrate(settings_v4, 4, 5)

    assert migrated["version"] == 5
    coach_defaults = get_category_defaults("coach")
    for key, value in coach_defaults.items():
        assert migrated["coach"].get(key) == value


def test_needs_migration_returns_true_for_old_version():
    """Test that needs_migration returns True for old settings."""
    old_settings = {"version": 1}

    assert needs_migration(old_settings) is True


def test_needs_migration_returns_false_for_current_version():
    """Test that needs_migration returns False for current settings."""
    current_settings = {"version": CURRENT_SETTINGS_VERSION}

    assert needs_migration(current_settings) is False


def test_needs_migration_returns_true_for_missing_version():
    """Test that needs_migration returns True for settings without version."""
    legacy_settings = {}

    assert needs_migration(legacy_settings) is True


def test_get_settings_version_returns_version():
    """Test that get_settings_version returns the correct version."""
    settings = {"version": 3}

    assert get_settings_version(settings) == 3


def test_get_settings_version_returns_zero_for_missing():
    """Test that get_settings_version returns 0 for settings without version."""
    settings = {}

    assert get_settings_version(settings) == 0


def test_migrate_no_op_for_same_version():
    """Test that migration is a no-op when from_version equals to_version."""
    settings = {"version": 5, "general": {"theme": "dark"}}

    migrated = migrate(settings, 5, 5)

    assert migrated["version"] == 5
    assert migrated["general"]["theme"] == "dark"


def test_migrate_no_op_for_newer_version():
    """Test that migration is a no-op when from_version > to_version."""
    settings = {"version": 6, "general": {}}

    migrated = migrate(settings, 6, 5)

    assert migrated["version"] == 6


def test_migrate_invalid_settings_graceful_handling():
    """Test that invalid settings are handled gracefully during migration."""
    invalid_settings = None

    with pytest.raises(TypeError):
        migrate(invalid_settings, 0, 1)


def test_migrate_partial_settings_graceful():
    """Test migration handles partial settings with missing categories."""
    partial_settings = {
        "version": 0,
        "transcription": {"model_name": "tiny"},
    }

    migrated = migrate_to_current(partial_settings)

    assert migrated["version"] == CURRENT_SETTINGS_VERSION
    assert "general" in migrated
    assert "transcription" in migrated
    assert migrated["transcription"]["default_asr_model_id"] == "whisper-tiny"


def test_migrate_preserves_existing_values():
    """Test that migration preserves existing values while adding defaults."""
    settings = {
        "version": 1,
        "transcription": {
            "model_name": "small",
            "language": "en",
        },
        "hotkey": {
            "enabled": False,
        },
    }

    migrated = migrate(settings, 1, 2)

    assert migrated["transcription"]["language"] == "en"
    assert migrated["hotkey"]["enabled"] is False
    assert migrated["transcription"]["default_asr_model_id"] == "whisper-small"


def test_migrate_legacy_audio_backend():
    """Test migration of legacy audio backend settings."""
    legacy_settings = {
        "version": 2,
        "audio": {
            "backend": "pyaudio",
            "sample_rate": 16000,
        },
    }

    migrated = migrate(legacy_settings, 2, CURRENT_SETTINGS_VERSION)

    assert migrated["audio"]["audio_backend"] == "pyaudio"
    assert migrated["audio"]["sample_rate"] == 16000


def test_settings_migration_integration_with_manager(tmp_path):
    """Test that migration functions correctly transform legacy settings."""
    legacy_settings = {
        "general": {"theme": "dark"},
        "transcription": {
            "model_name": "medium",
            "vad_enabled": True,
            "vad_threshold_db": -40,
        },
        "audio": {
            "backend": "pyaudio",
            "captureMode": "microphone",
        },
        "hotkey": {
            "enabled": True,
            "language": "en",
        },
        "advanced": {},
        "refiner": {},
        "coach": {},
        "version": 0,
    }

    migrated = migrate_to_current(legacy_settings)

    assert migrated["version"] == CURRENT_SETTINGS_VERSION
    assert migrated["transcription"]["default_asr_model_id"] == "whisper-turbo"
    assert migrated["transcription"]["vad_enabled"] is True
    assert migrated["transcription"]["vad_threshold_db"] == -40
    assert migrated["hotkey"]["enabled"] is True
    assert migrated["hotkey"]["language"] == "en"


def test_settings_migration_invalid_json_loads_defaults(tmp_path):
    """Test that SettingsManager falls back to defaults on invalid JSON."""
    from app.core.settings.manager import SettingsManager

    settings_path = tmp_path / "user_settings.json"
    settings_path.write_text("invalid json {", encoding="utf-8")

    manager = SettingsManager(settings_dir=tmp_path)
    settings = manager.get_settings()

    assert settings.general.theme == "light"
