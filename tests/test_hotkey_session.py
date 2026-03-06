"""Unit tests for hotkey session handler.

Tests cover:
- State machine transitions
- Circular audio buffer functionality
- Metrics collection
- Text injection (mocked)
- Session lifecycle
- Error handling and graceful degradation
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

from app.core.hotkey_session import (
    CircularAudioBuffer,
    HotkeySession,
    HotkeySessionConfig,
    HotkeySessionMetrics,
    HotkeySessionPool,
    HotkeySessionState,
    PlatformTextInjector,
)


class TestCircularAudioBuffer:
    """Tests for CircularAudioBuffer."""

    def test_init(self):
        """Test buffer initialization."""
        buffer = CircularAudioBuffer(sample_rate=16000, max_duration_seconds=10.0)
        assert buffer.sample_rate == 16000
        assert buffer.max_duration_seconds == 10.0
        assert buffer.max_samples == 160000
        assert buffer.sample_count == 0
        assert buffer.duration_seconds == 0.0
        assert not buffer.is_full

    def test_push_and_get(self):
        """Test pushing and retrieving audio data."""
        buffer = CircularAudioBuffer(sample_rate=16000)
        samples = np.random.randn(1600).astype(np.float32)  # 100ms

        count = buffer.push(samples)
        assert count == 1600
        assert buffer.sample_count == 1600
        assert buffer.duration_seconds == 0.1

        retrieved = buffer.get_all()
        np.testing.assert_array_equal(retrieved, samples)

    def test_circular_overwrite(self):
        """Test that old data is overwritten when buffer is full."""
        buffer = CircularAudioBuffer(sample_rate=16000, max_duration_seconds=1.0)
        max_samples = buffer.max_samples

        # Push more data than buffer can hold
        samples1 = np.ones(max_samples // 2) * 1.0
        samples2 = np.ones(max_samples // 2) * 2.0
        samples3 = np.ones(max_samples // 2) * 3.0

        buffer.push(samples1)
        buffer.push(samples2)
        buffer.push(samples3)  # Should overwrite part of samples1

        retrieved = buffer.get_all()
        # Buffer should contain end of samples2 and all of samples3
        assert len(retrieved) == max_samples
        assert np.all(retrieved[max_samples // 2 :] == 3.0)

    def test_clear(self):
        """Test buffer clear operation."""
        buffer = CircularAudioBuffer(sample_rate=16000)
        samples = np.random.randn(1600).astype(np.float32)

        buffer.push(samples)
        assert buffer.sample_count == 1600

        buffer.clear()
        assert buffer.sample_count == 0
        assert buffer.duration_seconds == 0.0
        assert len(buffer.get_all()) == 0

    def test_thread_safety(self):
        """Test thread-safe operations."""
        buffer = CircularAudioBuffer(sample_rate=16000)
        errors = []
        results = {"total_pushed": 0}

        def push_samples():
            try:
                for _ in range(100):
                    samples = np.random.randn(160).astype(np.float32)
                    count = buffer.push(samples)
                    results["total_pushed"] += count
                    time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=push_samples) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert buffer.sample_count > 0


class TestHotkeySessionMetrics:
    """Tests for HotkeySessionMetrics."""

    def test_init(self):
        """Test metrics initialization."""
        metrics = HotkeySessionMetrics(session_id="test123")
        assert metrics.session_id == "test123"
        assert metrics.duration_seconds == 0.0
        assert metrics.errors == []

    def test_duration_calculations(self):
        """Test duration property calculations."""
        metrics = HotkeySessionMetrics(session_id="test")
        now = time.monotonic()

        metrics.start_time = now
        metrics.stop_time = now + 5.0
        metrics.completion_time = now + 6.0

        assert metrics.recording_duration_seconds == 5.0
        assert metrics.duration_seconds == 6.0

    def test_latency_calculations(self):
        """Test latency property calculations."""
        metrics = HotkeySessionMetrics(session_id="test")
        now = time.monotonic()

        metrics.start_time = now
        metrics.first_audio_time = now + 0.05  # 50ms
        metrics.processing_start_time = now + 5.0
        metrics.completion_time = now + 5.5

        assert metrics.hotkey_to_audio_latency_ms == 50.0
        assert metrics.processing_latency_ms == 500.0

    def test_to_dict(self):
        """Test serialization to dictionary."""
        metrics = HotkeySessionMetrics(session_id="test")
        metrics.start_time = time.monotonic()
        metrics.stop_time = metrics.start_time + 1.0
        metrics.completion_time = metrics.stop_time + 0.5
        metrics.final_text_length = 100
        metrics.confidence = 0.85
        metrics.inject_success = True

        data = metrics.to_dict()
        assert data["session_id"] == "test"
        assert data["final_text_length"] == 100
        assert data["confidence"] == 0.85
        assert data["inject_success"] is True
        assert "duration_seconds" in data


class TestHotkeySessionConfig:
    """Tests for HotkeySessionConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = HotkeySessionConfig()
        assert config.sample_rate == 16000
        assert config.max_duration_seconds == 60.0
        assert config.auto_inject is True
        assert config.copy_to_clipboard is True
        assert config.save_sessions is False
        assert config.model_name == "tiny"
        assert config.beam_size == 1

    def test_custom_config(self):
        """Test custom configuration."""
        config = HotkeySessionConfig(
            sample_rate=22050,
            max_duration_seconds=30.0,
            auto_inject=False,
            save_sessions=True,
            model_name="base",
        )
        assert config.sample_rate == 22050
        assert config.max_duration_seconds == 30.0
        assert config.auto_inject is False
        assert config.save_sessions is True
        assert config.model_name == "base"

    def test_output_dir_default(self):
        """Test default output directory creation."""
        config = HotkeySessionConfig()
        assert config.output_dir is not None
        assert ".transcripta" in str(config.output_dir)
        assert "hotkey_sessions" in str(config.output_dir)


