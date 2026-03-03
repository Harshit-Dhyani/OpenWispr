"""Pipeline Factory - Creates the correct pipeline for each mode.

Provides a factory interface for creating and managing audio pipelines
with automatic device detection and mode-specific optimizations.
"""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from app.audio.pipeline_base import (
    AudioPipeline,
    PipelineConfig,
    PipelineHealth,
    PipelineMode,
    PipelineState,
)

if TYPE_CHECKING:
    from pathlib import Path

    from app.core.models import DeviceProbeResult

# Import pipeline implementations
from app.audio.system_pipeline import SystemPipeline, SystemPipelineConfig
from app.audio.wispr_pipeline import WisprPipeline, WisprPipelineConfig

logger = logging.getLogger(__name__)


class PipelineType(Enum):
    """Types of audio pipelines available."""

    WISPR = "wispr"  # Hotkey/mic mode
    SYSTEM = "system"  # System audio mode
    AUTO = "auto"  # Auto-detect based on device


def create_pipeline(
    pipeline_type: PipelineType | str,
    *,
    device_id: str | None = None,
    sample_rate: int = 16000,
    **kwargs,
) -> AudioPipeline:
    """Create an audio pipeline of the specified type.

    Args:
        pipeline_type: Type of pipeline to create (wispr, system, or auto)
        device_id: Audio device ID to use (None for default)
        sample_rate: Sample rate for audio capture (default 16000)
        **kwargs: Additional configuration parameters

    Returns:
        Configured AudioPipeline instance

    Raises:
        ValueError: If pipeline_type is invalid
    """
    # Normalize pipeline type
    if isinstance(pipeline_type, str):
        try:
            pipeline_type = PipelineType(pipeline_type.lower())
        except ValueError as exc:
            valid_types = [t.value for t in PipelineType]
            raise ValueError(
                f"Invalid pipeline type '{pipeline_type}'. Valid types: {valid_types}"
            ) from exc

    # Auto-detect pipeline type based on device
    if pipeline_type == PipelineType.AUTO:
        pipeline_type = _detect_pipeline_type(device_id)
        logger.info(
            f"Auto-detected pipeline type: {pipeline_type.value}", extra={"device_id": device_id}
        )

    # Create appropriate pipeline
    if pipeline_type == PipelineType.WISPR:
        return _create_wispr_pipeline(device_id, sample_rate, **kwargs)
    elif pipeline_type == PipelineType.SYSTEM:
        return _create_system_pipeline(device_id, sample_rate, **kwargs)
    else:
        raise ValueError(f"Unhandled pipeline type: {pipeline_type}")


def _create_wispr_pipeline(
    device_id: str | None,
    sample_rate: int,
    **kwargs,
) -> WisprPipeline:
    """Create a Wispr (hotkey/mic) pipeline with optimized defaults."""
    config = WisprPipelineConfig(
        device_id=device_id,
        sample_rate=sample_rate,
        channels=1,
        # Wispr-specific defaults
        frame_duration_ms=kwargs.get("frame_duration_ms", 50.0),
        pre_buffer_duration_ms=kwargs.get("pre_buffer_duration_ms", 200.0),
        vad_threshold_db=kwargs.get("vad_threshold_db", -40.0),
        early_emission_frames=kwargs.get("early_emission_frames", 2),
        target_first_word_latency_ms=kwargs.get("target_first_word_latency_ms", 200.0),
        # Base config
        max_buffer_size=kwargs.get("max_buffer_size", sample_rate * 5),
        health_report_interval_ms=kwargs.get("health_report_interval_ms", 1000.0),
        max_consecutive_errors=kwargs.get("max_consecutive_errors", 5),
        reconnect_cooldown_seconds=kwargs.get("reconnect_cooldown_seconds", 1.0),
        # Callbacks
        on_error=kwargs.get("on_error"),
        on_health_update=kwargs.get("on_health_update"),
        on_state_change=kwargs.get("on_state_change"),
    )

    logger.debug(
        "Creating Wispr pipeline",
        extra={
            "device_id": device_id,
            "sample_rate": sample_rate,
            "frame_duration_ms": config.frame_duration_ms,
            "target_latency_ms": config.target_first_word_latency_ms,
        },
    )

    return WisprPipeline(config)


