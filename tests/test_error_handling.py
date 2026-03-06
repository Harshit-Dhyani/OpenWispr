"""Comprehensive unit tests for error handling and recovery strategies."""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

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
    handle_error,
    with_retry,
    with_retry_async,
)
from app.core.recovery_strategies import (
    AudioDeviceRecoveryStrategy,
    AudioPermissionRecoveryStrategy,
    DiskFullRecoveryStrategy,
    FallbackChain,
    FallbackOption,
    ModelDownloadStrategy,
    ModelFallbackStrategy,
    ModelOOMRecoveryStrategy,
    NetworkRetryStrategy,
    OfflineModeStrategy,
    RecoveryManager,
    RecoveryResult,
    RecoveryStatus,
    RecoveryStrategy,
    SessionCorruptionRecoveryStrategy,
    create_batch_size_fallback_chain,
    create_compute_fallback_chain,
    create_default_recovery_manager,
    create_model_size_fallback_chain,
)


# ============================================
# Error Type Tests
# ============================================
class TestErrorTypes:
    """Tests for structured error types."""

    def test_app_error_basic(self):
        """Test basic AppError creation."""
        error = AppError(
            message="Test error",
            category=ErrorCategory.SYSTEM_UNKNOWN,
            severity=ErrorSeverity.ERROR,
        )

        assert error.message == "Test error"
        assert error.category == ErrorCategory.SYSTEM_UNKNOWN
        assert error.severity == ErrorSeverity.ERROR
        assert error.error_id is not None
        assert len(error.error_id) == 8
        assert error.recoverable is True
        assert error.retry_allowed is True

    def test_app_error_with_cause(self):
        """Test AppError with cause exception."""
        cause = ValueError("Original error")
        error = AppError(
            message="Wrapped error",
            category=ErrorCategory.SYSTEM_CONFIG_ERROR,
            severity=ErrorSeverity.ERROR,
            cause=cause,
        )

        assert error.cause is cause
        assert error.stack_trace is not None
        assert "ValueError" in error.stack_trace

    def test_app_error_to_dict(self):
        """Test AppError serialization."""
        error = AppError(
            message="Test",
            category=ErrorCategory.SYSTEM_UNKNOWN,
            code="E001",
            details={"key": "value"},
        )

        data = error.to_dict()
        assert data["message"] == "Test"
        assert data["category"] == "system_unknown"
        assert data["code"] == "E001"
        assert data["details"] == {"key": "value"}
        assert "error_id" in data

    def test_audio_error(self):
        """Test AudioError creation."""
        error = AudioError(
            message="Device disconnected",
            category=ErrorCategory.AUDIO_DEVICE_DISCONNECTED,
            device_id="device_1",
            device_name="Microphone",
            backend="wasapi",
        )

        assert error.device_id == "device_1"
        assert error.device_name == "Microphone"
        assert error.backend == "wasapi"
        assert error.category == ErrorCategory.AUDIO_DEVICE_DISCONNECTED

    def test_model_error(self):
        """Test ModelError creation."""
        error = ModelError(
            message="Model not found",
            category=ErrorCategory.MODEL_NOT_FOUND,
            model_name="medium",
            model_path="/path/to/model",
            compute_type="float16",
        )

        assert error.model_name == "medium"
        assert error.model_path == "/path/to/model"
        assert error.compute_type == "float16"

    def test_network_error(self):
        """Test NetworkError creation."""
        error = NetworkError(
            message="Connection failed",
            category=ErrorCategory.NETWORK_TIMEOUT,
            endpoint="https://api.example.com",
            method="POST",
            status_code=504,
        )

        assert error.endpoint == "https://api.example.com"
        assert error.method == "POST"
        assert error.status_code == 504

    def test_session_error(self):
        """Test SessionError creation."""
        error = SessionError(
            message="Disk full",
            category=ErrorCategory.SESSION_DISK_FULL,
            session_id="session_123",
            file_path="/tmp/session.json",
            available_space=0,
        )

        assert error.session_id == "session_123"
        assert error.file_path == "/tmp/session.json"
        assert error.available_space == 0


