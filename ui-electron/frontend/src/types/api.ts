export type Device = {
  id: string;
  name: string;
  kind: string;
  is_loopback: boolean;
  channels: number | null;
  sample_rate: number | null;
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
  estimated_backlog_seconds?: number;
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

export type DeviceProbeResult = {
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

export type ModelPreloadStatus = {
  loading: boolean;
  progress: number;
  message: string;
  model_name?: string;
};

// ============================================
// Hotkey Types
// ============================================

export type HotkeyStatus = 'idle' | 'listening' | 'processing' | 'error';

export type HotkeyConfig = {
  enabled: boolean;
  key_combination: string;
  hold_mode: boolean;
  auto_inject: boolean;
  show_floating_window: boolean;
  floating_window_position: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right' | 'center';
  record_on_start: boolean;
  stop_on_release: boolean;
  copy_to_clipboard: boolean;
};

export type HotkeySession = {
  session_id: string;
  is_active: boolean;
  status: HotkeyStatus;
  last_activated_at: string | null;
  total_activations: number;
  current_text: string;
  duration_seconds: number;
};

export type HotkeyState = {
  config: HotkeyConfig;
  session: HotkeySession | null;
  is_registered: boolean;
  error: string | null;
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
  beam_size: number;
  best_of: number;
  patience: number;
  temperature: number;
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

// ============================================
// API Request/Response Types
// ============================================

export type HotkeyUpdateRequest = {
  config?: Partial<HotkeyConfig>;
  action?: 'register' | 'unregister' | 'test';
};

export type HotkeyUpdateResponse = {
  success: boolean;
  config: HotkeyConfig;
  session: HotkeySession | null;
  error: string | null;
};

export type OptimizeRequest = {
  mode?: 'maximum' | 'balanced' | 'fast' | 'low_memory';
  hotkey_mode?: boolean;
  manual_overrides?: Partial<OptimizedSettings>;
};

export type FloatingWindowOptions = {
  position: HotkeyConfig['floating_window_position'];
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

export type GeneralSettings = {
  defaultSessionTitle: string;
  defaultLanguage: string;
  exportDirectory: string;
  autoSaveInterval: number;
  showNotifications: boolean;
  minimizeToTray: boolean;
  startupWithSystem: boolean;
  theme: string;
};

export type TranscriptionSettings = {
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
  beam_size: number;
  best_of: number;
  patience: number;
  temperature: number;
};

export type AudioSettings = {
  defaultDeviceId: string;
  sampleRate: number;
  vadEnabled: boolean;
  vadThresholdDb: number;
  noiseFiltering: boolean;
  echoCancellation: boolean;
  autoGainControl: boolean;
};

export type HotkeySettings = {
  enabled: boolean;
  key_combination: string;
  hold_mode: boolean;
  auto_inject: boolean;
  show_floating_window: boolean;
  floating_window_position: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right' | 'center';
  record_on_start: boolean;
  stop_on_release: boolean;
  copy_to_clipboard: boolean;
};

export type AdvancedSettings = {
  debugMode: boolean;
  logLevel: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';
  enableMetrics: boolean;
  maxLogFiles: number;
  experimentalStem: boolean;
  experimentalGpuAccel: boolean;
};

export type SettingsState = {
  general: GeneralSettings;
  transcription: TranscriptionSettings;
  audio: AudioSettings;
  hotkey: HotkeySettings;
  advanced: AdvancedSettings;
  version: number;
};
