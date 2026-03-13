"""E2E tests for model routing (microphone vs system)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.models]


class TestModelRouting:
    @pytest.mark.asyncio
    async def test_model_catalog_returns_list(self, api_client):
        """Model catalog endpoint should return a list."""
        catalog = await api_client.get_model_catalog()
        assert "catalog" in catalog
        assert isinstance(catalog["catalog"], list)

    @pytest.mark.asyncio
    async def test_source_specific_models(self, api_client):
        """Settings should support source-specific model selection."""
        settings = await api_client.get_settings()

        assert "transcription" in settings
        transcription = settings["transcription"]

        assert "microphone_asr_model_id" in transcription
        assert "system_asr_model_id" in transcription

        assert transcription["microphone_asr_model_id"] is not None
        assert transcription["system_asr_model_id"] is not None

    @pytest.mark.asyncio
    async def test_model_installed_state(self, api_client):
        """Should be able to check model installation state."""
        state = await api_client.get_model_state()

        assert "installed" in state
        assert isinstance(state["installed"], (list, dict))
