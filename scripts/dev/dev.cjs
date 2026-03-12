const { spawn } = require("child_process");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..", "..");
const nodeExe = process.execPath;

function sanitizeCwd(cwd) {
  return typeof cwd === "string" && cwd.startsWith("\\\\?\\") ? cwd.slice(4) : cwd;
}

function resolveChildCwd() {
  return sanitizeCwd(repoRoot);
}

function resolveDevTargets() {
  return {
    backend: {
      command: nodeExe,
      args: [path.join(repoRoot, "scripts", "dev", "run-backend-dev.cjs")],
    },
    electron: {
      command: nodeExe,
      args: [path.join(repoRoot, "app", "electron", "scripts", "dev.js")],
    },
  };
}

function prefixOutput(stream, prefix, chunk) {
  stream.write(prefix + String(chunk).replace(/\n/g, `\n${prefix}`).replace(/\n\[[^\]]+\] $/, "\n"));
}

function runDev() {
  const childCwd = resolveChildCwd();
  const targets = resolveDevTargets();
  const processes = [];
  let shuttingDown = false;

  function start(name, target) {
    const child = spawn(target.command, target.args, {
      cwd: childCwd,
      stdio: ["inherit", "pipe", "pipe"],
      windowsHide: false,
      env: process.env,
    });

    const prefix = `[${name}] `;

    child.stdout.on("data", (chunk) => prefixOutput(process.stdout, prefix, chunk));
    child.stderr.on("data", (chunk) => prefixOutput(process.stderr, prefix, chunk));

    child.on("exit", (code, signal) => {
      if (shuttingDown) {
        return;
      }
      shuttingDown = true;
      const exitCode = typeof code === "number" ? code : signal ? 1 : 0;
      for (const proc of processes) {
        if (proc !== child && !proc.killed) {
          proc.kill("SIGINT");
        }
      }
      process.exit(exitCode);
    });

    processes.push(child);
    return child;
  }

  function shutdown() {
    if (shuttingDown) {
      return;
    }
    shuttingDown = true;
    for (const child of processes) {
      if (!child.killed) {
        child.kill("SIGINT");
      }
    }
  }

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);

  start("backend", targets.backend);
  start("electron", targets.electron);
}

if (require.main === module) {
  runDev();
}

module.exports = {
  prefixOutput,
  repoRoot,
  resolveChildCwd,
  resolveDevTargets,
  runDev,
  sanitizeCwd,
};
