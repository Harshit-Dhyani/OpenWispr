const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const { resolvePnpmLaunch, sanitizeCwd } = require("./dev.cjs");

test("sanitizeCwd strips Windows extended-length prefix", () => {
  assert.equal(sanitizeCwd("\\\\?\\D:\\repo\\openwispr"), "D:\\repo\\openwispr");
  assert.equal(sanitizeCwd("D:\\repo\\openwispr"), "D:\\repo\\openwispr");
});

test("resolvePnpmLaunch prefers npm_execpath when provided", () => {
  const launch = resolvePnpmLaunch({ npm_execpath: "C:/npm/pnpm.cjs" }, "C:/node/node.exe");
  assert.deepEqual(launch, {
    command: "C:/node/node.exe",
    args: ["C:/npm/pnpm.cjs"],
  });
});

test("resolvePnpmLaunch uses explicit pnpm.cjs on Windows-like setups without npm_execpath", () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "openwispr-dev-test-"));
  const appData = path.join(tempRoot, "AppData");
  const pnpmPath = path.join(appData, "npm", "node_modules", "pnpm", "bin", "pnpm.cjs");
  fs.mkdirSync(path.dirname(pnpmPath), { recursive: true });
  fs.writeFileSync(pnpmPath, "// test");

  const originalPlatform = process.platform;
  Object.defineProperty(process, "platform", { value: "win32" });

  try {
    const launch = resolvePnpmLaunch({ APPDATA: appData }, "C:/node/node.exe");
    assert.deepEqual(launch, {
      command: "C:/node/node.exe",
      args: [pnpmPath],
    });
  } finally {
    Object.defineProperty(process, "platform", { value: originalPlatform });
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});
