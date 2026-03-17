/**
 * ASR Routing - Model selection utilities for capture sources
 * 
 * Provides functions to resolve and sync ASR model IDs between system audio
 * and microphone capture sources.
 */
import type { SettingsState } from '../config/settingsSchema';

export type CaptureSource = 'system' | 'microphone';

export function resolveSourceModelId(
  settings: SettingsState,
  captureSource: CaptureSource,
): string {
  return captureSource === 'system'
    ? settings.transcription.system_asr_model_id ||
        settings.transcription.default_asr_model_id ||
        settings.transcription.model_name
    : settings.transcription.microphone_asr_model_id ||
        settings.transcription.default_asr_model_id ||
        settings.transcription.model_name;
}

export function syncInheritedAsrModelIds(
  previous: SettingsState,
  next: SettingsState,
): SettingsState {
  const previousDefault = previous.transcription.default_asr_model_id;
  const nextDefault = next.transcription.default_asr_model_id;
  if (!nextDefault || !previousDefault || nextDefault === previousDefault) {
    return next;
  }

  const transcription = { ...next.transcription };
  if (!transcription.microphone_asr_model_id || transcription.microphone_asr_model_id === previousDefault) {
    transcription.microphone_asr_model_id = nextDefault;
  }
  if (!transcription.system_asr_model_id || transcription.system_asr_model_id === previousDefault) {
    transcription.system_asr_model_id = nextDefault;
  }

  return {
    ...next,
    transcription,
  };
}
