import { z } from 'zod';
import {
  AudioConstants,
  ModelConstants,
  PerformanceConstants,
  RefinerConstants,
  ServerConstants,
  SessionConstants,
  SettingsBounds,
  UIConstants,
  VADConstants,
  VALID_MODEL_NAMES,
  VALID_COMPUTE_TYPES,
  VALID_THEMES,
  VALID_LOG_LEVELS,
  VALID_REFINER_ENGINES,
  VALID_REFINEMENT_MODES,
  VALID_SAMPLE_RATES,
} from '../lib/constants';
import {
  SETTING_LABELS,
  SETTING_DESCRIPTIONS,
  THEME_LABELS,
  MODEL_NAMES_SHORT,
  COMPUTE_TYPE_LABELS,
  CAPTURE_MODE_LABELS,
  AUDIO_BACKEND_LABELS,
  SAMPLE_RATE_LABELS,
  FINISH_ACTION_LABELS,
  FLOATING_POSITION_LABELS,
  LOG_LEVEL_LABELS,
} from './text';
// Re-export from centralized settings registry for consistency
export {
  FAKE_SETTINGS,
  SETTINGS_REGISTRY,
  getSetting,
  getSettingsByCategory,
  getSettingDefault,
  getCategoryDefaults,
  isFakeSetting,
  getFakeSettings,
  validateSetting,
  CURRENT_SETTINGS_VERSION,
} from './settings';

// ============================================
// Settings Schema with Zod
// ============================================

// Version for migrations
export const SETTINGS_VERSION = UIConstants.SETTINGS_VERSION;

// ============================================
// General Settings Schema
// ============================================
export const generalSettingsSchema = z.object({
  defaultSessionTitle: z.string()
    .min(SettingsBounds.SESSION_TITLE_MIN_LENGTH)
    .max(SettingsBounds.SESSION_TITLE_MAX_LENGTH)
    .default(SessionConstants.DEFAULT_SESSION_TITLE),
  defaultLanguage: z.string().default(UIConstants.DEFAULT_LANGUAGE),
  exportDirectory: z.string().default(''),
  autoSaveInterval: z.number()
    .min(SettingsBounds.AUTO_SAVE_INTERVAL_MIN)
    .max(SettingsBounds.AUTO_SAVE_INTERVAL_MAX)
    .default(UIConstants.AUTO_SAVE_INTERVAL_SECONDS),
  showNotifications: z.boolean().default(true),
  minimizeToTray: z.boolean().default(true),
  startupWithSystem: z.boolean().default(false),
  theme: z.enum(VALID_THEMES).default(UIConstants.DEFAULT_THEME),
});

export type GeneralSettings = z.infer<typeof generalSettingsSchema>;

// ============================================
// Transcription Settings Schema
// ============================================
export const transcriptionSettingsSchema = z.object({
  model_name: z.enum(VALID_MODEL_NAMES).default(ModelConstants.DEFAULT_MODEL_NAME),
  default_asr_model_id: z.string().default('whisper-medium'),
  microphone_asr_model_id: z.string().default('whisper-medium'),
  system_asr_model_id: z.string().default('whisper-medium'),
  refinement_mode: z.enum(VALID_REFINEMENT_MODES).default(RefinerConstants.DEFAULT_REFINEMENT_MODE),
  refinement_profile: z.enum(['raw', 'clean_dictation', 'professional', 'student_notes', 'code_logs']).default('clean_dictation'),
  transcription_mode: z.enum(['dictation', 'literal', 'session_paragraph']).default('dictation'),
  compute_type: z.enum(VALID_COMPUTE_TYPES).default(ModelConstants.DEFAULT_COMPUTE_TYPE),
  chunk_duration: z.number()
    .min(SettingsBounds.CHUNK_DURATION_MIN)
    .max(SettingsBounds.CHUNK_DURATION_MAX)
    .default(AudioConstants.DEFAULT_CHUNK_SECONDS),
  overlap_ratio: z.number()
    .min(SettingsBounds.OVERLAP_RATIO_MIN)
    .max(SettingsBounds.OVERLAP_RATIO_MAX)
    .default(AudioConstants.DEFAULT_OVERLAP_SECONDS / AudioConstants.DEFAULT_CHUNK_SECONDS),
  vad_enabled: z.boolean().default(VADConstants.DEFAULT_FILTER_ENABLED),
  vad_threshold_db: z.number()
    .min(SettingsBounds.VAD_THRESHOLD_MIN)
    .max(SettingsBounds.VAD_THRESHOLD_MAX)
    .default(VADConstants.DEFAULT_THRESHOLD_DB),
  vad_min_silence_ms: z.number()
    .min(0)
    .max(5000)
    .default(200),
  vad_speech_pad_ms: z.number()
    .min(0)
    .max(1000)
    .default(200),
  confidence_threshold: z.number()
    .min(SettingsBounds.CONFIDENCE_THRESHOLD_MIN)
    .max(SettingsBounds.CONFIDENCE_THRESHOLD_MAX)
    .default(ModelConstants.DEFAULT_CONFIDENCE_THRESHOLD),
  enable_filler_filter: z.boolean().default(true),
  enable_hallucination_filter: z.boolean().default(true),
  min_segment_length: z.number()
    .min(SettingsBounds.MIN_SEGMENT_LENGTH_MIN)
    .max(SettingsBounds.MIN_SEGMENT_LENGTH_MAX)
    .default(ModelConstants.MIN_SEGMENT_LENGTH),
  max_workers: z.number()
    .min(SettingsBounds.MAX_WORKERS_MIN)
    .max(SettingsBounds.MAX_WORKERS_MAX)
    .default(PerformanceConstants.DEFAULT_MAX_WORKERS),
  use_parallel_processing: z.boolean().default(true),
  preload_model: z.boolean().default(true),
  hotkey_optimized: z.boolean().default(false),
  beam_size: z.number()
    .min(SettingsBounds.BEAM_SIZE_MIN)
    .max(SettingsBounds.BEAM_SIZE_MAX)
    .default(ModelConstants.DEFAULT_BEAM_SIZE),
  best_of: z.number()
    .min(SettingsBounds.BEST_OF_MIN)
    .max(SettingsBounds.BEST_OF_MAX)
    .default(ModelConstants.DEFAULT_BEST_OF),
  patience: z.number()
    .min(SettingsBounds.PATIENCE_MIN)
    .max(SettingsBounds.PATIENCE_MAX)
    .default(ModelConstants.DEFAULT_PATIENCE),
  temperature: z.number()
    .min(SettingsBounds.TEMPERATURE_MIN)
    .max(SettingsBounds.TEMPERATURE_MAX)
    .default(ModelConstants.DEFAULT_TEMPERATURE),
});

