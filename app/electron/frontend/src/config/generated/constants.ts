// Auto-generated from app/config/constants.py
// Do not edit manually - run `python app/config/generate_ts.py` to regenerate

// ============================================
// App Constants
// ============================================
export const AppConstants = {
  APP_NAME: 'OpenWispr' as const,
  APP_SLUG: 'openwispr' as const,
  LOCAL_API_TITLE_SUFFIX: 'Local API' as const,
  DOWNLOAD_USER_AGENT: 'OpenWispr/1.0' as const,
} as const;

// ============================================
// Audio Constants
// ============================================
export const AudioConstants = {
  DEFAULT_SAMPLE_RATE: 16000,
  DEFAULT_CHANNELS: 1,
  DEFAULT_CHUNK_SECONDS: 1.6,
  DEFAULT_OVERLAP_SECONDS: 0.32,
  MIN_CHUNK_SECONDS: 0.4,
  MAX_CHUNK_SECONDS: 4.5,
  DEFAULT_BLOCK_SECONDS: 0.02,
  DEFAULT_METER_DECAY: 0.85,
  MAX_QUEUE_ITEMS: 16,
  CAPTURE_TIMEOUT_SECONDS: 0.25,
  DEFAULT_BACKEND: 'auto' as const,
  DEFAULT_CAPTURE_DEVICE_ID: 'default' as const,
  DEFAULT_CAPTURE_MODE: 'system' as const,
  DEFAULT_PROBE_DURATION: 3.0,
  DEFAULT_PROBE_BLOCK_SIZE: 1024,
} as const;

export const VALID_SAMPLE_RATES = [8000, 16000, 22050, 44100, 48000] as const;

// ============================================
// VAD Constants
// ============================================
export const VADConstants = {
  DEFAULT_THRESHOLD_DB: -40.0,
  DEFAULT_MIN_SILENCE_MS: 300,
  DEFAULT_SPEECH_PAD_MS: 200,
  DEFAULT_FILTER_ENABLED: true,
  DEFAULT_HYSTERESIS_MS: 100.0,
  MIN_THRESHOLD_DB: -60.0,
  MAX_THRESHOLD_DB: -20.0,
} as const;

// ============================================
// Model Constants
// ============================================
export const ModelConstants = {
  DEFAULT_MODEL_NAME: 'medium' as const,
  DEFAULT_COMPUTE_TYPE: 'float16' as const,
  DEFAULT_BEAM_SIZE: 5,
  DEFAULT_BEST_OF: 5,
  DEFAULT_PATIENCE: 1.0,
  DEFAULT_TEMPERATURE: 0.0,
  DEFAULT_CONFIDENCE_THRESHOLD: 0.6,
  MIN_SEGMENT_LENGTH: 0.5,
} as const;

export const VALID_MODEL_NAMES = ["turbo", "tiny", "medium", "large-v3", "small", "base"] as const;
export const VALID_COMPUTE_TYPES = ['float16', 'int8', 'int8_float16'] as const;

export const MODEL_CATALOG_MAPPING = {"tiny": "whisper-tiny", "base": "whisper-tiny", "small": "whisper-small", "medium": "whisper-medium", "large-v3": "whisper-large-v3", "turbo": "whisper-turbo"} as const;

// ============================================
// Performance Constants
// ============================================
export const PerformanceConstants = {
  DEFAULT_LIVE_MODE: 'balanced' as const,
  DEFAULT_EXECUTION_MODE: 'auto' as const,
  DEFAULT_MAX_WORKERS: 4,
  OUTPUT_REFRESH_SECONDS: 0.5,
  TARGET_LATENCY_MS: 500,
  DEFAULT_THREAD_POOL_WORKERS: 2,
  MAX_THREAD_POOL_WORKERS: 16,
  DEFAULT_CHUNK_DURATION_MS: 200,
  MAX_QUEUE_SIZE: 16,
} as const;

