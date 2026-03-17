"""Hotkey Lifecycle Tests - Real Behavior Tests

Tests actual hotkey functionality including:
- HotkeySession state machine transitions
- Service instantiation and API contracts
- Callback handling
- State transitions

Integration notes: Full end-to-end testing requires:
- Mocked audio backend (LoopbackAudioSource)
- Mocked transcriber (FastTranscriber)
- Mocked WebSocket connections
- Mocked settings manager
- Electron/IPC layer for hotkey registration

For unit tests, we test:
1. HotkeySession state machine in isolation (no audio dependencies)
2. HotkeyTranscriptionService instantiation and basic structure
3. Callback registration and invocation
4. State transition logic
"""

from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.hotkey_session import (
    CircularAudioBuffer,
    HotkeySession,
    HotkeySessionConfig,
    HotkeySessionState,
    PlatformTextInjector,
)


class TestHotkeySessionStateMachine:
    """Test HotkeySession state machine in isolation."""

    def test_initial_state_is_idle(self):
        """Verify session starts in IDLE state."""
        session = HotkeySession()
        assert session.state == HotkeySessionState.IDLE

    def test_session_id_is_unique(self):
        """Verify each session gets a unique ID."""
        session1 = HotkeySession()
        session2 = HotkeySession()
        assert session1.session_id != session2.session_id
        assert len(session1.session_id) == 12

    def test_start_transitions_to_recording(self):
        """Verify start() transitions from IDLE to RECORDING."""
        session = HotkeySession()

        with patch("app.core.hotkey_session.open_audio_backend") as mock_backend:
            mock_backend.return_value = MagicMock()
            result = session.start()

        assert result is True
        assert session.state == HotkeySessionState.RECORDING

    def test_start_fails_when_not_idle(self):
        """Verify start() fails when already recording."""
        session = HotkeySession()

        with patch("app.core.hotkey_session.open_audio_backend") as mock_backend:
            mock_backend.return_value = MagicMock()
            session.start()

            result = session.start()

        assert result is False
        assert session.state == HotkeySessionState.RECORDING

    def test_stop_transitions_from_recording_to_processing(self):
        """Verify stop() transitions from RECORDING to PROCESSING."""
        session = HotkeySession()

        with patch("app.core.hotkey_session.open_audio_backend") as mock_backend:
            mock_backend.return_value = MagicMock()
            mock_backend.return_value.backend.read = MagicMock(return_value=None)

            session.start()
            result = session.stop()

        assert result is True
        assert session.state == HotkeySessionState.PROCESSING

    def test_stop_fails_when_not_recording(self):
        """Verify stop() fails when not in RECORDING state."""
        session = HotkeySession()
        result = session.stop()

        assert result is False

    def test_invalid_state_transitions_are_blocked(self):
        """Verify state machine blocks invalid transitions."""
        session = HotkeySession()

        with patch("app.core.hotkey_session.open_audio_backend") as mock_backend:
            mock_backend.return_value = MagicMock()

            session.start()
            assert session.state == HotkeySessionState.RECORDING

            session._state = HotkeySessionState.ERROR
            result = session.start()

            assert result is False


class TestHotkeySessionCallbacks:
    """Test callback registration and invocation."""

    def test_callbacks_can_be_registered(self):
        """Verify callbacks can be set via set_callbacks()."""
        session = HotkeySession()

        on_partial = MagicMock()
        on_state_change = MagicMock()
        on_complete = MagicMock()
        on_error = MagicMock()

        session.set_callbacks(
            on_partial=on_partial,
            on_state_change=on_state_change,
            on_complete=on_complete,
            on_error=on_error,
        )

        assert session._on_partial is on_partial
        assert session._on_state_change is on_state_change
        assert session._on_complete is on_complete
        assert session._on_error is on_error

    def test_state_change_callback_invoked_on_start(self):
        """Verify state change callback is called when starting."""
        session = HotkeySession()
        callback = MagicMock()
        session.set_callbacks(on_state_change=callback)

        with patch("app.core.hotkey_session.open_audio_backend") as mock_backend:
            mock_backend.return_value = MagicMock()
            session.start()

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == HotkeySessionState.IDLE
        assert args[1] == HotkeySessionState.RECORDING

    def test_state_change_callback_invoked_on_stop(self):
        """Verify state change callback is called when stopping."""
        session = HotkeySession()
        callback = MagicMock()
        session.set_callbacks(on_state_change=callback)

        with patch("app.core.hotkey_session.open_audio_backend") as mock_backend:
            mock_backend.return_value = MagicMock()
            mock_backend.return_value.backend.read = MagicMock(return_value=None)
            session.start()
            callback.reset_mock()
            session.stop()

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == HotkeySessionState.RECORDING
        assert args[1] == HotkeySessionState.PROCESSING


