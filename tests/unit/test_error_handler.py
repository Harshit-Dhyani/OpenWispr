"""Unit tests for the error handler system.

Tests cover:
- Error creation and serialization
- Error severity and category handling
- User notification system
- Error reporting and telemetry
- Retry mechanisms
- Central error handler
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from app.core.error_handler import (
    AppError,
    AudioError,
    ErrorCategory,
    ErrorHandler,
    ErrorReporter,
    ErrorSeverity,
    ModelError,
    NetworkError,
    RetryConfig,
    SessionError,
    UserNotifier,
    get_error_handler,
    set_default_handler,
    with_retry,
)


class TestErrorSeverity:
    """Tests for ErrorSeverity enum."""

    def test_severity_ordering(self) -> None:
        """Test severity levels are correctly ordered."""
        assert ErrorSeverity.DEBUG < ErrorSeverity.INFO
        assert ErrorSeverity.INFO < ErrorSeverity.WARNING
        assert ErrorSeverity.WARNING < ErrorSeverity.ERROR
        assert ErrorSeverity.ERROR < ErrorSeverity.CRITICAL
        assert ErrorSeverity.CRITICAL < ErrorSeverity.FATAL

    def test_severity_values(self) -> None:
        """Test severity level values."""
        assert ErrorSeverity.DEBUG.value == 10
        assert ErrorSeverity.INFO.value == 20
        assert ErrorSeverity.WARNING.value == 30
        assert ErrorSeverity.ERROR.value == 40
        assert ErrorSeverity.CRITICAL.value == 50
        assert ErrorSeverity.FATAL.value == 60


class TestErrorCategory:
    """Tests for ErrorCategory enum."""

    def test_audio_categories(self) -> None:
        """Test audio-related error categories."""
        assert ErrorCategory.AUDIO_DEVICE_DISCONNECTED.value == "audio_device_disconnected"
        assert ErrorCategory.AUDIO_PERMISSION_DENIED.value == "audio_permission_denied"
        assert ErrorCategory.AUDIO_BACKEND_FAILURE.value == "audio_backend_failure"

    def test_model_categories(self) -> None:
        """Test model-related error categories."""
        assert ErrorCategory.MODEL_OOM.value == "model_out_of_memory"
        assert ErrorCategory.MODEL_NOT_FOUND.value == "model_not_found"
        assert ErrorCategory.MODEL_LOAD_FAILED.value == "model_load_failed"


class TestAppError:
    """Tests for AppError base class."""

    def test_basic_creation(self) -> None:
        """Test basic error creation."""
        error = AppError(message="Test error")

        assert error.message == "Test error"
        assert error.category == ErrorCategory.SYSTEM_UNKNOWN
        assert error.severity == ErrorSeverity.ERROR
        assert error.recoverable is True
        assert error.retry_allowed is True
        assert error.max_retries == 3
        assert error.error_id is not None
        assert len(error.error_id) == 8

    def test_custom_values(self) -> None:
        """Test error with custom values."""
        error = AppError(
            message="Custom error",
            category=ErrorCategory.MODEL_OOM,
            severity=ErrorSeverity.CRITICAL,
            recoverable=False,
            retry_allowed=False,
            max_retries=0,
        )

        assert error.category == ErrorCategory.MODEL_OOM
        assert error.severity == ErrorSeverity.CRITICAL
        assert error.recoverable is False
        assert error.retry_allowed is False

    def test_to_dict(self) -> None:
        """Test error serialization."""
        error = AppError(
            message="Test error",
            category=ErrorCategory.AUDIO_DEVICE_DISCONNECTED,
            details={"device_id": "test-device"},
        )

        data = error.to_dict()

        assert data["message"] == "Test error"
        assert data["category"] == "audio_device_disconnected"
        assert data["details"]["device_id"] == "test-device"
        assert "timestamp" in data

    def test_str_representation(self) -> None:
        """Test string representation."""
        error = AppError(message="Test error")

        str_repr = str(error)

        assert error.error_id in str_repr
        assert "Test error" in str_repr

    def test_error_with_cause(self) -> None:
        """Test error with underlying cause."""
        original = ValueError("Original error")
        error = AppError(message="Wrapped error", cause=original)

        assert error.cause is original
        assert error.stack_trace is not None


class TestAudioError:
    """Tests for AudioError."""

    def test_audio_error_creation(self) -> None:
        """Test audio error creation."""
        error = AudioError(
            message="Device disconnected",
            device_id="device-1",
            device_name="Test Mic",
            backend="sounddevice",
        )

        assert error.device_id == "device-1"
        assert error.device_name == "Test Mic"
        assert error.backend == "sounddevice"
        assert error.category == ErrorCategory.AUDIO_DEVICE_DISCONNECTED

    def test_audio_error_category_correction(self) -> None:
        """Test that audio errors get correct category."""
        error = AudioError(message="Test", category=ErrorCategory.MODEL_OOM)

        # Should be corrected to audio category
        assert "AUDIO" in error.category.name or error.category == ErrorCategory.AUDIO_CAPTURE_ERROR


class TestModelError:
    """Tests for ModelError."""

    def test_model_error_creation(self) -> None:
        """Test model error creation."""
        error = ModelError(
            message="Out of memory",
            model_name="large-v3",
            compute_type="float16",
            device="cuda",
        )

        assert error.model_name == "large-v3"
        assert error.compute_type == "float16"
        assert error.device == "cuda"

    def test_model_oom_category(self) -> None:
        """Test OOM error gets correct category."""
        error = ModelError(
            message="CUDA out of memory",
            category=ErrorCategory.MODEL_OOM,
        )

        assert error.category == ErrorCategory.MODEL_OOM


class TestNetworkError:
    """Tests for NetworkError."""

    def test_network_error_creation(self) -> None:
        """Test network error creation."""
        error = NetworkError(
            message="Connection failed",
            endpoint="/api/transcribe",
            method="POST",
            status_code=503,
        )

        assert error.endpoint == "/api/transcribe"
        assert error.method == "POST"
        assert error.status_code == 503


class TestSessionError:
    """Tests for SessionError."""

    def test_session_error_creation(self) -> None:
        """Test session error creation."""
        error = SessionError(
            message="Disk full",
            session_id="session-123",
            file_path="/output/session.json",
        )

        assert error.session_id == "session-123"
        assert error.file_path == "/output/session.json"


class TestUserNotifier:
    """Tests for UserNotifier."""

    def test_init(self) -> None:
        """Test notifier initialization."""
        notifier = UserNotifier()

        assert notifier.min_severity == ErrorSeverity.WARNING
        assert notifier.callback is None

    def test_notify_above_threshold(self) -> None:
        """Test notification above severity threshold."""
        callback_called = False

        def callback(data: dict) -> None:
            nonlocal callback_called
            callback_called = True

        notifier = UserNotifier(min_severity=ErrorSeverity.WARNING, callback=callback)
        error = AppError(message="Test", severity=ErrorSeverity.ERROR)

        notifier.notify(error)

        assert callback_called is True

    def test_notify_below_threshold(self) -> None:
        """Test no notification below severity threshold."""
        callback_called = False

        def callback(data: dict) -> None:
            nonlocal callback_called
            callback_called = True

        notifier = UserNotifier(min_severity=ErrorSeverity.ERROR, callback=callback)
        error = AppError(message="Test", severity=ErrorSeverity.DEBUG)

        notifier.notify(error)

        assert callback_called is False

    def test_suppressed_category(self) -> None:
        """Test suppressed category doesn't notify."""
        callback_called = False

        def callback(data: dict) -> None:
            nonlocal callback_called
            callback_called = True

        notifier = UserNotifier(callback=callback)
        notifier.suppress_category(ErrorCategory.AUDIO_DEVICE_DISCONNECTED)

        error = AppError(
            message="Test",
            category=ErrorCategory.AUDIO_DEVICE_DISCONNECTED,
            severity=ErrorSeverity.ERROR,
        )

        notifier.notify(error)

        assert callback_called is False

    def test_get_history(self) -> None:
        """Test notification history."""
        notifier = UserNotifier()
        error = AppError(message="Test", severity=ErrorSeverity.ERROR)

        notifier.notify(error)
        history = notifier.get_history()

        assert len(history) == 1
        assert history[0]["error_id"] == error.error_id