export const VALID_LIVE_MODES = ['ultra', 'realtime', 'low_latency', 'balanced', 'high_accuracy'] as const;
export const VALID_EXECUTION_MODES = ['auto', 'cpu_only', 'gpu_only'] as const;

// ============================================
// Session Constants
// ============================================
export const SessionConstants = {
  DEFAULT_SESSION_TITLE: 'New Session',
  DEFAULT_EXPORT_ROOT: 'sessions',
  MAX_TRANSCRIPT_SEGMENTS: 500,
  MAX_SUPPRESSED_SEGMENTS: 200,
  MAX_FORMULAS: 200,
  MAX_REVIEW_ITEMS: 200,
  THREAD_JOIN_TIMEOUT: 3.0,
  STOP_TIMEOUT: 5.0,
  CAPTURE_THREAD_JOIN_TIMEOUT: 3.0,
} as const;

// ============================================
// UI Constants
// ============================================
export const UIConstants = {
  DEFAULT_THEME: 'light' as const,
  DEFAULT_LANGUAGE: 'auto' as const,
  SETTINGS_VERSION: 7,
  AUTO_SAVE_INTERVAL_SECONDS: 30,
  MAX_LOG_FILES: 10,
  DEFAULT_HOTKEY: 'Ctrl+Shift+T',
} as const;

export const VALID_THEMES = ["cyber", "dark", "dracula", "forest", "light", "ocean", "sunset"] as const;
export const VALID_LOG_LEVELS = ['DEBUG', 'INFO', 'WARN', 'ERROR'] as const;

// ============================================
// Quality Constants
// ============================================
export const QualityConstants = {
  MAX_PUNCTUATION_RATIO: 0.45,
  MAX_REPEATED_CHAR_RUN: 12,
  LOW_ENTROPY_UNIQUE_RATIO_THRESHOLD: 0.12,
  LOW_ENTROPY_TOKEN_REPEAT_THRESHOLD: 6,
  LOW_ENTROPY_SHORT_TOKEN_THRESHOLD: 2,
  LOW_ENTROPY_SHORT_UNIQUE_RATIO: 0.2,
  FILLER_CONFIDENCE_THRESHOLD: 0.72,
  SHORT_TEXT_CONFIDENCE_THRESHOLD: 0.65,
  SHORT_TEXT_MAX_LENGTH: 5,
  QUALITY_LABEL_JUNK: 'junk',
  QUALITY_LABEL_WEAK: 'weak',
  QUALITY_LABEL_OK: 'ok',
  JUNK_CONFIDENCE_THRESHOLD: 0.7,
  WEAK_CONFIDENCE_THRESHOLD: 0.85,
  DUPLICATE_CONFIDENCE_THRESHOLD: 0.55,
  NO_SPEECH_PROB_THRESHOLD: 0.6,
  NO_SPEECH_CONFIDENCE_THRESHOLD: 0.7,
  LOW_LOGPROB_THRESHOLD: -1.0,
  LOW_LOGPROB_CONFIDENCE_THRESHOLD: 0.7,
  COMPRESSION_RATIO_THRESHOLD: 2.4,
  COMPRESSION_CONFIDENCE_THRESHOLD: 0.7,
  OVERLAP_DEDUP_TIME_WINDOW_SECONDS: 10.0,
  OVERLAP_DEDUP_MAX_DUPLICATES: 1,
  CONFIDENCE_PROXY_BASE: 0.65,
  CONFIDENCE_PROXY_AVG_LOGPROB_OFFSET: 1.2,
  CONFIDENCE_PROXY_AVG_LOGPROB_SCALE: 1.2,
  CONFIDENCE_PROXY_MAX_BONUS: 0.25,
  CONFIDENCE_PROXY_MAX_PENALTY: 0.35,
  CONFIDENCE_PROXY_NO_SPEECH_SCALE: 0.25,
  CONFIDENCE_PROXY_COMPRESSION_THRESHOLD: 2.2,
  CONFIDENCE_PROXY_COMPRESSION_PENALTY_SCALE: 0.08,
  CONFIDENCE_PROXY_COMPRESSION_MAX_PENALTY: 0.2,
  CONFIDENCE_PROXY_MAX_SCORE: 0.99,
} as const;

