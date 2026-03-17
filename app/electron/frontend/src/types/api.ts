/**
 * API Types - Type definitions for backend communication
 * 
 * Defines types for sessions, transcripts, models, hotkeys, settings,
 * hardware profiles, history, and other API request/response payloads.
 */
export type Device = {
  id: string;
  name: string;
  kind: string;
  is_loopback: boolean;
  channels: number | null;
  sample_rate: number | null;
  backend_candidates?: string[];
  is_input?: boolean;
  is_output?: boolean;
  supports_loopback?: boolean | null;
  driver?: string | null;
};

export type SessionDocument = {
  path: string;
  name: string;
  added_at: string;
};

export type SessionSummary = {
  session_id: string;
  title: string;
  output_dir: string;
  model_name: string;
  language_mode: string;
  device_id: string;
  live_mode: string;
  execution_mode: string;
  started_at: string;
  status: string;
  documents: SessionDocument[];
  segment_count: number;
  formula_count: number;
  review_count: number;
  suppressed_count: number;
  health?: Health;
};

export type Word = {
  text: string;
  start: number;
  end: number;
  confidence: number;
};

export type Segment = {
  id: string;
  start: number;
  end: number;
  text: string;
  display_text: string;
  raw_text?: string;
  refined_text?: string;
  was_refined?: boolean;
  language: string;
  avg_logprob?: number | null;
  no_speech_prob?: number | null;
  compression_ratio?: number | null;
  confidence: number;
  review_flag: boolean;
  review_reasons: string[];
  suppressed: boolean;
  suppression_reasons: string[];
  quality_label: string;
  script_mismatch: boolean;
  words?: Word[];
  latency_ms?: number;
  is_partial?: boolean;
};

export type DraftPartialPayload = {
  session_id: string;
  segment_id: string;
  revision: number;
  stream_id: string;
  text: string;
  start: number;
  end: number;
  committed_text: string;
  draft_suffix: string;
  metrics?: Record<string, number | null>;
};

export type CommitFinalPayload = DraftPartialPayload & {
  segment: Segment;
};

export type RefineFinalPayload = {
  session_id: string;
  segment_id: string;
  base_revision: number;
  refinement_mode: 'off' | 'strict' | 'polished';
  refinement_profile?: 'raw' | 'clean_dictation' | 'professional' | 'student_notes' | 'code_logs';
  refiner_model_id?: string | null;
  used_runtime: boolean;
  segment: Segment;
};

export type Formula = {
  expression: string;
  timestamp_start: number;
  timestamp_end: number;
  context: string;
  confidence: number;
  parseable: boolean;
  review_flag: boolean;
  reasons: string[];
  variables?: string[];
  units?: string[];
};

export type Health = {
  audio_stream_active: boolean;
  gpu_mode: string;
  execution_mode: string;
  model_runtime_device: string;
  last_transcript_at: string | null;
  dropped_frames: number;
  queue_depth: number;
  dropped_stt_chunks: number;
  stt_backpressure_state: string;
  estimated_backlog_seconds: number;
  last_error: string | null;
  last_warning: string | null;
};

export type SnapshotPayload = {
  session: SessionSummary | null;
  transcript: Segment[];
  suppressed_transcript: Segment[];
  formulas: Formula[];
  needs_review: Segment[];
  health: Health;
  meter_value: number;
  available_models: string[];
  available_languages: string[];
  available_live_modes: string[];
  available_execution_modes: string[];
  runtime_revision: number;
  loading?: boolean;
  loading_message?: string;
  model_cache?: Record<string, unknown>;
  system_profile?: SystemProfile;
};

export type ModelCatalogEntry = {
  id: string;
  display_name: string;
  category: 'asr' | 'refiner';
  family: 'whisper' | 'qwen' | 'mistral' | 'phi';
  engine: 'faster-whisper' | 'llamacpp' | 'ollama';
  size_gb_estimate: number;
  recommended_vram_gb: number;
  speed_tier: 'fast' | 'balanced' | 'quality';
  license_note: string;
  description_short: string;
  why_choose_this: string;
  runtime_model_name: string | null;
  enabled_runtime: boolean;
  installed: boolean;
  verified: boolean;
  recommended: boolean;
  download_artifacts: Array<{
    filename: string;
    url: string;
    min_size_bytes: number;
    sha256?: string | null;
  }>;
  default_runtime_config: Record<string, unknown>;
};

export type ModelInstallState = {
  model_id: string;
  installed: boolean;
  verified: boolean;
  install_path: string;
  size_bytes: number;
  last_checked_at: number;
};