class TestPlatformTextInjector:
    """Tests for PlatformTextInjector."""

    def test_init(self):
        """Test injector initialization."""
        injector = PlatformTextInjector()
        assert injector._platform in ["windows", "darwin", "linux"]
        assert injector.last_error is None

    def test_copy_to_clipboard_fallback(self):
        """Test clipboard copy with fallback."""
        injector = PlatformTextInjector()

        # Mock platform-specific methods to fail
        with patch.object(injector, "_copy_windows", return_value=False):
            with patch.object(injector, "_copy_macos", return_value=False):
                with patch.object(injector, "_copy_linux", return_value=False):
                    with patch.object(injector, "_copy_fallback", return_value=True) as fallback:
                        result = injector.copy_to_clipboard("test text")
                        assert result is True
                        fallback.assert_called_once_with("test text")

    def test_inject_platform_detection(self):
        """Test platform detection in inject method."""
        injector = PlatformTextInjector()

        # Test that correct platform method is called
        if injector._platform == "windows":
            with patch.object(injector, "_inject_windows", return_value=True) as mock:
                result = injector.inject("test")
                assert result is True
                mock.assert_called_once_with("test")
        elif injector._platform == "darwin":
            with patch.object(injector, "_inject_macos", return_value=True) as mock:
                result = injector.inject("test")
                assert result is True
                mock.assert_called_once_with("test")
        else:
            with patch.object(injector, "_inject_linux", return_value=True) as mock:
                result = injector.inject("test")
                assert result is True
                mock.assert_called_once_with("test")

    def test_inject_failure_handling(self):
        """Test graceful handling of injection failures."""
        injector = PlatformTextInjector()

        with patch.object(injector, "_inject_windows", side_effect=Exception("Test error")):
            with patch.object(injector, "_platform", "windows"):
                result = injector.inject("test")
                assert result is False
                assert injector.last_error is not None