// ============================================
// Filler Words
// ============================================
export const COMMON_FILLER_WORDS = ["ah", "ahh", "er", "erm", "hmm", "uh", "uhh", "um"] as const;

// ============================================
// Hallucination Detection
// ============================================
export const HALLUCINATION_PHRASES = ["bye", "check the description", "click the link", "don't forget to like", "goodbye", "like and subscribe", "please subscribe", "see you next time", "thank you", "thank you for watching", "thank you very much", "thanks", "thanks a lot", "thanks for watching"] as const;
export const HALLUCINATION_CONFIDENCE_THRESHOLD = 0.8;

// ============================================
// Short Form Expansions
// ============================================
export const COMMON_SHORT_FORMS = {"$1": "one dollar", "$10": "ten dollars", "$100": "one hundred dollars", "$2": "two dollars", "$20": "twenty dollars", "$5": "five dollars", "$50": "fifty dollars", "1d": "1 day", "1h": "1 hour", "1m": "1 minute", "1mo": "1 month", "1s": "1 second", "1w": "1 week", "1yr": "1 year", "2d": "2 days", "2h": "2 hours", "2m": "2 minutes", "2mo": "2 months", "2s": "2 seconds", "2w": "2 weeks", "ai": "artificial intelligence", "aint": "isn't", "api": "application programming interface", "ar": "augmented reality", "arent": "are not", "asap": "as soon as possible", "b": "billion", "b2b": "business to business", "b2c": "business to consumer", "bbl": "be back later", "brb": "be right back", "btw": "by the way", "bug": "bug", "cant": "cannot", "cd": "continuous deployment", "ceo": "chief executive officer", "cfo": "chief financial officer", "chore": "chore", "ci": "continuous integration", "cmo": "chief marketing officer", "coo": "chief operating officer", "coulda": "could have", "cpu": "central processing unit", "css": "cascading style sheets", "cto": "chief technology officer", "cv": "computer vision", "db": "database", "def": "definitely", "devops": "development operations", "dl": "deep learning", "dns": "domain name system", "docs": "documentation", "doesnt": "does not", "dont": "do not", "dunno": "don't know", "eod": "end of day", "eta": "estimated time of arrival", "feat": "feature", "fix": "fix", "fomo": "fear of missing out", "ftp": "file transfer protocol", "fyi": "for your information", "gd": "good day", "gimme": "give me", "gm": "good morning", "gn": "good night", "gonna": "going to", "gotta": "got to", "gpu": "graphics processing unit", "hadnt": "had not", "hasnt": "has not", "havent": "have not", "hes": "he is", "hows": "how is", "hr": "human resources", "html": "hypertext markup language", "http": "hypertext transfer protocol", "https": "hypertext transfer protocol secure", "iaas": "infrastructure as a service", "id": "I would", "idc": "I don't care", "ide": "integrated development environment", "idgaf": "I don't give a f***", "idk": "I don't know", "ill": "I will", "im": "I am", "imho": "in my humble opinion", "imo": "in my opinion", "info": "information", "isnt": "is not", "issue": "issue", "it": "information technology", "its": "it is", "ive": "I have", "js": "JavaScript", "json": "JavaScript Object Notation", "k": "thousand", "kinda": "kind of", "kpi": "key performance indicator", "lan": "local area network", "lemme": "let me", "lets": "let us", "lmao": "laughing my a** off", "loa": "leave of absence", "lol": "laughing out loud", "m": "million", "mbo": "management by objectives", "ml": "machine learning", "mr": "merge request", "msg": "message", "mtd": "month to date", "nda": "non-disclosure agreement", "nlp": "natural language processing", "nosql": "not only sql", "okr": "objectives and key results", "omfg": "oh my f***ing god", "omg": "oh my god", "ot": "overtime", "p&l": "profit and loss", "paas": "platform as a service", "pic": "picture", "pls": "please", "plz": "please", "pr": "pull request", "probs": "probably", "pto": "paid time off", "pua": "personal use agreement", "qa": "quality assurance", "qtd": "quarter to date", "r&d": "research and development", "ram": "random access memory", "refactor": "refactor", "repo": "repository", "rly": "really", "rofl": "rolling on the floor laughing", "roi": "return on investment", "rom": "read only memory", "saas": "software as a service", "sdk": "software development kit", "shes": "she is", "shoulda": "should have", "sla": "service level agreement", "smh": "shaking my head", "sorta": "sort of", "sql": "structured query language", "ssh": "secure shell", "t": "trillion", "tbc": "to be confirmed", "tbd": "to be determined", "tbh": "to be honest", "tcp": "transmission control protocol", "test": "test", "thats": "that is", "theyll": "they will", "theyre": "they are", "theyve": "they have", "thnx": "thanks", "thx": "thanks", "tod": "today", "tom": "tomorrow", "ts": "TypeScript", "ttyl": "talk to you later", "udp": "user datagram protocol", "uri": "uniform resource identifier", "url": "uniform resource locator", "vpn": "virtual private network", "vr": "virtual reality", "wan": "wide area network", "wanna": "want to", "wasnt": "was not", "well": "we will", "were": "we are", "werent": "were not", "weve": "we have", "wfh": "work from home", "whats": "what is", "whens": "when is", "wheres": "where is", "wip": "work in progress", "wont": "will not", "woulda": "would have", "wtf": "what the f***", "wth": "what the heck", "xml": "extensible markup language", "yaml": "yaml ain't markup language", "yolo": "you only live once", "youll": "you will", "youre": "you are", "youve": "you have", "ytd": "year to date"} as const;

