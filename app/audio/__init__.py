"""Audio capture, processing, and device discovery."""

from app.audio.processing import (
    AudioPreprocessor,
    ProcessingConfig,
    ProcessingMode,
    create_preprocessor,
    preprocess_audio,
)
from app.audio.vad import (
    NoiseProfiler,
    OptimizedVAD,
    SpeechSegmenter,
    VADConfig,
    VADMode,
    VADState,
    create_vad,
    detect_speech_regions,
)

__all__ = [
    "OptimizedVAD",
    "VADConfig",
    "VADMode",
    "VADState",
    "NoiseProfiler",
    "SpeechSegmenter",
    "create_vad",
    "detect_speech_regions",
    "AudioPreprocessor",
    "ProcessingConfig",
    "ProcessingMode",
    "preprocess_audio",
    "create_preprocessor",
]
