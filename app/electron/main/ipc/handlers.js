/**
 * Central IPC handler registry for OpenWispr Electron main process
 * Handles all renderer-to-main communication including: file dialogs, hotkey management,
 * text injection, model downloads, quick settings, and floating window actions.
 * Collaborates with hotkeyHandlers.js for recording lifecycle, and services for backend integration.
 * @module ipcHandlers
 */
const { ipcMain, dialog, shell } = require("electron");
const path = require("path");
const state = require("../shared/state");
const { loadUserSettings, saveUserSettings, loadDevicesForDesktop } = require("../utils/api");
const { injectText } = require("../services/textInjector");
const { showMainWindowAndFocus } = require("../windows/mainWindow");
const { hideFloatingWindow } = require("../windows/floatingWindow");
const { createTray, scheduleTrayRefresh } = require("../windows/tray");
const {
  validateAccelerator, checkHotkeyAvailability, registerHotkey, unregisterHotkey,
  applyHotkeyConfig, buildHotkeyStatePayload
} = require("./hotkeyHandlers");
const { requestStartRecording, requestStopRecording, stopRecording } = require("./hotkeyHandlers");
const { closeHotkeyWebSocket } = require("./hotkeyHandlers");
const { ELECTRON_STRINGS } = require("../../strings/en");

// File dialogs

/**
 * Opens a native directory picker dialog
 * @returns {Promise<string|null>} Selected directory path or null if cancelled
 */
