const test = require("node:test");
const assert = require("node:assert/strict");

const {
  parseHoldAccelerator,
  eventMatchesAccelerator,
  shouldReleaseAccelerator,
  createHoldModeController,
} = require("./holdModeHotkeys");

test("parses CommandOrControl accelerators for Windows hold mode", () => {
  assert.deepEqual(parseHoldAccelerator("CommandOrControl+Shift+T", "win32"), {
    accelerator: "CommandOrControl+Shift+T",
    modifiers: { ctrl: true, alt: false, shift: true, meta: false },
    key: "T",
  });
});

test("matches keydown events with exact modifiers", () => {
  const definition = parseHoldAccelerator("Alt+D", "win32");
  assert.equal(
    eventMatchesAccelerator(definition, {
      rawcode: 68,
      altKey: true,
      ctrlKey: false,
      shiftKey: false,
      metaKey: false,
    }),
    true,
  );
  assert.equal(
    eventMatchesAccelerator(definition, {
      rawcode: 68,
      altKey: true,
      ctrlKey: false,
      shiftKey: true,
      metaKey: false,
    }),
    false,
  );
});

test("releases an active hold shortcut when the main key is released", () => {
  const definition = parseHoldAccelerator("Alt+D", "win32");
  assert.equal(
    shouldReleaseAccelerator(definition, {
      rawcode: 68,
      altKey: true,
      ctrlKey: false,
      shiftKey: false,
      metaKey: false,
    }),
    true,
  );
});

test("configures a hold-mode hook and fires press/release callbacks", async () => {
  const listeners = new Map();
  const fakeHook = {
    on(eventName, handler) {
      listeners.set(eventName, handler);
    },
    off(eventName) {
      listeners.delete(eventName);
    },
    start() {},
    stop() {},
  };

  const calls = [];
  const controller = createHoldModeController({
    platform: "win32",
    loadHook: () => fakeHook,
    onPress: async (source) => calls.push(`press:${source}`),
    onRelease: async (source) => calls.push(`release:${source}`),
  });

  const result = controller.configure([{ accelerator: "Alt+D", source: "microphone" }]);
  assert.equal(result.success, true);
  assert.equal(result.enabled, true);

  listeners.get("keydown")?.({
    rawcode: 68,
    altKey: true,
    ctrlKey: false,
    shiftKey: false,
    metaKey: false,
  });
  listeners.get("keyup")?.({
    rawcode: 68,
    altKey: false,
    ctrlKey: false,
    shiftKey: false,
    metaKey: false,
  });

  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(calls, ["press:microphone", "release:microphone"]);
});

test("reports whether hold mode is supported", () => {
  const supportedController = createHoldModeController({
    loadHook: () => ({ on() {}, off() {}, start() {}, stop() {} }),
  });
  assert.equal(supportedController.isSupported(), true);

  const unsupportedController = createHoldModeController({
    loadHook: () => {
      throw new Error("missing");
    },
  });
  assert.equal(unsupportedController.isSupported(), false);
});
