"""Central error handling system for OpenWispr.

Provides structured error types, centralized error dispatch, user notification,
and crash reporting with full stack trace preservation.
"""

from __future__ import annotations

import enum
import logging
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional, Union

from app.core.logging_utils import JsonFormatter

logger = logging.getLogger("openwispr.errors")


# ============================================
# Error Severity Levels
# ============================================
class ErrorSeverity(enum.IntEnum):
    """Error severity levels for prioritization and handling."""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    FATAL = 60


# ============================================
# Error Categories
# ============================================
class ErrorCategory(enum.Enum):
    """Categorized error types for targeted recovery."""

    # Audio errors
    AUDIO_DEVICE_DISCONNECTED = "audio_device_disconnected"
    AUDIO_PERMISSION_DENIED = "audio_permission_denied"
    AUDIO_BACKEND_FAILURE = "audio_backend_failure"
    AUDIO_CAPTURE_ERROR = "audio_capture_error"

    # Model errors
    MODEL_OOM = "model_out_of_memory"
    MODEL_NOT_FOUND = "model_not_found"
    MODEL_CORRUPTED = "model_corrupted"
    MODEL_LOAD_FAILED = "model_load_failed"
    MODEL_INFERENCE_ERROR = "model_inference_error"

    # Network errors
    NETWORK_BACKEND_UNAVAILABLE = "network_backend_unavailable"
    NETWORK_SYNC_FAILED = "network_sync_failed"
    NETWORK_TIMEOUT = "network_timeout"
    NETWORK_CONNECTION_ERROR = "network_connection_error"

    # Session errors
    SESSION_DISK_FULL = "session_disk_full"
    SESSION_WRITE_PERMISSION = "session_write_permission"
    SESSION_CORRUPTED = "session_corrupted"
    SESSION_NOT_FOUND = "session_not_found"

    # System errors
    SYSTEM_RESOURCE_EXHAUSTED = "system_resource_exhausted"
    SYSTEM_CONFIG_ERROR = "system_config_error"
    SYSTEM_UNKNOWN = "system_unknown"


# ============================================
# Structured Error Types
# ============================================
@dataclass
class AppError(Exception):
    """Base application error with structured metadata."""

    message: str
    category: ErrorCategory = ErrorCategory.SYSTEM_UNKNOWN
    severity: ErrorSeverity = ErrorSeverity.ERROR
    code: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)
    cause: Optional[BaseException] = None
    recoverable: bool = True
    retry_allowed: bool = True
    max_retries: int = 3
    error_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stack_trace: Optional[str] = None

    def __post_init__(self):
        super().__init__(self.message)
        if self.stack_trace is None and self.cause:
            self.stack_trace = "".join(
                traceback.format_exception(type(self.cause), self.cause, self.cause.__traceback__)
            )
        elif self.stack_trace is None:
            self.stack_trace = traceback.format_stack()[:-1]

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_id": self.error_id,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.name,
            "code": self.code,
            "details": self.details,
            "recoverable": self.recoverable,
            "retry_allowed": self.retry_allowed,
            "max_retries": self.max_retries,
            "timestamp": self.timestamp.isoformat(),
            "stack_trace": self.stack_trace,
        }

    def __str__(self) -> str:
        return f"[{self.error_id}] {self.category.value}: {self.message}"


@dataclass
class AudioError(AppError):
    """Audio-related error with device information."""

    device_id: Optional[str] = None
    device_name: Optional[str] = None
    backend: Optional[str] = None

    def __post_init__(self):
        if self.category not in {
            ErrorCategory.AUDIO_DEVICE_DISCONNECTED,
            ErrorCategory.AUDIO_PERMISSION_DENIED,
            ErrorCategory.AUDIO_BACKEND_FAILURE,
            ErrorCategory.AUDIO_CAPTURE_ERROR,
        }:
            self.category = ErrorCategory.AUDIO_CAPTURE_ERROR
        super().__post_init__()


