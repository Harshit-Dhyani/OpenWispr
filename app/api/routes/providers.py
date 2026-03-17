"""Provider configuration and health endpoints.

Provides endpoints for managing LLM providers (OpenAI, Anthropic, etc.),
health checks, and model discovery.
"""

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
async def get_providers_health() -> dict[str, ProviderHealth]:
    """
    Get health status of all configured LLM providers.

    Returns:
        dict: Contains health status for each provider (ollama, lm_studio, llamacpp)
    """
    settings = get_settings_manager().get_settings()

    providers = ["ollama", "lm_studio", "llamacpp"]
    result: dict[str, ProviderHealth] = {}

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
            result[provider_type] = health
        except Exception as e:
            logger.error("Health check failed for %s: %s", provider_type, e)
            result[provider_type] = ProviderHealth(
                available=False,
                error=str(e),
                response_time_ms=None,
            )

    return result


@router.get("/api/providers/models")
@log_route("GET", "/api/providers/models")
async def get_provider_models() -> list[dict[str, str]]:
    """
    Get available models from configured LLM provider.

    Returns:
        list: List of available models with id, name, and provider
    """
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


@router.get("/api/providers/all-models")
@log_route("GET", "/api/providers/all-models")
async def get_all_provider_models() -> dict[str, list[dict[str, str]]]:
    """
    Get available models from all LLM providers.

    Returns:
        dict: Contains models for each provider (ollama, lm_studio, llamacpp)
    """
    settings = get_settings_manager().get_settings()

    providers_config = {
        "ollama": "http://localhost:11434",
        "lm_studio": "http://localhost:1234",
    }

    result: dict[str, list[dict[str, str]]] = {
        "ollama": [],
        "lm_studio": [],
        "llamacpp": [],
    }

    for provider_type, default_url in providers_config.items():
        try:
            base_url = (
                settings.refiner.refiner_provider_base_url or default_url
                if provider_type in ("ollama", "lm_studio")
                else None
            )
            provider = get_provider(provider_type, base_url)
            models = await provider.list_models()
            result[provider_type] = [
                {"id": m.id, "name": m.name, "provider": m.provider} for m in models
            ]
        except Exception as e:
            logger.error("Failed to list models for %s: %s", provider_type, e)
            result[provider_type] = []

    return result


@router.post("/api/providers/test")
@log_route("POST", "/api/providers/test")
async def test_provider(request: TestProviderRequest) -> dict[str, ProviderHealth | str]:
    """
    Test connectivity to a specific LLM provider.

    Args:
        request: TestProviderRequest containing provider_type and optional base_url

    Returns:
        dict: Contains available status, error message, and response_time_ms

    Raises:
        HTTPException: 400 if provider test fails
    """
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
    """
    Get current provider settings.

    Returns:
        dict: Contains engine_preference and provider_base_url
    """
    settings = get_settings_manager().get_settings()
    return {
        "engine_preference": settings.refiner.engine_preference or "llamacpp",
        "provider_base_url": settings.refiner.refiner_provider_base_url or "",
    }