export type TranscriptionSettings = z.infer<typeof transcriptionSettingsSchema>;

export const refinerSettingsSchema = z.object({
  selected_model_id: z.string().default(RefinerConstants.DEFAULT_MODEL_ID),
  runtime_enabled: z.boolean().default(false),
  cleanup_instructions: z.string().default(''),
  engine_preference: z.enum(VALID_REFINER_ENGINES).default(RefinerConstants.DEFAULT_ENGINE_PREFERENCE),
});

export type RefinerSettings = z.infer<typeof refinerSettingsSchema>;

// ============================================
// Audio Settings Schema
// ============================================
export const audioSettingsSchema = z.object({
  captureMode: z.enum(['system', 'microphone']).default('microphone'),
  default_capture_source: z.enum(['system', 'microphone']).default('microphone'),
  defaultDeviceId: z.string().default(AudioConstants.DEFAULT_CAPTURE_DEVICE_ID),
  audio_backend: z.enum(['auto', 'pyaudio', 'soundcard']).default(AudioConstants.DEFAULT_BACKEND),
  sampleRate: z.coerce.number().refine(
    (val) => VALID_SAMPLE_RATES.includes(val as typeof VALID_SAMPLE_RATES[number]),
    { message: `Sample rate must be one of: ${VALID_SAMPLE_RATES.join(', ')}` }
  ).default(AudioConstants.DEFAULT_SAMPLE_RATE),
  noiseFiltering: z.boolean().default(true),
  echoCancellation: z.boolean().default(true),
  autoGainControl: z.boolean().default(true),
  mute_transcripta_audio_during_dictation: z.boolean().default(false),
});

export type AudioSettings = z.infer<typeof audioSettingsSchema>;

// ============================================
// Hotkey Settings Schema
// ============================================
export const hotkeySettingsSchema = z.object({
  enabled: z.boolean().default(false),
  key_combination: z.string().min(1).default(UIConstants.DEFAULT_HOTKEY),
  microphone_key_combination: z.string().min(1).default(UIConstants.DEFAULT_HOTKEY),
  system_key_combination: z.string().min(1).default('CommandOrControl+Shift+Y'),
  hold_mode: z.boolean().default(false),
  auto_inject: z.boolean().default(true),
  language: z.string().default(UIConstants.DEFAULT_LANGUAGE),
  capture_source: z.enum(['system', 'microphone']).default('microphone'),
  device_id: z.string().default(AudioConstants.DEFAULT_CAPTURE_DEVICE_ID),
  finish_mode_default: z.enum(['finish', 'finish_and_paste', 'cancel']).default('finish_and_paste'),
  enable_refiner_on_stop: z.boolean().default(false),
  save_debug_wav: z.boolean().default(false),
  show_floating_window: z.boolean().default(true),
  floating_window_position: z.enum(['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center']).default('bottom-right'),
  record_on_start: z.boolean().default(false),
  stop_on_release: z.boolean().default(false),
  copy_to_clipboard: z.boolean().default(true),
});

export type HotkeySettings = z.infer<typeof hotkeySettingsSchema>;

