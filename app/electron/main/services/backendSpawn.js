// Backend Python process management
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const state = require("../shared/state");

function resolvePythonLaunch() {
  const repoRoot = path.resolve(__dirname, "..", "..", "..");
  const venvPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
  if (process.env.TRANSCRIPTA_PYTHON) {
    return { command: process.env.TRANSCRIPTA_PYTHON, args: ["-m", "app.api_main"] };
  }
  if (fs.existsSync(venvPython)) {
    return { command: venvPython, args: ["-m", "app.api_main"] };
  }
  return { command: "py", args: ["-3", "-m", "app.api_main"] };
}

async function backendAlreadyRunning() {
  try {
    const response = await fetch(`${state.API_ORIGIN}/api/health`);
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForBackendReady(timeoutMs = 20000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (await backendAlreadyRunning()) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return false;
}

async function startBackend() {
  if (state.backendProcess) {
    return;
  }
  if (await backendAlreadyRunning()) {
    return;
  }
  const repoRoot = path.resolve(__dirname, "..", "..", "..");
  const { command, args } = resolvePythonLaunch();
  const { app } = require("electron");
  const modelsRoot = path.join(app.getPath("userData"), "models");

  state.backendProcess = spawn(command, args, {
    cwd: repoRoot,
    env: {
      ...process.env,
      TRANSCRIPTA_DOWNLOAD_ROOT: modelsRoot,
    },
    stdio: "pipe",
    windowsHide: true
  });

  state.backendProcess.stdout.on("data", (chunk) => {
    process.stdout.write(`[backend] ${chunk}`);
  });

  state.backendProcess.stderr.on("data", (chunk) => {
    process.stderr.write(`[backend] ${chunk}`);
  });

  state.backendProcess.on("exit", () => {
    state.backendProcess = null;
    if (state.mainWindow && !state.mainWindow.isDestroyed()) {
      state.mainWindow.webContents.send("backend-exit");
    }
  });
}

function stopBackend() {
  if (state.backendProcess) {
    state.backendProcess.kill();
    state.backendProcess = null;
  }
}

module.exports = {
  resolvePythonLaunch,
  backendAlreadyRunning,
  waitForBackendReady,
  startBackend,
  stopBackend,
};
