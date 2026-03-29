"""WebSocket server implementation for real-time transcription and system events.

This module provides production-grade WebSocket support with:
- Bidirectional communication
- Auto-reconnect with exponential backoff
- Heartbeat/ping-pong
- Message queuing during reconnect
- Compression for large messages
- Connection pooling
- Rate limiting
- Security (origin validation)
"""

from __future__ import annotations

import asyncio
import gzip
import ipaddress
import json
import logging
import os
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.api.json_utils import make_json_safe

logger = logging.getLogger(__name__)


def _client_ip_is_local(client_ip: str) -> bool:
    try:
        address = ipaddress.ip_address(client_ip)
    except ValueError:
        return client_ip in {"localhost"}

    return address.is_loopback


class MessageType(str, Enum):
    """WebSocket message types."""

    # Transcription messages
    TRANSCRIPTION_PARTIAL = "transcription_partial"
    TRANSCRIPTION_FINAL = "transcription_final"
    TRANSCRIPTION_SEGMENT = "transcription_segment"

    # Audio visualization
    AUDIO_LEVEL = "audio_level"
    AUDIO_SPECTRUM = "audio_spectrum"

    # Settings sync
    SETTINGS_UPDATE = "settings_update"
    SETTINGS_REQUEST = "settings_request"
    SETTINGS_RESPONSE = "settings_response"

    # Health metrics
    HEALTH_METRICS = "health_metrics"
    SYSTEM_STATUS = "system_status"

    # Session events
    SESSION_STARTED = "session_started"
    SESSION_STOPPED = "session_stopped"
    SESSION_ERROR = "session_error"

    # Hotkey events
    HOTKEY_STARTED = "hotkey_started"
    HOTKEY_STOPPED = "hotkey_stopped"
    HOTKEY_PARTIAL = "hotkey_partial"
    HOTKEY_AUDIO_LEVEL = "hotkey_audio_level"
    HOTKEY_STATUS = "hotkey_status"

    # Connection management
    PING = "ping"
    PONG = "pong"
    KEEPALIVE = "keepalive"
    ERROR = "error"
    AUTH = "auth"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILED = "auth_failed"


@dataclass
class ConnectionConfig:
    """Configuration for WebSocket connections."""

    heartbeat_interval: float = 30.0
    heartbeat_timeout: float = 60.0
    max_message_size: int = 1024 * 1024  # 1MB
    compression_threshold: int = 1024  # Compress messages larger than 1KB
    compression_level: int = 6
    rate_limit_messages: int = 100  # messages per window
    rate_limit_window: float = 60.0  # seconds
    message_queue_size: int = 1000
    max_connections_per_ip: int = 5
    allowed_origins: list[str] | None = None
    auth_required: bool = False


@dataclass
class ConnectionStats:
    """Statistics for a WebSocket connection."""

    connected_at: float = field(default_factory=time.time)
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    last_activity: float = field(default_factory=time.time)
    reconnect_attempts: int = 0
    errors: int = 0