export const coachPromptOverridesSchema = z.object({
  tone: z.enum(['neutral', 'friendly', 'strict']).default('neutral'),
  aggressiveness: z.enum(['light', 'medium', 'strong']).default('light'),
  filler_removal: z.boolean().default(true),
  keep_slang: z.boolean().default(true),
  target_style: z.enum(['email', 'chat', 'formal', 'simple']).default('simple'),
});

export type CoachPromptOverrides = z.infer<typeof coachPromptOverridesSchema>;

export const coachPromptTemplateSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  version: z.number().int().min(1).default(1),
  system: z.string().min(1),
  user_template: z.string().min(1),
  enabled: z.boolean().default(true),
  built_in: z.boolean().default(false),
});

export type CoachPromptTemplate = z.infer<typeof coachPromptTemplateSchema>;

export const coachSettingsSchema = z.object({
  coach_enabled: z.boolean().default(true),
  coach_show_live_hints: z.boolean().default(false),
  coach_detail_level: z.enum(['compact', 'standard', 'deep']).default('compact'),
  copy_polished_by_default: z.boolean().default(true),
  show_diff_view: z.boolean().default(true),
  coach_template_id_mic: z.string().default('default_english_coach'),
  coach_template_id_system: z.string().default('default_english_coach'),
  coach_prompt_custom_enabled: z.boolean().default(false),
  coach_prompt_custom_text: z.string().default(''),
  coach_overrides: coachPromptOverridesSchema.default({
    tone: 'neutral',
    aggressiveness: 'light',
    filler_removal: true,
    keep_slang: true,
    target_style: 'simple',
  }),
  privacy_mode: z.enum(['local_only', 'allow_llm']).default('local_only'),
  show_floating_coach_result: z.boolean().default(true),
  coach_prompt_templates: z.array(coachPromptTemplateSchema).default([
    {
      id: 'default_english_coach',
      name: 'Default English Coach',
      version: 1,
      system:
        'You are an English writing coach for dictation transcripts.\nYou must preserve the speakers meaning and tone.\nYou must NOT add new facts.\nPrefer minimal edits.\nOutput MUST be valid JSON only, matching the schema exactly.',
      user_template:
        'Language mode: {language_mode}\nDetail level: {detail_level}\nOverrides JSON: {overrides_json}\n\nOriginal transcript:\n{original_text}\n\nTask:\n1) Produce "polished" that reads naturally (single paragraph unless clearly multiple).\n2) Provide "diff" operations aligned to the original string indices where possible. If exact indices are hard, provide approximate ranges but keep them consistent.\n3) Provide 2–5 short tips.\n4) Provide up to 5 mistakes with fixes and short explanations.\n5) Provide one short practice rewrite.\n\nReturn JSON with keys: original, polished, diff, tips, mistakes, practice, meta.',
      enabled: true,
      built_in: true,
    },
  ]),
});

export type CoachSettings = z.infer<typeof coachSettingsSchema>;

export const historySettingsSchema = z.object({
  retention_days: z.number().int().min(1).max(3650).default(30),
  persist_audio: z.boolean().default(true),
  allow_retry: z.boolean().default(true),
  default_analytics_range_days: z.union([z.literal('all'), z.number().int().min(1).max(3650)]).default(7),
});

export type HistorySettings = z.infer<typeof historySettingsSchema>;

export const dictionarySettingsSchema = z.object({
  dictionary_enabled: z.boolean().default(true),
});

export type DictionarySettings = z.infer<typeof dictionarySettingsSchema>;

export const snippetsSettingsSchema = z.object({
  snippets_enabled: z.boolean().default(true),
  snippets_quick_insert: z.boolean().default(false),
});

export type SnippetsSettings = z.infer<typeof snippetsSettingsSchema>;

export const styleSettingsSchema = z.object({
  style_default_profile: z.string().default('casual'),
  style_apply_enabled: z.boolean().default(true),
});

export type StyleSettings = z.infer<typeof styleSettingsSchema>;

// ============================================
// Advanced Settings Schema
// ============================================
export const advancedSettingsSchema = z.object({
  debugMode: z.boolean().default(false),
  logLevel: z.enum(VALID_LOG_LEVELS).default(ServerConstants.DEFAULT_LOG_LEVEL),
  enableMetrics: z.boolean().default(true),
  maxLogFiles: z.number()
    .min(SettingsBounds.MAX_LOG_FILES_MIN)
    .max(SettingsBounds.MAX_LOG_FILES_MAX)
    .default(UIConstants.MAX_LOG_FILES),
  experimentalStem: z.boolean().default(false),
  experimentalGpuAccel: z.boolean().default(true),
});

export type AdvancedSettings = z.infer<typeof advancedSettingsSchema>;

