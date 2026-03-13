"""Backward compatibility - wispr_pipeline moved to app.audio.pipelines package."""

from app.audio.pipelines.wispr_pipeline import *  # noqa: F401, F403

__all__ = [
    "WisprPipeline",
    "WisprPipelineConfig",
    "StreamingVAD",
]
