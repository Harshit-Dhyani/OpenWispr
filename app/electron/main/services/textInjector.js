// Text injection service for typing transcribed text
const { clipboard } = require("electron");
const state = require("../shared/state");

async function initTextInjector() {
  // Try to load native modules for text injection
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
      }
    };
    if (state.isDebugLoggingEnabled()) {
      console.log("[main] Text injection: using robotjs");
    }
    return;
  } catch {
    state.hasRobotjs = false;
  }

  try {
    const nodeKeySender = require("node-key-sender");
    state.hasNodeKeySender = true;
    state.textInjector = {
      typeString: (text) => {
        try {
          nodeKeySender.sendText(text);
          return { success: true };
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

  // Fallback: clipboard-based injection
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
    }
  };
}

async function injectText(text) {
  if (!state.textInjector) {
    await initTextInjector();
  }

  if (state.textInjector) {
    return await state.textInjector.typeString(text);
  }

  return { success: false, error: "No text injection method available" };
}

module.exports = {
  initTextInjector,
  injectText,
};
