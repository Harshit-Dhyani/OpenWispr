const { app, BrowserWindow, dialog, ipcMain, Tray, Menu, globalShortcut, screen, nativeImage } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");

// Window references
let mainWindow = null;
let floatingWindow = null;
let tray = null;

// Backend process
let backendProcess = null;
const API_ORIGIN = "http://127.0.0.1:8765";

// Hotkey state
let hotkeyEnabled = true;
let isRecording = false;
let currentHotkeyAccelerator = null;

// Text injection module (loaded dynamically)
let textInjector = null;

// Native module availability flags
let hasRobotjs = false;
let hasNodeKeySender = false;

// Audio feedback enabled
let audioFeedbackEnabled = true;

// WebSocket for audio levels
let hotkeyWebSocket = null;
let webSocketReconnectTimeout = null;

// Tray icons cache
let trayIconIdle = null;
let trayIconRecording = null;

// Default hotkey - Windows-friendly, avoids Alt+Space (system menu)
const DEFAULT_HOTKEY = "CommandOrControl+Shift+T";

function resolvePythonLaunch() {
  const repoRoot = path.resolve(__dirname, "..");
  const venvPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
  if (process.env.TRANSCRIPTA_PYTHON) {
    return { command: process.env.TRANSCRIPTA_PYTHON, args: ["-m", "app.api_main"] };
  }
  if (fs.existsSync(venvPython)) {
    return { command: venvPython, args: ["-m", "app.api_main"] };
  }
  return { command: "py", args: ["-3", "-m", "app.api_main"] };
}

async function backendAlreadyRunning() {
  try {
    const response = await fetch(`${API_ORIGIN}/api/health`);
    return response.ok;
  } catch {
    return false;
  }
}

