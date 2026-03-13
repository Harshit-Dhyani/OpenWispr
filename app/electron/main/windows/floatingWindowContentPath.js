const fs = require("fs");
const path = require("path");

function resolveFloatingWindowContentPath(options = {}) {
  const existsSync = options.existsSync || fs.existsSync;
  const baseDir = options.baseDir || __dirname;

  const preferredPath = path.join(baseDir, "..", "..", "renderer", "dist", "floating.html");
  if (existsSync(preferredPath)) {
    return preferredPath;
  }

  return path.join(baseDir, "..", "..", "floating-window.html");
}

module.exports = {
  resolveFloatingWindowContentPath,
};
