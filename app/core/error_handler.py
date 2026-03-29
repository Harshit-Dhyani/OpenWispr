"""Central error handling system for OpenWispr.

Provides structured error types, centralized error dispatch, user notification,
and crash reporting with full stack trace preservation.
"""

from __future__ import annotations

import contextvars
import enum
import logging
import traceback
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from app.core.recovery_strategies import RecoveryManager, RecoveryResult, RecoveryStatus

logger = logging.getLogger("openwispr.errors")

_error_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "error_context", default={}
)


def set_error_context(**kwargs: Any) -> None:
    """Set error context for the current execution scope."""
    _error_context.set({**_error_context.get(), **kwargs})


def get_error_context() -> dict[str, Any]:
    """Get current error context."""
    return _error_context.get()


def clear_error_context() -> None:
    """Clear error context."""
    _error_context.set({})


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
    code: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    cause: BaseException | None = None
    recoverable: bool = True
    retry_allowed: bool = True
    max_retries: int = 3
    error_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    stack_trace: str | None = None
    endpoint: str | None = None
    file_path: str | None = None

    def __post_init__(self):
        super().__init__(self.message)
        if self.stack_trace is None and self.cause:
            self.stack_trace = "".join(
                traceback.format_exception(type(self.cause), self.cause, self.cause.__traceback__)
            )
        elif self.stack_trace is None:
            self.stack_trace = traceback.format_stack()[:-1]
        self._log_with_error_id()

    def _log_with_error_id(self) -> None:
        """Log error creation with correlation ID for log tracing."""
        set_error_context(error_id=self.error_id, category=self.category.value)
        logger.debug(
            f"Error created: [{self.error_id}] {self.category.value}: {self.message[:100]}",
            extra={"error_id": self.error_id, "error_category": self.category.value},
        )

    def with_context(self, **kwargs: Any) -> "AppError":
        """Create a copy of this error with additional context."""
        new_details = {**self.details, **kwargs}
        new_error = AppError(
            message=self.message,
            category=self.category,
            severity=self.severity,
            code=self.code,
            details=new_details,
            cause=self.cause,
            recoverable=self.recoverable,
            retry_allowed=self.retry_allowed,
            max_retries=self.max_retries,
            stack_trace=self.stack_trace,
        )
        return new_error

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

    device_id: str | None = None
    device_name: str | None = None
    backend: str | None = None

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

    model_name: str | None = None
    model_path: str | None = None
    compute_type: str | None = None
    device: str | None = None

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

    endpoint: str | None = None
    method: str | None = None
    status_code: int | None = None
    response_body: str | None = None

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

    session_id: str | None = None
    file_path: str | None = None
    file_size: int | None = None
    available_space: int | None = None

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


def _lazy_import_recovery() -> tuple[type, type]:
    """Lazily import recovery types to avoid circular imports."""
    from app.core.recovery_strategies import RecoveryResult, RecoveryStatus

    return RecoveryStatus, RecoveryResult


