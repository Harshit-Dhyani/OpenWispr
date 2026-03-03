const { app, BrowserWindow, dialog, ipcMain, Tray, Menu, globalShortcut, screen, nativeImage, shell } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");
const { ModelDownloadManager } = require("./model-download-manager");
const { ModelDownloadService } = require("./services/modelDownloadService");
const { APP_NAME } = require("./shared/generated/appMeta");

// Window references
let mainWindow = null;
let floatingWindow = null;
let quickSettingsWindow = null;
let tray = null;
let modelDownloadManager = null;
let modelDownloadService = null;

// Backend process
let backendProcess = null;
const API_ORIGIN = "http://127.0.0.1:8765";

// Hotkey state
let hotkeyEnabled = false;
let isRecording = false;
let currentHotkeyAccelerator = null;
let lastHotkeyPressTime = 0;
const HOTKEY_DEBOUNCE_MS = 150; // Prevent double-fires within 150ms

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
let hotkeyTransitionInFlight = false;

// Tray icons cache
let trayIconIdle = null;
let trayIconRecording = null;

function broadcastToWindows(channel, payload) {
  const windows = [mainWindow, floatingWindow, quickSettingsWindow].filter(
    (win) => win && !win.isDestroyed()
  );
  for (const win of windows) {
    win.webContents.send(channel, payload);
  }
}

// Default hotkey - Windows-friendly, avoids Alt+Space (system menu)
const DEFAULT_HOTKEY = "CommandOrControl+Shift+T";
let hotkeyConfigState = {
  enabled: false,
  key_combination: DEFAULT_HOTKEY,
  hold_mode: false,
  auto_inject: true,
  language: "auto",
  device_id: "default",
  finish_mode_default: "finish_and_paste",
  show_floating_window: true,
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

function resolvePythonLaunch() {
  const repoRoot = path.resolve(__dirname, "..", "..", "..", "..");
  const venvPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
  const apiMainPath = path.join(repoRoot, "app", "api_main.py");

  // Verify api_main.py exists for debugging
  if (!fs.existsSync(apiMainPath)) {
    console.error("[main] Cannot find api_main.py at:", apiMainPath);
    console.error("[main] repoRoot calculated as:", repoRoot);
  }

  // Prefer venv Python if it exists
  if (process.env.TRANSCRIPTA_PYTHON) {
    console.log(`[main] Using TRANSCRIPTA_PYTHON: ${process.env.TRANSCRIPTA_PYTHON}`);
    return { command: process.env.TRANSCRIPTA_PYTHON, args: [apiMainPath] };
  }
  if (fs.existsSync(venvPython)) {
    console.log(`[main] Using venv Python: ${venvPython}`);
    return { command: venvPython, args: [apiMainPath] };
  }
  console.log(`[main] Falling back to system Python (py -3)`);
  return { command: "py", args: ["-3", apiMainPath] };
}

async function backendAlreadyRunning() {
  try {
    const response = await fetch(`${API_ORIGIN}/api/health`);
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForBackendReady(timeoutMs = 20000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (await backendAlreadyRunning()) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return false;
}

async function startBackend() {
  if (backendProcess) {
    return;
  }
  if (await backendAlreadyRunning()) {
    return;
  }
  const repoRoot = path.resolve(__dirname, "..", "..", "..", "..");
  const { command, args } = resolvePythonLaunch();
  const modelsRoot = path.join(app.getPath("userData"), "models");

  // Build PYTHONPATH explicitly for Windows (; separator) or Unix (: separator)
  const pathSeparator = process.platform === "win32" ? ";" : ":";
  const pythonPath = repoRoot + (process.env.PYTHONPATH ? pathSeparator + process.env.PYTHONPATH : "");

  console.log(`[main] Starting Python backend:`);
  console.log(`[main]   Command: ${command}`);
  console.log(`[main]   Args: ${JSON.stringify(args)}`);
  console.log(`[main]   CWD: ${repoRoot}`);
  console.log(`[main]   PYTHONPATH: ${pythonPath}`);

  backendProcess = spawn(command, args, {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHONPATH: pythonPath,
      TRANSCRIPTA_DOWNLOAD_ROOT: modelsRoot,
    },
    stdio: "pipe",
    windowsHide: true
  });

  backendProcess.stdout.on("data", (chunk) => {
    process.stdout.write(`[backend] ${chunk}`);
  });

  backendProcess.stderr.on("data", (chunk) => {
    process.stderr.write(`[backend] ${chunk}`);
  });

  backendProcess.on("exit", () => {
    backendProcess = null;
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("backend-exit");
    }
  });
}

async function fetchBackendJson(apiPath, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const isRetryableGet = method === "GET";
  const timeoutMs = options.timeout || 30000; // Default 30 second timeout
  let response;
  let lastError = null;

  for (let attempt = 0; attempt < (isRetryableGet ? 5 : 1); attempt += 1) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      response = await fetch(`${API_ORIGIN}${apiPath}`, {
        headers: {
          "Content-Type": "application/json",
          ...(options.headers || {}),
        },
        ...options,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      break;
    } catch (error) {
      clearTimeout(timeoutId);
      lastError = error;

      // Handle abort/timeout errors specifically
      if (error.name === 'AbortError') {
        lastError = new Error(`Request timeout after ${timeoutMs}ms`);
      }

      if (!isRetryableGet || attempt === 4) {
        throw lastError;
      }
      await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)));
    }
  }

  if (!response) {
    throw lastError || new Error("Failed to fetch");
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      typeof payload === "string"
        ? payload
        : payload?.detail || payload?.error?.message || `HTTP ${response.status}`;
    throw new Error(message);
  }

  return payload;
}

async function loadUserSettings() {
  return fetchBackendJson("/api/settings");
}

async function saveUserSettings(settings) {
  return fetchBackendJson("/api/settings", {
    method: "POST",
    body: JSON.stringify(settings),
  });
}

async function loadDevicesForDesktop() {
  const result = await fetchBackendJson("/api/devices");
  return Array.isArray(result?.devices) ? result.devices : [];
}

