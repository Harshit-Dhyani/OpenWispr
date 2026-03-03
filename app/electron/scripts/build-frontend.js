const { spawnSync } = require("child_process");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..");
const frontendRoot = path.join(repoRoot, "frontend");
const nodeExe = process.execPath;

function run(scriptPath, args = []) {
  const result = spawnSync(nodeExe, [scriptPath, ...args], {
    cwd: frontendRoot,
    stdio: "inherit",
    windowsHide: false,
  });

  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

run(path.join(frontendRoot, "node_modules", "typescript", "bin", "tsc"));
run(path.join(frontendRoot, "node_modules", "vite", "bin", "vite.js"), ["build"]);
