/** Centralized UI text constants for Transcripta frontend */

// ============================================
// Model Names
// ============================================
export const MODEL_NAMES = {
  tiny: 'Tiny (Fastest, Lowest Quality)',
  base: 'Base (Fast, Good Quality)',
  small: 'Small (Balanced)',
  medium: 'Medium (Best Quality, Slower)',
  'large-v3': 'Large v3 (Highest Quality, Slowest)',
  turbo: 'Turbo (Fast, High Quality)',
} as const;

/** Short model names for compact UI */
export const MODEL_NAMES_SHORT = {
  tiny: 'Tiny',
  base: 'Base',
  small: 'Small',
  medium: 'Medium',
  'large-v3': 'Large v3',
  turbo: 'Turbo',
} as const;

// ============================================
// Live Mode Labels
// ============================================
export const LIVE_MODE_LABELS = {
  ultra: 'Ultra (100ms chunks)',
  realtime: 'Real-Time (Ultra Low Latency)',
  low_latency: 'Low Latency',
  balanced: 'Balanced',
  high_accuracy: 'High Accuracy',
} as const;

export const LIVE_MODE_DESCRIPTIONS = {
  ultra: 'Fastest response with smallest chunks. May reduce accuracy.',
  realtime: 'Ultra low latency for real-time applications. 200ms chunks.',
  low_latency: 'Fast transcription with good accuracy. 500ms chunks.',
  balanced: 'Best balance for most use cases. 1 second chunks.',
  high_accuracy: 'Maximum accuracy with larger chunks. 2 second chunks.',
} as const;

// ============================================
// Setting Category Labels
// ============================================
export const CATEGORY_LABELS = {
  general: 'General',
  transcription: 'Transcription',
  audio: 'Audio',
  hotkey: 'Hotkey',
  advanced: 'Advanced',
  refiner: 'Refiner',
} as const;

// ============================================
// Setting Labels
// ============================================
export const SETTING_LABELS = {
  // General
  defaultSessionTitle: 'Default Session Title',
  defaultLanguage: 'Default Language',
  exportDirectory: 'Export Directory',
  autoSaveInterval: 'Auto-Save Interval',
  theme: 'Theme',
  showNotifications: 'Show Notifications',
  minimizeToTray: 'Minimize to Tray',
  startupWithSystem: 'Start with System',
  
  // Transcription
  model_name: 'Model',
  default_asr_model_id: 'ASR Model ID',
  compute_type: 'Compute Type',
  chunk_duration: 'Chunk Duration',
  overlap_ratio: 'Overlap Ratio',
  live_mode: 'Live Mode',
  vad_enabled: 'Enable VAD',
  vad_threshold_db: 'VAD Threshold',
  vad_min_silence_ms: 'VAD Min Silence',
  vad_speech_pad_ms: 'VAD Speech Padding',
  confidence_threshold: 'Confidence Threshold',
  enable_filler_filter: 'Filter Filler Words',
  enable_hallucination_filter: 'Filter Hallucinations',
  min_segment_length: 'Min Segment Length',
  max_workers: 'Max Workers',
  use_parallel_processing: 'Parallel Processing',
  preload_model: 'Preload Model',
  hotkey_optimized: 'Hotkey Optimized',
  beam_size: 'Beam Size',
  best_of: 'Best Of',
  patience: 'Patience',
  temperature: 'Temperature',
  refinement_mode: 'Refinement Mode',
  
  // Audio
  captureMode: 'Capture Mode',
  defaultDeviceId: 'Default Audio Device',
  audio_backend: 'Audio Backend',
  sampleRate: 'Sample Rate',
  noiseFiltering: 'Noise Filtering',
  echoCancellation: 'Echo Cancellation',
  autoGainControl: 'Auto Gain Control',
  
  // Hotkey
  enabled: 'Enable Global Hotkey',
  key_combination: 'Key Combination',
  hold_mode: 'Hold Mode',
  auto_inject: 'Auto-inject Text',
  language: 'Dictation Language',
  device_id: 'Dictation Microphone',
  finish_mode_default: 'Default Finish Action',
  show_floating_window: 'Show Floating Window',
  floating_window_position: 'Floating Window Position',
  record_on_start: 'Record on Start',
  stop_on_release: 'Stop on Release',
  copy_to_clipboard: 'Copy to Clipboard',
  
  // Advanced
  debugMode: 'Debug Mode',
  logLevel: 'Log Level',
  enableMetrics: 'Enable Metrics',
  maxLogFiles: 'Max Log Files',
  experimentalStem: 'Enhanced STEM Detection',
  experimentalGpuAccel: 'GPU Acceleration',
  
  // Refiner
  selected_model_id: 'Selected Model',
  runtime_enabled: 'Runtime Enabled',
  engine_preference: 'Engine Preference',
} as const;

