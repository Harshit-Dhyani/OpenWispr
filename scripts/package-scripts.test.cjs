const test = require("node:test");
const assert = require("node:assert/strict");

const pkg = require("../package.json");

test("root dev scripts resolve script paths from npm_package_json", () => {
  assert.match(pkg.scripts.dev, /npm_package_json/);
  assert.match(pkg.scripts.dev, /runDev\(\)/);
  assert.match(pkg.scripts["dev:backend"], /npm_package_json/);
});
