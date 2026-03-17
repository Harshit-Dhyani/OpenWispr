"""Backward compatibility shim - redirects to app.audio.pipelines.pipeline_base.

This module exists for backwards compatibility during the audio pipeline
reorganization. The canonical source is app.audio.pipelines.pipeline_base.
"""

from app.audio.pipelines.pipeline_base import *  # noqa: F401, F403

__all__ = [
    "AudioPipeline",
    "PipelineConfig",
    "PipelineHealth",
    "PipelineMode",
    "PipelineState",
]
