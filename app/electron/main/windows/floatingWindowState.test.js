const test = require("node:test");
const assert = require("node:assert/strict");

const {
  DEFAULT_FLOATING_WINDOW_SIZE,
  clampFloatingWindowPosition,
  resolveFloatingWindowBounds,
} = require("./floatingWindowState");

test("clampFloatingWindowPosition keeps window inside visible work area", () => {
  const result = clampFloatingWindowPosition(
    { x: 5000, y: -120 },
    { x: 0, y: 0, width: 1920, height: 1080 },
    DEFAULT_FLOATING_WINDOW_SIZE,
  );

  assert.equal(result.x, 1460);
  assert.equal(result.y, 0);
});

test("resolveFloatingWindowBounds prefers saved position but clamps it", () => {
  const bounds = resolveFloatingWindowBounds({
    savedPosition: { x: 1800, y: 980 },
    preset: "top-left",
    workArea: { x: 0, y: 0, width: 1600, height: 900 },
  });

  assert.deepEqual(bounds, {
    width: 460,
    height: 300,
    x: 1140,
    y: 600,
  });
});

test("resolveFloatingWindowBounds falls back to preset position", () => {
  const bounds = resolveFloatingWindowBounds({
    savedPosition: null,
    preset: "bottom-right",
    workArea: { x: 10, y: 20, width: 1000, height: 700 },
  });

  assert.deepEqual(bounds, {
    width: 460,
    height: 300,
    x: 526,
    y: 392,
  });
});