// ============================================
// Setting Descriptions
// ============================================
export const SETTING_DESCRIPTIONS = {
  // General
  defaultSessionTitle: 'Default name for new transcription sessions',
  defaultLanguage: 'Primary language for transcription',
  exportDirectory: 'Default location for exported transcripts',
  autoSaveInterval: 'How often to save session progress',
  theme: 'Application color theme',
  showNotifications: 'Display desktop notifications for events',
  minimizeToTray: 'Keep running in system tray when closed',
  startupWithSystem: 'Launch automatically on Windows startup',
  
  // Transcription
  model_name: 'Whisper model size - larger is more accurate but slower',
  compute_type: 'Precision mode - float16 for quality, int8 for speed',
  chunk_duration: 'Audio chunk size in seconds',
  overlap_ratio: 'Audio overlap between chunks',
  vad_enabled: 'Voice Activity Detection - only transcribe when speech is detected',
  vad_threshold_db: 'Energy threshold for speech detection',
  vad_min_silence_ms: 'Minimum silence duration to consider end of speech',
  vad_speech_pad_ms: 'Padding added to speech segments',
  confidence_threshold: 'Minimum confidence for transcript segments',
  enable_filler_filter: 'Remove um, uh, etc.',
  enable_hallucination_filter: 'Remove likely incorrect segments',
  min_segment_length: 'Minimum duration for transcript segments',
  max_workers: 'Number of parallel processing workers',
  use_parallel_processing: 'Use multiple workers for faster transcription',
  preload_model: 'Keep model loaded in memory',
  hotkey_optimized: 'Optimize for quick hotkey-triggered sessions',
  beam_size: 'Beam search width for decoding',
  best_of: 'Number of candidates to consider during sampling',
  patience: 'Beam search patience factor',
  temperature: 'Sampling temperature - higher = more random',
  refinement_mode: 'Level of LLM post-processing applied to transcripts',
  
  // Audio
  captureMode: 'Choose between microphone dictation and system-audio capture',
  defaultDeviceId: 'Primary device for the selected capture mode',
  audio_backend: 'Low-level Windows capture backend',
  sampleRate: 'Audio sample rate - 16kHz recommended for Whisper',
  noiseFiltering: 'Reduce background noise',
  echoCancellation: 'Remove echo from speakers',
  autoGainControl: 'Automatically adjust input volume',
  
  // Hotkey
  enabled: 'Activate transcription from anywhere using a hotkey',
  key_combination: 'Press the button to record a new hotkey',
  hold_mode: 'Record while holding the hotkey',
  auto_inject: 'Type transcription into active window',
  language: 'Default language for hotkey dictation',
  device_id: 'Microphone used for quick dictation',
  finish_mode_default: 'What happens when dictation stops from the hotkey toggle',
  show_floating_window: 'Display overlay during transcription',
  floating_window_position: 'Where to show the transcription overlay',
  record_on_start: 'Begin recording when hotkey is activated',
  stop_on_release: 'End recording when hotkey is released',
  copy_to_clipboard: 'Automatically copy transcription to clipboard',
  
  // Advanced
  debugMode: 'Enable verbose logging and diagnostics',
  logLevel: 'Minimum severity for log messages',
  enableMetrics: 'Collect and report performance metrics',
  maxLogFiles: 'Number of log files to retain',
  experimentalStem: 'Advanced formula and equation recognition',
  experimentalGpuAccel: 'Use GPU for pre-processing when available',
  
  // Refiner
  selected_model_id: 'LLM model for transcript refinement',
  runtime_enabled: 'Enable runtime LLM refinement',
  engine_preference: 'Preferred LLM inference engine',
} as const;

