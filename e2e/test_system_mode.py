"""E2E smoke tests for current system-audio session endpoints."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.system]


class TestSystemSessionSmoke:
    @pytest.mark.asyncio
    async def test_system_session_start_returns_session_payload(self, api_client):
        result = await api_client.start_system_session(
            title="System Smoke Test",
            language_mode="auto",
            live_mode="balanced",
        )

        session = result["session"]
        assert session["title"] == "System Smoke Test"
        assert session["status"] in {"running", "starting"}
        assert session["device_id"] == "default"

        snapshot = await api_client.get("/api/session")
        assert snapshot["session"]["session_id"] == session["session_id"]

        await api_client.stop_system_session()

    @pytest.mark.asyncio
    async def test_system_session_stop_returns_session_wrapper(self, api_client):
        await api_client.start_system_session(title="System Stop Smoke Test")
        result = await api_client.stop_system_session()

        assert "session" in result
