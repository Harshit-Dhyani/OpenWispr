/**
 * Icon path resolution utilities for OpenWispr
 * Resolves window and tray icon paths from build directory. Exports: getWindowIconPath,
 * getTrayIconPath
 * @module iconPaths
 */

const path = require('path');
const fs = require('fs');

function resolveRepoRoot() {
  return path.resolve(__dirname, '..', '..', '..', '..');
}

function existingPath(candidate) {
  return fs.existsSync(candidate) ? candidate : null;
}

function getWindowIconPath() {
  return existingPath(path.join(resolveRepoRoot(), 'build', 'icon.ico'));
}

function getTrayIconPath() {
  const repoRoot = resolveRepoRoot();
  return (
    existingPath(path.join(repoRoot, 'build', 'logo.png')) ||
    existingPath(path.join(repoRoot, 'build', 'icons', '512x512.png')) ||
    existingPath(path.join(repoRoot, 'build', 'icons', '256x256.png')) ||
    existingPath(path.join(repoRoot, 'build', 'icons', '32x32.png')) ||
    null
  );
}

module.exports = {
  getWindowIconPath,
  getTrayIconPath,
};
