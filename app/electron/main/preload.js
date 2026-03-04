const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("transcriptaDesktop", {
  // Existing APIs
  chooseDirectory: () => ipcRenderer.invoke("choose-directory"),
  choosePdf: () => ipcRenderer.invoke("choose-pdf"),
  onBackendExit: (callback) => {
    ipcRenderer.on("backend-exit", callback);
    return () => ipcRenderer.removeListener("backend-exit", callback);
  },
  onOpenSettings: (callback) => {
    ipcRenderer.on("open-settings", callback);
    return () => ipcRenderer.removeListener("open-settings", callback);
  },
  getApiOrigin: () => "http://127.0.0.1:8765",

  // Fetch API for backend communication
  fetchJson: async (path, options = {}) => {
    const method = (options.method || "GET").toUpperCase();
    const headers = {
      ...(options.headers || {})
    };
    const hasBody = options.body !== undefined && options.body !== null;

    if (hasBody && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    const isRetryableGet = method === "GET";
    let response;
    let lastError;

    for (let attempt = 0; attempt < (isRetryableGet ? 5 : 1); attempt += 1) {
      try {
        response = await fetch(`http://127.0.0.1:8765${path}`, {
          ...options,
          method,
          headers
        });
        break;
      } catch (error) {
        lastError = error;
        if (!isRetryableGet || attempt === 4) {
          throw error;
        }
        await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)));
      }
    }

    if (!response) {
      throw lastError || new Error("Failed to fetch");
    }
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    return response.json();
  },

  // Hotkey APIs
  hotkey: {
    /**
     * Register a new global hotkey
     * @param {string} accelerator - The accelerator string (e.g., "CommandOrControl+Shift+T")
     * @returns {Promise<{success: boolean, accelerator?: string, error?: string, details?: object}>}
     */
    register: (accelerator) => ipcRenderer.invoke("hotkey:register", { accelerator }),

    /**
     * Unregister the current global hotkey
     * @returns {Promise<{success: boolean, wasRegistered?: boolean, error?: string}>}
     */
    unregister: () => ipcRenderer.invoke("hotkey:unregister"),

    /**
     * Validate a hotkey format without registering it
     * @param {string} accelerator - The accelerator string to validate
     * @returns {Promise<{valid: boolean, available?: boolean, error?: string}>}
     */
    validate: (accelerator) => ipcRenderer.invoke("hotkey:validate", { accelerator }),

    /**
     * Toggle the hotkey system on/off
     * @param {boolean} enabled - Whether to enable the hotkey system
     * @returns {Promise<{success: boolean, enabled: boolean}>}
     */
    toggle: (enabled) => ipcRenderer.invoke("hotkey:toggle", enabled),
    start: (source) => ipcRenderer.invoke("hotkey:start", { source }),
    stop: () => ipcRenderer.invoke("hotkey:stop"),

    /**
     * Get current hotkey state
     * @returns {Promise<{enabled: boolean, isRecording: boolean, accelerator: string, registered: boolean, defaultHotkey: string, mode: string}>}
     */
    getState: () => ipcRenderer.invoke("hotkey:get-state"),

    /**
     * Update hotkey configuration
     * @param {object} config - The configuration object
     * @param {boolean} config.enabled - Whether hotkey is enabled
     * @param {string} config.key_combination - The key combination
     * @param {boolean} config.hold_mode - Whether hold mode is enabled
     * @param {boolean} config.auto_inject - Whether auto-inject is enabled
     * @param {boolean} config.show_floating_window - Whether to show floating window
     * @param {string} config.floating_window_position - Position of floating window
     * @param {boolean} config.record_on_start - Whether to record on start
     * @param {boolean} config.stop_on_release - Whether to stop on release
     * @param {boolean} config.copy_to_clipboard - Whether to copy to clipboard
     * @returns {Promise<{success: boolean, config?: object, error?: string}>}
     */
    updateConfig: (config) => ipcRenderer.invoke("hotkey:update-config", config),

    /**
     * Get the default hotkey for this platform
     * @returns {Promise<{accelerator: string, platform: string, note: string}>}
     */
    getDefault: () => ipcRenderer.invoke("hotkey:get-default"),

    /**
     * Listen for hotkey state changes (recording start/stop)
     * @param {function} callback - Callback function(event, {isRecording, hotkeyEnabled, accelerator})
     */
    onStateChange: (callback) => ipcRenderer.on("hotkey-state-change", callback),

    onTranscriptEvent: (callback) => {
      const listener = (_event, payload) => callback(payload);
      ipcRenderer.on("hotkey-transcript-event", listener);
      return () => ipcRenderer.removeListener("hotkey-transcript-event", listener);
    },

    /**
     * Remove hotkey state change listener
     * @param {function} callback - The callback to remove
     */
    removeStateChangeListener: (callback) => ipcRenderer.removeListener("hotkey-state-change", callback),

    /**
     * Listen for hotkey registration failure on startup
     * @param {function} callback - Callback function(event, {accelerator, error, details})
     */
    onRegistrationFailed: (callback) => ipcRenderer.on("hotkey-registration-failed", callback),

    /**
     * Remove hotkey registration failure listener
     * @param {function} callback - The callback to remove
     */
    removeRegistrationFailedListener: (callback) => ipcRenderer.removeListener("hotkey-registration-failed", callback)
  },

  // Text injection API
  text: {
    inject: (text) => ipcRenderer.invoke("text:inject", text)
  },

  // Tray API
  tray: {
    updateTooltip: (tooltip) => ipcRenderer.invoke("tray:update-tooltip", tooltip)
  },

  models: {
    getDownloadRoot: () => ipcRenderer.invoke("models:get-download-root"),
    download: (modelId) => ipcRenderer.invoke("models:download", { modelId }),
    cancel: (modelId) => ipcRenderer.invoke("models:cancel", { modelId }),
    remove: (modelId) => ipcRenderer.invoke("models:remove", { modelId }),
    onDownloadEvent: (callback) => {
      const listener = (_event, payload) => callback(payload);
      ipcRenderer.on("model-download-event", listener);
      return () => ipcRenderer.removeListener("model-download-event", listener);
    },
  },

  // Platform info
  platform: process.platform,

  // Version info
  versions: {
    node: process.versions.node,
    electron: process.versions.electron,
    chrome: process.versions.chrome
  }
});
