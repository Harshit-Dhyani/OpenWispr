const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const Module = require("node:module");

const PRELOAD_PATH = path.join(__dirname, "preload-floating.js");

function loadPreload({ sendSync }) {
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
    delete require.cache[PRELOAD_PATH];
    require(PRELOAD_PATH);
    return exposed;
  } finally {
    Module._load = originalLoad;
    delete require.cache[PRELOAD_PATH];
  }
}

test("preload-floating reads strings from sync IPC", () => {
  const floating = {
    status: { idle: "Idle" },
    waitingForSpeech: "Wait",
    actions: { cancel: "Cancel" },
    resultMeta: { transcriptReady: "Ready" },
  };

  let channel = null;
  const exposed = loadPreload({
    sendSync: (requestedChannel) => {
      channel = requestedChannel;
      return floating;
    },
  });

  assert.equal(channel, "floating:get-strings");
  assert.deepEqual(exposed.transcriptaFloating.strings, floating);
});

test("preload-floating falls back when IPC string resolution fails", () => {
  const originalConsoleError = console.error;
  console.error = () => {};

  try {
    const exposed = loadPreload({
      sendSync: () => {
        throw new Error("channel unavailable");
      },
    });

    assert.equal(
      exposed.transcriptaFloating.strings.waitingForSpeech,
      "Waiting for speech...",
    );
  } finally {
    console.error = originalConsoleError;
  }
});
