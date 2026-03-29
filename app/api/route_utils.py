from __future__ import annotations

import asyncio
import inspect
import logging
import os
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def resolve_log_level_from_settings_payload(settings_payload: dict[str, Any]) -> str:
    advanced = settings_payload.get("advanced", {})
    configured = str(advanced.get("logLevel", "INFO") or "INFO").upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    return configured if configured in valid_levels else "INFO"


def resolve_runtime_log_level(settings_payload: dict[str, Any]) -> str:
    env_level = str(os.getenv("OPENWISPR_LOG_LEVEL", "") or "").upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if env_level in valid_levels:
        return env_level
    return resolve_log_level_from_settings_payload(settings_payload)


def apply_runtime_log_levels(log_level: str) -> None:
    resolved = str(log_level or "INFO").upper()
    if resolved not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        resolved = "INFO"
    logging.getLogger().setLevel(getattr(logging, resolved))
    logger.setLevel(getattr(logging, resolved))
    quiet_level = logging.DEBUG if resolved == "DEBUG" else logging.WARNING
    for noisy_logger in (
        "httpx",
        "httpcore",
        "faster_whisper",
        "ctranslate2",
        "uvicorn.access",
    ):
        logging.getLogger(noisy_logger).setLevel(quiet_level)


def log_route(method: str, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        func.__endpoint_path__ = path  # type: ignore[attr-defined]
        func.__http_method__ = method  # type: ignore[attr-defined]
        return log_endpoint(func)

    return decorator


_SIGNATURE_CACHE: dict[int, tuple[inspect.Signature, dict[str, Any]]] = {}


def log_endpoint(func):
    func_id = id(func)
    cached = _SIGNATURE_CACHE.get(func_id)
    if cached is not None:
        cached_signature, cached_annotations = cached
        is_async = asyncio.iscoroutinefunction(func)
    else:
        cached_annotations = inspect.get_annotations(func, eval_str=True)
        cached_signature = inspect.signature(func)
        is_async = asyncio.iscoroutinefunction(func)
        _SIGNATURE_CACHE[func_id] = (cached_signature, cached_annotations)

    if is_async:

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await _log_endpoint_call_async(func, args, kwargs)

        async_wrapper.__signature__ = cached_signature
        async_wrapper.__annotations__ = cached_annotations
        async_wrapper.__module__ = func.__module__
        return async_wrapper

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        return _log_endpoint_call_sync(func, args, kwargs)

    sync_wrapper.__signature__ = cached_signature
    sync_wrapper.__annotations__ = cached_annotations
    sync_wrapper.__module__ = func.__module__
    return sync_wrapper


_SENSITIVE_FIELDS = frozenset(
    {
        "password",
        "token",
        "secret",
        "api_key",
        "apikey",
        "api_secret",
        "access_token",
        "refresh_token",
        "private_key",
        "client_secret",
        "credential",
        "auth",
        "authorization",
    }
)


def _get_request_info(kwargs: dict[str, Any]) -> dict[str, Any]:
    request_info: dict[str, Any] = {}
    for key, value in kwargs.items():
        if key == "request" and hasattr(value, "dict"):
            try:
                req_dict = value.dict()
                request_info = {
                    k: v for k, v in req_dict.items() if k.lower() not in _SENSITIVE_FIELDS
                }
            except Exception:
                logger.warning(
                    "Failed to extract request info from %s | operation=get_request_dict",
                    type(value).__name__,
                )
                request_info = {"type": type(value).__name__}
        elif key in ("device_id", "model_name", "duration"):
            request_info[key] = str(value)
    return request_info


def _get_client_info() -> str:
    return "local"


def _log_endpoint_call_sync(func, args, kwargs):
    start_time = time.perf_counter()
    endpoint_name = func.__name__
    endpoint_path = getattr(func, "__endpoint_path__", "unknown")
    http_method = getattr(func, "__http_method__", "unknown")
    request_info = _get_request_info(kwargs)
    client_info = _get_client_info()

    logger.debug(
        "API endpoint invoked: %s %s (func=%s) | client=%s | params=%s",
        http_method,
        endpoint_path,
        endpoint_name,
        client_info,
        request_info,
    )

    try:
        result = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        status_code = 200
        response_size = 0
        if hasattr(result, "status_code"):
            status_code = result.status_code
        if hasattr(result, "body"):
            response_size = len(result.body) if result.body else 0
        elif isinstance(result, dict):
            response_size = len(str(result))
        logger.debug(
            "API endpoint completed: %s %s | status=%s | size=%s bytes | time=%.2fms",
            http_method,
            endpoint_path,
            status_code,
            response_size,
            elapsed_ms,
        )
        return result
    except HTTPException as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.warning(
            "API endpoint HTTP error: %s %s | status=%s | detail=%s | time=%.2fms",
            http_method,
            endpoint_path,
            exc.status_code,
            exc.detail,
            elapsed_ms,
        )
        raise
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        error_id = getattr(exc, "error_id", None)
        logger.error(
            "API endpoint exception: %s %s | error=%s | time=%.2fms",
            http_method,
            endpoint_path,
            str(exc),
            elapsed_ms,
            extra={"error_id": error_id, "exception_type": type(exc).__name__},
            exc_info=True,
        )
        raise


async def _log_endpoint_call_async(func, args, kwargs):
    start_time = time.perf_counter()
    endpoint_name = func.__name__
    endpoint_path = getattr(func, "__endpoint_path__", "unknown")
    http_method = getattr(func, "__http_method__", "unknown")
    request_info = _get_request_info(kwargs)
    client_info = _get_client_info()

    logger.debug(
        "API endpoint invoked: %s %s (func=%s) | client=%s | params=%s",
        http_method,
        endpoint_path,
        endpoint_name,
        client_info,
        request_info,
    )

    try:
        result = await func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        status_code = 200
        response_size = 0
        if hasattr(result, "status_code"):
            status_code = result.status_code
        if hasattr(result, "body"):
            response_size = len(result.body) if result.body else 0
        elif isinstance(result, dict):
            response_size = len(str(result))
        logger.debug(
            "API endpoint completed: %s %s | status=%s | size=%s bytes | time=%.2fms",
            http_method,
            endpoint_path,
            status_code,
            response_size,
            elapsed_ms,
        )
        return result
    except HTTPException as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.warning(
            "API endpoint HTTP error: %s %s | status=%s | detail=%s | time=%.2fms",
            http_method,
            endpoint_path,
            exc.status_code,
            exc.detail,
            elapsed_ms,
        )
        raise
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        error_id = getattr(exc, "error_id", None)
        logger.error(
            "API endpoint exception: %s %s | error=%s | time=%.2fms",
            http_method,
            endpoint_path,
            str(exc),
            elapsed_ms,
            extra={"error_id": error_id, "exception_type": type(exc).__name__},
            exc_info=True,
        )
        raise
