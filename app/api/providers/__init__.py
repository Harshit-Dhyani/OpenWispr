"""LLM provider implementations for coach and refiner services.

This module provides abstract and concrete provider implementations for
connecting to local LLM runtimes:

Provider Types:
- OllamaProvider: Connects to Ollama server (http://localhost:11434)
- LMStudioProvider: Connects to LM Studio server (http://localhost:1234)
- LlamaCPPProvider: Direct llama-cpp-python integration

Security:
- URL validation prevents SSRF attacks by restricting to localhost/internal IPs
- is_safe_url() validates all provider URLs before connection

Base Provider Interface:
- health_check(): Returns availability and response time
- list_models(): Returns available models from provider
- complete(): Generates text completion from prompt

Usage:
    from app.api.providers import get_provider, ProviderType

    provider = get_provider("ollama", "http://localhost:11434")
    health = await provider.health_check()
    models = await provider.list_models()
    result = await provider.complete(prompt, model_id, {"max_tokens": 512})

Edge Cases:
- Provider server unavailable: health_check returns available=False with error
- Invalid model: complete() raises RuntimeError
- Connection timeout: httpx timeout configured per provider
"""

from __future__ import annotations

import ipaddress
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

ProviderType = Literal["ollama", "lm_studio", "llamacpp"]


def is_safe_url(url: str) -> bool:
    """Validate URL is a safe localhost/internal URL to prevent SSRF."""
    try:
        parsed = urlparse(url)
        if not parsed.hostname:
            return False
        allowed_hosts = {"localhost", "127.0.0.1", "::1"}
        if parsed.hostname in allowed_hosts:
            return True
        ip = ipaddress.ip_address(parsed.hostname)
        return ip.is_private or ip.is_loopback
    except (ValueError, TypeError):
        return False


@dataclass(slots=True)
class ProviderHealth:
    available: bool
    error: str | None
    response_time_ms: int | None


@dataclass(slots=True)
class ProviderModel:
    id: str
    name: str
    provider: str


class BaseProvider(ABC):
    def __init__(self, base_url: str) -> None:
        if not is_safe_url(base_url):
            raise ValueError(f"URL must be a localhost or internal URL: {base_url}")
        self.base_url = base_url.rstrip("/")

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        pass

    @abstractmethod
    async def list_models(self) -> list[ProviderModel]:
        pass

    @abstractmethod
    async def complete(self, prompt: str, model: str, options: dict) -> str:
        pass


