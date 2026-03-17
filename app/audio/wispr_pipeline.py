"""Backward compatibility shim - redirects to app.audio.pipelines.wispr_pipeline.

This module exists for backwards compatibility during the audio pipeline
reorganization. The canonical source is app.audio.pipelines.wispr_pipeline.
"""

from app.audio.pipelines.wispr_pipeline import *  # noqa: F401, F403

__all__ = [
    "WisprPipeline",
    "WisprPipelineConfig",
    "StreamingVAD",
]
