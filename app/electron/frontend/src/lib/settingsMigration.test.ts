import { describe, expect, it } from 'vitest';
import { sanitizeSettings } from '../config/settingsMigration';

describe('settingsMigration source-aware defaults', () => {
  it('maps legacy hotkey model_name into microphone_asr_model_id', () => {
    const migrated = sanitizeSettings({
      general: {},
      transcription: {
        default_asr_model_id: 'whisper-large-v3',
      },
      audio: {
        captureMode: 'system',
      },
      hotkey: {
        model_name: 'small',
      },
      advanced: {},
      version: 4,
    });

    expect(migrated.audio.captureMode).toBe('system');
    expect(migrated.audio.default_capture_source).toBe('system');
    expect(migrated.transcription.microphone_asr_model_id).toBe('whisper-small');
    expect(migrated.transcription.system_asr_model_id).toBe('whisper-large-v3');
    expect('model_name' in migrated.hotkey).toBe(false);
  });

  it('defaults capture source to microphone for empty settings', () => {
    const migrated = sanitizeSettings({});

    expect(migrated.audio.captureMode).toBe('microphone');
    expect(migrated.audio.default_capture_source).toBe('microphone');
    expect(migrated.transcription.microphone_asr_model_id).toBeTruthy();
    expect(migrated.transcription.system_asr_model_id).toBeTruthy();
  });
});