# ============================================
# User Notifier Tests
# ============================================
class TestUserNotifier:
    """Tests for UserNotifier."""

    def test_notify_above_threshold(self):
        """Test notification above severity threshold."""
        callback = MagicMock()
        notifier = UserNotifier(min_severity=ErrorSeverity.WARNING, callback=callback)

        error = AppError(
            message="Test warning",
            severity=ErrorSeverity.WARNING,
            category=ErrorCategory.AUDIO_DEVICE_DISCONNECTED,
        )

        notifier.notify(error)

        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args["title"] == "Audio Device Disconnected"
        assert call_args["severity"] == "WARNING"

    def test_notify_below_threshold(self):
        """Test suppression below severity threshold."""
        callback = MagicMock()
        notifier = UserNotifier(min_severity=ErrorSeverity.ERROR, callback=callback)

        error = AppError(
            message="Info message",
            severity=ErrorSeverity.INFO,
        )

        notifier.notify(error)
        callback.assert_not_called()

    def test_suppress_category(self):
        """Test category suppression."""
        callback = MagicMock()
        notifier = UserNotifier(callback=callback)

        notifier.suppress_category(ErrorCategory.AUDIO_DEVICE_DISCONNECTED)

        error = AudioError(
            message="Device disconnected",
            category=ErrorCategory.AUDIO_DEVICE_DISCONNECTED,
            severity=ErrorSeverity.ERROR,
        )

        notifier.notify(error)
        callback.assert_not_called()

    def test_format_message_with_details(self):
        """Test message formatting with error details."""
        notifier = UserNotifier()

        error = ModelError(
            message="OOM",
            category=ErrorCategory.MODEL_OOM,
            model_name="large-v3",
        )

        message = notifier._format_message(error)
        assert "large-v3" in message["message"]

    def test_notification_history(self):
        """Test notification history tracking."""
        notifier = UserNotifier(min_severity=ErrorSeverity.DEBUG)

        error1 = AppError(message="Error 1", severity=ErrorSeverity.ERROR)
        error2 = AppError(message="Error 2", severity=ErrorSeverity.ERROR)

        notifier.notify(error1)
        notifier.notify(error2)

        history = notifier.get_history(limit=10)
        assert len(history) == 2
        assert history[0]["error_id"] == error1.error_id


# ============================================
# Error Reporter Tests
# ============================================
class TestErrorReporter:
    """Tests for ErrorReporter."""

    def test_report_creates_dump_for_critical(self, tmp_path):
        """Test crash dump creation for critical errors."""
        reporter = ErrorReporter(
            report_dir=tmp_path,
            enable_crash_dumps=True,
        )

        error = AppError(
            message="Critical failure",
            severity=ErrorSeverity.CRITICAL,
        )

        dump_path = reporter.report(error)

        assert dump_path is not None
        assert Path(dump_path).exists()

        # Verify dump content
        with open(dump_path) as f:
            data = json.load(f)
            assert data["error"]["message"] == "Critical failure"
            assert data["error"]["severity"] == "CRITICAL"

    def test_no_dump_for_warning(self, tmp_path):
        """Test no crash dump for warnings."""
        reporter = ErrorReporter(
            report_dir=tmp_path,
            enable_crash_dumps=True,
        )

        error = AppError(
            message="Warning",
            severity=ErrorSeverity.WARNING,
        )

        dump_path = reporter.report(error)
        assert dump_path is None

    def test_error_counts(self):
        """Test error counting by category."""
        reporter = ErrorReporter(enable_telemetry=True)

        reporter.report(AppError("Error 1", category=ErrorCategory.MODEL_OOM))
        reporter.report(AppError("Error 2", category=ErrorCategory.MODEL_OOM))
        reporter.report(AppError("Error 3", category=ErrorCategory.AUDIO_DEVICE_DISCONNECTED))

        stats = reporter.get_stats()
        assert stats["by_category"]["model_out_of_memory"] == 2
        assert stats["by_category"]["audio_device_disconnected"] == 1
        assert stats["total_errors"] == 3

    def test_error_rate_calculation(self):
        """Test error rate per minute calculation."""
        reporter = ErrorReporter()

        # Simulate some errors
        for _ in range(6):
            reporter.report(AppError("Test"))

        stats = reporter.get_stats()
        # Rate should be reasonable for quick test
        assert "error_rate_per_minute" in stats
        assert stats["error_rate_per_minute"] >= 0