def _create_system_pipeline(
    device_id: str | None,
    sample_rate: int,
    **kwargs,
) -> SystemPipeline:
    """Create a System (loopback) pipeline with optimized defaults."""
    config = SystemPipelineConfig(
        device_id=device_id,
        sample_rate=sample_rate,
        channels=kwargs.get("channels", 2),  # System often has 2+ channels
        # System-specific defaults
        buffer_duration_ms=kwargs.get("buffer_duration_ms", 500.0),
        buffer_count=kwargs.get("buffer_count", 8),
        segment_on_silence=kwargs.get("segment_on_silence", True),
        silence_duration_ms=kwargs.get("silence_duration_ms", 1000.0),
        min_segment_duration_ms=kwargs.get("min_segment_duration_ms", 500.0),
        max_segment_duration_ms=kwargs.get("max_segment_duration_ms", 30000.0),
        mix_to_mono=kwargs.get("mix_to_mono", True),
        preferred_backend=kwargs.get("preferred_backend", "auto"),
        # Base config
        max_buffer_size=kwargs.get("max_buffer_size", sample_rate * 60),
        health_report_interval_ms=kwargs.get("health_report_interval_ms", 1000.0),
        max_consecutive_errors=kwargs.get("max_consecutive_errors", 5),
        reconnect_cooldown_seconds=kwargs.get("reconnect_cooldown_seconds", 1.0),
        # Callbacks
        on_error=kwargs.get("on_error"),
        on_health_update=kwargs.get("on_health_update"),
        on_state_change=kwargs.get("on_state_change"),
    )

    logger.debug(
        "Creating System pipeline",
        extra={
            "device_id": device_id,
            "sample_rate": sample_rate,
            "buffer_duration_ms": config.buffer_duration_ms,
            "buffer_count": config.buffer_count,
        },
    )

    return SystemPipeline(config)


def _detect_pipeline_type(device_id: str | None) -> PipelineType:
    """Auto-detect pipeline type based on device characteristics.

    Uses heuristics to determine if device is likely a microphone
    (use Wispr) or loopback (use System).
    """
    if device_id is None:
        return PipelineType.WISPR  # Default to mic mode

    device_lower = device_id.lower()

    # Loopback indicators
    loopback_indicators = [
        "loopback",
        "what u hear",
        "stereo mix",
        "waveout",
        "cable",
        "virtual",
    ]

    for indicator in loopback_indicators:
        if indicator in device_lower:
            return PipelineType.SYSTEM

    # Microphone indicators
    mic_indicators = [
        "microphone",
        "mic",
        "headset",
        "webcam",
        "builtin",
    ]

    for indicator in mic_indicators:
        if indicator in device_lower:
            return PipelineType.WISPR

    # Default to Wispr for unknown devices
    return PipelineType.WISPR


