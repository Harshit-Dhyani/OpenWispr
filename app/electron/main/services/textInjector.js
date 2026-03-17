/**
 * Text injection service for typing transcribed text into active applications
 * Tries robotjs first, falls back to node-key-sender, then clipboard-only mode.
 * Exports: initTextInjector, injectText
 * @module textInjector
 */
const { clipboard } = require("electron");
const state = require("../shared/state");

async function initTextInjector() {
  // Try node-key-sender first (more reliable on Windows)
  try {
    const ks = require("node-key-sender");
    state.hasNodeKeySender = true;
    state.textInjector = {
      typeString: async (text) => {
        try {
          await ks.sendText(text);
          return { success: true };
        } catch (error) {
          return { success: false, error: error.message };
        }
      },
      pasteString: async (text) => {
        try {
          clipboard.writeText(text);
          await new Promise(resolve => setTimeout(resolve, 50));
          await ks.sendCombination(['control', 'v']);
          return { success: true, method: "paste" };
        } catch (error) {
          return { success: false, error: error.message };
        }
      }
    };
    if (state.isDebugLoggingEnabled()) {
      console.log("[main] Text injection: using node-key-sender");
    }
    return;
  } catch {
    state.hasNodeKeySender = false;
  }

  // Try robotjs as alternative
  try {
    const robotjs = require("robotjs");
    state.hasRobotjs = true;
    state.textInjector = {
      typeString: (text) => {
        try {
          robotjs.typeString(text);
          return { success: true };
        } catch (error) {
          return { success: false, error: error.message };
        }
      },
      pasteString: async (text) => {
        try {
          clipboard.writeText(text);
          await new Promise(resolve => setTimeout(resolve, 50));
          robotjs.keyToggle("control", "down");
          robotjs.keyTap("v");
          robotjs.keyToggle("control", "up");
          return { success: true, method: "paste" };
        } catch (error) {
          return { success: false, error: error.message };
        }
      }
    };
    if (state.isDebugLoggingEnabled()) {
      console.log("[main] Text injection: using robotjs");
    }
    return;
  } catch {
    state.hasRobotjs = false;
  }

  // Fallback: clipboard-based injection (copy only, no typing)
  if (state.isDebugLoggingEnabled()) {
    console.log("[main] Text injection: using clipboard fallback");
  }
  state.textInjector = {
    typeString: async (text) => {
      try {
        clipboard.writeText(text);
        return {
          success: false,
          error: "Native text injection is unavailable. Transcription was copied to the clipboard.",
          method: "clipboard_only"
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },
    pasteString: async (text) => {
      // Same as typeString for clipboard fallback
      try {
        clipboard.writeText(text);
        return {
          success: false,
          error: "Native paste injection unavailable. Copied to clipboard - press Ctrl+V to paste.",
          method: "clipboard_only"
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    }
  };
}

async function injectText(text, useFastPaste = true) {
  if (!state.textInjector) {
    await initTextInjector();
  }

  if (state.textInjector) {
    // Use fast paste method if available and requested
    if (useFastPaste && state.textInjector.pasteString) {
      return await state.textInjector.pasteString(text);
    }
    return await state.textInjector.typeString(text);
  }

  return { success: false, error: "No text injection method available" };
}

module.exports = {
  initTextInjector,
  injectText,
};