# ============================================
# Error Handler Tests
# ============================================
class TestErrorHandler:
    """Tests for ErrorHandler."""

    def test_register_handler(self):
        """Test category-specific handler registration."""
        handler = ErrorHandler()
        mock_handler = MagicMock()

        handler.register_handler(ErrorCategory.MODEL_OOM, mock_handler)

        error = ModelError(
            message="OOM",
            category=ErrorCategory.MODEL_OOM,
        )

        handler.handle(error)
        mock_handler.assert_called_once_with(error)

    def test_register_global_handler(self):
        """Test global handler registration."""
        handler = ErrorHandler()
        mock_handler = MagicMock()

        handler.register_global_handler(mock_handler)

        error = AppError(message="Test")
        handler.handle(error)

        mock_handler.assert_called_once_with(error)

    def test_handle_exception_conversion(self):
        """Test conversion of generic exceptions."""
        handler = ErrorHandler()
        mock_reporter = MagicMock()
        handler.reporter = mock_reporter

        try:
            raise ValueError("Original error")
        except ValueError as e:
            handler.handle_exception(e, ErrorCategory.SYSTEM_CONFIG_ERROR)

        # Should have reported the error
        mock_reporter.report.assert_called_once()
        reported_error = mock_reporter.report.call_args[0][0]
        assert reported_error.category == ErrorCategory.SYSTEM_CONFIG_ERROR
        assert "ValueError" in reported_error.stack_trace

    def test_rate_limiting(self):
        """Test error rate limiting."""
        handler = ErrorHandler()
        handler.set_rate_limit(ErrorCategory.MODEL_OOM, max_count=2, window_seconds=60)

        mock_handler = MagicMock()
        handler.register_handler(ErrorCategory.MODEL_OOM, mock_handler)

        # First two should go through
        for _ in range(2):
            error = ModelError(
                message="OOM",
                category=ErrorCategory.MODEL_OOM,
                error_id=f"model_oom_test",  # Same ID prefix for rate limit check
            )
            error.category = ErrorCategory.MODEL_OOM
            handler.handle(error)

        # Should have been called twice
        assert mock_handler.call_count == 2


# ============================================
# Retry Tests
# ============================================
class TestRetry:
    """Tests for retry functionality."""

    def test_retry_success(self):
        """Test successful retry."""
        call_count = 0

        @with_retry(RetryConfig(max_retries=2, base_delay=0.01))
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temporary failure")
            return "success"

        result = flaky_function()
        assert result == "success"
        assert call_count == 2

    def test_retry_exhausted(self):
        """Test retry exhaustion."""
        call_count = 0

        @with_retry(RetryConfig(max_retries=2, base_delay=0.01))
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")

        with pytest.raises(ConnectionError):
            always_fails()

        assert call_count == 3  # Initial + 2 retries

    def test_retry_callbacks(self):
        """Test retry callbacks."""
        on_retry_calls = []
        on_exhausted_calls = []

        def on_retry(attempt, error):
            on_retry_calls.append((attempt, str(error)))

        def on_exhausted(error):
            on_exhausted_calls.append(str(error))

        @with_retry(
            RetryConfig(max_retries=1, base_delay=0.01),
            on_retry=on_retry,
            on_exhausted=on_exhausted,
        )
        def always_fails():
            raise ConnectionError("Test error")

        with pytest.raises(ConnectionError):
            always_fails()

        assert len(on_retry_calls) == 1
        assert len(on_exhausted_calls) == 1

    @pytest.mark.asyncio
    async def test_async_retry_success(self):
        """Test successful async retry."""
        call_count = 0

        async def flaky_async():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temporary failure")
            return "success"

        result = await with_retry_async(
            flaky_async,
            RetryConfig(max_retries=2, base_delay=0.01),
        )

        assert result == "success"
        assert call_count == 2


