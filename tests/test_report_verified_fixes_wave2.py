from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from starlette.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState

sys.modules.setdefault(
    "soundcard",
    SimpleNamespace(
        all_speakers=lambda: [],
        all_microphones=lambda include_loopback=True: [],
        default_microphone=lambda: None,
    ),
)
sys.modules.setdefault("faster_whisper", SimpleNamespace(WhisperModel=object))

import app.core.settings.manager as legacy_settings_manager

if not hasattr(legacy_settings_manager, "_settings_manager"):
    legacy_settings_manager._settings_manager = None


class DummyWebSocket:
    client_state = WebSocketState.CONNECTED
    application_state = WebSocketState.CONNECTED

    def __init__(self) -> None:
        self.scope = {"headers": []}


@pytest.fixture
def websocket_connection_cls():
    from app.api.websocket_server import WebSocketConnection

    return WebSocketConnection


def test_api_cors_disables_credentials_with_wildcard_origin() -> None:
    from app.api.server import app

    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)

    assert cors.kwargs["allow_origins"] == ["*"]
    assert cors.kwargs["allow_credentials"] is False


def test_websocket_local_loopback_client_can_auth_without_token(websocket_connection_cls) -> None:
    from app.api.websocket_server import ConnectionConfig

    connection = websocket_connection_cls(
        DummyWebSocket(), ConnectionConfig(auth_required=False), "conn", "127.0.0.1"
    )

    assert asyncio.run(connection.authenticate()) is True
    assert connection.is_authenticated is True


def test_websocket_non_local_client_is_rejected_without_auth(websocket_connection_cls) -> None:
    from app.api.websocket_server import ConnectionConfig

    connection = websocket_connection_cls(
        DummyWebSocket(), ConnectionConfig(auth_required=False), "conn", "10.0.0.5"
    )

    assert asyncio.run(connection.authenticate()) is False
    assert connection.is_authenticated is False


def test_websocket_auth_required_uses_env_token(
    monkeypatch: pytest.MonkeyPatch, websocket_connection_cls
) -> None:
    from app.api.websocket_server import ConnectionConfig

    monkeypatch.setenv("OPENWISPR_WS_TOKEN", "secret-token")
    connection = websocket_connection_cls(
        DummyWebSocket(), ConnectionConfig(auth_required=True), "conn", "10.0.0.5"
    )

    assert asyncio.run(connection.authenticate("secret-token")) is True
    assert asyncio.run(connection.authenticate("wrong-token")) is False


def test_model_catalog_mapping_uses_base_catalog_id() -> None:
    from app.config.constants import ModelConstants

    assert ModelConstants.MODEL_CATALOG_MAPPING["base"] == "whisper-base"


def test_system_profile_recommended_quality_uses_supported_labels() -> None:
    from app.core.profiling.system_profiler import (
        CPUProfile,
        GPUProfile,
        StorageProfile,
        SystemProfile,
    )

    supported = {"maximum", "balanced", "fast", "low_memory"}

    high = SystemProfile(
        gpu=GPUProfile(True, "gpu", 10.0, (8, 0), True, 1),
        cpu=CPUProfile(8, 16, 32.0, "x64", True),
        storage=StorageProfile(100.0, 50.0, Path("."), True),
        os_name="Windows",
    )
    mid = SystemProfile(
        gpu=GPUProfile(True, "gpu", 4.0, (7, 5), True, 1),
        cpu=CPUProfile(8, 16, 16.0, "x64", True),
        storage=StorageProfile(100.0, 50.0, Path("."), True),
        os_name="Windows",
    )
    low = SystemProfile(
        gpu=GPUProfile(False, "gpu", 1.0, (0, 0), False, 0),
        cpu=CPUProfile(4, 8, 4.0, "x64", True),
        storage=StorageProfile(100.0, 50.0, Path("."), True),
        os_name="Windows",
    )

    assert high.recommended_quality_level in supported
    assert mid.recommended_quality_level in supported
    assert low.recommended_quality_level in supported
    assert low.recommended_quality_level == "low_memory"


def test_backend_setting_is_hidden_legacy_alias() -> None:
    from app.config.settings import get_setting

    backend = get_setting("backend")
    audio_backend = get_setting("audio_backend")

    assert backend.is_fake is True
    assert audio_backend.is_fake is False


def test_backend_service_snapshot_includes_ultra_live_mode() -> None:
    from app.api.services.backend_service import BackendService

    settings = MagicMock(download_root=Path("."))
    service = BackendService(settings)
    snapshot = service.get_snapshot()

    assert "ultra" in snapshot.available_live_modes
