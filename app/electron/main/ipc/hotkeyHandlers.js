// Hotkey IPC handlers
const { globalShortcut } = require("electron");
const state = require("../shared/state");
const { updateTrayIcon, updateTrayTooltip, createTray } = require("../windows/tray");
const { showFloatingWindow, hideFloatingWindow, updateFloatingAudioLevel } = require("../windows/floatingWindow");
const { injectText } = require("../services/textInjector");
const { loadUserSettings, saveUserSettings } = require("../utils/api");

function validateAccelerator(accelerator) {
  if (!accelerator || typeof accelerator !== "string") {
    return { valid: false, error: "Accelerator must be a non-empty string" };
  }

  const validModifiers = [
    "Command", "Cmd",
    "Control", "Ctrl",
    "CommandOrControl", "CmdOrCtrl",
    "Alt", "Option",
    "Shift",
    "Super", "Meta"
  ];

  const validSpecialKeys = [
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "F13", "F14", "F15", "F16", "F17", "F18", "F19", "F20", "F21", "F22", "F23", "F24",
    "Plus", "Space", "Tab", "Backspace", "Delete", "Insert", "Return", "Enter",
    "Up", "Down", "Left", "Right", "Home", "End", "PageUp", "PageDown",
    "Escape", "Esc", "VolumeUp", "VolumeDown", "VolumeMute", "MediaNextTrack",
    "MediaPreviousTrack", "MediaStop", "MediaPlayPause", "PrintScreen"
  ];

  const parts = accelerator.split("+").map(p => p.trim());

  if (parts.length === 0) {
    return { valid: false, error: "Accelerator cannot be empty" };
  }

  const keyPart = parts[parts.length - 1];
  const modifiers = parts.slice(0, -1);

  const isValidSpecialKey = validSpecialKeys.includes(keyPart);
  const isValidKeyCode = /^[a-zA-Z0-9]$/.test(keyPart);

  if (!isValidSpecialKey && !isValidKeyCode) {
    return { valid: false, error: `Invalid key: "${keyPart}". Must be a letter, number, or valid special key` };
  }

  for (const mod of modifiers) {
    if (!validModifiers.includes(mod)) {
      return { valid: false, error: `Invalid modifier: "${mod}"` };
    }
  }

  return { valid: true };
}

function checkHotkeyAvailability(accelerator) {
  try {
    if (state.currentHotkeyAccelerator === accelerator && globalShortcut.isRegistered(accelerator)) {
      return { registered: false, ownedByApp: true };
    }

    const testRegistered = globalShortcut.register(accelerator, () => {});

    if (testRegistered) {
      globalShortcut.unregister(accelerator);
      return { registered: false };
    } else {
      return { registered: true, error: `Hotkey "${accelerator}" may already be registered by another application` };
    }
  } catch (error) {
    return { registered: false, error: error.message };
  }
}

function registerHotkey(accelerator) {
  if (!state.hotkeyEnabled) {
    return { success: false, error: "Hotkey system is disabled" };
  }

  if (state.currentHotkeyAccelerator === accelerator && globalShortcut.isRegistered(accelerator)) {
    return {
      success: true,
      accelerator,
      isToggleMode: true,
      alreadyRegistered: true,
    };
  }

  const validation = validateAccelerator(accelerator);
  if (!validation.valid) {
    return { success: false, error: `Invalid accelerator format: ${validation.error}` };
  }

  const availability = checkHotkeyAvailability(accelerator);
  if (availability.registered && availability.error) {
    return { success: false, error: availability.error };
  }

  if (state.currentHotkeyAccelerator && state.currentHotkeyAccelerator !== accelerator) {
    globalShortcut.unregister(state.currentHotkeyAccelerator);
    console.log(`[main] Unregistered previous hotkey: ${state.currentHotkeyAccelerator}`);
  }

  let registered = false;
  let registrationError = null;

  try {
    registered = globalShortcut.register(accelerator, () => {
      void toggleRecording();
    });

    if (!registered) {
      registrationError = "globalShortcut.register() returned false";
    }
  } catch (error) {
    registered = false;
    registrationError = error.message;
  }

  if (registered) {
    state.currentHotkeyAccelerator = accelerator;
    console.log(`[main] Global hotkey registered: ${accelerator}`);
    return {
      success: true,
      accelerator: accelerator,
      isToggleMode: true
    };
  } else {
    console.error(`[main] Failed to register global hotkey: ${accelerator}`);
    return {
      success: false,
      error: `Failed to register hotkey: ${registrationError || "unknown error"}`,
      details: {
        accelerator: accelerator,
        platform: process.platform,
        possibleCauses: [
          "Hotkey already registered by another application",
          "System restriction on global hotkeys",
          "Invalid accelerator format for this platform"
        ]
      }
    };
  }
}

