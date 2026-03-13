"""Centralized constants for OpenWispr backend.

This module contains all hardcoded values that were previously scattered
across the codebase. All modules should import from here.
"""


# ============================================
# App Constants
# ============================================
class AppConstants:
    """Application branding constants."""

    APP_NAME = "OpenWispr"
    APP_SLUG = "openwispr"
    LOCAL_API_TITLE_SUFFIX = "Local API"
    DOWNLOAD_USER_AGENT = f"{APP_NAME}/1.0"


# ============================================
# Audio Constants
# ============================================
class AudioConstants:
    """Audio processing constants."""

    DEFAULT_SAMPLE_RATE = 16000
    SAMPLE_RATES = [8000, 16000, 22050, 44100, 48000]
    DEFAULT_CHANNELS = 1
    DEFAULT_CHUNK_SECONDS = 1.6
    DEFAULT_OVERLAP_SECONDS = 0.32  # 20% of chunk
    MIN_CHUNK_SECONDS = 0.4
    MAX_CHUNK_SECONDS = 4.5
    DEFAULT_BLOCK_SECONDS = 0.02  # 20ms for low latency
    DEFAULT_METER_DECAY = 0.85
    MAX_QUEUE_ITEMS = 16
    CAPTURE_TIMEOUT_SECONDS = 0.25

    # Backend settings
    DEFAULT_BACKEND = "auto"
    DEFAULT_CAPTURE_DEVICE_ID = "default"
    DEFAULT_CAPTURE_MODE = "system"  # system or microphone

    # Probe settings
    DEFAULT_PROBE_DURATION = 3.0
    DEFAULT_PROBE_BLOCK_SIZE = 1024


# ============================================
# VAD Constants
# ============================================
class VADConstants:
    """Voice Activity Detection constants."""

    DEFAULT_THRESHOLD_DB = -40.0
    DEFAULT_MIN_SILENCE_MS = 300
    DEFAULT_SPEECH_PAD_MS = 200
    DEFAULT_FILTER_ENABLED = True
    DEFAULT_HYSTERESIS_MS = 100.0

    # Energy threshold bounds
    MIN_THRESHOLD_DB = -60.0
    MAX_THRESHOLD_DB = -20.0


# ============================================
# Model Constants
# ============================================
class ModelConstants:
    """Whisper model and transcription constants."""

    DEFAULT_MODEL_NAME = "medium"
    DEFAULT_COMPUTE_TYPE = "float16"
    DEFAULT_BEAM_SIZE = 5
    DEFAULT_BEST_OF = 5
    DEFAULT_PATIENCE = 1.0
    DEFAULT_TEMPERATURE = 0.0
    DEFAULT_CONFIDENCE_THRESHOLD = 0.6
    MIN_SEGMENT_LENGTH = 0.5  # seconds

    # Valid model sizes
    VALID_MODELS = {"tiny", "base", "small", "medium", "large-v3", "turbo"}

    # Model catalog IDs mapping
    MODEL_CATALOG_MAPPING = {
        "tiny": "whisper-tiny",
        "base": "whisper-base",
        "small": "whisper-small",
        "medium": "whisper-medium",
        "large-v3": "whisper-large-v3",
        "turbo": "whisper-turbo",
    }

    # Memory requirements in GB (approximate for float16)
    MEMORY_REQUIREMENTS_GB = {
        "tiny": 1.0,
        "base": 1.0,
        "small": 2.0,
        "medium": 5.0,
        "large-v3": 10.0,
        "turbo": 6.0,
    }

    # Compute type memory multipliers
    INT8_MEMORY_MULTIPLIER = 0.6


# ============================================
# Performance Constants
# ============================================
class PerformanceConstants:
    """Performance and optimization constants."""

    DEFAULT_LIVE_MODE = "balanced"
    DEFAULT_EXECUTION_MODE = "auto"
    DEFAULT_MAX_WORKERS = 4
    OUTPUT_REFRESH_SECONDS = 0.5
    TARGET_LATENCY_MS = 500

    # Thread pool settings
    DEFAULT_THREAD_POOL_WORKERS = 2
    MAX_THREAD_POOL_WORKERS = 16

    # Queue settings
    DEFAULT_CHUNK_DURATION_MS = 200
    MAX_QUEUE_SIZE = 16


