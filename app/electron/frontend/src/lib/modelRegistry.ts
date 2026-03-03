import type { ModelCatalogEntry, ModelCatalogPayload, ModelDownloadState, ModelInstallState } from '../types/api';

export type ModelManagerState = {
  catalog: ModelCatalogEntry[];
  installed: ModelInstallState[];
  downloads: Record<string, ModelDownloadState>;
  selectedAsrModelId: string;
  selectedRefinerModelId: string;
  refinementMode: 'off' | 'strict' | 'polished';
};

export const EMPTY_MODEL_MANAGER_STATE: ModelManagerState = {
  catalog: [],
  installed: [],
  downloads: {},
  selectedAsrModelId: 'whisper-medium',
  selectedRefinerModelId: 'qwen2.5-7b-instruct',
  refinementMode: 'off',
};

export function applyModelCatalogPayload(
  state: ModelManagerState,
  payload: ModelCatalogPayload,
): ModelManagerState {
  return {
    ...state,
    catalog: payload.catalog,
    installed: payload.installed,
    selectedAsrModelId: payload.selected_asr_model_id,
    selectedRefinerModelId: payload.selected_refiner_model_id,
    refinementMode: payload.refinement_mode,
  };
}

export function applyModelDownloadEvent(
  state: ModelManagerState,
  eventName: string,
  payload: ModelDownloadState | { model_id: string },
): ModelManagerState {
  const modelId = payload.model_id;
  if (eventName === 'model-removed') {
    return {
      ...state,
      installed: state.installed.map((entry) =>
        entry.model_id === modelId
          ? { ...entry, installed: false, verified: false, size_bytes: 0, install_path: '' }
          : entry,
      ),
    };
  }

  const nextDownloads = {
    ...state.downloads,
    [modelId]: payload as ModelDownloadState,
  };
  if (eventName === 'model-download-completed' || eventName === 'model-download-cancelled' || eventName === 'model-download-failed') {
    nextDownloads[modelId] = payload as ModelDownloadState;
  }

  return {
    ...state,
    downloads: nextDownloads,
  };
}

export function getModelsByCategory(state: ModelManagerState, category: 'asr' | 'refiner'): ModelCatalogEntry[] {
  return state.catalog.filter((entry) => entry.category === category);
}
