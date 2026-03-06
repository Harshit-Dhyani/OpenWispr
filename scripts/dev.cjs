const { spawn } = require("child_process");

const processes = [];
let shuttingDown = false;

function start(name, command) {
  const child = spawn(command, {
    shell: true,
    stdio: ["inherit", "pipe", "pipe"],
    windowsHide: false,
    env: process.env,
  });

  const prefix = `[${name}] `;

  child.stdout.on("data", (chunk) => {
    process.stdout.write(prefix + String(chunk).replace(/\n/g, `\n${prefix}`).replace(/\n\[[^\]]+\] $/, "\n"));
  });

  child.stderr.on("data", (chunk) => {
    process.stderr.write(prefix + String(chunk).replace(/\n/g, `\n${prefix}`).replace(/\n\[[^\]]+\] $/, "\n"));
  });

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

start("backend", "pnpm run dev:backend");
start("electron", "pnpm run dev:electron");