async function startBackend() {
  if (backendProcess) {
    return;
  }
  if (await backendAlreadyRunning()) {
    return;
  }
  const repoRoot = path.resolve(__dirname, "..");
  const { command, args } = resolvePythonLaunch();
  backendProcess = spawn(command, args, {
    cwd: repoRoot,
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
    if (currentHotkeyAccelerator === accelerator) {
      return { registered: true, error: "Hotkey is already registered by Transcripta" };
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
      toggleRecording();
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
async function connectHotkeyWebSocket() {
  if (hotkeyWebSocket) {
    try {
      hotkeyWebSocket.close();
    } catch {}
  }

  try {
    const WebSocket = require("ws");
    hotkeyWebSocket = new WebSocket(`ws://127.0.0.1:8765/api/transcription/hotkey/ws`);

    hotkeyWebSocket.on("open", () => {
      console.log("[main] Hotkey WebSocket connected");
    });

    hotkeyWebSocket.on("message", (data) => {
      try {
        const message = JSON.parse(data);

        // Forward audio level updates to floating window
        if (message.type === "hotkey_partial" && message.payload) {
          const audioLevel = message.payload.audio_level || 0;
          updateFloatingAudioLevel(audioLevel);
        }

        // Handle final transcription
        if (message.type === "hotkey_stopped" && message.payload) {
          const finalText = message.payload.final_text || "";
          if (finalText && floatingWindow && !floatingWindow.isDestroyed()) {
            floatingWindow.webContents.send("transcription-update", {
              text: finalText,
              isPartial: false
            });
          }
        }
      } catch (error) {
        console.error("[main] WebSocket message error:", error);
      }
    });

    hotkeyWebSocket.on("close", () => {
      console.log("[main] Hotkey WebSocket disconnected");
      hotkeyWebSocket = null;
      // Attempt to reconnect after a delay
      webSocketReconnectTimeout = setTimeout(connectHotkeyWebSocket, 3000);
    });

    hotkeyWebSocket.on("error", (error) => {
      console.error("[main] Hotkey WebSocket error:", error.message);
    });
  } catch (error) {
    console.error("[main] Failed to connect hotkey WebSocket:", error);
    webSocketReconnectTimeout = setTimeout(connectHotkeyWebSocket, 5000);
  }
}

// Update floating window with audio level data
function updateFloatingAudioLevel(level) {
  if (!floatingWindow || floatingWindow.isDestroyed()) return;

  // Generate frequency-like data based on the level
  const barCount = 36;
  const levels = [];

  // Create a realistic-looking waveform
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

  floatingWindow.webContents.send("audio-visualizer", { levels, peak: level });
}

async function toggleRecording(forceState) {
  const newState = forceState !== undefined ? forceState : !isRecording;

  if (newState === isRecording) return;

  isRecording = newState;

  if (isRecording) {
    // Start recording
    console.log("[main] Hotkey pressed - starting recording");
    playStartSound();
    showFloatingWindow();

    // Update tray icon to recording state
    updateTrayIcon();

    // Connect WebSocket for audio levels
    connectHotkeyWebSocket();

    // Notify backend to start hotkey mode transcription
    try {
      await fetch(`${API_ORIGIN}/api/transcription/hotkey/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "toggle" })
      });
    } catch (error) {
      console.error("[main] Failed to start hotkey transcription:", error);
    }

    // Update floating window
    if (floatingWindow && !floatingWindow.isDestroyed()) {
      floatingWindow.webContents.send("recording-state", { isRecording: true });
    }
  } else {
    // Stop recording
    console.log("[main] Hotkey pressed - stopping recording");
    playStopSound();

    // Update tray icon back to idle
    updateTrayIcon();

    // Get transcription result
    let transcribedText = "";
    try {
      const response = await fetch(`${API_ORIGIN}/api/transcription/hotkey/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      const result = await response.json();
      transcribedText = result.final_transcription || result.text || "";
    } catch (error) {
      console.error("[main] Failed to stop hotkey transcription:", error);
    }

    // Close WebSocket
    if (hotkeyWebSocket) {
      try {
        hotkeyWebSocket.close();
      } catch {}
      hotkeyWebSocket = null;
    }
    if (webSocketReconnectTimeout) {
      clearTimeout(webSocketReconnectTimeout);
      webSocketReconnectTimeout = null;
    }

    // Update floating window with processing state
    if (floatingWindow && !floatingWindow.isDestroyed()) {
      floatingWindow.webContents.send("recording-state", { isRecording: false, processing: true });
    }

    // Inject text into active window
    if (transcribedText) {
      hideFloatingWindow();

      // Small delay to allow window focus to return to previous app
      setTimeout(async () => {
        const injectResult = await injectText(transcribedText);
        if (!injectResult.success) {
          console.error("[main] Text injection failed:", injectResult.error);
          const { clipboard } = require("electron");
          clipboard.writeText(transcribedText);
        }
      }, 150);
    } else {
      // Show "Ready" state briefly then hide
      if (floatingWindow && !floatingWindow.isDestroyed()) {
        floatingWindow.webContents.send("recording-state", { isRecording: false, finished: true });
      }
      setTimeout(hideFloatingWindow, 500);
    }
  }

  // Update tray tooltip
  updateTrayTooltip();

  // Notify renderer of state change
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("hotkey-state-change", {
      isRecording: isRecording,
      hotkeyEnabled: hotkeyEnabled,
      accelerator: currentHotkeyAccelerator
    });
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
    title: "Transcripta",
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
    mainWindow.loadFile(path.join(__dirname, "renderer", "dist", "index.html"));
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
    movable: false,
    minimizable: false,
    maximizable: false,
    closable: false,
    focusable: false,
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

  floatingWindow.loadFile(path.join(__dirname, "floating-window.html"));

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

function updateFloatingTranscription(text, isPartial = true) {
  if (floatingWindow && !floatingWindow.isDestroyed()) {
    floatingWindow.webContents.send("transcription-update", { text, isPartial });
  }
}

function createTray() {
  createTrayIcons();

  const icon = isRecording ? trayIconRecording : trayIconIdle;
  tray = new Tray(icon || createCircleIcon(16, isRecording ? "#ef4444" : "#10b981"));
  updateTrayTooltip();

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Show Transcripta",
      click: () => {
        if (mainWindow) {
          if (mainWindow.isMinimized()) mainWindow.restore();
          mainWindow.show();
          mainWindow.focus();
        }
      }
    },
    {
      label: "Hide Transcripta",
      click: () => {
        if (mainWindow) {
          mainWindow.hide();
        }
      }
    },
    { type: "separator" },
    {
      label: "Settings",
      accelerator: "CommandOrControl+,",
      click: () => {
        if (mainWindow) {
          if (mainWindow.isMinimized()) mainWindow.restore();
          mainWindow.show();
          mainWindow.focus();
          mainWindow.webContents.send("open-settings");
        }
      }
    },
    { type: "separator" },
    {
      label: hotkeyEnabled ? "Disable Global Hotkey" : "Enable Global Hotkey",
      click: () => {
        hotkeyEnabled = !hotkeyEnabled;
        if (hotkeyEnabled && currentHotkeyAccelerator) {
          registerHotkey(currentHotkeyAccelerator);
        } else {
          unregisterHotkey();
        }
        createTray();
      }
    },
    {
      label: audioFeedbackEnabled ? "Disable Audio Feedback" : "Enable Audio Feedback",
      click: () => {
        audioFeedbackEnabled = !audioFeedbackEnabled;
        createTray();
      }
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => {
        app.quit();
      }
    }
  ]);

  tray.setContextMenu(contextMenu);

  tray.on("click", () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
        mainWindow.focus();
      }
    }
  });
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
    tray.setToolTip(`Transcripta - ${status}\nHotkey: ${hotkey}\nAudio: ${audioStatus}`);
  }
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
    audioFeedback: audioFeedbackEnabled
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
  
  if (config.accelerator && config.accelerator !== currentHotkeyAccelerator) {
    // Unregister old hotkey
    if (currentHotkeyAccelerator) {
      globalShortcut.unregister(currentHotkeyAccelerator);
    }
    // Register new hotkey
    const result = registerHotkey(config.accelerator);
    if (result.success) {
      console.log("[main] Hotkey updated to:", config.accelerator);
    } else {
      console.error("[main] Failed to update hotkey:", result.error);
    }
    return result;
  }
  
  // Update other settings
  if (config.audioFeedback !== undefined) {
    audioFeedbackEnabled = config.audioFeedback;
  }
  
  return { success: true };
});