class TestErrorReporter:
    """Tests for ErrorReporter."""

    def test_init(self, temp_dir: Path) -> None:
        """Test reporter initialization."""
        reporter = ErrorReporter(report_dir=temp_dir)

        assert reporter.report_dir == temp_dir
        assert reporter.enable_telemetry is True
        assert reporter.enable_crash_dumps is True

    def test_report_error(self) -> None:
        """Test error reporting."""
        reporter = ErrorReporter(enable_crash_dumps=False)
        error = AppError(message="Test error", severity=ErrorSeverity.ERROR)

        reporter.report(error)

        assert reporter._error_counts[error.category] == 1

    def test_report_critical_creates_dump(self, temp_dir: Path) -> None:
        """Test critical error creates crash dump."""
        reporter = ErrorReporter(report_dir=temp_dir, enable_crash_dumps=True)
        error = AppError(message="Critical error", severity=ErrorSeverity.CRITICAL)

        dump_path = reporter.report(error)

        assert dump_path is not None
        assert Path(dump_path).exists()

    def test_get_stats(self) -> None:
        """Test statistics retrieval."""
        reporter = ErrorReporter()

        # Report some errors
        reporter.report(AppError(message="Error 1", category=ErrorCategory.MODEL_OOM))
        reporter.report(AppError(message="Error 2", category=ErrorCategory.MODEL_OOM))
        reporter.report(
            AppError(message="Error 3", category=ErrorCategory.AUDIO_DEVICE_DISCONNECTED)
        )

        stats = reporter.get_stats()

        assert stats["total_errors"] == 3
        assert stats["by_category"]["model_out_of_memory"] == 2
        assert stats["by_category"]["audio_device_disconnected"] == 1
        assert "error_rate_per_minute" in stats


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_values(self) -> None:
        """Test default retry configuration."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_values(self) -> None:
        """Test custom retry configuration."""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            jitter=False,
        )

        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.jitter is False


class TestWithRetry:
    """Tests for retry decorator."""

    def test_success_no_retry(self) -> None:
        """Test successful function doesn't retry."""
        call_count = 0

        @with_retry()
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()

        assert result == "success"
        assert call_count == 1

    def test_retry_then_success(self) -> None:
        """Test retry until success."""
        call_count = 0

        @with_retry(config=RetryConfig(max_retries=3, base_delay=0.01))
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = flaky_func()

        assert result == "success"
        assert call_count == 3

    def test_retry_exhausted(self) -> None:
        """Test retry exhausted raises exception."""
        call_count = 0

        @with_retry(config=RetryConfig(max_retries=2, base_delay=0.01))
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            always_fails()

        assert call_count == 3  # Initial + 2 retries

    def test_specific_exceptions(self) -> None:
        """Test retry only on specific exceptions."""
        call_count = 0

        @with_retry(
            config=RetryConfig(max_retries=2, base_delay=0.01, retryable_exceptions={ValueError})
        )
        def mixed_errors():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TypeError("Type error - should not retry")
            raise ValueError("Value error - should retry")

        with pytest.raises(TypeError):
            mixed_errors()

        assert call_count == 1  # No retry for TypeError