# ============================================
# Session Constants
# ============================================
class SessionConstants:
    """Session management constants."""

    DEFAULT_SESSION_TITLE = "New Session"
    DEFAULT_EXPORT_ROOT = "sessions"
    MAX_TRANSCRIPT_SEGMENTS = 500
    MAX_SUPPRESSED_SEGMENTS = 200
    MAX_FORMULAS = 200
    MAX_REVIEW_ITEMS = 200

    # Session timeouts (seconds)
    THREAD_JOIN_TIMEOUT = 3.0
    STOP_TIMEOUT = 5.0
    CAPTURE_THREAD_JOIN_TIMEOUT = 3.0


# ============================================
# UI Constants
# ============================================
class UIConstants:
    """User interface constants."""

    DEFAULT_THEME = "light"
    DEFAULT_LANGUAGE = "auto"
    SETTINGS_VERSION = 5
    AUTO_SAVE_INTERVAL_SECONDS = 30
    MAX_LOG_FILES = 10

    # Valid themes
    VALID_THEMES = {"light", "dark", "cyber", "dracula", "ocean", "sunset", "forest"}

    # Hotkey defaults
    DEFAULT_HOTKEY = "Ctrl+Shift+T"


# ============================================
# Quality Filter Constants
# ============================================
class QualityConstants:
    """Transcription quality filtering constants."""

    # Punctuation filtering
    MAX_PUNCTUATION_RATIO = 0.45

    # Repeated character detection
    MAX_REPEATED_CHAR_RUN = 12

    # Low entropy detection
    LOW_ENTROPY_UNIQUE_RATIO_THRESHOLD = 0.12
    LOW_ENTROPY_TOKEN_REPEAT_THRESHOLD = 6
    LOW_ENTROPY_SHORT_TOKEN_THRESHOLD = 2
    LOW_ENTROPY_SHORT_UNIQUE_RATIO = 0.2

    # Filler word detection
    FILLER_CONFIDENCE_THRESHOLD = 0.72
    SHORT_TEXT_CONFIDENCE_THRESHOLD = 0.65
    SHORT_TEXT_MAX_LENGTH = 5

    # Quality labels
    QUALITY_LABEL_JUNK = "junk"
    QUALITY_LABEL_WEAK = "weak"
    QUALITY_LABEL_OK = "ok"

    # Confidence thresholds for quality labels
    JUNK_CONFIDENCE_THRESHOLD = 0.70
    WEAK_CONFIDENCE_THRESHOLD = 0.85
    DUPLICATE_CONFIDENCE_THRESHOLD = 0.55

    # No speech detection
    NO_SPEECH_PROB_THRESHOLD = 0.6
    NO_SPEECH_CONFIDENCE_THRESHOLD = 0.7

    # Low logprob detection
    LOW_LOGPROB_THRESHOLD = -1.0
    LOW_LOGPROB_CONFIDENCE_THRESHOLD = 0.7

    # Compression anomaly detection
    COMPRESSION_RATIO_THRESHOLD = 2.4
    COMPRESSION_CONFIDENCE_THRESHOLD = 0.7

    # Overlap deduplication
    OVERLAP_DEDUP_TIME_WINDOW_SECONDS = 10.0
    OVERLAP_DEDUP_MAX_DUPLICATES = 1

    # Confidence proxy calculation
    CONFIDENCE_PROXY_BASE = 0.65
    CONFIDENCE_PROXY_AVG_LOGPROB_OFFSET = 1.2
    CONFIDENCE_PROXY_AVG_LOGPROB_SCALE = 1.2
    CONFIDENCE_PROXY_MAX_BONUS = 0.25
    CONFIDENCE_PROXY_MAX_PENALTY = 0.35
    CONFIDENCE_PROXY_NO_SPEECH_SCALE = 0.25
    CONFIDENCE_PROXY_COMPRESSION_THRESHOLD = 2.2
    CONFIDENCE_PROXY_COMPRESSION_PENALTY_SCALE = 0.08
    CONFIDENCE_PROXY_COMPRESSION_MAX_PENALTY = 0.2
    CONFIDENCE_PROXY_MAX_SCORE = 0.99


# ============================================
# Filler Words
# ============================================
COMMON_FILLER_WORDS = {
    "hmm",
    "uh",
    "um",
    "ah",
    "uhh",
    "ahh",
    "er",
    "erm",
}


# ============================================
# Hallucination Detection
# ============================================
HALLUCINATION_PHRASES = {
    "thanks for watching",
    "thank you for watching",
    "please subscribe",
    "like and subscribe",
    "click the link",
    "check the description",
    "see you next time",
    "don't forget to like",
    "thank you",
    "thanks",
    "thanks a lot",
    "thank you very much",
    "bye",
    "goodbye",
}