// Text injection IPC handler
ipcMain.handle("text:inject", async (event, text) => {
  const result = await injectText(text);
  return result;
});

// Tray IPC handler
ipcMain.handle("tray:update-tooltip", async (event, tooltip) => {
  if (tray) {
    tray.setToolTip(tooltip || `Transcripta - ${isRecording ? "Recording" : "Ready"}`);
  }
  return { success: true };
});

// Backend-to-renderer forwarding for hotkey mode
ipcMain.on("transcription-result", (event, data) => {
  updateFloatingTranscription(data.text, data.isPartial);

  if (!data.isPartial && data.text) {
    hideFloatingWindow();
    injectText(data.text);
  }
});

// App event handlers

app.whenReady().then(async () => {
  await startBackend();
  await initTextInjector();
  createMainWindow();
  createTray();

  // Register global shortcut for Settings (Ctrl+,)
  globalShortcut.register("CommandOrControl+,", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
      mainWindow.webContents.send("open-settings");
    }
  });

  // Try to register the default hotkey on startup
  console.log("[main] Attempting to register default hotkey...");
  const result = registerHotkey(DEFAULT_HOTKEY);

  if (result.success) {
    console.log(`[main] Default hotkey registered successfully: ${DEFAULT_HOTKEY}`);
  } else {
    console.warn(`[main] Failed to register default hotkey: ${result.error}`);
    console.warn("[main] App will continue without global hotkey. User can configure a different hotkey from settings.");

    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("hotkey-registration-failed", {
        accelerator: DEFAULT_HOTKEY,
        error: result.error,
        details: result.details
      });
    }
  }
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