// ============================================
// Complete Settings State Schema
// ============================================
export const settingsStateSchema = z.object({
  general: generalSettingsSchema,
  transcription: transcriptionSettingsSchema,
  refiner: refinerSettingsSchema,
  audio: audioSettingsSchema,
  hotkey: hotkeySettingsSchema,
  coach: coachSettingsSchema,
  history: historySettingsSchema,
  dictionary: dictionarySettingsSchema,
  snippets: snippetsSettingsSchema,
  style: styleSettingsSchema,
  advanced: advancedSettingsSchema,
  version: z.number().default(SETTINGS_VERSION),
});

export type SettingsState = z.infer<typeof settingsStateSchema>;

// ============================================
// Default Values
// ============================================
export const DEFAULT_SETTINGS: SettingsState = {
  general: {
    defaultSessionTitle: SessionConstants.DEFAULT_SESSION_TITLE,
    defaultLanguage: UIConstants.DEFAULT_LANGUAGE,
    exportDirectory: '',
    autoSaveInterval: UIConstants.AUTO_SAVE_INTERVAL_SECONDS,
    showNotifications: true,
    minimizeToTray: true,
    startupWithSystem: false,
    theme: UIConstants.DEFAULT_THEME,
  },
  transcription: {
    model_name: ModelConstants.DEFAULT_MODEL_NAME,
    default_asr_model_id: 'whisper-medium',
    microphone_asr_model_id: 'whisper-medium',
    system_asr_model_id: 'whisper-medium',
    refinement_mode: RefinerConstants.DEFAULT_REFINEMENT_MODE,
    refinement_profile: 'clean_dictation',
    transcription_mode: 'dictation',
    compute_type: ModelConstants.DEFAULT_COMPUTE_TYPE,
    chunk_duration: AudioConstants.DEFAULT_CHUNK_SECONDS,
    overlap_ratio: AudioConstants.DEFAULT_OVERLAP_SECONDS / AudioConstants.DEFAULT_CHUNK_SECONDS,
    vad_enabled: VADConstants.DEFAULT_FILTER_ENABLED,
    vad_threshold_db: VADConstants.DEFAULT_THRESHOLD_DB,
    vad_min_silence_ms: 200,
    vad_speech_pad_ms: 200,
    confidence_threshold: ModelConstants.DEFAULT_CONFIDENCE_THRESHOLD,
    enable_filler_filter: true,
    enable_hallucination_filter: true,
    min_segment_length: ModelConstants.MIN_SEGMENT_LENGTH,
    max_workers: PerformanceConstants.DEFAULT_MAX_WORKERS,
    use_parallel_processing: true,
    preload_model: true,
    hotkey_optimized: false,
    beam_size: ModelConstants.DEFAULT_BEAM_SIZE,
    best_of: ModelConstants.DEFAULT_BEST_OF,
    patience: ModelConstants.DEFAULT_PATIENCE,
    temperature: ModelConstants.DEFAULT_TEMPERATURE,
  },
  refiner: {
    selected_model_id: RefinerConstants.DEFAULT_MODEL_ID,
    runtime_enabled: false,
    cleanup_instructions: '',
    engine_preference: RefinerConstants.DEFAULT_ENGINE_PREFERENCE,
  },
  audio: {
    captureMode: 'microphone',
    default_capture_source: 'microphone',
    defaultDeviceId: AudioConstants.DEFAULT_CAPTURE_DEVICE_ID,
    audio_backend: AudioConstants.DEFAULT_BACKEND,
    sampleRate: AudioConstants.DEFAULT_SAMPLE_RATE,
    noiseFiltering: true,
    echoCancellation: true,
    autoGainControl: true,
    mute_transcripta_audio_during_dictation: false,
  },
  hotkey: {
    enabled: false,
    key_combination: UIConstants.DEFAULT_HOTKEY,
    microphone_key_combination: UIConstants.DEFAULT_HOTKEY,
    system_key_combination: 'CommandOrControl+Shift+Y',
    hold_mode: false,
    auto_inject: true,
    language: UIConstants.DEFAULT_LANGUAGE,
    capture_source: 'microphone',
    device_id: AudioConstants.DEFAULT_CAPTURE_DEVICE_ID,
    finish_mode_default: 'finish_and_paste',
    enable_refiner_on_stop: false,
    save_debug_wav: false,
    show_floating_window: true,
    floating_window_position: 'bottom-right',
    record_on_start: false,
    stop_on_release: false,
    copy_to_clipboard: true,
  },
  coach: {
    coach_enabled: true,
    coach_show_live_hints: false,
    coach_detail_level: 'compact',
    copy_polished_by_default: true,
    show_diff_view: true,
    coach_template_id_mic: 'default_english_coach',
    coach_template_id_system: 'default_english_coach',
    coach_prompt_custom_enabled: false,
    coach_prompt_custom_text: '',
    coach_overrides: {
      tone: 'neutral',
      aggressiveness: 'light',
      filler_removal: true,
      keep_slang: true,
      target_style: 'simple',
    },
    privacy_mode: 'local_only',
    show_floating_coach_result: true,
    coach_prompt_templates: [
      {
        id: 'default_english_coach',
        name: 'Default English Coach',
        version: 1,
        system:
          'You are an English writing coach for dictation transcripts.\nYou must preserve the speakers meaning and tone.\nYou must NOT add new facts.\nPrefer minimal edits.\nOutput MUST be valid JSON only, matching the schema exactly.',
        user_template:
          'Language mode: {language_mode}\nDetail level: {detail_level}\nOverrides JSON: {overrides_json}\n\nOriginal transcript:\n{original_text}\n\nTask:\n1) Produce "polished" that reads naturally (single paragraph unless clearly multiple).\n2) Provide "diff" operations aligned to the original string indices where possible. If exact indices are hard, provide approximate ranges but keep them consistent.\n3) Provide 2–5 short tips.\n4) Provide up to 5 mistakes with fixes and short explanations.\n5) Provide one short practice rewrite.\n\nReturn JSON with keys: original, polished, diff, tips, mistakes, practice, meta.',
        enabled: true,
        built_in: true,
      },
    ],
  },
  history: {
    retention_days: 30,
    persist_audio: true,
    allow_retry: true,
    default_analytics_range_days: 7,
  },
  dictionary: {
    dictionary_enabled: true,
  },
  snippets: {
    snippets_enabled: true,
    snippets_quick_insert: false,
  },
  style: {
    style_default_profile: 'casual',
    style_apply_enabled: true,
  },
  advanced: {
    debugMode: false,
    logLevel: ServerConstants.DEFAULT_LOG_LEVEL,
    enableMetrics: true,
    maxLogFiles: UIConstants.MAX_LOG_FILES,
    experimentalStem: false,
    experimentalGpuAccel: true,
  },
  version: SETTINGS_VERSION,
};