class TestHotkeySession:
    """Tests for HotkeySession lifecycle and functionality."""

    def test_init(self):
        """Test session initialization."""
        config = HotkeySessionConfig()
        session = HotkeySession(config=config)

        assert session.state == HotkeySessionState.IDLE
        assert session.session_id is not None
        assert len(session.session_id) == 12
        assert session.transcription_result == ""
        assert session.config == config

    def test_state_transitions(self):
        """Test state machine transitions."""
        config = HotkeySessionConfig()
        session = HotkeySession(config=config)

        # Start with mocked audio
        with patch.object(session, "_recording_loop"):
            with patch.object(session, "_recording_thread"):
                result = session.start()
                # Won't fully start without actual audio, but state should change
                # or error out
                assert session.state in [HotkeySessionState.RECORDING, HotkeySessionState.ERROR]

    def test_cannot_start_while_recording(self):
        """Test that starting while already recording fails."""
        config = HotkeySessionConfig()
        session = HotkeySession(config=config)

        # Manually set state to RECORDING
        session._state = HotkeySessionState.RECORDING

        result = session.start()
        assert result is False

    def test_cannot_stop_while_idle(self):
        """Test that stopping while idle fails."""
        config = HotkeySessionConfig()
        session = HotkeySession(config=config)

        assert session.state == HotkeySessionState.IDLE
        result = session.stop()
        assert result is False

    def test_set_callbacks(self):
        """Test callback registration."""
        config = HotkeySessionConfig()
        session = HotkeySession(config=config)

        on_partial = Mock()
        on_state_change = Mock()
        on_complete = Mock()
        on_error = Mock()

        session.set_callbacks(
            on_partial=on_partial,
            on_state_change=on_state_change,
            on_complete=on_complete,
            on_error=on_error,
        )

        assert session._on_partial == on_partial
        assert session._on_state_change == on_state_change
        assert session._on_complete == on_complete
        assert session._on_error == on_error

    def test_metrics_accessible(self):
        """Test that metrics are accessible."""
        config = HotkeySessionConfig()
        session = HotkeySession(config=config)

        metrics = session.metrics
        assert isinstance(metrics, HotkeySessionMetrics)
        assert metrics.session_id == session.session_id

    def test_to_dict(self):
        """Test session serialization."""
        config = HotkeySessionConfig()
        session = HotkeySession(config=config)

        data = session.to_dict()
        assert data["session_id"] == session.session_id
        assert data["state"] == "IDLE"
        assert "metrics" in data
        assert "transcription_result" in data

    def test_force_cleanup(self):
        """Test forced cleanup."""
        config = HotkeySessionConfig()
        session = HotkeySession(config=config)

        # Add some data to buffer
        samples = np.random.randn(1600).astype(np.float32)
        session._audio_buffer.push(samples)
        assert session._audio_buffer.sample_count == 1600

        # Force cleanup
        session.force_cleanup()
        assert session._audio_buffer.sample_count == 0
        assert session.state == HotkeySessionState.IDLE

    def test_handle_output_inject_success(self):
        """Test successful text injection."""
        config = HotkeySessionConfig(auto_inject=True, copy_to_clipboard=False)
        mock_injector = Mock()
        mock_injector.inject.return_value = True

        session = HotkeySession(config=config, text_injector=mock_injector)
        session._transcription_result = "Project status update"
        session._handle_output()

        mock_injector.inject.assert_called_once_with("Project status update")
        assert session._metrics.inject_success is True

    def test_handle_output_inject_fails_fallback_to_clipboard(self):
        """Test fallback to clipboard when inject fails."""
        config = HotkeySessionConfig(auto_inject=True, copy_to_clipboard=True)
        mock_injector = Mock()
        mock_injector.inject.return_value = False
        mock_injector.copy_to_clipboard.return_value = True

        session = HotkeySession(config=config, text_injector=mock_injector)
        session._transcription_result = "Project status update"
        session._handle_output()

        mock_injector.inject.assert_called_once_with("Project status update")
        mock_injector.copy_to_clipboard.assert_called_once_with("Project status update")
        assert session._metrics.inject_success is False

    def test_handle_output_clipboard_only(self):
        """Test clipboard-only mode."""
        config = HotkeySessionConfig(auto_inject=False, copy_to_clipboard=True)
        mock_injector = Mock()
        mock_injector.copy_to_clipboard.return_value = True

        session = HotkeySession(config=config, text_injector=mock_injector)
        session._transcription_result = "Project status update"
        session._handle_output()

        mock_injector.inject.assert_not_called()
        mock_injector.copy_to_clipboard.assert_called_once_with("Project status update")

    def test_save_session(self, tmp_path):
        """Test session saving to disk."""
        config = HotkeySessionConfig(save_sessions=True, output_dir=tmp_path)
        session = HotkeySession(config=config)
        session._transcription_result = "Test transcript"
        session._metrics.final_text_length = 15
        session._metrics.confidence = 0.9

        session._save_session()

        # Check files were created
        txt_files = list(tmp_path.glob("*.txt"))
        json_files = list(tmp_path.glob("*.json"))
        assert len(txt_files) == 1
        assert len(json_files) == 1

        # Verify content
        assert txt_files[0].read_text() == "Test transcript"

    def test_short_audio_skips_transcription(self):
        """Test that very short audio is skipped."""
        config = HotkeySessionConfig()
        session = HotkeySession(config=config)

        # Add very short audio (< 300ms)
        samples = np.random.randn(1000).astype(np.float32)  # ~62ms at 16kHz
        session._audio_buffer.push(samples)

        with patch.object(session, "_complete_session") as mock_complete:
            with patch.object(session, "_transition_state"):
                session._process_transcription()
                assert session._transcription_result == ""
                mock_complete.assert_called_once()

    def test_transcription_result_empty_handling(self):
        """Test handling of empty transcription results."""
        config = HotkeySessionConfig(auto_inject=True)
        mock_injector = Mock()

        session = HotkeySession(config=config, text_injector=mock_injector)
        session._transcription_result = ""
        session._handle_output()

        # Should not attempt inject/copy with empty text
        mock_injector.inject.assert_not_called()
        mock_injector.copy_to_clipboard.assert_not_called()


