/**
 * Main application window for OpenWispr
 * Creates and manages the primary Electron BrowserWindow with preload script.
 * Exports: createMainWindow, showMainWindowAndFocus
 * @module mainWindow
 */
const { BrowserWindow } = require("electron");
const path = require("path");
const state = require("../shared/state");
const { getWindowIconPath } = require("../shared/iconPaths");

function shouldIgnoreRendererConsoleMessage(message) {
  return (
    typeof message === "string" &&
    (message.includes("Electron Security Warning") ||
      message.includes("'console-message' arguments are deprecated"))
  );
}

function createMainWindow() {
  const windowIcon = getWindowIconPath();

  state.mainWindow = new BrowserWindow({
    width: 1480,
    height: 960,
    minWidth: 1220,
    minHeight: 780,
    backgroundColor: "#0e141b",
    autoHideMenuBar: true,
    title: state.APP_NAME,
    ...(windowIcon ? { icon: windowIcon } : {}),
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "..", "preload", "main.js"),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: true,
      sandbox: true,
      allowRunningInsecureContent: false
    }
  });

  state.mainWindow.once("ready-to-show", () => {
    if (state.mainWindow && !state.mainWindow.isDestroyed()) {
      state.mainWindow.show();
    }
  });

  state.mainWindow.webContents.on("did-finish-load", () => {
    if (state.isDebugLoggingEnabled()) {
      console.log("[main] Renderer finished loading");
    }
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

  state.mainWindow.webContents.on("console-message", (event) => {
    const { level, message, lineNumber, sourceId } = event;
    if (shouldIgnoreRendererConsoleMessage(message)) {
      return;
    }
    if (level >= 2 || state.isDebugLoggingEnabled()) {
      console.error(`[renderer] ${sourceId}:${lineNumber} ${message}`);
    }
  });

  const explicitRendererUrl = process.env.OPENWISPR_RENDERER_URL;
  if (explicitRendererUrl) {
    state.mainWindow.loadURL(explicitRendererUrl);
  } else {
    state.mainWindow.loadFile(path.join(__dirname, "..", "..", "renderer", "dist", "index.html"));
  }

  state.mainWindow.on("close", (event) => {
    if (state.isQuitting) {
      // Force close without hiding when quitting
      return;
    }
    event.preventDefault();
    state.mainWindow.hide();
  });

  state.mainWindow.on("closed", () => {
    state.mainWindow = null;
  });
}

function showMainWindowAndFocus(openSettings = false) {
  if (!state.mainWindow || state.mainWindow.isDestroyed()) {
    createMainWindow();
    if (!state.mainWindow || state.mainWindow.isDestroyed()) {
      return;
    }
    state.mainWindow.once("ready-to-show", () => {
      if (!state.mainWindow || state.mainWindow.isDestroyed()) {
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
    });
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