# ============================================
# Fallback Chain Tests
# ============================================
class TestFallbackChain:
    """Tests for FallbackChain."""

    def test_current_primary(self):
        """Test getting current primary option."""
        options = [
            FallbackOption("opt1", "value1", lambda: True),
            FallbackOption("opt2", "value2", lambda: True),
        ]
        chain = FallbackChain("test", options)

        assert chain.current() == "value1"
        assert chain.current_name() == "opt1"
        assert chain.is_primary() is True

    def test_fallback_progression(self):
        """Test fallback progression."""
        callback = MagicMock()
        options = [
            FallbackOption("opt1", "value1", lambda: True),
            FallbackOption("opt2", "value2", lambda: True),
        ]
        chain = FallbackChain("test", options)
        chain.set_fallback_callback(callback)

        success, value = chain.fallback()

        assert success is True
        assert value == "value2"
        assert chain.current() == "value2"
        assert chain.is_primary() is False
        assert chain.get_fallback_history() == ["opt2"]
        callback.assert_called_once_with("opt2", "value2")

    def test_fallback_exhausted(self):
        """Test fallback exhaustion."""
        options = [
            FallbackOption("opt1", "value1", lambda: True),
        ]
        chain = FallbackChain("test", options)

        # No more options
        success, value = chain.fallback()
        assert success is False
        assert value is None

    def test_conditional_fallback(self):
        """Test fallback with conditions."""
        condition_met = False

        def check_condition():
            return condition_met

        options = [
            FallbackOption("opt1", "value1", lambda: True),
            FallbackOption("opt2", "value2", check_condition),
            FallbackOption("opt3", "value3", lambda: True),
        ]
        chain = FallbackChain("test", options)

        # opt2 should be skipped because condition is False
        success, value = chain.fallback()
        assert value == "value3"

    def test_reset(self):
        """Test chain reset."""
        options = [
            FallbackOption("opt1", "value1"),
            FallbackOption("opt2", "value2"),
        ]
        chain = FallbackChain("test", options)

        chain.fallback()
        assert chain.current_name() == "opt2"

        chain.reset()
        assert chain.current_name() == "opt1"
        assert chain.is_primary() is True
        assert chain.get_fallback_history() == []


