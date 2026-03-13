const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");

const { resolveFloatingWindowHtmlPath } = require("./floatingWindowState");

test("resolveFloatingWindowHtmlPath prefers the built floating renderer page", () => {
  const resolved = resolveFloatingWindowHtmlPath((candidate) =>
    candidate.endsWith(path.join("renderer", "dist", "floating.html")),
  );

  assert.equal(
    resolved,
    path.join(__dirname, "..", "..", "renderer", "dist", "floating.html"),
  );
});

test("resolveFloatingWindowHtmlPath falls back to the legacy html when needed", () => {
  const resolved = resolveFloatingWindowHtmlPath(() => false);

  assert.equal(
    resolved,
    path.join(__dirname, "..", "..", "floating-window.html"),
  );
});
