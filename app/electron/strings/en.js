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
  },
};

module.exports = { ELECTRON_STRINGS };

