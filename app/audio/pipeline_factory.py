"""Backward compatibility shim - redirects to app.audio.pipelines.pipeline_factory.

This module exists for backwards compatibility during the audio pipeline
reorganization. The canonical source is app.audio.pipelines.pipeline_factory.
"""

from app.audio.pipelines.pipeline_factory import *  # noqa: F401, F403
from app.audio.pipelines.pipeline_factory import _detect_pipeline_type

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
    "_detect_pipeline_type",
]