export type ModelDownloadState = {
  model_id: string;
  download_id?: string;
  correlation_id?: string;
  attempt?: number;
  current_artifact?: string | null;
  status: 'idle' | 'downloading' | 'retrying' | 'verifying' | 'completed' | 'failed' | 'cancelled';
  bytes_downloaded: number;
  total_bytes: number;
  total_bytes_known?: boolean;
  progress: number;
  speed_bytes_per_sec: number;
  error?: string | null;
};

export type ModelCatalogPayload = {
  catalog: ModelCatalogEntry[];
  installed: ModelInstallState[];
  selected_asr_model_id: string;
  selected_refiner_model_id: string;
  refinement_mode: 'off' | 'strict' | 'polished';
  refinement_profile?: 'raw' | 'clean_dictation' | 'professional' | 'student_notes' | 'code_logs';
  recommendations: string[];
};

// Device probe result - uses discriminated union pattern
// Backend always returns ok: true on success or ok: false on error
export type DeviceProbeResultSuccess = {
  ok: true;
  backend: string;
  sample_rate: number;
  channels: number;
  duration: number;
  rms_mean: number;
  rms_peak: number;
  has_signal: boolean;
  dominant_channels: number[];
  dropped_frames: number;
  wav_path: string | null;
};

export type DeviceProbeResultError = {
  ok: false;
  backend: string;
  error: string;
  device_id: string;
  duration: number;
  sample_rate?: number;
  channels?: number;
  rms_mean?: number;
  rms_peak?: number;
  has_signal?: boolean;
  dominant_channels?: number[];
  dropped_frames?: number;
  wav_path?: string | null;
};

export type DeviceProbeResult = DeviceProbeResultSuccess | DeviceProbeResultError;

export type ModelPreloadStatus = {
  loading: boolean;
  progress: number;
  message: string;
  model_name?: string;
  stage?: 'idle' | 'preparing' | 'downloading' | 'loading' | 'warming' | 'ready' | 'failed';
};

// ============================================
// Hotkey Types - Aligned with Backend
// ============================================

export type HotkeyStatus = 'idle' | 'listening' | 'processing' | 'error';

// HotkeySession aligned with backend HotkeySession dataclass
// Backend uses: is_recording, duration_ms (not is_active, duration_seconds)
export type HotkeySession = {
  session_id: string;
  is_recording: boolean;
  status: HotkeyStatus;
  lifecycle_state?: 'idle' | 'starting' | 'recording' | 'stopping' | 'error';
  capture_source?: 'microphone' | 'system' | null;
  last_activated_at: string | null;
  total_activations: number;
  current_text: string;
  duration_ms: number;
};

// Import type explicitly to avoid circular import resolution issues
import type { HotkeySettings } from '../config/settingsSchema';

export type HotkeyState = {
  config: HotkeySettings;
  session: HotkeySession | null;
  is_registered: boolean;
  error: string | null;
  capabilities?: {
    holdModeSupported?: boolean;
  };
};

// ============================================
// API Request/Response Types
// ============================================

export type HotkeyStartRequest = {
  capture_source?: 'microphone' | 'system' | null;
  device_id?: string | null;
  model_name?: string;
  language_mode?: string;
  execution_mode?: string;
  transcription_mode?: 'dictation' | 'literal' | 'session_paragraph';
};

export type HotkeyStartResponse = {
  session_id: string;
  status: string;
  message?: string;
};

export type CoachDiffOp = {
  op: 'delete' | 'insert' | 'replace';
  from: string;
  to: string;
  start: number;
  end: number;
};

export type CoachMistake = {
  type: 'grammar' | 'wording' | 'tense' | 'article' | 'preposition' | 'clarity';
  example: string;
  fix: string;
  why: string;
};

export type CoachPractice = {
  prompt: string;
  answer: string;
};

export type CoachMeta = {
  model: string;
  confidence: number;
  cache_hit: boolean;
  provider: string;
  prompt_template_id: string;
  prompt_version: number;
};

export type CoachResult = {
  original: string;
  polished: string;
  diff: CoachDiffOp[];
  tips: string[];
  mistakes: CoachMistake[];
  practice: CoachPractice;
  meta: CoachMeta;
};

