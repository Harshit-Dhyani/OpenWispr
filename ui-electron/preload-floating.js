const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("transcriptaFloating", {
  // Recording state
  onRecordingState: (callback) => {
    const handler = (event, state) => callback(state);
    ipcRenderer.on("recording-state", handler);
    return () => ipcRenderer.removeListener("recording-state", handler);
  },

  // Transcription updates
  onTranscription: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on("transcription-update", handler);
    return () => ipcRenderer.removeListener("transcription-update", handler);
  },

  // Audio visualizer data - receives { levels: number[], peak: number }
  onAudioVisualizer: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on("audio-visualizer", handler);
    return () => ipcRenderer.removeListener("audio-visualizer", handler);
  },

  // Hotkey events (start/stop sounds)
  onHotkeyEvent: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on("hotkey-event", handler);
    return () => ipcRenderer.removeListener("hotkey-event", handler);
  },

  // Platform info
  platform: process.platform
});
