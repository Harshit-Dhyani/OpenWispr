const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..", "..");
const pathSeparator = process.platform === "win32" ? ";" : ":";
const pythonPath = repoRoot + (process.env.PYTHONPATH ? pathSeparator + process.env.PYTHONPATH : "");
const venvPython =
  process.platform === "win32"
    ? path.join(repoRoot, ".venv", "Scripts", "python.exe")
    : path.join(repoRoot, ".venv", "bin", "python");

// Use port from environment or generate random
const port = process.env.OPENWISPR_PORT || String(Math.floor(10000 + Math.random() * 50000));

function resolvePythonLaunch() {
  if (process.env.OPENWISPR_PYTHON) {
    return {
      command: process.env.OPENWISPR_PYTHON,
      args: ["-m", "uvicorn", "app.api.server:app", "--port", port],
    };
  }

  if (fs.existsSync(venvPython)) {
    return {
      command: venvPython,
      args: ["-m", "uvicorn", "app.api.server:app", "--port", port],
    };
  }

  if (process.platform === "win32") {
    return {
      command: "py",
      args: ["-3", "-m", "uvicorn", "app.api.server:app", "--port", port],
    };
  }

  return {
    command: "python3",
    args: ["-m", "uvicorn", "app.api.server:app", "--port", port],
  };
}

const { command, args } = resolvePythonLaunch();

console.log(`Backend starting on port ${port}`);

const child = spawn(command, args, {
  cwd: repoRoot,
  env: {
    ...process.env,
    PYTHONPATH: pythonPath,
    OPENWISPR_DEV_EXTERNAL_BACKEND: "1",
    OPENWISPR_PORT: port,
  },
  stdio: "inherit",
  windowsHide: false,
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});
