// Main entry point for Electron
const { app, ipcMain, globalShortcut } = require("electron");
const { APP_NAME, APP_SLUG } = require("./shared/generated/appMeta");
if (process.env.OPENWISPR_DISABLE_GPU === "1") {
  app.disableHardwareAcceleration();
}

app.setName(APP_NAME);
if (process.platform === 'win32') {
  app.setAppUserModelId(`com.${APP_SLUG}.desktop`);
}
const state = require("./shared/state");
const { startBackend, waitForBackendReady, stopBackend } = require("./services/backendSpawn");
const { initTextInjector } = require("./services/textInjector");
const { ModelDownloadManager } = require("./services/modelDownloadManager");
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

process.on("uncaughtException", (error) => {
  console.error("[main] Uncaught exception", error);
});

process.on("unhandledRejection", (reason) => {
  console.error("[main] Unhandled rejection", reason);
});

// App event handlers
app.whenReady().then(async () => {
  // Initialize model download manager first
  state.modelDownloadManager = new ModelDownloadManager({
    getApiOrigin: () => state.API_ORIGIN,
    getUserDataPath: () => app.getPath("userData"),
    emit: (event, payload) => state.broadcastToWindows("model-download-event", { event, payload }),
  });
  
  // Create main window immediately 
  createMainWindow();
  
  // Start backend in background
  const backendReady = await startBackend();
  
  if (backendReady) {
    console.log("[main] Backend ready, loading settings...");
    await initTextInjector();
    const settings = await loadUserSettings();
    await loadDevicesForDesktop();
    
    // Apply hotkey config if enabled
    if (settings?.hotkey?.enabled) {
      console.log("[main] Applying saved hotkey configuration...");
      await applyHotkeyConfig(settings.hotkey);
    }
    state.backendReady = true;
  } else {
    console.log("[main] Backend failed to start");
  }
  
  // Create tray
  createTray();

  // Register global shortcut for Settings (Ctrl+,)
  globalShortcut.register("CommandOrControl+,", () => {
    if (state.mainWindow) {
      if (state.mainWindow.isMinimized()) state.mainWindow.restore();
      state.mainWindow.show();
      state.mainWindow.focus();
      state.mainWindow.webContents.send("open-settings");
    }
  });

  if (state.isDebugLoggingEnabled()) {
    console.log("[main] Global hotkey starts disabled until settings are loaded.");
  }
}).catch((error) => {
  console.error("[main] App startup failed", error);
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  state.isQuitting = true;
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


