from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest


def import_first(candidates: list[str]):
    for module_name in candidates:
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
    pytest.skip(f"Implementation module not found. Tried: {', '.join(candidates)}")


def resolve_symbol(module_candidates: list[str], symbol_candidates: list[str]) -> Any:
    module = import_first(module_candidates)
    for symbol_name in symbol_candidates:
        if hasattr(module, symbol_name):
            return getattr(module, symbol_name)
    pytest.skip(
        "Implementation symbol not found. "
        f"Module: {module.__name__}. Tried: {', '.join(symbol_candidates)}"
    )


def filtered_call(target: Any, /, *args: Any, **kwargs: Any) -> Any:
    signature = inspect.signature(target)
    accepted: dict[str, Any] = {}

    for name, parameter in signature.parameters.items():
        if parameter.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if name in kwargs:
            accepted[name] = kwargs[name]

    return target(*args, **accepted)


def instantiate(target: Any, **kwargs: Any) -> Any:
    if inspect.isclass(target):
        return filtered_call(target, **kwargs)
    return target


def first_method(instance: Any, candidates: list[str]) -> Any:
    for method_name in candidates:
        if hasattr(instance, method_name):
            return getattr(instance, method_name)
    pytest.skip(
        f"Implementation method not found on {type(instance).__name__}. "
        f"Tried: {', '.join(candidates)}"
    )


def chunk_text(chunk: Any) -> str:
    if isinstance(chunk, str):
        return chunk
    if isinstance(chunk, dict):
        if isinstance(chunk.get("text"), str):
            return chunk["text"]
        if isinstance(chunk.get("content"), str):
            return chunk["content"]
        if isinstance(chunk.get("segments"), list):
            return " ".join(segment_text(item) for item in chunk["segments"]).strip()
    for attr in ("text", "content"):
        value = getattr(chunk, attr, None)
        if isinstance(value, str):
            return value
    segments = getattr(chunk, "segments", None)
    if isinstance(segments, list):
        return " ".join(segment_text(item) for item in segments).strip()
    raise AssertionError(f"Unable to extract text from chunk: {chunk!r}")


def segment_text(segment: Any) -> str:
    if isinstance(segment, str):
        return segment
    if isinstance(segment, dict):
        return str(segment.get("text", "")).strip()
    return str(getattr(segment, "text", "")).strip()


def formula_text(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("formula", "text", "expression", "latex"):
            if isinstance(item.get(key), str):
                return item[key]
    for attr in ("formula", "text", "expression", "latex"):
        value = getattr(item, attr, None)
        if isinstance(value, str):
            return value
    raise AssertionError(f"Unable to extract formula text from: {item!r}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")