function unregisterHotkey() {
  if (!state.currentHotkeyAccelerator) {
    return { success: true, wasRegistered: false };
  }

  try {
    globalShortcut.unregister(state.currentHotkeyAccelerator);
    console.log(`[main] Global hotkey unregistered: ${state.currentHotkeyAccelerator}`);
    const wasRegistered = state.currentHotkeyAccelerator;
    state.currentHotkeyAccelerator = null;
    return { success: true, wasRegistered: true, accelerator: wasRegistered };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// WebSocket for audio levels
async function connectHotkeyWebSocket() {
  if (!state.isRecording || !state.allowHotkeyReconnect) {
    return;
  }

  if (state.hotkeyWebSocket) {
    try {
      state.hotkeyWebSocket.close();
    } catch {}
  }

  if (state.webSocketReconnectTimeout) {
    clearTimeout(state.webSocketReconnectTimeout);
    state.webSocketReconnectTimeout = null;
  }

  let WebSocket;
  try {
    const wsModulePath = require.resolve("ws");
    WebSocket = require(wsModulePath);
  } catch (error) {
    if (!state.wsModuleMissingLogged) {
      console.log("[main] WebSocket module 'ws' not available. Audio visualizer will use simulation.");
      state.wsModuleMissingLogged = true;
    }
    return;
  }

  try {
    state.wsConnectionAttempt++;
    const wsUrl = `ws://127.0.0.1:8765/api/transcription/hotkey/ws`;
    state.hotkeyWebSocket = new WebSocket(wsUrl);

    state.hotkeyWebSocket.on("open", () => {
      console.log("[main] Hotkey WebSocket connected");
      state.wsConnectionAttempt = 0;
      state.wsLastErrorTime = 0;
    });

    state.hotkeyWebSocket.on("message", (data) => {
      try {
        let message;
        try {
          message = JSON.parse(data);
        } catch (parseError) {
          const now = Date.now();
          if (now - state.wsLastErrorTime > state.WS_ERROR_DEBOUNCE_MS) {
            console.error("[main] WebSocket JSON parse error:", parseError.message);
            state.wsLastErrorTime = now;
          }
          return;
        }

        if (message.type === "hotkey_audio_level" && message.payload) {
          const { audio_level, levels, peak } = message.payload;
          updateFloatingAudioLevel(levels || [], peak || audio_level || 0);
        } else if (message.type === "hotkey_partial" && message.payload) {
          const audioLevel = message.payload.audio_level || 0;
          updateFloatingAudioLevel([], audioLevel);
        }

        if (message.type === "hotkey_partial" && message.payload) {
          const partialText =
            message.payload.display_partial_text ||
            message.payload.partial_text ||
            "";
          if (!partialText) {
            return;
          }
          if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
            state.floatingWindow.webContents.send("transcription-update", {
              text: partialText,
              isPartial: true
            });
          }
        }

        if (message.type === "hotkey_stopped" && message.payload) {
          const finalText =
            message.payload.final_transcription ||
            message.payload.final_text ||
            "";
          if (finalText && state.floatingWindow && !state.floatingWindow.isDestroyed()) {
            state.floatingWindow.webContents.send("transcription-update", {
              text: finalText,
              isPartial: false
            });
          }
        }
      } catch (error) {
        const now = Date.now();
        if (now - state.wsLastErrorTime > state.WS_ERROR_DEBOUNCE_MS) {
          console.error("[main] WebSocket message error:", error.message);
          state.wsLastErrorTime = now;
        }
      }
    });

    state.hotkeyWebSocket.on("close", (code, reason) => {
      if (state.wsConnectionAttempt <= 1) {
        console.log(`[main] Hotkey WebSocket closed (code: ${code})`);
      }
      state.hotkeyWebSocket = null;

      const backoffDelay = Math.min(3000 * Math.pow(1.5, Math.min(state.wsConnectionAttempt - 1, 5)), 30000);
      if (state.isRecording && state.allowHotkeyReconnect) {
        state.webSocketReconnectTimeout = setTimeout(connectHotkeyWebSocket, backoffDelay);
      }
    });

    state.hotkeyWebSocket.on("error", (error) => {
      const now = Date.now();
      if (now - state.wsLastErrorTime > state.WS_ERROR_DEBOUNCE_MS) {
        console.error("[main] Hotkey WebSocket error:", error.message);
        state.wsLastErrorTime = now;
      }
    });
  } catch (error) {
    const now = Date.now();
    if (now - state.wsLastErrorTime > state.WS_ERROR_DEBOUNCE_MS) {
      console.error("[main] Failed to create WebSocket:", error.message);
      state.wsLastErrorTime = now;
    }

    const backoffDelay = Math.min(5000 * Math.pow(1.5, Math.min(state.wsConnectionAttempt - 1, 5)), 30000);
    if (state.isRecording && state.allowHotkeyReconnect) {
      state.webSocketReconnectTimeout = setTimeout(connectHotkeyWebSocket, backoffDelay);
    }
  }
}

function closeHotkeyWebSocket() {
  state.allowHotkeyReconnect = false;
  if (state.webSocketReconnectTimeout) {
    clearTimeout(state.webSocketReconnectTimeout);
    state.webSocketReconnectTimeout = null;
  }
  if (state.hotkeyWebSocket) {
    try {
      state.hotkeyWebSocket.close();
    } catch {}
    state.hotkeyWebSocket = null;
  }
}

// Audio feedback
function playStartSound() {
  if (!state.audioFeedbackEnabled) return;

  if (process.platform === "win32") {
    try {
      if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
        state.floatingWindow.webContents.send("hotkey-event", { type: "start" });
      }
    } catch (error) {
      console.log("[main] Could not play start sound:", error.message);
    }
  } else if (process.platform === "darwin") {
    try {
      const { exec } = require("child_process");
      exec("afplay /System/Library/Sounds/Glass.aiff", { timeout: 1000 }, () => {});
    } catch {}
  }
}

