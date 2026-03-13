const { spawn, spawnSync } = require("child_process");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..");
const nodeExe = process.execPath;

const build = spawnSync(nodeExe, [path.join(repoRoot, "scripts", "build-frontend.js")], {
  cwd: repoRoot,
  stdio: "inherit",
  windowsHide: false,
});

if (build.status !== 0) {
  process.exit(build.status ?? 1);
}

const child = spawn(nodeExe, [path.join(repoRoot, "node_modules", "electron", "cli.js"), "."], {
  cwd: repoRoot,
  stdio: "inherit",
  windowsHide: false,
});

child.on("exit", (code) => {
  process.exit(code ?? 0);
});