export type HotkeyStopResponse = {
  session_id?: string | null;
  status?: 'idle' | 'stopping' | 'error';
  transcription_mode?: 'dictation' | 'literal' | 'session_paragraph';
  composed_text?: string;
  final_transcription: string;
  aggregated_raw_text?: string;
  aggregated_clean_text?: string;
  postprocessed_text?: string;
  paste_text?: string;
  live_paste_text?: string;
  final_cleanup_applied?: boolean;
  raw_transcription?: string;
  refined_transcription?: string | null;
  coach_result?: CoachResult | null;
  coach_status?: 'disabled' | 'queued' | 'running' | 'failed' | 'fallback' | 'cache_hit' | 'generated' | 'success';
  coach_display_source?: 'coach' | 'fallback' | 'faithful';
  coach_error?: string | null;
  coach_cache_hit?: boolean;
  debug_wav_path?: string | null;
  duration_ms: number;
  segment_count: number;
  source_backend?: string;
  language_used?: string;
  refinement_mode?: 'off' | 'strict' | 'polished';
  refinement_profile?: 'raw' | 'clean_dictation' | 'professional' | 'student_notes' | 'code_logs';
  refiner_model_id?: string | null;
  warnings?: string[];
};

export type HotkeyStatusResponse = {
  is_recording: boolean;
  partial_text: string;
  raw_partial_text?: string;
  display_partial_text?: string;
  audio_level: number;
  session_id?: string | null;
  duration_ms?: number;
  levels?: number[] | null;
};

export type HotkeyInjectRequest = {
  text: string;
};

export type HotkeyInjectResponse = {
  success: boolean;
  message?: string;
};

export type HotkeyConfigRequest = {
  chunk_seconds?: number;
  overlap_seconds?: number;
  vad_threshold_db?: number;
  vad_min_silence_ms?: number;
  vad_speech_pad_ms?: number;
  confidence_threshold?: number;
  enable_filler_filter?: boolean;
};

export type HotkeyConfig = {
  chunk_seconds: number;
  overlap_seconds: number;
  vad_threshold_db: number;
  vad_min_silence_ms: number;
  vad_speech_pad_ms: number;
  confidence_threshold: number;
  enable_filler_filter: boolean;
};

export type HotkeyConfigResponse = {
  success: boolean;
  config: HotkeyConfig;
  message?: string;
};

export type HotkeyUpdateRequest = {
  config?: Partial<HotkeySettings>;
  action?: 'register' | 'unregister' | 'test';
};

export type HotkeyUpdateResponse = {
  success: boolean;
  config: HotkeySettings;
  session: HotkeySession | null;
  error: string | null;
};

// ============================================
// Session Request/Response Types
// ============================================

export type StartSessionRequest = {
  title: string;
  output_root: string;
  model_name: string;
  language_mode: string;
  capture_source?: 'system' | 'microphone' | null;
  device_id?: string | null;
  live_mode?: string;
  execution_mode?: string;
  // VAD parameters
  vad_threshold?: number | null;
  vad_min_silence_ms?: number | null;
  vad_speech_pad_ms?: number | null;
};

export type AttachPdfRequest = {
  path: string;
};

export type PreloadModelRequest = {
  model_name: string;
  execution_mode?: string;
};

// ============================================
// Settings Request/Response Types
// ============================================

export type SettingsSaveResponse = {
  success: boolean;
  message: string;
};

export type SettingsResetResponse = {
  success: boolean;
  message: string;
};

// ============================================
// Auto-Optimizer Types
// ============================================

export type GPUInfo = {
  available: boolean;
  name: string;
  vram_gb: number;
  can_run_large: boolean;
  can_run_medium: boolean;
  cuda_version: string | null;
  compute_capability: string | null;
};

export type CPUInfo = {
  cores: number;
  threads: number;
  ram_gb: number;
  can_parallel: boolean;
  architecture: string;
};

export type StorageInfo = {
  free_gb: number;
  total_gb: number;
  can_download_large: boolean;
  ssd_available: boolean;
};

export type HardwareProfile = {
  gpu: GPUInfo;
  cpu: CPUInfo;
  storage: StorageInfo;
  platform: string;
  detected_at: string;
};

export type SystemProfile = HardwareProfile & {
  recommended_quality: 'maximum' | 'balanced' | 'fast' | 'low_memory';
  recommended_preset: string;
};