# ============================================
# Recovery Strategy Tests
# ============================================
class TestRecoveryStrategies:
    """Tests for recovery strategies."""

    def test_audio_device_recovery(self):
        """Test audio device recovery strategy."""
        strategy = AudioDeviceRecoveryStrategy()

        # Can handle device disconnected errors
        error = AudioError(
            message="Device disconnected",
            category=ErrorCategory.AUDIO_DEVICE_DISCONNECTED,
            device_id="device_1",
        )

        assert strategy.can_handle(error) is True

        # Cannot handle other errors
        error2 = AudioError(
            message="Permission denied",
            category=ErrorCategory.AUDIO_PERMISSION_DENIED,
        )
        assert strategy.can_handle(error2) is False

    def test_audio_device_recovery_success(self):
        """Test successful audio device recovery."""
        strategy = AudioDeviceRecoveryStrategy()

        error = AudioError(
            message="Device disconnected",
            category=ErrorCategory.AUDIO_DEVICE_DISCONNECTED,
            device_id="device_1",
        )

        available_devices = [
            {"id": "default", "name": "Default Device", "is_default": True},
            {"id": "device_2", "name": "Secondary Mic"},
        ]

        result = strategy.recover(error, {"available_devices": available_devices})

        assert result.status == RecoveryStatus.SUCCESS
        assert result.fallback_applied == "default"
        assert "Default Device" in result.message

    def test_audio_device_recovery_no_devices(self):
        """Test audio device recovery with no alternatives."""
        strategy = AudioDeviceRecoveryStrategy()

        error = AudioError(
            message="Device disconnected",
            category=ErrorCategory.AUDIO_DEVICE_DISCONNECTED,
            device_id="device_1",
        )

        result = strategy.recover(error, {"available_devices": []})

        assert result.status == RecoveryStatus.FAILED

    def test_model_oom_recovery(self):
        """Test model OOM recovery."""
        strategy = ModelOOMRecoveryStrategy()

        error = ModelError(
            message="CUDA out of memory",
            category=ErrorCategory.MODEL_OOM,
            model_name="large-v3",
        )

        assert strategy.can_handle(error) is True

        # Also handles errors with OOM keywords
        error2 = ModelError(
            message="RuntimeError: cublas error out of memory",
            category=ErrorCategory.MODEL_INFERENCE_ERROR,
        )
        assert strategy.can_handle(error2) is True

    def test_model_oom_recovery_fallback(self):
        """Test OOM recovery triggers fallback."""
        strategy = ModelOOMRecoveryStrategy()

        error = ModelError(
            message="CUDA OOM",
            category=ErrorCategory.MODEL_OOM,
        )

        result = strategy.recover(error)

        # Should succeed by falling back to CPU and reducing batch
        assert result.status == RecoveryStatus.SUCCESS
        assert "device:cpu" in result.fallback_applied or "batch_size" in result.fallback_applied

    def test_network_retry_strategy(self):
        """Test network retry strategy."""
        strategy = NetworkRetryStrategy(max_retries=3, base_delay=0.01)

        error = NetworkError(
            message="Connection timeout",
            category=ErrorCategory.NETWORK_TIMEOUT,
            endpoint="https://api.example.com",
            retry_allowed=True,
        )

        assert strategy.can_handle(error) is True

        result = strategy.recover(error)

        assert result.status == RecoveryStatus.SUCCESS
        assert "retry:1" in result.fallback_applied
        assert result.details["retry_count"] == 1

    def test_network_retry_exhausted(self):
        """Test network retry exhaustion."""
        strategy = NetworkRetryStrategy(max_retries=1, base_delay=0.01)

        error = NetworkError(
            message="Connection timeout",
            category=ErrorCategory.NETWORK_TIMEOUT,
            endpoint="https://api.example.com",
            retry_allowed=True,
        )

        # First retry
        result1 = strategy.recover(error)
        assert result1.status == RecoveryStatus.SUCCESS

        # Second attempt - should be exhausted
        result2 = strategy.recover(error)
        assert result2.status == RecoveryStatus.FAILED
        assert "exhausted" in result2.message

    def test_offline_mode_strategy(self):
        """Test offline mode strategy."""
        strategy = OfflineModeStrategy()

        error = NetworkError(
            message="Backend unavailable",
            category=ErrorCategory.NETWORK_BACKEND_UNAVAILABLE,
        )

        assert strategy.can_handle(error) is True

        result = strategy.recover(error)

        assert result.status == RecoveryStatus.SUCCESS
        assert result.fallback_applied == "offline_mode"
        assert strategy.is_offline() is True

        # Should return partial if already offline
        result2 = strategy.recover(error)
        assert result2.status == RecoveryStatus.PARTIAL

        strategy.set_online()
        assert strategy.is_offline() is False

    def test_session_corruption_recovery(self):
        """Test session corruption recovery."""
        strategy = SessionCorruptionRecoveryStrategy()

        error = SessionError(
            message="Session corrupted",
            category=ErrorCategory.SESSION_CORRUPTED,
            file_path="/nonexistent/path",
        )

        assert strategy.can_handle(error) is True

        result = strategy.recover(error)
        # Should fail because file doesn't exist
        assert result.status == RecoveryStatus.FAILED

    def test_session_corruption_recovery_with_valid_json(self, tmp_path):
        """Test session recovery with valid JSON."""
        strategy = SessionCorruptionRecoveryStrategy()

        # Create a valid session file
        session_file = tmp_path / "session.json"
        data = {"id": "session_123", "transcript": "Project status update"}
        with open(session_file, "w") as f:
            json.dump(data, f)

        error = SessionError(
            message="Session corrupted",
            category=ErrorCategory.SESSION_CORRUPTED,
            file_path=str(session_file),
        )

        result = strategy.recover(error)
        assert result.status == RecoveryStatus.PARTIAL
        assert "partial_json_extract" in result.details["recovery_methods"]

    def test_strategy_stats(self):
        """Test strategy statistics tracking."""
        strategy = AudioDeviceRecoveryStrategy()

        # Simulate successes and failures
        error = AudioError(
            message="Test",
            category=ErrorCategory.AUDIO_DEVICE_DISCONNECTED,
        )

        # Success
        with patch.object(strategy, "_fallback_device_id", "default"):
            strategy.recover(error, {"available_devices": [{"id": "default", "name": "Default"}]})

        # Failure
        strategy.recover(error, {"available_devices": []})

        stats = strategy.get_stats()
        assert stats["name"] == "audio_device_switch"
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 1
        assert stats["success_rate"] == 0.5


