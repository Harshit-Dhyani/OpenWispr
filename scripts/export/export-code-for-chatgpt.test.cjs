const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');

const {
  buildExportResult,
  createFormattedEntriesForFile,
  main,
  parseArgs,
} = require('./export-code-for-chatgpt.cjs');

function makeTempRepo() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'openwispr-code-export-'));
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function writeFile(root, relativePath, contents) {
  const fullPath = path.join(root, relativePath);
  ensureDir(path.dirname(fullPath));
  fs.writeFileSync(fullPath, contents, 'utf8');
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

test('parseArgs supports scope clean dry-run and max-chars', () => {
  const options = parseArgs(['--scope', 'api,core', '--clean', '--dry-run', '--max-chars', '12345', '--hard-max-chars', '20000']);
  assert.deepEqual(options.scope, ['api', 'core']);
  assert.equal(options.clean, true);
  assert.equal(options.dryRun, true);
  assert.equal(options.targetChars, 12345);
  assert.equal(options.hardMaxChars, 20000);
});

test('collect/build excludes vendor and build output', () => {
  const repoRoot = makeTempRepo();
  writeFile(repoRoot, 'app/api/server.py', 'print("ok")\n');
  writeFile(repoRoot, 'app/api/node_modules/pkg/index.js', 'ignored\n');
  writeFile(repoRoot, 'app/api/__pycache__/server.pyc', 'ignored\n');
  writeFile(repoRoot, 'app/electron/frontend/src/App.tsx', 'export const App = () => null;\n');
  writeFile(repoRoot, 'app/electron/frontend/node_modules/lib/index.js', 'ignored\n');
  writeFile(repoRoot, 'app/electron/renderer/dist/assets/main.js', 'ignored\n');
  const exportResult = buildExportResult({}, repoRoot);
  const api = exportResult.subsystems.find((entry) => entry.subsystem === 'api');
  const electron = exportResult.subsystems.find((entry) => entry.subsystem === 'electron');
  assert.equal(api.includedFileCount, 1);
  assert.equal(electron.includedFileCount, 1);
});

test('oversized files split into ranged fragments', () => {
  const lines = Array.from({ length: 60 }, (_, index) => `line-${index + 1}-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`).join('\n');
  const entries = createFormattedEntriesForFile('app/core/huge.py', lines, 400);
  assert.ok(entries.length > 1);
  assert.match(entries[0].displayPath, /lines 1-/);
  assert.match(entries[1].output, /BEGIN FILE: app\/core\/huge.py \(lines/);
});

test('chunking is deterministic for the same input order', () => {
  const repoRoot = makeTempRepo();
  writeFile(repoRoot, 'app/core/a.py', 'a\n');
  writeFile(repoRoot, 'app/core/b.py', 'b\n');
  writeFile(repoRoot, 'app/core/c.py', 'c\n');
  const first = buildExportResult({ scope: ['core'], targetChars: 40, hardMaxChars: 100 }, repoRoot);
  const second = buildExportResult({ scope: ['core'], targetChars: 40, hardMaxChars: 100 }, repoRoot);
  assert.deepEqual(first.manifest.subsystems.core.chunkFiles, second.manifest.subsystems.core.chunkFiles);
  assert.deepEqual(first.subsystems[0].chunkFiles.map((entry) => entry.contents), second.subsystems[0].chunkFiles.map((entry) => entry.contents));
});

test('scope only exports requested subsystems', () => {
  const repoRoot = makeTempRepo();
  writeFile(repoRoot, 'app/api/server.py', 'api\n');
  writeFile(repoRoot, 'app/core/main.py', 'core\n');
  const exportResult = buildExportResult({ scope: ['api'] }, repoRoot);
  assert.deepEqual(exportResult.subsystems.map((entry) => entry.subsystem), ['api']);
});

test('dry-run does not write output', () => {
  const repoRoot = makeTempRepo();
  writeFile(repoRoot, 'app/api/server.py', 'api\n');
  main(['--dry-run'], repoRoot);
  assert.equal(fs.existsSync(path.join(repoRoot, 'code')), false);
});

test('clean replaces prior generated output safely', () => {
  const repoRoot = makeTempRepo();
  writeFile(repoRoot, 'app/api/server.py', 'api\n');
  ensureDir(path.join(repoRoot, 'code'));
  writeFile(repoRoot, 'code/stale.txt', 'old\n');
  main(['--clean'], repoRoot);
  assert.equal(fs.existsSync(path.join(repoRoot, 'code', 'stale.txt')), false);
  assert.equal(fs.existsSync(path.join(repoRoot, 'code', 'api', 'api-part-001.txt')), true);
});

test('index.json matches generated chunk files', () => {
  const repoRoot = makeTempRepo();
  writeFile(repoRoot, 'app/api/server.py', 'api\n');
  writeFile(repoRoot, 'app/core/main.py', 'core\n');
  main(['--clean', '--scope', 'api,core'], repoRoot);
  const manifest = readJson(path.join(repoRoot, 'code', 'index.json'));
  assert.deepEqual(Object.keys(manifest.subsystems), ['api', 'core']);
  for (const [subsystem, details] of Object.entries(manifest.subsystems)) {
    for (const chunkFile of details.chunkFiles) {
      assert.equal(fs.existsSync(path.join(repoRoot, 'code', subsystem, chunkFile)), true);
    }
  }
});