// ============================================
// Validation Helpers
// ============================================
export function validateSettings(data: unknown): { success: true; data: SettingsState } | { success: false; errors: z.ZodError } {
  const result = settingsStateSchema.safeParse(data);
  if (result.success) {
    return { success: true, data: result.data };
  }
  return { success: false, errors: result.error };
}

export function validatePartialSettings(data: unknown): { success: true; data: Partial<SettingsState> } | { success: false; errors: z.ZodError } {
  const result = settingsStateSchema.partial().safeParse(data);
  if (result.success) {
    return { success: true, data: result.data };
  }
  return { success: false, errors: result.error };
}

export function validateCategory<K extends keyof SettingsState>(
  category: K,
  data: unknown
): { success: true; data: SettingsState[K] } | { success: false; errors: z.ZodError<SettingsState[K]> } {
  const schema = settingsStateSchema.shape[category];
  const result = schema.safeParse(data) as { success: true; data: SettingsState[K] } | { success: false; error: z.ZodError<SettingsState[K]> };
  if (result.success) {
    return { success: true, data: result.data };
  }
  return { success: false, errors: result.error };
}

// ============================================
// Setting Field Metadata (for UI generation)
// ============================================
export type SettingFieldType = 'string' | 'number' | 'boolean' | 'enum' | 'range';

export interface SettingFieldMeta {
  key: string;
  type: SettingFieldType;
  label: string;
  description: string;
  category: keyof SettingsState;
  options?: { value: string; label: string }[];
  min?: number;
  max?: number;
  step?: number;
  suffix?: string;
  isFake?: boolean;
}

