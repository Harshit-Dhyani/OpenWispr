/**
 * Audio feedback service for transcription sounds
 * Plays platform-specific sounds on recording start/stop. Windows uses renderer events,
 * macOS uses system sounds. Exports: playStartSound, playStopSound
 * @module audioFeedbackService
 */
const state = require("../shared/state");

function playStartSound() {
  if (!state.audioFeedbackEnabled) return;

  if (process.platform === "win32") {
    try {
      if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
        state.floatingWindow.webContents.send("hotkey-event", { type: "start" });
      }
    } catch (error) {
      console.log("[audio-feedback] Could not play start sound:", error.message);
    }
  } else if (process.platform === "darwin") {
    try {
      const { exec } = require("child_process");
      exec("afplay /System/Library/Sounds/Glass.aiff", { timeout: 1000 }, () => {});
    } catch (error) {
      console.error("[audio-feedback] Error playing start sound:", error);
    }
  }
}

function playStopSound() {
  if (!state.audioFeedbackEnabled) return;

  if (process.platform === "win32") {
    try {
      if (state.floatingWindow && !state.floatingWindow.isDestroyed()) {
        state.floatingWindow.webContents.send("hotkey-event", { type: "stop" });
      }
    } catch (error) {
      console.log("[audio-feedback] Could not play stop sound:", error.message);
    }
  } else if (process.platform === "darwin") {
    try {
      const { exec } = require("child_process");
      exec("afplay /System/Library/Sounds/Pop.aiff", { timeout: 1000 }, () => {});
    } catch (error) {
      console.error("[audio-feedback] Error playing stop sound:", error);
    }
  }
}

module.exports = {
  playStartSound,
  playStopSound,
};