// ============================================
// Theme Labels
// ============================================
export const THEME_LABELS = {
  light: 'Light (Lawn)',
  dark: 'Dark (Night)',
  cyber: 'Cyberpunk',
  dracula: 'Dracula',
} as const;

// ============================================
// Compute Type Labels
// ============================================
export const COMPUTE_TYPE_LABELS = {
  float16: 'Float16 (Best Quality)',
  float32: 'Float32 (Maximum Quality)',
  int8: 'Int8 (Fast, Low VRAM)',
  int8_float16: 'Int8_Float16 (Balanced)',
} as const;

// ============================================
// Capture Mode Labels
// ============================================
export const CAPTURE_MODE_LABELS = {
  system: 'System Audio',
  microphone: 'Microphone',
} as const;

// ============================================
// Audio Backend Labels
// ============================================
export const AUDIO_BACKEND_LABELS = {
  auto: 'Auto (PyAudio first)',
  pyaudio: 'PyAudio WASAPI',
  soundcard: 'Soundcard (Legacy)',
} as const;

// ============================================
// Sample Rate Labels
// ============================================
export const SAMPLE_RATE_LABELS: Record<string, string> = {
  '8000': '8 kHz',
  '16000': '16 kHz (Recommended)',
  '22050': '22.05 kHz',
  '44100': '44.1 kHz',
  '48000': '48 kHz',
};

// ============================================
// Finish Action Labels
// ============================================
export const FINISH_ACTION_LABELS = {
  finish: 'Finish Only',
  finish_and_paste: 'Finish & Paste',
} as const;

// ============================================
// Floating Window Position Labels
// ============================================
export const FLOATING_POSITION_LABELS = {
  'top-left': 'Top Left',
  'top-right': 'Top Right',
  'bottom-left': 'Bottom Left',
  'bottom-right': 'Bottom Right',
  center: 'Center',
} as const;

// ============================================
// Log Level Labels
// ============================================
export const LOG_LEVEL_LABELS = {
  DEBUG: 'Debug (Most Verbose)',
  INFO: 'Info',
  WARN: 'Warning',
  ERROR: 'Error (Least Verbose)',
} as const;

// ============================================
// Optimization Preset Labels
// ============================================
export const OPTIMIZATION_PRESET_LABELS = {
  maximum: 'Maximum Quality',
  balanced: 'Balanced',
  fast: 'Maximum Speed',
  low_memory: 'Low Memory',
} as const;

export const PRESET_DESCRIPTIONS = {
  maximum: 'Best accuracy, needs 10GB+ GPU',
  balanced: 'Best balance for most systems',
  fast: 'Fastest transcription',
  low_memory: 'Fits in limited VRAM',
} as const;

// ============================================
// Refinement Mode Labels
// ============================================
export const REFINEMENT_MODE_LABELS = {
  off: 'Off (No refinement)',
  strict: 'Strict (Minor corrections)',
  polished: 'Polished (Full rewrite)',
} as const;

// ============================================
// Refiner Engine Labels
// ============================================
export const REFINER_ENGINE_LABELS = {
  llamacpp: 'Llama.cpp (Local)',
  ollama: 'Ollama (Local)',
} as const;

// ============================================
// Tab Labels
// ============================================
export const TAB_LABELS = {
  presets: 'Presets',
  manual: 'Manual',
  hotkey: 'Hotkey',
  general: 'General',
  transcription: 'Transcription',
  audio: 'Audio',
  advanced: 'Advanced',
} as const;

// ============================================
// Button Labels
// ============================================
export const BUTTON_LABELS = {
  apply: 'Apply',
  cancel: 'Cancel',
  close: 'Close',
  save: 'Save',
  reset: 'Reset',
  start: 'Start',
  stop: 'Stop',
  pause: 'Pause',
  resume: 'Resume',
  export: 'Export',
  import: 'Import',
  delete: 'Delete',
  edit: 'Edit',
  create: 'Create',
  refresh: 'Refresh',
  search: 'Search',
  clear: 'Clear',
  copy: 'Copy',
  paste: 'Paste',
  applyOptimizedSettings: 'Apply Optimized Settings',
  applyManualSettings: 'Apply Manual Settings',
  recommended: 'Recommended',
} as const;

