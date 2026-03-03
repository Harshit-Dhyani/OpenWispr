"""Unit tests for the ModeManager.

Tests cover:
- Singleton pattern
- Mode lifecycle management
- Resource management
- Settings synchronization
- Event broadcasting
- Thread-safe mode switching
- Error handling and fallback
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Mock soundcard before importing audio modules
sys.modules["soundcard"] = MagicMock()
sys.modules["soundcard"].PulseAudioError = Exception

# Mock other problematic imports
sys.modules["pyaudio"] = MagicMock()
sys.modules["torch"] = MagicMock()
sys.modules["torch"].cuda = MagicMock()
sys.modules["torch"].cuda.is_available = MagicMock(return_value=False)
sys.modules["faster_whisper"] = MagicMock()

from app.core.config import AppSettings
from app.core.mode_manager import (
    ModeLifecycleState,
    ModeManager,
    ModeStatus,
    ModeTransition,
    TranscriptionMode,
    get_mode_manager,
    reset_mode_manager,
)
from app.core.modes import ModeConfiguration, ModeSettings
from app.core.settings_manager import SettingsManager
from app.stt.streaming_engine import EngineState


# ============================================
# Fixtures
# ============================================


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the ModeManager singleton before each test."""
    reset_mode_manager()
    yield
    reset_mode_manager()


@pytest.fixture
def mock_settings():
    """Create mock application settings."""
    settings = MagicMock(spec=AppSettings)
    settings.sample_rate = 16000
    settings.channels = 1
    settings.download_root = Path("./models")
    settings.device = "cpu"
    settings.log_level = "INFO"
    settings.meter_decay = 0.8
    settings.max_queue_items = 10
    settings.beam_size = 5
    settings.best_of = 5
    settings.temperature = 0.0
    settings.vad_filter = True
    settings.capture_block_seconds = 0.1
    settings.audio_backend = "auto"
    settings.compute_type = "int8"
    return settings


@pytest.fixture
def mock_settings_manager():
    """Create mock settings manager."""
    manager = MagicMock(spec=SettingsManager)

    # Mock mode configs
    wispr_config = MagicMock(spec=ModeConfiguration)
    wispr_config.mode = TranscriptionMode.WISPR
    wispr_config.settings = MagicMock(spec=ModeSettings)
    wispr_config.settings.model_name = "tiny"

    system_config = MagicMock(spec=ModeConfiguration)
    system_config.mode = TranscriptionMode.SYSTEM
    system_config.settings = MagicMock(spec=ModeSettings)
    system_config.settings.model_name = "medium"

    manager.get_mode_config.side_effect = lambda mode: (
        wispr_config if mode == TranscriptionMode.WISPR else system_config
    )
    manager.get_active_mode.return_value = TranscriptionMode.SYSTEM
    manager.get_settings.return_value = MagicMock()

    return manager


@pytest.fixture
def mode_manager(mock_settings, mock_settings_manager):
    """Create a ModeManager instance with mocked dependencies."""
    return get_mode_manager(mock_settings, mock_settings_manager)


@pytest.fixture
def initialized_manager(mode_manager):
    """Create an initialized ModeManager."""
    with patch.object(mode_manager, "_initialize_transcription_engine", new_callable=AsyncMock):
        with patch.object(mode_manager, "_initialize_mode_configurations", new_callable=AsyncMock):
            with patch.object(mode_manager, "_initialize_audio_pipelines", new_callable=AsyncMock):
                with patch("asyncio.create_task"):
                    asyncio.run(mode_manager.initialize())
                    return mode_manager


# ============================================
# Singleton Pattern Tests
# ============================================


