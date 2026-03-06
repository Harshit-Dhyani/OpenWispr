const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const Module = require("node:module");

const HANDLERS_PATH = path.join(__dirname, "handlers.js");

function loadHandlersModule() {
  const originalLoad = Module._load;
  const registeredOn = new Map();
  const registeredHandle = new Map();
  const stopCalls = [];

  const state = {
    isRecording: true,
    hotkeyPendingAction: null,
    hotkeyConfigState: {
      finish_mode_default: "finish_and_paste",
      auto_inject: true,
    },
    isDebugLoggingEnabled: () => false,
    mainWindow: null,
    quickSettingsWindow: null,
    tray: null,
    floatingWindow: null,
  };

  Module._load = function patchedLoad(request, parent, isMain) {
    if (request === "electron") {
      return {
        ipcMain: {
          on(channel, handler) {
            registeredOn.set(channel, handler);
          },
          handle(channel, handler) {
            registeredHandle.set(channel, handler);
          },
        },
        dialog: {
          showOpenDialog: async () => ({ canceled: true, filePaths: [] }),
        },
      };
    }

    if (request === "../shared/state") {
      return state;
    }

    if (request === "./hotkeyHandlers") {
      return {
        validateAccelerator: () => ({ valid: true }),
        checkHotkeyAvailability: () => ({ registered: false }),
        registerHotkey: () => ({ success: true }),
        unregisterHotkey: () => ({ success: true }),
        applyHotkeyConfig: async () => ({ success: true }),
        buildHotkeyStatePayload: () => ({}),
        requestStartRecording: async () => ({}),
        requestStopRecording: async () => ({}),
        stopRecording: async (options = {}) => {
          stopCalls.push(options);
          return {};
        },
        closeHotkeyWebSocket: () => {},
      };
    }

    if (request === "../utils/api") {
      return {
        loadUserSettings: async () => ({}),
        saveUserSettings: async () => {},
        loadDevicesForDesktop: async () => [],
      };
    }

    if (request === "../services/textInjector") {
      return { injectText: async () => ({ success: true }) };
    }

    if (request === "../windows/mainWindow") {
      return { showMainWindowAndFocus: () => {} };
    }

    if (request === "../windows/floatingWindow") {
      return { hideFloatingWindow: () => {} };
    }

    if (request === "../windows/tray") {
      return {
        createTray: async () => {},
        scheduleTrayRefresh: async () => {},
      };
    }

    if (request === "../../strings/en") {
      return {
        ELECTRON_STRINGS: {
          hotkey: {
            errors: { noAcceleratorProvided: "No accelerator provided" },
            notes: { toggleMode: "Toggle mode" },
          },
          floating: {},
        },
      };
    }

    return originalLoad.call(this, request, parent, isMain);
  };

  try {
    delete require.cache[HANDLERS_PATH];
    require(HANDLERS_PATH);
  } finally {
    Module._load = originalLoad;
    delete require.cache[HANDLERS_PATH];
  }

  return {
    registeredOn,
    registeredHandle,
    stopCalls,
    state,
  };
}

test("floating finish actions stop recording while keeping floating result visible", async () => {
  const { registeredOn, stopCalls, state } = loadHandlersModule();
  const handler = registeredOn.get("floating-window-action");

  assert.equal(typeof handler, "function");

  state.isRecording = true;
  await handler({}, { action: "finish" });
  assert.deepEqual(stopCalls.at(-1), { keepFloatingResultVisible: true });

  state.isRecording = true;
  await handler({}, { action: "finish-and-paste" });
  assert.deepEqual(stopCalls.at(-1), { keepFloatingResultVisible: true });
});
