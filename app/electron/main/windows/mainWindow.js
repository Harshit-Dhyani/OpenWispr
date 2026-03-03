// Main window creation and management
const { BrowserWindow } = require("electron");
const path = require("path");
const state = require("../shared/state");

function createMainWindow() {
  state.mainWindow = new BrowserWindow({
    width: 1480,
    height: 960,
    minWidth: 1220,
    minHeight: 780,
    backgroundColor: "#0e141b",
    autoHideMenuBar: true,
    title: state.APP_NAME,
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
    console.log("[main] Renderer finished loading");
  });

  state.mainWindow.webContents.on(
    "did-fail-load",
    (_event, errorCode, errorDescription, validatedURL) => {
      console.error(
        `[main] Renderer failed to load: code=${errorCode} description=${errorDescription} url=${validatedURL}`
      );
    }
  );

  state.mainWindow.webContents.on("render-process-gone", (_event, details) => {
    console.error(
      `[main] Renderer process gone: reason=${details.reason} exitCode=${details.exitCode}`
    );
  });

  state.mainWindow.webContents.on(
    "console-message",
    (_event, level, message, line, sourceId) => {
      if (level >= 2) {
        console.error(`[renderer] ${sourceId}:${line} ${message}`);
      }
    }
  );

  const explicitRendererUrl = process.env.TRANSCRIPTA_RENDERER_URL;
  if (explicitRendererUrl) {
    state.mainWindow.loadURL(explicitRendererUrl);
  } else {
    state.mainWindow.loadFile(path.join(__dirname, "..", "..", "renderer", "dist", "index.html"));
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
  showMainWindowAndFocus,
};
