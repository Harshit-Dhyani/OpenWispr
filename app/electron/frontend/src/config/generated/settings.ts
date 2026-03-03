// Auto-generated from app/config/settings.py
// Do not edit manually - run `python app/config/generate_ts.py` to regenerate

// ============================================
// Setting Definition Types
// ============================================
export type SettingType = 'string' | 'number' | 'boolean' | 'enum' | 'range';

export interface SettingDefinition {
  name: string;
  category: string;
  type: SettingType;
  default: unknown;
  label: string;
  description: string;
  options?: (string | number)[];
  min?: number;
  max?: number;
  step?: number;
  suffix?: string;
  isFake: boolean;
  isAdvanced: boolean;
}

// ============================================
// Settings Registry - Single Source of Truth
// ============================================
export const SETTINGS_REGISTRY: Record<string, SettingDefinition> = {
  audio_backend: {
    name: 'audio_backend',
    category: 'audio',
    type: 'enum',
    default: 'auto',
    label: 'Audio Backend',
    description: 'Low-level Windows capture backend',
    options: ['auto', 'pyaudio', 'soundcard'],
    isFake: false,
    isAdvanced: false,
  },
  autoGainControl: {
    name: 'autoGainControl',
    category: 'audio',
    type: 'boolean',
    default: true,
    label: 'Auto Gain Control',
    description: 'Automatically adjust input volume',
    isFake: true,
    isAdvanced: false,
  },
  autoSaveInterval: {
    name: 'autoSaveInterval',
    category: 'general',
    type: 'range',
    default: 30,
    label: 'Auto-save Interval',
    description: 'How often to save session progress (seconds)',
    min: 10,
    max: 300,
    step: 10,
    suffix: 's',
    isFake: false,
    isAdvanced: false,
  },
  auto_inject: {
    name: 'auto_inject',
    category: 'hotkey',
    type: 'boolean',
    default: true,
    label: 'Auto-inject Text',
    description: 'Type transcription into active window',
    isFake: false,
    isAdvanced: false,
  },
  backend: {
    name: 'backend',
    category: 'audio',
    type: 'enum',
    default: 'auto',
    label: 'Audio Backend',
    description: 'Low-level Windows capture backend',
    options: ['auto', 'pyaudio', 'soundcard'],
    isFake: false,
    isAdvanced: false,
  },
  beam_size: {
    name: 'beam_size',
    category: 'transcription',
    type: 'number',
    default: 5,
    label: 'Beam Size',
    description: 'Beam search width',
    min: 1,
    max: 20,
    isFake: false,
    isAdvanced: false,
  },
  best_of: {
    name: 'best_of',
    category: 'transcription',
    type: 'number',
    default: 5,
    label: 'Best Of',
    description: 'Number of candidates to consider',
    min: 1,
    max: 20,
    isFake: false,
    isAdvanced: false,
  },
  captureMode: {
    name: 'captureMode',
    category: 'audio',
    type: 'enum',
    default: 'microphone',
    label: 'Capture Mode',
    description: 'Choose between microphone dictation and system-audio capture',
    options: ['system', 'microphone'],
    isFake: false,
    isAdvanced: false,
  },
  chunk_duration: {
    name: 'chunk_duration',
    category: 'transcription',
    type: 'range',
    default: 1.6,
    label: 'Chunk Duration',
    description: 'Audio chunk size in seconds',
    min: 0.5,
    max: 5.0,
    step: 0.1,
    suffix: 's',
    isFake: false,
    isAdvanced: false,
  },
  cleanup_instructions: {
    name: 'cleanup_instructions',
    category: 'refiner',
    type: 'string',
    default: '',
    label: 'Cleanup Instructions',
    description: 'Optional additional instructions for the final refiner pass',
    isFake: false,
    isAdvanced: false,
  },
  compute_type: {
    name: 'compute_type',
    category: 'transcription',
    type: 'enum',
    default: 'float16',
    label: 'Compute Type',
    description: 'Precision mode - float16 for quality, int8 for speed',
    options: ['float16', 'int8', 'int8_float16'],
    isFake: false,
    isAdvanced: false,
  },
  confidence_threshold: {
    name: 'confidence_threshold',
    category: 'transcription',
    type: 'range',
    default: 0.6,
    label: 'Confidence Threshold',
    description: 'Minimum confidence for transcript segments',
    min: 0,
    max: 1,
    step: 0.05,
    isFake: false,
    isAdvanced: false,
  },
  copy_to_clipboard: {
    name: 'copy_to_clipboard',
    category: 'hotkey',
    type: 'boolean',
    default: true,
    label: 'Copy to Clipboard',
    description: 'Automatically copy transcription',
    isFake: false,
    isAdvanced: false,
  },
  debugMode: {
    name: 'debugMode',
    category: 'advanced',
    type: 'boolean',
    default: false,
    label: 'Debug Mode',
    description: 'Enable verbose logging and diagnostics',
    isFake: false,
    isAdvanced: false,
  },
  defaultDeviceId: {
    name: 'defaultDeviceId',
    category: 'audio',
    type: 'string',
    default: 'default',
    label: 'Default Audio Device',
    description: 'Primary device for the selected capture mode',
    isFake: false,
    isAdvanced: false,
  },
  defaultLanguage: {
    name: 'defaultLanguage',
    category: 'general',
    type: 'string',
    default: 'auto',
    label: 'Default Language',
    description: 'Primary language for transcription',
    isFake: false,
    isAdvanced: false,
  },
  defaultSessionTitle: {
    name: 'defaultSessionTitle',
    category: 'general',
    type: 'string',
    default: 'New Session',
    label: 'Default Session Title',
    description: 'Default title for new transcription sessions',
    isFake: false,
    isAdvanced: false,
  },
  default_asr_model_id: {
    name: 'default_asr_model_id',
    category: 'transcription',
    type: 'string',
    default: 'whisper-medium',
    label: 'Default ASR Model ID',
    description: 'Catalog ID for the default ASR model',
    isFake: false,
    isAdvanced: false,
  },
  default_capture_source: {
    name: 'default_capture_source',
    category: 'audio',
    type: 'enum',
    default: 'microphone',
    label: 'Default Capture Source',
    description: 'Capture source selected when the app starts and for hotkey dictation',
    options: ['system', 'microphone'],
    isFake: false,
    isAdvanced: false,
  },
  device_id: {
    name: 'device_id',
    category: 'hotkey',
    type: 'string',
    default: 'default',
    label: 'Dictation Microphone',
    description: 'Microphone used for quick dictation',
    isFake: false,
    isAdvanced: false,
  },
  echoCancellation: {
    name: 'echoCancellation',
    category: 'audio',
    type: 'boolean',
    default: true,
    label: 'Echo Cancellation',
    description: 'Remove echo from speakers',
    isFake: true,
    isAdvanced: false,
  },
  enableMetrics: {
    name: 'enableMetrics',
    category: 'advanced',
    type: 'boolean',
    default: true,
    label: 'Enable Metrics',
    description: 'Collect and report performance metrics',
    isFake: false,
    isAdvanced: false,
  },
  enable_filler_filter: {
    name: 'enable_filler_filter',
    category: 'transcription',
    type: 'boolean',
    default: true,
    label: 'Filter Filler Words',
    description: 'Remove um, uh, etc.',
    isFake: false,
    isAdvanced: false,
  },
  enable_hallucination_filter: {
    name: 'enable_hallucination_filter',
    category: 'transcription',
    type: 'boolean',
    default: true,
    label: 'Filter Hallucinations',
    description: 'Remove likely incorrect segments',
    isFake: false,
    isAdvanced: false,
  },
  enabled: {
    name: 'enabled',
    category: 'hotkey',
    type: 'boolean',
    default: false,
    label: 'Enable Global Hotkey',
    description: 'Activate transcription from anywhere',
    isFake: false,
    isAdvanced: false,
  },
  engine_preference: {
    name: 'engine_preference',
    category: 'refiner',
    type: 'enum',
    default: 'llamacpp',
    label: 'Engine Preference',
    description: 'Preferred LLM inference engine',
    options: ['llamacpp', 'ollama'],
    isFake: false,
    isAdvanced: false,
  },
  experimentalGpuAccel: {
    name: 'experimentalGpuAccel',
    category: 'advanced',
    type: 'boolean',
    default: true,
    label: 'GPU Acceleration',
    description: 'Use GPU for pre-processing when available',
    isFake: true,
    isAdvanced: false,
  },
  experimentalStem: {
    name: 'experimentalStem',
    category: 'advanced',
    type: 'boolean',
    default: false,
    label: 'Enhanced STEM Detection',
    description: 'Advanced formula and equation recognition',
    isFake: true,
    isAdvanced: false,
  },
  exportDirectory: {
    name: 'exportDirectory',
    category: 'general',
    type: 'string',
    default: '',
    label: 'Export Directory',
    description: 'Default location for exported transcripts',
    isFake: false,
    isAdvanced: false,
  },
  finish_mode_default: {
    name: 'finish_mode_default',
    category: 'hotkey',
    type: 'enum',
    default: 'finish_and_paste',
    label: 'Default Finish Action',
    description: 'What happens when dictation stops from the hotkey toggle',
    options: ['finish', 'finish_and_paste'],
    isFake: false,
    isAdvanced: false,
  },
  floating_window_position: {
    name: 'floating_window_position',
    category: 'hotkey',
    type: 'enum',
    default: 'bottom-right',
    label: 'Floating Window Position',
    description: 'Where to show the transcription overlay',
    options: ['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center'],
    isFake: false,
    isAdvanced: false,
  },
  hold_mode: {
    name: 'hold_mode',
    category: 'hotkey',
    type: 'boolean',
    default: false,
    label: 'Hold Mode',
    description: 'Record while holding the hotkey',
    isFake: false,
    isAdvanced: false,
  },
  hotkey_optimized: {
    name: 'hotkey_optimized',
    category: 'transcription',
    type: 'boolean',
    default: false,
    label: 'Hotkey Optimized',
    description: 'Optimize for quick hotkey-triggered sessions',
    isFake: false,
    isAdvanced: false,
  },
  key_combination: {
    name: 'key_combination',
    category: 'hotkey',
    type: 'string',
    default: 'Ctrl+Shift+T',
    label: 'Key Combination',
    description: 'Press the button to record a new hotkey',
    isFake: false,
    isAdvanced: false,
  },
  language: {
    name: 'language',
    category: 'hotkey',
    type: 'string',
    default: 'auto',
    label: 'Dictation Language',
    description: 'Default language for hotkey dictation',
    isFake: false,
    isAdvanced: false,
  },
  logLevel: {
    name: 'logLevel',
    category: 'advanced',
    type: 'enum',
    default: 'INFO',
    label: 'Log Level',
    description: 'Minimum severity for log messages',
    options: ['DEBUG', 'INFO', 'WARN', 'ERROR'],
    isFake: false,
    isAdvanced: false,
  },
  maxLogFiles: {
    name: 'maxLogFiles',
    category: 'advanced',
    type: 'number',
    default: 10,
    label: 'Max Log Files',
    description: 'Number of log files to retain',
    min: 1,
    max: 100,
    isFake: false,
    isAdvanced: false,
  },
  max_workers: {
    name: 'max_workers',
    category: 'transcription',
    type: 'range',
    default: 4,
    label: 'Max Workers',
    description: 'Number of parallel processing workers',
    min: 1,
    max: 16,
    step: 1,
    isFake: true,
    isAdvanced: false,
  },
  microphone_asr_model_id: {
    name: 'microphone_asr_model_id',
    category: 'transcription',
    type: 'string',
    default: 'whisper-medium',
    label: 'Microphone ASR Model ID',
    description: 'Catalog ID for the default microphone transcription model',
    isFake: false,
    isAdvanced: false,
  },
  min_segment_length: {
    name: 'min_segment_length',
    category: 'transcription',
    type: 'range',
    default: 0.5,
    label: 'Min Segment Length',
    description: 'Minimum duration for transcript segments',
    min: 0.1,
    max: 2.0,
    step: 0.1,
    suffix: 's',
    isFake: false,
    isAdvanced: false,
  },
  minimizeToTray: {
    name: 'minimizeToTray',
    category: 'general',
    type: 'boolean',
    default: true,
    label: 'Minimize to Tray',
    description: 'Keep running in system tray when closed',
    isFake: true,
    isAdvanced: false,
  },
  model_name: {
    name: 'model_name',
    category: 'transcription',
    type: 'enum',
    default: 'medium',
    label: 'Model',
    description: 'Whisper model size - larger is more accurate but slower',
    options: ['tiny', 'base', 'small', 'medium', 'large-v3'],
    isFake: false,
    isAdvanced: false,
  },
  noiseFiltering: {
    name: 'noiseFiltering',
    category: 'audio',
    type: 'boolean',
    default: true,
    label: 'Noise Filtering',
    description: 'Reduce background noise',
    isFake: true,
    isAdvanced: false,
  },
  overlap_ratio: {
    name: 'overlap_ratio',
    category: 'transcription',
    type: 'range',
    default: 0.19999999999999998,
    label: 'Overlap Ratio',
    description: 'Audio overlap between chunks',
    min: 0,
    max: 0.5,
    step: 0.05,
    isFake: false,
    isAdvanced: false,
  },
  patience: {
    name: 'patience',
    category: 'transcription',
    type: 'number',
    default: 1.0,
    label: 'Patience',
    description: 'Beam search patience factor',
    min: 0.1,
    max: 5.0,
    step: 0.1,
    isFake: true,
    isAdvanced: false,
  },
  preload_model: {
    name: 'preload_model',
    category: 'transcription',
    type: 'boolean',
    default: true,
    label: 'Preload Model',
    description: 'Keep model loaded in memory',
    isFake: true,
    isAdvanced: false,
  },
  record_on_start: {
    name: 'record_on_start',
    category: 'hotkey',
    type: 'boolean',
    default: false,
    label: 'Record on Start',
    description: 'Begin recording when hotkey is activated',
    isFake: false,
    isAdvanced: false,
  },
  refinement_mode: {
    name: 'refinement_mode',
    category: 'transcription',
    type: 'enum',
    default: 'off',
    label: 'Refinement Mode',
    description: 'Post-processing mode for transcript refinement',
    options: ['off', 'strict', 'polished'],
    isFake: false,
    isAdvanced: false,
  },
  runtime_enabled: {
    name: 'runtime_enabled',
    category: 'refiner',
    type: 'boolean',
    default: false,
    label: 'Runtime Enabled',
    description: 'Enable runtime LLM refinement',
    isFake: false,
    isAdvanced: false,
  },
  sampleRate: {
    name: 'sampleRate',
    category: 'audio',
    type: 'enum',
    default: 16000,
    label: 'Sample Rate',
    description: 'Audio sample rate - 16kHz recommended for Whisper',
    options: [8000, 16000, 22050, 44100, 48000],
    isFake: false,
    isAdvanced: false,
  },
  selected_model_id: {
    name: 'selected_model_id',
    category: 'refiner',
    type: 'string',
    default: 'qwen2.5-3b-instruct',
    label: 'Selected Model ID',
    description: 'LLM model for transcript refinement',
    isFake: false,
    isAdvanced: false,
  },
  showNotifications: {
    name: 'showNotifications',
    category: 'general',
    type: 'boolean',
    default: true,
    label: 'Show Notifications',
    description: 'Display desktop notifications for events',
    isFake: true,
    isAdvanced: false,
  },
  show_floating_window: {
    name: 'show_floating_window',
    category: 'hotkey',
    type: 'boolean',
    default: true,
    label: 'Show Floating Window',
    description: 'Display overlay during transcription',
    isFake: false,
    isAdvanced: false,
  },
  startupWithSystem: {
    name: 'startupWithSystem',
    category: 'general',
    type: 'boolean',
    default: false,
    label: 'Start with System',
    description: 'Launch automatically on Windows startup',
    isFake: true,
    isAdvanced: false,
  },
  stop_on_release: {
    name: 'stop_on_release',
    category: 'hotkey',
    type: 'boolean',
    default: false,
    label: 'Stop on Release',
    description: 'End recording when hotkey is released',
    isFake: false,
    isAdvanced: false,
  },
  system_asr_model_id: {
    name: 'system_asr_model_id',
    category: 'transcription',
    type: 'string',
    default: 'whisper-medium',
    label: 'System Audio ASR Model ID',
    description: 'Catalog ID for the default system-audio transcription model',
    isFake: false,
    isAdvanced: false,
  },
  temperature: {
    name: 'temperature',
    category: 'transcription',
    type: 'range',
    default: 0.0,
    label: 'Temperature',
    description: 'Sampling temperature',
    min: 0,
    max: 1,
    step: 0.1,
    isFake: false,
    isAdvanced: false,
  },
  theme: {
    name: 'theme',
    category: 'general',
    type: 'enum',
    default: 'light',
    label: 'Theme',
    description: 'Application color theme',
    options: ['light', 'dark', 'cyber', 'dracula'],
    isFake: false,
    isAdvanced: false,
  },
  use_parallel_processing: {
    name: 'use_parallel_processing',
    category: 'transcription',
    type: 'boolean',
    default: true,
    label: 'Parallel Processing',
    description: 'Use multiple workers for faster transcription',
    isFake: true,
    isAdvanced: false,
  },
  vadEnabled: {
    name: 'vadEnabled',
    category: 'audio',
    type: 'boolean',
    default: true,
    label: 'Enable VAD',
    description: 'Voice Activity Detection (audio capture)',
    isFake: false,
    isAdvanced: false,
  },
  vadThresholdDb: {
    name: 'vadThresholdDb',
    category: 'audio',
    type: 'range',
    default: -40.0,
    label: 'VAD Threshold',
    description: 'Energy threshold for speech detection',
    min: -60,
    max: -20,
    step: 1,
    suffix: 'dB',
    isFake: false,
    isAdvanced: false,
  },
  vad_enabled: {
    name: 'vad_enabled',
    category: 'transcription',
    type: 'boolean',
    default: true,
    label: 'Enable VAD',
    description: 'Voice Activity Detection',
    isFake: false,
    isAdvanced: false,
  },
  vad_min_silence_ms: {
    name: 'vad_min_silence_ms',
    category: 'transcription',
    type: 'range',
    default: 200,
    label: 'VAD Min Silence',
    description: 'Minimum silence duration to consider end of speech',
    min: 0,
    max: 5000,
    step: 50,
    suffix: 'ms',
    isFake: false,
    isAdvanced: false,
  },
  vad_speech_pad_ms: {
    name: 'vad_speech_pad_ms',
    category: 'transcription',
    type: 'range',
    default: 200,
    label: 'VAD Speech Padding',
    description: 'Padding added to speech segments',
    min: 0,
    max: 1000,
    step: 50,
    suffix: 'ms',
    isFake: false,
    isAdvanced: false,
  },
  vad_threshold_db: {
    name: 'vad_threshold_db',
    category: 'transcription',
    type: 'range',
    default: -40.0,
    label: 'VAD Threshold',
    description: 'Energy threshold for speech detection',
    min: -60,
    max: -20,
    step: 1,
    suffix: 'dB',
    isFake: false,
    isAdvanced: false,
  },
};