export const SETTING_FIELDS_META: SettingFieldMeta[] = [
  // General
  { key: 'theme', type: 'enum', label: SETTING_LABELS.theme, description: SETTING_DESCRIPTIONS.theme, category: 'general', options: [
    { value: 'light', label: THEME_LABELS.light },
    { value: 'dark', label: THEME_LABELS.dark },
    { value: 'cyber', label: THEME_LABELS.cyber },
    { value: 'dracula', label: THEME_LABELS.dracula },
  ]},
  { key: 'defaultSessionTitle', type: 'string', label: SETTING_LABELS.defaultSessionTitle, description: SETTING_DESCRIPTIONS.defaultSessionTitle, category: 'general' },
  { key: 'defaultLanguage', type: 'enum', label: SETTING_LABELS.defaultLanguage, description: SETTING_DESCRIPTIONS.defaultLanguage, category: 'general' },
  { key: 'exportDirectory', type: 'string', label: SETTING_LABELS.exportDirectory, description: SETTING_DESCRIPTIONS.exportDirectory, category: 'general' },
  { key: 'autoSaveInterval', type: 'range', label: SETTING_LABELS.autoSaveInterval, description: SETTING_DESCRIPTIONS.autoSaveInterval, category: 'general', min: 10, max: 300, step: 10, suffix: 's' },
  { key: 'showNotifications', type: 'boolean', label: SETTING_LABELS.showNotifications, description: SETTING_DESCRIPTIONS.showNotifications, category: 'general', isFake: true },
  { key: 'minimizeToTray', type: 'boolean', label: SETTING_LABELS.minimizeToTray, description: SETTING_DESCRIPTIONS.minimizeToTray, category: 'general', isFake: true },
  { key: 'startupWithSystem', type: 'boolean', label: SETTING_LABELS.startupWithSystem, description: SETTING_DESCRIPTIONS.startupWithSystem, category: 'general', isFake: true },

  // Transcription
  { key: 'model_name', type: 'enum', label: SETTING_LABELS.model_name, description: SETTING_DESCRIPTIONS.model_name, category: 'transcription', options: [
    { value: 'tiny', label: MODEL_NAMES_SHORT.tiny },
    { value: 'base', label: MODEL_NAMES_SHORT.base },
    { value: 'small', label: MODEL_NAMES_SHORT.small },
    { value: 'medium', label: MODEL_NAMES_SHORT.medium },
    { value: 'large-v3', label: MODEL_NAMES_SHORT['large-v3'] },
  ]},
  { key: 'default_asr_model_id', type: 'string', label: 'Fallback ASR Model', description: 'Used when a source-specific ASR model is not set.', category: 'transcription' },
  { key: 'microphone_asr_model_id', type: 'string', label: 'Microphone ASR Model', description: 'Default speech-to-text model when recording from the microphone.', category: 'transcription' },
  { key: 'system_asr_model_id', type: 'string', label: 'System Audio ASR Model', description: 'Default speech-to-text model when transcribing system audio.', category: 'transcription' },
  { key: 'compute_type', type: 'enum', label: SETTING_LABELS.compute_type, description: SETTING_DESCRIPTIONS.compute_type, category: 'transcription', options: [
    { value: 'float16', label: COMPUTE_TYPE_LABELS.float16 },
    { value: 'int8', label: COMPUTE_TYPE_LABELS.int8 },
    { value: 'int8_float16', label: COMPUTE_TYPE_LABELS.int8_float16 },
  ]},
  { key: 'chunk_duration', type: 'range', label: SETTING_LABELS.chunk_duration, description: SETTING_DESCRIPTIONS.chunk_duration, category: 'transcription', min: 0.5, max: 5.0, step: 0.1, suffix: 's' },
  { key: 'overlap_ratio', type: 'range', label: SETTING_LABELS.overlap_ratio, description: SETTING_DESCRIPTIONS.overlap_ratio, category: 'transcription', min: 0, max: 0.5, step: 0.05 },
  { key: 'vad_enabled', type: 'boolean', label: SETTING_LABELS.vad_enabled, description: SETTING_DESCRIPTIONS.vad_enabled, category: 'transcription' },
  { key: 'vad_threshold_db', type: 'range', label: SETTING_LABELS.vad_threshold_db, description: SETTING_DESCRIPTIONS.vad_threshold_db, category: 'transcription', min: -60, max: -20, step: 1, suffix: 'dB' },
  { key: 'vad_min_silence_ms', type: 'range', label: SETTING_LABELS.vad_min_silence_ms, description: SETTING_DESCRIPTIONS.vad_min_silence_ms, category: 'transcription', min: 0, max: 5000, step: 50, suffix: 'ms' },
  { key: 'vad_speech_pad_ms', type: 'range', label: SETTING_LABELS.vad_speech_pad_ms, description: SETTING_DESCRIPTIONS.vad_speech_pad_ms, category: 'transcription', min: 0, max: 1000, step: 50, suffix: 'ms' },
  { key: 'confidence_threshold', type: 'range', label: SETTING_LABELS.confidence_threshold, description: SETTING_DESCRIPTIONS.confidence_threshold, category: 'transcription', min: 0, max: 1, step: 0.05 },
  { key: 'enable_filler_filter', type: 'boolean', label: SETTING_LABELS.enable_filler_filter, description: SETTING_DESCRIPTIONS.enable_filler_filter, category: 'transcription' },
  { key: 'enable_hallucination_filter', type: 'boolean', label: SETTING_LABELS.enable_hallucination_filter, description: SETTING_DESCRIPTIONS.enable_hallucination_filter, category: 'transcription' },
  { key: 'min_segment_length', type: 'range', label: SETTING_LABELS.min_segment_length, description: SETTING_DESCRIPTIONS.min_segment_length, category: 'transcription', min: 0.1, max: 2.0, step: 0.1, suffix: 's' },
  { key: 'max_workers', type: 'range', label: SETTING_LABELS.max_workers, description: SETTING_DESCRIPTIONS.max_workers, category: 'transcription', min: 1, max: 16, step: 1, isFake: true },
  { key: 'use_parallel_processing', type: 'boolean', label: SETTING_LABELS.use_parallel_processing, description: SETTING_DESCRIPTIONS.use_parallel_processing, category: 'transcription', isFake: true },
  { key: 'preload_model', type: 'boolean', label: SETTING_LABELS.preload_model, description: SETTING_DESCRIPTIONS.preload_model, category: 'transcription', isFake: true },
  { key: 'hotkey_optimized', type: 'boolean', label: SETTING_LABELS.hotkey_optimized, description: SETTING_DESCRIPTIONS.hotkey_optimized, category: 'transcription' },
  { key: 'beam_size', type: 'number', label: SETTING_LABELS.beam_size, description: SETTING_DESCRIPTIONS.beam_size, category: 'transcription', min: 1, max: 20 },
  { key: 'best_of', type: 'number', label: SETTING_LABELS.best_of, description: SETTING_DESCRIPTIONS.best_of, category: 'transcription', min: 1, max: 20 },
  { key: 'patience', type: 'number', label: SETTING_LABELS.patience, description: SETTING_DESCRIPTIONS.patience, category: 'transcription', min: 0.1, max: 5.0, step: 0.1, isFake: true },
  { key: 'temperature', type: 'range', label: SETTING_LABELS.temperature, description: SETTING_DESCRIPTIONS.temperature, category: 'transcription', min: 0, max: 1, step: 0.1 },

  // Audio
  { key: 'captureMode', type: 'enum', label: SETTING_LABELS.captureMode, description: SETTING_DESCRIPTIONS.captureMode, category: 'audio', options: [
    { value: 'system', label: CAPTURE_MODE_LABELS.system },
    { value: 'microphone', label: CAPTURE_MODE_LABELS.microphone },
  ]},
  { key: 'default_capture_source', type: 'enum', label: 'Default Capture Source', description: SETTING_DESCRIPTIONS.default_capture_source, category: 'audio', options: [
    { value: 'system', label: CAPTURE_MODE_LABELS.system },
    { value: 'microphone', label: CAPTURE_MODE_LABELS.microphone },
  ]},
  { key: 'defaultDeviceId', type: 'enum', label: SETTING_LABELS.defaultDeviceId, description: SETTING_DESCRIPTIONS.defaultDeviceId, category: 'audio' },
  { key: 'audio_backend', type: 'enum', label: SETTING_LABELS.audio_backend, description: SETTING_DESCRIPTIONS.audio_backend, category: 'audio', options: [
    { value: 'auto', label: AUDIO_BACKEND_LABELS.auto },
    { value: 'pyaudio', label: AUDIO_BACKEND_LABELS.pyaudio },
    { value: 'soundcard', label: AUDIO_BACKEND_LABELS.soundcard },
  ]},
  { key: 'sampleRate', type: 'enum', label: SETTING_LABELS.sampleRate, description: SETTING_DESCRIPTIONS.sampleRate, category: 'audio', options: [
    { value: '8000', label: SAMPLE_RATE_LABELS['8000'] },
    { value: '16000', label: SAMPLE_RATE_LABELS['16000'] },
    { value: '22050', label: SAMPLE_RATE_LABELS['22050'] },
    { value: '44100', label: SAMPLE_RATE_LABELS['44100'] },
    { value: '48000', label: SAMPLE_RATE_LABELS['48000'] },
  ]},
  { key: 'noiseFiltering', type: 'boolean', label: SETTING_LABELS.noiseFiltering, description: SETTING_DESCRIPTIONS.noiseFiltering, category: 'audio', isFake: true },
  { key: 'echoCancellation', type: 'boolean', label: SETTING_LABELS.echoCancellation, description: SETTING_DESCRIPTIONS.echoCancellation, category: 'audio', isFake: true },
  { key: 'autoGainControl', type: 'boolean', label: SETTING_LABELS.autoGainControl, description: SETTING_DESCRIPTIONS.autoGainControl, category: 'audio', isFake: true },
  { key: 'mute_transcripta_audio_during_dictation', type: 'boolean', label: 'Mute App Audio During Dictation', description: SETTING_DESCRIPTIONS.mute_transcripta_audio_during_dictation, category: 'audio' },

  // Hotkey
  { key: 'enabled', type: 'boolean', label: SETTING_LABELS.enabled, description: SETTING_DESCRIPTIONS.enabled, category: 'hotkey' },
  { key: 'key_combination', type: 'string', label: SETTING_LABELS.key_combination, description: SETTING_DESCRIPTIONS.key_combination, category: 'hotkey' },
  { key: 'microphone_key_combination', type: 'string', label: 'Microphone Hotkey', description: 'Global shortcut for microphone dictation.', category: 'hotkey' },
  { key: 'system_key_combination', type: 'string', label: 'System Audio Hotkey', description: 'Global shortcut for system-audio transcription.', category: 'hotkey' },
  { key: 'hold_mode', type: 'boolean', label: SETTING_LABELS.hold_mode, description: SETTING_DESCRIPTIONS.hold_mode, category: 'hotkey' },
  { key: 'auto_inject', type: 'boolean', label: SETTING_LABELS.auto_inject, description: SETTING_DESCRIPTIONS.auto_inject, category: 'hotkey' },
  { key: 'language', type: 'string', label: SETTING_LABELS.language, description: SETTING_DESCRIPTIONS.language, category: 'hotkey' },
  { key: 'capture_source', type: 'enum', label: 'Hotkey Capture Source', description: 'Choose whether the hotkey records your microphone or system audio.', category: 'hotkey', options: [
    { value: 'system', label: CAPTURE_MODE_LABELS.system },
    { value: 'microphone', label: CAPTURE_MODE_LABELS.microphone },
  ]},
  { key: 'device_id', type: 'string', label: SETTING_LABELS.device_id, description: SETTING_DESCRIPTIONS.device_id, category: 'hotkey' },
  { key: 'finish_mode_default', type: 'enum', label: SETTING_LABELS.finish_mode_default, description: SETTING_DESCRIPTIONS.finish_mode_default, category: 'hotkey', options: [
    { value: 'finish', label: FINISH_ACTION_LABELS.finish },
    { value: 'finish_and_paste', label: FINISH_ACTION_LABELS.finish_and_paste },
    { value: 'cancel', label: FINISH_ACTION_LABELS.cancel },
  ]},
  { key: 'enable_refiner_on_stop', type: 'boolean', label: 'Enable Refiner on Dictation Stop', description: 'Run the text refiner after hotkey dictation stops.', category: 'hotkey' },
  { key: 'save_debug_wav', type: 'boolean', label: 'Save Hotkey Debug WAV', description: 'Write captured dictation audio to logs/hotkey-debug when dictation stops.', category: 'hotkey' },
  { key: 'show_floating_window', type: 'boolean', label: SETTING_LABELS.show_floating_window, description: SETTING_DESCRIPTIONS.show_floating_window, category: 'hotkey' },
  { key: 'floating_window_position', type: 'enum', label: SETTING_LABELS.floating_window_position, description: SETTING_DESCRIPTIONS.floating_window_position, category: 'hotkey', options: [
    { value: 'top-left', label: FLOATING_POSITION_LABELS['top-left'] },
    { value: 'top-right', label: FLOATING_POSITION_LABELS['top-right'] },
    { value: 'bottom-left', label: FLOATING_POSITION_LABELS['bottom-left'] },
    { value: 'bottom-right', label: FLOATING_POSITION_LABELS['bottom-right'] },
    { value: 'center', label: FLOATING_POSITION_LABELS.center },
  ]},
  { key: 'record_on_start', type: 'boolean', label: SETTING_LABELS.record_on_start, description: SETTING_DESCRIPTIONS.record_on_start, category: 'hotkey' },
  { key: 'stop_on_release', type: 'boolean', label: SETTING_LABELS.stop_on_release, description: SETTING_DESCRIPTIONS.stop_on_release, category: 'hotkey' },
  { key: 'copy_to_clipboard', type: 'boolean', label: SETTING_LABELS.copy_to_clipboard, description: SETTING_DESCRIPTIONS.copy_to_clipboard, category: 'hotkey' },

  // Advanced
  { key: 'debugMode', type: 'boolean', label: SETTING_LABELS.debugMode, description: SETTING_DESCRIPTIONS.debugMode, category: 'advanced' },
  { key: 'logLevel', type: 'enum', label: SETTING_LABELS.logLevel, description: SETTING_DESCRIPTIONS.logLevel, category: 'advanced', options: [
    { value: 'DEBUG', label: LOG_LEVEL_LABELS.DEBUG },
    { value: 'INFO', label: LOG_LEVEL_LABELS.INFO },
    { value: 'WARN', label: LOG_LEVEL_LABELS.WARN },
    { value: 'ERROR', label: LOG_LEVEL_LABELS.ERROR },
  ]},
  { key: 'enableMetrics', type: 'boolean', label: SETTING_LABELS.enableMetrics, description: SETTING_DESCRIPTIONS.enableMetrics, category: 'advanced' },
  { key: 'maxLogFiles', type: 'number', label: SETTING_LABELS.maxLogFiles, description: SETTING_DESCRIPTIONS.maxLogFiles, category: 'advanced', min: 1, max: 100 },
  { key: 'experimentalStem', type: 'boolean', label: SETTING_LABELS.experimentalStem, description: SETTING_DESCRIPTIONS.experimentalStem, category: 'advanced', isFake: true },
  { key: 'experimentalGpuAccel', type: 'boolean', label: SETTING_LABELS.experimentalGpuAccel, description: SETTING_DESCRIPTIONS.experimentalGpuAccel, category: 'advanced', isFake: true },
];

// Helper to get meta for a specific setting
export function getSettingMeta(category: keyof SettingsState, key: string): SettingFieldMeta | undefined {
  return SETTING_FIELDS_META.find(f => f.category === category && f.key === key);
}

// Helper to search settings
export function searchSettings(query: string): SettingFieldMeta[] {
  const q = query.toLowerCase();
  return SETTING_FIELDS_META.filter(f =>
    f.label.toLowerCase().includes(q) ||
    f.description.toLowerCase().includes(q) ||
    f.key.toLowerCase().includes(q)
  );
}