@dataclass
class ModelError(AppError):
    """Model-related error with model information."""

    model_name: Optional[str] = None
    model_path: Optional[str] = None
    compute_type: Optional[str] = None
    device: Optional[str] = None

    def __post_init__(self):
        if self.category not in {
            ErrorCategory.MODEL_OOM,
            ErrorCategory.MODEL_NOT_FOUND,
            ErrorCategory.MODEL_CORRUPTED,
            ErrorCategory.MODEL_LOAD_FAILED,
            ErrorCategory.MODEL_INFERENCE_ERROR,
        }:
            self.category = ErrorCategory.MODEL_LOAD_FAILED
        super().__post_init__()


@dataclass
class NetworkError(AppError):
    """Network-related error with endpoint information."""

    endpoint: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None
    response_body: Optional[str] = None

    def __post_init__(self):
        if self.category not in {
            ErrorCategory.NETWORK_BACKEND_UNAVAILABLE,
            ErrorCategory.NETWORK_SYNC_FAILED,
            ErrorCategory.NETWORK_TIMEOUT,
            ErrorCategory.NETWORK_CONNECTION_ERROR,
        }:
            self.category = ErrorCategory.NETWORK_CONNECTION_ERROR
        super().__post_init__()


@dataclass
class SessionError(AppError):
    """Session-related error with file information."""

    session_id: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    available_space: Optional[int] = None

    def __post_init__(self):
        if self.category not in {
            ErrorCategory.SESSION_DISK_FULL,
            ErrorCategory.SESSION_WRITE_PERMISSION,
            ErrorCategory.SESSION_CORRUPTED,
            ErrorCategory.SESSION_NOT_FOUND,
        }:
            self.category = ErrorCategory.SESSION_NOT_FOUND
        super().__post_init__()


# Type alias for all error types
OpenWisprError = Union[AppError, AudioError, ModelError, NetworkError, SessionError]


# ============================================
# User-Friendly Messages
# ============================================
USER_MESSAGES: dict[ErrorCategory, dict[str, str]] = {
    ErrorCategory.AUDIO_DEVICE_DISCONNECTED: {
        "title": "Audio Device Disconnected",
        "message": "Your audio device was disconnected. Switching to default device.",
        "action": "Please check your audio device connection.",
    },
    ErrorCategory.AUDIO_PERMISSION_DENIED: {
        "title": "Microphone Access Denied",
        "message": "OpenWispr needs microphone access to transcribe audio.",
        "action": "Please grant microphone permission in your system settings.",
    },
    ErrorCategory.AUDIO_BACKEND_FAILURE: {
        "title": "Audio System Error",
        "message": "The audio backend encountered an error.",
        "action": "Please restart the application or check your audio drivers.",
    },
    ErrorCategory.MODEL_OOM: {
        "title": "Out of Memory",
        "message": "The transcription model ran out of memory.",
        "action": "Switching to CPU mode with reduced settings. Performance may be slower.",
    },
    ErrorCategory.MODEL_NOT_FOUND: {
        "title": "Model Not Found",
        "message": "The requested transcription model is not available.",
        "action": "Downloading the model now. This may take a few minutes.",
    },
    ErrorCategory.MODEL_CORRUPTED: {
        "title": "Model Corrupted",
        "message": "The transcription model file appears to be corrupted.",
        "action": "Re-downloading the model to fix the issue.",
    },
    ErrorCategory.MODEL_LOAD_FAILED: {
        "title": "Model Load Failed",
        "message": "Failed to load the transcription model.",
        "action": "Trying fallback model. Quality may be reduced temporarily.",
    },
    ErrorCategory.NETWORK_BACKEND_UNAVAILABLE: {
        "title": "Backend Unavailable",
        "message": "The transcription backend is not responding.",
        "action": "Retrying connection. You can continue working offline.",
    },
    ErrorCategory.NETWORK_SYNC_FAILED: {
        "title": "Sync Failed",
        "message": "Could not synchronize your settings with the cloud.",
        "action": "Changes are saved locally and will sync when connection is restored.",
    },
    ErrorCategory.SESSION_DISK_FULL: {
        "title": "Disk Full",
        "message": "Your disk is full. Recording has been paused.",
        "action": "Please free up some disk space to continue recording.",
    },
    ErrorCategory.SESSION_WRITE_PERMISSION: {
        "title": "Write Permission Denied",
        "message": "Cannot save session to the selected location.",
        "action": "Please choose a different folder or check folder permissions.",
    },
    ErrorCategory.SESSION_CORRUPTED: {
        "title": "Session Corrupted",
        "message": "Your session file appears to be corrupted.",
        "action": "Attempting to recover available data. Some content may be lost.",
    },
    ErrorCategory.SYSTEM_UNKNOWN: {
        "title": "Unexpected Error",
        "message": "An unexpected error occurred.",
        "action": "Please try again or restart the application.",
    },
}


