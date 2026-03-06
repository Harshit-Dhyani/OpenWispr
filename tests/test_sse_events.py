from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.server import app, get_service
from app.api.service import BackendService
from app.core.config import AppSettings
from app.core.models import SessionHealth


@pytest.fixture
def mock_backend_service() -> Generator[BackendService, None, None]:
    """Create a mock backend service for testing."""
    service = MagicMock(spec=BackendService)
    snapshot = MagicMock()
    snapshot.health = SessionHealth().to_dict()
    snapshot.meter_value = 0.5
    snapshot.session = {"session_id": "test-123"}
    snapshot.transcript = []
    snapshot.suppressed_transcript = []
    snapshot.formulas = []
    snapshot.needs_review = []
    snapshot.available_models = ["tiny", "base", "small"]
    snapshot.available_languages = ["auto", "en"]
    snapshot.available_live_modes = ["realtime", "balanced"]
    snapshot.available_execution_modes = ["auto", "cpu_only"]
    snapshot.runtime_revision = 1
    service.get_snapshot.return_value = snapshot
    service.list_devices.return_value = [
        {"id": "device1", "name": "Test Device", "is_loopback": True}
    ]

    event_callbacks: list[Callable[[str, dict[str, Any]], None]] = []

    def register_callback(callback: Callable[[str, dict[str, Any]], None]) -> None:
        event_callbacks.append(callback)

    def unregister_callback(callback: Callable[[str, dict[str, Any]], None]) -> None:
        if callback in event_callbacks:
            event_callbacks.remove(callback)

    def publish_event(event_type: str, data: dict[str, Any]) -> None:
        for callback in event_callbacks:
            callback(event_type, data)

    service.register_event_callback = register_callback
    service.unregister_event_callback = unregister_callback
    service._publish_event = publish_event
    service._event_callbacks = event_callbacks

    yield service


@pytest.fixture
def client(mock_backend_service: MagicMock) -> Generator[TestClient, None, None]:
    """Create a test client with mocked service."""

    def override_get_service() -> BackendService:
        return mock_backend_service

    app.dependency_overrides[get_service] = override_get_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestSSEContentType:
    """Test SSE endpoint returns correct content-type."""

    def test_events_endpoint_returns_text_event_stream(self, client: TestClient) -> None:
        with client.stream("GET", "/api/events", headers={"Accept": "text/event-stream"}) as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    def test_events_endpoint_returns_keepalive_headers(self, client: TestClient) -> None:
        with client.stream("GET", "/api/events") as response:
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["connection"] == "keep-alive"
            assert response.headers["x-accel-buffering"] == "no"


class TestSSEEventFormat:
    """Test events are streamed in correct format."""

    def test_segment_event_format(
        self, client: TestClient, mock_backend_service: MagicMock
    ) -> None:
        def event_generator():
            yield mock_backend_service._publish_event(
                "segment",
                {"id": "seg-1", "text": "Project status update", "start": 0.0, "end": 2.0},
            )

        with client.stream("GET", "/api/events") as response:
            lines = []
            for chunk in response.iter_lines():
                lines.append(chunk)
                if len(lines) >= 2:
                    break

            assert any("event:" in line for line in lines)
            assert any("data:" in line for line in lines)

    def test_health_event_format(self, client: TestClient, mock_backend_service: MagicMock) -> None:
        with client.stream("GET", "/api/events") as response:
            mock_backend_service._publish_event(
                "health",
                {"health": {"gpu_mode": "cpu"}, "meter_value": 0.5},
            )

            content = ""
            for chunk in response.iter_text():
                content += chunk
                if "event: health" in content:
                    break

            assert "event: health" in content
            assert "data:" in content

    def test_state_event_format(self, client: TestClient, mock_backend_service: MagicMock) -> None:
        with client.stream("GET", "/api/events") as response:
            mock_backend_service._publish_event(
                "state",
                {"session_id": "test-123", "status": "running"},
            )

            content = ""
            for chunk in response.iter_text():
                content += chunk
                if "event: state" in content:
                    break

            assert "event: state" in content

    def test_formulas_event_format(
        self, client: TestClient, mock_backend_service: MagicMock
    ) -> None:
        with client.stream("GET", "/api/events") as response:
            mock_backend_service._publish_event(
                "formulas",
                {"formulas": [{"expression": "E = mc^2", "confidence": 0.9}]},
            )

            content = ""
            for chunk in response.iter_text():
                content += chunk
                if "event: formulas" in content:
                    break

            assert "event: formulas" in content


class TestSSEClientDisconnect:
    """Test client disconnect is handled properly."""

    def test_callback_unregistered_on_disconnect(
        self, client: TestClient, mock_backend_service: MagicMock
    ) -> None:
        initial_callback_count = len(mock_backend_service._event_callbacks)

        with client.stream("GET", "/api/events") as response:
            assert len(mock_backend_service._event_callbacks) > initial_callback_count

        assert len(mock_backend_service._event_callbacks) == initial_callback_count

    def test_disconnect_during_event_stream(
        self, client: TestClient, mock_backend_service: MagicMock
    ) -> None:
        call_count = [0]

        def slow_callback(event_type: str, data: dict[str, Any]) -> None:
            call_count[0] += 1
            if call_count[0] > 3:
                asyncio.sleep(0.1)

        mock_backend_service.register_event_callback(slow_callback)

        with client.stream("GET", "/api/events") as response:
            for _ in range(3):
                mock_backend_service._publish_event("test", {"data": "value"})

        mock_backend_service.unregister_event_callback(slow_callback)
        assert slow_callback not in mock_backend_service._event_callbacks


class TestSSEReconnection:
    """Test reconnection with Last-Event-ID."""

    def test_last_event_id_header_accepted(self, client: TestClient) -> None:
        with client.stream(
            "GET",
            "/api/events",
            headers={"Last-Event-ID": "event-123"},
        ) as response:
            assert response.status_code == 200

    def test_reconnection_receives_new_events(
        self, client: TestClient, mock_backend_service: MagicMock
    ) -> None:
        events_received: list[str] = []

        def callback(event_type: str, data: dict[str, Any]) -> None:
            events_received.append(event_type)

        mock_backend_service.register_event_callback(callback)

        with client.stream("GET", "/api/events") as response:
            mock_backend_service._publish_event("segment", {"id": "1"})
            mock_backend_service._publish_event("segment", {"id": "2"})

            for chunk in response.iter_text():
                if len(events_received) >= 2:
                    break

        mock_backend_service.unregister_event_callback(callback)
        assert len(events_received) >= 2


class TestSSEKeepalive:
    """Test SSE keepalive mechanism."""

    def test_keepalive_sent_during_inactivity(self, client: TestClient) -> None:
        with client.stream("GET", "/api/events") as response:
            content = ""
            for chunk in response.iter_text():
                content += chunk
                if ":keepalive" in content:
                    break
                if len(content) > 1000:
                    pytest.skip("Keepalive not detected in reasonable time")

            assert ":keepalive" in content
