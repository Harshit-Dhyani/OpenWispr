import type {
  Device,
  SessionSummary,
  Segment,
  Formula,
  Health,
  SnapshotPayload,
  ModelCatalogEntry,
  ModelInstallState,
  ModelDownloadState,
  ModelCatalogPayload,
  HotkeyState,
  HotkeySession,
  SystemProfile,
  GPUInfo,
  CPUInfo,
  StorageInfo,
  Word,
} from '../types/api';
import type { SettingsState } from '../config/settingsSchema';
import { DEFAULT_SETTINGS } from '../config/settingsSchema';

// ============================================
// Device Factories
// ============================================

export const createMockDevice = (overrides: Partial<Device> = {}): Device => ({
  id: 'device-1',
  name: 'Test Microphone',
  kind: 'microphone',
  is_loopback: false,
  channels: 2,
  sample_rate: 16000,
  backend_candidates: ['pyaudio', 'soundcard'],
  is_input: true,
  is_output: false,
  supports_loopback: null,
  driver: 'default',
  ...overrides,
});

export const createMockLoopbackDevice = (overrides: Partial<Device> = {}): Device => ({
  id: 'loopback-1',
  name: 'System Audio',
  kind: 'loopback',
  is_loopback: true,
  channels: 2,
  sample_rate: 48000,
  backend_candidates: ['soundcard'],
  is_input: false,
  is_output: true,
  supports_loopback: true,
  driver: 'wasapi',
  ...overrides,
});

// ============================================
// Session Factories
// ============================================

export const createMockSessionSummary = (overrides: Partial<SessionSummary> = {}): SessionSummary => ({
  session_id: 'test-session-123',
  title: 'Test Session',
  output_dir: '/tmp/sessions',
  model_name: 'small',
  language_mode: 'en',
  device_id: 'device-1',
  live_mode: 'balanced',
  execution_mode: 'auto',
  started_at: new Date().toISOString(),
  status: 'running',
  documents: [],
  segment_count: 0,
  formula_count: 0,
  review_count: 0,
  suppressed_count: 0,
  ...overrides,
});

// ============================================
// Segment Factories
// ============================================

export const createMockWord = (overrides: Partial<Word> = {}): Word => ({
  text: 'test',
  start: 0,
  end: 1,
  confidence: 0.9,
  ...overrides,
});

export const createMockSegment = (overrides: Partial<Segment> = {}): Segment => ({
  id: `segment-${Date.now()}`,
  start: 0,
  end: 5,
  text: 'Test transcription segment',
  display_text: 'Test transcription segment',
  language: 'en',
  avg_logprob: -0.5,
  no_speech_prob: 0.1,
  compression_ratio: 1.2,
  confidence: 0.85,
  review_flag: false,
  review_reasons: [],
  suppressed: false,
  suppression_reasons: [],
  quality_label: 'good',
  script_mismatch: false,
  words: [
    createMockWord({ text: 'Test', start: 0, end: 1, confidence: 0.9 }),
    createMockWord({ text: 'transcription', start: 1, end: 3, confidence: 0.85 }),
    createMockWord({ text: 'segment', start: 3, end: 5, confidence: 0.88 }),
  ],
  latency_ms: 150,
  is_partial: false,
  ...overrides,
});

export const createMockPartialSegment = (overrides: Partial<Segment> = {}): Segment =>
  createMockSegment({
    id: `partial-${Date.now()}`,
    is_partial: true,
    text: 'Partial...',
    display_text: 'Partial...',
    ...overrides,
  });

export const createMockSuppressedSegment = (overrides: Partial<Segment> = {}): Segment =>
  createMockSegment({
    id: `suppressed-${Date.now()}`,
    suppressed: true,
    suppression_reasons: ['low_confidence'],
    ...overrides,
  });

export const createMockReviewSegment = (overrides: Partial<Segment> = {}): Segment =>
  createMockSegment({
    id: `review-${Date.now()}`,
    review_flag: true,
    review_reasons: ['formula_detected', 'low_confidence'],
    ...overrides,
  });