class OllamaProvider(BaseProvider):
    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        super().__init__(base_url)
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> ProviderHealth:
        start = time.perf_counter()
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return ProviderHealth(available=True, error=None, response_time_ms=elapsed_ms)
        except httpx.HTTPStatusError as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return ProviderHealth(
                available=False, error=f"HTTP {e.response.status_code}", response_time_ms=elapsed_ms
            )
        except httpx.RequestError as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return ProviderHealth(available=False, error=str(e), response_time_ms=elapsed_ms)
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return ProviderHealth(available=False, error=str(e), response_time_ms=elapsed_ms)

    async def list_models(self) -> list[ProviderModel]:
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            models = []
            for model in data.get("models", []):
                model_name = model.get("name", model.get("model", "unknown"))
                models.append(ProviderModel(id=model_name, name=model_name, provider="ollama"))
            return models
        except httpx.HTTPStatusError as e:
            logger.error("Failed to list Ollama models: HTTP %d", e.response.status_code)
            return []
        except httpx.RequestError as e:
            logger.error("Failed to list Ollama models: %s", e)
            return []
        except Exception as e:
            logger.error("Failed to list Ollama models: %s", e)
            return []

    async def complete(self, prompt: str, model: str, options: dict) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }
        try:
            response = await self.client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except httpx.HTTPStatusError as e:
            logger.error("Ollama completion failed: HTTP %d", e.response.status_code)
            raise RuntimeError(f"Ollama completion failed: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error("Ollama completion failed: %s", e)
            raise RuntimeError(f"Ollama completion failed: {e}") from e
        except Exception as e:
            logger.error("Ollama completion failed: %s", e)
            raise RuntimeError(f"Ollama completion failed: {e}") from e


class LMStudioProvider(BaseProvider):
    def __init__(self, base_url: str = "http://localhost:1234") -> None:
        super().__init__(base_url)
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> ProviderHealth:
        start = time.perf_counter()
        try:
            response = await self.client.get(f"{self.base_url}/v1/models")
            response.raise_for_status()
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return ProviderHealth(available=True, error=None, response_time_ms=elapsed_ms)
        except httpx.HTTPStatusError as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return ProviderHealth(
                available=False, error=f"HTTP {e.response.status_code}", response_time_ms=elapsed_ms
            )
        except httpx.RequestError as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return ProviderHealth(available=False, error=str(e), response_time_ms=elapsed_ms)
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return ProviderHealth(available=False, error=str(e), response_time_ms=elapsed_ms)

    async def list_models(self) -> list[ProviderModel]:
        try:
            response = await self.client.get(f"{self.base_url}/v1/models")
            response.raise_for_status()
            data = response.json()
            models = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                model_name = model.get("id", model.get("id", "unknown"))
                if model_id:
                    models.append(ProviderModel(id=model_id, name=model_name, provider="lm_studio"))
            return models
        except httpx.HTTPStatusError as e:
            logger.error("Failed to list LM Studio models: HTTP %d", e.response.status_code)
            return []
        except httpx.RequestError as e:
            logger.error("Failed to list LM Studio models: %s", e)
            return []
        except Exception as e:
            logger.error("Failed to list LM Studio models: %s", e)
            return []

    async def complete(self, prompt: str, model: str, options: dict) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "max_tokens": options.get("max_tokens", 512),
            "temperature": options.get("temperature", 0.7),
            "stream": False,
        }
        try:
            response = await self.client.post(f"{self.base_url}/v1/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("text", "").strip()
            return ""
        except httpx.HTTPStatusError as e:
            logger.error("LM Studio completion failed: HTTP %d", e.response.status_code)
            raise RuntimeError(f"LM Studio completion failed: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error("LM Studio completion failed: %s", e)
            raise RuntimeError(f"LM Studio completion failed: {e}") from e
        except Exception as e:
            logger.error("LM Studio completion failed: %s", e)
            raise RuntimeError(f"LM Studio completion failed: {e}") from e


class LlamaCPPProvider(BaseProvider):
    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path
        self._llm: Any | None = None

    @staticmethod
    def is_available() -> bool:
        return find_spec("llama_cpp") is not None

    def _ensure_model(self, model_path: str) -> Any:
        if self._llm is not None:
            return self._llm
        if not self.is_available():
            raise RuntimeError("llama-cpp-python is not installed")
        from llama_cpp import Llama

        self._llm = Llama(model_path=model_path, n_ctx=4096, verbose=False)
        return self._llm

    async def health_check(self) -> ProviderHealth:
        start = time.perf_counter()
        if not self.is_available():
            return ProviderHealth(
                available=False, error="llama-cpp-python not installed", response_time_ms=None
            )
        if self.model_path and not Path(self.model_path).exists():
            return ProviderHealth(
                available=False, error=f"Model not found: {self.model_path}", response_time_ms=None
            )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return ProviderHealth(available=True, error=None, response_time_ms=elapsed_ms)

    async def list_models(self) -> list[ProviderModel]:
        return []

    async def complete(self, prompt: str, model: str, options: dict) -> str:
        if not self.model_path:
            raise RuntimeError("No model path configured for LlamaCPP provider")
        llm = self._ensure_model(self.model_path)
        max_tokens = options.get("max_tokens", 512)
        temperature = options.get("temperature", 0.7)
        output = llm.create_completion(
            prompt=prompt, max_tokens=max_tokens, temperature=temperature
        )
        return output.get("choices", [{}])[0].get("text", "").strip()


def get_provider(provider_type: ProviderType, base_url: str | None = None) -> BaseProvider:
    if provider_type == "ollama":
        return OllamaProvider(base_url or "http://localhost:11434")
    elif provider_type == "lm_studio":
        return LMStudioProvider(base_url or "http://localhost:1234")
    elif provider_type == "llamacpp":
        return LlamaCPPProvider(model_path=base_url)
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")
