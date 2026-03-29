/**
 * Floating window controller script
 * Handles recording state, waveform animation, transcript rendering, and IPC with main process.
 */
(function () {
  "use strict";

  const BAR_COUNT = 48;
  const TIMER_INTERVAL_MS = 125;
  const SILENCE_PUSH_INTERVAL_MS = 50;
  const MIN_BAR_HEIGHT = 4;
  const MAX_BAR_HEIGHT = 52;

  const windowRoot = document.getElementById("window");
  const statusText = document.getElementById("statusText");
  const timer = document.getElementById("timer");
  const waveform = document.getElementById("waveform");
  const transcriptScroll = document.getElementById("transcriptScroll");
  const transcriptEmpty = document.getElementById("transcriptEmpty");
  const transcriptCommitted = document.getElementById("transcriptCommitted");
  const transcriptPartial = document.getElementById("transcriptPartial");
  const resultMeta = document.getElementById("resultMeta");
  const cancelBtn = document.getElementById("cancelBtn");
  const finishBtn = document.getElementById("finishBtn");
  const sttModelEl = document.getElementById("sttModel");
  const llmModelEl = document.getElementById("llmModel");

  const floatingStrings = window.openwisprFloating?.strings || {
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
      copyPolished: "Copy polished",
      copyFinal: "Copy final",
    },
    resultMeta: {
      transcriptReady: "Transcript ready",
      coachUnavailable: "Coach unavailable",
      livePartialHint: "Live transcript updates during recording.",
      sessionParagraphHint: "Live partials stay temporary until stop.",
      genericError: "Something went wrong.",
    },
  };

  let recordingState = "idle";
  let currentMode = "dictation";
  let currentSessionId = null;
  let recordingStartPerf = null;
  let timerInterval = null;
  let animationFrameId = null;
  let latestCoachPayload = null;
  let committedText = "";
  let partialText = "";
  let autoScrollEnabled = true;
  let amplitudeHistory = new Array(BAR_COUNT).fill(0);
  let targetHistory = new Array(BAR_COUNT).fill(0);
  let lastAmplitudePushAt = 0;

  let currentSttModel = null;
  let currentLlmProvider = null;
  let currentLlmModel = null;

  function updateModelInfo(sttModel, llmProvider, llmModel) {
    if (sttModel !== undefined && sttModel !== null) {
      currentSttModel = sttModel;
    }
    if (llmProvider !== undefined && llmProvider !== null) {
      currentLlmProvider = llmProvider;
    }
    if (llmModel !== undefined && llmModel !== null) {
      currentLlmModel = llmModel;
    }

    if (sttModelEl) sttModelEl.textContent = currentSttModel || "-";
    if (llmModelEl) {
      const display =
        currentLlmProvider && currentLlmModel
          ? `${currentLlmProvider}: ${currentLlmModel}`
          : currentLlmModel || "-";
      llmModelEl.textContent = display;
    }
  }

  statusText.textContent = floatingStrings.status.idle;
  transcriptEmpty.textContent = floatingStrings.waitingForSpeech;
  cancelBtn.textContent = floatingStrings.actions.cancel;
  finishBtn.textContent = floatingStrings.actions.finish;

  function createBars() {
    waveform.innerHTML = "";
    for (let i = 0; i < BAR_COUNT; i += 1) {
      const bar = document.createElement("div");
      bar.className = "waveform-bar";
      waveform.appendChild(bar);
    }
  }

  function pushAmplitude(level) {
    const safeLevel = Math.max(0, Math.min(1, Number.isFinite(level) ? level : 0));
    targetHistory.shift();
    targetHistory.push(safeLevel);
    lastAmplitudePushAt = performance.now();
  }

  function renderWaveform() {
    const bars = waveform.querySelectorAll(".waveform-bar");
    bars.forEach((bar, index) => {
      const target = targetHistory[index] || 0;
      const current = amplitudeHistory[index] || 0;
      const next = current + (target - current) * 0.4;
      amplitudeHistory[index] = next;
      const height = Math.max(MIN_BAR_HEIGHT, MIN_BAR_HEIGHT + next * (MAX_BAR_HEIGHT - MIN_BAR_HEIGHT));
      bar.style.height = `${height}px`;
    });
  }

  function tickWaveform() {
    const now = performance.now();
    if (recordingState === "listening" && now - lastAmplitudePushAt >= SILENCE_PUSH_INTERVAL_MS) {
      pushAmplitude(0);
    }
    renderWaveform();
    animationFrameId = requestAnimationFrame(tickWaveform);
  }

  function startWaveform() {
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId);
    }
    animationFrameId = requestAnimationFrame(tickWaveform);
  }

  function stopWaveform() {
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    }
  }

  function atBottom() {
    return transcriptScroll.scrollTop + transcriptScroll.clientHeight >= transcriptScroll.scrollHeight - 12;
  }

  function syncAutoScroll() {
    autoScrollEnabled = atBottom();
  }

  function scrollTranscriptToBottom(force = false) {
    if (force || autoScrollEnabled) {
      transcriptScroll.scrollTop = transcriptScroll.scrollHeight;
    }
  }

  function renderTranscript() {
    const hideCommittedDuringSession = currentMode === "session_paragraph" && recordingState !== "result";
    const hasCommitted = !hideCommittedDuringSession && Boolean(committedText.trim());
    const hasPartial = Boolean(partialText.trim());

    transcriptEmpty.hidden = hasCommitted || hasPartial;
    transcriptCommitted.hidden = !hasCommitted;
    transcriptPartial.hidden = !hasPartial;
    transcriptCommitted.textContent = committedText;
    transcriptPartial.textContent = partialText;
    scrollTranscriptToBottom(false);
  }

  function resetTranscript() {
    committedText = "";
    partialText = "";
    autoScrollEnabled = true;
    renderTranscript();
  }

  function formatDuration(elapsedMs) {
    const totalSeconds = Math.max(0, Math.floor(elapsedMs / 1000));
    const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
    const seconds = String(totalSeconds % 60).padStart(2, "0");
    return `${minutes}:${seconds}`;
  }

  function startTimer() {
    recordingStartPerf = performance.now();
    timer.textContent = "00:00";
    if (timerInterval) {
      clearInterval(timerInterval);
    }
    timerInterval = setInterval(() => {
      timer.textContent = formatDuration(performance.now() - recordingStartPerf);
    }, TIMER_INTERVAL_MS);
  }

  function stopTimer(reset = false) {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
    if (reset) {
      recordingStartPerf = null;
      timer.textContent = "00:00";
    }
  }

  function updateUIState() {
    windowRoot.classList.toggle("listening", recordingState === "listening");
    windowRoot.classList.toggle("transcribing", recordingState === "transcribing");
    windowRoot.classList.toggle("processing", recordingState === "processing");
    windowRoot.classList.toggle("result", recordingState === "result");

    if (recordingState === "listening") {
      statusText.textContent = floatingStrings.status.listening;
      cancelBtn.textContent = floatingStrings.actions.cancel;
      finishBtn.textContent = floatingStrings.actions.finish;
    } else if (recordingState === "transcribing") {
      statusText.textContent = floatingStrings.status.transcribing || floatingStrings.status.listening;
      cancelBtn.textContent = floatingStrings.actions.cancel;
      finishBtn.textContent = floatingStrings.actions.finish;
    } else if (recordingState === "processing") {
      statusText.textContent = floatingStrings.status.processing;
      cancelBtn.textContent = floatingStrings.actions.cancel;
      finishBtn.textContent = floatingStrings.actions.finish;
    } else if (recordingState === "result") {
      statusText.textContent = latestCoachPayload?.coach_result
        ? floatingStrings.status.coachResult
        : floatingStrings.status.result;
      cancelBtn.textContent = floatingStrings.actions.close;
      finishBtn.textContent = latestCoachPayload?.coach_result
        ? floatingStrings.actions.copyPolished
        : floatingStrings.actions.copyFinal;
    } else {
      statusText.textContent = floatingStrings.status.idle;
      cancelBtn.textContent = floatingStrings.actions.cancel;
      finishBtn.textContent = floatingStrings.actions.finish;
    }
  }

  async function copyText(value) {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
    } catch {}
  }

  function setRecordingState(nextState) {
    recordingState = nextState;
    if (nextState === "idle") {
      stopTimer(true);
      targetHistory.fill(0);
      amplitudeHistory.fill(0);
    } else if (nextState === "processing" || nextState === "result" || nextState === "error") {
      stopTimer(false);
      targetHistory.fill(0);
    }
    updateUIState();
  }

  function handleCancel() {
    if (recordingState === "result") {
      if (window.openwisprFloating?.dismissResult) {
        window.openwisprFloating.dismissResult();
      }
      return;
    }
    if (window.openwisprFloating?.cancelRecording) {
      window.openwisprFloating.cancelRecording();
    }
  }

  function handleFinish() {
    if (recordingState === "result") {
      void copyText(
        latestCoachPayload?.paste_text ||
          latestCoachPayload?.postprocessed_text ||
          latestCoachPayload?.final_transcription ||
          committedText
      );
      return;
    }
    if (window.openwisprFloating?.finishRecording) {
      window.openwisprFloating.finishRecording();
    }
  }

  function handleAudioLevelData(data) {
    if (!data || (recordingState !== "listening" && recordingState !== "transcribing")) {
      return;
    }
    const amplitude = Math.max(
      Number.isFinite(data.peak) ? data.peak : 0,
      Number.isFinite(data.audio_level) ? data.audio_level : 0
    );
    pushAmplitude(amplitude);
  }

  function handleTranscriptionUpdate(data) {
    const payload = typeof data === "string" ? { text: data, isPartial: true } : (data || {});
    if (payload.mode) {
      currentMode = payload.mode;
    }
    if (payload.sessionId !== undefined) {
      currentSessionId = payload.sessionId || null;
    }
    committedText = (
      payload.committedText ||
      (payload.isPartial === false ? payload.text : committedText) ||
      ""
    ).trim();
    partialText = (payload.partialText || (payload.isPartial !== false ? payload.text : ""))?.trim() || "";
    if (payload.isPartial && partialText && (recordingState === "idle" || recordingState === "listening")) {
      setRecordingState("transcribing");
    }
    renderTranscript();
  }

  transcriptScroll.addEventListener("scroll", syncAutoScroll);
  cancelBtn.addEventListener("click", handleCancel);
  finishBtn.addEventListener("click", handleFinish);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      handleCancel();
      return;
    }

    if (event.key === "Enter" || (event.key === "Enter" && event.ctrlKey)) {
      event.preventDefault();
      handleFinish();
    }
  });

  createBars();
  startWaveform();
  renderTranscript();
  updateUIState();

  if (window.openwisprFloating) {
    window.openwisprFloating.onRecordingState((state) => {
      if (state.mode) {
        currentMode = state.mode;
      }
      if (state.sessionId !== undefined) {
        currentSessionId = state.sessionId || null;
      }
      if (state.error) {
        resultMeta.textContent = state.error || floatingStrings.resultMeta.genericError;
        setRecordingState("error");
        return;
      }
      if (state.isRecording) {
        latestCoachPayload = null;
        resultMeta.textContent = "";
        resetTranscript();
        startTimer();
        setRecordingState("listening");
        return;
      }
      if (state.processing) {
        setRecordingState("processing");
        return;
      }
      if (state.finished) {
        if (currentMode === "session_paragraph" && partialText && !committedText) {
          committedText = partialText;
          partialText = "";
        }
        if (committedText || partialText) {
          resultMeta.textContent = floatingStrings.resultMeta.transcriptReady;
          renderTranscript();
          setRecordingState("result");
        } else {
          setRecordingState("idle");
        }
        return;
      }
      setRecordingState("idle");
    });

    window.openwisprFloating.onModelPreparation((data) => {
      if (data) {
        updateModelInfo(data.sttModel, data.llmProvider, data.llmModel);
      }
    });

    window.openwisprFloating.onTranscription((data) => {
      handleTranscriptionUpdate(data);
    });

    window.openwisprFloating.onAudioVisualizer((data) => {
      handleAudioLevelData(data);
    });

    window.openwisprFloating.onCoachResult((payload) => {
      latestCoachPayload = payload || null;
      committedText =
        payload?.coach_result?.polished ||
        payload?.paste_text ||
        payload?.postprocessed_text ||
        payload?.final_transcription ||
        "";
      partialText = "";
      resultMeta.textContent =
        payload?.coach_result
          ? `${payload.coach_status || "generated"} \u2022 ${payload.coach_result?.tips?.length || 0} tips`
          : floatingStrings.resultMeta.transcriptReady;
      setRecordingState("result");
      autoScrollEnabled = true;
      renderTranscript();
    });

    window.openwisprFloating.onCoachResultClear(() => {
      latestCoachPayload = null;
      resultMeta.textContent = "";
      setRecordingState("idle");
      resetTranscript();
    });
  }
})();
