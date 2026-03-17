/**
 * Electron Strings - Localization constants for Electron shell UI
 * 
 * Contains hotkey, floating window status, actions, and result metadata strings.
 */
const ELECTRON_STRINGS = {
  hotkey: {
    errors: {
      noAcceleratorProvided: "No accelerator provided",
    },
    notes: {
      toggleMode: "Uses toggle mode: press once to start, press again to stop",
    },
  },
  floating: {
    status: {
      idle: "Ready",
      preparing: "Preparing",
      listening: "Listening",
      transcribing: "Transcribing",
      processing: "Finishing",
      result: "Transcript ready",
      coachResult: "Coach Result",
      error: "Error",
    },
    waitingForSpeech: "Waiting for speech...",
    actions: {
      cancel: "Cancel",
      finish: "Finish",
      close: "Close",
      copyPolished: "Copy Polished",
      copyFinal: "Copy Final",
    },
    resultMeta: {
      transcriptReady: "Transcript ready",
      coachUnavailable: "Coach unavailable",
      livePartialHint: "Live transcript updates during recording.",
      sessionParagraphHint: "Live partials stay temporary until stop.",
      genericError: "Something went wrong.",
    },
    modelPrep: {
      title: "Preparing speech model",
      hint: "The first run can take longer while the model loads into memory.",
    },
  },
};

module.exports = { ELECTRON_STRINGS };

