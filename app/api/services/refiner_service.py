"""LLM-powered transcript refiner service.

Provides RefinerService for rephrasing and improving transcripts using
configurable LLM providers. Supports different refinement modes (casual,
professional, concise) and maintains request queue for load management.

This service is optional - falls back gracefully when no LLM provider is available.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from threading import Lock
from typing import Any

from app.api.providers import ProviderHealth, ProviderType, get_provider
from app.config.constants import ProviderConstants
from app.core.model_catalog import get_model_catalog_entry
from app.core.settings.manager import get_settings_manager
from app.stt.prompts import build_refiner_prompt

logger = logging.getLogger(__name__)
LLAMA_CPP_AVAILABLE = find_spec("llama_cpp") is not None
PLACEHOLDER_TOKEN_RE = re.compile(r"\[\[KEEP_TOKEN_(\d{4})\]\]")


def is_llama_cpp_available() -> bool:
    return LLAMA_CPP_AVAILABLE


@dataclass(slots=True)
class RefinerResult:
    text: str
    mode: str
    model_id: str | None
    used_runtime: bool
    error: str | None = None


@dataclass(slots=True)
class ProtectedText:
    protected_text: str
    placeholders: dict[str, str]


class RefinerService:
    """LLM-powered transcript refiner service.

    Rephrases and improves transcripts using configurable LLM providers.
    Supports different refinement modes (casual, professional, concise) and
    maintains placeholder protection for sensitive tokens.

    State ownership:
    - Lazy-loaded LLM model (llama.cpp)
    - Lock-protected model loading
    - Placeholder tracking for token protection

    Fallback behavior:
    - Returns original text when runtime unavailable
    - Preserves protected tokens (numbers, URLs, hotkeys, etc.)
    - Validates output doesn't change protected content aggressively
    """

    def __init__(self, download_root: Path) -> None:
        self.download_root = Path(download_root)
        self._lock = Lock()
        self._loaded_model_id: str | None = None
        self._llm: Any | None = None
        self._engine_preference: str = "llamacpp"
        self._provider_base_url: str = ProviderConstants.DEFAULT_OLLAMA_URL

    def update_settings(
        self, engine_preference: str | None = None, provider_base_url: str | None = None
    ) -> None:
        if engine_preference is not None:
            self._engine_preference = engine_preference
        if provider_base_url is not None:
            self._provider_base_url = provider_base_url

    def _get_settings(self) -> tuple[str, str]:
        try:
            settings = get_settings_manager().get_settings()
            engine_preference = getattr(settings.refiner, "engine_preference", "llamacpp")
            provider_base_url = (
                settings.refiner.refiner_provider_base_url
                if hasattr(settings, "refiner")
                and hasattr(settings.refiner, "refiner_provider_base_url")
                else ProviderConstants.DEFAULT_OLLAMA_URL
            )
            return engine_preference, provider_base_url
        except Exception:
            return self._engine_preference, self._provider_base_url

    def unload(self) -> None:
        with self._lock:
            self._llm = None
            self._loaded_model_id = None

    def is_available(self, model_id: str) -> bool:
        return self._resolve_model_path(model_id) is not None

    def refine_text(
        self,
        text: str,
        *,
        mode: str,
        profile: str = "raw",
        model_id: str | None,
        runtime_enabled: bool,
        language_hint: str = "auto",
        cleanup_instructions: str = "",
    ) -> RefinerResult:
        start_time = time.perf_counter()
        normalized = (text or "").strip()
        if not normalized or mode == "off" or profile == "raw":
            result = RefinerResult(
                text=normalized,
                mode="off" if mode == "off" else profile,
                model_id=model_id,
                used_runtime=False,
            )
            logger.info(
                "Refiner skipped: mode=%s model=%s used_runtime=%s reason=%s latency_ms=%.1f",
                mode if mode == "off" else profile,
                result.model_id,
                result.used_runtime,
                "mode_off_profile_raw_or_empty",
                (time.perf_counter() - start_time) * 1000.0,
            )
            return result

        if not runtime_enabled:
            result = RefinerResult(
                text=normalized,
                mode=mode,
                model_id=model_id,
                used_runtime=False,
                error="Selected refiner runtime is disabled; using built-in cleanup only.",
            )
            logger.info(
                "Refiner fallback: mode=%s model=%s used_runtime=%s reason=%s latency_ms=%.1f",
                mode,
                result.model_id,
                result.used_runtime,
                result.error,
                (time.perf_counter() - start_time) * 1000.0,
            )
            return result

        if not model_id:
            result = RefinerResult(
                text=normalized,
                mode=mode,
                model_id=None,
                used_runtime=False,
                error="No refiner model is selected.",
            )
            logger.info(
                "Refiner fallback: mode=%s model=%s used_runtime=%s reason=%s latency_ms=%.1f",
                mode,
                result.model_id,
                result.used_runtime,
                result.error,
                (time.perf_counter() - start_time) * 1000.0,
            )
            return result

        protected = self._protect_sensitive_tokens(normalized)
        prompt = build_refiner_prompt(
            protected.protected_text,
            mode=mode,
            profile=profile,
            language_hint=language_hint,
            cleanup_instructions=cleanup_instructions,
        )
        temperature = 0.05 if mode == "strict" else 0.2
        max_tokens = min(1024, max(192, len(normalized.split()) * 6))

        try:
            engine_preference, provider_base_url = self._get_settings()
            candidate = self._call_llm(
                model_id=model_id,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                engine_preference=engine_preference,
                provider_base_url=provider_base_url,
            )
        except Exception as exc:  # pragma: no cover - runtime/hardware dependent
            result = RefinerResult(
                text=normalized,
                mode=mode,
                model_id=model_id,
                used_runtime=False,
                error=f"Refiner runtime failed: {exc}",
            )
            logger.warning(
                "Refiner runtime error: mode=%s model=%s error=%s latency_ms=%.1f",
                mode,
                result.model_id,
                exc,
                (time.perf_counter() - start_time) * 1000.0,
            )
            return result

        refined = self._extract_refined_text(candidate)
        if not refined:
            result = RefinerResult(
                text=normalized,
                mode=mode,
                model_id=model_id,
                used_runtime=False,
                error="Refiner returned no usable text; using built-in cleanup only.",
            )
            logger.info(
                "Refiner fallback: mode=%s model=%s used_runtime=%s reason=%s latency_ms=%.1f",
                mode,
                result.model_id,
                result.used_runtime,
                result.error,
                (time.perf_counter() - start_time) * 1000.0,
            )
            return result

        if not self._placeholders_intact(refined, protected.placeholders):
            result = RefinerResult(
                text=normalized,
                mode=mode,
                model_id=model_id,
                used_runtime=False,
                error="Refiner output did not preserve protected placeholders; using original text.",
            )
            logger.info(
                "Refiner fallback: mode=%s model=%s used_runtime=%s reason=%s latency_ms=%.1f",
                mode,
                result.model_id,
                result.used_runtime,
                result.error,
                (time.perf_counter() - start_time) * 1000.0,
            )
            return result

        restored = self._restore_sensitive_tokens(refined, protected.placeholders)

        if self._is_unsafe_rewrite(normalized, restored):
            result = RefinerResult(
                text=normalized,
                mode=mode,
                model_id=model_id,
                used_runtime=False,
                error="Refiner output changed protected tokens too aggressively; using original text.",
            )
            logger.info(
                "Refiner fallback: mode=%s model=%s used_runtime=%s reason=%s latency_ms=%.1f",
                mode,
                result.model_id,
                result.used_runtime,
                result.error,
                (time.perf_counter() - start_time) * 1000.0,
            )
            return result

        result = RefinerResult(
            text=restored,
            mode=mode,
            model_id=model_id,
            used_runtime=True,
        )
        logger.info(
            "Refiner completed: mode=%s model=%s used_runtime=%s latency_ms=%.1f",
            mode,
            result.model_id,
            result.used_runtime,
            (time.perf_counter() - start_time) * 1000.0,
        )
        return result

    def _ensure_model(self, model_id: str):  # pragma: no cover - runtime/hardware dependent
        with self._lock:
            if self._llm is not None and self._loaded_model_id == model_id:
                return self._llm

            model_path = self._resolve_model_path(model_id)
            if model_path is None:
                raise RuntimeError(
                    f"Selected refiner model '{model_id}' is not installed in {self.download_root}."
                )

            if not LLAMA_CPP_AVAILABLE:
                raise RuntimeError(
                    "llama-cpp-python is not installed; refiner runtime is unavailable."
                )

            from llama_cpp import Llama

            entry = get_model_catalog_entry(model_id)
            runtime_config = entry.default_runtime_config if entry else {}
            threads = int(runtime_config.get("threads", max(2, (os.cpu_count() or 4) - 2)))
            gpu_layers = int(runtime_config.get("gpuLayers", 0))

            self._llm = Llama(
                model_path=str(model_path),
                n_ctx=4096,
                n_threads=threads,
                n_gpu_layers=gpu_layers,
                verbose=False,
            )
            self._loaded_model_id = model_id
            return self._llm

    def _resolve_model_path(self, model_id: str) -> Path | None:
        entry = get_model_catalog_entry(model_id)
        if entry is None:
            return None

        model_dir = self.download_root / entry.category / entry.id
        if not model_dir.exists():
            return None

        for artifact in entry.download_artifacts:
            candidate = model_dir / artifact.filename
            if candidate.exists():
                return candidate

        gguf_candidates = sorted(model_dir.glob("*.gguf"))
        if gguf_candidates:
            return gguf_candidates[0]
        return None

    def _extract_refined_text(self, text: str) -> str:
        candidate = (text or "").strip()
        if not candidate:
            return ""
        candidate = candidate.replace("</REFINED_TEXT>", "").replace("<END_REFINED_TEXT>", "")
        candidate = candidate.strip()
        if candidate.startswith("Refined text:"):
            candidate = candidate[len("Refined text:") :].strip()
        if candidate.startswith('"') and candidate.endswith('"') and len(candidate) > 1:
            candidate = candidate[1:-1].strip()
        return candidate

    def _is_unsafe_rewrite(self, original: str, refined: str) -> bool:
        original_tokens = self._protected_tokens(original)
        refined_tokens = self._protected_tokens(refined)
        if original_tokens != refined_tokens:
            return True

        original_words = original.split()
        refined_words = refined.split()
        if not original_words:
            return False

        word_delta = abs(len(refined_words) - len(original_words)) / len(original_words)
        if word_delta > 0.35:
            return True

        return False

    def _protect_sensitive_tokens(self, text: str) -> ProtectedText:
        patterns = [
            re.compile(r"\b\d+\.\d+(?:\.\d+)+\b"),
            re.compile(r"\b\d+\.\d+\b"),
            re.compile(r"\b\d+%\b"),
            re.compile(
                r"\b(?:Ctrl|Alt|Shift|Win|Meta|Cmd|CommandOrControl)(?:\+[A-Za-z0-9]+)+\b",
                re.IGNORECASE,
            ),
            re.compile(r"\b[A-Z]{2,}(?:[A-Z0-9._-]*[A-Z0-9])?\b"),
            re.compile(r"\b[a-zA-Z0-9._/-]{3,}\b"),
        ]
        placeholders: dict[str, str] = {}
        protected_text = text

        def replace_matches(pattern: re.Pattern[str], current_text: str) -> str:
            def _replacement(match: re.Match[str]) -> str:
                token = match.group(0)
                if PLACEHOLDER_TOKEN_RE.search(token):
                    return token
                for placeholder, existing_token in placeholders.items():
                    if existing_token == token:
                        return placeholder
                placeholder = f"[[KEEP_TOKEN_{len(placeholders):04d}]]"
                placeholders[placeholder] = token
                return placeholder

            parts = PLACEHOLDER_TOKEN_RE.split(current_text)
            rebuilt: list[str] = []
            for index, part in enumerate(parts):
                if index % 2 == 1:
                    rebuilt.append(f"[[KEEP_TOKEN_{part}]]")
                else:
                    rebuilt.append(pattern.sub(_replacement, part))
            return "".join(rebuilt)

        for pattern in patterns:
            protected_text = replace_matches(pattern, protected_text)

        return ProtectedText(protected_text=protected_text, placeholders=placeholders)

    def _placeholders_intact(self, text: str, placeholders: dict[str, str]) -> bool:
        if not placeholders:
            return True
        return all(text.count(placeholder) == 1 for placeholder in placeholders)

    def _restore_sensitive_tokens(self, text: str, placeholders: dict[str, str]) -> str:
        restored = text
        for placeholder, token in placeholders.items():
            restored = restored.replace(placeholder, token)
        return restored

    def _protected_tokens(self, text: str) -> list[str]:
        return [
            token.lower().strip(".,:;!?\"'()[]{}")
            for token in re.findall(
                r"[A-Za-z_]+\.[A-Za-z0-9_./-]+|[A-Za-z_][A-Za-z0-9_]*|[-+]?\d+(?:\.\d+)?(?:[A-Za-z/%]+)?",
                text,
            )
        ]

    def _call_llm(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        engine_preference: str,
        provider_base_url: str,
    ) -> str:
        if engine_preference in ("ollama", "lm_studio"):
            return self._call_provider(
                model_id=model_id,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                engine_preference=engine_preference,
                provider_base_url=provider_base_url,
            )
        return self._call_llama_cpp(
            model_id=model_id,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def _call_provider(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        engine_preference: str,
        provider_base_url: str,
    ) -> str:
        try:
            provider_type: ProviderType = engine_preference  # type: ignore
            provider = get_provider(provider_type, provider_base_url)
            import asyncio

            async def get_completion() -> str:
                return await provider.complete(
                    prompt=prompt,
                    model=model_id,
                    options={"max_tokens": max_tokens, "temperature": temperature},
                )

            return asyncio.run(get_completion())
        except Exception as exc:
            logger.warning(
                "Provider %s unavailable, falling back to llama_cpp: %s", engine_preference, exc
            )
            return self._call_llama_cpp(
                model_id=model_id,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )

    def _call_llama_cpp(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        llm = self._ensure_model(model_id)
        response = llm.create_completion(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["\n<END_REFINED_TEXT>", "\nUser:", "\nAssistant:"],
        )
        return (
            response.get("choices", [{}])[0].get("text", "") if isinstance(response, dict) else ""
        )

    async def check_provider_health(
        self, engine_preference: str | None = None, provider_base_url: str | None = None
    ) -> ProviderHealth:
        if engine_preference is None or provider_base_url is None:
            engine_preference, provider_base_url = self._get_settings()

        if engine_preference == "llamacpp":
            from app.api.providers import LlamaCPPProvider

            llama_cpp_provider = LlamaCPPProvider()
            return await llama_cpp_provider.health_check()

        if engine_preference in ("ollama", "lm_studio"):
            try:
                provider_type: ProviderType = engine_preference  # type: ignore
                from app.api.providers import BaseProvider

                http_provider: BaseProvider = get_provider(provider_type, provider_base_url)
                return await http_provider.health_check()
            except Exception as exc:
                return ProviderHealth(available=False, error=str(exc), response_time_ms=None)

        return ProviderHealth(
            available=False, error=f"Unknown engine: {engine_preference}", response_time_ms=None
        )
