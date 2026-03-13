// Shared state for Electron main process
const { app } = require("electron");
const { APP_NAME, APP_SLUG, DOWNLOAD_USER_AGENT } = require("./generated/appMeta");

// Window references
let mainWindow = null;
let floatingWindow = null;
let quickSettingsWindow = null;
let tray = null;
let modelDownloadManager = null;

// Backend process
let backendProcess = null;
const API_ORIGIN = "http://127.0.0.1:8765";
let backendReady = false;
let cachedSettings = null;
let cachedDevices = [];

// Hotkey state
let hotkeyEnabled = false;
let isRecording = false;
let currentHotkeyAccelerator = null;
let currentMicrophoneHotkeyAccelerator = null;
let currentSystemHotkeyAccelerator = null;
let lastHotkeyPressTime = 0;
const HOTKEY_DEBOUNCE_MS = 150;

// Text injection module (loaded dynamically)
let textInjector = null;

// Native module availability flags
let hasRobotjs = false;
let hasNodeKeySender = false;

// Audio feedback enabled
let audioFeedbackEnabled = true;
let lastTranscriptionText = "";

// WebSocket for audio levels
let hotkeyWebSocket = null;
let webSocketReconnectTimeout = null;
let allowHotkeyReconnect = false;
let hotkeyLifecycleState = "idle"; // idle | starting | recording | stopping | error
let pendingRestart = false;
let activeHotkeySessionId = null;
let hotkeyCurrentText = "";
let hotkeyLastError = null;
let hotkeyWebSocketSessionId = null;
let hotkeyWebSocketGeneration = 0;
let hotkeyPendingAction = null;
let pendingRestartSource = null;
let activeHotkeyCaptureSource = null;
let hotkeyLatestPasteCandidate = "";
let hotkeyPastedLiveCandidate = false;
let floatingWindowSuppressResult = false;
let hotkeyMutedAppAudio = false;
let isQuitting = false;

// Tray icons cache
let trayIconIdle = null;
let trayIconRecording = null;

// Module loading flags for WebSocket errors
let wsModuleMissingLogged = false;
let wsConnectionAttempt = 0;
let wsLastErrorTime = 0;
const WS_ERROR_DEBOUNCE_MS = 5000;

// Default hotkey
const DEFAULT_HOTKEY = "CommandOrControl+Shift+T";

let hotkeyConfigState = {
  enabled: false,
  key_combination: DEFAULT_HOTKEY,
  microphone_key_combination: DEFAULT_HOTKEY,
  system_key_combination: "CommandOrControl+Shift+Y",
  hold_mode: false,
  auto_inject: true,
  language: "auto",
  capture_source: "microphone",
  device_id: "default",
  model_name: "small",  // Default ASR model: tiny, base, small, medium, large-v3
  default_asr_model_id: "whisper-medium",
  microphone_asr_model_id: "whisper-medium",
  system_asr_model_id: "whisper-medium",
  finish_mode_default: "finish_and_paste",
  enable_refiner_on_stop: false,
  save_debug_wav: false,
  mute_openwispr_audio_during_dictation: false,
  show_floating_window: true,
  show_floating_coach_result: true,
  floating_window_position: "bottom-right",
  record_on_start: false,
  stop_on_release: false,
  copy_to_clipboard: true,
};

const QUICK_LANGUAGE_OPTIONS = [
  { code: "auto", label: "Auto-detect" },
  { code: "en", label: "English" },
  { code: "hi", label: "Hindi" },
  { code: "es", label: "Spanish" },
  { code: "fr", label: "French" },
  { code: "de", label: "German" },
  { code: "ja", label: "Japanese" },
  { code: "ko", label: "Korean" },
  { code: "zh", label: "Chinese" },
];

function broadcastToWindows(channel, payload) {
  const windows = [mainWindow, floatingWindow, quickSettingsWindow].filter(
    (win) => win && !win.isDestroyed()
  );
  for (const win of windows) {
    win.webContents.send(channel, payload);
  }
}

function isDebugLoggingEnabled() {
  if ((process.env.OPENWISPR_LOG_LEVEL || "").toLowerCase() === "debug") {
    return true;
  }

  const advanced = cachedSettings?.advanced;
  if (!advanced || typeof advanced !== "object") {
    return false;
  }

  return (
    advanced.debugMode === true ||
    String(advanced.logLevel || "").toUpperCase() === "DEBUG"
  );
}

