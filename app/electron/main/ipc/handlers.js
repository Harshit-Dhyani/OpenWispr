// General IPC handlers
const { ipcMain, dialog } = require("electron");
const path = require("path");
const state = require("../shared/state");
const { loadUserSettings, saveUserSettings, loadDevicesForDesktop } = require("../utils/api");
const { injectText } = require("../services/textInjector");
const { showMainWindowAndFocus } = require("../windows/mainWindow");
const { hideFloatingWindow } = require("../windows/floatingWindow");
const { createTray, scheduleTrayRefresh } = require("../windows/tray");
const {
  validateAccelerator, checkHotkeyAvailability, registerHotkey, unregisterHotkey,
  applyHotkeyConfig, toggleRecording, buildHotkeyStatePayload
} = require("./hotkeyHandlers");
const { startRecording, stopRecording } = require("./hotkeyHandlers");
const { closeHotkeyWebSocket } = require("./hotkeyHandlers");

// File dialogs
ipcMain.handle("choose-directory", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory", "createDirectory"]
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

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

// Hotkey IPC handlers
ipcMain.handle("hotkey:register", async (event, { accelerator }) => {
  if (!accelerator) {
    return { success: false, error: "No accelerator provided" };
  }

  console.log(`[main] IPC: Registering hotkey "${accelerator}"`);
  const result = registerHotkey(accelerator);

  if (result.success) {
    const { updateTrayTooltip } = require("../windows/tray");
    updateTrayTooltip();
  }

  return result;
});

ipcMain.handle("hotkey:unregister", async () => {
  console.log("[main] IPC: Unregistering hotkey");
  const result = unregisterHotkey();

  if (result.success) {
    const { updateTrayTooltip } = require("../windows/tray");
    updateTrayTooltip();
  }

  return result;
});

ipcMain.handle("hotkey:validate", async (event, { accelerator }) => {
  if (!accelerator) {
    return { valid: false, error: "No accelerator provided" };
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

ipcMain.handle("hotkey:start", async (event, { source } = {}) => {
  return startRecording(source);
});

ipcMain.handle("hotkey:stop", async (event) => {
  return stopRecording();
});

ipcMain.handle("hotkey:get-state", async () => {
  return buildHotkeyStatePayload();
});

ipcMain.handle("hotkey:get-default", async () => {
  return {
    accelerator: state.DEFAULT_HOTKEY,
    platform: process.platform,
    note: "Uses toggle mode: press once to start, press again to stop"
  };
});

ipcMain.handle("hotkey:update-config", async (event, config) => {
  console.log("[main] IPC: Updating hotkey config", config);
  const result = await applyHotkeyConfig(config);
  await scheduleTrayRefresh();
  return result;
});

// Text injection IPC handler
ipcMain.handle("text:inject", async (event, text) => {
  const result = await injectText(text);
  return result;
});

// Tray IPC handler
ipcMain.handle("tray:update-tooltip", async (event, tooltip) => {
  if (state.tray) {
    state.tray.setToolTip(tooltip || `${state.APP_NAME} - ${state.isRecording ? "Recording" : "Ready"}`);
  }
  return { success: true };
});

// Model download IPC handlers
ipcMain.handle("models:get-download-root", async () => {
  const { app } = require("electron");
  return { root: path.join(app.getPath("userData"), "models") };
});

ipcMain.handle("models:download", async (event, { modelId }) => {
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

ipcMain.handle("models:cancel", async (event, { modelId }) => {
  console.log('[models:cancel:ipc] Request received:', { modelId, timestamp: new Date().toISOString() });
  if (!state.modelDownloadManager) {
    console.error('[models:cancel:ipc] Manager not ready');
    return { ok: false, error: "model-download-manager-not-ready" };
  }
  const result = await state.modelDownloadManager.cancelDownload(modelId);
  console.log('[models:cancel:ipc] Result:', result);
  return result;
});

ipcMain.handle("models:remove", async (event, { modelId }) => {
  console.log('[models:remove:ipc] Request received:', { modelId, timestamp: new Date().toISOString() });
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

ipcMain.handle("quick-settings:update", async (event, nextSettings) => {
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

ipcMain.handle("quick-settings:open-full", async () => {
  showMainWindowAndFocus(true);
  if (state.quickSettingsWindow && !state.quickSettingsWindow.isDestroyed()) {
    state.quickSettingsWindow.hide();
  }
  return { success: true };
});

ipcMain.handle("quick-settings:close", async () => {
  if (state.quickSettingsWindow && !state.quickSettingsWindow.isDestroyed()) {
    state.quickSettingsWindow.hide();
  }
  return { success: true };
});

// Floating window actions
ipcMain.on("floating-window-action", async (event, { action }) => {
  console.log("[main] Floating window action:", action);

  if (action === "cancel") {
    if (state.isRecording) {
      try {
        state.hotkeyPendingAction = "cancel";
        await toggleRecording(false);
      } catch (error) {
        console.error("[main] Failed to stop:", error);
      } finally {
        state.hotkeyPendingAction = null;
      }
    }
  } else if (action === "finish") {
    if (state.isRecording) {
      state.hotkeyPendingAction = "finish";
      try {
        await toggleRecording(false);
      } finally {
        state.hotkeyPendingAction = null;
      }
    }
  } else if (action === "finish-and-paste") {
    if (state.isRecording) {
      try {
        state.hotkeyPendingAction = "finish_and_paste";
        await toggleRecording(false);
      } finally {
        state.hotkeyPendingAction = null;
      }
    }
  }
});

// Open settings handler
ipcMain.on("open-settings", () => {
  if (state.mainWindow && !state.mainWindow.isDestroyed()) {
    state.mainWindow.webContents.send("open-settings");
  }
});

console.log("[main] IPC handlers registered");