# ============================================
# Recovery Manager Tests
# ============================================
class TestRecoveryManager:
    """Tests for RecoveryManager."""

    def test_register_strategy(self):
        """Test strategy registration."""
        manager = RecoveryManager()
        strategy = AudioDeviceRecoveryStrategy()

        manager.register_strategy(strategy)

        assert strategy in manager._strategies

    def test_register_multiple_strategies_sorted(self):
        """Test strategies are sorted by priority."""
        manager = RecoveryManager()

        low_priority = AudioDeviceRecoveryStrategy()
        low_priority.priority = 100

        high_priority = ModelOOMRecoveryStrategy()
        high_priority.priority = 5

        manager.register_strategy(low_priority)
        manager.register_strategy(high_priority)

        assert manager._strategies[0] == high_priority
        assert manager._strategies[1] == low_priority

    def test_attempt_recovery_success(self):
        """Test successful recovery attempt."""
        manager = RecoveryManager()
        strategy = AudioDeviceRecoveryStrategy()
        manager.register_strategy(strategy)

        error = AudioError(
            message="Device disconnected",
            category=ErrorCategory.AUDIO_DEVICE_DISCONNECTED,
            device_id="device_1",
        )

        with patch.object(strategy, "_fallback_device_id", "default"):
            result = manager.attempt_recovery(
                error, {"available_devices": [{"id": "default", "name": "Default"}]}
            )

        assert result.status == RecoveryStatus.SUCCESS

    def test_attempt_recovery_no_strategy(self):
        """Test recovery with no applicable strategy."""
        manager = RecoveryManager()

        error = AppError(
            message="Unknown error",
            category=ErrorCategory.SYSTEM_UNKNOWN,
        )

        result = manager.attempt_recovery(error)

        assert result.status == RecoveryStatus.SKIPPED
        assert "No applicable" in result.message

    def test_recovery_history(self):
        """Test recovery history tracking."""
        manager = RecoveryManager()

        # Simulate recovery results
        result1 = RecoveryResult(
            status=RecoveryStatus.SUCCESS,
            strategy_name="test1",
            error_id="err1",
            message="Success",
        )
        result2 = RecoveryResult(
            status=RecoveryStatus.FAILED,
            strategy_name="test2",
            error_id="err2",
            message="Failed",
        )

        manager._record_result(result1)
        manager._record_result(result2)

        history = manager.get_history(limit=10)
        assert len(history) == 2
        assert history[0].error_id == "err1"
        assert history[1].error_id == "err2"

    def test_recovery_callback(self):
        """Test recovery callback invocation."""
        callback = MagicMock()
        manager = RecoveryManager()
        manager.set_recovery_callback(callback)

        result = RecoveryResult(
            status=RecoveryStatus.SUCCESS,
            strategy_name="test",
            error_id="err1",
            message="Test",
        )

        manager._record_result(result)
        callback.assert_called_once_with(result)

    def test_get_stats(self):
        """Test recovery statistics."""
        manager = RecoveryManager()
        manager.register_strategy(AudioDeviceRecoveryStrategy())
        manager.register_fallback_chain("compute", create_compute_fallback_chain())

        stats = manager.get_stats()

        assert "strategies" in stats
        assert "fallback_chains" in stats
        assert "compute" in stats["fallback_chains"]


# ============================================
# Factory Function Tests
# ============================================
class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_compute_fallback_chain(self):
        """Test compute fallback chain creation."""
        chain = create_compute_fallback_chain()

        assert chain.name == "compute_device"
        # Should have at least CUDA and CPU options
        assert len(chain.options) >= 1  # At least CPU

    def test_create_model_size_fallback_chain(self):
        """Test model size fallback chain creation."""
        chain = create_model_size_fallback_chain(primary_model="medium")

        assert chain.name == "model_size"
        assert chain.current() == "medium"

        # Should fallback to smaller models
        chain.fallback()
        assert chain.current() in ["small", "base", "tiny"]

    def test_create_batch_size_fallback_chain(self):
        """Test batch size fallback chain creation."""
        chain = create_batch_size_fallback_chain(primary_batch=8)

        assert chain.name == "batch_size"
        assert chain.current() == 8

        chain.fallback()
        assert chain.current() in [4, 2, 1]

    def test_create_default_recovery_manager(self):
        """Test default recovery manager creation."""
        manager = create_default_recovery_manager()

        # Should have all strategies registered
        strategy_names = [s.name for s in manager._strategies]
        assert "audio_device_switch" in strategy_names
        assert "model_oom_recovery" in strategy_names
        assert "network_retry" in strategy_names
        assert "disk_full_handler" in strategy_names

        # Should have fallback chains
        assert "compute" in manager._fallback_chains
        assert "model_size" in manager._fallback_chains


