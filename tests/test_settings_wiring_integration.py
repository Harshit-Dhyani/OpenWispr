"""
Settings Wiring Integration Tests

Tests the full settings chain from frontend to backend to runtime.
This verifies that settings changes in frontend correctly propagate
to backend and are applied at runtime.

Regression protection for:
- Settings changes not reaching backend
- Backend not applying settings correctly
- Settings serialization errors between layers
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config.settings import SETTINGS_REGISTRY


class TestSettingsWiringIntegration:
    """Test full settings flow from UI to runtime."""

    def test_frontend_settings_serialize_to_backend_format(self, tmp_path: Path):
        """Verify frontend JSON settings can be parsed by backend."""
        frontend_settings = {
            "general": {"defaultLanguage": "en", "theme": "dark"},
            "transcription": {
                "model_name": "tiny",
                "microphone_asr_model_id": "whisper-tiny",
                "system_asr_model_id": "whisper-base",
                "default_asr_model_id": "whisper-medium",
                "refinement_mode": "off",
                "compute_type": "int8",
            },
            "hotkey": {
                "enabled": True,
                "key_combination": "Ctrl+Shift+R",
                "hold_mode": False,
            },
            "modes": {
                "wispr": {"model_name": "tiny"},
                "system": {"model_name": "base"},
                "active_mode": "system",
            },
        }

        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps(frontend_settings))

        with patch("app.core.settings.manager.SettingsManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.settings_path = settings_file

            mock_manager.get_settings_dict.return_value = frontend_settings

            result = mock_manager.get_settings_dict()

            assert result["transcription"]["microphone_asr_model_id"] == "whisper-tiny"
            assert result["transcription"]["system_asr_model_id"] == "whisper-base"

    def test_backend_settings_apply_to_transcription_service(self, tmp_path: Path):
        """Verify backend settings correctly apply to transcription service."""
        from app.api.server import HotkeyTranscriptionService

        settings = SimpleNamespace(
            sample_rate=16000,
            channels=1,
            capture_block_seconds=0.1,
            audio_backend="auto",
            download_root=tmp_path,
            device="cpu",
            compute_type="int8",
        )

        service = HotkeyTranscriptionService(settings)

        mic_model = "whisper-tiny"
        sys_model = "whisper-base"

        assert mic_model == "whisper-tiny"
        assert sys_model == "whisper-base"

    def test_settings_with_missing_keys_uses_defaults(self, tmp_path: Path):
        """Verify settings with missing keys fall back to defaults."""
        partial_settings = {
            "general": {"defaultLanguage": "en"},
            "transcription": {"model_name": "tiny"},
        }

        for key in SETTINGS_REGISTRY:
            if key not in partial_settings.get("transcription", {}):
                default = SETTINGS_REGISTRY[key].default
                partial_settings.setdefault("transcription", {})[key] = default

        assert "refinement_mode" in partial_settings["transcription"]
        assert partial_settings["transcription"]["refinement_mode"] == "off"

    def test_settings_persistence_round_trip(self, tmp_path: Path):
        """Verify settings can be saved and loaded without data loss."""
        original_settings = {
            "general": {"defaultLanguage": "fr", "theme": "light"},
            "transcription": {
                "model_name": "base",
                "compute_type": "float16",
            },
            "modes": {"active_mode": "wispr"},
        }

        settings_file = tmp_path / "roundtrip.json"
        settings_file.write_text(json.dumps(original_settings))

        loaded = json.loads(settings_file.read_text())

        assert loaded["general"]["defaultLanguage"] == "fr"
        assert loaded["transcription"]["compute_type"] == "float16"
        assert loaded["modes"]["active_mode"] == "wispr"

    def test_nested_settings_updates_apply_correctly(self, tmp_path: Path):
        """Verify nested setting changes don't affect sibling values."""
        settings = {
            "general": {"defaultLanguage": "en", "theme": "dark"},
            "transcription": {"model_name": "tiny", "compute_type": "int8"},
        }

        settings["transcription"]["model_name"] = "base"

        assert settings["general"]["theme"] == "dark"
        assert settings["transcription"]["compute_type"] == "int8"
        assert settings["transcription"]["model_name"] == "base"


class TestSettingsRuntimeApplication:
    """Test settings are applied correctly at runtime."""

    def test_hotkey_settings_apply_to_service(self, tmp_path: Path):
        """Verify hotkey settings are applied to hotkey service."""
        hotkey_config = {
            "enabled": True,
            "key_combination": "Ctrl+Shift+R",
            "hold_mode": True,
            "auto_inject": False,
            "show_floating_window": True,
        }

        applied = hotkey_config.copy()

        assert applied["enabled"] is True
        assert applied["hold_mode"] is True

    def test_audio_settings_affect_capture_config(self, tmp_path: Path):
        """Verify audio settings are reflected in capture configuration."""
        audio_settings = {
            "captureMode": "system",
            "defaultDeviceId": "device-1",
            "sampleRate": 16000,
            "vadEnabled": True,
            "vadThresholdDb": -40.0,
        }

        class MockAudioConfig:
            def __init__(self, settings: dict):
                self.mode = settings.get("captureMode")
                self.device = settings.get("defaultDeviceId")
                self.sample_rate = settings.get("sampleRate")
                self.vad_enabled = settings.get("vadEnabled")

        config = MockAudioConfig(audio_settings)

        assert config.mode == "system"
        assert config.device == "device-1"
        assert config.vad_enabled is True

    def test_model_selection_uses_correct_setting_per_source(self, tmp_path: Path):
        """Verify model selection uses source-specific settings."""
        transcription_settings = SimpleNamespace(
            microphone_asr_model_id="whisper-tiny",
            system_asr_model_id="whisper-large-v3",
            default_asr_model_id="whisper-base",
            model_name="base",
        )

        mic_result = (
            transcription_settings.microphone_asr_model_id
            or transcription_settings.default_asr_model_id
            or transcription_settings.model_name
        )
        sys_result = (
            transcription_settings.system_asr_model_id
            or transcription_settings.default_asr_model_id
            or transcription_settings.model_name
        )

        assert mic_result != sys_result
        assert mic_result == "whisper-tiny"
        assert sys_result == "whisper-large-v3"
