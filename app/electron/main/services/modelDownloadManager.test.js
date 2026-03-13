const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const { ModelDownloadManager } = require("./modelDownloadManager");

function createManager() {
  return new ModelDownloadManager({
    getApiOrigin: () => "http://127.0.0.1:8765",
    getUserDataPath: () => process.cwd(),
    emit: () => {},
  });
}

test("marks undici connect timeout errors as retryable", () => {
  const manager = createManager();
  const error = new Error("fetch failed");
  error.cause = { code: "UND_ERR_CONNECT_TIMEOUT", message: "connect timeout" };

  assert.equal(manager._isRetryableDownloadError(error), true);
});

test("prefers content-range total bytes for resumed downloads", () => {
  const manager = createManager();
  const response = {
    headers: new Headers({
      "content-range": "bytes 1048576-2097151/3145728",
      "content-length": "1048576",
    }),
    status: 206,
  };

  assert.equal(manager._resolveArtifactTotalBytes(response, 1048576), 3145728);
});

test("adds jittered exponential backoff", () => {
  const manager = createManager();
  const delay = manager._computeRetryDelayMs(2);

  assert.ok(delay >= 4000);
  assert.ok(delay < 4500);
});

test("streams a web response to disk and fsyncs it", async () => {
  const manager = createManager();
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "transcripta-download-"));
  const filePath = path.join(dir, "artifact.partial");
  const response = {
    body: new ReadableStream({
      start(controller) {
        controller.enqueue(new Uint8Array(Buffer.from("hello ")));
        controller.enqueue(new Uint8Array(Buffer.from("world")));
        controller.close();
      },
    }),
  };

  let bytes = 0;
  await manager._streamArtifactToDisk({
    response,
    tempPath: filePath,
    append: false,
    signal: null,
    onChunk: (chunkSize) => {
      bytes += chunkSize;
    },
  });

  assert.equal(bytes, 11);
  assert.equal(fs.readFileSync(filePath, "utf8"), "hello world");

  fs.rmSync(dir, { recursive: true, force: true });
});

test("extracts remote total bytes from a 416 content-range response", () => {
  const manager = createManager();
  const response = {
    headers: new Headers({
      "content-range": "bytes */2263",
    }),
  };

  assert.equal(manager._extractContentRangeTotal(response), 2263);
});

test("treats vocabulary-style artifacts as optional", () => {
  const manager = createManager();

  assert.equal(manager._isOptionalArtifactFilename("vocabulary.txt"), true);
  assert.equal(manager._isOptionalArtifactFilename("vocab.json"), true);
  assert.equal(manager._isOptionalArtifactFilename("config.json"), false);
});

test("adds HF token authorization header when configured", () => {
  const manager = createManager();
  manager.hfToken = "test-token";

  const headers = manager._buildRequestHeaders({ Range: "bytes=0-" });

  assert.equal(headers.Authorization, "Bearer test-token");
  assert.equal(headers.Range, "bytes=0-");
});

