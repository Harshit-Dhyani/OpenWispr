"""LLM-powered English coaching and transcript refinement service.

Provides CoachService for analyzing transcripts and suggesting improvements.
Uses configurable LLM providers (llama.cpp, OpenAI, etc.) with caching for
performance. Returns structured corrections with diffs, mistakes, and practice suggestions.

This service is optional - falls back gracefully when no LLM provider is available.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.api.coach_cache import CoachCache
from app.api.providers import ProviderHealth, ProviderType, get_provider
from app.config.coach_prompts import (
    DEFAULT_COACH_TEMPLATE,
    DEFAULT_COACH_TEMPLATE_ID,
    compile_coach_prompt,
    get_default_coach_templates,
)
from app.config.constants import ProviderConstants
from app.core.model_catalog import get_model_catalog_entry
from app.core.settings.manager import get_settings_manager

logger = logging.getLogger(__name__)

try:
    from llama_cpp import Llama  # type: ignore
except Exception:  # pragma: no cover - optional runtime
    Llama = None  # type: ignore


class CoachDiffOp(BaseModel):
    op: Literal["delete", "insert", "replace"]
    from_: str = Field(alias="from")
    to: str
    start: int
    end: int

    model_config = {"populate_by_name": True}


class CoachMistake(BaseModel):
    type: Literal["grammar", "wording", "tense", "article", "preposition", "clarity"]
    example: str
    fix: str
    why: str


class CoachPractice(BaseModel):
    prompt: str = ""
    answer: str = ""


class CoachMeta(BaseModel):
    model: str = "none"
    confidence: float = 0.0
    cache_hit: bool = False
    provider: str = "fallback"
    prompt_template_id: str = DEFAULT_COACH_TEMPLATE_ID
    prompt_version: int = 1


class CoachResult(BaseModel):
    original: str
    polished: str
    diff: list[CoachDiffOp] = Field(default_factory=list)
    tips: list[str] = Field(default_factory=list)
    mistakes: list[CoachMistake] = Field(default_factory=list)
    practice: CoachPractice = Field(default_factory=CoachPractice)
    meta: CoachMeta = Field(default_factory=CoachMeta)


@dataclass(slots=True)
class CoachRequestContext:
    text: str
    language_mode: str
    detail_level: Literal["compact", "standard", "deep"]
    capture_source: Literal["microphone", "system"]
    template_id: str
    overrides: dict[str, Any]
    privacy_mode: Literal["local_only", "allow_llm"]
    runtime_enabled: bool
    model_id: str | None
    custom_user_template: str = ""
    templates: list[dict[str, Any]] | None = None


class CoachService:
    """LLM-powered English coaching service for transcript improvement.

    Analyzes transcripts and suggests improvements using configurable LLM providers
    (llama.cpp, Ollama, LM Studio). Returns structured corrections with diffs,
    mistakes, and practice suggestions.

    State ownership:
    - CoachCache for response caching (file-based)
    - Lazy-loaded LLM model (llama.cpp)
    - Lock-protected model loading

    Fallback behavior:
    - Returns fallback result when runtime unavailable
    - Falls back gracefully when no LLM provider is available
    """

    def __init__(self, download_root: Path, cache_path: Path) -> None:
        self.download_root = Path(download_root)
        self._cache = CoachCache(cache_path)
        self._lock = Lock()
        self._llm: Any | None = None
        self._loaded_model_id: str | None = None
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
            engine_preference = getattr(settings.coach, "coach_engine_preference", "llamacpp")
            provider_base_url = (
                settings.coach.coach_provider_base_url
                if hasattr(settings, "coach")
                else ProviderConstants.DEFAULT_OLLAMA_URL
            )
            return engine_preference, provider_base_url
        except Exception:
            return self._engine_preference, self._provider_base_url

    def generate(self, context: CoachRequestContext, *, fallback_text: str) -> CoachResult:
        template = self._resolve_template(context.template_id, context.templates)
        compiled = compile_coach_prompt(
            template=template,
            original_text=context.text,
            language_mode=context.language_mode,
            detail_level=context.detail_level,
            overrides=context.overrides,
            custom_user_template=context.custom_user_template,
        )
        cache_key = self._cache.build_key(
            context.text,
            fallback_text,
            context.language_mode,
            context.detail_level,
            compiled["resolved_template_id"],
            compiled["resolved_template_version"],
            json.dumps(context.overrides, ensure_ascii=True, sort_keys=True),
            context.privacy_mode,
        )

        cached = self._cache.get(cache_key)
        if cached is not None:
            result = CoachResult.model_validate(cached["result"])
            result.meta.cache_hit = True
            result.meta.provider = "cache"
            return self._normalize_result(result, context.text)

        if context.privacy_mode == "local_only":
            result = self._fallback_result(
                original=context.text,
                polished=fallback_text,
                provider="disabled_local_only",
                template_id=str(compiled["resolved_template_id"]),
                template_version=int(compiled["resolved_template_version"]),
                model=context.model_id or "none",
            )
            self._cache.put(cache_key, {"result": result.model_dump(by_alias=True)})
            return result

        if not context.runtime_enabled or not context.model_id:
            return self._fallback_result(
                original=context.text,
                polished=fallback_text,
                provider="fallback_runtime_unavailable",
                template_id=str(compiled["resolved_template_id"]),
                template_version=int(compiled["resolved_template_version"]),
                model=context.model_id or "none",
            )

        try:
            engine_preference, provider_base_url = self._get_settings()
            candidate = self._call_llm(
                model_id=context.model_id,
                prompt=f"{compiled['system_prompt']}\n\n{compiled['user_prompt']}\n",
                max_tokens=min(1400, max(384, len(context.text.split()) * 12)),
                temperature=0.05,
                engine_preference=engine_preference,
                provider_base_url=provider_base_url,
            )
            result = self._parse_candidate(
                candidate,
                original=context.text,
                fallback_text=fallback_text,
                template_id=str(compiled["resolved_template_id"]),
                template_version=int(compiled["resolved_template_version"]),
                model=context.model_id,
            )
            self._cache.put(cache_key, {"result": result.model_dump(by_alias=True)})
            return result
        except Exception as exc:
            logger.warning("Coach generation failed: %s", exc)
            return self._fallback_result(
                original=context.text,
                polished=fallback_text,
                provider="fallback_error",
                template_id=str(compiled["resolved_template_id"]),
                template_version=int(compiled["resolved_template_version"]),
                model=context.model_id or "none",
            )

    def prompt_preview(self, context: CoachRequestContext) -> dict[str, Any]:
        template = self._resolve_template(context.template_id, context.templates)
        compiled = compile_coach_prompt(
            template=template,
            original_text=context.text,
            language_mode=context.language_mode,
            detail_level=context.detail_level,
            overrides=context.overrides,
            custom_user_template=context.custom_user_template,
        )
        return {
            **compiled,
            "warnings": [],
        }

    def _resolve_template(
        self,
        template_id: str,
        templates: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        for template in templates or get_default_coach_templates():
            if template.get("id") == template_id and template.get("enabled", True):
                return template
        return DEFAULT_COACH_TEMPLATE.to_dict()

    def _parse_candidate(
        self,
        candidate: str,
        *,
        original: str,
        fallback_text: str,
        template_id: str,
        template_version: int,
        model: str,
    ) -> CoachResult:
        cleaned = (candidate or "").strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()

        # Try to extract just the JSON if there's extra text after it
        json_start = cleaned.find("{")
        json_end = cleaned.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            extracted = cleaned[json_start:json_end]
        else:
            extracted = cleaned

        try:
            parsed = json.loads(extracted)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse coach response as JSON: {e}")
            return self._fallback_result(
                original=original or "",
                polished=fallback_text or original or "",
                provider="fallback_parse_error",
                template_id=template_id or "unknown",
                template_version=template_version or 1,
                model=model or "unknown",
            )

        # Handle case where parsed is not a dict
        if not isinstance(parsed, dict):
            logger.warning(f"Coach response is not a dict: {type(parsed)}")
            return self._fallback_result(
                original=original or "",
                polished=fallback_text or original or "",
                provider="fallback_invalid_response",
                template_id=template_id or "unknown",
                template_version=template_version or 1,
                model=model or "unknown",
            )

        try:
            result = CoachResult.model_validate(parsed)
        except Exception as e:
            logger.warning(f"Coach validation failed: {e}, parsed={parsed}")
            return self._fallback_result(
                original=original or "",
                polished=fallback_text or original or "",
                provider="fallback_validation_error",
                template_id=template_id or "unknown",
                template_version=template_version or 1,
                model=model or "unknown",
            )
        if not result.original.strip():
            result.original = original
        if not result.polished.strip():
            result.polished = fallback_text
        result.meta.model = model
        result.meta.provider = "local_llm"
        result.meta.prompt_template_id = template_id
        result.meta.prompt_version = template_version
        result.meta.cache_hit = False
        return self._normalize_result(result, original)

    def _normalize_result(self, result: CoachResult, original: str) -> CoachResult:
        result.original = original
        result.polished = result.polished.strip() or original
        result.meta.confidence = max(0.0, min(1.0, float(result.meta.confidence or 0.0)))
        result.tips = [tip.strip() for tip in result.tips if tip.strip()][:5]
        result.mistakes = result.mistakes[:5]
        result.diff = self._build_diff(original, result.polished)
        return result

    def _fallback_result(
        self,
        *,
        original: str,
        polished: str,
        provider: str,
        template_id: str,
        template_version: int,
        model: str,
    ) -> CoachResult:
        return CoachResult(
            original=original,
            polished=polished,
            diff=self._build_diff(original, polished),
            tips=[],
            mistakes=[],
            practice=CoachPractice(),
            meta=CoachMeta(
                model=model,
                confidence=0.0,
                cache_hit=False,
                provider=provider,
                prompt_template_id=template_id,
                prompt_version=template_version,
            ),
        )

    def _build_diff(self, original: str, polished: str) -> list[CoachDiffOp]:
        matcher = SequenceMatcher(None, original, polished)
        ops: list[CoachDiffOp] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            op: Literal["delete", "insert", "replace"]
            if tag == "delete":
                op = "delete"
            elif tag == "insert":
                op = "insert"
            else:
                op = "replace"
            ops.append(
                CoachDiffOp(
                    op=op,
                    **{
                        "from": original[i1:i2],
                        "to": polished[j1:j2],
                        "start": i1,
                        "end": i2,
                    },
                )
            )
        return ops

    def _ensure_model(self, model_id: str):  # pragma: no cover - runtime/hardware dependent
        with self._lock:
            if self._llm is not None and self._loaded_model_id == model_id:
                return self._llm
            if Llama is None:
                raise RuntimeError("llama-cpp-python is not installed")
            entry = get_model_catalog_entry(model_id)
            if entry is None:
                raise RuntimeError(f"Unknown coach model: {model_id}")
            model_dir = self.download_root / entry.category / entry.id
            if not model_dir.exists():
                raise RuntimeError(f"Coach model '{model_id}' is not installed")
            model_path = next(model_dir.glob("*.gguf"), None)
            if model_path is None:
                raise RuntimeError(f"Coach model '{model_id}' has no GGUF file")
            runtime_config = entry.default_runtime_config if entry else {}
            self._llm = Llama(
                model_path=str(model_path),
                n_ctx=4096,
                n_threads=int(runtime_config.get("threads", 4)),
                n_gpu_layers=int(runtime_config.get("gpuLayers", 0)),
                verbose=False,
            )
            self._loaded_model_id = model_id
            return self._llm

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
            stop=["```", "\n\nOriginal transcript:"],
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
