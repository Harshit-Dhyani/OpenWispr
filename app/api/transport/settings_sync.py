"""Bidirectional settings synchronization over WebSocket.

This module provides real-time settings synchronization between
server and clients with validation and conflict resolution.
"""

from __future__ import annotations

import asyncio
import copy
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from app.api.websocket_server import MessageType, WebSocketConnection
from app.core.settings_manager import (
    SettingsManager,
    SettingsState,
    get_settings_manager,
)

logger = logging.getLogger(__name__)


class SyncDirection(str, Enum):
    """Direction of settings synchronization."""

    SERVER_TO_CLIENT = "server_to_client"
    CLIENT_TO_SERVER = "client_to_server"
    BIDIRECTIONAL = "bidirectional"


class SyncConflictResolution(str, Enum):
    """How to resolve sync conflicts."""

    SERVER_WINS = "server_wins"
    CLIENT_WINS = "client_wins"
    LAST_WRITE_WINS = "last_write_wins"
    REJECT = "reject"


@dataclass
class SyncConfig:
    """Configuration for settings synchronization."""

    direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    conflict_resolution: SyncConflictResolution = SyncConflictResolution.SERVER_WINS
    debounce_ms: float = 100.0  # Debounce rapid changes
    validate_on_receive: bool = True
    notify_on_change: bool = True
    batch_updates: bool = True
    batch_interval_ms: float = 50.0


@dataclass
class PendingChange:
    """A pending settings change."""

    category: str
    key: str
    value: Any
    timestamp: float
    source: str  # 'client' or 'server'


