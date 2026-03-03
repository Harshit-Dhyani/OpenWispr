"""Abstract base class for audio pipelines.

Provides a common interface for all audio capture pipelines with support for
async/await, health monitoring, pause/resume, and graceful shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable

import numpy as np

if TYPE_CHECKING:
    from pathlib import Path

    from app.core.models import DeviceProbeResult

logger = logging.getLogger(__name__)


class PipelineState(Enum):
    """Pipeline lifecycle states."""

    IDLE = auto()
    INITIALIZING = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()


class PipelineMode(Enum):
    """Pipeline operation modes."""

    WISPR = "wispr"  # Hotkey/mic mode - low latency
    SYSTEM = "system"  # System audio - buffer-based


@dataclass(slots=True)
class PipelineHealth:
    """Health metrics for audio pipeline."""

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
    """Base configuration for audio pipelines."""

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
    - State management (IDLE, RUNNING, PAUSED, STOPPED, ERROR)
    - Health metrics reporting
    - Pause/resume capability
    - Graceful shutdown
    - Device change handling
    - Error recovery (disconnect/reconnect)
    """

    def __init__(self, config: PipelineConfig) -> None:
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
            maxsize=config.max_buffer_size // 800  # Approximate frame count
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
        return self._state

    @property
    def health(self) -> PipelineHealth:
        return self._health

    @property
    def is_running(self) -> bool:
        return self._state == PipelineState.RUNNING

    @property
    def is_paused(self) -> bool:
        return self._state == PipelineState.PAUSED

    @property
    def is_stopped(self) -> bool:
        return self._state in (PipelineState.STOPPED, PipelineState.ERROR)

    @abstractmethod
    def _get_mode(self) -> PipelineMode:
        """Return the pipeline mode (WISPR or SYSTEM)."""
        pass

    @abstractmethod
    async def _initialize_device(self) -> None:
        """Initialize the audio device. Called at start and on reconnect."""
        pass

    @abstractmethod
    async def _capture_loop(self) -> None:
        """Main capture loop implementation. Must check _stop_event and _pause_event."""
        pass

    @abstractmethod
    async def _cleanup_device(self) -> None:
        """Cleanup audio device resources."""
        pass

    @abstractmethod
    def probe_device(self, *, duration: float, output_dir: Path) -> DeviceProbeResult:
        """Probe the audio device and return metrics."""
        pass

    async def start(self) -> None:
        """Start the audio pipeline.

        Transitions from IDLE -> INITIALIZING -> RUNNING.
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

        Transitions to STOPPED state and cleans up resources.
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
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
            try:
                await asyncio.wait_for(self._health_task, timeout=1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

        try:
            await self._cleanup_device()
        except Exception as exc:
            logger.warning(f"Error during cleanup: {exc}")

        await self._transition_state(PipelineState.STOPPED)
        logger.info(f"{self.__class__.__name__} stopped")

    async def pause(self) -> None:
        """Pause audio capture.

        Transitions from RUNNING -> PAUSED.
        Device remains open but capture is suspended.
        """
        if self._state != PipelineState.RUNNING:
            raise RuntimeError(f"Cannot pause from state {self._state.name}")

        self._pause_event.set()
        await self._transition_state(PipelineState.PAUSED)
        logger.debug(f"{self.__class__.__name__} paused")

    async def resume(self) -> None:
        """Resume audio capture.

        Transitions from PAUSED -> RUNNING.
        """
        if self._state != PipelineState.PAUSED:
            raise RuntimeError(f"Cannot resume from state {self._state.name}")

        self._pause_event.clear()
        await self._transition_state(PipelineState.RUNNING)
        logger.debug(f"{self.__class__.__name__} resumed")

    async def read(self, timeout: float | None = None) -> np.ndarray | None:
        """Read audio data from the pipeline output queue.

        Args:
            timeout: Maximum time to wait for data (None = wait forever)

        Returns:
            Audio data as numpy array or None if timeout/no data
        """
        try:
            return await asyncio.wait_for(self._output_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def change_device(self, device_id: str | None) -> None:
        """Change the audio device.

        Triggers a reconnection to the new device.
        """
        logger.info(f"Changing device from {self._current_device_id} to {device_id}")
        self._current_device_id = device_id
        self.config.device_id = device_id

        # Trigger reconnect in capture loop
        self._consecutive_errors = self.config.max_consecutive_errors

    def get_health(self) -> PipelineHealth:
        """Get current health metrics."""
        return self._health

    async def _transition_state(self, new_state: PipelineState) -> None:
        """Transition to a new state with optional callback."""
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
        """Run capture loop with error recovery."""
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
        """Attempt to recover from an error."""
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
        """Periodically report health metrics."""
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.config.health_report_interval_ms / 1000.0
                )
            except asyncio.TimeoutError:
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
        """Update health metrics."""
        self._health.updated_at = time.monotonic()

        if self._latency_window:
            self._health.average_latency_ms = sum(self._latency_window) / len(self._latency_window)

    def _record_latency(self, latency_ms: float) -> None:
        """Record a latency measurement."""
        self._latency_window.append(latency_ms)

    def _calculate_rms(self, audio: np.ndarray) -> float:
        """Calculate RMS of audio data."""
        if audio.size == 0:
            return 0.0
        rms = float(np.sqrt(np.mean(np.square(audio)) + 1e-12))
        self._health.current_rms = rms
        self._health.peak_rms = max(self._health.peak_rms, rms)
        return rms

    def _config_to_dict(self) -> dict[str, Any]:
        """Convert config to dict for logging."""
        return {
            "device_id": self.config.device_id,
            "sample_rate": self.config.sample_rate,
            "channels": self.config.channels,
            "max_buffer_size": self.config.max_buffer_size,
            "mode": self._get_mode().value,
        }

    async def _wait_while_paused(self) -> None:
        """Wait while paused, returns when resumed or stopped."""
        while self._pause_event.is_set() and not self._stop_event.is_set():
            await asyncio.sleep(0.01)