class TestHotkeySessionPool:
    """Tests for HotkeySessionPool."""

    def test_init(self):
        """Test pool initialization."""
        config = HotkeySessionConfig()
        pool = HotkeySessionPool(config=config, pool_size=3)

        assert pool.config == config
        assert pool.pool_size == 3
        assert not pool.is_ready
        assert pool.active_session is None

    def test_preload(self):
        """Test model preloading."""
        config = HotkeySessionConfig()
        pool = HotkeySessionPool(config=config)

        with patch("app.stt.fast_engine.FastTranscriber") as mock_transcriber_class:
            mock_transcriber = Mock()
            mock_transcriber.load_model = Mock()
            mock_transcriber_class.return_value = mock_transcriber

            result = pool.preload()
            assert result is True
            assert pool.is_ready
            mock_transcriber.load_model.assert_called_once()

    def test_preload_failure(self):
        """Test preload failure handling."""
        config = HotkeySessionConfig()
        pool = HotkeySessionPool(config=config)

        with patch("app.stt.fast_engine.FastTranscriber", side_effect=Exception("Load failed")):
            result = pool.preload()
            assert result is False
            assert not pool.is_ready

    def test_acquire_and_release(self):
        """Test session acquisition and release."""
        config = HotkeySessionConfig()
        pool = HotkeySessionPool(config=config)

        # Acquire session
        session = pool.acquire()
        assert isinstance(session, HotkeySession)
        assert pool.active_session is session

        # Release session
        with patch.object(session, "force_cleanup") as mock_cleanup:
            pool.release(session)
            mock_cleanup.assert_called_once()
            assert pool.active_session is None

    def test_acquire_replaces_active(self):
        """Test that acquiring replaces existing active session."""
        config = HotkeySessionConfig()
        pool = HotkeySessionPool(config=config)

        session1 = pool.acquire()
        with patch.object(session1, "force_cleanup") as mock_cleanup:
            session2 = pool.acquire()
            mock_cleanup.assert_called_once()
            assert pool.active_session is session2

    def test_acquire_shares_transcriber(self):
        """Test that acquired sessions share preloaded transcriber."""
        config = HotkeySessionConfig()
        pool = HotkeySessionPool(config=config)

        # Preload transcriber
        mock_transcriber = Mock()
        pool._transcriber = mock_transcriber

        # Acquire session
        session = pool.acquire()
        assert session._transcriber is mock_transcriber