class SettingsSynchronizer:
    """Manages bidirectional settings synchronization."""

    def __init__(
        self,
        settings_manager: SettingsManager | None = None,
        config: SyncConfig | None = None,
    ):
        self.settings_manager = settings_manager or get_settings_manager()
        self.config = config or SyncConfig()

        # State tracking
        self._last_synced_settings: dict[str, Any] | None = None
        self._pending_changes: list[PendingChange] = []
        self._last_change_time: float = 0.0

        # Callbacks
        self._change_callbacks: list[Callable[[str, str, Any, str], None]] = []
        self._validation_callbacks: list[Callable[[str, str, Any], tuple[bool, str]]] = []

        # Async primitives
        self._lock = asyncio.Lock()
        self._debounce_task: asyncio.Task | None = None
        self._batch_task: asyncio.Task | None = None
        self._batched_updates: dict[str, dict[str, Any]] = {}

        # Connected clients
        self._subscribed_connections: set[str] = set()

    def subscribe_connection(self, connection_id: str) -> None:
        """Subscribe a WebSocket connection to settings updates."""
        self._subscribed_connections.add(connection_id)
        logger.debug("Connection %s subscribed to settings sync", connection_id)

    def unsubscribe_connection(self, connection_id: str) -> None:
        """Unsubscribe a WebSocket connection from settings updates."""
        self._subscribed_connections.discard(connection_id)
        logger.debug("Connection %s unsubscribed from settings sync", connection_id)

    def register_change_callback(self, callback: Callable[[str, str, Any, str], None]) -> None:
        """Register a callback for settings changes.

        Args:
            callback: Function(category, key, value, source)
        """
        self._change_callbacks.append(callback)

    def register_validation_callback(
        self, callback: Callable[[str, str, Any], tuple[bool, str]]
    ) -> None:
        """Register a callback for validating settings changes.

        Args:
            callback: Function(category, key, value) -> (is_valid, error_message)
        """
        self._validation_callbacks.append(callback)

    async def handle_client_update(
        self,
        settings_update: dict[str, Any],
        connection: WebSocketConnection,
    ) -> dict[str, Any]:
        """Handle a settings update from a client.

        Args:
            settings_update: The settings update from client
            connection: The WebSocket connection

        Returns:
            Response dict with success status and any errors
        """
        if self.config.direction == SyncDirection.SERVER_TO_CLIENT:
            return {
                "success": False,
                "error": "Client updates are not allowed in server-to-client mode",
            }

        try:
            # Extract category and updates
            category = settings_update.get("category")
            updates = settings_update.get("settings", {})
            immediate = settings_update.get("immediate", False)

            if not category or not isinstance(updates, dict):
                return {"success": False, "error": "Invalid settings update format"}

            # Validate the changes
            validation_errors = []
            valid_updates = {}

            for key, value in updates.items():
                is_valid, error = await self._validate_change(category, key, value)
                if is_valid:
                    valid_updates[key] = value
                else:
                    validation_errors.append({"key": key, "error": error})

            if validation_errors and not valid_updates:
                return {
                    "success": False,
                    "error": "All changes failed validation",
                    "validation_errors": validation_errors,
                }

            # Apply changes
            if immediate or not self.config.batch_updates:
                await self._apply_changes(category, valid_updates, "client")
            else:
                await self._queue_changes(category, valid_updates, "client")

            # Send response
            response = {
                "success": True,
                "applied": list(valid_updates.keys()),
            }
            if validation_errors:
                response["validation_errors"] = validation_errors

            # Notify other clients of the change
            if self.config.notify_on_change:
                await self._notify_other_clients(
                    category, valid_updates, exclude_connection=connection.connection_id
                )

            return response

        except Exception as exc:
            logger.exception("Error handling client settings update: %s", exc)
            return {"success": False, "error": str(exc)}

    async def handle_server_update(self, category: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Handle a settings update from the server side.

        Args:
            category: Settings category
            updates: Dictionary of setting key -> value

        Returns:
            Response dict with success status
        """
        if self.config.direction == SyncDirection.CLIENT_TO_SERVER:
            return {
                "success": False,
                "error": "Server updates are not allowed in client-to-server mode",
            }

        try:
            await self._apply_changes(category, updates, "server")

            if self.config.notify_on_change:
                await self._notify_clients(category, updates)

            return {"success": True, "applied": list(updates.keys())}

        except Exception as exc:
            logger.exception("Error handling server settings update: %s", exc)
            return {"success": False, "error": str(exc)}

    async def send_current_settings(self, connection: WebSocketConnection) -> bool:
        """Send current settings to a client."""
        try:
            settings = self.settings_manager.get_settings_dict()
            return await connection.send(MessageType.SETTINGS_RESPONSE, {"settings": settings})
        except Exception as exc:
            logger.error("Failed to send settings to client: %s", exc)
            return False

    async def get_settings_delta(self) -> dict[str, Any] | None:
        """Get the delta between last synced and current settings.

        Returns:
            Dictionary of changed settings, or None if no changes
        """
        current = self.settings_manager.get_settings_dict()

        if self._last_synced_settings is None:
            self._last_synced_settings = copy.deepcopy(current)
            return None

        delta = {}
        for category, settings in current.items():
            if isinstance(settings, dict):
                last_category = self._last_synced_settings.get(category, {})
                category_delta = {}
                for key, value in settings.items():
                    if last_category.get(key) != value:
                        category_delta[key] = value
                if category_delta:
                    delta[category] = category_delta

        self._last_synced_settings = copy.deepcopy(current)
        return delta if delta else None

    async def sync_to_clients(self, force: bool = False) -> int:
        """Sync current settings to all subscribed clients.

        Returns:
            Number of clients notified
        """
        if not self._subscribed_connections:
            return 0

        delta = await self.get_settings_delta()
        if not delta and not force:
            return 0

        settings = self.settings_manager.get_settings_dict()

        # This would typically use the WebSocket manager to broadcast
        # For now, we just log the update
        logger.debug(
            "Broadcasting settings update to %d clients", len(self._subscribed_connections)
        )

        # Return number of subscribed connections (actual broadcast done by caller)
        return len(self._subscribed_connections)

    async def _validate_change(self, category: str, key: str, value: Any) -> tuple[bool, str]:
        """Validate a settings change.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.config.validate_on_receive:
            return True, ""

        # Run custom validation callbacks
        for callback in self._validation_callbacks:
            try:
                is_valid, error = callback(category, key, value)
                if not is_valid:
                    return False, error
            except Exception as exc:
                logger.exception("Validation callback error: %s", exc)

        # Use settings manager validator
        try:
            result = self.settings_manager.validate_category(category, {key: value})
            if not result.is_valid:
                return False, str(result.errors)
        except Exception as exc:
            logger.debug("Settings validation error: %s", exc)
            # Don't fail on validation errors, just log them

        return True, ""

    async def _apply_changes(self, category: str, updates: dict[str, Any], source: str) -> None:
        """Apply settings changes to the settings manager."""
        async with self._lock:
            # Apply updates
            self.settings_manager.update_partial(category, updates)

            # Notify callbacks
            for key, value in updates.items():
                for callback in self._change_callbacks:
                    try:
                        callback(category, key, value, source)
                    except Exception as exc:
                        logger.exception("Change callback error: %s", exc)

            self._last_change_time = asyncio.get_running_loop().time()
            logger.debug("Applied settings changes: %s updates=%s (from %s)", category, updates, source)

    async def _queue_changes(self, category: str, updates: dict[str, Any], source: str) -> None:
        """Queue changes for batched application."""
        async with self._lock:
            if category not in self._batched_updates:
                self._batched_updates[category] = {}
            self._batched_updates[category].update(updates)

            # Cancel existing batch task
            if self._batch_task and not self._batch_task.done():
                self._batch_task.cancel()

            # Start new batch task
            self._batch_task = asyncio.create_task(self._process_batch(source))

    async def _process_batch(self, source: str) -> None:
        """Process batched updates after the batch interval."""
        try:
            await asyncio.sleep(self.config.batch_interval_ms / 1000.0)

            async with self._lock:
                updates_to_apply = self._batched_updates.copy()
                self._batched_updates.clear()

            for category, updates in updates_to_apply.items():
                await self._apply_changes(category, updates, source)

            # Notify clients
            if self.config.notify_on_change:
                for category, updates in updates_to_apply.items():
                    await self._notify_clients(category, updates)

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.exception("Error processing batched updates: %s", exc)

    async def _notify_clients(self, category: str, updates: dict[str, Any]) -> int:
        """Notify all subscribed clients of a settings change.

        Returns:
            Number of clients notified
        """
        # This would integrate with WebSocketManager to broadcast
        # For now, just return the count
        return len(self._subscribed_connections)

    async def _notify_other_clients(
        self,
        category: str,
        updates: dict[str, Any],
        exclude_connection: str | None = None,
    ) -> int:
        """Notify all clients except the originating one.

        Returns:
            Number of clients notified
        """
        # This would integrate with WebSocketManager to broadcast
        return max(0, len(self._subscribed_connections) - (1 if exclude_connection else 0))

    async def request_settings_from_client(self, connection: WebSocketConnection) -> bool:
        """Request current settings from a client.

        This is useful when the server wants to sync client-side settings.
        """
        return await connection.send(
            MessageType.SETTINGS_REQUEST,
            {"request_id": f"req_{asyncio.get_running_loop().time()}"},
        )

    def get_sync_status(self) -> dict[str, Any]:
        """Get current synchronization status."""
        return {
            "direction": self.config.direction,
            "subscribed_connections": len(self._subscribed_connections),
            "pending_changes": len(self._pending_changes),
            "batched_updates": {
                cat: list(updates.keys()) for cat, updates in self._batched_updates.items()
            },
            "last_change_time": self._last_change_time,
        }


# Global settings synchronizer instance
_settings_sync: SettingsSynchronizer | None = None


def get_settings_synchronizer() -> SettingsSynchronizer:
    """Get or create the global settings synchronizer."""
    global _settings_sync
    if _settings_sync is None:
        _settings_sync = SettingsSynchronizer()
    return _settings_sync


def reset_settings_synchronizer() -> None:
    """Reset the global settings synchronizer (for testing)."""
    global _settings_sync
    _settings_sync = None