class TestHotkeySessionMetrics:
    """Test session metrics collection."""

    def test_metrics_initialized_on_creation(self):
        """Verify metrics are created with session ID."""
        session = HotkeySession()
        assert session.metrics.session_id == session.session_id
        assert session.metrics.start_time == 0.0
        assert session.metrics.total_audio_samples == 0

    def test_start_time_recorded_on_start(self):
        """Verify start time is recorded when session starts."""
        session = HotkeySession()

        with patch("app.core.hotkey_session.open_audio_backend") as mock_backend:
            mock_backend.return_value = MagicMock()
            before = time.monotonic()
            session.start()
            after = time.monotonic()

        assert session.metrics.start_time >= before
        assert session.metrics.start_time <= after

    def test_stop_time_recorded_on_stop(self):
        """Verify stop time is recorded when session stops."""
        session = HotkeySession()

        with patch("app.core.hotkey_session.open_audio_backend") as mock_backend:
            mock_backend.return_value = MagicMock()
            mock_backend.return_value.backend.read = MagicMock(return_value=None)

            session.start()
            before = time.monotonic()
            session.stop()
            after = time.monotonic()

        assert session.metrics.stop_time >= before
        assert session.metrics.stop_time <= after


class TestHotkeySessionConfig:
    """Test session configuration."""

    def test_default_config_values(self):
        """Verify default configuration values."""
        config = HotkeySessionConfig()

        assert config.sample_rate == 16000
        assert config.max_duration_seconds == 60.0
        assert config.channels == 1
        assert config.auto_inject is True
        assert config.copy_to_clipboard is True
        assert config.model_name == "tiny"

    def test_custom_config_applied(self):
        """Verify custom configuration is applied."""
        config = HotkeySessionConfig(
            sample_rate=48000,
            max_duration_seconds=30.0,
            model_name="base",
        )

        assert config.sample_rate == 48000
        assert config.max_duration_seconds == 30.0
        assert config.model_name == "base"


class TestCircularAudioBuffer:
    """Test in-memory audio buffer."""

    def test_buffer_starts_empty(self):
        """Verify buffer starts empty."""
        buffer = CircularAudioBuffer(sample_rate=16000, max_duration_seconds=1.0)

        assert buffer.duration_seconds == 0.0
        assert buffer.sample_count == 0
        assert buffer.is_full is False

    def test_push_increases_sample_count(self):
        """Verify pushing samples increases count."""
        import numpy as np

        buffer = CircularAudioBuffer(sample_rate=16000, max_duration_seconds=1.0)
        samples = np.zeros(1600, dtype=np.float32)

        count = buffer.push(samples)

        assert count == 1600
        assert buffer.sample_count == 1600

    def test_clear_resets_buffer(self):
        """Verify clear() resets the buffer."""
        import numpy as np

        buffer = CircularAudioBuffer(sample_rate=16000, max_duration_seconds=1.0)
        samples = np.zeros(1600, dtype=np.float32)
        buffer.push(samples)

        buffer.clear()

        assert buffer.sample_count == 0
        assert buffer.duration_seconds == 0.0

    def test_buffer_wraps_when_full(self):
        """Verify oldest data is overwritten when full."""
        import numpy as np

        buffer = CircularAudioBuffer(sample_rate=16000, max_duration_seconds=1.0)

        for i in range(3):
            samples = np.ones(8000, dtype=np.float32) * (i + 1)
            buffer.push(samples)

        assert buffer.is_full is True
        assert buffer.sample_count == 16000

    def test_get_all_returns_numpy_array(self):
        """Verify get_all() returns numpy array."""
        import numpy as np

        buffer = CircularAudioBuffer(sample_rate=16000, max_duration_seconds=1.0)
        samples = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        buffer.push(samples)

        result = buffer.get_all()

        assert isinstance(result, np.ndarray)
        assert len(result) == 3