function getRecentTranscriptEntries(limit = 8) {
  const sessionsRoot = path.resolve(__dirname, "..", "..", "sessions");
  if (!fs.existsSync(sessionsRoot)) {
    return [];
  }

  const entries = [];
  for (const dirent of fs.readdirSync(sessionsRoot, { withFileTypes: true })) {
    if (!dirent.isDirectory()) {
      continue;
    }

    const sessionDir = path.join(sessionsRoot, dirent.name);
    const sessionJsonPath = path.join(sessionDir, "session.json");
    const transcriptPath = path.join(sessionDir, "transcript.txt");

    let sessionMeta = {};
    if (fs.existsSync(sessionJsonPath)) {
      try {
        sessionMeta = JSON.parse(fs.readFileSync(sessionJsonPath, "utf8"));
      } catch {}
    }

    let preview = "";
    if (fs.existsSync(transcriptPath)) {
      try {
        preview = fs.readFileSync(transcriptPath, "utf8").trim().replace(/\s+/g, " ").slice(0, 120);
      } catch {}
    }

    let modifiedAt = 0;
    try {
      modifiedAt = fs.statSync(sessionDir).mtimeMs;
    } catch {}

    entries.push({
      id: dirent.name,
      title: sessionMeta.title || dirent.name,
      preview,
      sessionDir,
      transcriptPath,
      modifiedAt,
    });
  }

  return entries.sort((a, b) => b.modifiedAt - a.modifiedAt).slice(0, limit);
}

function showPlaceholderDialog(title, message) {
  dialog.showMessageBox({
    type: "info",
    title,
    message,
    buttons: ["OK"],
  }).catch(() => {});
}

