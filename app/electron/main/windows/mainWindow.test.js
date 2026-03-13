const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const Module = require("node:module");

const MAIN_WINDOW_PATH = path.join(__dirname, "mainWindow.js");

class FakeBrowserWindow {
  static instances = [];

  constructor() {
    this.visible = false;
    this.minimized = false;
    this.destroyed = false;
    this.handlers = new Map();
    this.onceHandlers = new Map();
    this.webContents = {
      sent: [],
      on: () => {},
      send: (channel, payload) => {
        this.webContents.sent.push({ channel, payload });
      },
    };
    FakeBrowserWindow.instances.push(this);
  }

  once(event, handler) { this.onceHandlers.set(event, handler); }
  on(event, handler) { this.handlers.set(event, handler); }
  emit(event, ...args) {
    const onceHandler = this.onceHandlers.get(event);
    if (onceHandler) {
      this.onceHandlers.delete(event);
      onceHandler(...args);
    }
    const handler = this.handlers.get(event);
    if (handler) {
      handler(...args);
    }
  }
  show() { this.visible = true; }
  hide() { this.visible = false; }
  focus() {}
  restore() { this.minimized = false; }
  isVisible() { return this.visible; }
  isMinimized() { return this.minimized; }
  isDestroyed() { return this.destroyed; }
  loadURL() {}
  loadFile() {}
}

function loadMainWindowModule() {
  const originalLoad = Module._load;
  const state = {
    APP_NAME: "OpenWispr",
    mainWindow: null,
    isQuitting: false,
    isDebugLoggingEnabled: () => false,
  };

  Module._load = function patchedLoad(request, parent, isMain) {
    if (request === "electron") {
      return { BrowserWindow: FakeBrowserWindow };
    }
    if (request === "../shared/state") {
      return state;
    }
    if (request === "../shared/iconPaths") {
      return { getWindowIconPath: () => null };
    }
    return originalLoad.call(this, request, parent, isMain);
  };

  try {
    delete require.cache[MAIN_WINDOW_PATH];
    const moduleExports = require(MAIN_WINDOW_PATH);
    return { ...moduleExports, state };
  } finally {
    Module._load = originalLoad;
    delete require.cache[MAIN_WINDOW_PATH];
  }
}

test("createMainWindow hides on close until a real quit is in progress", () => {
  FakeBrowserWindow.instances = [];
  const { createMainWindow, state } = loadMainWindowModule();
  createMainWindow();

  const win = state.mainWindow;
  assert.ok(win);
  const closeHandler = win.handlers.get("close");
  assert.equal(typeof closeHandler, "function");

  const event = {
    prevented: false,
    preventDefault() { this.prevented = true; },
  };

  closeHandler(event);
  assert.equal(event.prevented, true);
  assert.equal(win.isVisible(), false);

  state.isQuitting = true;
  const quitEvent = {
    prevented: false,
    preventDefault() { this.prevented = true; },
  };
  closeHandler(quitEvent);
  assert.equal(quitEvent.prevented, false);
});

test("showMainWindowAndFocus recreates the main window and opens settings", () => {
  FakeBrowserWindow.instances = [];
  const { showMainWindowAndFocus, state } = loadMainWindowModule();

  showMainWindowAndFocus(true);
  const win = state.mainWindow;

  assert.ok(win);
  assert.equal(FakeBrowserWindow.instances.length, 1);

  win.emit("ready-to-show");
  assert.equal(win.isVisible(), true);
  assert.deepEqual(win.webContents.sent, [{ channel: "open-settings", payload: undefined }]);
});
