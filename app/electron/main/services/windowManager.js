// Window management service
const { BrowserWindow, screen } = require("electron");
const path = require("path");
const state = require("../shared/state");

const { APP_NAME } = require("../shared/generated/appMeta");

function shouldIgnoreRendererConsoleMessage(message) {
  return (
    typeof message === "string" &&
    (message.includes("Electron Security Warning") ||
      message.includes("'console-message' arguments are deprecated"))
  );
}

const isDebugRendererLogging =
  (process.env.OPENWISPR_LOG_LEVEL || "").toLowerCase() === "debug";

function createMainWindow() {
  state.mainWindow = new BrowserWindow({
    width: 1480,
    height: 960,
    minWidth: 1220,
    minHeight: 780,
    backgroundColor: "#0e141b",
    autoHideMenuBar: true,
    title: APP_NAME,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "..", "preload.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  state.mainWindow.once("ready-to-show", () => {
    if (state.mainWindow && !state.mainWindow.isDestroyed()) {
      state.mainWindow.show();
    }
  });

  state.mainWindow.webContents.on("did-finish-load", () => {
    console.log("[window-manager] Renderer finished loading");
  });

  state.mainWindow.webContents.on(
    "did-fail-load",
    (_event, errorCode, errorDescription, validatedURL) => {
      console.error(
        `[window-manager] Renderer failed to load: code=${errorCode} description=${errorDescription} url=${validatedURL}`
      );
    }
  );

  state.mainWindow.webContents.on("render-process-gone", (_event, details) => {
    console.error(
      `[window-manager] Renderer process gone: reason=${details.reason} exitCode=${details.exitCode}`
    );
  });

  state.mainWindow.webContents.on("console-message", (event) => {
    const { level, message, lineNumber, sourceId } = event;
    if (shouldIgnoreRendererConsoleMessage(message)) {
      return;
    }
    if (level >= 2 || isDebugRendererLogging) {
      console.error(`[renderer] ${sourceId}:${lineNumber} ${message}`);
    }
  });

  const explicitRendererUrl = process.env.OPENWISPR_RENDERER_URL;
  if (explicitRendererUrl) {
    state.mainWindow.loadURL(explicitRendererUrl);
  } else {
    state.mainWindow.loadFile(path.join(__dirname, "..", "renderer", "dist", "index.html"));
  }

  state.mainWindow.on("close", (event) => {
    if (process.platform === "darwin") {
      event.preventDefault();
      state.mainWindow.hide();
    }
  });

  state.mainWindow.on("closed", () => {
    state.mainWindow = null;
  });
}

function createFloatingWindow() {
  if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
    return state.floatingWindow;
  }

  const primaryDisplay = screen.getPrimaryDisplay();
  const { width, height } = primaryDisplay.workAreaSize;

  const windowWidth = 420;
  const windowHeight = 140;
  const x = Math.round((width - windowWidth) / 2);
  const y = height - windowHeight - 30;

  state.floatingWindow = new BrowserWindow({
    width: windowWidth,
    height: windowHeight,
    x: x,
    y: y,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    show: false,
    resizable: false,
    movable: true,
    minimizable: false,
    maximizable: false,
    closable: false,
    focusable: true,
    transparent: true,
    backgroundColor: "#00000000",
    hasShadow: true,
    webPreferences: {
      preload: path.join(__dirname, "..", "preload-floating.js"),
      contextIsolation: true,
      nodeIntegration: false,
      offscreen: false
    }
  });

  state.floatingWindow.loadFile(path.join(__dirname, "..", "floating-window.html"));

  state.floatingWindow.on("closed", () => {
    state.floatingWindow = null;
  });

  return state.floatingWindow;
}

function showFloatingWindow() {
  if (!state.floatingWindow || state.floatingWindow.isDestroyed()) {
    createFloatingWindow();
  }

  if (state.floatingWindow) {
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width, height } = primaryDisplay.workAreaSize;
    const windowWidth = 420;
    const windowHeight = 140;
    const x = Math.round((width - windowWidth) / 2);
    const y = height - windowHeight - 30;

    state.floatingWindow.setPosition(x, y);
    state.floatingWindow.showInactive();
    state.floatingWindow.setAlwaysOnTop(true, "screen-saver");
  }
}

function hideFloatingWindow() {
  if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
    state.floatingWindow.hide();
  }
}

function createQuickSettingsWindow() {
  if (state.quickSettingsWindow && !state.quickSettingsWindow.isDestroyed()) {
    return state.quickSettingsWindow;
  }

  state.quickSettingsWindow = new BrowserWindow({
    width: 420,
    height: 520,
    frame: false,
    resizable: false,
    minimizable: false,
    maximizable: false,
    show: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    backgroundColor: "#10161f",
    webPreferences: {
      preload: path.join(__dirname, "..", "preload-quick-settings.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  state.quickSettingsWindow.loadFile(path.join(__dirname, "..", "quick-settings.html"));

  state.quickSettingsWindow.on("blur", () => {
    if (state.quickSettingsWindow && !state.quickSettingsWindow.isDestroyed()) {
      state.quickSettingsWindow.hide();
    }
  });

  state.quickSettingsWindow.on("closed", () => {
    state.quickSettingsWindow = null;
  });

  return state.quickSettingsWindow;
}

function showQuickSettingsWindow() {
  const win = createQuickSettingsWindow();
  if (!state.tray || !win) {
    return;
  }

  const trayBounds = state.tray.getBounds();
  const bounds = win.getBounds();
  const x = Math.max(0, Math.round(trayBounds.x + trayBounds.width / 2 - bounds.width / 2));
  const y = Math.max(0, Math.round(trayBounds.y - bounds.height - 8));

  win.setPosition(x, y, false);
  win.show();
  win.focus();
}

function updateFloatingTranscription(text, isPartial = true) {
  if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
    state.floatingWindow.webContents.send("transcription-update", { text, isPartial });
  }
}

function showMainWindowAndFocus(openSettings = false) {
  if (!state.mainWindow) {
    return;
  }
  if (state.mainWindow.isMinimized()) {
    state.mainWindow.restore();
  }
  state.mainWindow.show();
  state.mainWindow.focus();
  if (openSettings) {
    state.mainWindow.webContents.send("open-settings");
  }
}

module.exports = {
  createMainWindow,
  createFloatingWindow,
  showFloatingWindow,
  hideFloatingWindow,
  createQuickSettingsWindow,
  showQuickSettingsWindow,
  updateFloatingTranscription,
  showMainWindowAndFocus,
};