function playStopSound() {
  if (!state.audioFeedbackEnabled) return;

  if (process.platform === "win32") {
    try {
      if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
        state.floatingWindow.webContents.send("hotkey-event", { type: "stop" });
      }
    } catch (error) {
      console.log("[main] Could not play stop sound:", error.message);
    }
  } else if (process.platform === "darwin") {
    try {
      const { exec } = require("child_process");
      exec("afplay /System/Library/Sounds/Pop.aiff", { timeout: 1000 }, () => {});
    } catch {}
  }
}

async function applyHotkeyConfig(config) {
  state.hotkeyConfigState = {
    ...state.hotkeyConfigState,
    ...config,
    key_combination:
      config.key_combination || config.accelerator || state.hotkeyConfigState.key_combination || state.DEFAULT_HOTKEY,
  };

  if (config.audioFeedback !== undefined) {
    state.audioFeedbackEnabled = config.audioFeedback;
  }

  const requestedEnabled =
    typeof config.enabled === "boolean" ? config.enabled : state.hotkeyEnabled;
  const requestedAccelerator =
    state.hotkeyConfigState.key_combination || state.currentHotkeyAccelerator || state.DEFAULT_HOTKEY;

  state.hotkeyEnabled = requestedEnabled;

  if (!state.hotkeyEnabled) {
    unregisterHotkey();
    updateTrayTooltip();
    return { success: true, enabled: false, accelerator: requestedAccelerator, config: state.hotkeyConfigState };
  }

  const result = registerHotkey(requestedAccelerator);
  if (result.success) {
    console.log("[main] Hotkey updated to:", requestedAccelerator);
    updateTrayTooltip();
    return { success: true, enabled: true, accelerator: requestedAccelerator, config: state.hotkeyConfigState };
  }

  console.error("[main] Failed to update hotkey:", result.error);
  return result;
}

