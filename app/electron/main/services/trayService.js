// Tray management service
const { Tray, Menu, nativeImage, shell } = require("electron");
const path = require("path");
const fs = require("fs");
const state = require("../shared/state");
const windowManager = require("./windowManager");

const { APP_NAME } = require("../shared/generated/appMeta");

async function loadUserSettings() {
  const stateModule = require("../shared/state");
  const response = await fetch(`${stateModule.API_ORIGIN}/api/settings`);
  return response.json();
}

async function saveUserSettings(settings) {
  const stateModule = require("../shared/state");
  return fetch(`${stateModule.API_ORIGIN}/api/settings`, {
    method: "POST",
    body: JSON.stringify(settings),
    headers: { "Content-Type": "application/json" },
  });
}

async function loadDevicesForDesktop() {
  const stateModule = require("../shared/state");
  const result = await fetch(`${stateModule.API_ORIGIN}/api/devices`);
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
      } catch (error) {
        console.error("[tray] Error reading session metadata:", error);
      }
    }

    let preview = "";
    if (fs.existsSync(transcriptPath)) {
      try {
        preview = fs.readFileSync(transcriptPath, "utf8").trim().replace(/\s+/g, " ").slice(0, 120);
      } catch (error) {
        console.error("[tray] Error reading transcript file:", error);
      }
    }

    let modifiedAt = 0;
    try {
      modifiedAt = fs.statSync(sessionDir).mtimeMs;
    } catch (error) {
      console.error("[tray] Error getting session directory stats:", error);
    }

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
  const { dialog } = require("electron");
  dialog.showMessageBox({
    type: "info",
    title,
    message,
    buttons: ["OK"],
  }).catch((error) => {
    console.error("[tray] Error showing dialog:", error);
  });
}

function createTrayIcons() {
  const size = 16;

  state.trayIconIdle = createCircleIcon(size, "#10b981");
  state.trayIconRecording = createCircleIcon(size, "#ef4444");
}

function createCircleIcon(size, color) {
  const canvas = Buffer.alloc(size * size * 4);

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const idx = (y * size + x) * 4;
      const dx = x - size / 2 + 0.5;
      const dy = y - size / 2 + 0.5;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist <= size / 2 - 1) {
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

async function createTray() {
  createTrayIcons();

  if (!state.tray) {
    const icon = state.isRecording ? state.trayIconRecording : state.trayIconIdle;
    state.tray = new Tray(icon || createCircleIcon(16, state.isRecording ? "#ef4444" : "#10b981"));
    state.tray.on("click", () => {
      if (!state.mainWindow) {
        return;
      }
      if (state.mainWindow.isVisible()) {
        state.mainWindow.hide();
      } else {
        const windowManager = require("./windowManager");
        windowManager.showMainWindowAndFocus(false);
      }
    });
  }

  updateTrayTooltip();

  let settings = null;
  let devices = [];
  try {
    settings = await loadUserSettings();
  } catch (error) {
    const stateModule = require("../shared/state");
    const backendReady = await fetch(`${stateModule.API_ORIGIN}/api/health`).then(r => r.ok).catch(() => false);
    if (backendReady) {
      console.error("[tray] Failed to load settings for tray:", error.message);
    }
  }
  try {
    devices = await loadDevicesForDesktop();
  } catch (error) {
    const stateModule = require("../shared/state");
    const backendReady = await fetch(`${stateModule.API_ORIGIN}/api/health`).then(r => r.ok).catch(() => false);
    if (backendReady) {
      console.error("[tray] Failed to load devices for tray:", error.message);
    }
  }

  const hotkeySettings = settings?.hotkey || {};
  const activeLanguage = hotkeySettings.language || state.hotkeyConfigState.language || "auto";
  const activeDeviceId = hotkeySettings.device_id || state.hotkeyConfigState.device_id || "default";
  const pasteOnStop = (hotkeySettings.finish_mode_default || state.hotkeyConfigState.finish_mode_default) === "finish_and_paste";
  const microphoneDevices = devices.filter((device) => device.is_input && !(device.supports_loopback || device.is_loopback));
  const recentEntries = getRecentTranscriptEntries(8);

  const windowManager = require("./windowManager");

  const contextMenu = Menu.buildFromTemplate([
    {
      label: `Show ${APP_NAME}`,
      click: () => windowManager.showMainWindowAndFocus(false),
    },
    {
      label: `Hide ${APP_NAME}`,
      click: () => state.mainWindow?.hide(),
    },
    { type: "separator" },
    {
      label: "Recent Transcripts",
      submenu: recentEntries.length
        ? recentEntries.map((entry) => ({
            label: entry.title,
            toolTip: entry.preview || entry.transcriptPath,
            click: () => {
              windowManager.showMainWindowAndFocus(false);
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
      click: () => windowManager.showQuickSettingsWindow(),
    },
    {
      label: "Settings…",
      accelerator: "CommandOrControl+,",
      click: () => windowManager.showMainWindowAndFocus(true),
    },
    { type: "separator" },
    {
      label: "Recording",
      submenu: [
        {
          label: state.isRecording ? "Stop Recording" : "Start Recording",
          accelerator: state.currentHotkeyAccelerator || state.hotkeyConfigState.key_combination || state.DEFAULT_HOTKEY,
          click: async () => {
            const hotkeyService = require("./hotkeyService");
            await hotkeyService.toggleRecording(state.isRecording ? false : true);
          },
        },
        {
          label: "Paste Last Transcript",
          enabled: Boolean(state.lastTranscriptionText),
          click: async () => {
            if (!state.lastTranscriptionText) {
              return;
            }
            const textInjector = require("./textInjector");
            const result = await textInjector.injectText(state.lastTranscriptionText);
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
          checked: Boolean(hotkeySettings.enabled ?? state.hotkeyEnabled),
          click: async (menuItem) => {
            const next = {
              ...(settings || {}),
              hotkey: {
                ...(hotkeySettings || {}),
                enabled: menuItem.checked,
              },
            };
            await saveUserSettings(next);
            const hotkeyService = require("./hotkeyService");
            await hotkeyService.applyHotkeyConfig(next.hotkey);
            if (state.mainWindow && !state.mainWindow.isDestroyed()) {
              state.mainWindow.webContents.send("settings-updated");
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
          submenu: state.QUICK_LANGUAGE_OPTIONS.map((language) => ({
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
      click: () => {
        const { app } = require("electron");
        app.quit();
      },
    },
  ]);

  state.tray.setContextMenu(contextMenu);
}

function updateTrayIcon() {
  if (!state.tray) return;

  const icon = state.isRecording ? state.trayIconRecording : state.trayIconIdle;
  if (icon) {
    state.tray.setImage(icon);
  }
}

function updateTrayTooltip() {
  if (state.tray) {
    const status = state.isRecording ? "Recording" : (state.hotkeyEnabled ? "Ready" : "Disabled");
    const hotkey = state.currentHotkeyAccelerator || state.DEFAULT_HOTKEY;
    const audioStatus = state.audioFeedbackEnabled ? "On" : "Off";
    state.tray.setToolTip(`${APP_NAME} - ${status}\nHotkey: ${hotkey}\nAudio: ${audioStatus}`);
  }
}

module.exports = {
  createTray,
  updateTrayIcon,
  updateTrayTooltip,
  showPlaceholderDialog,
};