ipcMain.handle("choose-directory", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory", "createDirectory"]
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

/**
 * Opens a native file picker dialog filtered for PDF files
 * @returns {Promise<string|null>} Selected PDF path or null if cancelled
 */
ipcMain.handle("choose-pdf", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openFile"],
    filters: [{ name: "PDF Files", extensions: ["pdf"] }]
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

// Open path in file explorer

/**
 * Reveals a file path in the OS file explorer (selecting the file)
 * @param {string} filePath - Path to reveal
 * @returns {Promise<boolean>} True if successful
 */
ipcMain.handle("open-path", async (event, filePath) => {
  if (!filePath) {
    return { success: false, error: "No file path provided" };
  }
  try {
    const normalizedPath = path.normalize(filePath);
    if (normalizedPath.includes('..')) {
      console.error("Path traversal attempt detected:", filePath);
      return { success: false, error: "Path traversal not allowed" };
    }
    shell.showItemInFolder(normalizedPath);
    return { success: true };
  } catch (error) {
    console.error("Failed to open path:", error.message);
    return { success: false, error: error.message };
  }
});

ipcMain.on("floating:get-strings", (event) => {
  event.returnValue = ELECTRON_STRINGS.floating;
});

/**
 * Returns floating window settings including coach result visibility
 * @returns {Promise<object>} Settings object with showFloatingCoachResult
 */
ipcMain.on("floating:get-settings", (event) => {
  const showFloatingCoachResult =
    state.hotkeyConfigState.show_floating_coach_result ??
    state.cachedSettings?.coach?.show_floating_coach_result ??
    true;
  event.returnValue = { showFloatingCoachResult };
});

// Hotkey IPC handlers

/**
 * Registers a global hotkey accelerator with the system
 * @param {object} params - Handler parameters
 * @param {string} params.accelerator - Keyboard accelerator string
 * @returns {Promise<object>} Registration result with success boolean
 */
ipcMain.handle("hotkey:register", async (event, { accelerator }) => {
  if (!accelerator) {
    return { success: false, error: ELECTRON_STRINGS.hotkey.errors.noAcceleratorProvided };
  }

  console.log(`[main] IPC: Registering hotkey "${accelerator}"`);
  const result = registerHotkey(accelerator);

  if (result.success) {
    const { updateTrayTooltip } = require("../windows/tray");
    updateTrayTooltip();
  }

  return result;
});

/**
 * Unregisters all currently registered global hotkeys
 * @returns {Promise<object>} Unregistration result with success boolean
 */
ipcMain.handle("hotkey:unregister", async () => {
  console.log("[main] IPC: Unregistering hotkey");
  const result = unregisterHotkey();

  if (result.success) {
    const { updateTrayTooltip } = require("../windows/tray");
    updateTrayTooltip();
  }

  return result;
});

/**
 * Validates a keyboard accelerator string for format and availability
 * @param {object} params - Handler parameters
 * @param {string} params.accelerator - Keyboard accelerator string to validate
 * @returns {Promise<object>} Validation result with valid, available, and error fields
 */
ipcMain.handle("hotkey:validate", async (event, { accelerator }) => {
  if (!accelerator) {
    return { valid: false, error: ELECTRON_STRINGS.hotkey.errors.noAcceleratorProvided };
  }

  const validation = validateAccelerator(accelerator);

  if (!validation.valid) {
    return { valid: false, error: validation.error };
  }

  const availability = checkHotkeyAvailability(accelerator);

  return {
    valid: true,
    available: !availability.registered,
    error: availability.error
  };
});

/**
 * Enables or disables the hotkey recording system
 * @param {boolean} enabled - Whether to enable or disable hotkeys
 * @returns {Promise<object>} Toggle result with success and enabled state
 */
ipcMain.handle("hotkey:toggle", async (event, enabled) => {
  state.hotkeyEnabled = enabled;

  if (state.hotkeyEnabled) {
    const accelerator = state.currentHotkeyAccelerator || state.DEFAULT_HOTKEY;
    const result = registerHotkey(accelerator);
    console.log(`[main] Hotkey system ${enabled ? "enabled" : "disabled"}`, result.success ? "" : `- ${result.error}`);
  } else {
    unregisterHotkey();
    console.log("[main] Hotkey system disabled");
  }

  const { updateTrayTooltip } = require("../windows/tray");
  updateTrayTooltip();
  return { success: true, enabled: state.hotkeyEnabled };
});

/**
 * Initiates hotkey recording for the specified audio source
 * @param {object} params - Handler parameters
 * @param {string} [params.source] - Audio source ("microphone" or "system")
 * @returns {Promise<object>} Recording start result with current hotkey state
 */
ipcMain.handle("hotkey:start", async (event, { source } = {}) => {
  const allowedSources = ['microphone', 'system'];
  if (source !== undefined && !allowedSources.includes(source)) {
    return { success: false, error: 'Invalid source parameter. Must be "microphone" or "system".' };
  }
  return requestStartRecording(source);
});

/**
 * Stops the current hotkey recording session
 * @returns {Promise<object>} Recording stop result with current hotkey state
 */
ipcMain.handle("hotkey:stop", async (event) => {
  return requestStopRecording({ keepFloatingResultVisible: false });
});

/**
 * Retrieves current hotkey system state for UI sync
 * @returns {Promise<object>} Complete hotkey state payload
 */
ipcMain.handle("hotkey:get-state", async () => {
  return buildHotkeyStatePayload();
});

/**
 * Returns the default hotkey accelerator for the platform
 * @returns {Promise<object>} Default hotkey with accelerator and platform info
 */
ipcMain.handle("hotkey:get-default", async () => {
  return {
    accelerator: state.DEFAULT_HOTKEY,
    platform: process.platform,
    note: ELECTRON_STRINGS.hotkey.notes.toggleMode
  };
});

/**
 * Applies a new hotkey configuration and re-registers hotkeys
 * @param {object} config - Hotkey configuration object
 * @returns {Promise<object>} Application result with success boolean
 */
ipcMain.handle("hotkey:update-config", async (event, config) => {
  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    return { success: false, error: 'Invalid config: expected object' };
  }
  if (state.isDebugLoggingEnabled()) {
    console.log("[main] IPC: Updating hotkey config", config);
  }
  const result = await applyHotkeyConfig(config);
  await scheduleTrayRefresh();
  return result;
});

// Text injection IPC handler

/**
 * Injects transcribed text into the active application via clipboard simulation
 * @param {string} text - Text to inject
 * @returns {Promise<object>} Injection result with success boolean
 */
ipcMain.handle("text:inject", async (event, text) => {
  if (typeof text !== 'string' || text.length === 0) {
    return { success: false, error: 'Invalid text parameter' };
  }
  if (text.length > 100000) {
    return { success: false, error: 'Text parameter exceeds maximum length' };
  }
  const result = await injectText(text);
  return result;
});

// Tray IPC handler

/**
 * Updates the system tray tooltip text
 * @param {string} tooltip - New tooltip text
 * @returns {Promise<object>} Update result with success boolean
 */
ipcMain.handle("tray:update-tooltip", async (event, tooltip) => {
  if (state.tray) {
    state.tray.setToolTip(tooltip || `${state.APP_NAME} - ${state.isRecording ? "Recording" : "Ready"}`);
  }
  return { success: true };
});

// Model download IPC handlers

/**
 * Returns the root directory for downloaded models
 * @returns {Promise<object>} Root path object
 */
ipcMain.handle("models:get-download-root", async () => {
  const { app } = require("electron");
  return { root: path.join(app.getPath("userData"), "models") };
});

/**
 * Initiates download of a model by ID
 * @param {object} params - Handler parameters
 * @param {string} params.modelId - Model identifier to download
 * @returns {Promise<object>} Download result
 */
ipcMain.handle("models:download", async (event, { modelId }) => {
  // Validate modelId format
  if (!modelId || typeof modelId !== 'string' || modelId.length > 100) {
    return { ok: false, error: "invalid_model_id" };
  }

  const requestContext = {
    modelId,
    timestamp: new Date().toISOString(),
    sender: event.sender.getTitle?.() || 'unknown'
  };
  console.log('[models:download:ipc] Request received:', requestContext);

  if (!state.modelDownloadManager) {
    const error = new Error("Model download manager is not ready");
    console.error('[models:download:ipc] Manager not ready:', requestContext);
    throw error;
  }

  try {
    const result = await state.modelDownloadManager.downloadModel(modelId);
    console.log('[models:download:ipc] Request completed successfully:', { modelId });
    return result;
  } catch (error) {
    console.error('[models:download:ipc] Request failed:', {
      ...requestContext,
      error: error.message,
      code: error.code,
      stack: error.stack
    });
    throw error;
  }
});

/**
 * Cancels an in-progress model download
 * @param {object} params - Handler parameters
 * @param {string} params.modelId - Model identifier to cancel
 * @returns {Promise<object>} Cancel result
 */
ipcMain.handle("models:cancel", async (event, { modelId }) => {
  console.log('[models:cancel:ipc] Request received:', { modelId, timestamp: new Date().toISOString() });
  if (!modelId || typeof modelId !== 'string' || modelId.length > 100) {
    console.error('[models:cancel:ipc] Invalid modelId:', { modelId });
    return { ok: false, error: "invalid_model_id" };
  }
  if (!state.modelDownloadManager) {
    console.error('[models:cancel:ipc] Manager not ready');
    return { ok: false, error: "model-download-manager-not-ready" };
  }
  const result = await state.modelDownloadManager.cancelDownload(modelId);
  console.log('[models:cancel:ipc] Result:', result);
  return result;
});

/**
 * Removes a downloaded model from local storage
 * @param {object} params - Handler parameters
 * @param {string} params.modelId - Model identifier to remove
 * @returns {Promise<object>} Remove result
 */
ipcMain.handle("models:remove", async (event, { modelId }) => {
  console.log('[models:remove:ipc] Request received:', { modelId, timestamp: new Date().toISOString() });
  if (!modelId || typeof modelId !== 'string' || modelId.length > 100) {
    console.error('[models:remove:ipc] Invalid modelId:', { modelId });
    throw new Error("Invalid model ID");
  }
  if (!state.modelDownloadManager) {
    console.error('[models:remove:ipc] Manager not ready');
    throw new Error("Model download manager is not ready");
  }
  try {
    const result = await state.modelDownloadManager.removeModel(modelId);
    console.log('[models:remove:ipc] Success:', { modelId });
    return result;
  } catch (error) {
    console.error('[models:remove:ipc] Failed:', { modelId, error: error.message });
    throw error;
  }
});

// Quick settings IPC handlers

/**
 * Retrieves data needed to populate the quick settings window
 * @returns {Promise<object>} Settings data including app name, settings, devices, languages, and hotkey state
 */
ipcMain.handle("quick-settings:get-data", async () => {
  const settings = await loadUserSettings();
  const devices = await loadDevicesForDesktop();
  return {
    appName: state.APP_NAME,
    settings,
    devices,
    languages: state.QUICK_LANGUAGE_OPTIONS,
    hotkeyState: {
      enabled: state.hotkeyEnabled,
      accelerator: state.currentHotkeyAccelerator || state.hotkeyConfigState.key_combination || state.DEFAULT_HOTKEY,
      isRecording: state.isRecording,
    },
  };
});

/**
 * Updates user settings from quick settings window
 * @param {object} nextSettings - New settings object to save
 * @returns {Promise<object>} Save result with success boolean
 */
ipcMain.handle("quick-settings:update", async (event, nextSettings) => {
  if (!nextSettings || typeof nextSettings !== 'object' || Array.isArray(nextSettings)) {
    return { success: false, error: 'Invalid settings: expected object' };
  }
  await saveUserSettings(nextSettings);
  if (nextSettings?.hotkey) {
    await applyHotkeyConfig(nextSettings.hotkey);
  }
  await scheduleTrayRefresh();
  if (state.mainWindow && !state.mainWindow.isDestroyed()) {
    state.mainWindow.webContents.send("settings-updated");
  }
  return { success: true };
});

/**
 * Closes quick settings and opens full settings window
 * @returns {Promise<object>} Operation result
 */
ipcMain.handle("quick-settings:open-full", async () => {
  showMainWindowAndFocus(true);
  if (state.quickSettingsWindow && !state.quickSettingsWindow.isDestroyed()) {
    state.quickSettingsWindow.hide();
  }
  return { success: true };
});

/**
 * Closes the quick settings window
 * @returns {Promise<object>} Operation result
 */
ipcMain.handle("quick-settings:close", async () => {
  if (state.quickSettingsWindow && !state.quickSettingsWindow.isDestroyed()) {
    state.quickSettingsWindow.hide();
  }
  return { success: true };
});

// Apply hotkey config when settings are saved from main window
ipcMain.handle("settings:apply-hotkey", async (event, hotkeyConfig) => {
  if (!hotkeyConfig || typeof hotkeyConfig !== 'object' || Array.isArray(hotkeyConfig)) {
    return { success: false, error: 'Invalid hotkey config: expected object' };
  }
  await applyHotkeyConfig(hotkeyConfig);
  return { success: true };
});

// Floating window actions

/**
 * Handles floating window button actions (cancel, finish, finish-and-paste, dismiss-result)
 * @param {object} params - Handler parameters
 * @param {string} params.action - Action to perform
 */
ipcMain.on("floating-window-action", async (event, { action }) => {
  console.log("[main] Floating window action:", action);

  if (action === "cancel") {
    if (state.isRecording) {
      try {
        state.floatingWindowSuppressResult = true;
        state.hotkeyPendingAction = "cancel";
        await stopRecording({ keepFloatingResultVisible: false });
      } catch (error) {
        console.error("[main] Failed to stop on cancel:", error.message);
        state.hotkeyPendingAction = null;
      }
    }
  } else if (action === "finish") {
    if (state.isRecording) {
      state.hotkeyPendingAction = "finish";
      try {
        await stopRecording({ keepFloatingResultVisible: true });
      } catch (error) {
        console.error("[main] Failed to stop on finish:", error.message);
        state.hotkeyPendingAction = null;
      }
    }
  } else if (action === "finish-and-paste") {
    if (state.isRecording) {
      try {
        state.hotkeyPendingAction = "finish_and_paste";
        await stopRecording({ keepFloatingResultVisible: true });
      } catch (error) {
        console.error("[main] Failed to stop on finish-and-paste:", error.message);
        state.hotkeyPendingAction = null;
      }
    }
  } else if (action === "dismiss-result") {
    if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
      state.floatingWindow.hide();
    }
  }
});

// Open settings handler

/**
 * Signals renderer to open the settings window
 */
ipcMain.on("open-settings", () => {
  if (state.mainWindow && !state.mainWindow.isDestroyed()) {
    state.mainWindow.webContents.send("open-settings");
  }
});

console.log("[main] IPC handlers registered");
