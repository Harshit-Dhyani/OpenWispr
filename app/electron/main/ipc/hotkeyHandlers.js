// Hotkey IPC handlers
const { globalShortcut } = require("electron");
const state = require("../shared/state");
const { updateTrayIcon, updateTrayTooltip } = require("../windows/trayUtils");
const { createTray } = require("../windows/tray");
const {
  showFloatingWindow,
  hideFloatingWindow,
  updateFloatingAudioLevel,
} = require("../windows/floatingWindow");
const { injectText } = require("../services/textInjector");

let stopWaiter = null;
let stopInFlightPromise = null;

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

function validateAccelerator(accelerator) {
  if (!accelerator || typeof accelerator !== "string") {
    return { valid: false, error: "Accelerator must be a non-empty string" };
  }
  return { valid: true };
}

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

function buildHotkeyStatePayload() {
  return {
    enabled: state.hotkeyEnabled,
    isRecording: state.isRecording,
    accelerator: state.currentHotkeyAccelerator || state.DEFAULT_HOTKEY,
    registered: !!state.currentHotkeyAccelerator,
    defaultHotkey: state.DEFAULT_HOTKEY,
    mode: "toggle",
    audioFeedback: state.audioFeedbackEnabled,
    config: {
      ...state.hotkeyConfigState,
      enabled: state.hotkeyEnabled,
      key_combination:
        state.currentHotkeyAccelerator ||
        state.hotkeyConfigState.key_combination ||
        state.DEFAULT_HOTKEY,
    },
    is_registered: !!state.currentHotkeyAccelerator,
    error: state.hotkeyLastError,
    session: {
      session_id: state.activeHotkeySessionId,
      is_recording: state.isRecording,
      status: getRendererStatus(),
      lifecycle_state: state.hotkeyLifecycleState,
      last_activated_at: null,
      total_activations: 0,
      current_text: state.hotkeyCurrentText,
      duration_ms: 0,
    },
  };
}

function emitStateChange() {
  const payload = buildHotkeyStatePayload();
  state.broadcastToWindows("hotkey-state-change", payload);
}

