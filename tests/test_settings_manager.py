from __future__ import annotations

import json

from app.core.settings_manager import SettingsManager


def test_settings_manager_applies_new_hotkey_defaults_when_fields_are_missing(tmp_path):
    settings_path = tmp_path / "user_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "general": {},
                "transcription": {},
                "audio": {},
                "hotkey": {
                    "enabled": True,
                    "key_combination": "Ctrl+Shift+T",
                },
                "advanced": {},
                "version": 1,
            }
        ),
        encoding="utf-8",
    )

    manager = SettingsManager(settings_dir=tmp_path)
    settings = manager.get_settings()

    assert settings.hotkey.enabled is True
    assert settings.hotkey.language == "auto"
    assert settings.hotkey.device_id == "default"
    assert settings.hotkey.finish_mode_default == "finish_and_paste"
    assert settings.hotkey.enable_refiner_on_stop is False
    assert settings.hotkey.save_debug_wav is False
    assert settings.hotkey.record_on_start is False
    assert settings.transcription.transcription_mode == "dictation"
    assert settings.transcription.refinement_profile == "raw"


def test_settings_manager_import_keeps_capture_mode_and_backend(tmp_path):
    manager = SettingsManager(settings_dir=tmp_path)

    success = manager.import_settings(
        {
            "general": {},
            "transcription": {},
            "audio": {
                "captureMode": "microphone",
                "backend": "pyaudio",
            },
            "hotkey": {
                "language": "en",
                "device_id": "mic-123",
                "finish_mode_default": "finish",
            },
            "advanced": {},
            "version": 2,
        }
    )

    settings = manager.get_settings()

    assert success is True
    assert settings.audio.captureMode == "microphone"
    assert settings.audio.backend == "pyaudio"
    assert settings.hotkey.language == "en"
    assert settings.hotkey.device_id == "mic-123"
    assert settings.hotkey.finish_mode_default == "finish"


def test_settings_manager_persists_model_selections_and_refinement_mode(tmp_path):
    manager = SettingsManager(settings_dir=tmp_path)

    success = manager.import_settings(
        {
            "general": {},
            "transcription": {
                "default_asr_model_id": "whisper-large-v3",
                "refinement_mode": "strict",
            },
            "refiner": {
                "selected_model_id": "phi-3-mini-4k-instruct",
                "runtime_enabled": False,
                "engine_preference": "llamacpp",
            },
            "audio": {},
            "hotkey": {},
            "advanced": {},
            "version": 3,
        }
    )

    assert success is True

    reloaded_manager = SettingsManager(settings_dir=tmp_path)
    settings = reloaded_manager.get_settings()

    assert settings.transcription.default_asr_model_id == "whisper-large-v3"
    assert settings.transcription.refinement_mode == "strict"
    assert settings.transcription.refinement_profile == "raw"
    assert settings.refiner.selected_model_id == "phi-3-mini-4k-instruct"
    assert settings.refiner.engine_preference == "llamacpp"


def test_settings_manager_migrates_legacy_hotkey_model_name_into_source_specific_asr_fields(tmp_path):
    settings_path = tmp_path / "user_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "general": {},
                "transcription": {
                    "default_asr_model_id": "whisper-large-v3",
                },
                "audio": {
                    "captureMode": "system",
                },
                "hotkey": {
                    "model_name": "small",
                },
                "advanced": {},
                "version": 4,
            }
        ),
        encoding="utf-8",
    )

    manager = SettingsManager(settings_dir=tmp_path)
    settings = manager.get_settings()

    assert settings.audio.captureMode == "system"
    assert settings.audio.default_capture_source == "system"
    assert settings.transcription.microphone_asr_model_id == "whisper-small"
    assert settings.transcription.system_asr_model_id == "whisper-large-v3"


def test_settings_manager_import_persists_source_specific_asr_models_and_default_capture_source(tmp_path):
    manager = SettingsManager(settings_dir=tmp_path)

    success = manager.import_settings(
        {
            "general": {},
            "transcription": {
                "default_asr_model_id": "whisper-medium",
                "microphone_asr_model_id": "whisper-small",
                "system_asr_model_id": "whisper-large-v3",
            },
            "audio": {
                "default_capture_source": "microphone",
            },
            "hotkey": {},
            "advanced": {},
            "version": 4,
        }
    )

    assert success is True

    reloaded_manager = SettingsManager(settings_dir=tmp_path)
    settings = reloaded_manager.get_settings()

    assert settings.audio.captureMode == "microphone"
    assert settings.audio.default_capture_source == "microphone"
    assert settings.transcription.microphone_asr_model_id == "whisper-small"
    assert settings.transcription.system_asr_model_id == "whisper-large-v3"