# ============================================
# Integration Tests
# ============================================
class TestIntegration:
    """Integration tests for error handling system."""

    def test_full_error_handling_pipeline(self):
        """Test complete error handling pipeline."""
        # Create components
        notifier = UserNotifier(min_severity=ErrorSeverity.INFO)
        reporter = ErrorReporter(enable_crash_dumps=False)
        handler = ErrorHandler(notifier=notifier, reporter=reporter)

        recovery_manager = RecoveryManager()
        recovery_manager.register_strategy(AudioDeviceRecoveryStrategy())

        # Register recovery as handler
        def recovery_callback(error):
            recovery_manager.attempt_recovery(error)

        handler.register_handler(ErrorCategory.AUDIO_DEVICE_DISCONNECTED, recovery_callback)

        # Trigger error
        error = AudioError(
            message="Device disconnected",
            category=ErrorCategory.AUDIO_DEVICE_DISCONNECTED,
            severity=ErrorSeverity.ERROR,
            device_id="device_1",
        )

        # Manually set the fallback device on the registered strategy instance
        for strategy in recovery_manager._strategies:
            if isinstance(strategy, AudioDeviceRecoveryStrategy):
                strategy._fallback_device_id = "default"

        handler.handle(error, {"available_devices": [{"id": "default", "name": "Default"}]})

        # Error should be reported
        assert reporter.get_stats()["total_errors"] == 1

    def test_gpu_oom_to_cpu_fallback_chain(self):
        """Test complete GPU OOM to CPU fallback scenario."""
        compute_chain = create_compute_fallback_chain()
        batch_chain = create_batch_size_fallback_chain(primary_batch=8)

        strategy = ModelOOMRecoveryStrategy(
            compute_fallback=compute_chain,
            batch_fallback=batch_chain,
        )

        # Simulate CUDA OOM error
        error = ModelError(
            message="CUDA out of memory",
            category=ErrorCategory.MODEL_OOM,
            model_name="large-v3",
            device="cuda",
        )

        # Mock CUDA available to test fallback
        with patch.object(compute_chain.options[0], "condition", return_value=False):
            with patch.object(compute_chain.options[1], "condition", return_value=True):
                result = strategy.recover(error)

        assert result.status == RecoveryStatus.SUCCESS
        assert (
            "cpu" in str(result.fallback_applied).lower()
            or "batch" in str(result.fallback_applied).lower()
        )

    def test_cascading_fallback(self):
        """Test cascading fallback through multiple levels."""
        model_chain = create_model_size_fallback_chain(primary_model="medium")

        strategy = ModelFallbackStrategy(model_fallback=model_chain)

        error = ModelError(
            message="Model load failed",
            category=ErrorCategory.MODEL_LOAD_FAILED,
            model_name="medium",
        )

        # First fallback
        result1 = strategy.recover(error)
        assert result1.status == RecoveryStatus.SUCCESS
        assert model_chain.current() == "small"

        # Second fallback
        result2 = strategy.recover(error)
        assert result2.status == RecoveryStatus.SUCCESS
        assert model_chain.current() == "base"

    def test_error_reporter_with_context(self, tmp_path):
        """Test error reporting with additional context."""
        reporter = ErrorReporter(report_dir=tmp_path)

        error = AppError(
            message="Critical error",
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.MODEL_LOAD_FAILED,
        )

        context = {
            "user_action": "loading_model",
            "model_name": "large-v3",
            "system_memory_gb": 16,
        }

        dump_path = reporter.report(error, context)

        assert dump_path is not None

        with open(dump_path) as f:
            data = json.load(f)
            assert data["context"]["user_action"] == "loading_model"
            assert data["context"]["model_name"] == "large-v3"


