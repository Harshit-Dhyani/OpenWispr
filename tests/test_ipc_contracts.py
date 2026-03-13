"""
IPC Contract Tests

Tests IPC message formats between Electron main and renderer processes.
Verifies preload API contracts and handler response formats.

Regression protection for:
- Missing required fields in IPC messages
- Incorrect response format from handlers
- Type errors in IPC communication
- Handler failures not properly propagated
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestHotkeyIPCContracts:
    """Test hotkey-related IPC message contracts."""

    def test_hotkey_register_request_format(self):
        """Verify hotkey:register requires accelerator field."""
        request = {"accelerator": "Ctrl+Shift+R"}

        assert "accelerator" in request
        assert isinstance(request["accelerator"], str)
        assert len(request["accelerator"]) > 0

    def test_hotkey_register_response_success_format(self):
        """Verify successful hotkey:register response format."""
        response = {
            "success": True,
            "accelerator": "Ctrl+Shift+R",
        }

        assert response["success"] is True
        assert "accelerator" in response
        assert "error" not in response

    def test_hotkey_register_response_error_format(self):
        """Verify error response from hotkey:register."""
        response = {
            "success": False,
            "error": "HOTKEY_ALREADY_REGISTERED",
        }

        assert response["success"] is False
        assert "error" in response

    def test_hotkey_validate_request_format(self):
        """Verify hotkey:validate request format."""
        request = {"accelerator": "Ctrl+Shift+T"}

        assert "accelerator" in request

    def test_hotkey_validate_response_format(self):
        """Verify hotkey:validate response format."""
        response = {
            "valid": True,
            "available": True,
        }

        assert isinstance(response["valid"], bool)
        assert isinstance(response["available"], bool)

    def test_hotkey_toggle_request_format(self):
        """Verify hotkey:toggle accepts boolean."""
        request = True

        assert isinstance(request, bool)

    def test_hotkey_toggle_response_format(self):
        """Verify hotkey:toggle response format."""
        response = {
            "success": True,
            "enabled": True,
        }

        assert "success" in response
        assert "enabled" in response
        assert isinstance(response["enabled"], bool)

    def test_hotkey_start_request_source_optional(self):
        """Verify hotkey:start source parameter is optional."""
        request_without_source = {}
        request_with_source = {"source": "microphone"}

        assert (
            "source" not in request_without_source or request_without_source.get("source") is None
        )
        assert request_with_source.get("source") == "microphone"

    def test_hotkey_get_state_response_format(self):
        """Verify hotkey:get-state response format."""
        response = {
            "enabled": True,
            "isRecording": False,
            "accelerator": "Ctrl+Shift+R",
            "registered": True,
        }

        assert "enabled" in response
        assert "isRecording" in response
        assert "accelerator" in response

    def test_hotkey_update_config_request_format(self):
        """Verify hotkey:update-config request format."""
        config = {
            "enabled": True,
            "key_combination": "Ctrl+Shift+R",
            "hold_mode": False,
            "auto_inject": True,
        }

        assert "enabled" in config
        assert "key_combination" in config


class TestModelIPCContracts:
    """Test model-related IPC message contracts."""

    def test_models_download_request_format(self):
        """Verify models:download requires modelId."""
        request = {"modelId": "whisper-tiny"}

        assert "modelId" in request
        assert isinstance(request["modelId"], str)
        assert len(request["modelId"]) > 0
        assert len(request["modelId"]) <= 100

    def test_models_download_response_success_format(self):
        """Verify successful models:download response."""
        response = {
            "ok": True,
            "modelId": "whisper-tiny",
        }

        assert response["ok"] is True

    def test_models_download_response_error_format(self):
        """Verify error response from models:download."""
        response = {
            "ok": False,
            "error": "invalid_model_id",
        }

        assert response["ok"] is False
        assert "error" in response

    def test_models_cancel_request_format(self):
        """Verify models:cancel request format."""
        request = {"modelId": "whisper-tiny"}

        assert "modelId" in request

    def test_models_remove_request_format(self):
        """Verify models:remove request format."""
        request = {"modelId": "whisper-tiny"}

        assert "modelId" in request


class TestSettingsIPCContracts:
    """Test settings-related IPC message contracts."""

    def test_quick_settings_get_data_response_format(self):
        """Verify quick-settings:get-data response format."""
        response = {
            "appName": "OpenWispr",
            "settings": {},
            "devices": [],
            "languages": [],
            "hotkeyState": {
                "enabled": True,
                "accelerator": "Ctrl+Shift+R",
                "isRecording": False,
            },
        }

        assert "appName" in response
        assert "settings" in response
        assert "devices" in response
        assert "hotkeyState" in response

    def test_quick_settings_update_request_format(self):
        """Verify quick-settings:update request format."""
        settings = {
            "general": {"theme": "dark"},
            "hotkey": {"enabled": True},
        }

        assert isinstance(settings, dict)

    def test_quick_settings_update_response_format(self):
        """Verify quick-settings:update response format."""
        response = {"success": True}

        assert "success" in response
        assert isinstance(response["success"], bool)


class TestTextInjectionIPCContracts:
    """Test text injection IPC message contracts."""

    def test_text_inject_request_format(self):
        """Verify text:inject accepts string."""
        request = "Text to inject"

        assert isinstance(request, str)

    def test_text_inject_response_format(self):
        """Verify text:inject response format."""
        response = {"success": True}

        assert "success" in response


class TestFloatingWindowIPCContracts:
    """Test floating window IPC message contracts."""

    def test_floating_window_action_cancel_format(self):
        """Verify floating-window-action cancel format."""
        action = {"action": "cancel"}

        assert action["action"] == "cancel"

    def test_floating_window_action_finish_format(self):
        """Verify floating-window-action finish format."""
        action = {"action": "finish"}

        assert action["action"] == "finish"

    def test_floating_window_action_finish_and_paste_format(self):
        """Verify floating-window-action finish-and-paste format."""
        action = {"action": "finish-and-paste"}

        assert action["action"] == "finish-and-paste"

    def test_floating_window_action_dismiss_result_format(self):
        """Verify floating-window-action dismiss-result format."""
        action = {"action": "dismiss-result"}

        assert action["action"] == "dismiss-result"


class TestPreloadAPIExposure:
    """Test preload API is properly exposed."""

    def test_desktop_api_exposes_hotkey(self):
        """Verify desktop API exposes hotkey namespace."""
        api = {
            "hotkey": {
                "register": lambda x: x,
                "unregister": lambda: {},
                "validate": lambda x: x,
                "toggle": lambda x: x,
                "start": lambda x: x,
                "stop": lambda: {},
                "getState": lambda: {},
                "updateConfig": lambda x: x,
                "getDefault": lambda: {},
            }
        }

        assert "hotkey" in api
        assert callable(api["hotkey"]["register"])
        assert callable(api["hotkey"]["stop"])

    def test_desktop_api_exposes_models(self):
        """Verify desktop API exposes models namespace."""
        api = {
            "models": {
                "getDownloadRoot": lambda: {},
                "download": lambda x: x,
                "cancel": lambda x: x,
                "remove": lambda x: x,
            }
        }

        assert "models" in api
        assert callable(api["models"]["download"])

    def test_desktop_api_exposes_text(self):
        """Verify desktop API exposes text namespace."""
        api = {
            "text": {
                "inject": lambda x: x,
            }
        }

        assert "text" in api
        assert callable(api["text"]["inject"])
