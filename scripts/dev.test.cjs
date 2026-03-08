const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const { repoRoot, resolveChildCwd, resolveDevTargets, sanitizeCwd } = require("./dev.cjs");

test("sanitizeCwd strips Windows extended-length prefix", () => {
  assert.equal(sanitizeCwd("\\\\?\\D:\\repo\\openwispr"), "D:\\repo\\openwispr");
  assert.equal(sanitizeCwd("D:\\repo\\openwispr"), "D:\\repo\\openwispr");
});

test("resolveChildCwd is derived from repo root, not inherited process cwd", () => {
  assert.equal(resolveChildCwd(), sanitizeCwd(repoRoot));
  assert.ok(path.isAbsolute(resolveChildCwd()));
});

test("resolveDevTargets launches backend and electron scripts directly", () => {
  const targets = resolveDevTargets();

  assert.equal(targets.backend.command, process.execPath);
  assert.equal(targets.electron.command, process.execPath);
  assert.equal(targets.backend.args[0], path.join(repoRoot, "scripts", "run-backend-dev.cjs"));
  assert.equal(targets.electron.args[0], path.join(repoRoot, "app", "electron", "scripts", "dev.js"));
});