HALLUCINATION_CONFIDENCE_THRESHOLD = 0.80


# ============================================
# Server/API Constants
# ============================================
class ServerConstants:
    """API server constants."""

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 8765
    DEFAULT_LOG_LEVEL = "INFO"


# ============================================
# Live Mode Profiles
# ============================================
LIVE_MODE_PROFILES: dict[str, dict[str, float]] = {
    "ultra": {"chunk_seconds": 0.1, "overlap_seconds": 0.02},  # 100ms - fastest
    "realtime": {"chunk_seconds": 0.2, "overlap_seconds": 0.04},  # 200ms - fast
    "low_latency": {"chunk_seconds": 0.5, "overlap_seconds": 0.1},  # 500ms
    "balanced": {"chunk_seconds": 1.0, "overlap_seconds": 0.2},  # 1s - default
    "high_accuracy": {"chunk_seconds": 2.0, "overlap_seconds": 0.4},  # 2s
}


# ============================================
# Fast Chunker Constants
# ============================================
class FastChunkerConstants:
    """Fast chunking constants."""

    DEFAULT_BASE_CHUNK_MS = 200.0
    DEFAULT_OVERLAP_MS = 50.0
    DEFAULT_MIN_CHUNK_MS = 100.0
    DEFAULT_MAX_CHUNK_MS = 400.0
    DEFAULT_VAD_THRESHOLD_DB = -35.0
    DEFAULT_VAD_HYSTERESIS_MS = 100.0

    # Adaptive sizing
    HIGH_SPEECH_DENSITY_THRESHOLD = 0.7
    LOW_SPEECH_DENSITY_THRESHOLD = 0.2
    ADAPTIVE_SIZE_HIGH_MULTIPLIER = 0.75
    ADAPTIVE_SIZE_LOW_MULTIPLIER = 1.25

    # Buffer settings
    BUFFER_CAPACITY_SECONDS = 2.0  # 2 seconds to handle up to 1.6s chunks

    # Speech density window
    SPEECH_DENSITY_WINDOW_SIZE = 10
    SPEECH_DENSITY_MIN_SAMPLES = 3

    # Streaming iterator
    DEFAULT_MAX_QUEUE_SIZE = 100


# ============================================
# Audio Capture Constants
# ============================================
class AudioCaptureConstants:
    """Audio capture constants."""

    MAX_CONSECUTIVE_ERRORS = 5
    STATS_LOG_INTERVAL_SECONDS = 2.0
    QUEUE_PUT_TIMEOUT_SECONDS = 0.2
    READ_TIMEOUT_SECONDS = 0.25
    SLOW_CHUNK_PROCESSING_THRESHOLD_MS = 100.0


# ============================================
# Health Monitoring Constants
# ============================================
class HealthConstants:
    """Health monitoring and logging constants."""

    LOOP_STATS_INTERVAL_SECONDS = 1.0
    HEALTH_EMIT_INTERVAL_SECONDS = 0.1
    LOOP_LOG_INTERVAL_SECONDS = 5.0
    LOG_LEVEL_DEBUG = 10  # logging.DEBUG


# ============================================
# Auto-optimization Constants
# ============================================
class AutoOptimizationConstants:
    """Auto-optimization constants."""

    DEFAULT_ENABLED = True
    DEFAULT_MODE = "balanced"  # maximum, balanced, speed, low_memory
    VALID_MODES = {"maximum", "balanced", "speed", "low_memory"}


# ============================================
# Refiner Constants
# ============================================
class RefinerConstants:
    """LLM refiner constants."""

    DEFAULT_MODEL_ID = "qwen2.5-3b-instruct"
    DEFAULT_ENGINE_PREFERENCE = "llamacpp"
    VALID_ENGINES = {"llamacpp", "ollama"}
    DEFAULT_REFINEMENT_MODE = "off"
    VALID_REFINEMENT_MODES = {"off", "strict", "polished"}
    DEFAULT_REFINEMENT_PROFILE = "clean_dictation"
    VALID_REFINEMENT_PROFILES = {
        "raw",
        "clean_dictation",
        "professional",
        "student_notes",
        "code_logs",
    }


# ============================================
# GPU Fallback Keywords
# ============================================
GPU_FALLBACK_KEYWORDS = [
    "cublas",
    "cuda",
    "cudnn",
    "gpu",
    "out of memory",
    "curand",
    "cusolver",
    "cusparse",
    "nccl",
    "thrust",
    "device-side assert",
    "an illegal memory access",
    "cuda error",
    "no kernel image",
    "nvidia",
]
