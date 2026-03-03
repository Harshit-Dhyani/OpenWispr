from __future__ import annotations

import logging
import os
import re
import time
from importlib.util import find_spec
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from app.core.model_catalog import get_model_catalog_entry

logger = logging.getLogger(__name__)
LLAMA_CPP_AVAILABLE = find_spec("llama_cpp") is not None


def is_llama_cpp_available() -> bool:
    return LLAMA_CPP_AVAILABLE


@dataclass(slots=True)
class RefinerResult:
    text: str
    mode: str
    model_id: str | None
    used_runtime: bool
    error: str | None = None


class RefinerService:
    def __init__(self, download_root: Path) -> None:
        self.download_root = Path(download_root)
        self._lock = Lock()
        self._loaded_model_id: str | None = None
        self._llm: Any | None = None

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
        model_id: str | None,
        runtime_enabled: bool,
        language_hint: str = "auto",
        cleanup_instructions: str = "",
    ) -> RefinerResult:
        start_time = time.perf_counter()
        normalized = (text or "").strip()
        if not normalized or mode == "off":
            result = RefinerResult(
                text=normalized,
                mode="off",
                model_id=model_id,
                used_runtime=False,
            )
            logger.info(
                "Refiner skipped: mode=%s model=%s used_runtime=%s reason=%s latency_ms=%.1f",
                "off",
                result.model_id,
                result.used_runtime,
                "mode_off_or_empty",
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

        try:
            llm = self._ensure_model(model_id)
        except Exception as exc:  # pragma: no cover - runtime/hardware dependent
            result = RefinerResult(
                text=normalized,
                mode=mode,
                model_id=model_id,
                used_runtime=False,
                error=str(exc),
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

        prompt = self._build_prompt(
            normalized,
            mode=mode,
            language_hint=language_hint,
            cleanup_instructions=cleanup_instructions,
        )
        temperature = 0.05 if mode == "strict" else 0.2
        max_tokens = min(1024, max(192, len(normalized.split()) * 6))

        try:
            response = llm.create_completion(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=["\n<END_REFINED_TEXT>", "\nUser:", "\nAssistant:"],
            )
            candidate = (
                response.get("choices", [{}])[0].get("text", "") if isinstance(response, dict) else ""
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

        if self._is_unsafe_rewrite(normalized, refined):
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
            text=refined,
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

    def _build_prompt(
        self, text: str, *, mode: str, language_hint: str, cleanup_instructions: str = ""
    ) -> str:
        if mode == "strict":
            instruction = (
                "Correct punctuation, capitalization, spacing, and paragraphing only. "
                "Do not change meaning. Do not summarize, add, remove, or reorder facts. "
                "Preserve numbers, units, formulas, code tokens, identifiers, filenames, product names, and technical terms exactly."
            )
        else:
            instruction = (
                "Polish the transcript for readability while preserving meaning exactly. "
                "Do not summarize, add, remove, or reorder facts. "
                "Preserve numbers, units, formulas, code tokens, identifiers, filenames, product names, and technical terms exactly."
            )

        extra_instructions = cleanup_instructions.strip()

        prompt = (
            "You are a transcript refiner.\n"
            f"Language hint: {language_hint}.\n"
            f"Task: {instruction}\n"
            "Return only the refined transcript text.\n"
            "If the transcript already looks correct, return it unchanged.\n"
        )
        if extra_instructions:
            prompt += (
                "Additional cleanup instructions for final text only:\n"
                f"{extra_instructions}\n"
            )
        prompt += (
            "<TRANSCRIPT>\n"
            f"{text}\n"
            "</TRANSCRIPT>\n"
            "<REFINED_TEXT>\n"
        )
        return prompt

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

    def _protected_tokens(self, text: str) -> list[str]:
        return [
            token.lower().strip(".,:;!?\"'()[]{}")
            for token in re.findall(
                r"[A-Za-z_]+\.[A-Za-z0-9_./-]+|[A-Za-z_][A-Za-z0-9_]*|[-+]?\d+(?:\.\d+)?(?:[A-Za-z/%]+)?",
                text,
            )
        ]
