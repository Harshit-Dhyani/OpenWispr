"""Speech-to-text engine and rolling chunking.

Optimized transcription engine with dual-mode support (Wispr/System),
adaptive beam sizing, and GPU memory pooling.
"""

from app.stt.fast_whisper_backend import (
    FastWhisperBackend as OptimizedWhisperBackend,
    ModeConfig,
    OptimizedWhisperFactory,
    SYSTEM_MODE,
    WISPR_MODE,
)
from app.stt.model_pool import ModelPool
from app.stt.streaming_engine import (
    DualModeTranscriptionEngine,
    PartialResult,
    PerformanceMetrics,
    StreamingInferenceEngine,
    TranscriptionMode,
)

__all__ = [
    # New optimized components
    "DualModeTranscriptionEngine",
    "StreamingInferenceEngine",
    "TranscriptionMode",
    "PartialResult",
    "PerformanceMetrics",
    "OptimizedWhisperBackend",
    "OptimizedWhisperFactory",
    "WISPR_MODE",
    "SYSTEM_MODE",
    "ModeConfig",
    "ModelPool",
]
