import { validateSettings, type SettingsState, DEFAULT_SETTINGS } from './settingsSchema';
import { CURRENT_SETTINGS_VERSION } from './settings';

// ============================================
// Settings Migration Utility
// ============================================
// Re-export for backward compatibility
export { CURRENT_SETTINGS_VERSION };

function mapRuntimeModelToCatalogId(modelName?: string): string {
  switch (modelName) {
    case 'tiny':
      return 'whisper-tiny';
    case 'small':
      return 'whisper-small';
    case 'large-v3':
      return 'whisper-large-v3';
    case 'turbo':
      return 'whisper-turbo';
    case 'medium':
    default:
      return 'whisper-medium';
  }
}

function normalizeSourceAwareSettings(data: Record<string, unknown>): Record<string, unknown> {
  const normalized = { ...data };
  const transcription = { ...((normalized.transcription as Record<string, unknown>) ?? {}) };
  const audio = { ...((normalized.audio as Record<string, unknown>) ?? {}) };
  const hotkey = { ...((normalized.hotkey as Record<string, unknown>) ?? {}) };
  const coach = { ...((normalized.coach as Record<string, unknown>) ?? {}) };

  const fallbackModel = (
    transcription.default_asr_model_id ??
    mapRuntimeModelToCatalogId(transcription.model_name as string | undefined)
  ) as string;
  const legacyHotkeyModel = hotkey.model_name
    ? mapRuntimeModelToCatalogId(hotkey.model_name as string)
    : undefined;

  transcription.default_asr_model_id = fallbackModel;
  transcription.transcription_mode =
    (transcription.transcription_mode as string | undefined) ?? 'dictation';
  transcription.refinement_profile =
    (transcription.refinement_profile as string | undefined) ?? 'raw';
  transcription.microphone_asr_model_id =
    (transcription.microphone_asr_model_id as string | undefined) ??
    legacyHotkeyModel ??
    fallbackModel;
  transcription.system_asr_model_id =
    (transcription.system_asr_model_id as string | undefined) ??
    fallbackModel;

  const captureSource = ((audio.default_capture_source as string | undefined) ??
    (audio.captureMode as string | undefined) ??
    'microphone') as 'microphone' | 'system';
  audio.default_capture_source = captureSource;
  audio.captureMode = captureSource;
  hotkey.capture_source =
    ((hotkey.capture_source as string | undefined) ?? captureSource) as 'microphone' | 'system';
  hotkey.microphone_key_combination =
    (hotkey.microphone_key_combination as string | undefined) ??
    (hotkey.key_combination as string | undefined) ??
    'Ctrl+Shift+T';
  hotkey.system_key_combination =
    (hotkey.system_key_combination as string | undefined) ?? 'CommandOrControl+Shift+Y';

  if ('model_name' in hotkey) {
    delete hotkey.model_name;
  }

  normalized.transcription = transcription;
  normalized.audio = audio;
  normalized.hotkey = hotkey;
  normalized.coach = {
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
      ...((coach.coach_overrides as Record<string, unknown>) ?? {}),
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
    ...coach,
  };
  return normalized;
}

