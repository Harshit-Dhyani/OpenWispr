"""Central Mode Manager for orchestrating between Hotkey and System modes.

This module provides a singleton-based central orchestrator that manages
mode switching, resource allocation, settings synchronization, and event
broadcasting between Hotkey and System transcription modes.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Protocol

from app.audio.system_pipeline import SystemPipeline, SystemPipelineConfig
from app.audio.wispr_pipeline import WisprPipeline, WisprPipelineConfig
from app.core.settings.config import AppSettings
from app.core.logging_utils import configure_logging
from app.core.modes import (
    ModeConfiguration,
    ModeSettings,
    SystemModeDefaults,
    TranscriptionMode,
    WisprModeDefaults,
    get_mode_configuration,
    get_mode_defaults,
)
from app.core.models import SessionHealth, SessionState, TranscriptSegment
from app.core.session_manager import SessionManager
from app.core.settings.manager import SettingsManager, get_settings_manager
from app.stt.streaming_engine import (
    DualModeTranscriptionEngine,
    EngineState,
    TranscriptionMode as EngineMode,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ModeManager",
    "ModeManagerState",
    "ModeTransition",
    "ModeStatus",
    "ModeLifecycleState",
    "get_mode_manager",
]


class ModeLifecycleState(Enum):
    """Lifecycle states for a transcription mode."""

    UNINITIALIZED = auto()
    INITIALIZING = auto()
    READY = auto()
    STARTING = auto()
    RUNNING = auto()
    PAUSING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()
    CLEANING_UP = auto()
    ERROR = auto()


@dataclass
class ModeResourceAllocation:
    """Resource allocation information for a mode."""

    audio_pipeline_initialized: bool = False
    transcription_engine_ready: bool = False
    model_loaded: bool = False
    memory_mb_allocated: float = 0.0
    gpu_memory_mb: float = 0.0
    cpu_threads: int = 0


@dataclass
class ModeStatus:
    """Detailed status for a specific transcription mode."""

    mode: TranscriptionMode
    lifecycle_state: ModeLifecycleState
    resource_allocation: ModeResourceAllocation = field(default_factory=ModeResourceAllocation)
    error_message: str | None = None
    error_timestamp: float | None = None
    start_time: float | None = None
    total_runtime_seconds: float = 0.0
    segments_transcribed: int = 0
    audio_frames_processed: int = 0
    last_activity_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert status to dictionary for API responses."""
        return {
            "mode": self.mode.value,
            "lifecycle_state": self.lifecycle_state.name,
            "resources": {
                "audio_pipeline_initialized": self.resource_allocation.audio_pipeline_initialized,
                "transcription_engine_ready": self.resource_allocation.transcription_engine_ready,
                "model_loaded": self.resource_allocation.model_loaded,
                "memory_mb_allocated": round(self.resource_allocation.memory_mb_allocated, 2),
                "gpu_memory_mb": round(self.resource_allocation.gpu_memory_mb, 2),
                "cpu_threads": self.resource_allocation.cpu_threads,
            },
            "error": {
                "message": self.error_message,
                "timestamp": self.error_timestamp,
            }
            if self.error_message
            else None,
            "runtime": {
                "start_time": self.start_time,
                "total_seconds": round(self.total_runtime_seconds, 2),
                "segments_transcribed": self.segments_transcribed,
                "audio_frames_processed": self.audio_frames_processed,
                "last_activity_at": self.last_activity_at,
            },
        }


@dataclass
class ModeTransition:
    """Represents a mode transition event."""

    from_mode: TranscriptionMode | None
    to_mode: TranscriptionMode
    timestamp: float
    duration_ms: float
    success: bool
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_mode": self.from_mode.value if self.from_mode else None,
            "to_mode": self.to_mode.value,
            "timestamp": self.timestamp,
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "error": self.error_message,
        }


@dataclass
class ModeManagerState:
    """Complete state of the ModeManager."""

    current_mode: TranscriptionMode | None = None
    previous_mode: TranscriptionMode | None = None
    transition_history: list[ModeTransition] = field(default_factory=list)
    wispr_status: ModeStatus = field(
        default_factory=lambda: ModeStatus(
            mode=TranscriptionMode.WISPR,
            lifecycle_state=ModeLifecycleState.UNINITIALIZED,
        )
    )
    system_status: ModeStatus = field(
        default_factory=lambda: ModeStatus(
            mode=TranscriptionMode.SYSTEM,
            lifecycle_state=ModeLifecycleState.UNINITIALIZED,
        )
    )
    global_error: str | None = None
    initialized_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_mode": self.current_mode.value if self.current_mode else None,
            "previous_mode": self.previous_mode.value if self.previous_mode else None,
            "wispr": self.wispr_status.to_dict(),
            "system": self.system_status.to_dict(),
            "global_error": self.global_error,
            "initialized_at": self.initialized_at,
            "recent_transitions": [t.to_dict() for t in self.transition_history[-5:]],
        }


