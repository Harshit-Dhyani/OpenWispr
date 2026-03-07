// Floating transcription window
const { BrowserWindow, screen, app } = require("electron");
const path = require("path");
const fs = require("fs");
const state = require("../shared/state");
const {
  resolveFloatingWindowBounds,
  DEFAULT_FLOATING_WINDOW_SIZE,
  resolveFloatingWindowHtmlPath,
} = require("./floatingWindowState");

const VISUALIZER_THROTTLE_MS = 50;
let lastVisualizerSentAt = 0;
let pendingVisualizerPayload = null;
let visualizerFlushTimer = null;
let persistPositionTimer = null;
let floatingWindowReady = false;
let pendingRecordingState = {
  isRecording: false,
  processing: false,
  finished: false,
  sessionId: null,
  mode: "dictation",
  error: null,
};
let pendingTranscriptionPayload = {
  text: "",
  committedText: "",
  partialText: "",
  isPartial: false,
  sessionId: null,
  segmentIndex: null,
  mode: "dictation",
};

function getFloatingWindowStatePath() {
  return path.join(app.getPath("userData"), "floating-window-state.json");
}

function readSavedFloatingWindowPosition() {
  try {
    const filePath = getFloatingWindowStatePath();
    if (!fs.existsSync(filePath)) {
      return null;
    }
    const payload = JSON.parse(fs.readFileSync(filePath, "utf8"));
    if (!Number.isFinite(payload?.x) || !Number.isFinite(payload?.y)) {
      return null;
    }
    return { x: payload.x, y: payload.y };
  } catch {
    return null;
  }
}

function persistFloatingWindowPosition() {
  if (!state.floatingWindow || state.floatingWindow.isDestroyed()) {
    return;
  }

  try {
    const { x, y } = state.floatingWindow.getBounds();
    fs.writeFileSync(
      getFloatingWindowStatePath(),
      JSON.stringify({ x, y }, null, 2),
      "utf8",
    );
  } catch {}
}

function schedulePersistFloatingWindowPosition() {
  if (persistPositionTimer) {
    clearTimeout(persistPositionTimer);
  }
  persistPositionTimer = setTimeout(() => {
    persistPositionTimer = null;
    persistFloatingWindowPosition();
  }, 150);
}

function getPrimaryWorkArea() {
  return screen.getPrimaryDisplay().workArea;
}

function createFloatingWindow() {
  if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
    return state.floatingWindow;
  }

  const workArea = getPrimaryWorkArea();
  const settingsPosition = state.cachedSettings?.hotkey?.floating_window_position || "bottom-right";
  const initialBounds = resolveFloatingWindowBounds({
    savedPosition: readSavedFloatingWindowPosition(),
    preset: settingsPosition,
    workArea,
    size: DEFAULT_FLOATING_WINDOW_SIZE,
  });

  state.floatingWindow = new BrowserWindow({
    width: initialBounds.width,
    height: initialBounds.height,
    x: initialBounds.x,
    y: initialBounds.y,
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
      preload: path.join(__dirname, "..", "preload", "floating.js"),
      contextIsolation: true,
      nodeIntegration: false,
      offscreen: false
    }
  });

  state.floatingWindow.loadFile(resolveFloatingWindowHtmlPath());

  floatingWindowReady = false;

  state.floatingWindow.webContents.on(
    "did-fail-load",
    (_event, errorCode, errorDescription, validatedURL) => {
      console.error(
        `[floating] failed to load: code=${errorCode} description=${errorDescription} url=${validatedURL}`,
      );
    },
  );

  state.floatingWindow.webContents.on("render-process-gone", (_event, details) => {
    console.error(
      `[floating] render process gone: reason=${details.reason} exitCode=${details.exitCode}`,
    );
  });

  state.floatingWindow.webContents.on("console-message", (event) => {
    const { level, message, lineNumber, sourceId } = event;
    if (level >= 2 || state.isDebugLoggingEnabled()) {
      console.error(`[floating:renderer] ${sourceId}:${lineNumber} ${message}`);
    }
  });

  state.floatingWindow.webContents.on("did-finish-load", () => {
    floatingWindowReady = true;
    if (state.isDebugLoggingEnabled()) {
      console.log("[floating] did-finish-load");
    }
    state.floatingWindow?.webContents.send("recording-state", pendingRecordingState);
    state.floatingWindow?.webContents.send("transcription-update", pendingTranscriptionPayload);
    state.floatingWindow?.webContents.send(
      "audio-visualizer",
      pendingVisualizerPayload || {
        levels: new Array(36).fill(0),
        peak: 0,
      },
    );
  });

  state.floatingWindow.on("move", () => {
    schedulePersistFloatingWindowPosition();
  });

  state.floatingWindow.on("closed", () => {
    if (persistPositionTimer) {
      clearTimeout(persistPositionTimer);
      persistPositionTimer = null;
    }
    floatingWindowReady = false;
    state.floatingWindow = null;
  });

  return state.floatingWindow;
}