class PipelineManager:
    """Manages multiple pipeline instances with lifecycle tracking.

    Provides centralized management for creating, starting, stopping,
    and monitoring multiple audio pipelines.
    """

    def __init__(self) -> None:
        self._pipelines: dict[str, AudioPipeline] = {}
        self._pipeline_types: dict[str, PipelineType] = {}
        logger.debug("PipelineManager initialized")

    def create(
        self,
        pipeline_id: str,
        pipeline_type: PipelineType | str,
        **kwargs,
    ) -> AudioPipeline:
        """Create and register a new pipeline.

        Args:
            pipeline_id: Unique identifier for this pipeline
            pipeline_type: Type of pipeline to create
            **kwargs: Configuration parameters

        Returns:
            Created AudioPipeline instance
        """
        if pipeline_id in self._pipelines:
            raise ValueError(f"Pipeline '{pipeline_id}' already exists")

        pipeline = create_pipeline(pipeline_type, **kwargs)
        self._pipelines[pipeline_id] = pipeline
        self._pipeline_types[pipeline_id] = (
            pipeline_type
            if isinstance(pipeline_type, PipelineType)
            else PipelineType(pipeline_type)
        )

        logger.info(
            f"Pipeline '{pipeline_id}' created",
            extra={"type": str(pipeline_type), "mode": pipeline._get_mode().value},
        )

        return pipeline

    async def start(self, pipeline_id: str) -> None:
        """Start a registered pipeline."""
        pipeline = self._get_pipeline(pipeline_id)
        await pipeline.start()

    async def stop(self, pipeline_id: str) -> None:
        """Stop a registered pipeline."""
        pipeline = self._get_pipeline(pipeline_id)
        await pipeline.stop()

    async def stop_all(self) -> None:
        """Stop all registered pipelines."""
        for pipeline_id in list(self._pipelines.keys()):
            try:
                await self.stop(pipeline_id)
            except Exception as exc:
                logger.error(f"Error stopping pipeline '{pipeline_id}': {exc}")

    async def pause(self, pipeline_id: str) -> None:
        """Pause a registered pipeline."""
        pipeline = self._get_pipeline(pipeline_id)
        await pipeline.pause()

    async def resume(self, pipeline_id: str) -> None:
        """Resume a registered pipeline."""
        pipeline = self._get_pipeline(pipeline_id)
        await pipeline.resume()

    async def read(
        self,
        pipeline_id: str,
        timeout: float | None = None,
    ) -> Any:
        """Read audio from a pipeline."""
        pipeline = self._get_pipeline(pipeline_id)
        return await pipeline.read(timeout=timeout)

    def get_health(self, pipeline_id: str) -> PipelineHealth:
        """Get health metrics for a pipeline."""
        pipeline = self._get_pipeline(pipeline_id)
        return pipeline.get_health()

    def get_all_health(self) -> dict[str, PipelineHealth]:
        """Get health metrics for all pipelines."""
        return {pid: pipeline.get_health() for pid, pipeline in self._pipelines.items()}

    def remove(self, pipeline_id: str) -> None:
        """Remove a pipeline from management.

        The pipeline should be stopped before removal.
        """
        if pipeline_id not in self._pipelines:
            raise KeyError(f"Pipeline '{pipeline_id}' not found")

        pipeline = self._pipelines[pipeline_id]
        if pipeline.is_running:
            logger.warning(
                f"Removing running pipeline '{pipeline_id}'", extra={"state": pipeline.state.name}
            )

        del self._pipelines[pipeline_id]
        del self._pipeline_types[pipeline_id]
        logger.debug(f"Pipeline '{pipeline_id}' removed from manager")

    def list_pipelines(self) -> list[str]:
        """List all registered pipeline IDs."""
        return list(self._pipelines.keys())

    def get_pipeline_info(self, pipeline_id: str) -> dict:
        """Get information about a pipeline."""
        pipeline = self._get_pipeline(pipeline_id)
        return {
            "id": pipeline_id,
            "type": self._pipeline_types.get(pipeline_id, PipelineType.AUTO).value,
            "mode": pipeline._get_mode().value,
            "state": pipeline.state.name,
            "is_running": pipeline.is_running,
            "is_paused": pipeline.is_paused,
            "health": pipeline.health.to_dict(),
        }

    def _get_pipeline(self, pipeline_id: str) -> AudioPipeline:
        """Get a pipeline by ID."""
        if pipeline_id not in self._pipelines:
            raise KeyError(f"Pipeline '{pipeline_id}' not found")
        return self._pipelines[pipeline_id]


# Convenience exports
__all__ = [
    "create_pipeline",
    "PipelineManager",
    "PipelineType",
    "AudioPipeline",
    "PipelineConfig",
    "PipelineHealth",
    "PipelineMode",
    "PipelineState",
    "WisprPipeline",
    "WisprPipelineConfig",
    "SystemPipeline",
    "SystemPipelineConfig",
]