// ============================================
// Registry Access Functions
// ============================================

export function getSetting(name: string): SettingDefinition {
  const defn = SETTINGS_REGISTRY[name];
  if (!defn) {
    throw new Error(`Unknown setting: ${name}`);
  }
  return defn;
}

export function getSettingsByCategory(category: string): Record<string, SettingDefinition> {
  return Object.fromEntries(
    Object.entries(SETTINGS_REGISTRY).filter(([_, defn]) => defn.category === category)
  );
}

export function getAllCategories(): string[] {
  return [...new Set(Object.values(SETTINGS_REGISTRY).map(d => d.category))];
}

export function getSettingDefault(name: string): unknown {
  return getSetting(name).default;
}

export function getCategoryDefaults(category: string): Record<string, unknown> {
  const settings = getSettingsByCategory(category);
  return Object.fromEntries(
    Object.entries(settings).map(([name, defn]) => [name, defn.default])
  );
}

export function isFakeSetting(name: string): boolean;
export function isFakeSetting(_category: string | null, name: string): boolean;
export function isFakeSetting(arg1: string | null, arg2?: string): boolean {
  const name = arg2 ?? arg1 as string;
  const defn = SETTINGS_REGISTRY[name];
  return defn?.isFake ?? false;
}

export function getFakeSettings(): Record<string, string[]> {
  const result: Record<string, string[]> = {};
  Object.values(SETTINGS_REGISTRY).forEach(defn => {
    if (defn.isFake) {
      if (!result[defn.category]) {
        result[defn.category] = [];
      }
      result[defn.category].push(defn.name);
    }
  });
  return result;
}

