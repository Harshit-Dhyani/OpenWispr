/**
 * Hotkey IPC handlers for OpenWispr Electron main process
 * Handles global hotkey registration, recording lifecycle, WebSocket communication,
 * floating window updates, and text transformation. Key collaborators: handlers.js,
 * floatingWindow.js, hotkeyStopPolicy.js, holdModeHotkeys.js
 * @module hotkeyHandlers
 */
const { clipboard, globalShortcut, net } = require("electron");
const state = require("../shared/state");
const { updateTrayIcon, updateTrayTooltip } = require("../windows/trayUtils");
const { createTray } = require("../windows/tray");
const {
  showFloatingWindow,
  hideFloatingWindow,
  resetFloatingWindow,
  updateFloatingRecordingState,
  updateFloatingModelPreparation,
  updateFloatingAudioLevel,
  updateFloatingTranscription,
  showFloatingCoachResult,
  clearFloatingCoachResult,
} = require("../windows/floatingWindow");
const { injectText } = require("../services/textInjector");
const { createHoldModeController } = require("../services/holdModeHotkeys");
const { shouldKeepFloatingResultVisible } = require("./hotkeyStopPolicy");
const { ELECTRON_STRINGS } = require("../../strings/en");

// Get port from environment variable (set by backend startup script)
const API_PORT = process.env.OPENWISPR_PORT || "8765";
const API_BASE_URL = `http://127.0.0.1:${API_PORT}`;

/**
 * Transforms text via backend API for auto-correction, punctuation, casing, etc.
 * @param {string} text - Raw transcribed text
 * @returns {Promise<string>} Transformed text
 */
