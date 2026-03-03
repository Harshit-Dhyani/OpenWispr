"""Core constants for Transcripta configuration.

These constants are shared between Python and TypeScript.
When modifying, run `python config/generate_ts.py` to update TypeScript definitions.
"""

from enum import Enum
from typing import Dict, List, Set


class AudioBackend(str, Enum):
    """Available audio backends."""

    SOUNDCARD = "soundcard"
    PYAUDIO = "pyaudio"


class ExecutionMode(str, Enum):
    """Model execution modes."""

    GPU = "gpu"
    CPU = "cpu"
    AUTO = "auto"


class LiveModeProfile(str, Enum):
    """Live transcription latency profiles."""

    ULTRA = "ultra"
    REALTIME = "realtime"
    LOW_LATENCY = "low_latency"
    BALANCED = "balanced"
    HIGH_ACCURACY = "high_accuracy"


class AudioConstants:
    """Audio processing constants."""

    DEFAULT_SAMPLE_RATE: int = 16000
    DEFAULT_CHANNELS: int = 1
    DEFAULT_CHUNK_SECONDS: float = 1.0
    DEFAULT_OVERLAP_SECONDS: float = 0.2
    DEFAULT_BLOCK_SECONDS: float = 0.1
    DEFAULT_METER_DECAY: float = 0.3
    DEFAULT_BACKEND: AudioBackend = AudioBackend.SOUNDCARD
    MAX_QUEUE_ITEMS: int = 100


SAMPLE_RATES: List[int] = [8000, 16000, 22050, 44100, 48000]


class VADConstants:
    """Voice Activity Detection constants."""

    DEFAULT_THRESHOLD_DB: float = -40.0
    DEFAULT_MIN_SILENCE_MS: int = 200
    DEFAULT_SPEECH_PAD_MS: int = 200
    DEFAULT_FILTER_ENABLED: bool = True


class ModelConstants:
    """ML model constants."""

    DEFAULT_MODEL_NAME: str = "small"
    DEFAULT_COMPUTE_TYPE: str = "float16"
    DEFAULT_CONFIDENCE_THRESHOLD: float = 0.6
    DEFAULT_BEAM_SIZE: int = 5
    DEFAULT_BEST_OF: int = 5
    DEFAULT_TEMPERATURE: float = 0.0
    MIN_SEGMENT_LENGTH: float = 0.5


class PerformanceConstants:
    """Performance and optimization constants."""

    DEFAULT_LIVE_MODE: LiveModeProfile = LiveModeProfile.BALANCED
    DEFAULT_EXECUTION_MODE: ExecutionMode = ExecutionMode.AUTO
    OUTPUT_REFRESH_SECONDS: float = 0.5


class SessionConstants:
    """Session management constants."""

    DEFAULT_EXPORT_ROOT: str = "sessions"
    DEFAULT_SESSION_NAME: str = "Untitled Session"


class UIConstants:
    """UI behavior constants."""

    DEFAULT_THEME: str = "dark"
    DEFAULT_FLOATING_POSITION: str = "bottom_right"
    DEFAULT_AUTO_HIDE_FLOATING: bool = True


class QualityConstants:
    """Quality control constants."""

    HALLUCINATION_CONFIDENCE_THRESHOLD: float = 0.3
    FILLER_CONFIDENCE_THRESHOLD: float = 0.4


class ServerConstants:
    """API server constants."""

    DEFAULT_HOST: str = "127.0.0.1"
    DEFAULT_PORT: int = 8765
    DEFAULT_LOG_LEVEL: str = "INFO"


# Live mode profiles with their timing parameters
LIVE_MODE_PROFILES: Dict[str, Dict[str, float]] = {
    LiveModeProfile.ULTRA: {"chunk_seconds": 0.1, "overlap_seconds": 0.02},
    LiveModeProfile.REALTIME: {"chunk_seconds": 0.2, "overlap_seconds": 0.04},
    LiveModeProfile.LOW_LATENCY: {"chunk_seconds": 0.5, "overlap_seconds": 0.1},
    LiveModeProfile.BALANCED: {"chunk_seconds": 1.0, "overlap_seconds": 0.2},
    LiveModeProfile.HIGH_ACCURACY: {"chunk_seconds": 2.0, "overlap_seconds": 0.4},
}

# Common filler words to filter
COMMON_FILLER_WORDS: Set[str] = {
    "um",
    "uh",
    "ah",
    "er",
    "hmm",
    "mmm",
    "uhh",
}

# Phrases that indicate hallucination
HALLUCINATION_PHRASES: List[str] = [
    "thank you for watching",
    "thanks for watching",
    "subscribe to",
    "like and subscribe",
    "click the link",
    "check out my",
]

# GPU fallback keywords (error messages that indicate GPU issues)
GPU_FALLBACK_KEYWORDS: List[str] = [
    "cuda",
    "out of memory",
    "gpu",
    "cudnn",
]
