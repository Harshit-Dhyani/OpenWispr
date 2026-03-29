"""Logging configuration utilities for OpenWispr.

Provides JSON formatting and structured logging setup for the application.
Used by the core logging system for consistent log output across the app.
"""

from __future__ import annotations

import contextvars
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


_log_error_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "log_error_context", default={}
)


def set_log_context(**kwargs: Any) -> None:
    """Set context variables for the current log scope."""
    current = _log_error_context.get()
    _log_error_context.set({**current, **kwargs})


def get_log_context() -> dict[str, Any]:
    """Get current log context variables."""
    return _log_error_context.get()


def clear_log_context() -> None:
    """Clear log context variables."""
    _log_error_context.set({})


class StructuredLogFilter(logging.Filter):
    """Filter that adds context variables to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        context = get_log_context()
        for key, value in context.items():
            setattr(record, key, value)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        standard_attrs = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "asctime",
            "message",
            "getMessage",
        }

        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


class ErrorTrackingFormatter(JsonFormatter):
    """Formatter that adds error correlation IDs to log entries."""

    ERROR_ID_ATTRS = frozenset({"error_id", "error_category", "error_severity", "correlation_id"})

    def format(self, record: logging.LogRecord) -> str:
        context = get_log_context()
        for key, value in context.items():
            if key not in record.__dict__:
                setattr(record, key, value)

        return super().format(record)


def configure_logging(
    log_dir: Path,
    level: str,
    enable_structured_filter: bool = True,
) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("openwispr")
    level_int = getattr(logging, str(level).upper(), logging.INFO)
    logger.setLevel(level_int)
    logger.handlers.clear()

    if enable_structured_filter:
        formatter = ErrorTrackingFormatter()
        structured_filter = StructuredLogFilter()
    else:
        formatter = JsonFormatter()
        structured_filter = None

    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    if structured_filter:
        file_handler.addFilter(structured_filter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    if structured_filter:
        console_handler.addFilter(structured_filter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False
    return logger


def configure_error_logging(log_dir: Path) -> logging.Logger:
    """Configure dedicated error logging with error tracking."""
    log_dir.mkdir(parents=True, exist_ok=True)
    error_logger = logging.getLogger("openwispr.errors")
    error_logger.setLevel(logging.ERROR)
    error_logger.handlers.clear()

    error_handler = RotatingFileHandler(
        log_dir / "errors.log",
        maxBytes=1_000_000,
        backupCount=10,
        encoding="utf-8",
    )
    error_handler.setFormatter(ErrorTrackingFormatter())
    error_handler.addFilter(StructuredLogFilter())
    error_logger.addHandler(error_handler)
    error_logger.propagate = False

    return error_logger


def get_openwispr_logger() -> logging.Logger:
    """Get the main openwispr logger, creating handlers if needed."""
    logger = logging.getLogger("openwispr")
    if not logger.handlers:
        root_handlers = logging.getLogger().handlers
        if root_handlers:
            for handler in root_handlers:
                logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
