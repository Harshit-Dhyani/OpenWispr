const { contextBridge, ipcRenderer } = require("electron");

const FALLBACK_FLOATING_STRINGS = {
  status: {
    idle: "Ready",
    preparing: "Preparing",
    listening: "Listening",
    transcribing: "Transcribing",
    processing: "Finishing",
    result: "Transcript ready",
    coachResult: "Coach Result",
    error: "Error",
  },
  waitingForSpeech: "Waiting for speech...",
  actions: {
    cancel: "Cancel",
    finish: "Finish",
    close: "Close",
    copyPolished: "Copy Polished",
    copyFinal: "Copy Final",
  },
  resultMeta: {
    transcriptReady: "Transcript ready",
    coachUnavailable: "Coach unavailable",
    livePartialHint: "Live transcript updates during recording.",
    sessionParagraphHint: "Live partials stay temporary until stop.",
    genericError: "Something went wrong.",
  },
  modelPrep: {
    title: "Preparing speech model",
    hint: "The first run can take longer while the model loads into memory.",
  },
};

let floatingStrings = FALLBACK_FLOATING_STRINGS;
try {
  const resolvedStrings = ipcRenderer.sendSync("floating:get-strings");
  if (resolvedStrings && typeof resolvedStrings === "object") {
    floatingStrings = resolvedStrings;
  }
} catch (error) {
  console.error("[floating:preload] Failed to resolve floating strings via IPC, using fallback:", error);
}

let floatingSettings = { showFloatingCoachResult: true };
try {
  const resolvedSettings = ipcRenderer.sendSync("floating:get-settings");
  if (resolvedSettings && typeof resolvedSettings === "object") {
    floatingSettings = resolvedSettings;
  }
} catch (error) {
  console.error("[floating:preload] Failed to resolve floating settings via IPC, using default:", error);
}

const debugEnabled =
  String(process.env.OPENWISPR_LOG_LEVEL || "").toLowerCase() === "debug";

function logFloatingEvent(label, payload) {
  if (!debugEnabled) {
    return;
  }
  console.debug(`[floating:preload] ${label}`, payload);
}

let latestRecordingState = {
  isRecording: false,
  processing: false,
  finished: false,
};
let latestTranscription = {
  text: "",
  committedText: "",
  partialText: "",
  isPartial: false,
};
let latestAudioVisualizer = {
  levels: new Array(36).fill(0),
  peak: 0,
};
let latestCoachResult = null;
let latestModelPreparation = {
  active: false,
  stage: "idle",
  message: "",
  modelName: null,
  sessionId: null,
};

ipcRenderer.on("recording-state", (_event, state) => {
  latestRecordingState = state || latestRecordingState;
  logFloatingEvent("recording-state", latestRecordingState);
});

ipcRenderer.on("transcription-update", (_event, data) => {
  latestTranscription = data || latestTranscription;
});

ipcRenderer.on("audio-visualizer", (_event, data) => {
  latestAudioVisualizer = data || latestAudioVisualizer;
});

ipcRenderer.on("coach-result", (_event, data) => {
  latestCoachResult = data ?? null;
  logFloatingEvent("coach-result", latestCoachResult);
});

ipcRenderer.on("coach-result-clear", () => {
  latestCoachResult = null;
  logFloatingEvent("coach-result-clear");
});

ipcRenderer.on("model-preparation", (_event, data) => {
  latestModelPreparation = data || latestModelPreparation;
  logFloatingEvent("model-preparation", latestModelPreparation);
});

contextBridge.exposeInMainWorld("openwisprFloating", {
  // Recording state
  onRecordingState: (callback) => {
    const handler = (event, state) => callback(state);
    ipcRenderer.on("recording-state", handler);
    callback(latestRecordingState);
    return () => ipcRenderer.removeListener("recording-state", handler);
  },

  // Transcription updates
  onTranscription: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on("transcription-update", handler);
    callback(latestTranscription);
    return () => ipcRenderer.removeListener("transcription-update", handler);
  },

  // Audio visualizer data - receives { levels: number[], peak: number }
  onAudioVisualizer: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on("audio-visualizer", handler);
    callback(latestAudioVisualizer);
    return () => ipcRenderer.removeListener("audio-visualizer", handler);
  },

  // Hotkey events (start/stop sounds)
  onHotkeyEvent: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on("hotkey-event", handler);
    return () => ipcRenderer.removeListener("hotkey-event", handler);
  },

  onCoachResult: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on("coach-result", handler);
    if (latestCoachResult) {
      callback(latestCoachResult);
    }
    return () => ipcRenderer.removeListener("coach-result", handler);
  },

  onCoachResultClear: (callback) => {
    const handler = () => callback();
    ipcRenderer.on("coach-result-clear", handler);
    return () => ipcRenderer.removeListener("coach-result-clear", handler);
  },

  onModelPreparation: (callback) => {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on("model-preparation", handler);
    callback(latestModelPreparation);
    return () => ipcRenderer.removeListener("model-preparation", handler);
  },

  // Platform info
  platform: process.platform,
  strings: floatingStrings,
  settings: floatingSettings,
  debugEnabled,

  // Button actions
  cancelRecording: () => {
    ipcRenderer.send('floating-window-action', { action: 'cancel' });
  },

  finishRecording: () => {
    ipcRenderer.send('floating-window-action', { action: 'finish' });
  },

  finishAndPaste: () => {
    ipcRenderer.send('floating-window-action', { action: 'finish-and-paste' });
  },

  dismissResult: () => {
    ipcRenderer.send('floating-window-action', { action: 'dismiss-result' });
  }
});
