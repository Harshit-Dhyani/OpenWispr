import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  EMPTY_MODEL_MANAGER_STATE,
  applyModelCatalogPayload,
  applyModelDownloadEvent,
  getRecommendedModels,
  isModelInstalled,
  getModelById,
  type ModelManagerState,
} from './modelRegistry';
import type { ModelCatalogPayload, ModelDownloadState } from '../types/api';
import {
  createMockModelCatalogEntry,
  createMockModelInstallState,
  createMockModelCatalogPayload,
} from '../test/factories';

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
      id: 'qwen2.5-3b-instruct',
      display_name: 'Qwen 2.5 3B',
      category: 'refiner',
      family: 'qwen',
      engine: 'llamacpp',
      size_gb_estimate: 1.93,
      recommended_vram_gb: 4,
      speed_tier: 'fast',
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
  selected_refiner_model_id: 'qwen2.5-3b-instruct',
  refinement_mode: 'strict',
  recommendations: ['whisper-medium'],
};

describe('model registry', () => {
  it('hydrates from the model catalog payload', () => {
    const state = applyModelCatalogPayload(EMPTY_MODEL_MANAGER_STATE, basePayload);
    expect(state.catalog).toHaveLength(2);
    expect(state.installed).toHaveLength(1);
    expect(state.selectedAsrModelId).toBe('whisper-medium');
    expect(state.selectedRefinerModelId).toBe('qwen2.5-3b-instruct');
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

  it('returns empty model manager state by default', () => {
    expect(EMPTY_MODEL_MANAGER_STATE.catalog).toEqual([]);
    expect(EMPTY_MODEL_MANAGER_STATE.installed).toEqual([]);
    expect(EMPTY_MODEL_MANAGER_STATE.downloads).toEqual({});
    expect(EMPTY_MODEL_MANAGER_STATE.selectedAsrModelId).toBe('');
    expect(EMPTY_MODEL_MANAGER_STATE.selectedRefinerModelId).toBe('');
  });

  it('applies catalog from factory-generated payload', () => {
    const payload = createMockModelCatalogPayload({
      catalog: [
        createMockModelCatalogEntry({ id: 'model-1' }),
        createMockModelCatalogEntry({ id: 'model-2' }),
      ],
    });

    const result = applyModelCatalogPayload(EMPTY_MODEL_MANAGER_STATE, payload);

    expect(result.catalog).toHaveLength(2);
    expect(result.catalog[0].id).toBe('model-1');
  });

  it('preserves existing downloads state when applying payload', () => {
    const stateWithDownload: ModelManagerState = {
      ...EMPTY_MODEL_MANAGER_STATE,
      downloads: {
        'model-1': {
          model_id: 'model-1',
          status: 'downloading',
          bytes_downloaded: 500000,
          total_bytes: 1000000,
          progress: 50,
          speed_bytes_per_sec: 100000,
          error: null,
        },
      },
    };

    const payload = createMockModelCatalogPayload();
    const result = applyModelCatalogPayload(stateWithDownload, payload);

    expect(result.downloads['model-1']?.progress).toBe(50);
  });

  it('handles download started event', () => {
    const result = applyModelDownloadEvent(
      EMPTY_MODEL_MANAGER_STATE,
      'model-download-started',
      { model_id: 'model-1', total_bytes: 1000000 }
    );

    expect(result.downloads['model-1']).toBeDefined();
    expect(result.downloads['model-1']?.status).toBe('downloading');
  });

  it('handles download error event', () => {
    const state = applyModelDownloadEvent(
      EMPTY_MODEL_MANAGER_STATE,
      'model-download-started',
      { model_id: 'model-1', total_bytes: 1000000 }
    );

    const result = applyModelDownloadEvent(
      state,
      'model-download-error',
      { model_id: 'model-1', error: 'Network error' }
    );

    expect(result.downloads['model-1']?.status).toBe('error');
    expect(result.downloads['model-1']?.error).toBe('Network error');
  });

  it('handles download cancelled event', () => {
    const state = applyModelDownloadEvent(
      EMPTY_MODEL_MANAGER_STATE,
      'model-download-started',
      { model_id: 'model-1' }
    );

    const result = applyModelDownloadEvent(
      state,
      'model-download-cancelled',
      { model_id: 'model-1' }
    );

    expect(result.downloads['model-1']?.status).toBe('cancelled');
  });

  it('clears download after completion', () => {
    const state = applyModelDownloadEvent(
      EMPTY_MODEL_MANAGER_STATE,
      'model-download-started',
      { model_id: 'model-1' }
    );

    const result = applyModelDownloadEvent(
      state,
      'model-download-completed',
      { model_id: 'model-1', install_path: '/models/model-1' }
    );

    expect(result.downloads['model-1']).toBeUndefined();
  });

  it('returns recommended models', () => {
    const state: ModelManagerState = {
      ...EMPTY_MODEL_MANAGER_STATE,
      catalog: [
        createMockModelCatalogEntry({ id: 'rec-1', recommended: true }),
        createMockModelCatalogEntry({ id: 'not-rec', recommended: false }),
        createMockModelCatalogEntry({ id: 'rec-2', recommended: true }),
      ],
      installed: [],
      downloads: {},
      selectedAsrModelId: '',
      selectedRefinerModelId: '',
      refinementMode: 'off',
    };

    const recommended = getRecommendedModels(state);

    expect(recommended).toHaveLength(2);
    expect(recommended.map(m => m.id)).toContain('rec-1');
    expect(recommended.map(m => m.id)).toContain('rec-2');
  });

  it('checks if model is installed', () => {
    const state: ModelManagerState = {
      ...EMPTY_MODEL_MANAGER_STATE,
      catalog: [],
      installed: [
        createMockModelInstallState({ model_id: 'installed-model', installed: true }),
        createMockModelInstallState({ model_id: 'not-installed', installed: false }),
      ],
      downloads: {},
      selectedAsrModelId: '',
      selectedRefinerModelId: '',
      refinementMode: 'off',
    };

    expect(isModelInstalled(state, 'installed-model')).toBe(true);
    expect(isModelInstalled(state, 'not-installed')).toBe(false);
    expect(isModelInstalled(state, 'unknown')).toBe(false);
  });

  it('gets model by ID', () => {
    const state: ModelManagerState = {
      ...EMPTY_MODEL_MANAGER_STATE,
      catalog: [
        createMockModelCatalogEntry({ id: 'model-1', display_name: 'Test Model' }),
      ],
      installed: [],
      downloads: {},
      selectedAsrModelId: '',
      selectedRefinerModelId: '',
      refinementMode: 'off',
    };

    const model = getModelById(state, 'model-1');

    expect(model).toBeDefined();
    expect(model?.display_name).toBe('Test Model');
  });

  it('returns undefined for unknown model ID', () => {
    const model = getModelById(EMPTY_MODEL_MANAGER_STATE, 'unknown');
    expect(model).toBeUndefined();
  });

  it('ignores unknown download events', () => {
    const result = applyModelDownloadEvent(
      EMPTY_MODEL_MANAGER_STATE,
      'unknown-event' as Parameters<typeof applyModelDownloadEvent>[1],
      { model_id: 'model-1' }
    );

    expect(result).toEqual(EMPTY_MODEL_MANAGER_STATE);
  });
});
