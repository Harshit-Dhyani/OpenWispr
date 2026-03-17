/**
 * Floating window state management for OpenWispr
 * Resolves window bounds, positions, HTML path, and provides clamping utilities
 * for keeping the floating window within screen work areas. Exports:
 * DEFAULT_FLOATING_WINDOW_SIZE, clampFloatingWindowPosition, resolvePresetFloatingWindowPosition,
 * resolveFloatingWindowBounds, resolveFloatingWindowHtmlPath
 * @module floatingWindowState
 */
const path = require("path");
const fs = require("fs");

const DEFAULT_FLOATING_WINDOW_SIZE = Object.freeze({
  width: 460,
  height: 300,
});

function resolveFloatingWindowHtmlPath(exists = fs.existsSync, baseDir = __dirname) {
  const builtPath = path.join(baseDir, "..", "..", "renderer", "dist", "floating.html");
  if (exists(builtPath)) {
    return builtPath;
  }

  return path.join(baseDir, "..", "..", "floating-window.html");
}

function clampFloatingWindowPosition(position, workArea, size = DEFAULT_FLOATING_WINDOW_SIZE) {
  const safeWidth = Number.isFinite(size?.width) ? size.width : DEFAULT_FLOATING_WINDOW_SIZE.width;
  const safeHeight = Number.isFinite(size?.height) ? size.height : DEFAULT_FLOATING_WINDOW_SIZE.height;
  const minX = workArea.x;
  const minY = workArea.y;
  const maxX = workArea.x + Math.max(workArea.width - safeWidth, 0);
  const maxY = workArea.y + Math.max(workArea.height - safeHeight, 0);

  return {
    x: Math.min(Math.max(Math.round(position.x), minX), maxX),
    y: Math.min(Math.max(Math.round(position.y), minY), maxY),
  };
}

function resolvePresetFloatingWindowPosition(preset, workArea, size = DEFAULT_FLOATING_WINDOW_SIZE) {
  const width = Number.isFinite(size?.width) ? size.width : DEFAULT_FLOATING_WINDOW_SIZE.width;
  const height = Number.isFinite(size?.height) ? size.height : DEFAULT_FLOATING_WINDOW_SIZE.height;
  const horizontalPadding = 24;
  const verticalPadding = 28;

  const positions = {
    "top-left": {
      x: workArea.x + horizontalPadding,
      y: workArea.y + verticalPadding,
    },
    "top-right": {
      x: workArea.x + workArea.width - width - horizontalPadding,
      y: workArea.y + verticalPadding,
    },
    "bottom-left": {
      x: workArea.x + horizontalPadding,
      y: workArea.y + workArea.height - height - verticalPadding,
    },
    "center": {
      x: workArea.x + Math.round((workArea.width - width) / 2),
      y: workArea.y + Math.round((workArea.height - height) / 2),
    },
    "bottom-right": {
      x: workArea.x + workArea.width - width - horizontalPadding,
      y: workArea.y + workArea.height - height - verticalPadding,
    },
  };

  return clampFloatingWindowPosition(
    positions[preset] || positions["bottom-right"],
    workArea,
    size,
  );
}

function resolveFloatingWindowBounds({
  savedPosition,
  preset = "bottom-right",
  workArea,
  size = DEFAULT_FLOATING_WINDOW_SIZE,
}) {
  const width = Number.isFinite(size?.width) ? size.width : DEFAULT_FLOATING_WINDOW_SIZE.width;
  const height = Number.isFinite(size?.height) ? size.height : DEFAULT_FLOATING_WINDOW_SIZE.height;

  const resolvedPosition =
    savedPosition &&
    Number.isFinite(savedPosition.x) &&
    Number.isFinite(savedPosition.y)
      ? clampFloatingWindowPosition(savedPosition, workArea, { width, height })
      : resolvePresetFloatingWindowPosition(preset, workArea, { width, height });

  return {
    width,
    height,
    x: resolvedPosition.x,
    y: resolvedPosition.y,
  };
}

module.exports = {
  DEFAULT_FLOATING_WINDOW_SIZE,
  clampFloatingWindowPosition,
  resolvePresetFloatingWindowPosition,
  resolveFloatingWindowBounds,
  resolveFloatingWindowHtmlPath,
};