// Migration functions for each version
const migrations: Record<number, (data: unknown) => unknown> = {
  // Version 1 -> 2: Add missing fields and normalize structure
  1: (data: unknown) => {
    const old = data as Record<string, unknown>;
    return {
      general: {
        defaultSessionTitle: (old.general as Record<string, unknown>)?.defaultSessionTitle ?? 'New Session',
        defaultLanguage: (old.general as Record<string, unknown>)?.defaultLanguage ?? 'auto',
        exportDirectory: (old.general as Record<string, unknown>)?.exportDirectory ?? '',
        autoSaveInterval: (old.general as Record<string, unknown>)?.autoSaveInterval ?? 30,
        showNotifications: (old.general as Record<string, unknown>)?.showNotifications ?? true,
        minimizeToTray: (old.general as Record<string, unknown>)?.minimizeToTray ?? true,
        startupWithSystem: (old.general as Record<string, unknown>)?.startupWithSystem ?? false,
        theme: (old.general as Record<string, unknown>)?.theme ?? 'light',
      },
      transcription: {
        model_name: (old.transcription as Record<string, unknown>)?.model_name ?? 'medium',
        default_asr_model_id: mapRuntimeModelToCatalogId((old.transcription as Record<string, unknown>)?.model_name as string | undefined),
        microphone_asr_model_id:
          mapRuntimeModelToCatalogId((old.hotkey as Record<string, unknown>)?.model_name as string | undefined) ??
          mapRuntimeModelToCatalogId((old.transcription as Record<string, unknown>)?.model_name as string | undefined),
        system_asr_model_id: mapRuntimeModelToCatalogId((old.transcription as Record<string, unknown>)?.model_name as string | undefined),
        refinement_mode: (old.transcription as Record<string, unknown>)?.refinement_mode ?? 'off',
        transcription_mode: (old.transcription as Record<string, unknown>)?.transcription_mode ?? 'dictation',
        compute_type: (old.transcription as Record<string, unknown>)?.compute_type ?? 'float16',
        chunk_duration: (old.transcription as Record<string, unknown>)?.chunk_duration ?? 1.6,
        overlap_ratio: (old.transcription as Record<string, unknown>)?.overlap_ratio ?? 0.2,
        vad_enabled: (old.transcription as Record<string, unknown>)?.vad_enabled ?? true,
        vad_threshold_db: (old.transcription as Record<string, unknown>)?.vad_threshold_db ?? -40,
        confidence_threshold: (old.transcription as Record<string, unknown>)?.confidence_threshold ?? 0.6,
        enable_filler_filter: (old.transcription as Record<string, unknown>)?.enable_filler_filter ?? true,
        enable_hallucination_filter: (old.transcription as Record<string, unknown>)?.enable_hallucination_filter ?? true,
        min_segment_length: (old.transcription as Record<string, unknown>)?.min_segment_length ?? 0.5,
        max_workers: (old.transcription as Record<string, unknown>)?.max_workers ?? 4,
        use_parallel_processing: (old.transcription as Record<string, unknown>)?.use_parallel_processing ?? true,
        preload_model: (old.transcription as Record<string, unknown>)?.preload_model ?? true,
        hotkey_optimized: (old.transcription as Record<string, unknown>)?.hotkey_optimized ?? false,
        beam_size: (old.transcription as Record<string, unknown>)?.beam_size ?? 5,
        best_of: (old.transcription as Record<string, unknown>)?.best_of ?? 5,
        patience: (old.transcription as Record<string, unknown>)?.patience ?? 1.0,
        temperature: (old.transcription as Record<string, unknown>)?.temperature ?? 0.0,
      },
      refiner: {
        selected_model_id: (old.refiner as Record<string, unknown>)?.selected_model_id ?? 'qwen2.5-3b-instruct',
        runtime_enabled: (old.refiner as Record<string, unknown>)?.runtime_enabled ?? false,
        cleanup_instructions: (old.refiner as Record<string, unknown>)?.cleanup_instructions ?? '',
        engine_preference: (old.refiner as Record<string, unknown>)?.engine_preference ?? 'llamacpp',
      },
      audio: {
        captureMode: (old.audio as Record<string, unknown>)?.captureMode ?? 'microphone',
        default_capture_source:
          (old.audio as Record<string, unknown>)?.default_capture_source ??
          (old.audio as Record<string, unknown>)?.captureMode ??
          'microphone',
        defaultDeviceId: (old.audio as Record<string, unknown>)?.defaultDeviceId ?? 'default',
        audio_backend: (old.audio as Record<string, unknown>)?.audio_backend ?? (old.audio as Record<string, unknown>)?.backend ?? 'auto',
        sampleRate: (old.audio as Record<string, unknown>)?.sampleRate ?? 16000,
        noiseFiltering: (old.audio as Record<string, unknown>)?.noiseFiltering ?? true,
        echoCancellation: (old.audio as Record<string, unknown>)?.echoCancellation ?? true,
        autoGainControl: (old.audio as Record<string, unknown>)?.autoGainControl ?? true,
        mute_openwispr_audio_during_dictation:
          (old.audio as Record<string, unknown>)?.mute_openwispr_audio_during_dictation ?? false,
      },
      hotkey: {
        enabled: (old.hotkey as Record<string, unknown>)?.enabled ?? false,
        key_combination: (old.hotkey as Record<string, unknown>)?.key_combination ?? 'Ctrl+Shift+T',
        microphone_key_combination:
          (old.hotkey as Record<string, unknown>)?.microphone_key_combination ??
          (old.hotkey as Record<string, unknown>)?.key_combination ??
          'Ctrl+Shift+T',
        system_key_combination:
          (old.hotkey as Record<string, unknown>)?.system_key_combination ??
          'CommandOrControl+Shift+Y',
        hold_mode: (old.hotkey as Record<string, unknown>)?.hold_mode ?? false,
        auto_inject: (old.hotkey as Record<string, unknown>)?.auto_inject ?? true,
        language: (old.hotkey as Record<string, unknown>)?.language ?? 'auto',
        capture_source:
          (old.hotkey as Record<string, unknown>)?.capture_source ??
          (old.audio as Record<string, unknown>)?.default_capture_source ??
          (old.audio as Record<string, unknown>)?.captureMode ??
          'microphone',
        device_id: (old.hotkey as Record<string, unknown>)?.device_id ?? 'default',
        finish_mode_default: (old.hotkey as Record<string, unknown>)?.finish_mode_default ?? 'finish_and_paste',
        show_floating_window: (old.hotkey as Record<string, unknown>)?.show_floating_window ?? true,
        floating_window_position: (old.hotkey as Record<string, unknown>)?.floating_window_position ?? 'bottom-right',
        record_on_start: (old.hotkey as Record<string, unknown>)?.record_on_start ?? false,
        stop_on_release: (old.hotkey as Record<string, unknown>)?.stop_on_release ?? false,
        copy_to_clipboard: (old.hotkey as Record<string, unknown>)?.copy_to_clipboard ?? true,
      },
      advanced: {
        debugMode: (old.advanced as Record<string, unknown>)?.debugMode ?? false,
        logLevel: (old.advanced as Record<string, unknown>)?.logLevel ?? 'INFO',
        enableMetrics: (old.advanced as Record<string, unknown>)?.enableMetrics ?? true,
        maxLogFiles: (old.advanced as Record<string, unknown>)?.maxLogFiles ?? 10,
        experimentalStem: (old.advanced as Record<string, unknown>)?.experimentalStem ?? false,
        experimentalGpuAccel: (old.advanced as Record<string, unknown>)?.experimentalGpuAccel ?? true,
      },
      version: 3,
    };
  },
  // Version 3 -> 4: Rename backend to audio_backend, remove duplicate VAD settings from audio
  3: (data: unknown) => {
    const old = data as Record<string, unknown>;
    const oldAudio = old.audio as Record<string, unknown>;
    return {
      ...old,
      audio: {
        captureMode: oldAudio?.captureMode ?? 'microphone',
        default_capture_source: oldAudio?.default_capture_source ?? oldAudio?.captureMode ?? 'microphone',
        defaultDeviceId: oldAudio?.defaultDeviceId ?? 'default',
        audio_backend: oldAudio?.audio_backend ?? oldAudio?.backend ?? 'auto',
        sampleRate: oldAudio?.sampleRate ?? 16000,
        noiseFiltering: oldAudio?.noiseFiltering ?? true,
        echoCancellation: oldAudio?.echoCancellation ?? true,
        autoGainControl: oldAudio?.autoGainControl ?? true,
        mute_openwispr_audio_during_dictation:
          oldAudio?.mute_openwispr_audio_during_dictation ?? false,
      },
      version: 4,
    };
  },
  4: (data: unknown) => {
    const old = data as Record<string, unknown>;
    return {
      ...old,
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
        ...((old.coach as Record<string, unknown>) ?? {}),
      },
      version: 5,
    };
  },
};

