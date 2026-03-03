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
  last_activated_at: string | null;
  total_activations: number;
  current_text: string;
  duration_ms: number;
};

// Import type explicitly to avoid circular import resolution issues
import type { HotkeySettings } from '../lib/settingsSchema';

export type HotkeyState = {
  config: HotkeySettings;
  session: HotkeySession | null;
  is_registered: boolean;
  error: string | null;
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
};

export type HotkeyStartResponse = {
  session_id: string;
  status: string;
  message?: string;
};

export type HotkeyStopResponse = {
  final_transcription: string;
  raw_transcription?: string;
  refined_transcription?: string | null;
  duration_ms: number;
  segment_count: number;
  source_backend?: string;
  language_used?: string;
  refinement_mode?: 'off' | 'strict' | 'polished';
  refiner_model_id?: string | null;
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

// ============================================
// Settings Types
// ============================================
// NOTE: SettingsState, GeneralSettings, TranscriptionSettings, AudioSettings,
// HotkeySettings, and AdvancedSettings are defined in lib/settingsSchema.ts
// Import them from there to use Zod-inferred types as the single source of truth.
//
// Example: import type { SettingsState } from '../lib/settingsSchema';