async function toggleRecording(forceState) {
  if (state.hotkeyTransitionInFlight) {
    console.log("[main] Hotkey transition already in progress");
    return;
  }

  const now = Date.now();
  if (now - state.lastHotkeyPressTime < state.HOTKEY_DEBOUNCE_MS) {
    console.log("[main] Hotkey debounced - ignoring rapid press");
    return;
  }
  state.lastHotkeyPressTime = now;

  const newState = forceState !== undefined ? forceState : !state.isRecording;

  if (newState === state.isRecording) return;
  state.hotkeyTransitionInFlight = true;

  try {
    if (newState) {
      console.log("[main] Hotkey pressed - starting recording");
      if (state.hotkeyConfigState.show_floating_window) {
        showFloatingWindow();
      }

      try {
        const response = await fetch(`${state.API_ORIGIN}/api/transcription/hotkey/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            device_id:
              state.hotkeyConfigState.device_id && state.hotkeyConfigState.device_id !== "default"
                ? state.hotkeyConfigState.device_id
                : null,
            model_name: "small",
            language_mode: state.hotkeyConfigState.language || "auto",
            execution_mode: "auto",
          })
        });
        if (!response.ok) {
          throw new Error(`Hotkey start failed with status ${response.status}`);
        }
      } catch (error) {
        console.error("[main] Failed to start hotkey transcription:", error);
        state.isRecording = false;
        closeHotkeyWebSocket();
        hideFloatingWindow();
        updateTrayIcon();
        updateTrayTooltip();
        return;
      }

      state.isRecording = true;
      state.allowHotkeyReconnect = true;
      playStartSound();
      updateTrayIcon();
      updateTrayTooltip();
      await createTray();
      connectHotkeyWebSocket();

      if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
        state.floatingWindow.webContents.send("recording-state", { isRecording: true });
      }
    } else {
      console.log("[main] Hotkey pressed - stopping recording");
      state.isRecording = false;
      closeHotkeyWebSocket();
      playStopSound();
      updateTrayIcon();

      let transcribedText = "";
      try {
        const response = await fetch(`${state.API_ORIGIN}/api/transcription/hotkey/stop`, {
          method: "POST",
          headers: { "Content-Type": "application/json" }
        });
        const result = await response.json();
        console.log("[main] Hotkey stop result:", JSON.stringify(result));
        transcribedText = result.final_transcription || result.final_text || result.text || "";
        state.lastTranscriptionText = transcribedText || state.lastTranscriptionText;
      } catch (error) {
        console.error("[main] Failed to stop hotkey transcription:", error);
      }

      if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
        state.floatingWindow.webContents.send("recording-state", { isRecording: false, processing: true });
      }

      const shouldPaste =
        state.hotkeyConfigState.auto_inject &&
        state.hotkeyConfigState.finish_mode_default === "finish_and_paste";

      if (transcribedText && shouldPaste) {
        hideFloatingWindow();
        setTimeout(async () => {
          const injectResult = await injectText(transcribedText);
          if (!injectResult.success) {
            console.error("[main] Text injection failed:", injectResult.error);
            const { clipboard } = require("electron");
            clipboard.writeText(transcribedText);
          }
        }, 150);
      } else {
        if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
          state.floatingWindow.webContents.send("recording-state", { isRecording: false, finished: true });
        }
        if (transcribedText && state.mainWindow && !state.mainWindow.isDestroyed()) {
          state.mainWindow.webContents.send("transcription-result", { text: transcribedText, isPartial: false });
        }
        setTimeout(hideFloatingWindow, 500);
      }
      updateTrayTooltip();
      await createTray();
    }
  } finally {
    state.hotkeyTransitionInFlight = false;
    if (state.mainWindow && !state.mainWindow.isDestroyed()) {
      state.mainWindow.webContents.send("hotkey-state-change", {
        isRecording: state.isRecording,
        hotkeyEnabled: state.hotkeyEnabled,
        accelerator: state.currentHotkeyAccelerator
      });
    }
  }
}

module.exports = {
  validateAccelerator,
  checkHotkeyAvailability,
  registerHotkey,
  unregisterHotkey,
  connectHotkeyWebSocket,
  closeHotkeyWebSocket,
  playStartSound,
  playStopSound,
  applyHotkeyConfig,
  toggleRecording,
};
