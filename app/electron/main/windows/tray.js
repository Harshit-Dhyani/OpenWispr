// Tray icon and menu management
const { Tray, Menu, shell, dialog, app } = require("electron");
const path = require("path");
const fs = require("fs");
const state = require("../shared/state");
const { loadUserSettings, saveUserSettings, loadDevicesForDesktop } = require("../utils/api");
const { showMainWindowAndFocus } = require("./mainWindow");
const { showQuickSettingsWindow } = require("./quickSettingsWindow");
const { injectText } = require("../services/textInjector");
const { createTrayIcons, createCircleIcon, updateTrayIcon, updateTrayTooltip } = require("./trayUtils");

let trayRefreshTimer = null;
let trayRefreshPromise = null;

function getRecentTranscriptEntries(limit = 8) {
  const sessionsRoot = path.resolve(__dirname, "..", "..", "..", "sessions");
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

async function createTray() {
  createTrayIcons();

  if (!state.tray) {
    const icon = state.isRecording ? state.trayIconRecording : state.trayIconIdle;
    state.tray = new Tray(icon || createCircleIcon(16, state.isRecording ? "#ef4444" : "#10b981"));
    state.tray.on("click", () => {
      if (!state.mainWindow || state.mainWindow.isDestroyed()) {
        showMainWindowAndFocus(false);
        return;
      }
      if (state.mainWindow.isVisible()) {
        state.mainWindow.hide();
      } else {
        showMainWindowAndFocus(false);
      }
    });
  }

  updateTrayTooltip();

  let settings = state.cachedSettings;
  let devices = Array.isArray(state.cachedDevices) ? state.cachedDevices : [];
  if (!settings) {
    try {
      settings = await loadUserSettings();
      state.cachedSettings = settings;
    } catch (error) {
      const { backendAlreadyRunning } = require("../services/backendSpawn");
      const backendReady = await backendAlreadyRunning();
      if (backendReady) {
        console.error("[main] Failed to load settings for tray:", error.message);
      }
    }
  }
  if (devices.length === 0) {
    try {
      devices = await loadDevicesForDesktop();
      state.cachedDevices = devices;
    } catch (error) {
      const { backendAlreadyRunning } = require("../services/backendSpawn");
      const backendReady = await backendAlreadyRunning();
      if (backendReady) {
        console.error("[main] Failed to load devices for tray:", error.message);
      }
    }
  }

  const hotkeySettings = settings?.hotkey || {};
  const activeLanguage = hotkeySettings.language || state.hotkeyConfigState.language || "auto";
  const activeDeviceId = hotkeySettings.device_id || state.hotkeyConfigState.device_id || "default";
  const pasteOnStop = (hotkeySettings.finish_mode_default || state.hotkeyConfigState.finish_mode_default) === "finish_and_paste";
  const microphoneDevices = devices.filter((device) => device.is_input && !(device.supports_loopback || device.is_loopback));
  const recentEntries = getRecentTranscriptEntries(8);

  async function persistTraySettings(nextSettings) {
    const { applyHotkeyConfig } = require("../ipc/hotkeyHandlers");
    state.cachedSettings = nextSettings;
    settings = nextSettings;
    await saveUserSettings(nextSettings);
    if (nextSettings.hotkey) {
      await applyHotkeyConfig(nextSettings.hotkey);
    }
    if (state.mainWindow && !state.mainWindow.isDestroyed()) {
      state.mainWindow.webContents.send("settings-updated");
    }
    await createTray();
  }

  const contextMenu = Menu.buildFromTemplate([
    {
      label: `Show ${state.APP_NAME}`,
      click: () => showMainWindowAndFocus(false),
    },
    {
      label: `Hide ${state.APP_NAME}`,
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
          label: state.isRecording ? "Stop Recording" : "Start Recording",
          accelerator: state.currentHotkeyAccelerator || state.hotkeyConfigState.key_combination || state.DEFAULT_HOTKEY,
          click: () => {
            const { toggleRecording } = require("../ipc/hotkeyHandlers");
            void toggleRecording(state.isRecording ? false : true);
          },
        },
        {
          label: "Paste Last Transcript",
          enabled: Boolean(state.lastTranscriptionText),
          click: async () => {
            if (!state.lastTranscriptionText) {
              return;
            }
            const result = await injectText(state.lastTranscriptionText);
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
          click: async (menuItem) => {            const next = {
              ...(settings || {}),
              hotkey: {
                ...(hotkeySettings || {}),
                enabled: menuItem.checked,
              },
            };
            await persistTraySettings(next);
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
            await persistTraySettings(next);
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
              await persistTraySettings(next);
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
                await persistTraySettings(next);
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
                await persistTraySettings(next);
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
        app.quit();
      },
    },
  ]);

  state.tray.setContextMenu(contextMenu);
}

function scheduleTrayRefresh(delayMs = 150) {
  if (trayRefreshTimer) {
    clearTimeout(trayRefreshTimer);
  }

  trayRefreshPromise = new Promise((resolve) => {
    trayRefreshTimer = setTimeout(async () => {
      trayRefreshTimer = null;
      try {
        await createTray();
      } catch (error) {
        console.error("[main] Failed to refresh tray:", error.message);
      } finally {
        trayRefreshPromise = null;
        resolve();
      }
    }, delayMs);
  });

  return trayRefreshPromise;
}

module.exports = {
  createTrayIcons,
  createCircleIcon,
  updateTrayIcon,
  updateTrayTooltip,
  createTray,
  scheduleTrayRefresh,
};