async function transformText(text) {
  if (!text || !text.trim()) {
    return text;
  }

  const shouldTransform =
    state.hotkeyConfigState.auto_transform ??
    state.cachedSettings?.hotkey?.auto_transform ??
    true;

  if (!shouldTransform) {
    return text;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/text/transform`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text: text,
        apply_smart_punctuation: true,
        apply_short_forms: true,
        apply_url_normalization: true,
        apply_casing: true,
        apply_user_corrections: true,
        apply_dictionary: true,
        apply_snippets: true,
      }),
    });

    if (!response.ok) {
      console.warn("[main] Transform API failed:", response.status);
      return text;
    }

    const result = await response.json();
    if (result.transformed && result.transformed !== text) {
      if (state.isDebugLoggingEnabled()) {
        console.log(
          "[main] Text transformed:",
          JSON.stringify({
            original: text.substring(0, 50),
            transformed: result.transformed.substring(0, 50),
            expansions: result.expansions?.length || 0,
          })
        );
      }
      return result.transformed;
    }
    return text;
  } catch (error) {
    console.warn("[main] Transform error:", error.message);
    return text;
  }
}

let stopWaiter = null;
let stopInFlightPromise = null;
const holdModeController = createHoldModeController({
  platform: process.platform,
  onPress: async (source) => {
    try {
      await toggleRecordingForSource(source, true, { keepFloatingResultVisible: false });
    } catch (error) {
      console.error("[main] Hold-mode keydown failed:", error.message);
      applyLifecycleState("error", { error: error.message, isRecording: false });
    }
  },
  onRelease: async (source) => {
    try {
      await toggleRecordingForSource(source, false, { keepFloatingResultVisible: false });
    } catch (error) {
      console.error("[main] Hold-mode keyup failed:", error.message);
      applyLifecycleState("error", { error: error.message, isRecording: false });
    }
  },
});

function safeUpdateTrayIcon() {
  try {
    if (typeof updateTrayIcon === "function") {
      updateTrayIcon();
    }
  } catch (e) {
    console.log("[main] Tray icon update failed:", e.message);
  }
}

function safeUpdateTrayTooltip() {
  try {
    if (typeof updateTrayTooltip === "function") {
      updateTrayTooltip();
    }
  } catch (e) {
    console.log("[main] Tray tooltip update failed:", e.message);
  }
}

function safeCreateTray() {
  try {
    if (typeof createTray === "function") {
      return createTray();
    }
  } catch (e) {
    console.log("[main] Tray creation failed:", e.message);
  }
}

function playStopSound() {}

/**
 * Validates if an accelerator string is properly formatted
 * @param {string} accelerator - The keyboard accelerator string to validate
 * @returns {{valid: boolean, error?: string}} Validation result
 */
function validateAccelerator(accelerator) {
  if (!accelerator || typeof accelerator !== "string") {
    return { valid: false, error: ELECTRON_STRINGS.hotkey.errors.noAcceleratorProvided };
  }
  return { valid: true };
}

/**
 * Gets the current renderer status based on lifecycle state
 * @returns {string} Status string: "idle", "listening", "processing", or "error"
 */
function getRendererStatus() {
  switch (state.hotkeyLifecycleState) {
    case "recording":
      return "listening";
    case "starting":
    case "stopping":
      return "processing";
    case "error":
      return "error";
    default:
      return "idle";
  }
}

/**
 * Builds the current hotkey system state payload for IPC communication
 * @returns {object} Complete hotkey state including enabled, isRecording, accelerators, mode, config, session
 */
function buildHotkeyStatePayload() {
  const microphoneAccelerator =
    state.currentMicrophoneHotkeyAccelerator ||
    state.hotkeyConfigState.microphone_key_combination ||
    state.hotkeyConfigState.key_combination ||
    state.DEFAULT_HOTKEY;
  const systemAccelerator =
    state.currentSystemHotkeyAccelerator ||
    state.hotkeyConfigState.system_key_combination ||
    "CommandOrControl+Shift+Y";

  return {
    enabled: state.hotkeyEnabled,
    isRecording: state.isRecording,
    accelerator: microphoneAccelerator,
    microphoneAccelerator,
    systemAccelerator,
    registered: !!(state.currentMicrophoneHotkeyAccelerator || state.currentSystemHotkeyAccelerator),
    defaultHotkey: state.DEFAULT_HOTKEY,
    mode: usesReleaseDrivenHotkeys() ? "hold" : "toggle",
    audioFeedback: state.audioFeedbackEnabled,
    config: {
      ...state.hotkeyConfigState,
      enabled: state.hotkeyEnabled,
      key_combination: microphoneAccelerator,
      microphone_key_combination: microphoneAccelerator,
      system_key_combination: systemAccelerator,
    },
    is_registered: !!(state.currentMicrophoneHotkeyAccelerator || state.currentSystemHotkeyAccelerator),
    error: state.hotkeyLastError,
    capabilities: {
      holdModeSupported: holdModeController.isSupported(),
    },
    session: {
      session_id: state.activeHotkeySessionId,
      is_recording: state.isRecording,
      status: getRendererStatus(),
      lifecycle_state: state.hotkeyLifecycleState,
      capture_source: state.activeHotkeyCaptureSource,
      last_activated_at: null,
      total_activations: 0,
      current_text: state.hotkeyCurrentText,
      duration_ms: 0,
    },
  };
}

/**
 * Broadcasts current hotkey state to all renderer windows
 */
function emitStateChange() {
  const payload = buildHotkeyStatePayload();
  state.broadcastToWindows("hotkey-state-change", payload);
}

/**
 * Broadcasts a transcript event to all renderer windows
 * @param {string} type - Event type (e.g., "hotkey_status", "hotkey_commit_final")
 * @param {object} payload - Event payload data
 */
function emitHotkeyTranscriptEvent(type, payload) {
  state.broadcastToWindows("hotkey-transcript-event", { type, payload });
}

/**
 * Updates the hotkey lifecycle state and syncs UI components
 * @param {string} nextState - New lifecycle state ("idle", "starting", "recording", "stopping", "error")
 * @param {object} [extra={}] - Additional state to merge
 */
function applyLifecycleState(nextState, extra = {}) {
  state.hotkeyLifecycleState = nextState;
  if (extra.sessionId !== undefined) {
    state.activeHotkeySessionId = extra.sessionId;
  }
  if (extra.captureSource !== undefined) {
    state.activeHotkeyCaptureSource = extra.captureSource;
  }
  if (extra.currentText !== undefined) {
    state.hotkeyCurrentText = extra.currentText;
  }
  if (extra.error !== undefined) {
    state.hotkeyLastError = extra.error;
  }
  if (extra.isRecording !== undefined) {
    state.isRecording = extra.isRecording;
  } else {
    state.isRecording = nextState === "recording";
  }
  safeUpdateTrayIcon();
  safeUpdateTrayTooltip();
  emitStateChange();
}

/**
 * Checks if a session ID matches the currently active session
 * @param {string|null} sessionId - Session ID to validate
 * @returns {boolean} True if session is expected/active
 */
function isExpectedHotkeySession(sessionId) {
  if (!sessionId) {
    return true;
  }
  return (
    sessionId === state.activeHotkeySessionId || sessionId === state.hotkeyWebSocketSessionId
  );
}

function resolveStopWaiter(reason = "resolved", sessionId = null) {
  if (stopWaiter) {
    if (sessionId && stopWaiter.sessionId && stopWaiter.sessionId !== sessionId) {
      return;
    }
    if (stopWaiter.timeout) {
      clearTimeout(stopWaiter.timeout);
    }
    stopWaiter.resolve(reason);
    stopWaiter = null;
  }
}

function rejectStopWaiter(error) {
  if (stopWaiter) {
    if (stopWaiter.timeout) {
      clearTimeout(stopWaiter.timeout);
    }
    stopWaiter.reject(error);
    stopWaiter = null;
  }
}

function waitForStopAck(sessionId) {
  if (stopWaiter) {
    return stopWaiter.promise;
  }

  stopWaiter = { sessionId };
  stopWaiter.promise = new Promise((resolve, reject) => {
    stopWaiter.resolve = resolve;
    stopWaiter.reject = reject;
    stopWaiter.timeout = setTimeout(() => {
      console.warn("[main] Timed out waiting for hotkey stop acknowledgement");
      stopWaiter.timeout = null;
    }, 2500);
  }).finally(() => {
    if (stopWaiter?.timeout) {
      clearTimeout(stopWaiter.timeout);
    }
  });

  return stopWaiter.promise;
}

/**
 * Resolves the capture source from config ("system" or "microphone")
 * @param {object} [config=state.hotkeyConfigState] - Configuration to resolve from
 * @returns {string} Capture source
 */
function resolveCaptureSource(config = state.hotkeyConfigState) {
  return config.capture_source === "system" ? "system" : "microphone";
}

/**
 * Resolves the ASR model ID to use based on capture source and config
 * @param {object} [config=state.hotkeyConfigState] - Configuration to resolve from
 * @returns {string} Model identifier
 */
function resolveHotkeyModelId(config = state.hotkeyConfigState) {
  const captureSource = resolveCaptureSource(config);
  const sourceSpecificModel =
    captureSource === "system"
      ? config.system_asr_model_id
      : config.microphone_asr_model_id;
  return (
    sourceSpecificModel ||
    config.default_asr_model_id ||
    config.model_name ||
    "whisper-medium"
  );
}

/**
 * Checks if a hotkey accelerator is available or already registered
 * @param {string} accelerator - The accelerator string to check
 * @returns {{registered: boolean, ownedByApp?: boolean, error?: string}} Availability result
 */
function checkHotkeyAvailability(accelerator) {
  try {
    if (
      (state.currentHotkeyAccelerator === accelerator ||
        state.currentMicrophoneHotkeyAccelerator === accelerator ||
        state.currentSystemHotkeyAccelerator === accelerator) &&
      globalShortcut.isRegistered(accelerator)
    ) {
      return { registered: false, ownedByApp: true };
    }

    const testRegistered = globalShortcut.register(accelerator, () => {});
    if (testRegistered) {
      globalShortcut.unregister(accelerator);
      return { registered: false };
    }
    return {
      registered: true,
      error: `Hotkey "${accelerator}" may already be registered by another application`,
    };
  } catch (error) {
    return { registered: false, error: error.message };
  }
}

/**
 * Resolves the transcription mode from cached settings
 * @returns {string} Transcription mode ("dictation" or "session")
 */
function resolveTranscriptionMode() {
  return state.cachedSettings?.transcription?.transcription_mode || "dictation";
}

/**
 * Checks if app audio should be muted during dictation for the given source
 * @param {string} captureSource - Audio capture source
 * @returns {boolean} True if app audio should be muted
 */
function shouldMuteAppAudioDuringDictation(captureSource) {
  if (captureSource !== "microphone") {
    return false;
  }
  if (state.hotkeyConfigState?.mute_openwispr_audio_during_dictation !== undefined) {
    return Boolean(state.hotkeyConfigState.mute_openwispr_audio_during_dictation);
  }
  return Boolean(state.cachedSettings?.audio?.mute_openwispr_audio_during_dictation);
}

/**
 * Mutes or unmutes audio in all OpenWispr windows
 * @param {boolean} muted - Whether to mute audio
 */
function setOpenwisprWindowAudioMuted(muted) {
  const windows = [state.mainWindow, state.floatingWindow, state.quickSettingsWindow];
  for (const win of windows) {
    if (!win || win.isDestroyed()) {
      continue;
    }
    try {
      win.webContents.setAudioMuted(Boolean(muted));
    } catch (error) {
      if (state.isDebugLoggingEnabled()) {
        console.warn("[main] Failed to update window mute state:", error.message);
      }
    }
  }
}

/**
 * Clears all registered global shortcuts and hold-mode controllers
 */
function clearRegisteredHotkeys() {
  holdModeController.clear();
  if (state.currentMicrophoneHotkeyAccelerator) {
    globalShortcut.unregister(state.currentMicrophoneHotkeyAccelerator);
    state.currentMicrophoneHotkeyAccelerator = null;
  }
  if (state.currentSystemHotkeyAccelerator) {
    globalShortcut.unregister(state.currentSystemHotkeyAccelerator);
    state.currentSystemHotkeyAccelerator = null;
  }
  state.currentHotkeyAccelerator = null;
}

/**
 * Toggles recording state for a specific audio source with debouncing
 * @param {string} source - Audio source ("microphone" or "system")
 * @param {boolean|undefined} forceState - Force start (true), stop (false), or toggle (undefined)
 * @param {object} [options={}] - Toggle options
 * @param {boolean} [options.keepFloatingResultVisible=false] - Whether to keep floating window visible
 */
async function toggleRecordingForSource(source, forceState, options = {}) {
  const now = Date.now();
  const useDebounce = forceState === undefined;
  if (useDebounce && now - state.lastHotkeyPressTime < state.HOTKEY_DEBOUNCE_MS) {
    return;
  }
  if (useDebounce) {
    state.lastHotkeyPressTime = now;
  }

  const requestedSource = source === "system" ? "system" : "microphone";
  const lifecycle = state.hotkeyLifecycleState;
  const activeSource = state.activeHotkeyCaptureSource || resolveCaptureSource();
  const shouldStart =
    forceState !== undefined ? forceState : lifecycle === "idle" || lifecycle === "error";

  if (shouldStart) {
    if (lifecycle === "starting" && activeSource === requestedSource) {
      return;
    }
    if (lifecycle === "recording" && activeSource === requestedSource) {
      return;
    }
    if (lifecycle === "stopping") {
      state.pendingRestart = true;
      state.pendingRestartSource = requestedSource;
      return;
    }
    if ((lifecycle === "starting" || lifecycle === "recording") && activeSource !== requestedSource) {
      state.pendingRestart = true;
      state.pendingRestartSource = requestedSource;
      await stopRecording({
        keepFloatingResultVisible: options.keepFloatingResultVisible ?? false,
      });
      return;
    }

    try {
      await startRecording(requestedSource);
    } catch (error) {
      console.error("[main] Toggle error:", error.message);
      applyLifecycleState("error", {
        error: error.message,
        isRecording: false,
        captureSource: null,
      });
      hideFloatingWindow();
    }
    return;
  }

  if (lifecycle === "idle" || lifecycle === "error" || lifecycle === "stopping") {
    return;
  }

  try {
    await stopRecording({
      keepFloatingResultVisible: options.keepFloatingResultVisible ?? false,
    });
  } catch (error) {
    console.error("[main] Stop failed:", error.message);
    applyLifecycleState("error", {
      error: error.message,
      isRecording: false,
      captureSource: null,
    });
    hideFloatingWindow();
  }
}

/**
 * Checks if hold-mode (release-driven) hotkeys are configured
 * @param {object} [config=state.hotkeyConfigState] - Configuration to check
 * @returns {boolean} True if hold mode is enabled
 */
function usesReleaseDrivenHotkeys(config = state.hotkeyConfigState) {
  return Boolean(config.hold_mode || config.stop_on_release);
}

/**
 * Registers microphone and system audio hotkeys based on current configuration
 * Supports both toggle mode and hold (release-driven) mode
 * @returns {object} Registration result with success boolean and accelerator details
 */
function registerConfiguredHotkeys() {
  if (!state.hotkeyEnabled) {
    return { success: false, error: "Hotkey system is disabled" };
  }

  const microphoneAccelerator =
    state.hotkeyConfigState.microphone_key_combination ||
    state.hotkeyConfigState.key_combination ||
    state.DEFAULT_HOTKEY;
  const systemAccelerator =
    state.hotkeyConfigState.system_key_combination || "CommandOrControl+Shift+Y";

  if (
    microphoneAccelerator &&
    systemAccelerator &&
    microphoneAccelerator === systemAccelerator
  ) {
    return {
      success: false,
      error: "Microphone and system audio hotkeys must be different",
    };
  }

  for (const accelerator of [microphoneAccelerator, systemAccelerator]) {
    const validation = validateAccelerator(accelerator);
    if (!validation.valid) {
      return { success: false, error: validation.error };
    }
    if (!usesReleaseDrivenHotkeys()) {
      const availability = checkHotkeyAvailability(accelerator);
      if (availability.registered && availability.error) {
        return { success: false, error: availability.error };
      }
    }
  }

  clearRegisteredHotkeys();

  if (usesReleaseDrivenHotkeys()) {
    const holdRegistration = holdModeController.configure([
      { accelerator: microphoneAccelerator, source: "microphone" },
      { accelerator: systemAccelerator, source: "system" },
    ]);
    if (!holdRegistration.success) {
      return { success: false, error: holdRegistration.error };
    }

    state.currentMicrophoneHotkeyAccelerator = microphoneAccelerator;
    state.currentSystemHotkeyAccelerator = systemAccelerator;
    state.currentHotkeyAccelerator = microphoneAccelerator;
    emitStateChange();
    return {
      success: true,
      accelerator: microphoneAccelerator,
      microphoneAccelerator,
      systemAccelerator,
      isToggleMode: false,
    };
  }

  let microphoneRegistered = false;
  let systemRegistered = false;

  try {
    microphoneRegistered = globalShortcut.register(microphoneAccelerator, async () => {
      try {
        await toggleRecordingForSource("microphone");
      } catch (error) {
        console.error("[main] Hotkey toggle error:", error);
        applyLifecycleState("error", { error: error.message, isRecording: false });
      }
    });

    systemRegistered = globalShortcut.register(systemAccelerator, async () => {
      try {
        await toggleRecordingForSource("system");
      } catch (error) {
        console.error("[main] Hotkey toggle error:", error);
        applyLifecycleState("error", { error: error.message, isRecording: false });
      }
    });

    if (!microphoneRegistered || !systemRegistered) {
      clearRegisteredHotkeys();
      return { success: false, error: "Failed to register hotkey" };
    }

    state.currentMicrophoneHotkeyAccelerator = microphoneAccelerator;
    state.currentSystemHotkeyAccelerator = systemAccelerator;
    state.currentHotkeyAccelerator = microphoneAccelerator;
    emitStateChange();
    return {
      success: true,
      accelerator: microphoneAccelerator,
      microphoneAccelerator,
      systemAccelerator,
      isToggleMode: true,
    };
  } catch (error) {
    clearRegisteredHotkeys();
    return { success: false, error: error.message };
  }
}

/**
 * Registers a global hotkey with the system using the provided accelerator
 * @param {string} accelerator - The keyboard accelerator to register
 * @returns {{success: boolean, accelerator?: string, error?: string}} Registration result
 */
function registerHotkey(accelerator) {
  state.hotkeyConfigState = {
    ...state.hotkeyConfigState,
    key_combination: accelerator,
    microphone_key_combination: accelerator,
  };
  return registerConfiguredHotkeys();
}

/**
 * Unregisters all currently registered global hotkeys
 * @returns {{success: boolean, wasRegistered: boolean}} Unregistration result
 */
function unregisterHotkey() {
  clearRegisteredHotkeys();
  emitStateChange();
  return { success: true, wasRegistered: true };
}

/**
 * Establishes WebSocket connection for real-time transcription events
 * @param {string|null} sessionId - The recording session identifier
 */
async function connectHotkeyWebSocket(sessionId) {
  try {
    const WebSocket = require("ws");
    const wsUrl = `ws://127.0.0.1:${API_PORT}/api/transcription/hotkey/ws`;
    if (state.hotkeyWebSocket) {
      closeHotkeyWebSocket();
    }

    state.hotkeyWebSocket = new WebSocket(wsUrl);
    state.hotkeyWebSocketSessionId = sessionId;

    state.hotkeyWebSocket.on("open", () => {});

    state.hotkeyWebSocket.on("message", (data) => {
      try {
        const message = JSON.parse(data);
        const payload = message.payload || {};

        if (message.type === "hotkey_audio_level") {
          if (
            state.hotkeyLifecycleState === "stopping" ||
            !isExpectedHotkeySession(payload.session_id)
          ) {
            return;
          }
          const { levels, peak, audio_level } = payload;
          updateFloatingAudioLevel(levels || [], peak || audio_level || 0);
          return;
        }

        if (message.type === "hotkey_status") {
          if (!isExpectedHotkeySession(payload.session_id)) {
            return;
          }
          emitHotkeyTranscriptEvent("hotkey_status", payload);
          state.activeHotkeySessionId = payload.session_id ?? state.activeHotkeySessionId;
          state.hotkeyCurrentText = payload.display_partial_text || payload.partial_text || "";
          state.hotkeyLastError = null;
          if (payload.state === "recording") {
            updateFloatingRecordingState({
              isRecording: true,
              processing: false,
              finished: false,
              sessionId: payload.session_id ?? state.activeHotkeySessionId,
              mode: resolveTranscriptionMode(),
            });
            applyLifecycleState("recording", {
              sessionId: payload.session_id,
              currentText: state.hotkeyCurrentText,
            });
          } else if (payload.state === "stopping") {
            updateFloatingRecordingState({
              isRecording: false,
              processing: true,
              finished: false,
              sessionId: payload.session_id ?? state.activeHotkeySessionId,
              mode: resolveTranscriptionMode(),
            });
            applyLifecycleState("stopping", {
              sessionId: payload.session_id,
              currentText: state.hotkeyCurrentText,
              isRecording: false,
            });
          }

          // Message type handlers continue below...
          if (!isExpectedHotkeySession(payload.session_id)) {
            return;
          }
          const stage = payload.stage || "loading";
          
          // Store model info when first received, preserve for subsequent events
          if (payload.stt_model) {
            state.hotkeySttModel = payload.stt_model;
          }
          if (payload.llm_provider) {
            state.hotkeyLlmProvider = payload.llm_provider;
          }
          if (payload.llm_model) {
            state.hotkeyLlmModel = payload.llm_model;
          }
          
          updateFloatingModelPreparation({
            active: stage !== "ready" && stage !== "error",
            stage,
            message: payload.message || "",
            modelName: payload.model_name || null,
            sessionId: payload.session_id ?? state.activeHotkeySessionId,
            sttModel: payload.stt_model || state.hotkeySttModel || null,
            llmProvider: payload.llm_provider || state.hotkeyLlmProvider || null,
            llmModel: payload.llm_model || state.hotkeyLlmModel || null,
          });
          return;
        }

        if (message.type === "hotkey_partial" || message.type === "hotkey_draft_partial") {
          if (
            !isExpectedHotkeySession(payload.session_id) ||
            state.hotkeyLifecycleState === "stopping"
          ) {
            return;
          }
          const text = payload.display_partial_text || payload.partial_text || "";
          state.hotkeyCurrentText = text;
          emitStateChange();
          emitHotkeyTranscriptEvent("hotkey_draft_partial", payload);
          if (text) {
            // Don't clear model preparation - preserve it until backend says ready
            updateFloatingTranscription(text, {
              sessionId: payload.session_id ?? state.activeHotkeySessionId,
              mode: payload.transcription_mode || resolveTranscriptionMode(),
              committedText: state.hotkeyLatestPasteCandidate || "",
              partialText: text,
              isPartial: true,
            });
          }
          return;
        }

        if (message.type === "hotkey_commit_final") {
          if (
            !isExpectedHotkeySession(payload.session_id) ||
            state.hotkeyLifecycleState === "stopping"
          ) {
            return;
          }
          emitHotkeyTranscriptEvent("hotkey_commit_final", payload);
          const liveBufferText =
            payload.live_buffer_text ||
            payload.segment?.display_text ||
            payload.segment?.text ||
            payload.committed_text ||
            payload.text ||
            "";
          if (liveBufferText) {
            state.hotkeyLatestPasteCandidate = liveBufferText;
            if (state.hotkeyConfigState.copy_to_clipboard) {
              try {
                clipboard.writeText(liveBufferText);
              } catch (error) {
                console.warn("[main] Clipboard live update failed:", error.message);
              }
            }
          }
          const text =
            payload.segment?.display_text ||
            payload.segment?.text ||
            payload.committed_text ||
            payload.text ||
            "";
          if (text) {
            updateFloatingModelPreparation({
              active: false,
              stage: "ready",
              message: "",
              sessionId: payload.session_id ?? state.activeHotkeySessionId,
              sttModel: payload.stt_model || state.hotkeySttModel || null,
              llmProvider: payload.llm_provider || state.hotkeyLlmProvider || null,
              llmModel: payload.llm_model || state.hotkeyLlmModel || null,
            });
            updateFloatingTranscription(liveBufferText || text, {
              sessionId: payload.session_id ?? state.activeHotkeySessionId,
              mode: payload.transcription_mode || resolveTranscriptionMode(),
              segmentIndex: payload.segment_index ?? payload.segment?.index ?? null,
              committedText: liveBufferText || text,
              partialText: "",
              isPartial: false,
            });
          }
          return;
        }

        if (message.type === "final_text") {
          if (!isExpectedHotkeySession(payload.session_id)) {
            return;
          }
          emitHotkeyTranscriptEvent("final_text", payload);
          const text = payload.text || payload.final_text || "";
          if (text) {
            state.hotkeyLatestPasteCandidate = text;
            updateFloatingModelPreparation({
              active: false,
              stage: "ready",
              message: "",
              sessionId: payload.session_id ?? state.activeHotkeySessionId,
              sttModel: payload.stt_model || state.hotkeySttModel || null,
              llmProvider: payload.llm_provider || state.hotkeyLlmProvider || null,
              llmModel: payload.llm_model || state.hotkeyLlmModel || null,
            });
            updateFloatingTranscription(text, {
              sessionId: payload.session_id ?? state.activeHotkeySessionId,
              mode: payload.mode || resolveTranscriptionMode(),
              committedText: text,
              partialText: "",
              isPartial: false,
            });
          }
          return;
        }

        if (message.type === "hotkey_started") {
          if (!isExpectedHotkeySession(payload.session_id)) {
            return;
          }
          updateFloatingRecordingState({
            isRecording: true,
            processing: false,
            finished: false,
            sessionId: payload.session_id ?? state.activeHotkeySessionId,
            mode: payload.transcription_mode || resolveTranscriptionMode(),
          });
          updateFloatingTranscription("", {
            sessionId: payload.session_id ?? state.activeHotkeySessionId,
            mode: payload.transcription_mode || resolveTranscriptionMode(),
            committedText: "",
            partialText: "",
            isPartial: false,
          });
          updateFloatingModelPreparation({
            active: true,
            stage: "loading",
            message: "Loading models...",
            sessionId: payload.session_id ?? state.activeHotkeySessionId,
            sttModel: payload.stt_model || state.hotkeySttModel || null,
            llmProvider: payload.llm_provider || state.hotkeyLlmProvider || null,
            llmModel: payload.llm_model || state.hotkeyLlmModel || null,
          });
          applyLifecycleState("recording", {
            sessionId: payload.session_id ?? state.activeHotkeySessionId,
          });
          return;
        }

        if (message.type === "hotkey_stopping") {
          if (!isExpectedHotkeySession(payload.session_id)) {
            return;
          }
          updateFloatingRecordingState({
            isRecording: false,
            processing: true,
            finished: false,
            sessionId: payload.session_id ?? state.activeHotkeySessionId,
            mode: payload.transcription_mode || resolveTranscriptionMode(),
          });
          updateFloatingTranscription(
            state.hotkeyLatestPasteCandidate || state.hotkeyCurrentText || "",
            {
              sessionId: payload.session_id ?? state.activeHotkeySessionId,
              mode: payload.transcription_mode || resolveTranscriptionMode(),
              committedText: state.hotkeyLatestPasteCandidate || "",
              partialText: "",
              isPartial: false,
            },
          );
          applyLifecycleState("stopping", {
            sessionId: payload.session_id ?? state.activeHotkeySessionId,
            currentText: "",
            isRecording: false,
          });
          resolveStopWaiter("hotkey_stopping", payload.session_id ?? null);
          return;
        }

        if (message.type === "hotkey_stop_ack") {
          if (!isExpectedHotkeySession(payload.session_id)) {
            return;
          }
          updateFloatingRecordingState({
            isRecording: false,
            processing: true,
            finished: false,
            sessionId: payload.session_id ?? state.activeHotkeySessionId,
            mode: payload.transcription_mode || resolveTranscriptionMode(),
          });
          updateFloatingTranscription(
            state.hotkeyLatestPasteCandidate || state.hotkeyCurrentText || "",
            {
              sessionId: payload.session_id ?? state.activeHotkeySessionId,
              mode: payload.transcription_mode || resolveTranscriptionMode(),
              committedText: state.hotkeyLatestPasteCandidate || "",
              partialText: "",
              isPartial: false,
            },
          );
          applyLifecycleState("stopping", {
            sessionId: payload.session_id ?? state.activeHotkeySessionId,
            currentText: "",
            isRecording: false,
          });
          resolveStopWaiter("hotkey_stop_ack", payload.session_id ?? null);
          return;
        }

        if (message.type === "hotkey_stopped") {
          if (!isExpectedHotkeySession(payload.session_id)) {
            return;
          }
          emitHotkeyTranscriptEvent("hotkey_stopped", payload);
          const text =
            payload.paste_text ||
            payload.postprocessed_text ||
            payload.aggregated_clean_text ||
            payload.composed_text ||
            payload.final_transcription ||
            "";
          if (text && state.hotkeyPendingAction !== "cancel") {
            state.lastTranscriptionText = text;
            if (state.hotkeyConfigState.copy_to_clipboard) {
              try {
                clipboard.writeText(text);
              } catch (error) {
                console.warn("[main] Clipboard final update failed:", error.message);
              }
            }
            if (
              state.hotkeyPendingAction === "finish_and_paste" &&
              state.hotkeyConfigState.auto_inject &&
              !state.hotkeyPastedLiveCandidate
            ) {
              // paste_text already has transformations applied by backend
              // Inject directly without redundant API call for maximum speed
              void injectText(text).catch((error) => {
                console.error("[main] Hotkey text injection failed:", error.message);
              });
            }
          }
          const shouldEnableFloatingCoachResult =
            state.hotkeyConfigState.show_floating_coach_result ??
            state.cachedSettings?.coach?.show_floating_coach_result;
          const coachStatus = payload.coach_status || "disabled";
          const hasCoachFailure = coachStatus === "failed" || coachStatus === "fallback";
          const shouldShowCoachResult =
            Boolean(shouldEnableFloatingCoachResult) &&
            !state.floatingWindowSuppressResult &&
            (Boolean(payload.coach_result) || hasCoachFailure);
          if (state.isDebugLoggingEnabled()) {
            console.log(
              "[main] Coach floating decision:",
              JSON.stringify({
                showFloatingCoachResult: Boolean(shouldEnableFloatingCoachResult),
                suppressed: Boolean(state.floatingWindowSuppressResult),
                coachStatus,
                hasCoachResult: Boolean(payload.coach_result),
                shouldShowCoachResult,
              }),
            );
          }
          if (state.hotkeyPendingAction === "cancel") {
            clearFloatingCoachResult();
            resetFloatingWindow();
            hideFloatingWindow();
          } else if (shouldShowCoachResult) {
            showFloatingCoachResult(payload);
          } else {
            clearFloatingCoachResult();
            updateFloatingTranscription(text || payload.final_transcription || "", {
              sessionId: payload.session_id ?? state.activeHotkeySessionId,
              mode: payload.transcription_mode || resolveTranscriptionMode(),
              committedText: text || payload.final_transcription || "",
              partialText: "",
              isPartial: false,
            });
            updateFloatingRecordingState({
              isRecording: false,
              processing: false,
              finished: true,
              sessionId: payload.session_id ?? state.activeHotkeySessionId,
              mode: payload.transcription_mode || resolveTranscriptionMode(),
            });
          }
          state.hotkeyCurrentText = "";
          state.hotkeyLatestPasteCandidate = "";
          state.hotkeyPastedLiveCandidate = false;
          state.floatingWindowSuppressResult = false;
          state.hotkeyPendingAction = null;
          applyLifecycleState("idle", {
            sessionId: null,
            currentText: "",
            isRecording: false,
            captureSource: null,
          });
          resolveStopWaiter("hotkey_stopped", payload.session_id ?? null);
          if (state.pendingRestart) {
            const nextSource = state.pendingRestartSource || resolveCaptureSource();
            state.pendingRestart = false;
            state.pendingRestartSource = null;
            void startRecording(nextSource);
          }
          return;
        }

        if (message.type === "hotkey_error") {
          updateFloatingRecordingState({
            isRecording: false,
            processing: false,
            finished: false,
            error: payload.error || "Hotkey websocket error",
            sessionId: payload.session_id ?? state.activeHotkeySessionId,
            mode: payload.transcription_mode || resolveTranscriptionMode(),
          });
          applyLifecycleState("error", {
            error: payload.error || "Hotkey websocket error",
            isRecording: false,
          });
          rejectStopWaiter(new Error(payload.error || "Hotkey websocket error"));
        }
      } catch (e) {
        console.error("[main] WebSocket message error:", e.message);
      }
    });

    state.hotkeyWebSocket.on("close", (code, reason) => {
      state.hotkeyWebSocket = null;
      state.hotkeyWebSocketSessionId = null;
      state.hotkeySttModel = null;
      state.hotkeyLlmProvider = null;
      state.hotkeyLlmModel = null;
      if (code === 1000 && state.hotkeyLifecycleState === "stopping") {
        resolveStopWaiter(reason || "normal-close");
        return;
      }

      if (state.hotkeyLifecycleState === "starting" || state.hotkeyLifecycleState === "recording") {
        applyLifecycleState("error", {
          error: `Hotkey websocket closed (${code || "unknown"})`,
          isRecording: false,
        });
      }
    });
  } catch {}
}

