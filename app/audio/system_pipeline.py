"""Backward compatibility shim - redirects to app.audio.pipelines.system_pipeline.

This module exists for backwards compatibility during the audio pipeline
reorganization. The canonical source is app.audio.pipelines.system_pipeline.
"""

from app.audio.pipelines.system_pipeline import *  # noqa: F401, F403

__all__ = [
    "SystemPipeline",
    "SystemPipelineConfig",
    "SilenceDetector",
    "RingBuffer",
]
