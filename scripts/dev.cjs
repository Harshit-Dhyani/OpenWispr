const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..");

function sanitizeCwd(cwd) {
  return typeof cwd === "string" && cwd.startsWith("\\\\?\\") ? cwd.slice(4) : cwd;
}

function resolveChildCwd() {
  return sanitizeCwd(repoRoot);
}

function resolvePnpmLaunch(env = process.env, execPath = process.execPath) {
  if (env.npm_execpath) {
    return {
      command: execPath,
      args: [env.npm_execpath],
    };
  }

  if (process.platform === "win32") {
    const candidates = [
      path.join(env.APPDATA || "", "npm", "node_modules", "pnpm", "bin", "pnpm.cjs"),
      path.join(path.dirname(execPath), "node_modules", "pnpm", "bin", "pnpm.cjs"),
    ];

    for (const candidate of candidates) {
      if (candidate && fs.existsSync(candidate)) {
        return {
          command: execPath,
          args: [candidate],
        };
      }
    }
  }

  return {
    command: "pnpm",
    args: [],
  };
}

function prefixOutput(stream, prefix, chunk) {
  stream.write(prefix + String(chunk).replace(/\n/g, `\n${prefix}`).replace(/\n\[[^\]]+\] $/, "\n"));
}

function runDev() {
  const childCwd = resolveChildCwd();
  const pnpmLaunch = resolvePnpmLaunch();
  const processes = [];
  let shuttingDown = false;

  function start(name, scriptName) {
    const child = spawn(pnpmLaunch.command, [...pnpmLaunch.args, "run", scriptName], {
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

  start("backend", "dev:backend");
  start("electron", "dev:electron");
}

if (require.main === module) {
  runDev();
}

module.exports = {
  prefixOutput,
  repoRoot,
  resolveChildCwd,
  resolvePnpmLaunch,
  runDev,
  sanitizeCwd,
};