// ============================================
// Formula Factories
// ============================================

export const createMockFormula = (overrides: Partial<Formula> = {}): Formula => ({
  expression: 'E = mc^2',
  timestamp_start: 0,
  timestamp_end: 5,
  context: 'physics equation',
  confidence: 0.95,
  parseable: true,
  review_flag: false,
  reasons: [],
  variables: ['E', 'm', 'c'],
  units: ['J', 'kg', 'm/s'],
  ...overrides,
});

// ============================================
// Health Factories
// ============================================

export const createMockHealth = (overrides: Partial<Health> = {}): Health => ({
  audio_stream_active: true,
  gpu_mode: 'cuda',
  execution_mode: 'auto',
  model_runtime_device: 'cuda',
  last_transcript_at: new Date().toISOString(),
  dropped_frames: 0,
  queue_depth: 2,
  dropped_stt_chunks: 0,
  stt_backpressure_state: 'normal',
  estimated_backlog_seconds: 0,
  last_error: null,
  last_warning: null,
  ...overrides,
});

// ============================================
// Snapshot Factories
// ============================================

export const createMockSnapshot = (overrides: Partial<SnapshotPayload> = {}): SnapshotPayload => ({
  session: createMockSessionSummary(),
  transcript: [createMockSegment()],
  suppressed_transcript: [],
  formulas: [],
  needs_review: [],
  health: createMockHealth(),
  meter_value: 0.5,
  available_models: ['tiny', 'base', 'small', 'medium', 'large-v3'],
  available_languages: ['auto', 'en', 'es', 'fr', 'de'],
  available_live_modes: ['realtime', 'low_latency', 'balanced', 'high_accuracy'],
  available_execution_modes: ['auto', 'gpu_only', 'cpu_only'],
  runtime_revision: 1,
  loading: false,
  loading_message: '',
  model_cache: {},
  ...overrides,
});

// ============================================
// Model Catalog Factories
// ============================================

export const createMockModelCatalogEntry = (overrides: Partial<ModelCatalogEntry> = {}): ModelCatalogEntry => ({
  id: 'whisper-small',
  display_name: 'Whisper Small',
  category: 'asr',
  family: 'whisper',
  engine: 'faster-whisper',
  size_gb_estimate: 0.5,
  recommended_vram_gb: 2,
  speed_tier: 'balanced',
  license_note: 'MIT',
  description_short: 'Balanced speed and accuracy',
  why_choose_this: 'Good balance for most use cases',
  runtime_model_name: 'small',
  enabled_runtime: true,
  installed: true,
  verified: true,
  recommended: true,
  download_artifacts: [],
  default_runtime_config: {},
  ...overrides,
});

export const createMockModelInstallState = (overrides: Partial<ModelInstallState> = {}): ModelInstallState => ({
  model_id: 'whisper-small',
  installed: true,
  verified: true,
  install_path: '/models/whisper-small',
  size_bytes: 500000000,
  last_checked_at: Date.now(),
  ...overrides,
});

export const createMockModelDownloadState = (overrides: Partial<ModelDownloadState> = {}): ModelDownloadState => ({
  model_id: 'whisper-small',
  status: 'idle',
  bytes_downloaded: 0,
  total_bytes: 500000000,
  progress: 0,
  speed_bytes_per_sec: 0,
  error: null,
  ...overrides,
});

export const createMockModelCatalogPayload = (overrides: Partial<ModelCatalogPayload> = {}): ModelCatalogPayload => ({
  catalog: [createMockModelCatalogEntry()],
  installed: [createMockModelInstallState()],
  selected_asr_model_id: 'whisper-small',
  selected_refiner_model_id: 'qwen2.5-3b-instruct',
  refinement_mode: 'off',
  refinement_profile: 'raw',
  recommendations: ['whisper-small'],
  ...overrides,
});