/**
 * Closes the active hotkey WebSocket connection
 */
function closeHotkeyWebSocket() {
  if (state.hotkeyWebSocket) {
    try {
      state.hotkeyWebSocket.close(1000, "client-close");
    } catch (error) {
      console.error("[main] Failed to close websocket:", error.message);
    }
    state.hotkeyWebSocket = null;
    state.hotkeyWebSocketSessionId = null;
  }
}

/**
 * Applies hotkey configuration and re-registers hotkeys with new settings
 * @param {object} config - Hotkey configuration object with key_combination, enabled, etc.
 * @returns {{success: boolean, enabled?: boolean, error?: string}} Application result
 */
async function applyHotkeyConfig(config) {
  state.hotkeyConfigState = {
    ...state.hotkeyConfigState,
    ...config,
    key_combination:
      config.key_combination ||
      state.hotkeyConfigState.key_combination ||
      state.DEFAULT_HOTKEY,
    microphone_key_combination:
      config.microphone_key_combination ||
      config.key_combination ||
      state.hotkeyConfigState.microphone_key_combination ||
      state.hotkeyConfigState.key_combination ||
      state.DEFAULT_HOTKEY,
    system_key_combination:
      config.system_key_combination ||
      state.hotkeyConfigState.system_key_combination ||
      "CommandOrControl+Shift+Y",
    model_name: config.model_name || state.hotkeyConfigState.model_name || "small",
    capture_source:
      config.capture_source || state.hotkeyConfigState.capture_source || "microphone",
    default_asr_model_id:
      config.default_asr_model_id ||
      state.hotkeyConfigState.default_asr_model_id ||
      "whisper-medium",
    microphone_asr_model_id:
      config.microphone_asr_model_id ||
      state.hotkeyConfigState.microphone_asr_model_id ||
      "whisper-medium",
    system_asr_model_id:
      config.system_asr_model_id ||
      state.hotkeyConfigState.system_asr_model_id ||
      "whisper-medium",
    show_floating_coach_result:
      config.show_floating_coach_result !== undefined
        ? config.show_floating_coach_result
        : state.hotkeyConfigState.show_floating_coach_result,
  };

  state.hotkeyEnabled =
    config.enabled !== undefined ? config.enabled : state.hotkeyEnabled;

  if (!state.hotkeyEnabled) {
    unregisterHotkey();
    safeUpdateTrayTooltip();
    return { success: true, enabled: false };
  }

  const result = registerConfiguredHotkeys();
  if (result.success) {
    state.hotkeyLastError = null;
    safeUpdateTrayTooltip();
  } else {
    state.hotkeyLastError = result.error || "Failed to register hotkey";
    emitStateChange();
  }
  return result;
}

