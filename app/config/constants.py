"""Centralized constants for OpenWispr backend.

Contains all hardcoded values organized into constant classes:
- AppConstants: Application branding and metadata
- AudioConstants: Audio capture and processing parameters
- VADConstants: Voice Activity Detection thresholds
- ModelConstants: Whisper model sizes and transcription parameters
- PerformanceConstants: Threading, queue, and latency settings
- SessionConstants: Session management and timeout values
- UIConstants: Themes, languages, and UI-related defaults
- QualityConstants: Transcription quality filtering thresholds
- FastChunkerConstants: Audio chunking parameters
- RefinerConstants: LLM refiner configuration
- ProviderConstants: Local LLM provider URLs

Also exports:
- COMMON_FILLER_WORDS: Set of filler words to filter
- HALLUCINATION_PHRASES: Phrases indicating model hallucination
- COMMON_SHORT_FORMS: Dictionary of abbreviations to expand
- GPU_FALLBACK_KEYWORDS: Error keywords for GPU fallback logic
- LIVE_MODE_PROFILES: Predefined latency/accuracy profiles

All modules should import constants from here to avoid scattered magic numbers.
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
        "base": "whisper-tiny",
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
    SETTINGS_VERSION = 7
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

# Common short forms/abbreviations that get expanded in real-time
# These are applied BEFORE dictionary/snippet expansion
COMMON_SHORT_FORMS: dict[str, str] = {
    # Business & Professional
    "asap": "as soon as possible",
    "btw": "by the way",
    "fyi": "for your information",
    "eta": "estimated time of arrival",
    "eod": "end of day",
    "tod": "today",
    "tom": "tomorrow",
    "wfh": "work from home",
    "ot": "overtime",
    "pto": "paid time off",
    "loa": "leave of absence",
    "nda": "non-disclosure agreement",
    "pua": "personal use agreement",
    "sla": "service level agreement",
    "roi": "return on investment",
    "kpi": "key performance indicator",
    "okr": "objectives and key results",
    "mbo": "management by objectives",
    "ceo": "chief executive officer",
    "cto": "chief technology officer",
    "cfo": "chief financial officer",
    "coo": "chief operating officer",
    "cmo": "chief marketing officer",
    "hr": "human resources",
    "it": "information technology",
    "qa": "quality assurance",
    "r&d": "research and development",
    "b2b": "business to business",
    "b2c": "business to consumer",
    "p&l": "profit and loss",
    "ytd": "year to date",
    "mtd": "month to date",
    "qtd": "quarter to date",
    # Technical & Development
    "api": "application programming interface",
    "sdk": "software development kit",
    "ide": "integrated development environment",
    "ci": "continuous integration",
    "cd": "continuous deployment",
    "devops": "development operations",
    "sql": "structured query language",
    "nosql": "not only sql",
    "html": "hypertext markup language",
    "css": "cascading style sheets",
    "js": "JavaScript",
    "ts": "TypeScript",
    "json": "JavaScript Object Notation",
    "xml": "extensible markup language",
    "yaml": "yaml ain't markup language",
    "url": "uniform resource locator",
    "uri": "uniform resource identifier",
    "dns": "domain name system",
    "tcp": "transmission control protocol",
    "udp": "user datagram protocol",
    "http": "hypertext transfer protocol",
    "https": "hypertext transfer protocol secure",
    "ftp": "file transfer protocol",
    "ssh": "secure shell",
    "vpn": "virtual private network",
    "lan": "local area network",
    "wan": "wide area network",
    "ram": "random access memory",
    "rom": "read only memory",
    "cpu": "central processing unit",
    "gpu": "graphics processing unit",
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "dl": "deep learning",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "ar": "augmented reality",
    "vr": "virtual reality",
    "mr": "mixed reality",
    "saas": "software as a service",
    "paas": "platform as a service",
    "iaas": "infrastructure as a service",
    "db": "database",
    "repo": "repository",
    "pr": "pull request",
    "mr": "merge request",
    "issue": "issue",
    "bug": "bug",
    "feat": "feature",
    "fix": "fix",
    "docs": "documentation",
    "refactor": "refactor",
    "test": "test",
    "chore": "chore",
    "wip": "work in progress",
    "tbd": "to be determined",
    "tbc": "to be confirmed",
    # Communication
    "imo": "in my opinion",
    "imho": "in my humble opinion",
    "tbh": "to be honest",
    "idk": "I don't know",
    "idc": "I don't care",
    "idgaf": "I don't give a f***",
    "idc": "I don't care",
    "smh": "shaking my head",
    "fomo": "fear of missing out",
    "yolo": "you only live once",
    "lol": "laughing out loud",
    "lmao": "laughing my a** off",
    "rofl": "rolling on the floor laughing",
    "btw": "by the way",
    "omg": "oh my god",
    "omfg": "oh my f***ing god",
    "wtf": "what the f***",
    "wth": "what the heck",
    "brb": "be right back",
    "bbl": "be back later",
    "ttyl": "talk to you later",
    "gn": "good night",
    "gm": "good morning",
    "gd": "good day",
    "thx": "thanks",
    "thnx": "thanks",
    "pls": "please",
    "plz": "please",
    "rly": "really",
    "msg": "message",
    "pic": "picture",
    "info": "information",
    "def": "definitely",
    "probs": "probably",
    "gonna": "going to",
    "wanna": "want to",
    "gotta": "got to",
    "kinda": "kind of",
    "sorta": "sort of",
    "dunno": "don't know",
    "lemme": "let me",
    "gimme": "give me",
    "coulda": "could have",
    "woulda": "would have",
    "shoulda": "should have",
    "aint": "isn't",
    "cant": "cannot",
    "wont": "will not",
    "dont": "do not",
    "doesnt": "does not",
    "isnt": "is not",
    "arent": "are not",
    "wasnt": "was not",
    "werent": "were not",
    "hasnt": "has not",
    "havent": "have not",
    "hadnt": "had not",
    "isnt": "is not",
    "ive": "I have",
    "im": "I am",
    "id": "I would",
    "ill": "I will",
    "youre": "you are",
    "youve": "you have",
    "youll": "you will",
    "weve": "we have",
    "were": "we are",
    "well": "we will",
    "theyre": "they are",
    "theyve": "they have",
    "theyll": "they will",
    "hes": "he is",
    "shes": "she is",
    "its": "it is",
    "thats": "that is",
    "whats": "what is",
    "wheres": "where is",
    "whens": "when is",
    "hows": "how is",
    "lets": "let us",
    # Time & Dates
    "1d": "1 day",
    "2d": "2 days",
    "1w": "1 week",
    "2w": "2 weeks",
    "1mo": "1 month",
    "2mo": "2 months",
    "1yr": "1 year",
    "1h": "1 hour",
    "2h": "2 hours",
    "1m": "1 minute",
    "2m": "2 minutes",
    "1s": "1 second",
    "2s": "2 seconds",
    # Money & Numbers
    "$1": "one dollar",
    "$2": "two dollars",
    "$5": "five dollars",
    "$10": "ten dollars",
    "$20": "twenty dollars",
    "$50": "fifty dollars",
    "$100": "one hundred dollars",
    "k": "thousand",
    "m": "million",
    "b": "billion",
    "t": "trillion",
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
# Provider Constants
# ============================================
class ProviderConstants:
    """Local LLM provider URL constants."""

    DEFAULT_OLLAMA_URL = "http://localhost:11434"
    DEFAULT_LM_STUDIO_URL = "http://localhost:1234"


# ============================================
# Refiner Constants
# ============================================
class RefinerConstants:
    """LLM refiner constants."""

    DEFAULT_MODEL_ID = "qwen2.5-3b-instruct"
    DEFAULT_ENGINE_PREFERENCE = "llamacpp"
    VALID_ENGINES = {"llamacpp", "ollama", "lm_studio"}
    DEFAULT_REFINEMENT_MODE = "strict"
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

# Module-level exports for generate_ts.py compatibility - reference existing module-level constants
SAMPLE_RATES = AudioConstants.SAMPLE_RATES  # class attribute