/**
 * Migrate settings from any version to current version
 */
export function migrateSettings(data: unknown): { success: true; data: SettingsState } | { success: false; error: string } {
  // If data is null or undefined, return defaults
  if (!data || typeof data !== 'object') {
    return { success: true, data: DEFAULT_SETTINGS };
  }

  const obj = data as Record<string, unknown>;
  const currentVersion = (obj.version as number) || 1;
  const normalizedCurrent = normalizeSourceAwareSettings(obj);

  // If already at current version, just validate
  if (currentVersion >= CURRENT_SETTINGS_VERSION) {
    const validation = validateSettings(normalizedCurrent);
    if (validation.success) {
      return { success: true, data: validation.data };
    }
    // Validation failed but we have data - try to merge with defaults
    return { success: true, data: mergeWithDefaults(normalizedCurrent) };
  }

  // Apply migrations sequentially
  let migrated: Record<string, unknown> = normalizedCurrent;
  for (let v = currentVersion; v < CURRENT_SETTINGS_VERSION; v++) {
    const migration = migrations[v];
    if (migration) {
      migrated = migration(migrated) as Record<string, unknown>;
    }
  }
  migrated = normalizeSourceAwareSettings(migrated);

  // Final validation
  const validation = validateSettings(migrated);
  if (validation.success) {
    return { success: true, data: validation.data };
  }

  // If validation still fails, merge with defaults as fallback
  return { success: true, data: mergeWithDefaults(migrated) };
}