// ============================================
// Status Labels
// ============================================
export const STATUS_LABELS = {
  idle: 'Idle',
  recording: 'Recording',
  processing: 'Processing',
  paused: 'Paused',
  error: 'Error',
  loading: 'Loading',
  initializing: 'Initializing',
  ready: 'Ready',
  stopping: 'Stopping',
  saving: 'Saving',
} as const;

// ============================================
// Section Headers
// ============================================
export const SECTION_HEADERS = {
  systemProfile: 'System Profile',
  optimizationResults: 'Optimization Results',
  modelSettings: 'Model Settings',
  audioPipeline: 'Audio Pipeline',
  qualityFiltering: 'Quality Filtering',
  performance: 'Performance',
  liveModes: 'Live Modes',
  advancedSettings: 'Advanced Settings',
  generalSettings: 'General Settings',
  transcriptionSettings: 'Transcription Settings',
  audioSettings: 'Audio Settings',
  hotkeySettings: 'Hotkey Settings',
} as const;

// ============================================
// Error Messages
// ============================================
export const ERROR_MESSAGES = {
  backend_unavailable: 'Cannot connect to backend. Please restart the application.',
  device_not_found: 'Selected audio device not found. Please check your microphone.',
  model_load_failed: 'Failed to load model. Check your GPU memory and try a smaller model.',
  invalid_settings: 'Invalid settings provided. Please check your configuration.',
  session_save_failed: 'Failed to save session. Check disk space and permissions.',
  export_failed: 'Failed to export transcript. Check the export directory.',
  hotkey_register_failed: 'Failed to register hotkey. It may be in use by another application.',
  audio_capture_failed: 'Audio capture failed. Check your audio device settings.',
  transcription_error: 'Transcription error occurred. Check logs for details.',
  network_error: 'Network error. Check your connection.',
  timeout_error: 'Operation timed out. Please try again.',
  unknown_error: 'An unknown error occurred. Please restart the application.',
  failed_to_load_settings: 'Failed to load settings',
  failed_to_load_profile: 'Failed to load system profile',
  failed_to_optimize: 'Failed to load optimized settings',
} as const;

// ============================================
// Tooltips
// ============================================
export const TOOLTIPS = {
  hotkey_record: 'Press this key combination to start/stop recording',
  vad_threshold: 'Lower values detect more quiet speech',
  chunk_duration: 'Smaller chunks = lower latency, larger = better accuracy',
  overlap_ratio: 'Higher overlap improves accuracy at boundaries but uses more resources',
  beam_size: 'Larger values improve accuracy but slow down transcription',
  temperature: 'Higher values make output more random, lower more deterministic',
  confidence_threshold: 'Segments below this confidence will be flagged for review',
  auto_save_interval: 'How often session data is saved to disk',
  tradeoffs: 'Trade-offs made for this optimization preset',
} as const;

// ============================================
// Unit Labels
// ============================================
export const UNIT_LABELS = {
  seconds: 's',
  milliseconds: 'ms',
  percentage: '%',
  decibels: 'dB',
  gigabytes: 'GB',
  megabytes: 'MB',
  hertz: 'Hz',
  kilohertz: 'kHz',
  cores: 'Cores',
} as const;

// ============================================
// Hardware Labels
// ============================================
export const HARDWARE_LABELS = {
  gpu: 'GPU',
  cpu: 'CPU',
  vram: 'VRAM',
  ram: 'RAM',
  storage: 'Storage',
  ssd: 'SSD',
  hdd: 'HDD',
  available: 'Available',
  not_available: 'Not Available',
  cores: 'Cores',
  free_space: 'Free Space',
} as const;

// ============================================
// Metric Labels
// ============================================
export const METRIC_LABELS = {
  quality_level: 'Quality Level',
  vram_usage: 'VRAM Usage',
  latency: 'Latency',
  tradeoffs: 'Trade-offs',
  processing_time: 'Processing Time',
  confidence: 'Confidence',
} as const;
