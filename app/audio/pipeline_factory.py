"""Backward compatibility - pipeline_factory moved to app.audio.pipelines package."""

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