// ============================================
// Validation Functions
// ============================================

export interface ValidationResult {
  isValid: boolean;
  error?: string;
}

export function validateSetting(name: string, value: unknown): ValidationResult {
  const defn = SETTINGS_REGISTRY[name];
  if (!defn) {
    return { isValid: false, error: `Unknown setting: ${name}` };
  }

  switch (defn.type) {
    case 'boolean':
      if (typeof value !== 'boolean') {
        return { isValid: false, error: `Expected boolean, got ${typeof value}` };
      }
      break;
    case 'string':
      if (typeof value !== 'string') {
        return { isValid: false, error: `Expected string, got ${typeof value}` };
      }
      break;
    case 'number':
    case 'range':
      if (typeof value !== 'number') {
        return { isValid: false, error: `Expected number, got ${typeof value}` };
      }
      if (defn.min !== undefined && value < defn.min) {
        return { isValid: false, error: `Value must be >= ${defn.min}` };
      }
      if (defn.max !== undefined && value > defn.max) {
        return { isValid: false, error: `Value must be <= ${defn.max}` };
      }
      break;
    case 'enum':
      if (defn.options && !defn.options.includes(value as string | number)) {
        return { isValid: false, error: `Invalid value. Must be one of: ${defn.options.join(', ')}` };
      }
      break;
  }

  return { isValid: true };
}

// ============================================
// Settings Version
// ============================================
export const CURRENT_SETTINGS_VERSION = 3;

export function getSettingsVersion(): number {
  return CURRENT_SETTINGS_VERSION;
}
