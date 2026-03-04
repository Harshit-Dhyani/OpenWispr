"""Compatibility re-export for centralized runtime constants.

The canonical runtime definitions live in :mod:`app.core.constants`.
This module remains as a stable import path for config/codegen callers.
"""

from app.core.constants import (  # noqa: F401
    AppConstants,
    AudioConstants,
    AudioCaptureConstants,
    AutoOptimizationConstants,
    COMMON_FILLER_WORDS,
    FastChunkerConstants,
    GPU_FALLBACK_KEYWORDS,
    HALLUCINATION_CONFIDENCE_THRESHOLD,
    HALLUCINATION_PHRASES,
    HealthConstants,
    LIVE_MODE_PROFILES,
    ModelConstants,
    PerformanceConstants,
    QualityConstants,
    RefinerConstants,
    ServerConstants,
    SessionConstants,
    UIConstants,
    VADConstants,
)

SAMPLE_RATES = [8000, 16000, 22050, 44100, 48000]

__all__ = [
    "AppConstants",
    "AudioConstants",
    "AudioCaptureConstants",
    "AutoOptimizationConstants",
    "COMMON_FILLER_WORDS",
    "FastChunkerConstants",
    "GPU_FALLBACK_KEYWORDS",
    "HALLUCINATION_CONFIDENCE_THRESHOLD",
    "HALLUCINATION_PHRASES",
    "HealthConstants",
    "LIVE_MODE_PROFILES",
    "ModelConstants",
    "PerformanceConstants",
    "QualityConstants",
    "RefinerConstants",
    "SAMPLE_RATES",
    "ServerConstants",
    "SessionConstants",
    "UIConstants",
    "VADConstants",
]
