"""Centralized configuration package for Transcripta.

This package provides a single source of truth for all configuration values
shared between Python backend and TypeScript frontend.
"""

from config.python.constants import (
    AudioConstants,
    VADConstants,
    ModelConstants,
    PerformanceConstants,
    SessionConstants,
    UIConstants,
    QualityConstants,
    ServerConstants,
    LiveModeProfile,
    ExecutionMode,
    AudioBackend,
    SAMPLE_RATES,
    COMMON_FILLER_WORDS,
    HALLUCINATION_PHRASES,
    GPU_FALLBACK_KEYWORDS,
)
from config.python.text import (
    MODEL_NAMES,
    LIVE_MODE_LABELS,
    LIVE_MODE_DESCRIPTIONS,
    SETTING_LABELS,
    SETTING_DESCRIPTIONS,
    ERROR_MESSAGES,
    TOOLTIPS,
    BUTTON_LABELS,
    STATUS_LABELS,
)

__all__ = [
    # Constants classes
    "AudioConstants",
    "VADConstants",
    "ModelConstants",
    "PerformanceConstants",
    "SessionConstants",
    "UIConstants",
    "QualityConstants",
    "ServerConstants",
    "LiveModeProfile",
    "ExecutionMode",
    "AudioBackend",
    # Value constants
    "SAMPLE_RATES",
    "COMMON_FILLER_WORDS",
    "HALLUCINATION_PHRASES",
    "GPU_FALLBACK_KEYWORDS",
    # Text constants
    "MODEL_NAMES",
    "LIVE_MODE_LABELS",
    "LIVE_MODE_DESCRIPTIONS",
    "SETTING_LABELS",
    "SETTING_DESCRIPTIONS",
    "ERROR_MESSAGES",
    "TOOLTIPS",
    "BUTTON_LABELS",
    "STATUS_LABELS",
]