// OptimizedSettings - aligned with what backend /api/system/optimize returns
export type OptimizedSettings = {
  model_name: string;
  compute_type: string;
  chunk_duration: number;
  overlap_ratio: number;
  vad_enabled: boolean;
  vad_threshold_db: number;
  confidence_threshold: number;
  enable_filler_filter: boolean;
  enable_hallucination_filter: boolean;
  min_segment_length: number;
  max_workers: number;
  use_parallel_processing: boolean;
  preload_model: boolean;
  hotkey_optimized: boolean;
  // Optional beam search parameters (used in presets)
  beam_size?: number;
  best_of?: number;
  patience?: number;
  temperature?: number;
  refinement_mode?: 'off' | 'strict' | 'polished';
  refinement_profile?: 'raw' | 'clean_dictation' | 'professional' | 'student_notes' | 'code_logs';
};

export type OptimizationMetadata = {
  quality_level: 'maximum' | 'high' | 'balanced' | 'fast' | 'low_memory';
  optimization_reason: string;
  estimated_vram_usage_gb: number;
  estimated_latency_ms: number;
  recommended_for_hotkey: boolean;
  tradeoffs: string[];
};

export type OptimizationResult = {
  settings: OptimizedSettings;
  metadata: OptimizationMetadata;
  profile: HardwareProfile;
  preset_used: string;
};

export type OptimizationPreset = {
  id: string;
  name: string;
  description: string;
  icon: string;
  recommended_for: string[];
  settings_override: Partial<OptimizedSettings>;
};

export type OptimizeRequest = {
  mode?: 'maximum' | 'balanced' | 'fast' | 'low_memory';
  hotkey_mode?: boolean;
  manual_overrides?: Partial<OptimizedSettings>;
};

// Extract floating window position type for reuse
type FloatingWindowPosition = 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right' | 'center';

export type FloatingWindowOptions = {
  position: FloatingWindowPosition;
  opacity: number;
  always_on_top: boolean;
  show_waveform: boolean;
  show_transcription: boolean;
  width: number;
  height: number;
};

export type HistorySessionRevision = {
  revision_index: number;
  text_source: string;
  text_value: string;
  metadata_json: string;
  created_at: string;
};

export type HistorySession = {
  session_id: string;
  source_workflow: 'dictation' | 'session' | string;
  capture_source: 'microphone' | 'system' | string;
  title: string | null;
  transcription_mode: string | null;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number;
  model_name: string | null;
  model_id: string | null;
  language_mode: string | null;
  execution_mode: string | null;
  device_id: string | null;
  status: string;
  raw_text: string | null;
  aggregated_clean_text: string | null;
  postprocessed_text: string | null;
  coach_polished_text: string | null;
  active_text: string | null;
  active_text_source: string | null;
  audio_path?: string | null;
  audio_available: boolean;
  retry_status: string;
  retry_error?: string | null;
  retry_attempt_count: number;
  deleted_at?: string | null;
  created_at: string;
  updated_at: string;
  word_count: number;
  revisions?: HistorySessionRevision[];
};

export type HistoryAnalyticsSummary = {
  days_used: number;
  total_words: number;
  avg_wpm: number;
  peak_usage_hour: number | null;
};

export type HistoryAnalytics = {
  range_days: number | 'all';
  timezone: string;
  summary: HistoryAnalyticsSummary;
  daily: Array<{ day: string; count: number }>;
  hourly: Array<{ hour: number; count: number }>;
};

export type RetryJob = {
  session_id: string;
  retry_status: 'idle' | 'queued' | 'running' | 'completed' | 'failed' | string;
  retry_attempt_count: number;
  retry_error?: string | null;
};

export type SnippetEntry = {
  id: string;
  trigger: string;
  expansion: string;
  scope: 'personal' | 'shared' | 'team' | string;
  enabled: boolean;
  usage_count: number;
  created_at: string;
  updated_at: string;
};

export type DictionaryEntry = {
  id: string;
  phrase: string;
  replacement: string;
  scope: 'personal' | 'shared' | 'team' | string;
  enabled: boolean;
  usage_count: number;
  created_at: string;
  updated_at: string;
};

export type StyleProfile = {
  id: string;
  name: string;
  style_key: string;
  description: string;
  rules: Record<string, unknown>;
  enabled: boolean;
  built_in: boolean;
  created_at: string;
  updated_at: string;
};

export type StyleAssignments = Record<string, string>;

// ============================================
// Settings Types
// ============================================
// NOTE: SettingsState, GeneralSettings, TranscriptionSettings, AudioSettings,
// HotkeySettings, and AdvancedSettings are defined in config/settingsSchema.ts
// Import them from there to use Zod-inferred types as the single source of truth.
//
// Example: import type { SettingsState } from '../config/settingsSchema';

export type StoragePaths = {
  download_root: string;
  models_path: string;
  refiner_models_path: string;
  app_data: string;
  settings_file: string;
};

