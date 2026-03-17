"""Audio capture, processing, and voice activity detection.

Provides high-level audio pipeline components for speech recognition:
- VAD: Voice activity detection, noise profiling, speech segmentation
- Processing: Audio preprocessing, normalization, resampling

Key exports:
    OptimizedVAD, VADConfig, VADMode, VADState - Voice activity detection
    NoiseProfiler - Background noise analysis
    SpeechSegmenter - Speech region detection
    AudioPreprocessor, ProcessingConfig, ProcessingMode - Audio preprocessing

Key collaborators:
    app/audio/backends/ - Audio capture implementations
    app/audio/devices/ - Device discovery and resolution
    app/core/models.py - AudioDeviceInfo, DeviceProbeResult
"""

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
