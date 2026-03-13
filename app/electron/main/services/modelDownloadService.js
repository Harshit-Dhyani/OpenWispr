/**
 * ModelDownloadService - Service wrapper for model downloads
 * 
 * Provides a simplified interface for IPC handlers, wrapping ModelDownloadManager
 */

const { ModelDownloadManager } = require('../model-download-manager');

class ModelDownloadService {
  constructor() {
    this._manager = null;
    this._initialized = false;
  }

  _ensureInitialized() {
    if (!this._initialized || !this._manager) {
      throw new Error("Model download service is not ready");
    }
  }

  async _ensureManager() {
    if (!this._manager) {
      const { app } = require('electron');
      this._manager = new ModelDownloadManager({
        getApiOrigin: () => 'http://127.0.0.1:8765',
        getUserDataPath: () => app.getPath("userData"),
        emit: (event, payload) => {
          console.log('[ModelDownloadService] Event:', event, payload);
        },
      });
      this._initialized = true;
    }
    return this._manager;
  }

  async downloadModel(modelId, modelType, sourceUrl, options = {}) {
    const manager = await this._ensureManager();
    
    // Handle both catalog-based downloads (modelId only) and URL-based downloads
    if (sourceUrl) {
      // URL-based download not directly supported, use catalog-based
      console.warn('[ModelDownloadService] sourceUrl ignored, using catalog-based download');
    }
    
    const maxRetries = options.maxRetries || 3;
    return manager.downloadModel(modelId, maxRetries);
  }

  _getTargetPath(modelId, modelType) {
    this._ensureInitialized();
    // Build path: modelsRoot/{asr|refiner}/{modelId}/
    const root = this._manager.getModelsRoot();
    return `${root}\\${modelType || 'asr'}\\${modelId}`;
  }

  async removeModel(modelId) {
    const manager = await this._ensureManager();
    return manager.removeModel(modelId);
  }

  async cancelDownload(modelId) {
    const manager = await this._ensureInitialized();
    return manager.cancelDownload(modelId);
  }
}

module.exports = { ModelDownloadService };
