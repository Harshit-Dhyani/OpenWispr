// Backend Python process management
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const { app } = require("electron");
const state = require("../shared/state");

let restartTimer = null;
let suppressRestart = false;
let restartAttempts = 0;
const MAX_BACKEND_RESTARTS = 3;

function resolveBackendLayout() {
  const devRepoRoot = path.resolve(__dirname, "..", "..", "..", "..");
  const packagedBackendRoot = path.join(process.resourcesPath, "backend");
  const packagedAppRoot = path.join(packagedBackendRoot, "app");
  const devAppRoot = path.join(devRepoRoot, "app");
  const isPackagedBackend = app.isPackaged && fs.existsSync(path.join(packagedAppRoot, "api_main.py"));

  if (isPackagedBackend) {
    return {
      mode: "packaged",
      projectRoot: packagedBackendRoot,
      appRoot: packagedAppRoot,
      apiMainPath: path.join(packagedAppRoot, "api_main.py"),
      bundledPython: path.join(packagedBackendRoot, ".venv", "Scripts", "python.exe"),
    };
  }

  return {
    mode: "dev",
    projectRoot: devRepoRoot,
    appRoot: devAppRoot,
    apiMainPath: path.join(devAppRoot, "api_main.py"),
    bundledPython: path.join(devRepoRoot, ".venv", "Scripts", "python.exe"),
  };
}

function resolvePythonLaunch() {
  const layout = resolveBackendLayout();
  const fallbackRepoRoot = path.resolve(process.resourcesPath, "..", "..", "..", "..", "..");
  const fallbackVenvPython = path.join(fallbackRepoRoot, ".venv", "Scripts", "python.exe");

  if (process.env.OPENWISPR_PYTHON) {
    if (state.isDebugLoggingEnabled()) {
      console.log(`[backend] Using OPENWISPR_PYTHON: ${process.env.OPENWISPR_PYTHON}`);
    }
    return { command: process.env.OPENWISPR_PYTHON, args: [layout.apiMainPath], layout };
  }

  if (fs.existsSync(layout.bundledPython)) {
    if (state.isDebugLoggingEnabled()) {
      console.log(`[backend] Using bundled Python: ${layout.bundledPython}`);
    }
    return { command: layout.bundledPython, args: [layout.apiMainPath], layout };
  }

  if (layout.mode === "packaged" && fs.existsSync(fallbackVenvPython)) {
    if (state.isDebugLoggingEnabled()) {
      console.log(`[backend] Using fallback repo venv Python: ${fallbackVenvPython}`);
    }
    return { command: fallbackVenvPython, args: [layout.apiMainPath], layout };
  }

  if (!fs.existsSync(layout.apiMainPath)) {
    console.error("[backend] Cannot find api_main.py at:", layout.apiMainPath);
    console.error("[backend] Backend layout:", layout);
  }

  if (state.isDebugLoggingEnabled()) {
    console.log("[backend] Falling back to system Python (py -3)");
  }
  return { command: "py", args: ["-3", layout.apiMainPath], layout };
}

async function backendAlreadyRunning() {
  try {
    const response = await fetch(`${state.API_ORIGIN}/api/health`);
    state.backendReady = response.ok;
    if (response.ok) {
      restartAttempts = 0;
    }
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
  console.log("[backend] OPENWISPR_DEV_EXTERNAL_BACKEND:", process.env.OPENWISPR_DEV_EXTERNAL_BACKEND);
  if (state.backendProcess) {
    return state.backendReady;
  }
  if (process.env.OPENWISPR_DEV_EXTERNAL_BACKEND === "1") {
    console.log("[backend] External backend mode enabled, waiting for backend...");
    if (state.isDebugLoggingEnabled()) {
      console.log("[backend] External backend mode enabled, waiting for backend...");
    }
    state.backendReady = await waitForBackendReady(60000);
    if (state.backendReady) {
      restartAttempts = 0;
    }
    return state.backendReady;
  }
  if (await backendAlreadyRunning()) {
    state.backendReady = true;
    restartAttempts = 0;
    return true;
  }

  suppressRestart = false;
  const { command, args, layout } = resolvePythonLaunch();
  const modelsRoot = path.join(app.getPath("userData"), "models");
  const pathSeparator = process.platform === "win32" ? ";" : ":";
  const pythonPath = layout.projectRoot + (process.env.PYTHONPATH ? pathSeparator + process.env.PYTHONPATH : "");

  if (state.isDebugLoggingEnabled()) {
    console.log("[backend] Starting Python backend:");
    console.log(`[backend]   Command: ${command}`);
    console.log(`[backend]   Args: ${JSON.stringify(args)}`);
    console.log(`[backend]   Mode: ${layout.mode}`);
    console.log(`[backend]   CWD: ${layout.projectRoot}`);
    console.log(`[backend]   PYTHONPATH: ${pythonPath}`);
  }

  const backendEnv = {
    ...process.env,
    PYTHONPATH: pythonPath,
    OPENWISPR_DOWNLOAD_ROOT: modelsRoot,
  };

  if (process.env.OPENWISPR_LOG_LEVEL) {
    backendEnv.OPENWISPR_LOG_LEVEL = process.env.OPENWISPR_LOG_LEVEL;
  }

  state.backendProcess = spawn(command, args, {
    cwd: layout.projectRoot,
    env: backendEnv,
    stdio: "pipe",
    windowsHide: true,
  });

  state.backendProcess.stdout.on("data", (chunk) => {
    process.stdout.write(`[backend] ${chunk}`);
  });

  state.backendProcess.stderr.on("data", (chunk) => {
    process.stderr.write(`[backend] ${chunk}`);
  });

  state.backendProcess.on("error", (error) => {
    console.error("[backend] Spawn failed", error);
  });

  state.backendProcess.on("exit", (code, signal) => {
    console.error(`[backend] Process exited code=${code} signal=${signal}`);
    state.backendProcess = null;
    state.backendReady = false;
    if (state.mainWindow && !state.mainWindow.isDestroyed()) {
      state.mainWindow.webContents.send("backend-exit");
    }
    if (!suppressRestart && restartAttempts < MAX_BACKEND_RESTARTS) {
      restartAttempts += 1;
      clearTimeout(restartTimer);
      restartTimer = setTimeout(async () => {
        try {
          await startBackend();
          await waitForBackendReady(10000);
        } catch (error) {
          console.error("[backend] Restart attempt failed", error);
        }
      }, 1000);
    }
  });

  // Wait for backend to be ready and return result
  return waitForBackendReady(60000);
}

function stopBackend() {
  suppressRestart = true;
  clearTimeout(restartTimer);
  if (state.backendProcess) {
    state.backendProcess.kill();
    state.backendProcess = null;
  }
  state.backendReady = false;
}

module.exports = {
  resolveBackendLayout,
  resolvePythonLaunch,
  backendAlreadyRunning,
  waitForBackendReady,
  startBackend,
  stopBackend,
};
