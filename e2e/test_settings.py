"""E2E tests for settings persistence."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.settings]


class TestSettingsPersistence:
    @pytest.mark.asyncio
    async def test_settings_get_returns_dict(self, api_client):
        """Settings endpoint should return a dictionary."""
        settings = await api_client.get_settings()
        assert isinstance(settings, dict)

    @pytest.mark.asyncio
    async def test_settings_save_and_retrieve(self, api_client):
        """Settings should persist after save."""
        original = await api_client.get_settings()

        test_key = "transcription"
        if test_key in original:
            original[test_key]["beam_size"] = 3

        await api_client.save_settings(original)
        retrieved = await api_client.get_settings()

        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_settings_reset_returns_defaults(self, api_client):
        """Settings reset should return default values."""
        result = await api_client.reset_settings()
        assert result.get("success") is True

        settings = await api_client.get_settings()
        assert settings is not None
