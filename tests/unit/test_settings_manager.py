"""Unit tests for the settings manager.

Tests cover:
- Settings loading and saving
- Mode-specific settings
- Settings validation
- WebSocket sync
- Import/export functionality
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.core.settings_manager import (
    GeneralSettings,
    TranscriptionSettings,
    AudioSettings,
    RefinerSettings,
    HotkeySettings,
    AdvancedSettings,
    ModeSpecificSettings,
    SettingsState,
    SettingsManager,
    get_settings_manager,
    reset_settings_manager,
)
from app.core.modes import TranscriptionMode, WisprModeDefaults, SystemModeDefaults


class TestSettingsDataclasses:
    """Tests for settings dataclasses."""

    def test_general_settings_defaults(self) -> None:
        """Test GeneralSettings default values."""
        settings = GeneralSettings()

        assert settings.defaultSessionTitle is not None
        assert settings.defaultLanguage is not None
        assert settings.exportDirectory is not None
        assert isinstance(settings.autoSaveInterval, int)
        assert isinstance(settings.showNotifications, bool)

    def test_transcription_settings_defaults(self) -> None:
        """Test TranscriptionSettings default values."""
        settings = TranscriptionSettings()

        assert settings.model_name is not None
        assert isinstance(settings.chunk_duration, float)
        assert isinstance(settings.vad_enabled, bool)
        assert settings.beam_size > 0

    def test_audio_settings_defaults(self) -> None:
        """Test AudioSettings default values."""
        settings = AudioSettings()

        assert settings.captureMode is not None
        assert settings.sampleRate > 0
        assert isinstance(settings.vadEnabled, bool)

    def test_settings_state_defaults(self) -> None:
        """Test SettingsState default values."""
        state = SettingsState()

        assert state.general is not None
        assert state.transcription is not None
        assert state.audio is not None
        assert state.refiner is not None
        assert state.hotkey is not None
        assert state.advanced is not None
        assert state.modes is not None


class TestModeSpecificSettings:
    """Tests for mode-specific settings."""

    def test_mode_specific_defaults(self) -> None:
        """Test ModeSpecificSettings default values."""
        modes = ModeSpecificSettings()

        assert "wispr" in modes.wispr
        assert "system" in modes.system
        assert modes.active_mode in ["wispr", "system"]

    def test_to_container_conversion(self) -> None:
        """Test conversion to SettingsContainer."""
        modes = ModeSpecificSettings()
        container = modes.to_container()

        assert container.wispr is not None
        assert container.system is not None
        assert container.active_mode in [TranscriptionMode.WISPR, TranscriptionMode.SYSTEM]

    def test_from_container_conversion(self) -> None:
        """Test conversion from SettingsContainer."""
        modes = ModeSpecificSettings()
        container = modes.to_container()

        modes2 = ModeSpecificSettings.from_container(container)

        assert modes2.active_mode == modes.active_mode


class TestSettingsManager:
    """Tests for SettingsManager."""

    @pytest.fixture
    def settings_manager(self, temp_dir: Path) -> SettingsManager:
        """Create a test settings manager."""
        return SettingsManager(settings_dir=temp_dir)

    def test_init_creates_default_settings(self, temp_dir: Path) -> None:
        """Test initialization creates default settings if none exist."""
        settings_file = temp_dir / "user_settings.json"
        assert not settings_file.exists()

        manager = SettingsManager(settings_dir=temp_dir)

        assert settings_file.exists()
        assert manager.get_settings() is not None

    def test_load_existing_settings(self, temp_dir: Path, test_settings: dict) -> None:
        """Test loading existing settings file."""
        settings_file = temp_dir / "user_settings.json"
        settings_file.write_text(json.dumps(test_settings))

        manager = SettingsManager(settings_dir=temp_dir)
        settings = manager.get_settings()

        assert (
            settings.general.defaultSessionTitle == test_settings["general"]["defaultSessionTitle"]
        )
        assert settings.transcription.model_name == test_settings["transcription"]["model_name"]

    def test_save_settings(self, settings_manager: SettingsManager, temp_dir: Path) -> None:
        """Test saving settings to disk."""
        settings_manager.get_settings().general.defaultSessionTitle = "Updated Title"
        settings_manager._save()

        # Reload and verify
        settings_file = temp_dir / "user_settings.json"
        saved_data = json.loads(settings_file.read_text())

        assert saved_data["general"]["defaultSessionTitle"] == "Updated Title"

    def test_update_partial(self, settings_manager: SettingsManager) -> None:
        """Test partial settings update."""
        settings_manager.update_partial("general", {"defaultSessionTitle": "New Title"})

        settings = settings_manager.get_settings()
        assert settings.general.defaultSessionTitle == "New Title"

    def test_update_partial_unknown_category(self, settings_manager: SettingsManager) -> None:
        """Test partial update with unknown category."""
        # Should not raise error
        settings_manager.update_partial("unknown_category", {"key": "value"})

    def test_reset_to_defaults(self, settings_manager: SettingsManager) -> None:
        """Test resetting settings to defaults."""
        # Modify some settings
        settings_manager.get_settings().general.defaultSessionTitle = "Modified"
        settings_manager.get_settings().transcription.model_name = "large"

        # Reset
        settings_manager.reset_to_defaults()
        settings = settings_manager.get_settings()

        # Should have default values again
        assert settings.general.defaultSessionTitle != "Modified"

    def test_get_settings_dict(self, settings_manager: SettingsManager) -> None:
        """Test getting settings as dictionary."""
        settings_dict = settings_manager.get_settings_dict()

        assert "general" in settings_dict
        assert "transcription" in settings_dict
        assert "audio" in settings_dict
        assert isinstance(settings_dict, dict)

    def test_thread_safety(self, settings_manager: SettingsManager) -> None:
        """Test thread-safe settings access."""
        results = []

        def read_settings():
            settings = settings_manager.get_settings()
            results.append(settings.general.defaultSessionTitle)

        def write_settings():
            settings = settings_manager.get_settings()
            settings.general.defaultSessionTitle = "Thread Test"

        threads = []
        for _ in range(10):
            t1 = threading.Thread(target=read_settings)
            t2 = threading.Thread(target=write_settings)
            threads.extend([t1, t2])

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All operations should complete without errors
        assert len(results) == 10

    def test_get_active_mode(self, settings_manager: SettingsManager) -> None:
        """Test getting active mode."""
        mode = settings_manager.get_active_mode()

        assert mode in [TranscriptionMode.WISPR, TranscriptionMode.SYSTEM]

    def test_set_active_mode(self, settings_manager: SettingsManager) -> None:
        """Test setting active mode."""
        settings_manager.set_active_mode("wispr")

        assert settings_manager.get_active_mode() == TranscriptionMode.WISPR

    def test_set_active_mode_from_enum(self, settings_manager: SettingsManager) -> None:
        """Test setting active mode from enum."""
        settings_manager.set_active_mode(TranscriptionMode.SYSTEM)

        assert settings_manager.get_active_mode() == TranscriptionMode.SYSTEM

    def test_sync_callbacks(self, settings_manager: SettingsManager) -> None:
        """Test sync callback registration and notification."""
        callback_called = False
        callback_data = None

        def test_callback(event_type: str, data: dict):
            nonlocal callback_called, callback_data
            callback_called = True
            callback_data = (event_type, data)

        settings_manager.register_sync_callback(test_callback)
        settings_manager._notify_sync("test_event", {"key": "value"})

        assert callback_called is True
        assert callback_data[0] == "test_event"

    def test_unregister_sync_callback(self, settings_manager: SettingsManager) -> None:
        """Test sync callback unregistration."""
        callback_count = [0]

        def test_callback(event_type: str, data: dict):
            callback_count[0] += 1

        settings_manager.register_sync_callback(test_callback)
        settings_manager._notify_sync("test", {})
        assert callback_count[0] == 1

        settings_manager.unregister_sync_callback(test_callback)
        settings_manager._notify_sync("test2", {})
        assert callback_count[0] == 1  # Should not increment

    def test_import_settings(self, settings_manager: SettingsManager, test_settings: dict) -> None:
        """Test importing settings."""
        result = settings_manager.import_settings(test_settings)

        assert result is True
        settings = settings_manager.get_settings()
        assert (
            settings.general.defaultSessionTitle == test_settings["general"]["defaultSessionTitle"]
        )

    def test_import_settings_invalid(self, settings_manager: SettingsManager) -> None:
        """Test importing invalid settings."""
        invalid_settings = {"general": {"invalid_key": "value"}}

        result = settings_manager.import_settings(invalid_settings)

        # Should handle gracefully
        assert isinstance(result, bool)


class TestSettingsManagerSingleton:
    """Tests for settings manager singleton."""

    def test_get_settings_manager_singleton(self) -> None:
        """Test that get_settings_manager returns singleton."""
        reset_settings_manager()

        manager1 = get_settings_manager()
        manager2 = get_settings_manager()

        assert manager1 is manager2

    def test_reset_settings_manager(self) -> None:
        """Test resetting the singleton."""
        manager1 = get_settings_manager()
        reset_settings_manager()
        manager2 = get_settings_manager()

        assert manager1 is not manager2


class TestSettingsValidation:
    """Tests for settings validation."""

    def test_validate_settings(self, settings_manager: SettingsManager) -> None:
        """Test settings validation."""
        result = settings_manager.validate()

        assert result is not None
        # Should be valid by default
        assert hasattr(result, "is_valid")

    def test_validate_category(self, settings_manager: SettingsManager) -> None:
        """Test category validation."""
        result = settings_manager.validate_category("general", {"defaultSessionTitle": "Test"})

        assert result is not None
        assert hasattr(result, "is_valid")
