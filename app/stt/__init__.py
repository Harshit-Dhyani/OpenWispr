"""Speech-to-text engine and rolling chunking.

Optimized transcription engine with dual-mode support (Wispr/System),
adaptive beam sizing, and GPU memory estimation/tracking.
"""

from app.stt.fast_whisper_backend import (
    SYSTEM_MODE,
    WISPR_MODE,
    ModeConfig,
    OptimizedWhisperFactory,
)
from app.stt.fast_whisper_backend import (
    FastWhisperBackend as OptimizedWhisperBackend,
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
