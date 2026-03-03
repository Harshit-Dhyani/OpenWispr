"""Audio capture, processing, and device discovery."""

from app.audio.vad_optimized import (
    NoiseProfiler,
    OptimizedVAD,
    SpeechSegmenter,
    VADConfig,
    VADMode,
    VADState,
    create_vad,
    detect_speech_regions,
)
from app.audio.audio_processing import (
    AudioPreprocessor,
    ProcessingConfig,
    ProcessingMode,
    preprocess_audio,
    create_preprocessor,
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