# ============================================
# User Notifier
# ============================================
class UserNotifier:
    """Handles user-facing error notifications with severity-based filtering."""

    def __init__(
        self,
        min_severity: ErrorSeverity = ErrorSeverity.WARNING,
        callback: Optional[Callable[[dict[str, str]], None]] = None,
    ):
        self.min_severity = min_severity
        self.callback = callback
        self._notification_history: list[dict[str, Any]] = []
        self._suppressed_categories: set[ErrorCategory] = set()

    def notify(self, error: OpenWisprError) -> None:
        """Notify user of an error if severity meets threshold."""
        if error.severity < self.min_severity:
            logger.debug(f"Suppressed notification for {error.error_id} (below threshold)")
            return

        if error.category in self._suppressed_categories:
            logger.debug(f"Suppressed notification for {error.error_id} (category suppressed)")
            return

        message_data = self._format_message(error)
        self._notification_history.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_id": error.error_id,
                "data": message_data,
            }
        )

        logger.info(f"User notification: {message_data['title']}")

        if self.callback:
            try:
                self.callback(message_data)
            except Exception as e:
                logger.error(f"Notification callback failed: {e}")

    def _format_message(self, error: OpenWisprError) -> dict[str, str]:
        """Format error into user-friendly message."""
        template = USER_MESSAGES.get(error.category, USER_MESSAGES[ErrorCategory.SYSTEM_UNKNOWN])

        message = template["message"]
        action = template["action"]

        # Add error-specific details
        if isinstance(error, ModelError) and error.model_name:
            message = f"{message} (Model: {error.model_name})"
        elif isinstance(error, AudioError) and error.device_name:
            message = f"{message} (Device: {error.device_name})"
        elif isinstance(error, SessionError) and error.file_path:
            message = f"{message} (File: {Path(error.file_path).name})"

        return {
            "error_id": error.error_id,
            "severity": error.severity.name,
            "title": template["title"],
            "message": message,
            "action": action,
            "recoverable": str(error.recoverable),
        }

    def suppress_category(
        self, category: ErrorCategory, duration_seconds: Optional[float] = None
    ) -> None:
        """Temporarily suppress notifications for a category."""
        self._suppressed_categories.add(category)
        logger.debug(f"Suppressed notifications for {category.value}")

    def restore_category(self, category: ErrorCategory) -> None:
        """Restore notifications for a category."""
        self._suppressed_categories.discard(category)
        logger.debug(f"Restored notifications for {category.value}")

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get notification history."""
        return self._notification_history[-limit:]

    def clear_history(self) -> None:
        """Clear notification history."""
        self._notification_history.clear()


# ============================================
# Error Reporter (Telemetry)
# ============================================
class ErrorReporter:
    """Handles error telemetry and crash reporting."""

    def __init__(
        self,
        report_dir: Optional[Path] = None,
        enable_telemetry: bool = True,
        enable_crash_dumps: bool = True,
    ):
        self.report_dir = report_dir or Path.home() / ".openwispr" / "reports"
        self.enable_telemetry = enable_telemetry
        self.enable_crash_dumps = enable_crash_dumps
        self._error_counts: dict[ErrorCategory, int] = {}
        self._session_start = datetime.now(timezone.utc)

        if self.enable_crash_dumps:
            self.report_dir.mkdir(parents=True, exist_ok=True)

    def report(
        self, error: OpenWisprError, context: Optional[dict[str, Any]] = None
    ) -> Optional[str]:
        """Report an error to telemetry and optionally save crash dump."""
        self._error_counts[error.category] = self._error_counts.get(error.category, 0) + 1

        # Log structured error data
        log_data = {
            "error": error.to_dict(),
            "context": context or {},
            "session_duration_seconds": (
                datetime.now(timezone.utc) - self._session_start
            ).total_seconds(),
        }

        if error.severity >= ErrorSeverity.ERROR:
            logger.error(f"Error reported: {error.error_id}", extra=log_data)
        else:
            logger.warning(f"Error reported: {error.error_id}", extra=log_data)

        # Save crash dump for critical/fatal errors
        if self.enable_crash_dumps and error.severity >= ErrorSeverity.CRITICAL:
            return self._save_crash_dump(error, context)

        return None

    def _save_crash_dump(self, error: OpenWisprError, context: Optional[dict[str, Any]]) -> str:
        """Save crash dump file for analysis."""
        dump_path = (
            self.report_dir
            / f"crash_{error.error_id}_{int(datetime.now(timezone.utc).timestamp())}.json"
        )

        import json

        dump_data = {
            "error": error.to_dict(),
            "context": context or {},
            "session_start": self._session_start.isoformat(),
            "error_counts": {k.value: v for k, v in self._error_counts.items()},
        }

        try:
            with open(dump_path, "w", encoding="utf-8") as f:
                json.dump(dump_data, f, indent=2, default=str)
            logger.info(f"Crash dump saved: {dump_path}")
        except Exception as e:
            logger.error(f"Failed to save crash dump: {e}")

        return str(dump_path)

    def get_stats(self) -> dict[str, Any]:
        """Get error statistics for the current session."""
        return {
            "session_start": self._session_start.isoformat(),
            "total_errors": sum(self._error_counts.values()),
            "by_category": {k.value: v for k, v in self._error_counts.items()},
            "error_rate_per_minute": self._calculate_error_rate(),
        }

    def _calculate_error_rate(self) -> float:
        """Calculate errors per minute."""
        duration_minutes = (datetime.now(timezone.utc) - self._session_start).total_seconds() / 60
        if duration_minutes <= 0:
            return 0.0
        return sum(self._error_counts.values()) / duration_minutes


# ============================================
# Retry Decorator with Exponential Backoff
# ============================================
class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[set[type[BaseException]]] = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or {Exception}


def with_retry(
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, BaseException], None]] = None,
    on_exhausted: Optional[Callable[[BaseException], None]] = None,
):
    """Decorator for retry with exponential backoff."""
    cfg = config or RetryConfig()

    def decorator(func: Callable) -> Callable:
        import functools
        import random
        import time

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(cfg.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except tuple(cfg.retryable_exceptions) as e:
                    last_exception = e

                    if attempt >= cfg.max_retries:
                        logger.error(
                            f"Retry exhausted for {func.__name__} after {cfg.max_retries} attempts"
                        )
                        if on_exhausted:
                            on_exhausted(e)
                        raise

                    delay = min(
                        cfg.base_delay * (cfg.exponential_base**attempt),
                        cfg.max_delay,
                    )
                    if cfg.jitter:
                        delay *= 0.5 + random.random()

                    logger.warning(
                        f"Retry {attempt + 1}/{cfg.max_retries} for {func.__name__} "
                        f"after {delay:.1f}s: {e}"
                    )

                    if on_retry:
                        on_retry(attempt + 1, e)

                    time.sleep(delay)

            raise last_exception

        return wrapper

    return decorator


async def with_retry_async(
    func: Callable[..., Coroutine],
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, BaseException], Coroutine]] = None,
    on_exhausted: Optional[Callable[[BaseException], Coroutine]] = None,
    *args,
    **kwargs,
):
    """Async retry with exponential backoff."""
    cfg = config or RetryConfig()
    import asyncio
    import random

    last_exception = None

    for attempt in range(cfg.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except tuple(cfg.retryable_exceptions) as e:
            last_exception = e

            if attempt >= cfg.max_retries:
                logger.error(f"Async retry exhausted after {cfg.max_retries} attempts")
                if on_exhausted:
                    await on_exhausted(e)
                raise

            delay = min(
                cfg.base_delay * (cfg.exponential_base**attempt),
                cfg.max_delay,
            )
            if cfg.jitter:
                delay *= 0.5 + random.random()

            logger.warning(f"Async retry {attempt + 1}/{cfg.max_retries} after {delay:.1f}s: {e}")

            if on_retry:
                await on_retry(attempt + 1, e)

            await asyncio.sleep(delay)

    raise last_exception


# ============================================
# Central Error Handler
# ============================================
class ErrorHandler:
    """Central error handling and dispatch system."""

    def __init__(
        self,
        notifier: Optional[UserNotifier] = None,
        reporter: Optional[ErrorReporter] = None,
    ):
        self.notifier = notifier or UserNotifier()
        self.reporter = reporter or ErrorReporter()
        self._handlers: dict[ErrorCategory, list[Callable[[OpenWisprError], None]]] = {}
        self._global_handlers: list[Callable[[OpenWisprError], None]] = []
        self._error_counts: dict[str, int] = {}
        self._rate_limits: dict[ErrorCategory, tuple[int, float]] = {}

    def register_handler(
        self,
        category: ErrorCategory,
        handler: Callable[[OpenWisprError], None],
    ) -> None:
        """Register a handler for a specific error category."""
        if category not in self._handlers:
            self._handlers[category] = []
        self._handlers[category].append(handler)
        logger.debug(f"Registered handler for {category.value}")

    def register_global_handler(self, handler: Callable[[OpenWisprError], None]) -> None:
        """Register a global handler for all errors."""
        self._global_handlers.append(handler)
        logger.debug("Registered global error handler")

    def set_rate_limit(
        self, category: ErrorCategory, max_count: int, window_seconds: float
    ) -> None:
        """Set rate limit for error category."""
        self._rate_limits[category] = (max_count, window_seconds)

    def handle(
        self,
        error: OpenWisprError,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """Handle an error through all registered handlers."""
        # Check rate limiting
        if self._is_rate_limited(error):
            logger.debug(f"Rate limited error: {error.error_id}")
            return

        # Track error count
        self._error_counts[error.error_id] = self._error_counts.get(error.error_id, 0) + 1

        # Report to telemetry
        self.reporter.report(error, context)

        # Notify user
        self.notifier.notify(error)

        # Run category-specific handlers
        handlers = self._handlers.get(error.category, [])
        for handler in handlers:
            try:
                handler(error)
            except Exception as e:
                logger.error(f"Error handler failed for {error.error_id}: {e}")

        # Run global handlers
        for handler in self._global_handlers:
            try:
                handler(error)
            except Exception as e:
                logger.error(f"Global error handler failed for {error.error_id}: {e}")

    def handle_exception(
        self,
        exc: BaseException,
        category: ErrorCategory = ErrorCategory.SYSTEM_UNKNOWN,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """Convert generic exception to AppError and handle."""
        if isinstance(exc, AppError):
            self.handle(exc, context)
        else:
            error = AppError(
                message=str(exc),
                category=category,
                severity=ErrorSeverity.ERROR,
                cause=exc,
                stack_trace="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            )
            self.handle(error, context)

    def _is_rate_limited(self, error: OpenWisprError) -> bool:
        """Check if error category is rate limited."""
        if error.category not in self._rate_limits:
            return False

        max_count, window = self._rate_limits[error.category]
        # Simple rate limiting - could be enhanced with time windows
        count = sum(1 for e in self._error_counts if e.startswith(error.category.value))
        return count > max_count

    def get_error_stats(self) -> dict[str, Any]:
        """Get error handling statistics."""
        return {
            "total_handled": len(self._error_counts),
            "unique_errors": len(set(self._error_counts.keys())),
            "reporter_stats": self.reporter.get_stats(),
        }


# ============================================
# Singleton Instance
# ============================================
_default_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get or create the default error handler singleton."""
    global _default_handler
    if _default_handler is None:
        _default_handler = ErrorHandler()
    return _default_handler


def set_default_handler(handler: ErrorHandler) -> None:
    """Set the default error handler singleton."""
    global _default_handler
    _default_handler = handler


# Convenience functions
def handle_error(error: OpenWisprError, context: Optional[dict[str, Any]] = None) -> None:
    """Handle an error using the default handler."""
    get_error_handler().handle(error, context)


def notify_user(error: OpenWisprError) -> None:
    """Notify user of an error using the default notifier."""
    get_error_handler().notifier.notify(error)


def report_error(error: OpenWisprError, context: Optional[dict[str, Any]] = None) -> Optional[str]:
    """Report an error using the default reporter."""
    return get_error_handler().reporter.report(error, context)
