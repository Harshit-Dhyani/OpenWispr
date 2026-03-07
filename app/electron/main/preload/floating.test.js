const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const Module = require("node:module");

const CANONICAL_PRELOAD_PATH = path.join(__dirname, "floating.js");
const LEGACY_PRELOAD_PATH = path.join(__dirname, "..", "preload-floating.js");

function loadPreload(preloadPath, { sendSync }) {
  const originalLoad = Module._load;
  const exposed = {};

  Module._load = function patchedLoad(request, parent, isMain) {
    if (request === "electron") {
      return {
        contextBridge: {
          exposeInMainWorld(name, value) {
            exposed[name] = value;
          },
        },
        ipcRenderer: {
          sendSync,
          on() {},
          removeListener() {},
          send() {},
        },
      };
    }
    return originalLoad.call(this, request, parent, isMain);
  };

  try {
    delete require.cache[preloadPath];
    require(preloadPath);
    return exposed;
  } finally {
    Module._load = originalLoad;
    delete require.cache[preloadPath];
  }
}

test("floating preload reads strings from sync IPC via canonical path", () => {
  const floating = {
    status: { idle: "Idle" },
    waitingForSpeech: "Wait",
    actions: { cancel: "Cancel" },
    resultMeta: { transcriptReady: "Ready" },
  };

  let channel = null;
  const exposed = loadPreload(CANONICAL_PRELOAD_PATH, {
    sendSync: (requestedChannel) => {
      channel = requestedChannel;
      return floating;
    },
  });

  assert.equal(channel, "floating:get-strings");
  assert.deepEqual(exposed.openwisprFloating.strings, floating);
});

test("floating preload shim still resolves the canonical preload", () => {
  const exposed = loadPreload(LEGACY_PRELOAD_PATH, {
    sendSync: () => ({
      status: { idle: "Idle" },
      waitingForSpeech: "Wait",
      actions: { cancel: "Cancel" },
      resultMeta: { transcriptReady: "Ready" },
    }),
  });

  assert.equal(typeof exposed.openwisprFloating.finishRecording, "function");
});

test("floating preload falls back when IPC string resolution fails", () => {
  const originalConsoleError = console.error;
  console.error = () => {};

  try {
    const exposed = loadPreload(CANONICAL_PRELOAD_PATH, {
      sendSync: () => {
        throw new Error("channel unavailable");
      },
    });

    assert.equal(
      exposed.openwisprFloating.strings.waitingForSpeech,
      "Waiting for speech...",
    );
  } finally {
    console.error = originalConsoleError;
  }
});