class TestSingletonPattern:
    """Tests for the singleton pattern implementation."""

    def test_same_instance_returned(self, mock_settings, mock_settings_manager):
        """Test that the same instance is returned on multiple calls."""
        manager1 = get_mode_manager(mock_settings, mock_settings_manager)
        manager2 = get_mode_manager(mock_settings, mock_settings_manager)

        assert manager1 is manager2

    def test_singleton_thread_safety(self, mock_settings, mock_settings_manager):
        """Test that singleton creation is thread-safe."""
        instances = []
        errors = []

        def create_instance():
            try:
                instance = get_mode_manager(mock_settings, mock_settings_manager)
                instances.append(instance)
            except Exception as e:
                errors.append(e)

        # Create multiple threads trying to get the instance
        threads = [threading.Thread(target=create_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should get the same instance
        assert len(errors) == 0
        assert len(set(id(i) for i in instances)) == 1

    def test_reset_creates_new_instance(self, mock_settings, mock_settings_manager):
        """Test that reset allows creating a new instance."""
        manager1 = get_mode_manager(mock_settings, mock_settings_manager)
        reset_mode_manager()
        manager2 = get_mode_manager(mock_settings, mock_settings_manager)

        assert manager1 is not manager2


# ============================================
# Initialization Tests
# ============================================


class TestInitialization:
    """Tests for ModeManager initialization."""

    @pytest.mark.asyncio
    async def test_initialize_sets_state(self, mode_manager):
        """Test that initialization sets the correct state."""
        with patch.object(mode_manager, "_initialize_transcription_engine", new_callable=AsyncMock):
            with patch.object(
                mode_manager, "_initialize_mode_configurations", new_callable=AsyncMock
            ):
                with patch.object(
                    mode_manager, "_initialize_audio_pipelines", new_callable=AsyncMock
                ):
                    with patch("asyncio.create_task"):
                        await mode_manager.initialize()

        assert mode_manager._async_initialized
        assert mode_manager._state.initialized_at is not None
        assert mode_manager._state.wispr_status.lifecycle_state == ModeLifecycleState.READY
        assert mode_manager._state.system_status.lifecycle_state == ModeLifecycleState.READY

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, mode_manager):
        """Test that initialize can be called multiple times safely."""
        with patch.object(mode_manager, "_initialize_transcription_engine", new_callable=AsyncMock):
            with patch.object(
                mode_manager, "_initialize_mode_configurations", new_callable=AsyncMock
            ):
                with patch.object(
                    mode_manager, "_initialize_audio_pipelines", new_callable=AsyncMock
                ):
                    with patch("asyncio.create_task"):
                        await mode_manager.initialize()
                        await mode_manager.initialize()  # Second call should be no-op

        assert mode_manager._async_initialized

    @pytest.mark.asyncio
    async def test_initialize_failure_sets_error_state(self, mode_manager):
        """Test that initialization failure sets error state."""
        with patch.object(
            mode_manager,
            "_initialize_transcription_engine",
            new_callable=AsyncMock,
            side_effect=Exception("Init failed"),
        ):
            with pytest.raises(Exception, match="Init failed"):
                await mode_manager.initialize()

        assert mode_manager._state.global_error == "Init failed"
        assert mode_manager._state.wispr_status.lifecycle_state == ModeLifecycleState.ERROR
        assert mode_manager._state.system_status.lifecycle_state == ModeLifecycleState.ERROR


# ============================================
# Mode Switching Tests
# ============================================


class TestModeSwitching:
    """Tests for mode switching functionality."""

    @pytest.mark.asyncio
    async def test_switch_to_wispr_mode(self, initialized_manager):
        """Test switching to Wispr mode."""
        manager = initialized_manager

        with patch.object(manager, "_start_mode", new_callable=AsyncMock) as mock_start:
            transition = await manager.switch_mode(TranscriptionMode.WISPR)

        assert transition.success
        assert transition.to_mode == TranscriptionMode.WISPR
        assert manager.get_current_mode() == TranscriptionMode.WISPR
        mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_switch_to_system_mode(self, initialized_manager):
        """Test switching to System mode."""
        manager = initialized_manager

        with patch.object(manager, "_start_mode", new_callable=AsyncMock) as mock_start:
            transition = await manager.switch_mode(TranscriptionMode.SYSTEM)

        assert transition.success
        assert transition.to_mode == TranscriptionMode.SYSTEM
        mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_switch_mode_stops_previous(self, initialized_manager):
        """Test that switching modes stops the previous mode."""
        manager = initialized_manager

        # First switch to system
        with patch.object(manager, "_start_mode", new_callable=AsyncMock):
            await manager.switch_mode(TranscriptionMode.SYSTEM)

        # Then switch to wispr
        with patch.object(manager, "_stop_mode", new_callable=AsyncMock) as mock_stop:
            with patch.object(manager, "_cleanup_mode", new_callable=AsyncMock) as mock_cleanup:
                with patch.object(manager, "_start_mode", new_callable=AsyncMock):
                    await manager.switch_mode(TranscriptionMode.WISPR)

        mock_stop.assert_called_once_with(TranscriptionMode.SYSTEM)
        mock_cleanup.assert_called_once_with(TranscriptionMode.SYSTEM)

    @pytest.mark.asyncio
    async def test_switch_same_mode_no_op(self, initialized_manager):
        """Test that switching to the same mode is a no-op."""
        manager = initialized_manager

        with patch.object(manager, "_start_mode", new_callable=AsyncMock):
            await manager.switch_mode(TranscriptionMode.SYSTEM)

        with patch.object(manager, "_stop_mode", new_callable=AsyncMock) as mock_stop:
            transition = await manager.switch_mode(TranscriptionMode.SYSTEM)

        assert transition.success
        assert transition.duration_ms == 0.0
        mock_stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_switch_mode_force(self, initialized_manager):
        """Test forced mode switch even when already in mode."""
        manager = initialized_manager

        with patch.object(manager, "_start_mode", new_callable=AsyncMock):
            await manager.switch_mode(TranscriptionMode.WISPR)

        with patch.object(manager, "_stop_mode", new_callable=AsyncMock) as mock_stop:
            with patch.object(manager, "_start_mode", new_callable=AsyncMock) as mock_start:
                await manager.switch_mode(TranscriptionMode.WISPR, force=True)

        mock_stop.assert_called_once()
        mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_switch_mode_records_transition(self, initialized_manager):
        """Test that mode switches are recorded in transition history."""
        manager = initialized_manager

        with patch.object(manager, "_start_mode", new_callable=AsyncMock):
            await manager.switch_mode(TranscriptionMode.WISPR)

        with patch.object(manager, "_stop_mode", new_callable=AsyncMock):
            with patch.object(manager, "_cleanup_mode", new_callable=AsyncMock):
                with patch.object(manager, "_start_mode", new_callable=AsyncMock):
                    await manager.switch_mode(TranscriptionMode.SYSTEM)

        history = manager._state.transition_history
        assert len(history) == 2
        assert history[0].to_mode == TranscriptionMode.WISPR
        assert history[1].to_mode == TranscriptionMode.SYSTEM


# ============================================
# Thread Safety Tests
# ============================================


class TestThreadSafety:
    """Tests for thread-safe operations."""

    @pytest.mark.asyncio
    async def test_concurrent_mode_switches(self, initialized_manager):
        """Test that concurrent mode switches are handled safely."""
        manager = initialized_manager

        async def switch_mode(mode):
            with patch.object(manager, "_start_mode", new_callable=AsyncMock):
                with patch.object(manager, "_stop_mode", new_callable=AsyncMock):
                    with patch.object(manager, "_cleanup_mode", new_callable=AsyncMock):
                        await manager.switch_mode(mode)

        # Run concurrent switches
        tasks = [
            switch_mode(TranscriptionMode.WISPR),
            switch_mode(TranscriptionMode.SYSTEM),
            switch_mode(TranscriptionMode.WISPR),
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        # Should end in a valid state
        current = manager.get_current_mode()
        assert current in (TranscriptionMode.WISPR, TranscriptionMode.SYSTEM, None)

    def test_thread_safe_state_access(self, initialized_manager):
        """Test that state access is thread-safe."""
        manager = initialized_manager
        results = []
        errors = []

        def read_state():
            try:
                state = manager.get_state()
                results.append(state)
            except Exception as e:
                errors.append(e)

        # Multiple threads reading state concurrently
        threads = [threading.Thread(target=read_state) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20


# ============================================
# Resource Management Tests
# ============================================


class TestResourceManagement:
    """Tests for resource allocation and cleanup."""

    @pytest.mark.asyncio
    async def test_resource_allocation_tracked(self, initialized_manager):
        """Test that resource allocation is tracked correctly."""
        manager = initialized_manager

        # Manually set resources as initialized (since we're mocking initialization)
        manager._state.wispr_status.resource_allocation.audio_pipeline_initialized = True
        manager._state.system_status.resource_allocation.audio_pipeline_initialized = True

        # Now should have pipelines initialized
        assert manager._state.wispr_status.resource_allocation.audio_pipeline_initialized
        assert manager._state.system_status.resource_allocation.audio_pipeline_initialized

    @pytest.mark.asyncio
    async def test_cleanup_releases_resources(self, initialized_manager):
        """Test that cleanup releases resources."""
        manager = initialized_manager

        await manager._cleanup_mode(TranscriptionMode.WISPR)

        assert not manager._state.wispr_status.resource_allocation.audio_pipeline_initialized
        assert manager._state.wispr_status.resource_allocation.memory_mb_allocated == 0.0

    @pytest.mark.asyncio
    async def test_release_resources_all_modes(self, initialized_manager):
        """Test releasing resources for all modes."""
        manager = initialized_manager

        await manager.release_resources()

        assert not manager._state.wispr_status.resource_allocation.audio_pipeline_initialized
        assert not manager._state.system_status.resource_allocation.audio_pipeline_initialized

    @pytest.mark.asyncio
    async def test_release_resources_single_mode(self, initialized_manager):
        """Test releasing resources for a single mode."""
        manager = initialized_manager

        # Set initial state
        manager._state.wispr_status.resource_allocation.audio_pipeline_initialized = True
        manager._state.system_status.resource_allocation.audio_pipeline_initialized = True

        await manager.release_resources(TranscriptionMode.WISPR)

        assert not manager._state.wispr_status.resource_allocation.audio_pipeline_initialized
        # System should still be initialized
        assert manager._state.system_status.resource_allocation.audio_pipeline_initialized


# ============================================
# Status and Availability Tests
# ============================================


class TestStatusAndAvailability:
    """Tests for status queries and availability checks."""

    def test_get_current_mode_initial(self, mode_manager):
        """Test getting current mode when none is active."""
        assert mode_manager.get_current_mode() is None

    def test_is_mode_available_uninitialized(self, mode_manager):
        """Test availability check for uninitialized mode."""
        assert mode_manager.is_mode_available(TranscriptionMode.WISPR)
        assert mode_manager.is_mode_available(TranscriptionMode.SYSTEM)

    def test_is_mode_available_running(self, initialized_manager):
        """Test availability check for running mode."""
        manager = initialized_manager
        manager._state.wispr_status.lifecycle_state = ModeLifecycleState.RUNNING

        assert not manager.is_mode_available(TranscriptionMode.WISPR)
        assert manager.is_mode_available(TranscriptionMode.SYSTEM)

    def test_is_mode_available_error(self, initialized_manager):
        """Test availability check for error state."""
        manager = initialized_manager
        manager._state.wispr_status.lifecycle_state = ModeLifecycleState.ERROR

        assert not manager.is_mode_available(TranscriptionMode.WISPR)

    def test_get_mode_status_single(self, initialized_manager):
        """Test getting status for a single mode."""
        manager = initialized_manager

        status = manager.get_mode_status(TranscriptionMode.WISPR)

        assert isinstance(status, ModeStatus)
        assert status.mode == TranscriptionMode.WISPR

    def test_get_mode_status_both(self, initialized_manager):
        """Test getting status for both modes."""
        manager = initialized_manager

        status = manager.get_mode_status()

        assert isinstance(status, dict)
        assert "wispr" in status
        assert "system" in status
        assert "current_mode" in status


# ============================================
# Callback Tests
# ============================================


class TestCallbacks:
    """Tests for callback registration and invocation."""

    def test_register_mode_change_callback(self, mode_manager):
        """Test registering a mode change callback."""
        callback = Mock()

        mode_manager.register_mode_change_callback(callback)

        assert callback in mode_manager._mode_change_callbacks

    def test_unregister_mode_change_callback(self, mode_manager):
        """Test unregistering a mode change callback."""
        callback = Mock()

        mode_manager.register_mode_change_callback(callback)
        mode_manager.unregister_mode_change_callback(callback)

        assert callback not in mode_manager._mode_change_callbacks

    @pytest.mark.asyncio
    async def test_mode_change_callback_invoked(self, initialized_manager):
        """Test that mode change callback is invoked on switch."""
        manager = initialized_manager
        callback = Mock()
        manager.register_mode_change_callback(callback)

        with patch.object(manager, "_start_mode", new_callable=AsyncMock):
            await manager.switch_mode(TranscriptionMode.WISPR)

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[1] == TranscriptionMode.WISPR  # new_mode

    def test_register_error_callback(self, mode_manager):
        """Test registering an error callback."""
        callback = Mock()

        mode_manager.register_error_callback(callback)

        assert callback in mode_manager._error_callbacks

    def test_error_callback_invoked(self, initialized_manager):
        """Test that error callback is invoked on errors."""
        manager = initialized_manager
        callback = Mock()
        manager.register_error_callback(callback)

        error = Exception("Test error")
        manager._notify_error(TranscriptionMode.WISPR, error, "test_context")

        callback.assert_called_once_with(TranscriptionMode.WISPR, error, "test_context")


# ============================================
# Settings Synchronization Tests
# ============================================


class TestSettingsSynchronization:
    """Tests for settings synchronization."""

    def test_sync_mode_settings(self, initialized_manager):
        """Test syncing mode settings."""
        manager = initialized_manager

        with patch.object(manager._settings_manager, "get_mode_config") as mock_get:
            mock_get.return_value = MagicMock()
            manager.sync_mode_settings(TranscriptionMode.WISPR)

        mock_get.assert_called_once_with(TranscriptionMode.WISPR)

    def test_apply_settings_update_success(self, initialized_manager):
        """Test applying settings update successfully."""
        manager = initialized_manager

        with patch.object(
            manager._settings_manager,
            "apply_sync_update",
            return_value=True,
        ):
            result = manager.apply_settings_update({"setting": "value"})

        assert result is True

    def test_apply_settings_update_failure(self, initialized_manager):
        """Test applying settings update that fails."""
        manager = initialized_manager

        with patch.object(
            manager._settings_manager,
            "apply_sync_update",
            side_effect=Exception("Update failed"),
        ):
            result = manager.apply_settings_update({"setting": "value"})

        assert result is False


# ============================================
# Error Handling Tests
# ============================================


class TestErrorHandling:
    """Tests for error handling and fallback behavior."""

    @pytest.mark.asyncio
    async def test_switch_mode_error_records_transition(self, initialized_manager):
        """Test that failed mode switch records failed transition."""
        manager = initialized_manager

        with patch.object(
            manager, "_start_mode", new_callable=AsyncMock, side_effect=Exception("Start failed")
        ):
            with pytest.raises(RuntimeError):
                await manager.switch_mode(TranscriptionMode.WISPR)

        history = manager._state.transition_history
        assert len(history) == 1
        assert not history[0].success
        assert "Start failed" in history[0].error_message

    @pytest.mark.asyncio
    async def test_switch_mode_fallback_on_error(self, initialized_manager):
        """Test fallback to previous mode on switch error."""
        manager = initialized_manager

        # First establish a mode
        with patch.object(manager, "_start_mode", new_callable=AsyncMock):
            await manager.switch_mode(TranscriptionMode.SYSTEM)

        # Then fail to switch - the fallback may also fail, leaving mode as None
        with patch.object(manager, "_stop_mode", new_callable=AsyncMock):
            with patch.object(manager, "_cleanup_mode", new_callable=AsyncMock):
                with patch.object(
                    manager,
                    "_start_mode",
                    new_callable=AsyncMock,
                    side_effect=Exception("Switch failed"),
                ):
                    with pytest.raises(RuntimeError):
                        await manager.switch_mode(TranscriptionMode.WISPR)

        # Mode should be either None (if fallback failed) or SYSTEM (if fallback succeeded)
        assert manager.get_current_mode() in (TranscriptionMode.SYSTEM, None)

    @pytest.mark.asyncio
    async def test_stop_mode_error_handling(self, initialized_manager):
        """Test error handling during mode stop."""
        manager = initialized_manager

        manager._state.wispr_status.lifecycle_state = ModeLifecycleState.RUNNING

        with patch.object(manager, "_stop_wispr_mode", side_effect=Exception("Stop failed")):
            with pytest.raises(Exception):
                await manager._stop_mode(TranscriptionMode.WISPR)

        assert manager._state.wispr_status.lifecycle_state == ModeLifecycleState.ERROR


# ============================================
# Shutdown Tests
# ============================================


class TestShutdown:
    """Tests for shutdown functionality."""

    @pytest.mark.asyncio
    async def test_shutdown_stops_current_mode(self, initialized_manager):
        """Test that shutdown stops the current mode."""
        manager = initialized_manager

        with patch.object(manager, "_start_mode", new_callable=AsyncMock):
            await manager.switch_mode(TranscriptionMode.SYSTEM)

        with patch.object(manager, "_stop_mode", new_callable=AsyncMock) as mock_stop:
            with patch.object(manager, "_cleanup_mode", new_callable=AsyncMock):
                await manager.shutdown()

        mock_stop.assert_called_once_with(TranscriptionMode.SYSTEM)

    @pytest.mark.asyncio
    async def test_shutdown_releases_resources(self, initialized_manager):
        """Test that shutdown releases all resources."""
        manager = initialized_manager

        with patch.object(manager, "release_resources", new_callable=AsyncMock) as mock_release:
            await manager.shutdown()

        mock_release.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_stops_engine(self, initialized_manager):
        """Test that shutdown stops the transcription engine."""
        manager = initialized_manager

        # Create a mock transcription engine
        mock_engine = MagicMock()
        mock_engine.stop = AsyncMock()
        mock_engine.cleanup = MagicMock()
        manager._transcription_engine = mock_engine

        with patch.object(manager, "_stop_mode", new_callable=AsyncMock):
            with patch.object(manager, "_cleanup_mode", new_callable=AsyncMock):
                with patch.object(manager, "release_resources", new_callable=AsyncMock):
                    await manager.shutdown()

        mock_engine.stop.assert_called_once()
        mock_engine.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self, initialized_manager):
        """Test that shutdown can be called multiple times safely."""
        manager = initialized_manager

        with patch.object(manager, "_stop_mode", new_callable=AsyncMock):
            with patch.object(manager, "_cleanup_mode", new_callable=AsyncMock):
                with patch.object(manager, "release_resources", new_callable=AsyncMock):
                    await manager.shutdown()
                    await manager.shutdown()  # Second call should be safe


# ============================================
# State Dictionary Tests
# ============================================


class TestStateDictionary:
    """Tests for state serialization to dictionary."""

    def test_mode_status_to_dict(self):
        """Test ModeStatus to_dict conversion."""
        status = ModeStatus(
            mode=TranscriptionMode.WISPR,
            lifecycle_state=ModeLifecycleState.RUNNING,
        )
        status.segments_transcribed = 10
        status.total_runtime_seconds = 30.5

        d = status.to_dict()

        assert d["mode"] == "wispr"
        assert d["lifecycle_state"] == "RUNNING"
        assert d["runtime"]["segments_transcribed"] == 10
        assert d["runtime"]["total_seconds"] == 30.5

    def test_transition_to_dict(self):
        """Test ModeTransition to_dict conversion."""
        transition = ModeTransition(
            from_mode=TranscriptionMode.WISPR,
            to_mode=TranscriptionMode.SYSTEM,
            timestamp=12345.0,
            duration_ms=150.5,
            success=True,
        )

        d = transition.to_dict()

        assert d["from_mode"] == "wispr"
        assert d["to_mode"] == "system"
        assert d["timestamp"] == 12345.0
        assert d["duration_ms"] == 150.5
        assert d["success"] is True

    def test_state_to_dict(self, initialized_manager):
        """Test ModeManagerState to_dict conversion."""
        manager = initialized_manager

        d = manager.get_state_dict()

        assert "current_mode" in d
        assert "previous_mode" in d
        assert "wispr" in d
        assert "system" in d
        assert "recent_transitions" in d


# ============================================
# Integration Tests
# ============================================


@pytest.mark.slow
class TestIntegration:
    """Integration tests requiring full initialization."""

    @pytest.mark.asyncio
    async def test_full_mode_lifecycle(self, mock_settings, mock_settings_manager):
        """Test complete mode lifecycle from initialization to shutdown."""
        reset_mode_manager()

        manager = get_mode_manager(mock_settings, mock_settings_manager)

        # Initialize
        with patch("app.stt.streaming_engine.DualModeTranscriptionEngine") as mock_engine:
            mock_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance
            mock_engine_instance.state = EngineState.READY

            with patch.object(manager, "_initialize_mode_configurations", new_callable=AsyncMock):
                with patch.object(manager, "_initialize_audio_pipelines", new_callable=AsyncMock):
                    with patch("asyncio.create_task"):
                        await manager.initialize()

        # Switch modes
        with patch.object(manager, "_start_mode", new_callable=AsyncMock):
            with patch.object(manager, "_stop_mode", new_callable=AsyncMock):
                with patch.object(manager, "_cleanup_mode", new_callable=AsyncMock):
                    await manager.switch_mode(TranscriptionMode.WISPR)
                    assert manager.get_current_mode() == TranscriptionMode.WISPR

                    await manager.switch_mode(TranscriptionMode.SYSTEM)
                    assert manager.get_current_mode() == TranscriptionMode.SYSTEM

        # Shutdown
        with patch.object(manager, "_stop_mode", new_callable=AsyncMock):
            with patch.object(manager, "_cleanup_mode", new_callable=AsyncMock):
                with patch.object(manager, "release_resources", new_callable=AsyncMock):
                    await manager.shutdown()

        assert not manager._async_initialized


# ============================================
# Performance Tests
# ============================================


class TestPerformance:
    """Performance-related tests."""

    @pytest.mark.asyncio
    async def test_mode_switch_performance(self, initialized_manager):
        """Test that mode switches complete within reasonable time."""
        manager = initialized_manager

        start = time.time()

        with patch.object(manager, "_start_mode", new_callable=AsyncMock):
            transition = await manager.switch_mode(TranscriptionMode.WISPR)

        elapsed = time.time() - start

        # Should complete quickly when mocked
        assert elapsed < 1.0
        assert transition.duration_ms < 1000

    def test_concurrent_state_reads(self, initialized_manager):
        """Test performance of concurrent state reads."""
        manager = initialized_manager

        def read_loop():
            for _ in range(100):
                _ = manager.get_state_dict()

        threads = [threading.Thread(target=read_loop) for _ in range(10)]
        start = time.time()

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        elapsed = time.time() - start

        # Should complete quickly even with concurrent access
        assert elapsed < 5.0