module.exports = {
  // Window references
  get mainWindow() { return mainWindow; },
  set mainWindow(value) { mainWindow = value; },
  get floatingWindow() { return floatingWindow; },
  set floatingWindow(value) { floatingWindow = value; },
  get quickSettingsWindow() { return quickSettingsWindow; },
  set quickSettingsWindow(value) { quickSettingsWindow = value; },
  get tray() { return tray; },
  set tray(value) { tray = value; },
  get modelDownloadManager() { return modelDownloadManager; },
  set modelDownloadManager(value) { modelDownloadManager = value; },

  // Backend
  get backendProcess() { return backendProcess; },
  set backendProcess(value) { backendProcess = value; },
  API_ORIGIN,
  APP_NAME,
  APP_SLUG,
  DOWNLOAD_USER_AGENT,
  get backendReady() { return backendReady; },
  set backendReady(value) { backendReady = value; },
  get cachedSettings() { return cachedSettings; },
  set cachedSettings(value) { cachedSettings = value; },
  get cachedDevices() { return cachedDevices; },
  set cachedDevices(value) { cachedDevices = value; },

  // Hotkey state
  get hotkeyEnabled() { return hotkeyEnabled; },
  set hotkeyEnabled(value) { hotkeyEnabled = value; },
  get isRecording() { return isRecording; },
  set isRecording(value) { isRecording = value; },
  get currentHotkeyAccelerator() { return currentHotkeyAccelerator; },
  set currentHotkeyAccelerator(value) { currentHotkeyAccelerator = value; },
  get currentMicrophoneHotkeyAccelerator() { return currentMicrophoneHotkeyAccelerator; },
  set currentMicrophoneHotkeyAccelerator(value) { currentMicrophoneHotkeyAccelerator = value; },
  get currentSystemHotkeyAccelerator() { return currentSystemHotkeyAccelerator; },
  set currentSystemHotkeyAccelerator(value) { currentSystemHotkeyAccelerator = value; },
  get lastHotkeyPressTime() { return lastHotkeyPressTime; },
  set lastHotkeyPressTime(value) { lastHotkeyPressTime = value; },
  HOTKEY_DEBOUNCE_MS,

  // Text injection
  get textInjector() { return textInjector; },
  set textInjector(value) { textInjector = value; },

  // Native modules
  get hasRobotjs() { return hasRobotjs; },
  set hasRobotjs(value) { hasRobotjs = value; },
  get hasNodeKeySender() { return hasNodeKeySender; },
  set hasNodeKeySender(value) { hasNodeKeySender = value; },

  // Audio feedback
  get audioFeedbackEnabled() { return audioFeedbackEnabled; },
  set audioFeedbackEnabled(value) { audioFeedbackEnabled = value; },
  get lastTranscriptionText() { return lastTranscriptionText; },
  set lastTranscriptionText(value) { lastTranscriptionText = value; },

  // WebSocket
  get hotkeyWebSocket() { return hotkeyWebSocket; },
  set hotkeyWebSocket(value) { hotkeyWebSocket = value; },
  get webSocketReconnectTimeout() { return webSocketReconnectTimeout; },
  set webSocketReconnectTimeout(value) { webSocketReconnectTimeout = value; },
  get allowHotkeyReconnect() { return allowHotkeyReconnect; },
  set allowHotkeyReconnect(value) { allowHotkeyReconnect = value; },
  get hotkeyLifecycleState() { return hotkeyLifecycleState; },
  set hotkeyLifecycleState(value) { hotkeyLifecycleState = value; },
  get pendingRestart() { return pendingRestart; },
  set pendingRestart(value) { pendingRestart = value; },
  get activeHotkeySessionId() { return activeHotkeySessionId; },
  set activeHotkeySessionId(value) { activeHotkeySessionId = value; },
  get hotkeyCurrentText() { return hotkeyCurrentText; },
  set hotkeyCurrentText(value) { hotkeyCurrentText = value; },
  get hotkeyLastError() { return hotkeyLastError; },
  set hotkeyLastError(value) { hotkeyLastError = value; },
  get hotkeyWebSocketSessionId() { return hotkeyWebSocketSessionId; },
  set hotkeyWebSocketSessionId(value) { hotkeyWebSocketSessionId = value; },
  get hotkeyWebSocketGeneration() { return hotkeyWebSocketGeneration; },
  set hotkeyWebSocketGeneration(value) { hotkeyWebSocketGeneration = value; },
  get hotkeyPendingAction() { return hotkeyPendingAction; },
  set hotkeyPendingAction(value) { hotkeyPendingAction = value; },
  get pendingRestartSource() { return pendingRestartSource; },
  set pendingRestartSource(value) { pendingRestartSource = value; },
  get activeHotkeyCaptureSource() { return activeHotkeyCaptureSource; },
  set activeHotkeyCaptureSource(value) { activeHotkeyCaptureSource = value; },
  get hotkeyLatestPasteCandidate() { return hotkeyLatestPasteCandidate; },
  set hotkeyLatestPasteCandidate(value) { hotkeyLatestPasteCandidate = value; },
  get hotkeyPastedLiveCandidate() { return hotkeyPastedLiveCandidate; },
  set hotkeyPastedLiveCandidate(value) { hotkeyPastedLiveCandidate = value; },
  get floatingWindowSuppressResult() { return floatingWindowSuppressResult; },
  set floatingWindowSuppressResult(value) { floatingWindowSuppressResult = value; },
  get hotkeyMutedAppAudio() { return hotkeyMutedAppAudio; },
  set hotkeyMutedAppAudio(value) { hotkeyMutedAppAudio = value; },
  get isQuitting() { return isQuitting; },
  set isQuitting(value) { isQuitting = value; },

  // Tray icons
  get trayIconIdle() { return trayIconIdle; },
  set trayIconIdle(value) { trayIconIdle = value; },
  get trayIconRecording() { return trayIconRecording; },
  set trayIconRecording(value) { trayIconRecording = value; },

  // WebSocket logging
  get wsModuleMissingLogged() { return wsModuleMissingLogged; },
  set wsModuleMissingLogged(value) { wsModuleMissingLogged = value; },
  get wsConnectionAttempt() { return wsConnectionAttempt; },
  set wsConnectionAttempt(value) { wsConnectionAttempt = value; },
  get wsLastErrorTime() { return wsLastErrorTime; },
  set wsLastErrorTime(value) { wsLastErrorTime = value; },
  WS_ERROR_DEBOUNCE_MS,

  // Constants
  DEFAULT_HOTKEY,
  QUICK_LANGUAGE_OPTIONS,
  isDebugLoggingEnabled,

  // Hotkey config
  get hotkeyConfigState() { return hotkeyConfigState; },
  set hotkeyConfigState(value) { hotkeyConfigState = value; },

  // Functions
  broadcastToWindows,
};
