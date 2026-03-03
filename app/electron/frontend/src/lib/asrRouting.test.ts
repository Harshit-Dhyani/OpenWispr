import { describe, expect, it } from 'vitest';
import { DEFAULT_SETTINGS } from './settingsSchema';
import { resolveSourceModelId, syncInheritedAsrModelIds } from './asrRouting';

describe('asrRouting', () => {
  it('resolves microphone and system models from source-specific settings', () => {
    const settings = {
      ...DEFAULT_SETTINGS,
      transcription: {
        ...DEFAULT_SETTINGS.transcription,
        default_asr_model_id: 'whisper-medium',
        microphone_asr_model_id: 'whisper-tiny',
        system_asr_model_id: 'whisper-large-v3-turbo',
      },
    };

    expect(resolveSourceModelId(settings, 'microphone')).toBe('whisper-tiny');
    expect(resolveSourceModelId(settings, 'system')).toBe('whisper-large-v3-turbo');
  });

  it('propagates a new default model to source-specific ids that still inherit the default', () => {
    const previous = {
      ...DEFAULT_SETTINGS,
      transcription: {
        ...DEFAULT_SETTINGS.transcription,
        default_asr_model_id: 'whisper-medium',
        microphone_asr_model_id: 'whisper-medium',
        system_asr_model_id: 'whisper-medium',
      },
    };
    const next = {
      ...previous,
      transcription: {
        ...previous.transcription,
        default_asr_model_id: 'whisper-tiny',
      },
    };

    const synced = syncInheritedAsrModelIds(previous, next);

    expect(synced.transcription.microphone_asr_model_id).toBe('whisper-tiny');
    expect(synced.transcription.system_asr_model_id).toBe('whisper-tiny');
  });

  it('preserves explicit source-specific overrides when the default changes', () => {
    const previous = {
      ...DEFAULT_SETTINGS,
      transcription: {
        ...DEFAULT_SETTINGS.transcription,
        default_asr_model_id: 'whisper-medium',
        microphone_asr_model_id: 'whisper-tiny',
        system_asr_model_id: 'whisper-medium',
      },
    };
    const next = {
      ...previous,
      transcription: {
        ...previous.transcription,
        default_asr_model_id: 'whisper-small',
      },
    };

    const synced = syncInheritedAsrModelIds(previous, next);

    expect(synced.transcription.microphone_asr_model_id).toBe('whisper-tiny');
    expect(synced.transcription.system_asr_model_id).toBe('whisper-small');
  });
});
