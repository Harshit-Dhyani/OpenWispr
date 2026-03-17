"""Abstract base class for audio pipelines.

Provides a common interface for all audio capture pipelines with support for:
- Async/await throughout the entire pipeline lifecycle
- State management with lifecycle states (IDLE, INITIALIZING, RUNNING, PAUSED, STOPPING, STOPPED, ERROR)
- Health metrics reporting (frames captured, dropped, buffer events, latency, RMS)
- Pause/resume capability for temporary capture suspension
- Graceful shutdown with resource cleanup
- Device change handling and reconnection
- Error recovery with automatic reconnection attempts
- Ring buffer management for audio data

Subclasses (wispr_pipeline, system_pipeline) inherit this base class and implement
device-specific initialization, capture loops, and cleanup logic.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from pathlib import Path

    from app.core.models import DeviceProbeResult

logger = logging.getLogger(__name__)


class PipelineState(Enum):
    """Pipeline lifecycle states.

    Represents the possible states in the pipeline lifecycle:
    - IDLE: Initial state, no resources allocated
    - INITIALIZING: Device is being opened and configured
    - RUNNING: Actively capturing audio
    - PAUSED: Capture suspended but device remains open
    - STOPPING: Shutdown in progress
    - STOPPED: Clean shutdown complete
    - ERROR: Failure state requiring intervention
    """

    IDLE = auto()
    INITIALIZING = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()


class PipelineMode(Enum):
    """Pipeline operation modes.

    Defines the two primary pipeline modes:
    - WISPR: Hotkey/microphone mode optimized for low-latency real-time capture
    - SYSTEM: System audio mode with buffer-based batch processing
    """

    WISPR = "wispr"  # Hotkey/mic mode - low latency
    SYSTEM = "system"  # System audio - buffer-based


@dataclass(slots=True)
class PipelineHealth:
    """Health metrics for audio pipeline.

    Tracks runtime metrics for monitoring pipeline health and diagnosing issues.

    Attributes:
        state: Current pipeline state
        frames_captured: Total number of audio frames successfully captured
        frames_dropped: Number of frames lost due to buffer overflow or errors
        buffer_underruns: Number of times read operation found empty buffer
        buffer_overruns: Number of times write operation filled buffer completely
        device_errors: Total count of device-level errors encountered
        device_reconnects: Number of successful automatic reconnection attempts
        average_latency_ms: Rolling average capture-to-output latency in milliseconds
        current_rms: Current RMS energy level of audio data
        peak_rms: Maximum RMS energy observed since last reset
        is_speech_active: Whether voice activity is currently detected
        last_error: Description of most recent error (None if no errors)
        last_warning: Description of most recent warning (None if no warnings)
        updated_at: Timestamp of last health metric update
    """

    state: PipelineState = PipelineState.IDLE
    frames_captured: int = 0
    frames_dropped: int = 0
    buffer_underruns: int = 0
    buffer_overruns: int = 0
    device_errors: int = 0
    device_reconnects: int = 0
    average_latency_ms: float = 0.0
    current_rms: float = 0.0
    peak_rms: float = 0.0
    is_speech_active: bool = False
    last_error: str | None = None
    last_warning: str | None = None
    updated_at: float = field(default_factory=time.monotonic)

    def to_dict(self) -> dict[str, Any]:
        """Convert health metrics to dictionary for serialization.

        Returns:
            Dictionary representation of health metrics with rounded numeric values
        """
        return {
            "state": self.state.name,
            "frames_captured": self.frames_captured,
            "frames_dropped": self.frames_dropped,
            "buffer_underruns": self.buffer_underruns,
            "buffer_overruns": self.buffer_overruns,
            "device_errors": self.device_errors,
            "device_reconnects": self.device_reconnects,
            "average_latency_ms": round(self.average_latency_ms, 3),
            "current_rms": round(self.current_rms, 6),
            "peak_rms": round(self.peak_rms, 6),
            "is_speech_active": self.is_speech_active,
            "last_error": self.last_error,
            "last_warning": self.last_warning,
            "updated_at": self.updated_at,
        }


@dataclass(slots=True)
class PipelineConfig:
    """Base configuration for audio pipelines.

    Defines settings for device selection, audio format, buffer behavior,
    health monitoring, error recovery, and event callbacks.

    Attributes:
        device_id: Specific device identifier or None for default device
        sample_rate: Audio sample rate in Hz (default: 16000)
        channels: Number of audio channels (default: 1 for mono)
        dtype: numpy dtype for audio data (default: float32)
        max_buffer_size: Maximum samples to buffer (default: 5 seconds at 16kHz)
        health_report_interval_ms: Interval between health metric updates (default: 1000ms)
        max_consecutive_errors: Errors before triggering reconnection (default: 5)
        reconnect_cooldown_seconds: Minimum time between reconnection attempts (default: 1.0)
        on_error: Callback invoked when error threshold is exceeded
        on_health_update: Callback invoked on each health report interval
        on_state_change: Callback invoked when pipeline state changes
    """

    device_id: str | None = None
    sample_rate: int = 16000
    channels: int = 1
    dtype: np.dtype = np.float32

    # Buffer settings
    max_buffer_size: int = 16000 * 5  # 5 seconds at 16kHz

    # Health monitoring
    health_report_interval_ms: float = 1000.0

    # Error recovery
    max_consecutive_errors: int = 5
    reconnect_cooldown_seconds: float = 1.0

    # Callbacks
    on_error: Callable[[Exception], None] | None = None
    on_health_update: Callable[[PipelineHealth], None] | None = None
    on_state_change: Callable[[PipelineState, PipelineState], None] | None = None


class AudioPipeline(ABC):
    """Abstract base class for audio capture pipelines.

    Provides a common interface for all audio capture pipelines with:
    - Async/await support throughout
    - State management (IDLE, INITIALIZING, RUNNING, PAUSED, STOPPED, ERROR)
    - Health metrics reporting
    - Pause/resume capability
    - Graceful shutdown
    - Device change handling
    - Error recovery (disconnect/reconnect)

    Subclasses must implement:
    - _get_mode(): Return the pipeline mode (WISPR or SYSTEM)
    - _initialize_device(): Open and configure the audio device
    - _capture_loop(): Main capture loop that checks stop/pause events
    - _cleanup_device(): Release device resources
    - probe_device(): Test device and return metrics

    Example:
        >>> config = PipelineConfig(device_id="default", sample_rate=16000)
        >>> pipeline = MicrophonePipeline(config)
        >>>
        >>> await pipeline.start()
        >>> audio = await pipeline.read(timeout=5.0)
        >>> await pipeline.stop()
    """

    def __init__(self, config: PipelineConfig) -> None:
        """Initialize pipeline with configuration.

        Args:
            config: Pipeline configuration with device and behavior settings
        """
        self.config = config
        self._state = PipelineState.IDLE
        self._health = PipelineHealth()

        # Async primitives
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._capture_task: asyncio.Task | None = None
        self._health_task: asyncio.Task | None = None

        # Ring buffer for audio data (zero-copy where possible)
        self._ring_buffer: deque[np.ndarray] = deque(maxlen=100)
        self._buffer_lock = asyncio.Lock()

        # Output queue for processed audio
        self._output_queue: asyncio.Queue[np.ndarray] = asyncio.Queue(
            maxsize=max(1, config.max_buffer_size // 800)  # Approximate frame count
        )

        # Latency tracking
        self._latency_window: deque[float] = deque(maxlen=100)

        # Device management
        self._current_device_id = config.device_id
        self._consecutive_errors = 0
        self._last_reconnect_time = 0.0

        logger.debug(
            f"{self.__class__.__name__} initialized",
            extra={"config": self._config_to_dict()},
        )

    @property
    def state(self) -> PipelineState:
        """Current pipeline state."""
        return self._state

    @property
    def health(self) -> PipelineHealth:
        """Current health metrics snapshot."""
        return self._health

    @property
    def is_running(self) -> bool:
        """Whether pipeline is actively capturing."""
        return self._state == PipelineState.RUNNING

    @property
    def is_paused(self) -> bool:
        """Whether pipeline is paused."""
        return self._state == PipelineState.PAUSED

    @property
    def is_stopped(self) -> bool:
        """Whether pipeline has stopped or encountered error."""
        return self._state in (PipelineState.STOPPED, PipelineState.ERROR)

    @abstractmethod
    def _get_mode(self) -> PipelineMode:
        """Return the pipeline mode (WISPR or SYSTEM).

        Returns:
            Pipeline mode enum value
        """
        pass

    @abstractmethod
    async def _initialize_device(self) -> None:
        """Initialize the audio device. Called at start and on reconnect."""
        pass

    @abstractmethod
    async def _capture_loop(self) -> None:
        """Main capture loop implementation.

        Must check _stop_event and _pause_event to handle graceful shutdown
        and pause/resume. Should push captured audio to _output_queue.
        """
        pass

    @abstractmethod
    async def _cleanup_device(self) -> None:
        """Cleanup audio device resources.

        Called during stop or recovery to release device handle.
        """
        pass

    @abstractmethod
    def probe_device(self, *, duration: float, output_dir: Path) -> DeviceProbeResult:
        """Probe the audio device and return metrics.

        Args:
            duration: Probe test duration in seconds
            output_dir: Directory to write test audio files

        Returns:
            DeviceProbeResult with test metrics
        """
        pass

    async def start(self) -> None:
        """Start the audio pipeline.

        Transitions from IDLE -> INITIALIZING -> RUNNING.
        Initializes device, starts capture and health monitoring tasks.

        Raises:
            RuntimeError: If pipeline is not in IDLE, STOPPED, or ERROR state
        """
        if self._state not in (PipelineState.IDLE, PipelineState.STOPPED, PipelineState.ERROR):
            raise RuntimeError(f"Cannot start from state {self._state.name}")

        await self._transition_state(PipelineState.INITIALIZING)

        try:
            await self._initialize_device()
            self._stop_event.clear()
            self._pause_event.clear()

            # Start capture and health monitoring tasks
            self._capture_task = asyncio.create_task(
                self._run_capture_with_recovery(), name=f"{self.__class__.__name__}-capture"
            )
            self._health_task = asyncio.create_task(
                self._health_monitoring_loop(), name=f"{self.__class__.__name__}-health"
            )

            await self._transition_state(PipelineState.RUNNING)
            logger.info(f"{self.__class__.__name__} started")

        except Exception as exc:
            await self._transition_state(PipelineState.ERROR)
            self._health.last_error = str(exc)
            raise

    async def stop(self) -> None:
        """Stop the audio pipeline gracefully.

        Transitions to STOPPING then STOPPED state, cancels tasks,
        and cleans up device resources. Timeout-safe cancellation.
        """
        if self._state in (PipelineState.STOPPED, PipelineState.IDLE):
            return

        await self._transition_state(PipelineState.STOPPING)
        self._stop_event.set()

        # Cancel tasks
        if self._capture_task and not self._capture_task.done():
            self._capture_task.cancel()
            try:
                await asyncio.wait_for(self._capture_task, timeout=3.0)
            except (TimeoutError, asyncio.CancelledError):
                pass

        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
            try:
                await asyncio.wait_for(self._health_task, timeout=1.0)
            except (TimeoutError, asyncio.CancelledError):
                pass

        try:
            await self._cleanup_device()
        except Exception as exc:
            logger.warning(f"Error during cleanup: {exc}")

        await self._transition_state(PipelineState.STOPPED)
        logger.info(f"{self.__class__.__name__} stopped")

    async def pause(self) -> None:
        """Pause audio capture.

        Transitions from RUNNING to PAUSED state.
        Device remains open but capture is suspended via _pause_event.

        Raises:
            RuntimeError: If pipeline is not in RUNNING state
        """
        if self._state != PipelineState.RUNNING:
            raise RuntimeError(f"Cannot pause from state {self._state.name}")

        self._pause_event.set()
        await self._transition_state(PipelineState.PAUSED)
        logger.debug(f"{self.__class__.__name__} paused")

    async def resume(self) -> None:
        """Resume audio capture.

        Transitions from PAUSED to RUNNING state.
        Clears _pause_event to resume capture loop.

        Raises:
            RuntimeError: If pipeline is not in PAUSED state
        """
        if self._state != PipelineState.PAUSED:
            raise RuntimeError(f"Cannot resume from state {self._state.name}")

        self._pause_event.clear()
        await self._transition_state(PipelineState.RUNNING)
        logger.debug(f"{self.__class__.__name__} resumed")

    async def read(self, timeout: float | None = None) -> np.ndarray | None:
        """Read audio data from the pipeline output queue.

        Args:
            timeout: Maximum time to wait for data in seconds (None = wait forever)

        Returns:
            Audio data as numpy array or None if timeout occurred/no data available
        """
        try:
            return await asyncio.wait_for(self._output_queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    async def change_device(self, device_id: str | None) -> None:
        """Change the audio device.

        Updates device configuration and triggers reconnection by setting
        error count to threshold, forcing the capture loop to reconnect.

        Args:
            device_id: New device identifier or None for system default
        """
        logger.info(f"Changing device from {self._current_device_id} to {device_id}")
        self._current_device_id = device_id
        self.config.device_id = device_id

        # Trigger reconnect in capture loop
        self._consecutive_errors = self.config.max_consecutive_errors

    def get_health(self) -> PipelineHealth:
        """Get current health metrics snapshot.

        Returns:
            Current PipelineHealth metrics
        """
        return self._health

    async def _transition_state(self, new_state: PipelineState) -> None:
        """Transition to a new state with optional callback.

        Updates internal state, health metrics, and invokes state change callback
        if configured.

        Args:
            new_state: Target state to transition to
        """
        old_state = self._state
        self._state = new_state
        self._health.state = new_state

        if self.config.on_state_change and old_state != new_state:
            try:
                self.config.on_state_change(old_state, new_state)
            except Exception as exc:
                logger.warning(f"State change callback failed: {exc}")

        logger.debug(f"State transition: {old_state.name} -> {new_state.name}")

    async def _run_capture_with_recovery(self) -> None:
        """Run capture loop with error recovery.

        Wraps _capture_loop to handle exceptions, track error counts,
        trigger recovery attempts, and transition to ERROR state when
        max consecutive errors is exceeded.
        """
        while not self._stop_event.is_set():
            try:
                await self._capture_loop()
                self._consecutive_errors = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._consecutive_errors += 1
                self._health.device_errors += 1
                self._health.last_error = str(exc)

                logger.error(
                    f"Capture error ({self._consecutive_errors}/"
                    f"{self.config.max_consecutive_errors}): {exc}"
                )

                if self._consecutive_errors >= self.config.max_consecutive_errors:
                    if self.config.on_error:
                        self.config.on_error(exc)
                    await self._transition_state(PipelineState.ERROR)
                    break

                # Attempt recovery
                await self._attempt_recovery()

    async def _attempt_recovery(self) -> None:
        """Attempt to recover from an error.

        Implements reconnection cooldown to prevent rapid retry cycles.
        Cleans up existing device, waits briefly, then reinitializes.
        Updates health metrics with reconnection result.
        """
        now = time.monotonic()
        if now - self._last_reconnect_time < self.config.reconnect_cooldown_seconds:
            await asyncio.sleep(0.1)
            return

        self._last_reconnect_time = now
        logger.info("Attempting device recovery...")

        try:
            await self._cleanup_device()
            await asyncio.sleep(0.1)
            await self._initialize_device()
            self._health.device_reconnects += 1
            logger.info("Device recovery successful")
        except Exception as exc:
            logger.error(f"Device recovery failed: {exc}")

    async def _health_monitoring_loop(self) -> None:
        """Periodically report health metrics.

        Runs on configurable interval, updates health metrics and invokes
        on_health_update callback if configured. Continues until stop event is set.
        """
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.config.health_report_interval_ms / 1000.0
                )
            except TimeoutError:
                pass

            if self._stop_event.is_set():
                break

            self._update_health_metrics()

            if self.config.on_health_update:
                try:
                    self.config.on_health_update(self._health)
                except Exception as exc:
                    logger.warning(f"Health callback failed: {exc}")

    def _update_health_metrics(self) -> None:
        """Update health metrics.

        Updates timestamp and computes rolling average latency from latency window.
        """
        self._health.updated_at = time.monotonic()

        if self._latency_window:
            self._health.average_latency_ms = sum(self._latency_window) / len(self._latency_window)

    def _record_latency(self, latency_ms: float) -> None:
        """Record a latency measurement.

        Args:
            latency_ms: Latency in milliseconds to add to rolling window
        """
        self._latency_window.append(latency_ms)

    def _calculate_rms(self, audio: np.ndarray) -> float:
        """Calculate RMS energy of audio data.

        Updates current_rms and peak_rms in health metrics.

        Args:
            audio: Audio samples as numpy array

        Returns:
            RMS energy value
        """
        if audio.size == 0:
            return 0.0
        rms = float(np.sqrt(np.mean(np.square(audio)) + 1e-12))
        self._health.current_rms = rms
        self._health.peak_rms = max(self._health.peak_rms, rms)
        return rms

    def _config_to_dict(self) -> dict[str, Any]:
        """Convert config to dict for logging.

        Returns:
            Dictionary with non-sensitive configuration values
        """
        return {
            "device_id": self.config.device_id,
            "sample_rate": self.config.sample_rate,
            "channels": self.config.channels,
            "max_buffer_size": self.config.max_buffer_size,
            "mode": self._get_mode().value,
        }

    async def _wait_while_paused(self) -> None:
        """Wait while paused, returns when resumed or stopped.

        Used by subclasses in capture loop to efficiently wait during pause state
        without busy-waiting.
        """
        while self._pause_event.is_set() and not self._stop_event.is_set():
            await asyncio.sleep(0.01)
