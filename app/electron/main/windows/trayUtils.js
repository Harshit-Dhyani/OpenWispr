/**
 * Tray utility functions for OpenWispr
 * Creates tray icons (from file or generated circles) and updates icon/tooltip.
 * Separated from tray.js to avoid circular dependencies. Exports: createTrayIcons,
 * createCircleIcon, updateTrayIcon, updateTrayTooltip
 * @module trayUtils
 */
const { nativeImage } = require("electron");
const state = require("../shared/state");
const { getTrayIconPath } = require("../shared/iconPaths");

function createTrayIcons() {
  const trayIconPath = getTrayIconPath();
  if (trayIconPath) {
    const image = nativeImage.createFromPath(trayIconPath);
    if (!image.isEmpty()) {
      const targetSize = process.platform === 'win32' ? 20 : 18;
      const resized = image.resize({ width: targetSize, height: targetSize, quality: 'best' });
      state.trayIconIdle = resized;
      state.trayIconRecording = resized;
      return;
    }
  }

  const size = 16;
  state.trayIconIdle = createCircleIcon(size, "#10b981");
  state.trayIconRecording = createCircleIcon(size, "#ef4444");
}

function createCircleIcon(size, color) {
  const canvas = Buffer.alloc(size * size * 4);

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const idx = (y * size + x) * 4;
      const dx = x - size / 2 + 0.5;
      const dy = y - size / 2 + 0.5;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist <= size / 2 - 1) {
        const r = parseInt(color.slice(1, 3), 16);
        const g = parseInt(color.slice(3, 5), 16);
        const b = parseInt(color.slice(5, 7), 16);

        canvas[idx] = r;
        canvas[idx + 1] = g;
        canvas[idx + 2] = b;
        canvas[idx + 3] = 255;
      } else {
        canvas[idx] = 0;
        canvas[idx + 1] = 0;
        canvas[idx + 2] = 0;
        canvas[idx + 3] = 0;
      }
    }
  }

  return nativeImage.createFromBitmap(canvas, { width: size, height: size });
}

function updateTrayIcon() {
  if (!state.tray) return;

  const icon = state.isRecording ? state.trayIconRecording : state.trayIconIdle;
  if (icon) {
    state.tray.setImage(icon);
  }
}

function updateTrayTooltip() {
  if (state.tray) {
    const status = state.isRecording ? "Recording" : (state.hotkeyEnabled ? "Ready" : "Disabled");
    const hotkey = state.currentHotkeyAccelerator || state.DEFAULT_HOTKEY;
    const audioStatus = state.audioFeedbackEnabled ? "On" : "Off";
    state.tray.setToolTip(`${state.APP_NAME} - ${status}\nHotkey: ${hotkey}\nAudio: ${audioStatus}`);
  }
}

module.exports = {
  createTrayIcons,
  createCircleIcon,
  updateTrayIcon,
  updateTrayTooltip,
};
