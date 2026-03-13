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


@pytest.mark.asyncio
async def test_ollama_list_models():
    """Test Ollama model listing."""
    provider = OllamaProvider("http://localhost:11434")

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama2:7b"},
                {"name": "qwen2.5-3b-instruct"},
            ]
        }
        mock_get.return_value = mock_response

        models = await provider.list_models()
        assert len(models) == 2
        assert models[0].id == "llama2:7b"
        assert models[0].provider == "ollama"


@pytest.mark.asyncio
async def test_lm_studio_list_models():
    """Test LM Studio model listing."""
    provider = LMStudioProvider("http://localhost:1234")

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "llama-3-8b-instruct"},
                {"id": "mistral-7b"},
            ]
        }
        mock_get.return_value = mock_response

        models = await provider.list_models()
        assert len(models) == 2
        assert models[0].id == "llama-3-8b-instruct"
        assert models[0].provider == "lm_studio"


@pytest.mark.asyncio
async def test_ollama_complete():
    """Test Ollama completion."""
    provider = OllamaProvider("http://localhost:11434")

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "This is the refined text."}
        mock_post.return_value = mock_response

        result = await provider.complete("原始文本", "qwen2.5-3b-instruct", {"temperature": 0.7})
        assert result == "This is the refined text."


@pytest.mark.asyncio
async def test_lm_studio_complete():
    """Test LM Studio completion."""
    provider = LMStudioProvider("http://localhost:1234")

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"text": "LM Studio refined text."}]}
        mock_post.return_value = mock_response

        result = await provider.complete(
            "Original text", "llama-3-8b", {"temperature": 0.7, "max_tokens": 512}
        )
        assert result == "LM Studio refined text."


def test_get_provider_invalid_type():
    """Test factory raises error for invalid provider type."""
    with pytest.raises(ValueError, match="Unknown provider type"):
        get_provider("invalid_provider", None)


@pytest.mark.asyncio
async def test_llama_cpp_health_check_no_model():
    """Test LlamaCPP health check without model path."""
    provider = LlamaCPPProvider(None)

    with patch.object(provider, "is_available", return_value=True):
        health = await provider.health_check()
        assert health.available is True


@pytest.mark.asyncio
async def test_llama_cpp_health_check_missing_library():
    """Test LlamaCPP health check when library not installed."""
    provider = LlamaCPPProvider(None)

    with patch.object(provider, "is_available", return_value=False):
        health = await provider.health_check()
        assert health.available is False
        assert "not installed" in health.error


@pytest.mark.asyncio
async def test_llama_cpp_health_check_missing_model():
    """Test LlamaCPP health check when model file doesn't exist."""
    provider = LlamaCPPProvider("/nonexistent/model.gguf")

    with patch.object(provider, "is_available", return_value=True):
        health = await provider.health_check()
        assert health.available is False
        assert "Model not found" in health.error
