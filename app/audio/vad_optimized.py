"""Backward compatibility - vad_optimized moved to app.audio.vad package."""

from app.audio.vad.vad_optimized import *  # noqa: F401, F403

__all__ = [
    "NoiseProfiler",
    "OptimizedVAD",
    "SpeechSegmenter",
    "VADConfig",
    "VADMode",
    "VADState",
    "create_vad",
    "detect_speech_regions",
]