// Initialize text injection capabilities
async function initTextInjector() {
  // Try to load native modules for text injection
  try {
    const robotjs = require("robotjs");
    hasRobotjs = true;
    textInjector = {
      typeString: (text) => {
        try {
          robotjs.typeString(text);
          return { success: true };
        } catch (error) {
          return { success: false, error: error.message };
        }
      }
    };
    console.log("[main] Text injection: using robotjs");
    return;
  } catch {
    hasRobotjs = false;
  }

  try {
    const nodeKeySender = require("node-key-sender");
    hasNodeKeySender = true;
    textInjector = {
      typeString: (text) => {
        try {
          nodeKeySender.sendText(text);
          return { success: true };
        } catch (error) {
          return { success: false, error: error.message };
        }
      }
    };
    console.log("[main] Text injection: using node-key-sender");
    return;
  } catch {
    hasNodeKeySender = false;
  }

  // Fallback: clipboard-based injection
  console.log("[main] Text injection: using clipboard fallback");
  textInjector = {
    typeString: async (text) => {
      try {
        const { clipboard } = require("electron");
        clipboard.writeText(text);

        return {
          success: false,
          error: "Native text injection is unavailable. Transcription was copied to the clipboard.",
          method: "clipboard_only"
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    }
  };
}

// Audio feedback using system beep or electron-sounds
function playStartSound() {
  if (!audioFeedbackEnabled) return;

  // Use system beep as fallback
  if (process.platform === "win32") {
    // Windows beep
    try {
      // Play through floating window if available
      if (floatingWindow && !floatingWindow.isDestroyed()) {
        floatingWindow.webContents.send("hotkey-event", { type: "start" });
      }
    } catch (error) {
      console.log("[main] Could not play start sound:", error.message);
    }
  } else if (process.platform === "darwin") {
    // macOS system sound
    try {
      const { exec } = require("child_process");
      exec("afplay /System/Library/Sounds/Glass.aiff", { timeout: 1000 }, () => {});
    } catch {}
  }
}

function playStopSound() {
  if (!audioFeedbackEnabled) return;

  if (process.platform === "win32") {
    try {
      if (floatingWindow && !floatingWindow.isDestroyed()) {
        floatingWindow.webContents.send("hotkey-event", { type: "stop" });
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

// Create tray icons
function createTrayIcons() {
  const size = 16;

  // Idle icon (green dot)
  trayIconIdle = createCircleIcon(size, "#10b981");

  // Recording icon (red dot with pulse effect)
  trayIconRecording = createCircleIcon(size, "#ef4444");
}

function createCircleIcon(size, color) {
  // Create a simple colored circle PNG
  const canvas = Buffer.alloc(size * size * 4);

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const idx = (y * size + x) * 4;
      const dx = x - size / 2 + 0.5;
      const dy = y - size / 2 + 0.5;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist <= size / 2 - 1) {
        // Parse hex color
        const r = parseInt(color.slice(1, 3), 16);
        const g = parseInt(color.slice(3, 5), 16);
        const b = parseInt(color.slice(5, 7), 16);

        canvas[idx] = r;
        canvas[idx + 1] = g;
        canvas[idx + 2] = b;
        canvas[idx + 3] = 255;
      } else {
        canvas[idx] = 0;
        canvas[idx + 1] = 0;
        canvas[idx + 2] = 0;
        canvas[idx + 3] = 0;
      }
    }
  }

  return nativeImage.createFromBitmap(canvas, { width: size, height: size });
}

/**
 * Validates an Electron accelerator string
 * @param {string} accelerator - The accelerator string to validate
 * @returns {object} - { valid: boolean, error?: string }
 */
function validateAccelerator(accelerator) {
  if (!accelerator || typeof accelerator !== "string") {
    return { valid: false, error: "Accelerator must be a non-empty string" };
  }

  // Valid modifier keys
  const validModifiers = [
    "Command", "Cmd",
    "Control", "Ctrl",
    "CommandOrControl", "CmdOrCtrl",
    "Alt", "Option",
    "Shift",
    "Super", "Meta"
  ];

  // Valid special keys
  const validSpecialKeys = [
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "F13", "F14", "F15", "F16", "F17", "F18", "F19", "F20", "F21", "F22", "F23", "F24",
    "Plus", "Space", "Tab", "Backspace", "Delete", "Insert", "Return", "Enter",
    "Up", "Down", "Left", "Right", "Home", "End", "PageUp", "PageDown",
    "Escape", "Esc", "VolumeUp", "VolumeDown", "VolumeMute", "MediaNextTrack",
    "MediaPreviousTrack", "MediaStop", "MediaPlayPause", "PrintScreen"
  ];

  // Parse the accelerator
  const parts = accelerator.split("+").map(p => p.trim());

  if (parts.length === 0) {
    return { valid: false, error: "Accelerator cannot be empty" };
  }

  // Last part should be a key (either special key or single character)
  const keyPart = parts[parts.length - 1];
  const modifiers = parts.slice(0, -1);

  // Check if key part is valid
  const isValidSpecialKey = validSpecialKeys.includes(keyPart);
  const isValidKeyCode = /^[a-zA-Z0-9]$/.test(keyPart);

  if (!isValidSpecialKey && !isValidKeyCode) {
    return { valid: false, error: `Invalid key: "${keyPart}". Must be a letter, number, or valid special key` };
  }

  // Validate modifiers
  for (const mod of modifiers) {
    if (!validModifiers.includes(mod)) {
      return { valid: false, error: `Invalid modifier: "${mod}"` };
    }
  }

  return { valid: true };
}

/**
 * Checks if a hotkey is already registered by another application
 * @param {string} accelerator - The accelerator to check
 * @returns {object} - { registered: boolean, error?: string }
 */
function checkHotkeyAvailability(accelerator) {
  try {
    if (currentHotkeyAccelerator === accelerator && globalShortcut.isRegistered(accelerator)) {
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

/**
 * Registers a global hotkey with the given accelerator
 * @param {string} accelerator - The accelerator string (e.g., "CommandOrControl+Shift+T")
 * @returns {object} - { success: boolean, accelerator?: string, error?: string, details?: object }
 */
function registerHotkey(accelerator) {
  if (!hotkeyEnabled) {
    return { success: false, error: "Hotkey system is disabled" };
  }

  if (currentHotkeyAccelerator === accelerator && globalShortcut.isRegistered(accelerator)) {
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

  if (currentHotkeyAccelerator && currentHotkeyAccelerator !== accelerator) {
    globalShortcut.unregister(currentHotkeyAccelerator);
    console.log(`[main] Unregistered previous hotkey: ${currentHotkeyAccelerator}`);
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
    currentHotkeyAccelerator = accelerator;
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

/**
 * Unregisters the current global hotkey
 * @returns {object} - { success: boolean, wasRegistered?: boolean, error?: string }
 */
function unregisterHotkey() {
  if (!currentHotkeyAccelerator) {
    return { success: true, wasRegistered: false };
  }

  try {
    globalShortcut.unregister(currentHotkeyAccelerator);
    console.log(`[main] Global hotkey unregistered: ${currentHotkeyAccelerator}`);
    const wasRegistered = currentHotkeyAccelerator;
    currentHotkeyAccelerator = null;
    return { success: true, wasRegistered: true, accelerator: wasRegistered };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Connect to hotkey WebSocket for audio levels
let wsModuleMissingLogged = false;
let wsConnectionAttempt = 0;
let wsLastErrorTime = 0;
const WS_ERROR_DEBOUNCE_MS = 5000; // Only log errors every 5 seconds

async function connectHotkeyWebSocket() {
  if (!isRecording || !allowHotkeyReconnect) {
    return;
  }

  if (hotkeyWebSocket) {
    try {
      hotkeyWebSocket.close();
    } catch {}
  }

  // Clear any existing reconnect timeout
  if (webSocketReconnectTimeout) {
    clearTimeout(webSocketReconnectTimeout);
    webSocketReconnectTimeout = null;
  }

  let WebSocket;
  try {
    // Use require.resolve to ensure proper module resolution in Electron
    const wsModulePath = require.resolve("ws");
    WebSocket = require(wsModulePath);
  } catch (error) {
    // Only log ws module missing once to avoid spam
    if (!wsModuleMissingLogged) {
      console.log("[main] WebSocket module 'ws' not available. Audio visualizer will use simulation.");
      wsModuleMissingLogged = true;
    }
    return; // Don't retry - module is not available
  }

  try {
    wsConnectionAttempt++;
    const wsUrl = `ws://127.0.0.1:8765/api/transcription/hotkey/ws`;
    hotkeyWebSocket = new WebSocket(wsUrl);

    hotkeyWebSocket.on("open", () => {
      console.log("[main] Hotkey WebSocket connected");
      wsConnectionAttempt = 0; // Reset attempt counter on success
      wsLastErrorTime = 0;
    });

    hotkeyWebSocket.on("message", (data) => {
      try {
        let message;
        // FIX: Wrap JSON.parse in try-catch to handle malformed messages
        try {
          message = JSON.parse(data);
        } catch (parseError) {
          const now = Date.now();
          if (now - wsLastErrorTime > WS_ERROR_DEBOUNCE_MS) {
            console.error("[main] WebSocket JSON parse error:", parseError.message);
            wsLastErrorTime = now;
          }
          return;
        }

        // Forward audio level updates to floating window
        // Backend format: {type: "hotkey_audio_level", payload: {audio_level, levels, peak}}
        if (message.type === "hotkey_audio_level" && message.payload) {
          const { audio_level, levels, peak } = message.payload;
          updateFloatingAudioLevel(levels || [], peak || audio_level || 0);
        }
        // Legacy fallback for partial transcription with audio level
        else if (message.type === "hotkey_partial" && message.payload) {
          const audioLevel = message.payload.audio_level || 0;
          updateFloatingAudioLevel([], audioLevel);
        }

        // Handle partial transcription text
        if (message.type === "hotkey_partial" && message.payload) {
          const partialText =
            message.payload.display_partial_text ||
            message.payload.partial_text ||
            "";
          if (!partialText) {
            return;
          }
          if (floatingWindow && !floatingWindow.isDestroyed()) {
            floatingWindow.webContents.send("transcription-update", {
              text: partialText,
              isPartial: true
            });
          }
        }

        // Handle final transcription
        if (message.type === "hotkey_stopped" && message.payload) {
          const finalText =
            message.payload.final_transcription ||
            message.payload.final_text ||
            "";
          if (finalText && floatingWindow && !floatingWindow.isDestroyed()) {
            floatingWindow.webContents.send("transcription-update", {
              text: finalText,
              isPartial: false
            });
          }
        }
      } catch (error) {
        const now = Date.now();
        if (now - wsLastErrorTime > WS_ERROR_DEBOUNCE_MS) {
          console.error("[main] WebSocket message error:", error.message);
          wsLastErrorTime = now;
        }
      }
    });

    hotkeyWebSocket.on("close", (code, reason) => {
      // Only log if we were previously connected
      if (wsConnectionAttempt <= 1) {
        console.log(`[main] Hotkey WebSocket closed (code: ${code})`);
      }
      hotkeyWebSocket = null;

      // Exponential backoff for reconnection
      const backoffDelay = Math.min(3000 * Math.pow(1.5, Math.min(wsConnectionAttempt - 1, 5)), 30000);
      if (isRecording && allowHotkeyReconnect) {
        webSocketReconnectTimeout = setTimeout(connectHotkeyWebSocket, backoffDelay);
      }
    });

    hotkeyWebSocket.on("error", (error) => {
      const now = Date.now();
      if (now - wsLastErrorTime > WS_ERROR_DEBOUNCE_MS) {
        console.error("[main] Hotkey WebSocket error:", error.message);
        wsLastErrorTime = now;
      }
      // Close will be triggered after error, which triggers reconnect
    });
  } catch (error) {
    const now = Date.now();
    if (now - wsLastErrorTime > WS_ERROR_DEBOUNCE_MS) {
      console.error("[main] Failed to create WebSocket:", error.message);
      wsLastErrorTime = now;
    }

    // Exponential backoff for reconnection
    const backoffDelay = Math.min(5000 * Math.pow(1.5, Math.min(wsConnectionAttempt - 1, 5)), 30000);
    if (isRecording && allowHotkeyReconnect) {
      webSocketReconnectTimeout = setTimeout(connectHotkeyWebSocket, backoffDelay);
    }
  }
}

function closeHotkeyWebSocket() {
  allowHotkeyReconnect = false;
  if (webSocketReconnectTimeout) {
    clearTimeout(webSocketReconnectTimeout);
    webSocketReconnectTimeout = null;
  }
  if (hotkeyWebSocket) {
    try {
      hotkeyWebSocket.close();
    } catch {}
    hotkeyWebSocket = null;
  }
}

// Update floating window with audio level data
// Accepts either full levels array from backend, or generates from single level
function updateFloatingAudioLevel(levelsOrLevel, peakLevel) {
  if (!floatingWindow || floatingWindow.isDestroyed()) return;

  const barCount = 36;
  let levels;
  let peak;

  // Check if we received a full levels array or a single level value
  if (Array.isArray(levelsOrLevel) && levelsOrLevel.length > 0) {
    // Backend provided full frequency distribution
    levels = levelsOrLevel;
    peak = peakLevel !== undefined ? peakLevel : Math.max(...levels);
  } else {
    // Single level value - generate realistic waveform
    const level = typeof levelsOrLevel === 'number' ? levelsOrLevel : 0;
    peak = level;
    levels = [];

    // Create a realistic-looking waveform based on the single level
    const time = Date.now() / 200;
    for (let i = 0; i < barCount; i++) {
      // Frequency response curve (higher in middle)
      const freqResponse = Math.exp(-Math.pow((i - barCount / 2) / 10, 2));
      const wave = Math.sin(time + i * 0.5) * 0.3 + 0.7;
      const noise = Math.random() * 0.2;

      let barLevel = level * wave * freqResponse + noise * level * 0.3;
      barLevel = Math.max(0, Math.min(1, barLevel));
      levels.push(barLevel);
    }
  }

  // Ensure we have exactly barCount levels
  if (levels.length !== barCount) {
    // Interpolate or pad to match bar count
    const result = new Array(barCount).fill(0);
    const step = levels.length / barCount;
    for (let i = 0; i < barCount; i++) {
      const sourceIndex = Math.floor(i * step);
      result[i] = levels[Math.min(sourceIndex, levels.length - 1)] || 0;
    }
    levels = result;
  }

  floatingWindow.webContents.send("audio-visualizer", { levels, peak });
}

async function toggleRecording(forceState) {
  if (hotkeyTransitionInFlight) {
    console.log("[main] Hotkey transition already in progress");
    return;
  }

  // Debounce: prevent rapid successive calls
  const now = Date.now();
  if (now - lastHotkeyPressTime < HOTKEY_DEBOUNCE_MS) {
    console.log("[main] Hotkey debounced - ignoring rapid press");
    return;
  }
  lastHotkeyPressTime = now;

  const newState = forceState !== undefined ? forceState : !isRecording;

  if (newState === isRecording) return;
  hotkeyTransitionInFlight = true;
  try {
    if (newState) {
      console.log("[main] Hotkey pressed - starting recording");
      if (hotkeyConfigState.show_floating_window) {
        showFloatingWindow();
      }

      try {
        const response = await fetch(`${API_ORIGIN}/api/transcription/hotkey/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            device_id:
              hotkeyConfigState.device_id && hotkeyConfigState.device_id !== "default"
                ? hotkeyConfigState.device_id
                : null,
            model_name: "small",
            language_mode: hotkeyConfigState.language || "auto",
            execution_mode: "auto",
          })
        });
        if (!response.ok) {
          throw new Error(`Hotkey start failed with status ${response.status}`);
        }
      } catch (error) {
        console.error("[main] Failed to start hotkey transcription:", error);
        isRecording = false;
        closeHotkeyWebSocket();
        hideFloatingWindow();
        updateTrayIcon();
        updateTrayTooltip();
        return;
      }

      isRecording = true;
      allowHotkeyReconnect = true;
      playStartSound();
      updateTrayIcon();
      updateTrayTooltip();
      await createTray();
      connectHotkeyWebSocket();

      if (floatingWindow && !floatingWindow.isDestroyed()) {
        floatingWindow.webContents.send("recording-state", { isRecording: true });
      }
    } else {
      console.log("[main] Hotkey pressed - stopping recording");
      isRecording = false;
      closeHotkeyWebSocket();
      playStopSound();
      updateTrayIcon();

      let transcribedText = "";
      try {
        const response = await fetch(`${API_ORIGIN}/api/transcription/hotkey/stop`, {
          method: "POST",
          headers: { "Content-Type": "application/json" }
        });
        const result = await response.json();
        console.log("[main] Hotkey stop result:", JSON.stringify(result));
        transcribedText = result.final_transcription || result.final_text || result.text || "";
        lastTranscriptionText = transcribedText || lastTranscriptionText;
      } catch (error) {
        console.error("[main] Failed to stop hotkey transcription:", error);
      }

      if (floatingWindow && !floatingWindow.isDestroyed()) {
        floatingWindow.webContents.send("recording-state", { isRecording: false, processing: true });
      }

      const shouldPaste =
        hotkeyConfigState.auto_inject &&
        hotkeyConfigState.finish_mode_default === "finish_and_paste";

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
        if (floatingWindow && !floatingWindow.isDestroyed()) {
          floatingWindow.webContents.send("recording-state", { isRecording: false, finished: true });
        }
        if (transcribedText && mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send("transcription-result", { text: transcribedText, isPartial: false });
        }
        setTimeout(hideFloatingWindow, 500);
      }
      updateTrayTooltip();
      await createTray();
    }
  } finally {
    hotkeyTransitionInFlight = false;
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("hotkey-state-change", {
        isRecording: isRecording,
        hotkeyEnabled: hotkeyEnabled,
        accelerator: currentHotkeyAccelerator
      });
    }
  }
}

async function injectText(text) {
  if (!textInjector) {
    await initTextInjector();
  }

  if (textInjector) {
    return await textInjector.typeString(text);
  }

  return { success: false, error: "No text injection method available" };
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1480,
    height: 960,
    minWidth: 1220,
    minHeight: 780,
    backgroundColor: "#0e141b",
    autoHideMenuBar: true,
    title: APP_NAME,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.once("ready-to-show", () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.show();
    }
  });

  mainWindow.webContents.on("did-finish-load", () => {
    console.log("[main] Renderer finished loading");
  });

  mainWindow.webContents.on(
    "did-fail-load",
    (_event, errorCode, errorDescription, validatedURL) => {
      console.error(
        `[main] Renderer failed to load: code=${errorCode} description=${errorDescription} url=${validatedURL}`
      );
    }
  );

  mainWindow.webContents.on("render-process-gone", (_event, details) => {
    console.error(
      `[main] Renderer process gone: reason=${details.reason} exitCode=${details.exitCode}`
    );
  });

  mainWindow.webContents.on(
    "console-message",
    (_event, level, message, line, sourceId) => {
      if (level >= 2) {
        console.error(`[renderer] ${sourceId}:${line} ${message}`);
      }
    }
  );

  const explicitRendererUrl = process.env.TRANSCRIPTA_RENDERER_URL;
  if (explicitRendererUrl) {
    mainWindow.loadURL(explicitRendererUrl);
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "renderer", "dist", "index.html"));
  }

  mainWindow.on("close", (event) => {
    if (process.platform === "darwin") {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function createFloatingWindow() {
  if (floatingWindow && !floatingWindow.isDestroyed()) {
    return floatingWindow;
  }

  const primaryDisplay = screen.getPrimaryDisplay();
  const { width, height } = primaryDisplay.workAreaSize;

  const windowWidth = 420;
  const windowHeight = 140;
  const x = Math.round((width - windowWidth) / 2);
  const y = height - windowHeight - 30; // 30px from bottom

  floatingWindow = new BrowserWindow({
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
      preload: path.join(__dirname, "preload-floating.js"),
      contextIsolation: true,
      nodeIntegration: false,
      offscreen: false
    }
  });

  floatingWindow.loadFile(path.join(__dirname, "..", "floating-window.html"));

  floatingWindow.on("closed", () => {
    floatingWindow = null;
  });

  return floatingWindow;
}

function showFloatingWindow() {
  if (!floatingWindow || floatingWindow.isDestroyed()) {
    createFloatingWindow();
  }

  if (floatingWindow) {
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width, height } = primaryDisplay.workAreaSize;
    const windowWidth = 420;
    const windowHeight = 140;
    const x = Math.round((width - windowWidth) / 2);
    const y = height - windowHeight - 30;

    floatingWindow.setPosition(x, y);
    floatingWindow.showInactive();
    floatingWindow.setAlwaysOnTop(true, "screen-saver");
  }
}

function hideFloatingWindow() {
  if (floatingWindow && !floatingWindow.isDestroyed()) {
    floatingWindow.hide();
  }
}

function createQuickSettingsWindow() {
  if (quickSettingsWindow && !quickSettingsWindow.isDestroyed()) {
    return quickSettingsWindow;
  }

  quickSettingsWindow = new BrowserWindow({
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
    webPreferences: {
      preload: path.join(__dirname, "preload-quick-settings.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  quickSettingsWindow.loadFile(path.join(__dirname, "..", "quick-settings.html"));

  quickSettingsWindow.on("blur", () => {
    if (quickSettingsWindow && !quickSettingsWindow.isDestroyed()) {
      quickSettingsWindow.hide();
    }
  });

  quickSettingsWindow.on("closed", () => {
    quickSettingsWindow = null;
  });

  return quickSettingsWindow;
}

function showQuickSettingsWindow() {
  const win = createQuickSettingsWindow();
  if (!tray || !win) {
    return;
  }

  const trayBounds = tray.getBounds();
  const bounds = win.getBounds();
  const x = Math.max(0, Math.round(trayBounds.x + trayBounds.width / 2 - bounds.width / 2));
  const y = Math.max(0, Math.round(trayBounds.y - bounds.height - 8));

  win.setPosition(x, y, false);
  win.show();
  win.focus();
}

function updateFloatingTranscription(text, isPartial = true) {
  if (floatingWindow && !floatingWindow.isDestroyed()) {
    floatingWindow.webContents.send("transcription-update", { text, isPartial });
  }
}

function showMainWindowAndFocus(openSettings = false) {
  if (!mainWindow) {
    return;
  }
  if (mainWindow.isMinimized()) {
    mainWindow.restore();
  }
  mainWindow.show();
  mainWindow.focus();
  if (openSettings) {
    mainWindow.webContents.send("open-settings");
  }
}

async function createTray() {
  createTrayIcons();

  if (!tray) {
    const icon = isRecording ? trayIconRecording : trayIconIdle;
    tray = new Tray(icon || createCircleIcon(16, isRecording ? "#ef4444" : "#10b981"));
    tray.on("click", () => {
      if (!mainWindow) {
        return;
      }
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        showMainWindowAndFocus(false);
      }
    });
  }

  updateTrayTooltip();

  let settings = null;
  let devices = [];
  try {
    settings = await loadUserSettings();
  } catch (error) {
    const backendReady = await backendAlreadyRunning();
    if (backendReady) {
      console.error("[main] Failed to load settings for tray:", error.message);
    }
  }
  try {
    devices = await loadDevicesForDesktop();
  } catch (error) {
    const backendReady = await backendAlreadyRunning();
    if (backendReady) {
      console.error("[main] Failed to load devices for tray:", error.message);
    }
  }

  const hotkeySettings = settings?.hotkey || {};
  const activeLanguage = hotkeySettings.language || hotkeyConfigState.language || "auto";
  const activeDeviceId = hotkeySettings.device_id || hotkeyConfigState.device_id || "default";
  const pasteOnStop = (hotkeySettings.finish_mode_default || hotkeyConfigState.finish_mode_default) === "finish_and_paste";
  const microphoneDevices = devices.filter((device) => device.is_input && !(device.supports_loopback || device.is_loopback));
  const recentEntries = getRecentTranscriptEntries(8);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: `Show ${APP_NAME}`,
      click: () => showMainWindowAndFocus(false),
    },
    {
      label: `Hide ${APP_NAME}`,
      click: () => mainWindow?.hide(),
    },
    { type: "separator" },
    {
      label: "Recent Transcripts",
      submenu: recentEntries.length
        ? recentEntries.map((entry) => ({
            label: entry.title,
            toolTip: entry.preview || entry.transcriptPath,
            click: () => {
              showMainWindowAndFocus(false);
              if (fs.existsSync(entry.transcriptPath)) {
                shell.showItemInFolder(entry.transcriptPath);
              } else if (fs.existsSync(entry.sessionDir)) {
                shell.showItemInFolder(entry.sessionDir);
              }
            },
          }))
        : [{ label: "No recent transcripts", enabled: false }],
    },
    {
      label: "Quick Settings…",
      click: () => showQuickSettingsWindow(),
    },
    {
      label: "Settings…",
      accelerator: "CommandOrControl+,",
      click: () => showMainWindowAndFocus(true),
    },
    { type: "separator" },
    {
      label: "Recording",
      submenu: [
        {
          label: isRecording ? "Stop Recording" : "Start Recording",
          accelerator: currentHotkeyAccelerator || hotkeyConfigState.key_combination || DEFAULT_HOTKEY,
          click: () => void toggleRecording(isRecording ? false : true),
        },
        {
          label: "Paste Last Transcript",
          enabled: Boolean(lastTranscriptionText),
          click: async () => {
            if (!lastTranscriptionText) {
              return;
            }
            const result = await injectText(lastTranscriptionText);
            if (!result.success && result.method !== "clipboard_only") {
              showPlaceholderDialog("Paste Failed", result.error || "Text injection failed.");
            }
          },
        },
      ],
    },
    {
      label: "Quick Settings",
      submenu: [
        {
          label: "Enable Global Hotkey",
          type: "checkbox",
          checked: Boolean(hotkeySettings.enabled ?? hotkeyEnabled),
          click: async (menuItem) => {
            const next = {
              ...(settings || {}),
              hotkey: {
                ...(hotkeySettings || {}),
                enabled: menuItem.checked,
              },
            };
            await saveUserSettings(next);
            await applyHotkeyConfig(next.hotkey);
            if (mainWindow && !mainWindow.isDestroyed()) {
              mainWindow.webContents.send("settings-updated");
            }
            await createTray();
          },
        },
        {
          label: "Paste on Stop",
          type: "checkbox",
          checked: pasteOnStop,
          click: async (menuItem) => {
            const next = {
              ...(settings || {}),
              hotkey: {
                ...(hotkeySettings || {}),
                finish_mode_default: menuItem.checked ? "finish_and_paste" : "finish",
              },
            };
            await saveUserSettings(next);
            await createTray();
          },
        },
        { type: "separator" },
        {
          label: "Language",
          submenu: QUICK_LANGUAGE_OPTIONS.map((language) => ({
            label: language.label,
            type: "radio",
            checked: activeLanguage === language.code,
            click: async () => {
              const next = {
                ...(settings || {}),
                hotkey: {
                  ...(hotkeySettings || {}),
                  language: language.code,
                },
              };
              await saveUserSettings(next);
              await createTray();
            },
          })),
        },
        {
          label: "Microphone",
          submenu: [
            {
              label: "Default microphone",
              type: "radio",
              checked: activeDeviceId === "default",
              click: async () => {
                const next = {
                  ...(settings || {}),
                  hotkey: {
                    ...(hotkeySettings || {}),
                    device_id: "default",
                  },
                };
                await saveUserSettings(next);
                await createTray();
              },
            },
            ...microphoneDevices.map((device) => ({
              label: device.name,
              type: "radio",
              checked: activeDeviceId === device.id,
              click: async () => {
                const next = {
                  ...(settings || {}),
                  hotkey: {
                    ...(hotkeySettings || {}),
                    device_id: device.id,
                  },
                };
                await saveUserSettings(next);
                await createTray();
              },
            })),
          ],
        },
      ],
    },
    { type: "separator" },
    {
      label: "Help & Support",
      submenu: [
        {
          label: "Help Center",
          click: () => showPlaceholderDialog("Help Center", "Documentation and help-center links can be wired here once the public docs target is finalized."),
        },
        {
          label: "Talk to Support",
          click: () => showPlaceholderDialog("Support", "Support routing is not configured yet. Use the main app logs and session exports for troubleshooting."),
        },
        {
          label: "Send Feedback",
          click: () => showPlaceholderDialog("Feedback", "Feedback flow is not wired yet. Capture the issue details and session logs from the main app."),
        },
        { type: "separator" },
        {
          label: "Check for Updates",
          click: () => showPlaceholderDialog("Updates", "Auto-update is not configured in this dev build."),
        },
      ],
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => app.quit(),
    },
  ]);

  tray.setContextMenu(contextMenu);
}

function updateTrayIcon() {
  if (!tray) return;

  const icon = isRecording ? trayIconRecording : trayIconIdle;
  if (icon) {
    tray.setImage(icon);
  }
}

function updateTrayTooltip() {
  if (tray) {
    const status = isRecording ? "Recording" : (hotkeyEnabled ? "Ready" : "Disabled");
    const hotkey = currentHotkeyAccelerator || DEFAULT_HOTKEY;
    const audioStatus = audioFeedbackEnabled ? "On" : "Off";
    tray.setToolTip(`${APP_NAME} - ${status}\nHotkey: ${hotkey}\nAudio: ${audioStatus}`);
  }
}

async function applyHotkeyConfig(config) {
  hotkeyConfigState = {
    ...hotkeyConfigState,
    ...config,
    key_combination:
      config.key_combination || config.accelerator || hotkeyConfigState.key_combination || DEFAULT_HOTKEY,
  };

  if (config.audioFeedback !== undefined) {
    audioFeedbackEnabled = config.audioFeedback;
  }

  const requestedEnabled =
    typeof config.enabled === "boolean" ? config.enabled : hotkeyEnabled;
  const requestedAccelerator =
    hotkeyConfigState.key_combination || currentHotkeyAccelerator || DEFAULT_HOTKEY;

  hotkeyEnabled = requestedEnabled;

  if (!hotkeyEnabled) {
    unregisterHotkey();
    updateTrayTooltip();
    return { success: true, enabled: false, accelerator: requestedAccelerator, config: hotkeyConfigState };
  }

  const result = registerHotkey(requestedAccelerator);
  if (result.success) {
    console.log("[main] Hotkey updated to:", requestedAccelerator);
    updateTrayTooltip();
    return { success: true, enabled: true, accelerator: requestedAccelerator, config: hotkeyConfigState };
  }

  console.error("[main] Failed to update hotkey:", result.error);
  return result;
}

// IPC Handlers

ipcMain.handle("choose-directory", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory", "createDirectory"]
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle("choose-pdf", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openFile"],
    filters: [{ name: "PDF Files", extensions: ["pdf"] }]
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

// Hotkey IPC handlers
ipcMain.handle("hotkey:register", async (event, { accelerator }) => {
  if (!accelerator) {
    return { success: false, error: "No accelerator provided" };
  }

  console.log(`[main] IPC: Registering hotkey "${accelerator}"`);
  const result = registerHotkey(accelerator);

  if (result.success) {
    updateTrayTooltip();
  }

  return result;
});

ipcMain.handle("hotkey:unregister", async () => {
  console.log("[main] IPC: Unregistering hotkey");
  const result = unregisterHotkey();

  if (result.success) {
    updateTrayTooltip();
  }

  return result;
});

ipcMain.handle("hotkey:validate", async (event, { accelerator }) => {
  if (!accelerator) {
    return { valid: false, error: "No accelerator provided" };
  }

  const validation = validateAccelerator(accelerator);

  if (!validation.valid) {
    return { valid: false, error: validation.error };
  }

  const availability = checkHotkeyAvailability(accelerator);

  return {
    valid: true,
    available: !availability.registered,
    error: availability.error
  };
});

ipcMain.handle("hotkey:toggle", async (event, enabled) => {
  hotkeyEnabled = enabled;

  if (hotkeyEnabled) {
    const accelerator = currentHotkeyAccelerator || DEFAULT_HOTKEY;
    const result = registerHotkey(accelerator);
    console.log(`[main] Hotkey system ${enabled ? "enabled" : "disabled"}`, result.success ? "" : `- ${result.error}`);
  } else {
    unregisterHotkey();
    console.log("[main] Hotkey system disabled");
  }

  updateTrayTooltip();
  return { success: true, enabled: hotkeyEnabled };
});

ipcMain.handle("hotkey:get-state", async () => {
  return {
    enabled: hotkeyEnabled,
    isRecording: isRecording,
    accelerator: currentHotkeyAccelerator || DEFAULT_HOTKEY,
    registered: !!currentHotkeyAccelerator,
    defaultHotkey: DEFAULT_HOTKEY,
    mode: "toggle",
    audioFeedback: audioFeedbackEnabled,
    config: {
      ...hotkeyConfigState,
      enabled: hotkeyEnabled,
      key_combination: currentHotkeyAccelerator || hotkeyConfigState.key_combination || DEFAULT_HOTKEY,
    },
    is_registered: !!currentHotkeyAccelerator,
    session: {
      is_active: isRecording,
      total_activations: 0,
      last_activated_at: null,
    },
  };
});

ipcMain.handle("hotkey:get-default", async () => {
  return {
    accelerator: DEFAULT_HOTKEY,
    platform: process.platform,
    note: "Uses toggle mode: press once to start, press again to stop"
  };
});

// Update hotkey configuration from settings
ipcMain.handle("hotkey:update-config", async (event, config) => {
  console.log("[main] IPC: Updating hotkey config", config);
  const result = await applyHotkeyConfig(config);
  await createTray();
  return result;
});

// Text injection IPC handler
ipcMain.handle("text:inject", async (event, text) => {
  const result = await injectText(text);
  return result;
});

// Tray IPC handler
ipcMain.handle("tray:update-tooltip", async (event, tooltip) => {
  if (tray) {
    tray.setToolTip(tooltip || `${APP_NAME} - ${isRecording ? "Recording" : "Ready"}`);
  }
  return { success: true };
});

ipcMain.handle("models:get-download-root", async () => {
  return { root: path.join(app.getPath("userData"), "models") };
});

ipcMain.handle("models:download", async (event, { modelId }) => {
  const requestContext = {
    modelId,
    timestamp: new Date().toISOString(),
    sender: event.sender.getTitle?.() || 'unknown'
  };
  console.log('[models:download:ipc] Request received:', requestContext);

  if (!modelDownloadManager) {
    const error = new Error("Model download manager is not ready");
    console.error('[models:download:ipc] Manager not ready:', requestContext);
    throw error;
  }

  try {
    const result = await modelDownloadManager.downloadModel(modelId);
    console.log('[models:download:ipc] Request completed successfully:', { modelId });
    return result;
  } catch (error) {
    console.error('[models:download:ipc] Request failed:', {
      ...requestContext,
      error: error.message,
      code: error.code,
      stack: error.stack
    });
    throw error;
  }
});

ipcMain.handle("models:cancel", async (event, { modelId }) => {
  console.log('[models:cancel:ipc] Request received:', { modelId, timestamp: new Date().toISOString() });
  if (!modelDownloadManager) {
    console.error('[models:cancel:ipc] Manager not ready');
    return { ok: false, error: "model-download-manager-not-ready" };
  }
  const result = await modelDownloadManager.cancelDownload(modelId);
  console.log('[models:cancel:ipc] Result:', result);
  return result;
});

ipcMain.handle("models:remove", async (event, { modelId }) => {
  console.log('[models:remove:ipc] Request received:', { modelId, timestamp: new Date().toISOString() });
  if (!modelDownloadManager) {
    console.error('[models:remove:ipc] Manager not ready');
    throw new Error("Model download manager is not ready");
  }
  try {
    const result = await modelDownloadManager.removeModel(modelId);
    console.log('[models:remove:ipc] Success:', { modelId });
    return result;
  } catch (error) {
    console.error('[models:remove:ipc] Failed:', { modelId, error: error.message });
    throw error;
  }
});

// Model Download Service IPC handlers (with comprehensive logging)
ipcMain.handle("model-service:download", async (event, { modelId, modelType, sourceUrl, options = {} }) => {
  console.log('[model-service:download:ipc] Request received:', { modelId, modelType, sourceUrl: sourceUrl?.substring(0, 50) + '...', timestamp: new Date().toISOString() });
  if (!modelDownloadService) {
    console.error('[model-service:download:ipc] Service not ready');
    throw new Error("Model download service is not ready");
  }
  try {
    const result = await modelDownloadService.downloadModel(modelId, modelType, sourceUrl, options);
    console.log('[model-service:download:ipc] Success:', { modelId, path: result.path, size: result.size });
    return result;
  } catch (error) {
    console.error('[model-service:download:ipc] Failed:', { modelId, error: error.message });
    throw error;
  }
});

ipcMain.handle("model-service:get-target-path", async (event, { modelId, modelType }) => {
  if (!modelDownloadService) {
    throw new Error("Model download service is not ready");
  }
  return modelDownloadService._getTargetPath(modelId, modelType);
});

// Backend-to-renderer forwarding for hotkey mode
ipcMain.on("transcription-result", (event, data) => {
  updateFloatingTranscription(data.text, data.isPartial);
});

// Handle floating window button actions
ipcMain.on("floating-window-action", async (event, { action }) => {
  console.log("[main] Floating window action:", action);
  
  if (action === "cancel") {
    // Stop recording without pasting
    if (isRecording) {
      isRecording = false;
      playStopSound();
      updateTrayIcon();
      
      // Stop backend session without getting text
      try {
        await fetch(`${API_ORIGIN}/api/transcription/hotkey/stop`, {
          method: "POST",
          headers: { "Content-Type": "application/json" }
        });
      } catch (error) {
        console.error("[main] Failed to stop:", error);
      }
      
      // Close WebSocket
      closeHotkeyWebSocket();
      
      hideFloatingWindow();
      updateTrayTooltip();
      await createTray();
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send("hotkey-state-change", {
          isRecording: false,
          hotkeyEnabled: hotkeyEnabled,
          accelerator: currentHotkeyAccelerator
        });
      }
    }
  } else if (action === "finish") {
    if (isRecording) {
      isRecording = false;
      closeHotkeyWebSocket();
      playStopSound();
      updateTrayIcon();
      updateTrayTooltip();

      let transcribedText = "";
      try {
        const response = await fetch(`${API_ORIGIN}/api/transcription/hotkey/stop`, {
          method: "POST",
          headers: { "Content-Type": "application/json" }
        });
        const result = await response.json();
        transcribedText = result.final_transcription || result.final_text || result.text || "";
        lastTranscriptionText = transcribedText || lastTranscriptionText;
      } catch (error) {
        console.error("[main] Failed to finish hotkey transcription:", error);
      }

      if (floatingWindow && !floatingWindow.isDestroyed()) {
        floatingWindow.webContents.send("recording-state", { isRecording: false, finished: true });
      }
      if (transcribedText && mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send("transcription-result", { text: transcribedText, isPartial: false });
      }
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send("hotkey-state-change", {
          isRecording: false,
          hotkeyEnabled: hotkeyEnabled,
          accelerator: currentHotkeyAccelerator
        });
      }
      await createTray();
      setTimeout(hideFloatingWindow, 500);
    }
  } else if (action === "finish-and-paste") {
    if (isRecording) {
      const previousMode = hotkeyConfigState.finish_mode_default;
      hotkeyConfigState.finish_mode_default = "finish_and_paste";
      try {
        await toggleRecording(false);
      } finally {
        hotkeyConfigState.finish_mode_default = previousMode;
      }
    }
  }
});

ipcMain.handle("quick-settings:get-data", async () => {
  const settings = await loadUserSettings();
  const devices = await loadDevicesForDesktop();
  return {
    appName: APP_NAME,
    settings,
    devices,
    languages: QUICK_LANGUAGE_OPTIONS,
    hotkeyState: {
      enabled: hotkeyEnabled,
      accelerator: currentHotkeyAccelerator || hotkeyConfigState.key_combination || DEFAULT_HOTKEY,
      isRecording,
    },
  };
});

ipcMain.handle("quick-settings:update", async (event, nextSettings) => {
  await saveUserSettings(nextSettings);
  if (nextSettings?.hotkey) {
    await applyHotkeyConfig(nextSettings.hotkey);
  }
  await createTray();
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("settings-updated");
  }
  return { success: true };
});

ipcMain.handle("quick-settings:open-full", async () => {
  showMainWindowAndFocus(true);
  if (quickSettingsWindow && !quickSettingsWindow.isDestroyed()) {
    quickSettingsWindow.hide();
  }
  return { success: true };
});

ipcMain.handle("quick-settings:close", async () => {
  if (quickSettingsWindow && !quickSettingsWindow.isDestroyed()) {
    quickSettingsWindow.hide();
  }
  return { success: true };
});

// App event handlers

app.whenReady().then(async () => {
  await startBackend();
  await waitForBackendReady();
  modelDownloadManager = new ModelDownloadManager({
    getApiOrigin: () => API_ORIGIN,
    getUserDataPath: () => app.getPath("userData"),
    emit: (event, payload) => broadcastToWindows("model-download-event", { event, payload }),
  });
  modelDownloadService = new ModelDownloadService();
  await initTextInjector();
  createMainWindow();
  await createTray();

  // Register global shortcut for Settings (Ctrl+,)
  globalShortcut.register("CommandOrControl+,", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
      mainWindow.webContents.send("open-settings");
    }
  });

  console.log("[main] Global hotkey starts disabled until settings are loaded.");
}).catch((error) => {
  console.error("[main] App startup failed", error);
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  unregisterHotkey();
  if (backendProcess) {
    backendProcess.kill();
  }
  if (webSocketReconnectTimeout) {
    clearTimeout(webSocketReconnectTimeout);
  }
  if (hotkeyWebSocket) {
    try {
      hotkeyWebSocket.close();
    } catch {}
  }
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});

// Handle open-settings from main process (tray menu, keyboard shortcut)
ipcMain.on("open-settings", () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("open-settings");
  }
});

app.on("activate", () => {
  if (mainWindow === null) {
    createMainWindow();
  } else {
    mainWindow.show();
  }
});

// Hide dock icon on macOS for cleaner experience
if (process.platform === "darwin") {
  app.dock.hide();
}