class ModeChangeCallback(Protocol):
    """Protocol for mode change callbacks."""

    def __call__(
        self,
        old_mode: TranscriptionMode | None,
        new_mode: TranscriptionMode,
        status: ModeManagerState,
    ) -> None: ...


class StatusUpdateCallback(Protocol):
    """Protocol for status update callbacks."""

    def __call__(self, mode: TranscriptionMode, status: ModeStatus) -> None: ...


class ErrorCallback(Protocol):
    """Protocol for error callbacks."""

    def __call__(self, mode: TranscriptionMode | None, error: Exception, context: str) -> None: ...


class ModeManager:
    """Central orchestrator for transcription mode management.

    This class implements the singleton pattern to provide a single point
    of control for switching between Hotkey and System modes.

    Features:
    - Thread-safe mode switching with graceful transitions
    - Resource allocation and cleanup per mode
    - Settings synchronization between modes
    - Event broadcasting to UI components
    - Comprehensive error handling with fallback
    """

    _instance: ModeManager | None = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> ModeManager:
        """Ensure singleton pattern."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        settings: AppSettings | None = None,
        settings_manager: SettingsManager | None = None,
    ) -> None:
        """Initialize the mode manager.

        Args:
            settings: Application settings instance
            settings_manager: Settings manager for mode-specific settings
        """
        if self._initialized:
            return

        self._settings = settings or AppSettings()
        self._settings_manager = settings_manager or get_settings_manager()

        # State management
        self._state = ModeManagerState()
        self._state_lock = threading.RLock()
        self._transition_lock = asyncio.Lock()

        # Mode handlers (lazy initialization)
        self._wispr_session: Any | None = None
        self._system_session_manager: SessionManager | None = None
        self._transcription_engine: DualModeTranscriptionEngine | None = None

        # Audio pipelines
        self._wispr_pipeline: WisprPipeline | None = None
        self._system_pipeline: SystemPipeline | None = None

        # Event loop for async operations
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._async_initialized = False

        # Callbacks
        self._mode_change_callbacks: list[ModeChangeCallback] = []
        self._status_update_callbacks: list[StatusUpdateCallback] = []
        self._error_callbacks: list[ErrorCallback] = []

        # Background tasks
        self._monitoring_task: asyncio.Task | None = None
        self._stop_monitoring = asyncio.Event()

        self._initialized = True
        logger.info("ModeManager instance created")

    async def initialize(self) -> None:
        """Initialize the mode manager and prepare both modes."""
        if self._async_initialized:
            logger.debug("ModeManager already initialized")
            return

        self._event_loop = asyncio.get_running_loop()

        try:
            with self._state_lock:
                self._state.initialized_at = time.time()
                self._state.wispr_status.lifecycle_state = ModeLifecycleState.INITIALIZING
                self._state.system_status.lifecycle_state = ModeLifecycleState.INITIALIZING

            # Initialize transcription engine
            await self._initialize_transcription_engine()

            # Initialize mode configurations
            await self._initialize_mode_configurations()

            # Initialize audio pipelines (but don't start them yet)
            await self._initialize_audio_pipelines()

            with self._state_lock:
                self._state.wispr_status.lifecycle_state = ModeLifecycleState.READY
                self._state.system_status.lifecycle_state = ModeLifecycleState.READY

            self._async_initialized = True

            # Start background monitoring
            self._stop_monitoring.clear()
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())

            logger.info("ModeManager initialized successfully")

        except Exception as e:
            logger.exception("ModeManager initialization failed")
            self._notify_error(None, e, "initialization")
            with self._state_lock:
                self._state.global_error = str(e)
                self._state.wispr_status.lifecycle_state = ModeLifecycleState.ERROR
                self._state.system_status.lifecycle_state = ModeLifecycleState.ERROR
            raise

    async def _initialize_transcription_engine(self) -> None:
        """Initialize the dual-mode transcription engine."""
        logger.debug("Initializing transcription engine")

        try:
            self._transcription_engine = DualModeTranscriptionEngine(
                wispr_model="tiny",
                system_model="medium",
                download_root=str(self._settings.download_root),
                device=self._settings.device,
                warmup_on_init=True,
            )

            # Register callbacks
            self._transcription_engine.add_segment_callback(self._on_transcription_segment)
            self._transcription_engine.add_error_callback(self._on_transcription_error)

            logger.info("Transcription engine initialized")

        except Exception as e:
            logger.error(f"Failed to initialize transcription engine: {e}")
            raise

    async def _initialize_mode_configurations(self) -> None:
        """Initialize mode configurations from settings."""
        logger.debug("Initializing mode configurations")

        # Get mode configurations from settings manager
        wispr_config = self._settings_manager.get_mode_config(TranscriptionMode.WISPR)
        system_config = self._settings_manager.get_mode_config(TranscriptionMode.SYSTEM)

        # Initialize system session manager
        self._system_session_manager = SessionManager(self._settings)
        self._system_session_manager.set_callbacks(
            on_segment=self._on_system_segment,
            on_partial=self._on_system_partial,
            on_health=self._on_system_health,
            on_state=self._on_system_state,
        )

        logger.info("Mode configurations initialized")

    async def _initialize_audio_pipelines(self) -> None:
        """Initialize audio pipelines for both modes."""
        logger.debug("Initializing audio pipelines")

        try:
            # Initialize hotkey pipeline config
            wispr_pipeline_config = WisprPipelineConfig(
                sample_rate=self._settings.sample_rate,
                channels=1,
                device_id=self._settings_manager.get_settings().audio.defaultDeviceId,
            )
            self._wispr_pipeline = WisprPipeline(wispr_pipeline_config)

            # Initialize System pipeline config
            system_pipeline_config = SystemPipelineConfig(
                sample_rate=self._settings.sample_rate,
                channels=self._settings.channels,
                device_id=self._settings_manager.get_settings().audio.defaultDeviceId,
            )
            self._system_pipeline = SystemPipeline(system_pipeline_config)

            with self._state_lock:
                self._state.wispr_status.resource_allocation.audio_pipeline_initialized = True
                self._state.system_status.resource_allocation.audio_pipeline_initialized = True

            logger.info("Audio pipelines initialized")

        except Exception as e:
            logger.error(f"Failed to initialize audio pipelines: {e}")
            raise

    async def switch_mode(
        self,
        mode: TranscriptionMode,
        *,
        force: bool = False,
        context: dict[str, Any] | None = None,
    ) -> ModeTransition:
        """Switch to the specified transcription mode.

        This method performs a graceful transition:
        1. Stops the current mode (if any)
        2. Cleans up resources from the previous mode
        3. Initializes and starts the new mode
        4. Broadcasts the mode change event

        Args:
            mode: The mode to switch to
            force: Force switch even if current mode is running
            context: Additional context for the mode switch

        Returns:
            ModeTransition record of the switch operation

        Raises:
            RuntimeError: If mode switch fails and cannot recover
        """
        if not self._async_initialized:
            raise RuntimeError("ModeManager not initialized. Call initialize() first.")

        transition_start = time.time()

        async with self._transition_lock:
            current_mode = self.get_current_mode()

            # Check if already in requested mode
            if current_mode == mode and not force:
                logger.debug(f"Already in {mode.value} mode, no switch needed")
                return ModeTransition(
                    from_mode=current_mode,
                    to_mode=mode,
                    timestamp=transition_start,
                    duration_ms=0.0,
                    success=True,
                )

            logger.info(f"Switching mode from {current_mode} to {mode}")

            try:
                # Step 1: Stop current mode gracefully
                if current_mode is not None:
                    await self._stop_mode(current_mode)

                # Step 2: Cleanup resources from previous mode
                if current_mode is not None:
                    await self._cleanup_mode(current_mode)

                # Step 3: Start new mode
                await self._start_mode(mode, context)

                # Step 4: Update state
                with self._state_lock:
                    self._state.previous_mode = current_mode
                    self._state.current_mode = mode

                # Update settings
                self._settings_manager.set_active_mode(mode)

                # Sync mode settings to transcription engine
                if self._transcription_engine:
                    engine_mode = (
                        EngineMode.WISPR if mode == TranscriptionMode.WISPR else EngineMode.SYSTEM
                    )
                    self._transcription_engine.set_mode(engine_mode)

                # Create transition record
                duration_ms = (time.time() - transition_start) * 1000
                transition = ModeTransition(
                    from_mode=current_mode,
                    to_mode=mode,
                    timestamp=transition_start,
                    duration_ms=duration_ms,
                    success=True,
                )

                with self._state_lock:
                    self._state.transition_history.append(transition)

                # Notify callbacks
                self._notify_mode_change(current_mode, mode)

                logger.info(f"Mode switch completed in {duration_ms:.1f}ms")
                return transition

            except Exception as e:
                duration_ms = (time.time() - transition_start) * 1000
                logger.exception(f"Mode switch failed after {duration_ms:.1f}ms")

                # Update error state
                self._notify_error(current_mode, e, f"switch_to_{mode.value}")

                with self._state_lock:
                    self._state.global_error = str(e)

                # Attempt fallback to previous mode if available
                if current_mode is not None:
                    try:
                        logger.info(f"Attempting fallback to {current_mode}")
                        await self._start_mode(current_mode, context)
                        self._state.current_mode = current_mode
                    except Exception as fallback_error:
                        logger.error(f"Fallback also failed: {fallback_error}")
                        self._state.current_mode = None

                transition = ModeTransition(
                    from_mode=current_mode,
                    to_mode=mode,
                    timestamp=transition_start,
                    duration_ms=duration_ms,
                    success=False,
                    error_message=str(e),
                )

                with self._state_lock:
                    self._state.transition_history.append(transition)

                raise RuntimeError(f"Mode switch failed: {e}") from e

    async def _start_mode(
        self,
        mode: TranscriptionMode,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Start a specific mode."""
        logger.debug(f"Starting {mode.value} mode")

        status = self._get_mode_status(mode)
        status.lifecycle_state = ModeLifecycleState.STARTING
        status.start_time = time.time()
        status.error_message = None
        status.error_timestamp = None

        try:
            if mode == TranscriptionMode.WISPR:
                await self._start_wispr_mode(context)
            else:
                await self._start_system_mode(context)

            status.lifecycle_state = ModeLifecycleState.RUNNING
            status.last_activity_at = time.time()

            # Start transcription engine if not already running
            if self._transcription_engine and self._transcription_engine.state == EngineState.READY:
                await self._transcription_engine.start()
                status.resource_allocation.transcription_engine_ready = True

            logger.info(f"{mode.value} mode started successfully")

        except Exception as e:
            status.lifecycle_state = ModeLifecycleState.ERROR
            status.error_message = str(e)
            status.error_timestamp = time.time()
            raise

    async def _start_wispr_mode(self, context: dict[str, Any] | None) -> None:
        """Start hotkey mode."""
        # Get hotkey-specific settings
        mode_config = self._settings_manager.get_mode_config(TranscriptionMode.WISPR)
        settings = self._settings_manager.get_settings()

        # Apply mode settings to transcription engine
        if self._transcription_engine:
            self._transcription_engine.set_mode(EngineMode.WISPR)

        logger.debug("Hotkey mode configuration applied")

    async def _start_system_mode(self, context: dict[str, Any] | None) -> None:
        """Start System mode."""
        # Get System-specific settings
        mode_config = self._settings_manager.get_mode_config(TranscriptionMode.SYSTEM)

        # Apply mode settings to transcription engine
        if self._transcription_engine:
            self._transcription_engine.set_mode(EngineMode.SYSTEM)

        logger.debug("System mode configuration applied")

    async def _stop_mode(self, mode: TranscriptionMode) -> None:
        """Stop a specific mode gracefully."""
        logger.debug(f"Stopping {mode.value} mode")

        status = self._get_mode_status(mode)

        if status.lifecycle_state in (ModeLifecycleState.STOPPED, ModeLifecycleState.UNINITIALIZED):
            logger.debug(f"{mode.value} mode already stopped")
            return

        status.lifecycle_state = ModeLifecycleState.STOPPING

        try:
            if mode == TranscriptionMode.WISPR:
                await self._stop_wispr_mode()
            else:
                await self._stop_system_mode()

            # Update runtime statistics
            if status.start_time:
                runtime = time.time() - status.start_time
                status.total_runtime_seconds += runtime

            status.lifecycle_state = ModeLifecycleState.STOPPED
            logger.info(f"{mode.value} mode stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping {mode.value} mode: {e}")
            status.lifecycle_state = ModeLifecycleState.ERROR
            raise

    async def _stop_wispr_mode(self) -> None:
        """Stop hotkey mode."""
        # Stop hotkey-specific resources
        if self._wispr_pipeline and self._wispr_pipeline.is_running:
            await self._wispr_pipeline.stop()
        logger.debug("Hotkey mode stopped")

    async def _stop_system_mode(self) -> None:
        """Stop System mode."""
        # Stop System-specific resources
        if self._system_session_manager and self._system_session_manager.session:
            self._system_session_manager.stop_session()
        logger.debug("System mode stopped")

    async def _cleanup_mode(self, mode: TranscriptionMode) -> None:
        """Clean up resources for a specific mode."""
        logger.debug(f"Cleaning up {mode.value} mode resources")

        status = self._get_mode_status(mode)
        status.lifecycle_state = ModeLifecycleState.CLEANING_UP

        try:
            # Release mode-specific resources
            status.resource_allocation.audio_pipeline_initialized = False
            status.resource_allocation.transcription_engine_ready = False
            status.resource_allocation.model_loaded = False
            status.resource_allocation.memory_mb_allocated = 0.0

            status.lifecycle_state = ModeLifecycleState.READY
            logger.debug(f"{mode.value} mode cleanup completed")

        except Exception as e:
            logger.error(f"Error cleaning up {mode.value} mode: {e}")
            status.lifecycle_state = ModeLifecycleState.ERROR
            raise

    def get_current_mode(self) -> TranscriptionMode | None:
        """Get the currently active transcription mode."""
        with self._state_lock:
            return self._state.current_mode

    def get_mode_handler(self) -> Any:
        """Get the appropriate session handler for the current mode.

        Returns:
            Session handler for the active mode (HotkeySession or SessionManager)
        """
        current_mode = self.get_current_mode()

        if current_mode == TranscriptionMode.WISPR:
            return self._wispr_session
        elif current_mode == TranscriptionMode.SYSTEM:
            return self._system_session_manager
        else:
            return None

    def is_mode_available(self, mode: TranscriptionMode) -> bool:
        """Check if a mode can be started.

        Args:
            mode: The mode to check

        Returns:
            True if the mode is available to start
        """
        with self._state_lock:
            if mode == TranscriptionMode.WISPR:
                status = self._state.wispr_status
            else:
                status = self._state.system_status

        # Mode is available if it's not currently running and not in error state
        return status.lifecycle_state not in (
            ModeLifecycleState.RUNNING,
            ModeLifecycleState.STARTING,
            ModeLifecycleState.ERROR,
        )

    def get_mode_status(self, mode: TranscriptionMode | None = None) -> ModeStatus | dict[str, Any]:
        """Get detailed status of one or both modes.

        Args:
            mode: Specific mode to get status for, or None for both

        Returns:
            ModeStatus for specific mode, or dict with both statuses
        """
        with self._state_lock:
            if mode == TranscriptionMode.WISPR:
                return self._state.wispr_status
            elif mode == TranscriptionMode.SYSTEM:
                return self._state.system_status
            else:
                return {
                    "wispr": self._state.wispr_status.to_dict(),
                    "system": self._state.system_status.to_dict(),
                    "current_mode": self._state.current_mode.value
                    if self._state.current_mode
                    else None,
                }

    def _get_mode_status(self, mode: TranscriptionMode) -> ModeStatus:
        """Get the mutable ModeStatus for a specific mode."""
        with self._state_lock:
            if mode == TranscriptionMode.WISPR:
                return self._state.wispr_status
            else:
                return self._state.system_status

    def get_state(self) -> ModeManagerState:
        """Get the complete mode manager state."""
        with self._state_lock:
            return self._state

    def get_state_dict(self) -> dict[str, Any]:
        """Get the mode manager state as a dictionary."""
        with self._state_lock:
            return self._state.to_dict()

    # ============================================
    # Callback Registration
    # ============================================

    def register_mode_change_callback(self, callback: ModeChangeCallback) -> None:
        """Register a callback for mode changes.

        Args:
            callback: Function called when mode changes
        """
        self._mode_change_callbacks.append(callback)
        logger.debug(
            f"Registered mode change callback: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}"
        )

    def unregister_mode_change_callback(self, callback: ModeChangeCallback) -> None:
        """Unregister a mode change callback."""
        if callback in self._mode_change_callbacks:
            self._mode_change_callbacks.remove(callback)

    def register_status_update_callback(self, callback: StatusUpdateCallback) -> None:
        """Register a callback for status updates."""
        self._status_update_callbacks.append(callback)

    def unregister_status_update_callback(self, callback: StatusUpdateCallback) -> None:
        """Unregister a status update callback."""
        if callback in self._status_update_callbacks:
            self._status_update_callbacks.remove(callback)

    def register_error_callback(self, callback: ErrorCallback) -> None:
        """Register a callback for errors."""
        self._error_callbacks.append(callback)

    def unregister_error_callback(self, callback: ErrorCallback) -> None:
        """Unregister an error callback."""
        if callback in self._error_callbacks:
            self._error_callbacks.remove(callback)

    # ============================================
    # Event Handlers
    # ============================================

    def _notify_mode_change(
        self,
        old_mode: TranscriptionMode | None,
        new_mode: TranscriptionMode,
    ) -> None:
        """Notify all mode change callbacks."""
        state = self.get_state()
        for callback in self._mode_change_callbacks:
            try:
                callback(old_mode, new_mode, state)
            except Exception as e:
                logger.error(f"Mode change callback error: {e}")

    def _notify_status_update(self, mode: TranscriptionMode, status: ModeStatus) -> None:
        """Notify all status update callbacks."""
        for callback in self._status_update_callbacks:
            try:
                callback(mode, status)
            except Exception as e:
                logger.error(f"Status update callback error: {e}")

    def _notify_error(
        self,
        mode: TranscriptionMode | None,
        error: Exception,
        context: str,
    ) -> None:
        """Notify all error callbacks."""
        for callback in self._error_callbacks:
            try:
                callback(mode, error, context)
            except Exception as e:
                logger.error(f"Error callback error: {e}")

    # ============================================
    # Transcription Event Handlers
    # ============================================

    def _on_transcription_segment(self, segment: TranscriptSegment) -> None:
        """Handle transcription segment from engine."""
        current_mode = self.get_current_mode()
        if current_mode:
            status = self._get_mode_status(current_mode)
            status.segments_transcribed += 1
            status.last_activity_at = time.time()

    def _on_transcription_error(self, error: Exception) -> None:
        """Handle transcription error from engine."""
        current_mode = self.get_current_mode()
        self._notify_error(current_mode, error, "transcription_engine")

    def _on_system_segment(self, segment: TranscriptSegment) -> None:
        """Handle system mode transcription segment."""
        self._state.system_status.segments_transcribed += 1
        self._state.system_status.last_activity_at = time.time()

    def _on_system_partial(self, text: str, start: float, end: float) -> None:
        """Handle system mode partial transcription."""
        self._state.system_status.last_activity_at = time.time()

    def _on_system_health(self, health: SessionHealth, meter_value: float) -> None:
        """Handle system mode health update."""
        self._state.system_status.last_activity_at = time.time()

    def _on_system_state(self, state: SessionState) -> None:
        """Handle system mode state update."""
        self._state.system_status.last_activity_at = time.time()

    # ============================================
    # Settings Synchronization
    # ============================================

    def sync_mode_settings(self, mode: TranscriptionMode) -> None:
        """Synchronize settings for a specific mode.

        Args:
            mode: Mode to sync settings for
        """
        mode_config = self._settings_manager.get_mode_config(mode)

        # Apply settings to transcription engine
        if self._transcription_engine:
            engine_mode = EngineMode.WISPR if mode == TranscriptionMode.WISPR else EngineMode.SYSTEM
            # Settings are applied when mode is activated

        logger.debug(f"Settings synchronized for {mode.value} mode")

    def apply_settings_update(self, settings_update: dict[str, Any]) -> bool:
        """Apply settings update and sync to active mode.

        Args:
            settings_update: Dictionary of settings to update

        Returns:
            True if settings were applied successfully
        """
        try:
            # Update settings through manager
            result = self._settings_manager.apply_sync_update(settings_update)

            if result:
                # Sync to current mode if running
                current_mode = self.get_current_mode()
                if current_mode:
                    self.sync_mode_settings(current_mode)

            return result

        except Exception as e:
            logger.error(f"Failed to apply settings update: {e}")
            return False

    # ============================================
    # Resource Management
    # ============================================

    def get_resource_usage(self) -> dict[str, Any]:
        """Get current resource usage information."""
        with self._state_lock:
            return {
                "wispr": {
                    "memory_mb": self._state.wispr_status.resource_allocation.memory_mb_allocated,
                    "gpu_memory_mb": self._state.wispr_status.resource_allocation.gpu_memory_mb,
                    "cpu_threads": self._state.wispr_status.resource_allocation.cpu_threads,
                },
                "system": {
                    "memory_mb": self._state.system_status.resource_allocation.memory_mb_allocated,
                    "gpu_memory_mb": self._state.system_status.resource_allocation.gpu_memory_mb,
                    "cpu_threads": self._state.system_status.resource_allocation.cpu_threads,
                },
                "engine": self._transcription_engine.get_metrics().to_dict()
                if self._transcription_engine
                else None,
            }

    async def release_resources(self, mode: TranscriptionMode | None = None) -> None:
        """Release resources for a specific mode or all modes.

        Args:
            mode: Mode to release resources for, or None for all
        """
        if mode is None or mode == TranscriptionMode.WISPR:
            await self._cleanup_mode(TranscriptionMode.WISPR)

        if mode is None or mode == TranscriptionMode.SYSTEM:
            await self._cleanup_mode(TranscriptionMode.SYSTEM)

        logger.info(f"Resources released for {mode.value if mode else 'all modes'}")

    # ============================================
    # Background Monitoring
    # ============================================

    async def _monitoring_loop(self) -> None:
        """Background loop for monitoring mode health."""
        logger.debug("Starting mode monitoring loop")

        while not self._stop_monitoring.is_set():
            try:
                # Check each mode's health
                for mode in TranscriptionMode:
                    status = self._get_mode_status(mode)

                    # Detect stuck states
                    if status.lifecycle_state in (
                        ModeLifecycleState.STARTING,
                        ModeLifecycleState.STOPPING,
                        ModeLifecycleState.CLEANING_UP,
                    ):
                        # Check if stuck for too long (>30 seconds)
                        if status.last_activity_at and (time.time() - status.last_activity_at) > 30:
                            logger.warning(
                                f"{mode.value} mode appears stuck in {status.lifecycle_state.name}"
                            )
                            status.error_message = f"Stuck in {status.lifecycle_state.name} state"
                            status.lifecycle_state = ModeLifecycleState.ERROR

                # Wait before next check
                try:
                    await asyncio.wait_for(self._stop_monitoring.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5.0)

        logger.debug("Mode monitoring loop stopped")

    # ============================================
    # Cleanup
    # ============================================

    async def shutdown(self) -> None:
        """Shutdown the mode manager and cleanup all resources."""
        logger.info("Shutting down ModeManager")

        # Stop monitoring
        self._stop_monitoring.set()
        if self._monitoring_task and not self._monitoring_task.done():
            try:
                await asyncio.wait_for(self._monitoring_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._monitoring_task.cancel()

        # Stop current mode
        current_mode = self.get_current_mode()
        if current_mode:
            try:
                await self._stop_mode(current_mode)
                await self._cleanup_mode(current_mode)
            except Exception as e:
                logger.error(f"Error stopping current mode during shutdown: {e}")

        # Cleanup both modes
        await self.release_resources()

        # Stop transcription engine
        if self._transcription_engine:
            try:
                await self._transcription_engine.stop()
                self._transcription_engine.cleanup()
            except Exception as e:
                logger.error(f"Error stopping transcription engine: {e}")

        self._async_initialized = False
        logger.info("ModeManager shutdown complete")


# ============================================
# Global Instance
# ============================================

_global_mode_manager: ModeManager | None = None
_global_lock = threading.Lock()


def get_mode_manager(
    settings: AppSettings | None = None,
    settings_manager: SettingsManager | None = None,
) -> ModeManager:
    """Get or create the global ModeManager instance.

    This function ensures thread-safe singleton access to the ModeManager.

    Args:
        settings: Optional application settings
        settings_manager: Optional settings manager

    Returns:
        The global ModeManager instance
    """
    global _global_mode_manager

    if _global_mode_manager is None:
        with _global_lock:
            if _global_mode_manager is None:
                _global_mode_manager = ModeManager(settings, settings_manager)

    return _global_mode_manager


def reset_mode_manager() -> None:
    """Reset the global mode manager instance (for testing)."""
    global _global_mode_manager
    with _global_lock:
        _global_mode_manager = None
        ModeManager._instance = None


