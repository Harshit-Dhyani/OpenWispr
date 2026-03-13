"""E2E smoke tests for hotkey mode against the current API."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.hotkey]


class TestHotkeySmoke:
    @pytest.mark.asyncio
    async def test_hotkey_start_exposes_recording_status(self, api_client):
        result = await api_client.start_hotkey_session()

        assert result["status"] == "recording"
        assert result["capture_source"] == "microphone"
        assert "session_id" in result

        status = await api_client.get_hotkey_status()
        assert status["state"] in {"recording", "starting"}
        assert status["session_id"] == result["session_id"]
        assert status["correlation_id"] == result["session_id"]

        await api_client.stop_hotkey_session(mode="cancel")

    @pytest.mark.asyncio
    async def test_hotkey_stop_returns_structured_result(self, api_client):
        start = await api_client.start_hotkey_session()
        stop = await api_client.stop_hotkey_session(mode="cancel")

        assert stop["session_id"] == start["session_id"]
        assert stop["segment_count"] >= 0
        assert "used_refiner_runtime" in stop

        status = await api_client.get_hotkey_status()
        assert status["state"] == "idle"