// ============================================
// Server/API Constants
// ============================================
export const ServerConstants = {
  DEFAULT_HOST: '127.0.0.1',
  DEFAULT_PORT: 8765,
  DEFAULT_LOG_LEVEL: 'INFO' as const,
} as const;

// ============================================
// Live Mode Profiles
// ============================================
export const LIVE_MODE_PROFILES = {"ultra": {"chunk_seconds": 0.1, "overlap_seconds": 0.02}, "realtime": {"chunk_seconds": 0.2, "overlap_seconds": 0.04}, "low_latency": {"chunk_seconds": 0.5, "overlap_seconds": 0.1}, "balanced": {"chunk_seconds": 1.0, "overlap_seconds": 0.2}, "high_accuracy": {"chunk_seconds": 2.0, "overlap_seconds": 0.4}} as const;
export type LiveModeProfile = keyof typeof LIVE_MODE_PROFILES;

// ============================================
// Fast Chunker Constants
// ============================================
export const FastChunkerConstants = {
  DEFAULT_BASE_CHUNK_MS: 200.0,
  DEFAULT_OVERLAP_MS: 50.0,
  DEFAULT_MIN_CHUNK_MS: 100.0,
  DEFAULT_MAX_CHUNK_MS: 400.0,
  DEFAULT_VAD_THRESHOLD_DB: -35.0,
  DEFAULT_VAD_HYSTERESIS_MS: 100.0,
  HIGH_SPEECH_DENSITY_THRESHOLD: 0.7,
  LOW_SPEECH_DENSITY_THRESHOLD: 0.2,
  ADAPTIVE_SIZE_HIGH_MULTIPLIER: 0.75,
  ADAPTIVE_SIZE_LOW_MULTIPLIER: 1.25,
  BUFFER_CAPACITY_SECONDS: 2.0,
  SPEECH_DENSITY_WINDOW_SIZE: 10,
  SPEECH_DENSITY_MIN_SAMPLES: 3,
  DEFAULT_MAX_QUEUE_SIZE: 100,
} as const;

// ============================================
// Audio Capture Constants
// ============================================
export const AudioCaptureConstants = {
  MAX_CONSECUTIVE_ERRORS: 5,
  STATS_LOG_INTERVAL_SECONDS: 2.0,
  QUEUE_PUT_TIMEOUT_SECONDS: 0.2,
  READ_TIMEOUT_SECONDS: 0.25,
  SLOW_CHUNK_PROCESSING_THRESHOLD_MS: 100.0,
} as const;

