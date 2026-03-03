// Configuration constants for the Electron main process

const path = require("path");

// API Configuration
const API_ORIGIN = "http://127.0.0.1:8765";

// Default hotkey - Windows-friendly
const DEFAULT_HOTKEY = "CommandOrControl+Shift+T";

// Hotkey debounce to prevent rapid successive fires
const HOTKEY_DEBOUNCE_MS = 500;

// Window configuration
const WINDOW_CONFIG = {
  main: {
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 600,
  },
  floating: {
    width: 420,
    height: 140,
  },
};

// Paths
function getPaths() {
  return {
    repoRoot: path.resolve(__dirname, "..", ".."),
    preload: path.join(__dirname, "preload.js"),
    preloadFloating: path.join(__dirname, "preload-floating.js"),
    floatingHtml: path.join(__dirname, "..", "floating-window.html"),
    venvPython: path.join(path.resolve(__dirname, "..", ".."), ".venv", "Scripts", "python.exe"),
  };
}

module.exports = {
  API_ORIGIN,
  DEFAULT_HOTKEY,
  HOTKEY_DEBOUNCE_MS,
  WINDOW_CONFIG,
  getPaths,
};