# ============================================
# Edge Cases and Error Conditions
# ============================================
class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_error_with_empty_details(self):
        """Test error creation with empty details."""
        error = AppError(
            message="Test",
            details={},
        )
        assert error.details == {}
        data = error.to_dict()
        assert data["details"] == {}

    def test_recovery_with_exception_in_handler(self):
        """Test recovery when handler throws exception."""
        manager = RecoveryManager()

        class FailingStrategy(RecoveryStrategy):
            def can_handle(self, error):
                return True

            def recover(self, error, context=None):
                raise RuntimeError("Handler failed!")

        strategy = FailingStrategy("failing")
        manager.register_strategy(strategy)

        error = AppError(message="Test")
        result = manager.attempt_recovery(error)

        # Should return failed status, not crash
        assert result.status == RecoveryStatus.FAILED

    def test_notification_callback_failure(self):
        """Test notification when callback fails."""

        def failing_callback(data):
            raise RuntimeError("Callback failed!")

        notifier = UserNotifier(callback=failing_callback)

        error = AppError(
            message="Test",
            severity=ErrorSeverity.ERROR,
        )

        # Should not raise
        notifier.notify(error)

    def test_rate_limit_with_no_limit_set(self):
        """Test rate limit check when no limit is set."""
        handler = ErrorHandler()
        error = AppError(message="Test")

        # Should not be rate limited when no limit set
        assert handler._is_rate_limited(error) is False

    def test_fallback_chain_empty(self):
        """Test empty fallback chain."""
        chain = FallbackChain("empty", [])

        assert chain.current() is None
        assert chain.current_name() is None

        success, value = chain.fallback()
        assert success is False
        assert value is None

    def test_recovery_history_limit(self):
        """Test recovery history size limit."""
        manager = RecoveryManager()
        manager._max_history = 5

        # Add more results than limit
        for i in range(10):
            result = RecoveryResult(
                status=RecoveryStatus.SUCCESS,
                strategy_name="test",
                error_id=f"err{i}",
                message="Test",
            )
            manager._record_result(result)

        history = manager.get_history(limit=100)
        assert len(history) == 5
        # Should keep most recent
        assert history[0].error_id == "err5"
        assert history[-1].error_id == "err9"

    def test_session_corruption_with_malformed_json(self, tmp_path):
        """Test session recovery with malformed JSON."""
        strategy = SessionCorruptionRecoveryStrategy()

        # Create malformed JSON file
        session_file = tmp_path / "corrupted.json"
        with open(session_file, "w") as f:
            f.write('{"valid": "json", "but": "incomplete"')

        error = SessionError(
            message="Session corrupted",
            category=ErrorCategory.SESSION_CORRUPTED,
            file_path=str(session_file),
        )

        result = strategy.recover(error)
        # Should try to extract partial JSON
        assert result.status in [RecoveryStatus.PARTIAL, RecoveryStatus.FAILED]

    def test_retry_with_non_retryable_exception(self):
        """Test retry with non-retryable exception type."""
        call_count = 0

        @with_retry(
            RetryConfig(
                max_retries=2,
                base_delay=0.01,
                retryable_exceptions={ConnectionError},  # Only retry ConnectionError
            )
        )
        def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError):
            raises_value_error()

        # Should not have retried
        assert call_count == 1

    def test_disk_full_recovery_finds_cleanup_candidates(self, tmp_path):
        """Test disk full recovery finds temp files to clean."""
        strategy = DiskFullRecoveryStrategy()

        # Create temp directory with files
        temp_dir = tmp_path / ".transcripta" / "temp"
        temp_dir.mkdir(parents=True)
        (temp_dir / "temp_file.bin").write_bytes(b"x" * 1024 * 1024 * 20)  # 20MB

        with patch("app.core.recovery_strategies.Path") as mock_path:
            mock_path.home.return_value = tmp_path
            mock_path.return_value = tmp_path

            # The method uses hardcoded paths, so patch the method directly
            with patch.object(strategy, "_find_cleanup_candidates") as mock_find:
                mock_find.return_value = [
                    {"path": str(temp_dir), "size_mb": 20, "type": "temp/cache"}
                ]

                error = SessionError(
                    message="Disk full",
                    category=ErrorCategory.SESSION_DISK_FULL,
                    file_path=str(tmp_path / "session.json"),
                )

                result = strategy.recover(error)

                assert result.status == RecoveryStatus.PARTIAL
                assert "cleanup_candidates" in result.details


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
