const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const Module = require("node:module");

const TRAY_PATH = path.join(__dirname, "tray.js");

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
  let quitCalled = false;
  const electronModule = {
    Tray: FakeTray,
    Menu: { buildFromTemplate: (template) => template },
    shell: { showItemInFolder: () => {} },
    dialog: { showMessageBox: async () => ({}) },
    app: { quit: () => { quitCalled = true; } },
  };
  const state = {
    tray: null,
    mainWindow: null,
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
        saveUserSettings: async () => {},
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
    const moduleExports = require(TRAY_PATH);
    return { ...moduleExports, state, showCalls, getQuitCalled: () => quitCalled };
  } finally {
    Module._load = originalLoad;
    delete require.cache[TRAY_PATH];
  }
}

test("tray click recreates the main window when the reference is missing", async () => {
  const { createTray, state, showCalls } = loadTrayModule();
  await createTray();
  assert.ok(state.tray);

  const clickHandler = state.tray.handlers.get("click");
  assert.equal(typeof clickHandler, "function");
  clickHandler();

  assert.deepEqual(showCalls, [false]);
});

test("tray quit invokes app.quit", async () => {
  const { createTray, state, getQuitCalled } = loadTrayModule();
  await createTray();
  const quitItem = state.tray.contextMenu.find((item) => item.label === "Quit");
  assert.ok(quitItem);
  quitItem.click();
  assert.equal(getQuitCalled(), true);
});