// ============================================
// Health Monitoring Constants
// ============================================
export const HealthConstants = {
  LOOP_STATS_INTERVAL_SECONDS: 1.0,
  HEALTH_EMIT_INTERVAL_SECONDS: 0.1,
  LOOP_LOG_INTERVAL_SECONDS: 5.0,
} as const;

// ============================================
// Auto-optimization Constants
// ============================================
export const AutoOptimizationConstants = {
  DEFAULT_ENABLED: true,
  DEFAULT_MODE: 'balanced' as const,
} as const;

export const VALID_OPTIMIZATION_MODES = ['maximum', 'balanced', 'speed', 'low_memory'] as const;

// ============================================
// Refiner Constants
// ============================================
export const RefinerConstants = {
  DEFAULT_MODEL_ID: 'qwen2.5-3b-instruct',
  DEFAULT_ENGINE_PREFERENCE: 'llamacpp' as const,
  DEFAULT_REFINEMENT_MODE: 'strict' as const,
  DEFAULT_REFINEMENT_PROFILE: 'clean_dictation' as const,
} as const;
export const VALID_REFINER_ENGINES = ["llamacpp", "lm_studio", "ollama"] as const;
export const VALID_REFINEMENT_MODES = ['off', 'strict', 'polished'] as const;
export const VALID_REFINEMENT_PROFILES = ["clean_dictation", "code_logs", "professional", "raw", "student_notes"] as const;

// ============================================
// GPU Fallback Keywords
// ============================================
export const GPU_FALLBACK_KEYWORDS = ["cublas", "cuda", "cudnn", "gpu", "out of memory", "curand", "cusolver", "cusparse", "nccl", "thrust", "device-side assert", "an illegal memory access", "cuda error", "no kernel image", "nvidia"] as const;

// ============================================
// Settings Validation Bounds
// ============================================
export const SettingsBounds = {
  SESSION_TITLE_MIN_LENGTH: 1,
  SESSION_TITLE_MAX_LENGTH: 100,
  AUTO_SAVE_INTERVAL_MIN: 10,
  AUTO_SAVE_INTERVAL_MAX: 300,
  CHUNK_DURATION_MIN: 0.5,
  CHUNK_DURATION_MAX: 5.0,
  OVERLAP_RATIO_MIN: 0,
  OVERLAP_RATIO_MAX: 0.5,
  CONFIDENCE_THRESHOLD_MIN: 0,
  CONFIDENCE_THRESHOLD_MAX: 1,
  MIN_SEGMENT_LENGTH_MIN: 0.1,
  MIN_SEGMENT_LENGTH_MAX: 2.0,
  MAX_WORKERS_MIN: 1,
  MAX_WORKERS_MAX: 16,
  BEAM_SIZE_MIN: 1,
  BEAM_SIZE_MAX: 20,
  BEST_OF_MIN: 1,
  BEST_OF_MAX: 20,
  PATIENCE_MIN: 0.1,
  PATIENCE_MAX: 5.0,
  TEMPERATURE_MIN: 0,
  TEMPERATURE_MAX: 1,
  VAD_THRESHOLD_MIN: -60,
  VAD_THRESHOLD_MAX: -20,
  MAX_LOG_FILES_MIN: 1,
  MAX_LOG_FILES_MAX: 100,
} as const;

// ============================================
// Fake/Not Implemented Settings
// ============================================
export const FAKE_SETTINGS = new Set([
  'autoGainControl',
  'backend',
  'coach_show_live_hints',
  'echoCancellation',
  'experimentalGpuAccel',
  'experimentalStem',
  'max_workers',
  'minimizeToTray',
  'noiseFiltering',
  'patience',
  'preload_model',
  'showNotifications',
  'startupWithSystem',
  'use_parallel_processing',
]);