def exception_to_error(
    exc: BaseException,
    category: ErrorCategory = ErrorCategory.SYSTEM_UNKNOWN,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    message: str | None = None,
    **extra_details: Any,
) -> AppError:
    """Convert a generic exception to a structured AppError.

    This is the preferred way to wrap exceptions in the application.
    Preserves exception chain for proper traceback propagation.

    Args:
        exc: The exception to convert
        category: Error category for targeted recovery
        severity: Error severity level
        message: Optional custom message (defaults to str(exc))
        **extra_details: Additional error details

    Returns:
        Structured AppError with cause chain preserved
    """
    return AppError(
        message=message or str(exc),
        category=category,
        severity=severity,
        cause=exc,
        details=extra_details,
        stack_trace="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    )


def wrap_error(
    exc: BaseException,
    target_type: type[OpenWisprError],
    **extra_details: Any,
) -> OpenWisprError:
    """Convert exception to specific error type with additional context.

    Args:
        exc: The exception to convert
        target_type: Specific error type (AudioError, ModelError, etc.)
        **extra_details: Additional error details

    Returns:
        Error of the target type with cause chain preserved
    """
    import dataclasses

    error = target_type(message=str(exc), cause=exc)
    for key, value in extra_details.items():
        if hasattr(error, key):
            setattr(error, key, value)
    return error


# Mapping from exception types to default categories
_EXCEPTION_CATEGORY_MAP: dict[type[BaseException], ErrorCategory] = {}


def register_exception_category(exc_type: type[BaseException], category: ErrorCategory) -> None:
    """Register a default error category for an exception type.

    Enables automatic categorization when converting exceptions.
    """
    _EXCEPTION_CATEGORY_MAP[exc_type] = category


def auto_categorize_error(exc: BaseException) -> ErrorCategory:
    """Automatically determine error category from exception type.

    Checks registered mappings first, then falls back to
    heuristics based on exception class names.
    """
    if type(exc) in _EXCEPTION_CATEGORY_MAP:
        return _EXCEPTION_CATEGORY_MAP[type(exc)]

    exc_name = type(exc).__name__.lower()
    if "audio" in exc_name or "microphone" in exc_name or "device" in exc_name:
        return ErrorCategory.AUDIO_CAPTURE_ERROR
    if "model" in exc_name or "whisper" in exc_name:
        return ErrorCategory.MODEL_LOAD_FAILED
    if "network" in exc_name or "http" in exc_name or "connection" in exc_name:
        return ErrorCategory.NETWORK_CONNECTION_ERROR
    if "session" in exc_name or "disk" in exc_name or "storage" in exc_name:
        return ErrorCategory.SESSION_DISK_FULL

    return ErrorCategory.SYSTEM_UNKNOWN


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
        callback: Callable[[dict[str, str]], None] | None = None,
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
                "timestamp": datetime.now(UTC).isoformat(),
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
        self, category: ErrorCategory, duration_seconds: float | None = None
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
        report_dir: Path | None = None,
        enable_telemetry: bool = True,
        enable_crash_dumps: bool = True,
    ):
        self.report_dir = report_dir or Path.home() / ".openwispr" / "reports"
        self.enable_telemetry = enable_telemetry
        self.enable_crash_dumps = enable_crash_dumps
        self._error_counts: dict[ErrorCategory, int] = {}
        self._session_start = datetime.now(UTC)

        if self.enable_crash_dumps:
            self.report_dir.mkdir(parents=True, exist_ok=True)

    def report(self, error: OpenWisprError, context: dict[str, Any] | None = None) -> str | None:
        """Report an error to telemetry and optionally save crash dump."""
        self._error_counts[error.category] = self._error_counts.get(error.category, 0) + 1

        # Log structured error data
        log_data = {
            "error": error.to_dict(),
            "context": context or {},
            "session_duration_seconds": (datetime.now(UTC) - self._session_start).total_seconds(),
        }

        if error.severity >= ErrorSeverity.ERROR:
            logger.error(f"Error reported: {error.error_id}", extra=log_data)
        else:
            logger.warning(f"Error reported: {error.error_id}", extra=log_data)

        # Save crash dump for critical/fatal errors
        if self.enable_crash_dumps and error.severity >= ErrorSeverity.CRITICAL:
            return self._save_crash_dump(error, context)

        return None

    def _save_crash_dump(self, error: OpenWisprError, context: dict[str, Any] | None) -> str:
        """Save crash dump file for analysis."""
        dump_path = (
            self.report_dir / f"crash_{error.error_id}_{int(datetime.now(UTC).timestamp())}.json"
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
        duration_minutes = (datetime.now(UTC) - self._session_start).total_seconds() / 60
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
        retryable_exceptions: set[type[BaseException]] | None = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or {Exception}


def with_retry(
    config: RetryConfig | None = None,
    on_retry: Callable[[int, BaseException], None] | None = None,
    on_exhausted: Callable[[BaseException], None] | None = None,
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

            raise last_exception  # type: ignore[arg-type]

        return wrapper

    return decorator


async def with_retry_async(
    func: Callable[..., Coroutine],
    config: RetryConfig | None = None,
    on_retry: Callable[[int, BaseException], Coroutine] | None = None,
    on_exhausted: Callable[[BaseException], Coroutine] | None = None,
    *args,
    **kwargs,
):
    """Async retry with exponential backoff."""
    cfg = config or RetryConfig()
    import asyncio
    import random

    last_exception: BaseException | None = None
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
    """Central error handling and dispatch system.

    Coordinates error reporting, notification, recovery attempts,
    and telemetry through registered handlers.
    """

    def __init__(
        self,
        notifier: UserNotifier | None = None,
        reporter: ErrorReporter | None = None,
    ):
        self.notifier = notifier or UserNotifier()
        self.reporter = reporter or ErrorReporter()
        self._handlers: dict[ErrorCategory, list[Callable[[OpenWisprError], None]]] = {}
        self._global_handlers: list[Callable[[OpenWisprError], None]] = []
        self._error_counts: dict[str, int] = {}
        self._rate_limits: dict[ErrorCategory, tuple[int, float]] = {}
        self._error_history: list[OpenWisprError] = []
        self._max_history = 100
        self._recovery_manager: "RecoveryManager | None" = None

    def set_recovery_manager(self, manager: "RecoveryManager") -> None:
        """Set the recovery manager for automatic error recovery."""
        self._recovery_manager = manager

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
        context: dict[str, Any] | None = None,
        attempt_recovery: bool = True,
    ) -> "RecoveryResult | None":
        """Handle an error through all registered handlers.

        Args:
            error: The error to handle
            context: Additional context for the error
            attempt_recovery: Whether to attempt automatic recovery

        Returns:
            RecoveryResult if recovery was attempted, None otherwise
        """
        self._record_error(error)
        ctx = context or {}

        if self._is_rate_limited(error):
            logger.debug(f"Rate limited error: [{error.error_id}] {error.category.value}")
            return None

        self._error_counts[error.error_id] = self._error_counts.get(error.error_id, 0) + 1

        logger.error(
            f"Handling error: [{error.error_id}] {error.category.value}: {error.message}",
            extra={
                "error_id": error.error_id,
                "error_category": error.category.value,
                "error_severity": error.severity.name,
                "recoverable": error.recoverable,
                "context": ctx,
            },
        )

        self.reporter.report(error, ctx)
        self.notifier.notify(error)

        handlers = self._handlers.get(error.category, [])
        for handler in handlers:
            try:
                handler(error)
            except Exception as e:
                logger.error(
                    f"Error handler failed: [{error.error_id}] {type(e).__name__}: {e}",
                    extra={"error_id": error.error_id},
                    exc_info=True,
                )

        for handler in self._global_handlers:
            try:
                handler(error)
            except Exception as e:
                logger.error(
                    f"Global handler failed: [{error.error_id}] {type(e).__name__}: {e}",
                    extra={"error_id": error.error_id},
                    exc_info=True,
                )

        if attempt_recovery and error.recoverable and self._recovery_manager:
            return self._attempt_recovery(error, ctx)

        return None

    def _attempt_recovery(
        self, error: OpenWisprError, context: dict[str, Any]
    ) -> "RecoveryResult | None":
        """Attempt to recover from an error using the recovery manager."""
        if not self._recovery_manager:
            return None

        try:
            result = self._recovery_manager.attempt_recovery(error, context)
            if result.status == RecoveryStatus.SUCCESS:
                logger.info(
                    f"Recovery succeeded: [{error.error_id}] {result.message}",
                    extra={"error_id": error.error_id, "recovery": result.to_dict()},
                )
            elif result.status == RecoveryStatus.PARTIAL:
                logger.warning(
                    f"Recovery partial success: [{error.error_id}] {result.message}",
                    extra={"error_id": error.error_id, "recovery": result.to_dict()},
                )
            else:
                logger.warning(
                    f"Recovery failed: [{error.error_id}] {result.message}",
                    extra={"error_id": error.error_id, "recovery": result.to_dict()},
                )
            return result
        except Exception as e:
            logger.error(
                f"Recovery attempt threw exception: [{error.error_id}] {type(e).__name__}: {e}",
                extra={"error_id": error.error_id},
                exc_info=True,
            )
            return None

    def handle_exception(
        self,
        exc: BaseException,
        category: ErrorCategory = ErrorCategory.SYSTEM_UNKNOWN,
        context: dict[str, Any] | None = None,
        attempt_recovery: bool = True,
    ) -> "RecoveryResult | None":
        """Convert generic exception to AppError and handle.

        Args:
            exc: The exception to handle
            category: Default category if exception isn't an AppError
            context: Additional context
            attempt_recovery: Whether to attempt recovery

        Returns:
            RecoveryResult if recovery was attempted
        """
        if isinstance(exc, AppError):
            return self.handle(exc, context, attempt_recovery)

        auto_category = auto_categorize_error(exc)
        error = AppError(
            message=str(exc),
            category=auto_category if category == ErrorCategory.SYSTEM_UNKNOWN else category,
            severity=ErrorSeverity.ERROR,
            cause=exc,
            details=context or {},
            stack_trace="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        )
        return self.handle(error, context, attempt_recovery)

    def _record_error(self, error: OpenWisprError) -> None:
        """Record error to history for analysis."""
        self._error_history.append(error)
        if len(self._error_history) > self._max_history:
            self._error_history = self._error_history[-self._max_history :]

    def _is_rate_limited(self, error: OpenWisprError) -> bool:
        """Check if error category is rate limited."""
        if error.category not in self._rate_limits:
            return False

        max_count, window = self._rate_limits[error.category]
        now = datetime.now(UTC)
        recent_count = sum(
            1
            for e in self._error_history
            if e.category == error.category and (now - e.timestamp).total_seconds() < window
        )
        return recent_count >= max_count

    def get_error_stats(self) -> dict[str, Any]:
        """Get error handling statistics."""
        return {
            "total_handled": sum(self._error_counts.values()),
            "unique_errors": len(self._error_counts),
            "history_size": len(self._error_history),
            "reporter_stats": self.reporter.get_stats(),
        }

    def get_recent_errors(self, limit: int = 10) -> list[OpenWisprError]:
        """Get recent errors for debugging."""
        return self._error_history[-limit:]

    def get_errors_by_category(self, category: ErrorCategory) -> list[OpenWisprError]:
        """Get errors by category."""
        return [e for e in self._error_history if e.category == category]


# ============================================
# Singleton Instance
# ============================================
_default_handler: ErrorHandler | None = None


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
def handle_error(error: OpenWisprError, context: dict[str, Any] | None = None) -> None:
    """Handle an error using the default handler."""
    get_error_handler().handle(error, context)


def notify_user(error: OpenWisprError) -> None:
    """Notify user of an error using the default notifier."""
    get_error_handler().notifier.notify(error)


def report_error(error: OpenWisprError, context: dict[str, Any] | None = None) -> str | None:
    """Report an error using the default reporter."""
    return get_error_handler().reporter.report(error, context)
