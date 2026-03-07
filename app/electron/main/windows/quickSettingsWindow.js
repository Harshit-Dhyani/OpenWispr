// Quick settings window for tray menu
const { BrowserWindow } = require("electron");
const path = require("path");
const state = require("../shared/state");
const { getWindowIconPath } = require("../shared/iconPaths");

function createQuickSettingsWindow() {
  if (state.quickSettingsWindow && !state.quickSettingsWindow.isDestroyed()) {
    return state.quickSettingsWindow;
  }

  const windowIcon = getWindowIconPath();

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
    ...(windowIcon ? { icon: windowIcon } : {}),
    webPreferences: {
      preload: path.join(__dirname, "..", "preload-quick-settings.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  state.quickSettingsWindow.loadFile(path.join(__dirname, "..", "..", "quick-settings.html"));

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

module.exports = {
  createQuickSettingsWindow,
  showQuickSettingsWindow,
};