class TestIntegrationScenarios:
    """Integration-style tests for common scenarios."""

    def test_complete_session_lifecycle(self):
        """Test a complete session from start to finish."""
        config = HotkeySessionConfig()
        session = HotkeySession(config=config)

        state_changes = []

        def on_state_change(old, new):
            state_changes.append((old.name, new.name))

        session.set_callbacks(on_state_change=on_state_change)

        # Simulate session lifecycle
        with patch.object(session, "_recording_loop"):
            session.start()
            assert session.state == HotkeySessionState.RECORDING

        # Manually add some audio
        samples = np.random.randn(8000).astype(np.float32)  # 500ms
        session._audio_buffer.push(samples)

        with patch.object(session, "_process_transcription"):
            session.stop()
            assert session.state in [HotkeySessionState.PROCESSING, HotkeySessionState.ERROR]

        # Check state transitions were tracked
        assert len(state_changes) >= 1

    def test_error_recovery(self):
        """Test error handling and recovery."""
        config = HotkeySessionConfig()
        session = HotkeySession(config=config)

        errors = []
        session.set_callbacks(on_error=errors.append)

        # Simulate an error during processing
        session._error = "Test error"
        session._transition_state(HotkeySessionState.ERROR)

        assert session.state == HotkeySessionState.ERROR

        # Cleanup should still work
        session.force_cleanup()
        assert session.state == HotkeySessionState.IDLE

    def test_rapid_start_stop(self):
        """Test rapid start/stop cycles."""
        config = HotkeySessionConfig()
        pool = HotkeySessionPool(config=config)

        for _ in range(3):
            session = pool.acquire()
            with patch.object(session, "_recording_loop"):
                session.start()
            session.force_cleanup()
            pool.release(session)

            # Should be able to acquire again immediately
            session2 = pool.acquire()
            assert session2.state == HotkeySessionState.IDLE
            pool.release(session2)

    def test_concurrent_sessions_not_allowed(self):
        """Test that only one session can be active at a time."""
        config = HotkeySessionConfig()
        pool = HotkeySessionPool(config=config)

        session1 = pool.acquire()
        with patch.object(session1, "_recording_loop"):
            session1.start()

        # Try to start another session on same pool
        session2 = pool.acquire()  # This should cleanup session1
        assert pool.active_session is session2


class TestPerformanceRequirements:
    """Tests for performance requirements."""

    def test_hotkey_to_audio_latency(self):
        """Verify hotkey-to-audio latency is under 100ms target."""
        # This is a smoke test - real latency depends on hardware
        buffer = CircularAudioBuffer(sample_rate=16000)

        start_time = time.perf_counter()
        samples = np.zeros(160, dtype=np.float32)  # 10ms of silence
        buffer.push(samples)
        latency_ms = (time.perf_counter() - start_time) * 1000

        # Buffer operations should be extremely fast (< 1ms)
        assert latency_ms < 1.0

    def test_memory_buffer_no_disk_io(self):
        """Verify audio buffer doesn't perform disk I/O."""
        buffer = CircularAudioBuffer(sample_rate=16000, max_duration_seconds=5.0)

        # Push significant amount of data
        with patch("builtins.open") as mock_open:
            for _ in range(100):
                samples = np.random.randn(1600).astype(np.float32)
                buffer.push(samples)

            # Should never open any files
            mock_open.assert_not_called()

    def test_metrics_accuracy(self):
        """Test that metrics accurately track performance."""
        metrics = HotkeySessionMetrics(session_id="perf_test")

        # Simulate a recording session
        metrics.start_time = time.monotonic()
        time.sleep(0.01)  # 10ms
        metrics.first_audio_time = time.monotonic()
        time.sleep(0.05)  # 50ms
        metrics.stop_time = time.monotonic()
        time.sleep(0.02)  # 20ms
        metrics.processing_start_time = time.monotonic()
        time.sleep(0.1)  # 100ms
        metrics.completion_time = time.monotonic()

        # Verify metrics are reasonable
        assert metrics.hotkey_to_audio_latency_ms >= 10.0
        assert metrics.recording_duration_seconds >= 0.06
        assert metrics.processing_latency_ms >= 100.0
        assert metrics.duration_seconds >= 0.16


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