// ============================================
// Hotkey Factories
// ============================================

export const createMockHotkeySession = (overrides: Partial<HotkeySession> = {}): HotkeySession => ({
  session_id: 'hotkey-session-1',
  is_recording: false,
  status: 'idle',
  last_activated_at: null,
  total_activations: 0,
  current_text: '',
  duration_ms: 0,
  ...overrides,
});

export const createMockHotkeyState = (overrides: Partial<HotkeyState> = {}): HotkeyState => ({
  config: {
    enabled: false,
    key_combination: 'Ctrl+Shift+Space',
    hold_mode: false,
    auto_inject: true,
    language: 'en',
    capture_source: 'microphone',
    microphone_key_combination: 'Ctrl+Shift+Space',
    system_key_combination: 'Ctrl+Shift+Y',
    device_id: 'default',
    finish_mode_default: 'finish_and_paste',
    enable_refiner_on_stop: false,
    save_debug_wav: false,
    show_floating_window: true,
    floating_window_position: 'bottom-right',
    record_on_start: false,
    stop_on_release: false,
    copy_to_clipboard: true,
  },
  session: createMockHotkeySession(),
  is_registered: false,
  error: null,
  ...overrides,
});

// ============================================
// System Profile Factories
// ============================================

export const createMockGPUInfo = (overrides: Partial<GPUInfo> = {}): GPUInfo => ({
  available: true,
  name: 'NVIDIA RTX 4090',
  vram_gb: 24,
  can_run_large: true,
  can_run_medium: true,
  cuda_version: '12.1',
  compute_capability: '8.9',
  ...overrides,
});

export const createMockCPUInfo = (overrides: Partial<CPUInfo> = {}): CPUInfo => ({
  cores: 16,
  threads: 32,
  ram_gb: 64,
  can_parallel: true,
  architecture: 'x86_64',
  ...overrides,
});

export const createMockStorageInfo = (overrides: Partial<StorageInfo> = {}): StorageInfo => ({
  free_gb: 500,
  total_gb: 1000,
  can_download_large: true,
  ssd_available: true,
  ...overrides,
});

export const createMockSystemProfile = (overrides: Partial<SystemProfile> = {}): SystemProfile => ({
  gpu: createMockGPUInfo(),
  cpu: createMockCPUInfo(),
  storage: createMockStorageInfo(),
  platform: 'win32',
  detected_at: new Date().toISOString(),
  recommended_quality: 'maximum',
  recommended_preset: 'high_quality',
  ...overrides,
});

// ============================================
// Settings Factories
// ============================================

export const createMockSettings = (overrides: Partial<SettingsState> = {}): SettingsState => ({
  ...DEFAULT_SETTINGS,
  ...overrides,
  general: { ...DEFAULT_SETTINGS.general, ...overrides.general },
  transcription: { ...DEFAULT_SETTINGS.transcription, ...overrides.transcription },
  refiner: { ...DEFAULT_SETTINGS.refiner, ...overrides.refiner },
  audio: { ...DEFAULT_SETTINGS.audio, ...overrides.audio },
  hotkey: { ...DEFAULT_SETTINGS.hotkey, ...overrides.hotkey },
  coach: { ...DEFAULT_SETTINGS.coach, ...overrides.coach },
  history: { ...DEFAULT_SETTINGS.history, ...overrides.history },
  dictionary: { ...DEFAULT_SETTINGS.dictionary, ...overrides.dictionary },
  snippets: { ...DEFAULT_SETTINGS.snippets, ...overrides.snippets },
  style: { ...DEFAULT_SETTINGS.style, ...overrides.style },
  advanced: { ...DEFAULT_SETTINGS.advanced, ...overrides.advanced },
});

// ============================================
// Event Factories
// ============================================

export const createMockSegmentEvent = (segment: Segment = createMockSegment()) => ({
  type: 'segment' as const,
  payload: segment,
  timestamp: new Date().toISOString(),
});