class TestErrorHandler:
    """Tests for ErrorHandler."""

    @pytest.fixture
    def error_handler(self) -> ErrorHandler:
        """Create a test error handler."""
        return ErrorHandler()

    def test_init(self, error_handler: ErrorHandler) -> None:
        """Test handler initialization."""
        assert error_handler.notifier is not None
        assert error_handler.reporter is not None
        assert len(error_handler._handlers) == 0
        assert len(error_handler._global_handlers) == 0

    def test_register_handler(self, error_handler: ErrorHandler) -> None:
        """Test handler registration."""
        handler = Mock()

        error_handler.register_handler(ErrorCategory.MODEL_OOM, handler)

        assert handler in error_handler._handlers[ErrorCategory.MODEL_OOM]

    def test_register_global_handler(self, error_handler: ErrorHandler) -> None:
        """Test global handler registration."""
        handler = Mock()

        error_handler.register_global_handler(handler)

        assert handler in error_handler._global_handlers

    def test_handle_error(self, error_handler: ErrorHandler) -> None:
        """Test error handling."""
        category_handler = Mock()
        global_handler = Mock()

        error_handler.register_handler(ErrorCategory.MODEL_OOM, category_handler)
        error_handler.register_global_handler(global_handler)

        error = AppError(message="Test", category=ErrorCategory.MODEL_OOM)
        error_handler.handle(error)

        category_handler.assert_called_once_with(error)
        global_handler.assert_called_once_with(error)

    def test_handle_exception(self, error_handler: ErrorHandler) -> None:
        """Test handling generic exceptions."""
        global_handler = Mock()
        error_handler.register_global_handler(global_handler)

        original = ValueError("Original error")
        error_handler.handle_exception(original)

        # Should create AppError and call handlers
        global_handler.assert_called_once()
        passed_error = global_handler.call_args[0][0]
        assert isinstance(passed_error, AppError)

    def test_get_error_stats(self, error_handler: ErrorHandler) -> None:
        """Test error statistics."""
        error1 = AppError(message="Error 1")
        error2 = AppError(message="Error 2")

        error_handler.handle(error1)
        error_handler.handle(error2)

        stats = error_handler.get_error_stats()

        assert stats["total_handled"] == 2
        assert stats["unique_errors"] == 2


class TestSingleton:
    """Tests for error handler singleton."""

    def test_get_error_handler_singleton(self) -> None:
        """Test that get_error_handler returns singleton."""
        handler1 = get_error_handler()
        handler2 = get_error_handler()

        assert handler1 is handler2

    def test_set_default_handler(self) -> None:
        """Test setting custom default handler."""
        custom_handler = ErrorHandler()

        set_default_handler(custom_handler)
        current = get_error_handler()

        assert current is custom_handler