function showFloatingWindow() {
  if (!state.floatingWindow || state.floatingWindow.isDestroyed()) {
    createFloatingWindow();
  }

  if (state.floatingWindow) {
    const workArea = getPrimaryWorkArea();
    const settingsPosition = state.cachedSettings?.hotkey?.floating_window_position || "bottom-right";
    const bounds = resolveFloatingWindowBounds({
      savedPosition: readSavedFloatingWindowPosition(),
      preset: settingsPosition,
      workArea,
      size: DEFAULT_FLOATING_WINDOW_SIZE,
    });

    state.floatingWindow.setBounds(bounds, false);
    state.floatingWindow.showInactive();
    state.floatingWindow.setAlwaysOnTop(true, "screen-saver");
  }
}

function hideFloatingWindow() {
  if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
    state.floatingWindow.hide();
  }
}

function resetFloatingWindow() {
  pendingVisualizerPayload = null;
  lastVisualizerSentAt = 0;
  pendingRecordingState = {
    isRecording: false,
    processing: false,
    finished: false,
    sessionId: null,
    mode: pendingRecordingState.mode || "dictation",
    error: null,
  };
  pendingTranscriptionPayload = {
    text: "",
    committedText: "",
    partialText: "",
    isPartial: false,
    sessionId: null,
    segmentIndex: null,
    mode: pendingTranscriptionPayload.mode || "dictation",
  };
  if (visualizerFlushTimer) {
    clearTimeout(visualizerFlushTimer);
    visualizerFlushTimer = null;
  }

  updateFloatingRecordingState(pendingRecordingState);
  updateFloatingAudioLevel(new Array(36).fill(0), 0);
  updateFloatingTranscription("", {
    committedText: "",
    partialText: "",
    isPartial: false,
  });
}

function updateFloatingTranscription(text, options = {}) {
  pendingTranscriptionPayload = {
    text,
    committedText: options.committedText ?? pendingTranscriptionPayload.committedText ?? "",
    partialText: options.partialText ?? pendingTranscriptionPayload.partialText ?? "",
    isPartial: options.isPartial ?? true,
    sessionId: options.sessionId ?? pendingTranscriptionPayload.sessionId ?? null,
    segmentIndex: options.segmentIndex ?? pendingTranscriptionPayload.segmentIndex ?? null,
    mode: options.mode ?? pendingTranscriptionPayload.mode ?? "dictation",
  };

  if (
    floatingWindowReady &&
    state.floatingWindow &&
    !state.floatingWindow.isDestroyed()
  ) {
    state.floatingWindow.webContents.send("transcription-update", pendingTranscriptionPayload);
  }
}

function updateFloatingRecordingState(payload) {
  pendingRecordingState = {
    ...pendingRecordingState,
    ...payload,
  };
  if (
    floatingWindowReady &&
    state.floatingWindow &&
    !state.floatingWindow.isDestroyed()
  ) {
    if (state.isDebugLoggingEnabled()) {
      console.log("[floating] send recording-state", pendingRecordingState);
    }
    state.floatingWindow.webContents.send("recording-state", pendingRecordingState);
  }
}

function showFloatingCoachResult(payload) {
  if (!state.floatingWindow || state.floatingWindow.isDestroyed()) {
    createFloatingWindow();
  }
  if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
    if (state.isDebugLoggingEnabled()) {
      console.log("[floating] send coach-result", payload);
    }
    state.floatingWindow.webContents.send("coach-result", payload);
    showFloatingWindow();
  }
}

function clearFloatingCoachResult() {
  if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
    if (state.isDebugLoggingEnabled()) {
      console.log("[floating] send coach-result-clear");
    }
    state.floatingWindow.webContents.send("coach-result-clear");
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
  pendingVisualizerPayload = payload;

  const flush = () => {
    visualizerFlushTimer = null;
    if (!pendingVisualizerPayload) {
      return;
    }
    if (
      !floatingWindowReady ||
      !state.floatingWindow ||
      state.floatingWindow.isDestroyed()
    ) {
      return;
    }
    lastVisualizerSentAt = Date.now();
    state.floatingWindow.webContents.send("audio-visualizer", pendingVisualizerPayload);
  };

  const now = Date.now();
  const elapsed = now - lastVisualizerSentAt;
  if (elapsed >= VISUALIZER_THROTTLE_MS && !visualizerFlushTimer) {
    lastVisualizerSentAt = now;
    state.floatingWindow.webContents.send("audio-visualizer", payload);
    return;
  }

  if (!visualizerFlushTimer) {
    visualizerFlushTimer = setTimeout(flush, Math.max(0, VISUALIZER_THROTTLE_MS - elapsed));
  }
}

module.exports = {
  createFloatingWindow,
  showFloatingWindow,
  hideFloatingWindow,
  resetFloatingWindow,
  updateFloatingTranscription,
  updateFloatingRecordingState,
  updateFloatingAudioLevel,
  showFloatingCoachResult,
  clearFloatingCoachResult,
};
