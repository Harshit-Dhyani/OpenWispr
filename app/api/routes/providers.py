from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.providers import (
    ProviderHealth,
    ProviderType,
    get_provider,
)
from app.api.route_utils import log_route
from app.core.settings.manager import get_settings_manager

logger = logging.getLogger(__name__)
router = APIRouter()


class TestProviderRequest(BaseModel):
    provider_type: ProviderType
    base_url: str | None = None


@router.get("/api/providers/health")
@log_route("GET", "/api/providers/health")
async def get_providers_health() -> dict[str, dict[str, ProviderHealth]]:
    settings = get_settings_manager().get_settings()

    providers = ["ollama", "lm_studio", "llamacpp"]
    result: dict[str, dict[str, ProviderHealth]] = {}

    for provider_type in providers:
        try:
            base_url = None
            if provider_type == "ollama":
                base_url = settings.refiner.refiner_provider_base_url or "http://localhost:11434"
            elif provider_type == "lm_studio":
                base_url = settings.refiner.refiner_provider_base_url or "http://localhost:1234"
            elif provider_type == "llamacpp":
                base_url = None

            provider = get_provider(provider_type, base_url)
            health = await provider.health_check()
            result[provider_type] = {
                "available": health.available,
                "error": health.error,
                "response_time_ms": health.response_time_ms,
            }
        except Exception as e:
            logger.error("Health check failed for %s: %s", provider_type, e)
            result[provider_type] = {
                "available": False,
                "error": str(e),
                "response_time_ms": None,
            }

    return result


@router.get("/api/providers/models")
@log_route("GET", "/api/providers/models")
async def get_provider_models() -> list[dict[str, str]]:
    settings = get_settings_manager().get_settings()

    engine_preference = settings.refiner.engine_preference or "llamacpp"

    base_url = None
    if engine_preference in ("ollama", "lm_studio"):
        base_url = settings.refiner.refiner_provider_base_url or None
        if engine_preference == "ollama" and not base_url:
            base_url = "http://localhost:11434"
        elif engine_preference == "lm_studio" and not base_url:
            base_url = "http://localhost:1234"

    try:
        provider = get_provider(engine_preference, base_url)
        models = await provider.list_models()
        return [{"id": m.id, "name": m.name, "provider": m.provider} for m in models]
    except Exception as e:
        logger.error("Failed to list models for %s: %s", engine_preference, e)
        return []


@router.post("/api/providers/test")
@log_route("POST", "/api/providers/test")
async def test_provider(request: TestProviderRequest) -> dict[str, ProviderHealth | str]:
    try:
        provider = get_provider(request.provider_type, request.base_url)
        health = await provider.health_check()
        return {
            "available": health.available,
            "error": health.error,
            "response_time_ms": health.response_time_ms,
        }
    except Exception as e:
        logger.error("Test failed for %s: %s", request.provider_type, e)
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/providers/settings")
@log_route("GET", "/api/providers/settings")
def get_provider_settings() -> dict[str, str]:
    settings = get_settings_manager().get_settings()
    return {
        "engine_preference": settings.refiner.engine_preference or "llamacpp",
        "provider_base_url": settings.refiner.refiner_provider_base_url or "",
    }
