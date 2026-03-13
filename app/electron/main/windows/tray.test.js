const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const Module = require("node:module");

const TRAY_PATH = path.join(__dirname, "tray.js");
const HOTKEY_HANDLERS_PATH = require.resolve("../ipc/hotkeyHandlers", { paths: [__dirname] });

class FakeTray {
  constructor() {
    this.handlers = new Map();
    this.contextMenu = null;
  }
  on(event, handler) { this.handlers.set(event, handler); }
  setContextMenu(menu) { this.contextMenu = menu; }
  setToolTip() {}
}

function loadTrayModule() {
  const originalLoad = Module._load;
  const showCalls = [];
  const saveCalls = [];
  const applyHotkeyConfigCalls = [];
  const settingsUpdatedEvents = [];
  let quitCalled = false;
  const hotkeyHandlersModule = {
    applyHotkeyConfig: async (config) => { applyHotkeyConfigCalls.push(config); },
    toggleRecording: async () => {},
  };
  const electronModule = {
    Tray: FakeTray,
    Menu: { buildFromTemplate: (template) => template },
    shell: { showItemInFolder: () => {} },
    dialog: { showMessageBox: async () => ({}) },
    app: { quit: () => { quitCalled = true; } },
  };
  const state = {
    tray: null,
    mainWindow: {
      isDestroyed: () => false,
      webContents: { send: (channel) => settingsUpdatedEvents.push(channel) },
    },
    isRecording: false,
    trayIconRecording: null,
    trayIconIdle: null,
    cachedSettings: { hotkey: {} },
    cachedDevices: [],
    APP_NAME: "OpenWispr",
    QUICK_LANGUAGE_OPTIONS: [],
    DEFAULT_HOTKEY: "Control+F",
    hotkeyConfigState: {},
  };

  Module._load = function patchedLoad(request, parent, isMain) {
    if (request === "electron") {
      return electronModule;
    }
    if (request === "../shared/state") return state;
    if (request === "../utils/api") {
      return {
        loadUserSettings: async () => state.cachedSettings,
        saveUserSettings: async (next) => { saveCalls.push(next); },
        loadDevicesForDesktop: async () => [],
      };
    }
    if (request === "./mainWindow") {
      return { showMainWindowAndFocus: (openSettings) => showCalls.push(openSettings) };
    }
    if (request === "./quickSettingsWindow") return { showQuickSettingsWindow: () => {} };
    if (request === "../services/textInjector") return { injectText: async () => ({ success: true }) };
    if (request === "./trayUtils") {
      return {
        createTrayIcons: () => {},
        createCircleIcon: () => null,
        updateTrayIcon: () => {},
        updateTrayTooltip: () => {},
      };
    }
    if (request === "../services/backendSpawn") return { backendAlreadyRunning: async () => false };
    return originalLoad.call(this, request, parent, isMain);
  };

  try {
    delete require.cache[TRAY_PATH];
    delete require.cache[HOTKEY_HANDLERS_PATH];
    require.cache[HOTKEY_HANDLERS_PATH] = {
      id: HOTKEY_HANDLERS_PATH,
      filename: HOTKEY_HANDLERS_PATH,
      loaded: true,
      exports: hotkeyHandlersModule,
    };
    const moduleExports = require(TRAY_PATH);
    return { ...moduleExports, state, showCalls, saveCalls, applyHotkeyConfigCalls, settingsUpdatedEvents, getQuitCalled: () => quitCalled };
  } finally {
    Module._load = originalLoad;
    delete require.cache[TRAY_PATH];
    delete require.cache[HOTKEY_HANDLERS_PATH];
  }
}

test("tray click recreates the main window when the reference is missing", async () => {
  const { createTray, state, showCalls } = loadTrayModule();
  await createTray();
  assert.ok(state.tray);
  state.mainWindow = null;

  const clickHandler = state.tray.handlers.get("click");
  assert.equal(typeof clickHandler, "function");
  clickHandler();

  assert.deepEqual(showCalls, [false]);
});

test("tray quick settings updates persist and refresh cached settings", async () => {
  const { createTray, state, saveCalls, settingsUpdatedEvents } = loadTrayModule();
  state.cachedSettings = { hotkey: { finish_mode_default: "finish" } };
  await createTray();

  const quickSettingsMenu = state.tray.contextMenu.find((item) => item.label === "Quick Settings");
  const pasteOnStopItem = quickSettingsMenu.submenu.find((item) => item.label === "Paste on Stop");
  assert.ok(pasteOnStopItem);

  await pasteOnStopItem.click({ checked: true });

  assert.equal(saveCalls.length, 1);
  assert.equal(state.cachedSettings.hotkey.finish_mode_default, "finish_and_paste");
  assert.deepEqual(settingsUpdatedEvents, ["settings-updated"]);
});

test("tray quit invokes app.quit", async () => {
  const { createTray, state, getQuitCalled } = loadTrayModule();
  await createTray();
  const quitItem = state.tray.contextMenu.find((item) => item.label === "Quit");
  assert.ok(quitItem);
  quitItem.click();
  assert.equal(getQuitCalled(), true);
});