export const createMockHealthEvent = (health: Health = createMockHealth(), meterValue: number = 0.5) => ({
  type: 'health' as const,
  payload: { health, meter_value: meterValue },
  timestamp: new Date().toISOString(),
});

export const createMockStateEvent = (snapshot: SnapshotPayload = createMockSnapshot()) => ({
  type: 'state' as const,
  payload: snapshot,
  timestamp: new Date().toISOString(),
});

export const createMockFormulasEvent = (formulas: Formula[] = [createMockFormula()]) => ({
  type: 'formulas' as const,
  payload: formulas,
  timestamp: new Date().toISOString(),
});

export const createMockLoadingEvent = (loading: boolean, message: string = '') => ({
  type: 'loading' as const,
  payload: { loading, message },
  timestamp: new Date().toISOString(),
});

// ============================================
// Test Data Collections
// ============================================

export const MOCK_DEVICES: Device[] = [
  createMockDevice({ id: 'mic-1', name: 'Built-in Microphone' }),
  createMockDevice({ id: 'mic-2', name: 'USB Microphone' }),
  createMockLoopbackDevice({ id: 'loopback-1', name: 'System Audio' }),
];

export const MOCK_MODELS: ModelCatalogEntry[] = [
  createMockModelCatalogEntry({ id: 'tiny', display_name: 'Tiny', size_gb_estimate: 0.075, speed_tier: 'fast' }),
  createMockModelCatalogEntry({ id: 'base', display_name: 'Base', size_gb_estimate: 0.15, speed_tier: 'fast' }),
  createMockModelCatalogEntry({ id: 'small', display_name: 'Small', size_gb_estimate: 0.5, speed_tier: 'balanced' }),
  createMockModelCatalogEntry({ id: 'medium', display_name: 'Medium', size_gb_estimate: 1.5, speed_tier: 'quality' }),
  createMockModelCatalogEntry({ id: 'large-v3', display_name: 'Large v3', size_gb_estimate: 3, speed_tier: 'quality' }),
];

export const MOCK_SEGMENTS: Segment[] = [
  createMockSegment({ id: 'seg-1', text: 'First segment', start: 0, end: 3 }),
  createMockSegment({ id: 'seg-2', text: 'Second segment', start: 3, end: 6 }),
  createMockSegment({ id: 'seg-3', text: 'Third segment', start: 6, end: 9 }),
];

export const MOCK_FORMULAS: Formula[] = [
  createMockFormula({ expression: 'E = mc^2', context: 'Physics' }),
  createMockFormula({ expression: 'F = ma', context: 'Newton Second Law' }),
  createMockFormula({ expression: 'a^2 + b^2 = c^2', context: 'Pythagorean theorem' }),
];

// ============================================
// Utility Functions for Tests
// ============================================

export function createSequenceOfSegments(count: number, startTime = 0): Segment[] {
  return Array.from({ length: count }, (_, i) =>
    createMockSegment({
      id: `seq-${i}`,
      start: startTime + i * 3,
      end: startTime + i * 3 + 3,
      text: `Segment ${i + 1}`,
    })
  );
}

export function createDeviceList(count: number, type: 'microphone' | 'loopback' = 'microphone'): Device[] {
  return Array.from({ length: count }, (_, i) =>
    type === 'microphone'
      ? createMockDevice({ id: `mic-${i}`, name: `Microphone ${i + 1}` })
      : createMockLoopbackDevice({ id: `loopback-${i}`, name: `Loopback ${i + 1}` })
  );
}

export function createModelList(count: number): ModelCatalogEntry[] {
  const templates = ['tiny', 'base', 'small', 'medium', 'large-v3'];
  return Array.from({ length: count }, (_, i) =>
    createMockModelCatalogEntry({
      id: templates[i % templates.length] || `model-${i}`,
      display_name: `Model ${i + 1}`,
    })
  );
}
