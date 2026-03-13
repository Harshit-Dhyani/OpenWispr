const test = require("node:test");
const assert = require("node:assert/strict");

const { shouldKeepFloatingResultVisible } = require("./hotkeyStopPolicy");

test("keeps floating result visible only when explicitly requested", () => {
  assert.equal(
    shouldKeepFloatingResultVisible({
      showFloatingWindow: true,
      pendingAction: "finish",
      keepResultVisible: true,
    }),
    true,
  );

  assert.equal(
    shouldKeepFloatingResultVisible({
      showFloatingWindow: true,
      pendingAction: "finish",
      keepResultVisible: false,
    }),
    false,
  );

  assert.equal(
    shouldKeepFloatingResultVisible({
      showFloatingWindow: true,
      pendingAction: "cancel",
      keepResultVisible: true,
    }),
    false,
  );
});