/**
 * Starts a new recording session for the specified audio source
 * @param {string} [source="microphone"] - Audio source ("microphone" or "system")
 * @returns {Promise<object>} Session start result with session_id
 */
async function startRecording(source = resolveCaptureSource()) {
  const captureSource = source === "system" ? "system" : "microphone";
  const muteAppAudio = shouldMuteAppAudioDuringDictation(captureSource);
  state.hotkeyLatestPasteCandidate = "";
  state.hotkeyPastedLiveCandidate = false;
  state.floatingWindowSuppressResult = false;
  if (muteAppAudio) {
    setOpenwisprWindowAudioMuted(true);
    state.hotkeyMutedAppAudio = true;
  }
  applyLifecycleState("starting", {
    error: null,
    currentText: "",
    captureSource,
  });

  if (state.hotkeyConfigState.show_floating_window) {
    clearFloatingCoachResult();
    resetFloatingWindow();
    showFloatingWindow();
    updateFloatingRecordingState({
      isRecording: true,
      processing: false,
      finished: false,
      sessionId: null,
      mode: resolveTranscriptionMode(),
    });
  }

  const resolvedModelId = resolveHotkeyModelId({
    ...state.hotkeyConfigState,
    capture_source: captureSource,
  });
  let response;
  try {
    response = await fetch(`${state.API_ORIGIN}/api/transcription/hotkey/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        capture_source: captureSource,
        device_id:
          captureSource === "microphone" &&
          state.hotkeyConfigState.device_id !== "default"
            ? state.hotkeyConfigState.device_id
            : null,
        model_name: resolvedModelId,
        language_mode:
          state.hotkeyConfigState.language ||
          state.cachedSettings?.general?.defaultLanguage ||
          "auto",
        transcription_mode: resolveTranscriptionMode(),
      }),
    });
  } catch (error) {
    if (state.hotkeyMutedAppAudio) {
      setOpenwisprWindowAudioMuted(false);
      state.hotkeyMutedAppAudio = false;
    }
    throw error;
  }

  if (!response.ok) {
    if (state.hotkeyMutedAppAudio) {
      setOpenwisprWindowAudioMuted(false);
      state.hotkeyMutedAppAudio = false;
    }
    throw new Error(`Start failed: ${response.status}`);
  }

  const result = await response.json();
  state.hotkeyLatestPasteCandidate = "";
  state.hotkeyPastedLiveCandidate = false;
  state.activeHotkeySessionId = result.session_id || null;
  await connectHotkeyWebSocket(result.session_id || null);
  applyLifecycleState("starting", {
    sessionId: result.session_id || null,
    error: null,
    currentText: "",
    captureSource,
  });
  return result;
}

/**
 * Stops the current recording session and processes final transcription
 * @param {object} [options={}] - Stop options
 * @param {boolean} [options.keepFloatingResultVisible=false] - Whether to keep floating window visible after stop
 * @returns {Promise<object>} Stop result with final transcription data
 */
async function stopRecording(options = {}) {
  if (state.hotkeyLifecycleState === "idle" || state.hotkeyLifecycleState === "error") {
    return;
  }
  if (state.hotkeyLifecycleState === "stopping" && stopInFlightPromise) {
    return stopInFlightPromise;
  }

  const pendingAction =
    state.hotkeyPendingAction ||
    state.hotkeyConfigState.finish_mode_default ||
    (state.hotkeyConfigState.auto_inject ? "finish_and_paste" : "finish");

  state.hotkeyPendingAction = pendingAction;
  const shouldKeepFloatingVisible = shouldKeepFloatingResultVisible({
    showFloatingWindow: state.hotkeyConfigState.show_floating_window,
    pendingAction,
    keepResultVisible: options.keepFloatingResultVisible ?? false,
  });
  state.floatingWindowSuppressResult = !shouldKeepFloatingVisible;
  if (shouldKeepFloatingVisible) {
    updateFloatingRecordingState({
      isRecording: false,
      processing: true,
      finished: false,
      sessionId: state.activeHotkeySessionId,
      mode: resolveTranscriptionMode(),
      error: null,
    });
    updateFloatingTranscription(
      state.hotkeyLatestPasteCandidate || state.hotkeyCurrentText || "",
      {
        sessionId: state.activeHotkeySessionId,
        mode: resolveTranscriptionMode(),
        committedText: state.hotkeyLatestPasteCandidate || "",
        partialText: "",
        isPartial: false,
      },
    );
  } else {
    resetFloatingWindow();
    hideFloatingWindow();
  }
  applyLifecycleState("stopping", { currentText: "", isRecording: false });

  stopInFlightPromise = (async () => {
    const stopAck = waitForStopAck(state.activeHotkeySessionId).catch((error) => {
      console.warn("[main] Hotkey stop acknowledgement failed:", error.message);
      return "error";
    });
    const responsePromise = fetch(`${state.API_ORIGIN}/api/transcription/hotkey/stop`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: pendingAction }),
    });

    await stopAck;
    if (
      pendingAction === "finish_and_paste" &&
      state.hotkeyConfigState.auto_inject &&
      state.hotkeyLatestPasteCandidate &&
      resolveTranscriptionMode() !== "session_paragraph"
    ) {
      state.hotkeyPastedLiveCandidate = true;
      state.lastTranscriptionText = state.hotkeyLatestPasteCandidate;
      if (state.hotkeyConfigState.copy_to_clipboard) {
        try {
          clipboard.writeText(state.hotkeyLatestPasteCandidate);
        } catch (error) {
          console.warn("[main] Clipboard stop-ack update failed:", error.message);
        }
      }
      void injectText(state.hotkeyLatestPasteCandidate).catch((error) => {
        console.error("[main] Hotkey live text injection failed:", error.message);
      });
    }

    const response = await responsePromise;

    let result = {};
    try {
      result = await response.json();
    } catch {
      result = {};
    }

    if (!response.ok) {
      throw new Error(`Stop failed: ${response.status}`);
    }

    const finalText =
      result?.paste_text ||
      result?.postprocessed_text ||
      result?.aggregated_clean_text ||
      result?.composed_text ||
      result?.final_transcription ||
      "";
    if (
      shouldKeepFloatingVisible &&
      finalText &&
      !state.floatingWindowSuppressResult
    ) {
      updateFloatingTranscription(finalText, {
        sessionId: result?.session_id ?? state.activeHotkeySessionId,
        mode: result?.transcription_mode || resolveTranscriptionMode(),
        committedText: finalText,
        partialText: "",
        isPartial: false,
      });
      updateFloatingRecordingState({
        isRecording: false,
        processing: false,
        finished: true,
        sessionId: result?.session_id ?? state.activeHotkeySessionId,
        mode: result?.transcription_mode || resolveTranscriptionMode(),
      });
    }
    return result;
  })();

  try {
    return await stopInFlightPromise;
  } catch (error) {
    state.hotkeyLatestPasteCandidate = "";
    state.hotkeyPastedLiveCandidate = false;
    state.floatingWindowSuppressResult = false;
    state.hotkeyPendingAction = null;
    throw error;
  } finally {
    if (state.hotkeyMutedAppAudio) {
      setOpenwisprWindowAudioMuted(false);
      state.hotkeyMutedAppAudio = false;
    }
    stopInFlightPromise = null;
  }
}

/**
 * IPC handler wrapper for starting recording - initiates recording and returns state
 * @param {string} [source] - Audio source ("microphone" or "system")
 * @returns {Promise<object>} Current hotkey state payload
 */
async function requestStartRecording(source = resolveCaptureSource()) {
  await toggleRecordingForSource(source, true, { keepFloatingResultVisible: false });
  return buildHotkeyStatePayload();
}

/**
 * IPC handler wrapper for stopping recording - stops recording and returns state
 * @param {object} [options={}] - Stop options
 * @returns {Promise<object>} Current hotkey state payload
 */
async function requestStopRecording(options = {}) {
  await toggleRecording(false, options);
  return buildHotkeyStatePayload();
}

/**
 * Toggles recording state for the resolved capture source
 * @param {boolean} forceState - True to start, false to stop
 * @param {object} [options={}] - Toggle options
 */
async function toggleRecording(forceState, options = {}) {
  await toggleRecordingForSource(resolveCaptureSource(), forceState, options);
}

module.exports = {
  validateAccelerator,
  checkHotkeyAvailability,
  registerHotkey,
  unregisterHotkey,
  connectHotkeyWebSocket,
  closeHotkeyWebSocket,
  applyHotkeyConfig,
  requestStartRecording,
  requestStopRecording,
  startRecording,
  stopRecording,
  toggleRecording,
  toggleRecordingForSource,
  buildHotkeyStatePayload,
  emitStateChange,
  playStopSound,
};

