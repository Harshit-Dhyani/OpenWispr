"""E2E smoke tests for model catalog and preload flows."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.models]


class TestModelFlowsSmoke:
    @pytest.mark.asyncio
    async def test_model_catalog_and_preload_endpoint(self, api_client):
        catalog_payload = await api_client.get("/api/models/catalog")

        assert "catalog" in catalog_payload
        assert len(catalog_payload["catalog"]) > 0

        first_asr = next(entry for entry in catalog_payload["catalog"] if entry["category"] == "asr")
        preload_result = await api_client.post(
            "/api/models/preload",
            json={"model_name": first_asr["id"], "execution_mode": "auto"},
        )

        assert preload_result["status"] in {"loading", "ready"}
