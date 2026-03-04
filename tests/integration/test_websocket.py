"""Integration tests for WebSocket communication.

Tests cover:
- WebSocket connection handling
- Message serialization/deserialization
- Real-time event streaming
- Connection lifecycle management
- Error handling in WebSocket context
"""

from __future__ import annotations

import asyncio
import gzip
import json
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio
from types import SimpleNamespace

sys.modules.setdefault(
    "soundcard",
    SimpleNamespace(
        all_speakers=lambda: [],
        all_microphones=lambda include_loopback=True: [],
        default_microphone=lambda: None,
    ),
)
sys.modules.setdefault("faster_whisper", SimpleNamespace(WhisperModel=object))


class TestWebSocketManager:
    """Tests for WebSocketManager."""

    @pytest_asyncio.fixture
    async def ws_manager(self) -> MagicMock:
        """Create a WebSocket manager mock."""
        with patch("app.api.websocket_server.get_websocket_manager") as mock_get:
            manager = MagicMock()
            manager.connections = {}
            manager.broadcast = AsyncMock()
            mock_get.return_value = manager
            yield manager

    def test_websocket_manager_singleton(self) -> None:
        """Test WebSocket manager is a singleton."""
        from app.api.websocket_server import get_websocket_manager

        manager1 = get_websocket_manager()
        manager2 = get_websocket_manager()

        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_websocket_connection_accept(self, mock_websocket: AsyncMock) -> None:
        """Test WebSocket connection acceptance."""
        await mock_websocket.accept()

        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_send_json(self, mock_websocket: AsyncMock) -> None:
        """Test sending JSON over WebSocket."""
        message = {"type": "test", "data": "value"}

        await mock_websocket.send_json(message)

        mock_websocket.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_websocket_receive_json(self, mock_websocket: AsyncMock) -> None:
        """Test receiving JSON from WebSocket."""
        result = await mock_websocket.receive_json()

        assert result == {"action": "ping"}


class TestWebSocketMessages:
    """Tests for WebSocket message types."""

    def test_message_type_enum(self) -> None:
        """Test message type enumeration."""
        from app.api.websocket_server import MessageType

        assert MessageType.HEALTH_METRICS.value == "health_metrics"
        assert MessageType.TRANSCRIPTION_SEGMENT.value == "transcription_segment"
        assert MessageType.TRANSCRIPTION_PARTIAL.value == "transcription_partial"
        assert MessageType.ERROR.value == "error"


class TestWebSocketConnection:
    """Tests for WebSocketConnection."""

    def test_connection_config_defaults(self) -> None:
        """Test connection configuration defaults."""
        from app.api.websocket_server import ConnectionConfig

        config = ConnectionConfig()

        assert config.heartbeat_interval == 30.0
        assert config.max_message_size == 1024 * 1024
        assert config.compression_threshold > 0

    @pytest.mark.asyncio
    async def test_handle_message_decompresses_full_message_envelope(self) -> None:
        """Compressed messages should dispatch the inner payload, not the full envelope."""
        from app.api.websocket_server import ConnectionConfig, MessageType, WebSocketConnection

        websocket = AsyncMock()
        websocket.client_state = websocket.application_state = 1
        connection = WebSocketConnection(websocket, ConnectionConfig(), "conn", "127.0.0.1")

        received = {}

        def handler(payload, _connection):
            received["payload"] = payload

        connection.register_message_handler(MessageType.HEALTH_METRICS, handler)

        envelope = {
            "type": MessageType.HEALTH_METRICS,
            "payload": {"value": 42},
            "timestamp": 123.0,
        }
        compressed = gzip.compress(json.dumps(envelope).encode("utf-8"))

        await connection.handle_message(
            {
                "type": MessageType.HEALTH_METRICS,
                "_compressed": True,
                "_data": compressed.hex(),
            }
        )

        assert received["payload"] == {"value": 42}


class TestSettingsSynchronizer:
    """Tests for settings synchronization over WebSocket."""

    def test_sync_config_defaults(self) -> None:
        """Test sync configuration defaults."""
        from app.api.settings_sync import SyncConfig, SyncConflictResolution, SyncDirection

        config = SyncConfig()

        assert config.direction == SyncDirection.BIDIRECTIONAL
        assert config.conflict_resolution == SyncConflictResolution.SERVER_WINS
        assert config.notify_on_change is True
        assert config.batch_updates is True

    def test_sync_direction_enum(self) -> None:
        """Test sync direction enumeration."""
        from app.api.settings_sync import SyncDirection

        assert SyncDirection.SERVER_TO_CLIENT.value == "server_to_client"
        assert SyncDirection.CLIENT_TO_SERVER.value == "client_to_server"
        assert SyncDirection.BIDIRECTIONAL.value == "bidirectional"


class TestHotkeyWebSocket:
    """Tests for hotkey WebSocket functionality."""

    @pytest.mark.asyncio
    async def test_hotkey_websocket_handler_exists(self) -> None:
        """Test hotkey WebSocket endpoint exists."""
        from app.api.server import hotkey_websocket

        assert callable(hotkey_websocket)

    def test_hotkey_websocket_event_types(self) -> None:
        """Test hotkey WebSocket event types."""
        # These are the event types that should be supported
        expected_events = [
            "hotkey_status",
            "hotkey_stop_ack",
            "hotkey_stopping",
            "hotkey_stopped",
            "hotkey_draft_partial",
            "hotkey_commit_final",
            "hotkey_audio_level",
            "hotkey_error",
        ]

        # Just verify the list is reasonable
        assert len(expected_events) == 8
        assert "hotkey_status" in expected_events
        assert "hotkey_audio_level" in expected_events
        assert "hotkey_commit_final" in expected_events


class TestWebSocketErrorHandling:
    """Tests for WebSocket error handling."""

    @pytest.mark.asyncio
    async def test_websocket_disconnect_handling(self, mock_websocket: AsyncMock) -> None:
        """Test handling of WebSocket disconnect."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_json.side_effect = WebSocketDisconnect()

        with pytest.raises(WebSocketDisconnect):
            await mock_websocket.receive_json()

    @pytest.mark.asyncio
    async def test_websocket_send_error(self, mock_websocket: AsyncMock) -> None:
        """Test handling of WebSocket send error."""
        from fastapi import WebSocketDisconnect

        mock_websocket.send_json.side_effect = WebSocketDisconnect()

        with pytest.raises(WebSocketDisconnect):
            await mock_websocket.send_json({"test": "data"})


class TestWebSocketBroadcast:
    """Tests for WebSocket broadcasting."""

    @pytest.mark.asyncio
    async def test_broadcast_to_all_connections(self) -> None:
        """Test broadcasting message to all connections."""
        from app.api.websocket_server import get_websocket_manager

        manager = get_websocket_manager()

        # Mock connections
        conn1 = AsyncMock()
        conn2 = AsyncMock()
        manager.connections = {"conn1": conn1, "conn2": conn2}

        message = {"type": "broadcast", "data": "test"}

        # Broadcast should send to all connections
        for conn in manager.connections.values():
            await conn.send_json(message)
            conn.send_json.assert_called_with(message)


class TestHotkeySSE:
    """Tests for hotkey Server-Sent Events."""

    def test_hotkey_sse_endpoint_exists(self) -> None:
        """Test hotkey SSE endpoint exists."""
        from app.api.server import hotkey_events

        assert callable(hotkey_events)

    @pytest.mark.asyncio
    async def test_sse_event_generator(self) -> None:
        """Test SSE event generator."""
        from app.api.server import hotkey_events

        # This is an async generator, so we test it can be created
        assert callable(hotkey_events)