function applyLifecycleState(nextState, extra = {}) {
  state.hotkeyLifecycleState = nextState;
  if (extra.sessionId !== undefined) {
    state.activeHotkeySessionId = extra.sessionId;
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

function resolveCaptureSource(config = state.hotkeyConfigState) {
  return config.capture_source === "system" ? "system" : "microphone";
}

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

function checkHotkeyAvailability(accelerator) {
  try {
    if (
      state.currentHotkeyAccelerator === accelerator &&
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

function registerHotkey(accelerator) {
  if (!state.hotkeyEnabled) {
    return { success: false, error: "Hotkey system is disabled" };
  }

  if (state.currentHotkeyAccelerator === accelerator) {
    return { success: true, accelerator, isToggleMode: true, alreadyRegistered: true };
  }

  const validation = validateAccelerator(accelerator);
  if (!validation.valid) {
    return { success: false, error: validation.error };
  }

  const availability = checkHotkeyAvailability(accelerator);
  if (availability.registered && availability.error) {
    return { success: false, error: availability.error };
  }

  if (state.currentHotkeyAccelerator) {
    globalShortcut.unregister(state.currentHotkeyAccelerator);
  }

  try {
    const registered = globalShortcut.register(accelerator, async () => {
      try {
        await toggleRecording();
      } catch (error) {
        console.error("[main] Hotkey toggle error:", error);
        applyLifecycleState("error", { error: error.message, isRecording: false });
      }
    });

    if (!registered) {
      return { success: false, error: "Failed to register hotkey" };
    }

    state.currentHotkeyAccelerator = accelerator;
    console.log(`[main] Global hotkey registered: ${accelerator}`);
    emitStateChange();
    return { success: true, accelerator, isToggleMode: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

function unregisterHotkey() {
  if (state.currentHotkeyAccelerator) {
    globalShortcut.unregister(state.currentHotkeyAccelerator);
    state.currentHotkeyAccelerator = null;
  }
  emitStateChange();
  return { success: true, wasRegistered: true };
}

async function connectHotkeyWebSocket(sessionId) {
  try {
    const WebSocket = require("ws");
    const wsUrl = `ws://127.0.0.1:8765/api/transcription/hotkey/ws`;
    if (state.hotkeyWebSocket) {
      closeHotkeyWebSocket();
    }

    state.hotkeyWebSocket = new WebSocket(wsUrl);
    state.hotkeyWebSocketSessionId = sessionId;

    state.hotkeyWebSocket.on("open", () => {
      console.log("[main] WebSocket connected");
    });

    state.hotkeyWebSocket.on("message", (data) => {
      try {
        const message = JSON.parse(data);
        const payload = message.payload || {};

        if (message.type === "hotkey_audio_level") {
          const { levels, peak, audio_level } = payload;
          updateFloatingAudioLevel(levels || [], peak || audio_level || 0);
          return;
        }

        if (message.type === "hotkey_status") {
          if (!isExpectedHotkeySession(payload.session_id)) {
            return;
          }
          state.activeHotkeySessionId = payload.session_id ?? state.activeHotkeySessionId;
          state.hotkeyCurrentText = payload.display_partial_text || payload.partial_text || "";
          state.hotkeyLastError = null;
          if (payload.state === "recording") {
            applyLifecycleState("recording", {
              sessionId: payload.session_id,
              currentText: state.hotkeyCurrentText,
            });
          } else if (payload.state === "stopping") {
            applyLifecycleState("stopping", {
              sessionId: payload.session_id,
              currentText: state.hotkeyCurrentText,
              isRecording: false,
            });
          } else if (payload.state === "idle") {
            applyLifecycleState("idle", {
              sessionId: null,
              currentText: "",
              isRecording: false,
            });
          }
          return;
        }

        if (message.type === "hotkey_partial" || message.type === "hotkey_draft_partial") {
          if (!isExpectedHotkeySession(payload.session_id)) {
            return;
          }
          const text = payload.display_partial_text || payload.partial_text || "";
          state.hotkeyCurrentText = text;
          emitStateChange();
          if (text && state.floatingWindow && !state.floatingWindow.isDestroyed()) {
            state.floatingWindow.webContents.send("transcription-update", {
              text,
              isPartial: true,
            });
          }
          return;
        }

        if (message.type === "hotkey_commit_final") {
          if (!isExpectedHotkeySession(payload.session_id)) {
            return;
          }
          const text =
            payload.segment?.display_text ||
            payload.segment?.text ||
            payload.committed_text ||
            payload.text ||
            "";
          if (text && state.floatingWindow && !state.floatingWindow.isDestroyed()) {
            state.floatingWindow.webContents.send("transcription-update", {
              text,
              isPartial: false,
            });
          }
          return;
        }

        if (message.type === "hotkey_started") {
          if (!isExpectedHotkeySession(payload.session_id)) {
            return;
          }
          applyLifecycleState("recording", {
            sessionId: payload.session_id ?? state.activeHotkeySessionId,
          });
          return;
        }

        if (message.type === "hotkey_stopping") {
          if (!isExpectedHotkeySession(payload.session_id)) {
            return;
          }
          applyLifecycleState("stopping", {
            sessionId: payload.session_id ?? state.activeHotkeySessionId,
            isRecording: false,
          });
          resolveStopWaiter("hotkey_stopping", payload.session_id ?? null);
          return;
        }

        if (message.type === "hotkey_stop_ack") {
          if (!isExpectedHotkeySession(payload.session_id)) {
            return;
          }
          applyLifecycleState("stopping", {
            sessionId: payload.session_id ?? state.activeHotkeySessionId,
            isRecording: false,
          });
          resolveStopWaiter("hotkey_stop_ack", payload.session_id ?? null);
          return;
        }

        if (message.type === "hotkey_stopped") {
          if (!isExpectedHotkeySession(payload.session_id)) {
            return;
          }
          const text = payload.final_transcription || "";
          if (text && state.floatingWindow && !state.floatingWindow.isDestroyed()) {
            state.floatingWindow.webContents.send("transcription-update", {
              text,
              isPartial: false,
            });
          }
          state.hotkeyCurrentText = "";
          applyLifecycleState("idle", { sessionId: null, currentText: "", isRecording: false });
          resolveStopWaiter("hotkey_stopped", payload.session_id ?? null);
          return;
        }

        if (message.type === "hotkey_error") {
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
      if (code === 1000 && state.hotkeyLifecycleState === "stopping") {
        applyLifecycleState("idle", { sessionId: null, currentText: "", isRecording: false });
        resolveStopWaiter(reason || "normal-close");
        if (state.pendingRestart) {
          state.pendingRestart = false;
          void toggleRecording(true);
        }
        return;
      }

      if (state.hotkeyLifecycleState === "starting" || state.hotkeyLifecycleState === "recording") {
        applyLifecycleState("error", {
          error: `Hotkey websocket closed (${code || "unknown"})`,
          isRecording: false,
        });
      }
    });
  } catch (e) {
    console.log("[main] WebSocket not available");
  }
}

function closeHotkeyWebSocket() {
  if (state.hotkeyWebSocket) {
    try {
      state.hotkeyWebSocket.close(1000, "client-close");
    } catch {}
    state.hotkeyWebSocket = null;
    state.hotkeyWebSocketSessionId = null;
  }
}

async function applyHotkeyConfig(config) {
  state.hotkeyConfigState = {
    ...state.hotkeyConfigState,
    ...config,
    key_combination:
      config.key_combination ||
      state.hotkeyConfigState.key_combination ||
      state.DEFAULT_HOTKEY,
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
  };

  state.hotkeyEnabled =
    config.enabled !== undefined ? config.enabled : state.hotkeyEnabled;

  if (!state.hotkeyEnabled) {
    unregisterHotkey();
    safeUpdateTrayTooltip();
    return { success: true, enabled: false };
  }

  const result = registerHotkey(state.hotkeyConfigState.key_combination);
  if (result.success) {
    safeUpdateTrayTooltip();
  }
  return result;
}

async function startRecording() {
  console.log("[main] Starting recording");
  applyLifecycleState("starting", { error: null, currentText: "" });

  if (state.hotkeyConfigState.show_floating_window) {
    showFloatingWindow();
  }

  const captureSource = resolveCaptureSource();
  const resolvedModelId = resolveHotkeyModelId();
  const response = await fetch(`${state.API_ORIGIN}/api/transcription/hotkey/start`, {
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
      language_mode: state.hotkeyConfigState.language || "auto",
    }),
  });

  if (!response.ok) {
    throw new Error(`Start failed: ${response.status}`);
  }

  const result = await response.json();
  state.activeHotkeySessionId = result.session_id || null;
  await connectHotkeyWebSocket(result.session_id || null);
  applyLifecycleState("starting", {
    sessionId: result.session_id || null,
    error: null,
    currentText: "",
  });
  return result;
}

async function stopRecording() {
  if (state.hotkeyLifecycleState === "idle" || state.hotkeyLifecycleState === "error") {
    return;
  }
  if (state.hotkeyLifecycleState === "stopping" && stopInFlightPromise) {
    return stopInFlightPromise;
  }

  console.log("[main] Stopping recording");
  applyLifecycleState("stopping", { isRecording: false });

  stopInFlightPromise = (async () => {
    const pendingAction =
      state.hotkeyPendingAction ||
      state.hotkeyConfigState.finish_mode_default ||
      (state.hotkeyConfigState.auto_inject ? "finish_and_paste" : "finish");
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

    const text = result.final_transcription || result.text || "";
    if (text && pendingAction !== "cancel") {
      state.lastTranscriptionText = text;
      if (
        pendingAction === "finish_and_paste" &&
        state.hotkeyConfigState.auto_inject
      ) {
        await injectText(text);
      }
    }

    hideFloatingWindow();
    state.hotkeyPendingAction = null;
    applyLifecycleState("idle", {
      sessionId: null,
      currentText: "",
      error: null,
      isRecording: false,
    });

    if (state.pendingRestart) {
      state.pendingRestart = false;
      await startRecording();
    }
  })();

  try {
    await stopInFlightPromise;
  } finally {
    state.hotkeyPendingAction = null;
    stopInFlightPromise = null;
  }
}

async function toggleRecording(forceState) {
  const now = Date.now();
  if (now - state.lastHotkeyPressTime < state.HOTKEY_DEBOUNCE_MS) {
    console.log("[main] Hotkey debounced");
    return;
  }
  state.lastHotkeyPressTime = now;

  const lifecycle = state.hotkeyLifecycleState;
  const shouldStart =
    forceState !== undefined ? forceState : lifecycle === "idle" || lifecycle === "error";

  if (shouldStart) {
    if (lifecycle === "recording" || lifecycle === "starting") {
      return;
    }
    if (lifecycle === "stopping") {
      state.pendingRestart = true;
      return;
    }

    try {
      await startRecording();
    } catch (error) {
      console.error("[main] Toggle error:", error.message);
      applyLifecycleState("error", { error: error.message, isRecording: false });
      hideFloatingWindow();
    }
    return;
  }

  if (lifecycle === "idle" || lifecycle === "error") {
    return;
  }
  if (lifecycle === "stopping") {
    return;
  }

  try {
    await stopRecording();
  } catch (error) {
    console.error("[main] Stop failed:", error.message);
    applyLifecycleState("error", { error: error.message, isRecording: false });
    hideFloatingWindow();
  }
}

module.exports = {
  validateAccelerator,
  checkHotkeyAvailability,
  registerHotkey,
  unregisterHotkey,
  connectHotkeyWebSocket,
  closeHotkeyWebSocket,
  applyHotkeyConfig,
  toggleRecording,
  buildHotkeyStatePayload,
  emitStateChange,
  playStopSound,
};
