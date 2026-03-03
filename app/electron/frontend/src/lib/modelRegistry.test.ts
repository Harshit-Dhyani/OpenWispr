import { describe, expect, it } from 'vitest';
import {
  EMPTY_MODEL_MANAGER_STATE,
  applyModelCatalogPayload,
  applyModelDownloadEvent,
} from './modelRegistry';
import type { ModelCatalogPayload, ModelDownloadState } from '../types/api';

const basePayload: ModelCatalogPayload = {
  catalog: [
    {
      id: 'whisper-medium',
      display_name: 'Whisper Medium',
      category: 'asr',
      family: 'whisper',
      engine: 'faster-whisper',
      size_gb_estimate: 1.5,
      recommended_vram_gb: 5,
      speed_tier: 'balanced',
      license_note: 'test',
      description_short: 'default',
      why_choose_this: 'balanced',
      runtime_model_name: 'medium',
      enabled_runtime: true,
      installed: true,
      verified: true,
      recommended: true,
      download_artifacts: [],
      default_runtime_config: {},
    },
    {
      id: 'qwen2.5-7b-instruct',
      display_name: 'Qwen 2.5 7B',
      category: 'refiner',
      family: 'qwen',
      engine: 'llamacpp',
      size_gb_estimate: 4.7,
      recommended_vram_gb: 8,
      speed_tier: 'balanced',
      license_note: 'test',
      description_short: 'refiner',
      why_choose_this: 'default',
      runtime_model_name: null,
      enabled_runtime: false,
      installed: false,
      verified: false,
      recommended: false,
      download_artifacts: [],
      default_runtime_config: {},
    },
  ],
  installed: [
    {
      model_id: 'whisper-medium',
      installed: true,
      verified: true,
      install_path: 'C:/models/asr/whisper-medium',
      size_bytes: 123,
      last_checked_at: Date.now(),
    },
  ],
  selected_asr_model_id: 'whisper-medium',
  selected_refiner_model_id: 'qwen2.5-7b-instruct',
  refinement_mode: 'strict',
  recommendations: ['whisper-medium'],
};

describe('model registry', () => {
  it('hydrates from the model catalog payload', () => {
    const state = applyModelCatalogPayload(EMPTY_MODEL_MANAGER_STATE, basePayload);
    expect(state.catalog).toHaveLength(2);
    expect(state.installed).toHaveLength(1);
    expect(state.selectedAsrModelId).toBe('whisper-medium');
    expect(state.selectedRefinerModelId).toBe('qwen2.5-7b-instruct');
    expect(state.refinementMode).toBe('strict');
  });

  it('tracks download state transitions', () => {
    const downloading: ModelDownloadState = {
      model_id: 'whisper-medium',
      status: 'downloading',
      bytes_downloaded: 50,
      total_bytes: 100,
      progress: 50,
      speed_bytes_per_sec: 20,
      error: null,
    };
    const completed: ModelDownloadState = {
      ...downloading,
      status: 'completed',
      bytes_downloaded: 100,
      progress: 100,
      speed_bytes_per_sec: 0,
    };

    const downloadingState = applyModelDownloadEvent(
      EMPTY_MODEL_MANAGER_STATE,
      'model-download-progress',
      downloading,
    );
    expect(downloadingState.downloads['whisper-medium']).toMatchObject({
      status: 'downloading',
      progress: 50,
    });

    const completedState = applyModelDownloadEvent(
      downloadingState,
      'model-download-completed',
      completed,
    );
    expect(completedState.downloads['whisper-medium']).toMatchObject({
      status: 'completed',
      progress: 100,
    });
  });
});