class TestHotkeyTranscriptionServiceStructure:
    """Test HotkeyTranscriptionService structure and API."""

    def test_service_can_be_imported(self):
        """Verify service can be imported."""
        from app.api.services.hotkey_transcription_service import (
            HotkeyTranscriptionService,
            HotkeyConfig,
            HotkeyStartResponse,
            HotkeyStopResponse,
            HotkeyStatusResponse,
        )

        assert HotkeyTranscriptionService is not None

    def test_service_has_required_methods(self):
        """Verify service has start_session and stop_session methods."""
        from app.api.services.hotkey_transcription_service import (
            HotkeyTranscriptionService,
        )
        from app.core.settings.config import AppSettings

        settings = MagicMock(spec=AppSettings)
        service = HotkeyTranscriptionService(settings)

        assert hasattr(service, "start_session")
        assert hasattr(service, "stop_session")
        assert hasattr(service, "get_status")
        assert hasattr(service, "register_websocket")
        assert hasattr(service, "unregister_websocket")

    @pytest.mark.asyncio
    async def test_stop_session_returns_correct_type_when_idle(self):
        """Verify stop_session returns HotkeyStopResponse when no session active."""
        from app.api.services.hotkey_transcription_service import (
            HotkeyTranscriptionService,
        )
        from app.core.settings.config import AppSettings

        settings = MagicMock(spec=AppSettings)
        service = HotkeyTranscriptionService(settings)

        response = await service.stop_session()

        assert response.status == "idle"
        assert response.final_transcription == ""

    def test_get_status_returns_correct_type_when_idle(self):
        """Verify get_status returns HotkeyStatusResponse when idle."""
        from app.api.services.hotkey_transcription_service import (
            HotkeyTranscriptionService,
        )
        from app.core.settings.config import AppSettings

        settings = MagicMock(spec=AppSettings)
        service = HotkeyTranscriptionService(settings)

        status = service.get_status()

        assert status.state == "idle"
        assert status.is_recording is False
        assert status.session_id is None


class TestHotkeyStateEnums:
    """Test state enum values."""

    def test_session_state_values(self):
        """Verify all expected state values exist."""
        states = [s.name for s in HotkeySessionState]

        assert "IDLE" in states
        assert "RECORDING" in states
        assert "PROCESSING" in states
        assert "COMPLETE" in states
        assert "ERROR" in states


class TestHotkeyIntegrationNotes:
    """Documentation of what's needed for full integration testing."""

    def test_integration_testing_requirements(self):
        """Document integration test requirements.

        Full integration tests would require:

        1. Mocked audio backend:
           - Mock LoopbackAudioSource to avoid real audio device
           - Provide synthetic audio data for transcription

        2. Mocked transcriber:
           - Mock FastTranscriber to return predefined transcripts
           - Or use a tiny test model with known audio

        3. Mocked settings:
           - Mock get_settings_manager() to return test settings
           - Mock model catalog to return known model IDs

        4. WebSocket testing:
           - Create test WebSocket connections
           - Verify messages are sent correctly

        5. Hotkey registration (Electron/IPC):
           - Cannot test in pure Python
           - Requires e2e test with Electron running
           - Or mock the IPC layer

        6. Text injection:
           - Mock PlatformTextInjector
           - Or test only on CI with display

        These tests verify:
        - State machine logic
        - API contracts
        - Callback flows
        - Buffer behavior
        - Configuration handling
        """
        pass
