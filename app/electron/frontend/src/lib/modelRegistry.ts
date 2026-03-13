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
  selectedRefinerModelId: 'qwen2.5-3b-instruct',
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
  const currentDownload = state.downloads[modelId];
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

  if (
    currentDownload?.download_id &&
    'download_id' in payload &&
    payload.download_id &&
    currentDownload.download_id !== payload.download_id &&
    eventName !== 'model-download-started' &&
    eventName !== 'model-download-retrying'
  ) {
    return state;
  }

  const nextDownload =
    'status' in payload
      ? eventName === 'model-download-started' || eventName === 'model-download-retrying'
        ? {
            ...payload,
            total_bytes_known: payload.total_bytes_known ?? false,
          }
        : {
            ...(currentDownload ?? {}),
            ...payload,
            bytes_downloaded: Math.max(
              currentDownload?.bytes_downloaded ?? 0,
              payload.bytes_downloaded ?? 0,
            ),
            progress: Math.max(currentDownload?.progress ?? 0, payload.progress ?? 0),
            total_bytes_known:
              payload.total_bytes_known ??
              currentDownload?.total_bytes_known ??
              false,
          }
      : currentDownload;

  if (!nextDownload) {
    return state;
  }

  const nextDownloads = {
    ...state.downloads,
    [modelId]: nextDownload as ModelDownloadState,
  };
  if (eventName === 'model-download-completed' || eventName === 'model-download-cancelled' || eventName === 'model-download-failed') {
    nextDownloads[modelId] = nextDownload as ModelDownloadState;
  }

  return {
    ...state,
    downloads: nextDownloads,
  };
}

export function getModelsByCategory(state: ModelManagerState, category: 'asr' | 'refiner'): ModelCatalogEntry[] {
  return state.catalog.filter((entry) => entry.category === category);
}
