"""Backward compatibility - system_pipeline moved to app.audio.pipelines package."""

from app.audio.pipelines.system_pipeline import *  # noqa: F401, F403

__all__ = [
    "SystemPipeline",
    "SystemPipelineConfig",
    "SilenceDetector",
    "RingBuffer",
]
