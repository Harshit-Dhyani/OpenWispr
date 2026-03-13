"""Tests for the local LLM provider abstraction."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.api.providers import (
    get_provider,
    ProviderType,
    OllamaProvider,
    LMStudioProvider,
    LlamaCPPProvider,
)


def test_get_provider_returns_ollama():
    """Test factory returns Ollama provider."""
    provider = get_provider("ollama", "http://localhost:11434")
    assert isinstance(provider, OllamaProvider)


def test_get_provider_returns_lm_studio():
    """Test factory returns LM Studio provider."""
    provider = get_provider("lm_studio", "http://localhost:1234")
    assert isinstance(provider, LMStudioProvider)


def test_get_provider_returns_llama_cpp():
    """Test factory returns LlamaCPP provider."""
    provider = get_provider("llamacpp", None)
    assert isinstance(provider, LlamaCPPProvider)


@pytest.mark.asyncio
async def test_ollama_health_check():
    """Test Ollama health check."""
    provider = OllamaProvider("http://localhost:11434")

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        health = await provider.health_check()
        assert health.available is True


@pytest.mark.asyncio
async def test_provider_unavailable_on_error():
    """Test provider reports unavailable on error."""
    provider = OllamaProvider("http://localhost:11434")

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = Exception("Connection refused")

        health = await provider.health_check()
        assert health.available is False
        assert health.error is not None