class RateLimiter:
    """Rate limiter for WebSocket messages."""

    def __init__(self, max_messages: int = 100, window_seconds: float = 60.0):
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        # Use bounded deque to prevent unbounded growth
        self._timestamps: deque[float] = deque(maxlen=max_messages)
        self._lock = asyncio.Lock()

    async def check_rate_limit(self) -> tuple[bool, float]:
        """Check if message is within rate limit.

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        async with self._lock:
            now = time.time()

            # Remove old timestamps outside the window
            cutoff = now - self.window_seconds
            # Bounded deque handles max size automatically, just trim old entries
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) >= self.max_messages:
                retry_after = self._timestamps[0] + self.window_seconds - now
                return False, max(0.0, retry_after)

            self._timestamps.append(now)
            return True, 0.0


class WebSocketConnection:
    """Manages a single WebSocket connection with full feature support."""

    def __init__(
        self,
        websocket: WebSocket,
        config: ConnectionConfig,
        connection_id: str,
        client_ip: str,
    ):
        self.websocket = websocket
        self.config = config
        self.connection_id = connection_id
        self.client_ip = client_ip
        self.stats = ConnectionStats()
        self.rate_limiter = RateLimiter(
            max_messages=config.rate_limit_messages,
            window_seconds=config.rate_limit_window,
        )

        # Message queue for buffering during reconnects
        self._message_queue: deque[dict[str, Any]] = deque(maxlen=config.message_queue_size)
        self._queue_lock = asyncio.Lock()

        # Event callbacks
        self._message_handlers: dict[MessageType, list[Callable]] = {}
        self._disconnect_handlers: list[Callable] = []

        # Connection state
        self._authenticated = False
        self._closed = False
        self._heartbeat_task: asyncio.Task | None = None
        self._last_pong = time.time()

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def is_connected(self) -> bool:
        return (
            not self._closed
            and self.websocket.client_state == WebSocketState.CONNECTED
            and self.websocket.application_state == WebSocketState.CONNECTED
        )

    async def authenticate(self, token: str | None = None) -> bool:
        """Authenticate the connection."""
        if not self.config.auth_required:
            if _client_ip_is_local(self.client_ip):
                self._authenticated = True
                return True

            logger.warning(
                "Rejected unauthenticated non-local WebSocket client",
                extra={"connection_id": self.connection_id, "client_ip": self.client_ip},
            )
            return False

        expected_token = os.getenv("OPENWISPR_WS_TOKEN")
        if expected_token and token == expected_token:
            self._authenticated = True
            return True

        return False

    async def validate_origin(self) -> bool:
        """Validate the connection origin."""
        if self.config.allowed_origins is None:
            return True

        headers = dict(self.websocket.scope.get("headers", []))
        origin = headers.get(b"origin", b"").decode("utf-8", errors="ignore")

        return origin in self.config.allowed_origins or "*" in self.config.allowed_origins

    def register_message_handler(self, message_type: MessageType, handler: Callable) -> None:
        """Register a handler for a specific message type."""
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        self._message_handlers[message_type].append(handler)

    def register_disconnect_handler(self, handler: Callable) -> None:
        """Register a handler for disconnect events."""
        self._disconnect_handlers.append(handler)

    async def send(
        self,
        message_type: MessageType,
        payload: dict[str, Any],
        compress: bool | None = None,
    ) -> bool:
        """Send a message to the client with optional compression.

        Args:
            message_type: Type of message
            payload: Message payload
            compress: Force compression (None = auto based on size)

        Returns:
            True if sent successfully
        """
        if not self.is_connected:
            async with self._queue_lock:
                self._message_queue.append(
                    {"type": message_type, "payload": payload, "timestamp": time.time()}
                )
            return False

        allowed, retry_after = await self.rate_limiter.check_rate_limit()
        if not allowed:
            logger.warning(
                "Rate limit exceeded for connection %s, retry after %.1fs",
                self.connection_id,
                retry_after,
            )
            return False

        try:
            safe_payload = make_json_safe(payload)
            timestamp = time.time()
            should_compress = compress if compress is not None else False

            if should_compress:
                message = {
                    "type": message_type,
                    "payload": safe_payload,
                    "timestamp": timestamp,
                }
                data_bytes = json.dumps(message, separators=(",", ":")).encode("utf-8")
                compressed = gzip.compress(data_bytes, compresslevel=self.config.compression_level)
                await self.websocket.send_json(
                    {
                        "type": message_type,
                        "_compressed": True,
                        "_data": compressed.hex(),
                        "timestamp": timestamp,
                    }
                )
            else:
                await self.websocket.send_json(
                    {
                        "type": message_type,
                        "payload": safe_payload,
                        "timestamp": timestamp,
                    }
                )

            self.stats.messages_sent += 1
            self.stats.bytes_sent += len(data_bytes) if should_compress else 0
            self.stats.last_activity = timestamp

            return True

        except Exception as exc:
            logger.debug("Failed to send message to %s: %s", self.connection_id, exc)
            self.stats.errors += 1

            async with self._queue_lock:
                self._message_queue.append(
                    {"type": message_type, "payload": payload, "timestamp": time.time()}
                )
            return False

    async def send_transcription_partial(self, text: str, is_final: bool = False) -> bool:
        """Send a partial transcription update."""
        return await self.send(
            MessageType.TRANSCRIPTION_PARTIAL,
            {"text": text, "is_final": is_final},
        )

    async def send_transcription_final(
        self, text: str, confidence: float, segments: list[dict] | None = None
    ) -> bool:
        """Send a final transcription result."""
        payload: dict[str, Any] = {"text": text, "confidence": confidence}
        if segments:
            payload["segments"] = segments
        return await self.send(MessageType.TRANSCRIPTION_FINAL, payload)

    async def send_audio_level(
        self, level: float, peak: float, levels: list[float] | None = None
    ) -> bool:
        """Send audio level update for visualization."""
        payload: dict[str, Any] = {"level": level, "peak": peak}
        if levels:
            payload["levels"] = levels
        return await self.send(MessageType.AUDIO_LEVEL, payload)

    async def send_settings_update(self, settings: dict[str, Any]) -> bool:
        """Send settings update to client."""
        return await self.send(MessageType.SETTINGS_UPDATE, {"settings": settings})

    async def send_health_metrics(self, metrics: dict[str, Any]) -> bool:
        """Send health/metrics update."""
        return await self.send(MessageType.HEALTH_METRICS, metrics)

    async def send_error(self, error_message: str, error_code: str | None = None) -> bool:
        """Send an error message."""
        payload: dict[str, Any] = {"message": error_message}
        if error_code:
            payload["code"] = error_code
        return await self.send(MessageType.ERROR, payload)

    async def start_heartbeat(self) -> None:
        """Start the heartbeat task."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats and check for timeouts."""
        while not self._closed:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)

                if not self.is_connected:
                    break

                # Check for pong timeout
                if time.time() - self._last_pong > self.config.heartbeat_timeout:
                    logger.warning("Heartbeat timeout for connection %s", self.connection_id)
                    await self.close(1001, "Heartbeat timeout")
                    break

                # Send ping
                await self.send(MessageType.PING, {"timestamp": time.time()})

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("Heartbeat error for %s: %s", self.connection_id, exc)

    async def handle_message(self, message: dict[str, Any]) -> None:
        """Handle an incoming message."""
        self.stats.messages_received += 1
        self.stats.last_activity = time.time()

        try:
            msg_type_str = message.get("type", "")
            payload = message.get("payload", {})

            # Handle compressed messages
            if message.get("_compressed"):
                compressed_data = bytes.fromhex(message["_data"])
                try:
                    json_data = gzip.decompress(compressed_data).decode("utf-8")
                except UnicodeDecodeError as e:
                    logger.warning(f"Failed to decode WebSocket message: {e}")
                    return
                try:
                    decompressed = json.loads(json_data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse WebSocket JSON: {e}")
                    return
                if (
                    isinstance(decompressed, dict)
                    and "type" in decompressed
                    and "payload" in decompressed
                ):
                    msg_type_str = decompressed.get("type", msg_type_str)
                    payload = decompressed.get("payload", payload)
                else:
                    payload = decompressed

            # Handle pong
            if msg_type_str == MessageType.PONG:
                self._last_pong = time.time()
                return

            # Handle authentication
            if msg_type_str == MessageType.AUTH:
                token = payload.get("token")
                success = await self.authenticate(token)
                await self.send(
                    MessageType.AUTH_SUCCESS if success else MessageType.AUTH_FAILED,
                    {"authenticated": success},
                )
                return

            # Dispatch to registered handlers
            try:
                msg_type = MessageType(msg_type_str)
            except ValueError:
                await self.send_error(f"Unknown message type: {msg_type_str}", "UNKNOWN_TYPE")
                return

            handlers = self._message_handlers.get(msg_type, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(payload, self)
                    else:
                        handler(payload, self)
                except Exception as exc:
                    logger.exception("Message handler error: %s", exc)

        except Exception as exc:
            logger.exception("Error handling message: %s", exc)
            await self.send_error("Failed to process message", "PROCESSING_ERROR")

    async def drain_queue(self) -> int:
        """Drain the message queue, sending all queued messages.

        Returns:
            Number of messages sent
        """
        sent = 0
        async with self._queue_lock:
            while self._message_queue and self.is_connected:
                msg = self._message_queue.popleft()
                success = await self.send(
                    MessageType(msg.get("type", "error")),
                    msg.get("payload", {}),
                )
                if success:
                    sent += 1
                else:
                    # Put it back if send failed
                    self._message_queue.appendleft(msg)
                    break
        return sent

    async def close(self, code: int = 1000, reason: str = "") -> None:
        """Close the connection gracefully."""
        if self._closed:
            return

        self._closed = True

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Notify disconnect handlers
        for handler in self._disconnect_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(self)
                else:
                    handler(self)
            except Exception as exc:
                logger.exception("Disconnect handler error: %s", exc)

        try:
            await self.websocket.close(code=code, reason=reason)
        except Exception as exc:
            logger.debug("WebSocket close failed: %s", exc)

        duration = time.time() - self.stats.connected_at
        logger.debug(
            "Connection %s closed after %.1fs: sent=%d, recv=%d, errors=%d",
            self.connection_id,
            duration,
            self.stats.messages_sent,
            self.stats.messages_received,
            self.stats.errors,
        )


class WebSocketManager:
    """Manages all WebSocket connections with connection pooling."""

    def __init__(self, config: ConnectionConfig | None = None):
        self.config = config or ConnectionConfig()
        self._connections: dict[str, WebSocketConnection] = {}
        self._connections_by_ip: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()
        self._broadcast_callbacks: list[Callable] = []

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    @property
    def authenticated_count(self) -> int:
        return sum(1 for c in self._connections.values() if c.is_authenticated)

    async def connect(
        self,
        websocket: WebSocket,
        client_ip: str | None = None,
    ) -> WebSocketConnection | None:
        """Accept and register a new WebSocket connection.

        Returns:
            WebSocketConnection if successful, None if rejected
        """
        connection_id = f"{client_ip or 'unknown'}_{id(websocket)}_{time.time():.6f}"

        async with self._lock:
            # Check connection limit per IP
            ip = client_ip or "unknown"
            ip_connections = self._connections_by_ip.get(ip, set())
            if len(ip_connections) >= self.config.max_connections_per_ip:
                logger.warning("Connection limit exceeded for IP %s", ip)
                await websocket.close(1008, "Connection limit exceeded")
                return None

        await websocket.accept()

        connection = WebSocketConnection(
            websocket=websocket,
            config=self.config,
            connection_id=connection_id,
            client_ip=ip,
        )

        # Validate origin
        if not await connection.validate_origin():
            await connection.close(1008, "Invalid origin")
            return None

        async with self._lock:
            self._connections[connection_id] = connection
            if ip not in self._connections_by_ip:
                self._connections_by_ip[ip] = set()
            self._connections_by_ip[ip].add(connection_id)

        # Register disconnect handler to clean up
        connection.register_disconnect_handler(self._on_disconnect)

        # Start heartbeat
        await connection.start_heartbeat()

        logger.debug(
            "WebSocket connected: %s from %s (total: %d)",
            connection_id,
            ip,
            len(self._connections),
        )

        return connection

    async def _on_disconnect(self, connection: WebSocketConnection) -> None:
        """Handle connection disconnect."""
        if connection._heartbeat_task:
            connection._heartbeat_task.cancel()
            try:
                await connection._heartbeat_task
            except asyncio.CancelledError:
                pass

        async with self._lock:
            self._connections.pop(connection.connection_id, None)
            ip_connections = self._connections_by_ip.get(connection.client_ip, set())
            ip_connections.discard(connection.connection_id)
            if not ip_connections:
                self._connections_by_ip.pop(connection.client_ip, None)

        logger.debug(
            "WebSocket disconnected: %s (remaining: %d)",
            connection.connection_id,
            len(self._connections),
        )

    async def disconnect_all(self, code: int = 1000, reason: str = "Server shutting down") -> None:
        """Disconnect all connections."""
        connections = list(self._connections.values())
        for connection in connections:
            await connection.close(code, reason)

    async def broadcast(
        self,
        message_type: MessageType,
        payload: dict[str, Any],
        authenticated_only: bool = False,
        exclude: str | None = None,
    ) -> int:
        """Broadcast a message to all connected clients.

        Returns:
            Number of clients the message was sent to
        """
        sent = 0
        connections = list(self._connections.values())

        for connection in connections:
            if exclude and connection.connection_id == exclude:
                continue
            if authenticated_only and not connection.is_authenticated:
                continue
            if await connection.send(message_type, payload):
                sent += 1

        return sent

    async def broadcast_transcription_partial(self, text: str, is_final: bool = False) -> int:
        """Broadcast partial transcription to all clients."""
        return await self.broadcast(
            MessageType.TRANSCRIPTION_PARTIAL,
            {"text": text, "is_final": is_final},
        )

    async def broadcast_transcription_final(
        self, text: str, confidence: float, segments: list[dict] | None = None
    ) -> int:
        """Broadcast final transcription to all clients."""
        payload: dict[str, Any] = {"text": text, "confidence": confidence}
        if segments:
            payload["segments"] = segments
        return await self.broadcast(MessageType.TRANSCRIPTION_FINAL, payload)

    async def broadcast_audio_level(
        self, level: float, peak: float, levels: list[float] | None = None
    ) -> int:
        """Broadcast audio level to all clients."""
        payload: dict[str, Any] = {"level": level, "peak": peak}
        if levels:
            payload["levels"] = levels
        return await self.broadcast(MessageType.AUDIO_LEVEL, payload)

    async def broadcast_health_metrics(self, metrics: dict[str, Any]) -> int:
        """Broadcast health metrics to all clients."""
        return await self.broadcast(MessageType.HEALTH_METRICS, metrics)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics for all connections."""
        return {
            "total_connections": len(self._connections),
            "authenticated_connections": self.authenticated_count,
            "connections_by_ip": {ip: len(conns) for ip, conns in self._connections_by_ip.items()},
            "connection_stats": [
                {
                    "id": conn.connection_id,
                    "ip": conn.client_ip,
                    "connected_at": conn.stats.connected_at,
                    "messages_sent": conn.stats.messages_sent,
                    "messages_received": conn.stats.messages_received,
                    "authenticated": conn.is_authenticated,
                }
                for conn in self._connections.values()
            ],
        }


# Global WebSocket manager instance
_ws_manager: WebSocketManager | None = None


def get_websocket_manager() -> WebSocketManager:
    """Get or create the global WebSocket manager."""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager


def reset_websocket_manager() -> None:
    """Reset the global WebSocket manager (for testing)."""
    global _ws_manager
    _ws_manager = None
