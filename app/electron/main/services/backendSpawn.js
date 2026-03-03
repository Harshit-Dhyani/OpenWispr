// Backend Python process management
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const state = require("../shared/state");

function resolvePythonLaunch() {
  const repoRoot = path.resolve(__dirname, "..", "..", "..", "..");
  const venvPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
  const apiMainPath = path.join(repoRoot, "app", "api_main.py");

  // Verify api_main.py exists for debugging
  if (!fs.existsSync(apiMainPath)) {
    console.error("[backend] Cannot find api_main.py at:", apiMainPath);
    console.error("[backend] repoRoot calculated as:", repoRoot);
  }

  // Prefer venv Python if it exists
  if (process.env.TRANSCRIPTA_PYTHON) {
    console.log(`[backend] Using TRANSCRIPTA_PYTHON: ${process.env.TRANSCRIPTA_PYTHON}`);
    return { command: process.env.TRANSCRIPTA_PYTHON, args: [apiMainPath] };
  }
  if (fs.existsSync(venvPython)) {
    console.log(`[backend] Using venv Python: ${venvPython}`);
    return { command: venvPython, args: [apiMainPath] };
  }
  console.log(`[backend] Falling back to system Python (py -3)`);
  return { command: "py", args: ["-3", apiMainPath] };
}

async function backendAlreadyRunning() {
  try {
    const response = await fetch(`${state.API_ORIGIN}/api/health`);
    state.backendReady = response.ok;
    return response.ok;
  } catch {
    state.backendReady = false;
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
    state.backendReady = true;
    return;
  }
  const repoRoot = path.resolve(__dirname, "..", "..", "..", "..");
  const { command, args } = resolvePythonLaunch();
  const { app } = require("electron");
  const modelsRoot = path.join(app.getPath("userData"), "models");

  // Build PYTHONPATH explicitly for Windows (; separator) or Unix (: separator)
  const pathSeparator = process.platform === "win32" ? ";" : ":";
  const pythonPath = repoRoot + (process.env.PYTHONPATH ? pathSeparator + process.env.PYTHONPATH : "");

  console.log(`[backend] Starting Python backend:`);
  console.log(`[backend]   Command: ${command}`);
  console.log(`[backend]   Args: ${JSON.stringify(args)}`);
  console.log(`[backend]   CWD: ${repoRoot}`);
  console.log(`[backend]   PYTHONPATH: ${pythonPath}`);

  state.backendProcess = spawn(command, args, {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHONPATH: pythonPath,
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
    state.backendReady = false;
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
  state.backendReady = false;
}

module.exports = {
  resolvePythonLaunch,
  backendAlreadyRunning,
  waitForBackendReady,
  startBackend,
  stopBackend,
};
