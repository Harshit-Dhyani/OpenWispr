// Main entry point for Electron
const { app, ipcMain, globalShortcut } = require("electron");
const state = require("./shared/state");
const { startBackend, waitForBackendReady, stopBackend } = require("./services/backendSpawn");
const { initTextInjector } = require("./services/textInjector");
const { ModelDownloadManager } = require("./model-download-manager");
const { createMainWindow, showMainWindowAndFocus } = require("./windows/mainWindow");
const { createTray } = require("./windows/tray");
const { hideFloatingWindow, updateFloatingTranscription } = require("./windows/floatingWindow");
const { showQuickSettingsWindow } = require("./windows/quickSettingsWindow");
const { loadUserSettings, loadDevicesForDesktop } = require("./utils/api");
const {
  registerHotkey, unregisterHotkey, validateAccelerator, checkHotkeyAvailability,
  applyHotkeyConfig, toggleRecording
} = require("./ipc/hotkeyHandlers");

// Import IPC setup
require("./ipc/handlers");

// App event handlers
app.whenReady().then(async () => {
  await startBackend();
  await waitForBackendReady();
  state.backendReady = true;

  state.modelDownloadManager = new ModelDownloadManager({
    getApiOrigin: () => state.API_ORIGIN,
    getUserDataPath: () => app.getPath("userData"),
    emit: (event, payload) => state.broadcastToWindows("model-download-event", { event, payload }),
  });

  await initTextInjector();
  try {
    await Promise.allSettled([loadUserSettings(), loadDevicesForDesktop()]);
  } catch {}
  createMainWindow();
  await createTray();

  // Register global shortcut for Settings (Ctrl+,)
  globalShortcut.register("CommandOrControl+,", () => {
    if (state.mainWindow) {
      if (state.mainWindow.isMinimized()) state.mainWindow.restore();
      state.mainWindow.show();
      state.mainWindow.focus();
      state.mainWindow.webContents.send("open-settings");
    }
  });

  console.log("[main] Global hotkey starts disabled until settings are loaded.");
}).catch((error) => {
  console.error("[main] App startup failed", error);
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  unregisterHotkey();
  stopBackend();
  if (state.webSocketReconnectTimeout) {
    clearTimeout(state.webSocketReconnectTimeout);
  }
  if (state.hotkeyWebSocket) {
    try {
      state.hotkeyWebSocket.close();
    } catch {}
  }
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});

app.on("activate", () => {
  if (state.mainWindow === null) {
    createMainWindow();
  } else {
    state.mainWindow.show();
  }
});

// Hide dock icon on macOS for cleaner experience
if (process.platform === "darwin") {
  app.dock.hide();
}

// Backend-to-renderer forwarding for hotkey mode
ipcMain.on("transcription-result", (event, data) => {
  updateFloatingTranscription(data.text, data.isPartial);
});

console.log("[main] Electron main process started");