/**
 * Merge partial settings with defaults
 */
function mergeWithDefaults(partial: Record<string, unknown>): SettingsState {
  const typedPartial = partial as Partial<SettingsState>;
  return {
    general: { ...DEFAULT_SETTINGS.general, ...(typedPartial.general || {}) },
    transcription: { ...DEFAULT_SETTINGS.transcription, ...(typedPartial.transcription || {}) },
    refiner: { ...DEFAULT_SETTINGS.refiner, ...(typedPartial.refiner || {}) },
    audio: { ...DEFAULT_SETTINGS.audio, ...(typedPartial.audio || {}) },
    hotkey: { ...DEFAULT_SETTINGS.hotkey, ...(typedPartial.hotkey || {}) },
    coach: { ...DEFAULT_SETTINGS.coach, ...(typedPartial.coach || {}) },
    history: { ...DEFAULT_SETTINGS.history, ...(typedPartial.history || {}) },
    dictionary: { ...DEFAULT_SETTINGS.dictionary, ...(typedPartial.dictionary || {}) },
    snippets: { ...DEFAULT_SETTINGS.snippets, ...(typedPartial.snippets || {}) },
    style: { ...DEFAULT_SETTINGS.style, ...(typedPartial.style || {}) },
    advanced: { ...DEFAULT_SETTINGS.advanced, ...(typedPartial.advanced || {}) },
    version: CURRENT_SETTINGS_VERSION,
  } as SettingsState;
}

/**
 * Validate and fix settings on load
 * Adds missing fields with defaults and removes unknown fields
 */
export function sanitizeSettings(data: unknown): SettingsState {
  const migration = migrateSettings(data);
  if (migration.success) {
    return migration.data;
  }
  return DEFAULT_SETTINGS;
}

/**
 * Check if settings need migration
 */
export function needsMigration(data: unknown): boolean {
  if (!data || typeof data !== 'object') return true;
  const version = (data as Record<string, unknown>).version as number | undefined;
  return !version || version < CURRENT_SETTINGS_VERSION;
}

/**
 * Get settings version
 */
export function getSettingsVersion(data: unknown): number {
  if (!data || typeof data !== 'object') return 0;
  return ((data as Record<string, unknown>).version as number) || 1;
}
