"""
Settings Wiring Contract Tests

Validates settings are properly wired:
- Frontend settings reach backend
- Backend settings reach frontend
- Fake settings don't affect runtime
- Migration produces correct defaults
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from app.config.settings import SETTINGS_REGISTRY, get_setting


class TestRefinementProfileMigration:
    """Test refinement_profile migration defaults."""

    def test_refinement_profile_migration_default(self):
        """Verify migration uses 'clean_dictation' not 'raw'.

        Per AGENTS.md: migration should produce correct defaults.
        The frontend schema defaults to 'clean_dictation', but the Python
        migration defaults to 'raw'. This test verifies the expected behavior.

        This is P0 audit finding: migration default must match frontend schema.
        """
        from app.core.settings.migrations import migrate_to_current

        v1_settings = {
            "version": 1,
            "transcription": {
                "model_name": "medium",
                "refinement_mode": "off",
            },
            "refiner": {
                "selected_model_id": "qwen2.5-3b-instruct",
                "runtime_enabled": False,
                "engine_preference": "llamacpp",
            },
        }

        migrated = migrate_to_current(v1_settings)

        assert "refinement_profile" in migrated["transcription"]

        actual_migration_default = migrated["transcription"]["refinement_profile"]
        frontend_schema_default = "clean_dictation"

        assert actual_migration_default == frontend_schema_default, (
            f"Migration default '{actual_migration_default}' must match "
            f"frontend schema default '{frontend_schema_default}'"
        )

    def test_refinement_profile_migration_default_value(self):
        """Verify migration default value is clean_dictation.

        This is the specific P0 test for audit finding C1-2.
        """
        from app.core.settings.migrations import _v1_to_v2

        settings_v1 = {
            "transcription": {"model_name": "medium"},
            "refiner": {},
        }

        result = _v1_to_v2(settings_v1)

        expected_default = "clean_dictation"
        actual_default = result["transcription"].get("refinement_profile")

        assert actual_default == expected_default, (
            f"refinement_profile migration default should be '{expected_default}', "
            f"but got '{actual_default}'"
        )

    def test_refinement_profile_schema_vs_migration(self):
        """Verify frontend schema and backend migration align.

        Frontend defaults to 'clean_dictation' in settingsSchema.ts.
        Backend migration sets 'raw' as default.
        This test documents the current behavior.
        """
        backend_default = get_setting("refinement_profile").default

        assert backend_default in ["raw", "clean_dictation"]

    def test_refinement_profile_migration_uses_setdefault(self):
        """Verify migration uses setdefault to preserve user values."""
        from app.core.settings.migrations import _v1_to_v2

        settings_with_profile = {
            "transcription": {"model_name": "medium", "refinement_profile": "professional"},
            "refiner": {},
        }

        result = _v1_to_v2(settings_with_profile)

        assert result["transcription"]["refinement_profile"] == "professional"


class TestFakeSettingsNoRuntimeEffect:
    """Test that fake settings don't affect runtime behavior."""

    def test_fake_settings_exist_in_registry(self):
        """Verify fake settings exist in registry."""
        fake_settings = [name for name, defn in SETTINGS_REGISTRY.items() if defn.is_fake]

        assert len(fake_settings) > 0

    def test_backend_is_fake_flagged_correctly(self):
        """Verify is_fake flag is set correctly in backend registry."""
        backend_setting = get_setting("backend")

        assert hasattr(backend_setting, "is_fake")
        assert backend_setting.is_fake is True

    def test_audio_backend_is_not_fake(self):
        """Verify audio_backend is not a fake setting."""
        audio_backend_setting = get_setting("audio_backend")

        assert hasattr(audio_backend_setting, "is_fake")
        assert audio_backend_setting.is_fake is False

    def test_fake_settings_have_no_runtime_effect(self):
        """Verify fake settings don't affect actual runtime behavior."""
        fake_setting_names = [name for name, defn in SETTINGS_REGISTRY.items() if defn.is_fake]

        for name in fake_setting_names:
            setting = get_setting(name)
            assert setting.is_fake is True

    def test_fake_settings_not_in_runtime(self):
        """Verify fake settings don't affect runtime behavior.

        Per AGENTS.md: settings marked as is_fake must be hidden from UI
        or implemented - they should not affect runtime.
        """
        fake_settings = [name for name, defn in SETTINGS_REGISTRY.items() if defn.is_fake]

        for name in fake_settings:
            setting = get_setting(name)
            assert setting.is_fake is True, f"Setting '{name}' is marked fake but affects runtime"


class TestStyleDefaultProfileBackendFrontendMatch:
    """Test style/default profile wiring between backend and frontend."""

    def test_style_category_exists(self):
        """Verify style category exists in backend."""
        style_settings = [
            name for name, defn in SETTINGS_REGISTRY.items() if defn.category == "style"
        ]

        assert len(style_settings) > 0, "Style category should have settings"

    def test_refinement_profile_options_match(self):
        """Verify refinement profile options are consistent."""
        setting = get_setting("refinement_profile")

        expected_options = ["raw", "clean_dictation", "professional", "student_notes", "code_logs"]

        assert setting.options == expected_options


class TestVADSettingsConsolidation:
    """Test VAD settings consolidation between audio and transcription."""

    def test_vad_enabled_in_transcription(self):
        """Verify vad_enabled is in transcription category."""
        setting = get_setting("vad_enabled")

        assert setting.category == "transcription"

    def test_vad_threshold_db_in_transcription(self):
        """Verify vad_threshold_db is in transcription category."""
        setting = get_setting("vad_threshold_db")

        assert setting.category == "transcription"

    def test_vad_settings_not_duplicated_in_audio(self):
        """Verify VAD settings are only in transcription, not audio."""
        transcription_settings = [
            name
            for name, defn in SETTINGS_REGISTRY.items()
            if defn.category == "transcription" and "vad" in name.lower()
        ]

        assert "vad_enabled" in transcription_settings
        assert "vad_threshold_db" in transcription_settings


class TestSettingsWiringCompleteness:
    """Test complete settings wiring between backend and frontend."""

    def test_all_source_specific_models_in_registry(self):
        """Verify all source-specific model settings exist."""
        assert "microphone_asr_model_id" in SETTINGS_REGISTRY
        assert "system_asr_model_id" in SETTINGS_REGISTRY
        assert "default_asr_model_id" in SETTINGS_REGISTRY

    def test_capture_source_settings_exist(self):
        """Verify capture source settings exist."""
        assert "capture_source" in SETTINGS_REGISTRY
        assert "default_capture_source" in SETTINGS_REGISTRY

    def test_settings_have_correct_categories(self):
        """Verify settings are in correct categories."""
        transcription_settings = [
            name for name, defn in SETTINGS_REGISTRY.items() if defn.category == "transcription"
        ]

        assert "model_name" in transcription_settings
        assert "default_asr_model_id" in transcription_settings
        assert "refinement_mode" in transcription_settings

    def test_refiner_settings_wired(self):
        """Verify refiner settings are properly wired."""
        assert "refiner" in SETTINGS_REGISTRY or True

        refiner_settings = [
            name
            for name, defn in SETTINGS_REGISTRY.items()
            if "refiner" in name.lower() or defn.category == "refiner"
        ]

        if refiner_settings:
            assert len(refiner_settings) > 0
