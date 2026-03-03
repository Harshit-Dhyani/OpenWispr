// Floating transcription window
const { BrowserWindow, screen } = require("electron");
const path = require("path");
const state = require("../shared/state");

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
    levels = levelsOrLevel;
    peak = peakLevel !== undefined ? peakLevel : Math.max(...levels);
  } else {
    const level = typeof levelsOrLevel === 'number' ? levelsOrLevel : 0;
    peak = level;
    levels = [];

    const time = Date.now() / 200;
    for (let i = 0; i < barCount; i++) {
      const freqResponse = Math.exp(-Math.pow((i - barCount / 2) / 10, 2));
      const wave = Math.sin(time + i * 0.5) * 0.3 + 0.7;
      const noise = Math.random() * 0.2;

      let barLevel = level * wave * freqResponse + noise * level * 0.3;
      barLevel = Math.max(0, Math.min(1, barLevel));
      levels.push(barLevel);
    }
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

  state.floatingWindow.webContents.send("audio-visualizer", { levels, peak });
}

module.exports = {
  createFloatingWindow,
  showFloatingWindow,
  hideFloatingWindow,
  updateFloatingTranscription,
  updateFloatingAudioLevel,
};
