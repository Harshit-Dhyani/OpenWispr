// Floating transcription window
const { BrowserWindow, screen } = require("electron");
const path = require("path");
const state = require("../shared/state");

const VISUALIZER_THROTTLE_MS = 50;
let lastVisualizerSentAt = 0;
let pendingVisualizerPayload = null;
let visualizerFlushTimer = null;

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

  state.floatingWindow.loadFile(path.join(__dirname, "..", "..", "floating-window.html"));

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

function updateFloatingTranscription(text, isPartial = true) {
  if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
    state.floatingWindow.webContents.send("transcription-update", { text, isPartial });
  }
}

function updateFloatingAudioLevel(levelsOrLevel, peakLevel) {
  if (!state.floatingWindow || state.floatingWindow.isDestroyed()) return;

  const barCount = 36;
  let levels;
  let peak;

  if (Array.isArray(levelsOrLevel) && levelsOrLevel.length > 0) {
    levels = levelsOrLevel.map((value) => {
      const safeValue = Number.isFinite(value) ? value : 0;
      return Math.max(0, Math.min(1, safeValue));
    });
    peak = peakLevel !== undefined ? peakLevel : Math.max(...levels);
  } else {
    const level = Number.isFinite(levelsOrLevel) ? levelsOrLevel : 0;
    peak = level;
    levels = Array.from({ length: barCount }, (_, index) => {
      const centerDistance = Math.abs(index - barCount / 2) / (barCount / 2);
      const curve = Math.max(0.15, 1 - centerDistance * 0.75);
      return Math.max(0, Math.min(1, level * curve));
    });
  }

  if (levels.length !== barCount) {
    const result = new Array(barCount).fill(0);
    const step = levels.length / barCount;
    for (let i = 0; i < barCount; i++) {
      const sourceIndex = Math.floor(i * step);
      result[i] = levels[Math.min(sourceIndex, levels.length - 1)] || 0;
    }
    levels = result;
  }

  const payload = {
    levels,
    peak: Number.isFinite(peak) ? Math.max(0, Math.min(1, peak)) : 0,
  };

  const flush = () => {
    visualizerFlushTimer = null;
    if (!pendingVisualizerPayload) {
      return;
    }
    if (!state.floatingWindow || state.floatingWindow.isDestroyed()) {
      pendingVisualizerPayload = null;
      return;
    }
    lastVisualizerSentAt = Date.now();
    state.floatingWindow.webContents.send("audio-visualizer", pendingVisualizerPayload);
    pendingVisualizerPayload = null;
  };

  const now = Date.now();
  const elapsed = now - lastVisualizerSentAt;
  if (elapsed >= VISUALIZER_THROTTLE_MS && !visualizerFlushTimer) {
    lastVisualizerSentAt = now;
    state.floatingWindow.webContents.send("audio-visualizer", payload);
    return;
  }

  pendingVisualizerPayload = payload;
  if (!visualizerFlushTimer) {
    visualizerFlushTimer = setTimeout(flush, Math.max(0, VISUALIZER_THROTTLE_MS - elapsed));
  }
}

module.exports = {
  createFloatingWindow,
  showFloatingWindow,
  hideFloatingWindow,
  updateFloatingTranscription,
  updateFloatingAudioLevel,
};
