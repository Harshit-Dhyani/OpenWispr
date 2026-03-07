import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import type { HotkeyStopResponse } from '../types/api';

type FloatingPhase = 'idle' | 'listening' | 'transcribing' | 'finalizing' | 'done' | 'error';
type FloatingStyle = CSSProperties & { WebkitAppRegion?: 'drag' | 'no-drag' };

type FloatingStrings = NonNullable<Window['openwisprFloating']>['strings'];

interface AudioLevelData {
  levels: number[];
  peak: number;
}

interface RecordingStatePayload {
  isRecording: boolean;
  processing?: boolean;
  finished?: boolean;
  sessionId?: string | null;
  mode?: string;
  error?: string | null;
}

interface TranscriptPayload {
  text?: string;
  committedText?: string;
  partialText?: string;
  isPartial?: boolean;
  sessionId?: string | null;
  segmentIndex?: number | null;
  mode?: string;
}

type CoachResultPayload = HotkeyStopResponse;

const WAVEFORM_BAR_COUNT = 36;
const WAVEFORM_HISTORY_SIZE = 6;
const TIMER_INTERVAL_MS = 125;
const AUTOSCROLL_THRESHOLD_PX = 20;
const EMPTY_LEVELS = new Array(WAVEFORM_BAR_COUNT).fill(0);

function sanitizeLevels(levels?: number[]): number[] {
  if (!Array.isArray(levels) || levels.length === 0) {
    return [...EMPTY_LEVELS];
  }

  if (levels.length === WAVEFORM_BAR_COUNT) {
    return levels.map((value) => Math.max(0, Math.min(1, Number(value) || 0)));
  }

  const normalized = new Array(WAVEFORM_BAR_COUNT).fill(0);
  const step = levels.length / WAVEFORM_BAR_COUNT;
  for (let index = 0; index < WAVEFORM_BAR_COUNT; index += 1) {
    const sourceIndex = Math.min(levels.length - 1, Math.floor(index * step));
    normalized[index] = Math.max(0, Math.min(1, Number(levels[sourceIndex]) || 0));
  }
  return normalized;
}

function averageLevelFrames(frames: number[][]): number[] {
  if (frames.length === 0) {
    return [...EMPTY_LEVELS];
  }

  const averaged = new Array(WAVEFORM_BAR_COUNT).fill(0);
  for (const frame of frames) {
    for (let index = 0; index < WAVEFORM_BAR_COUNT; index += 1) {
      averaged[index] += frame[index] || 0;
    }
  }
  return averaged.map((value) => value / frames.length);
}

function formatElapsed(elapsedMs: number): string {
  const totalSeconds = Math.max(0, Math.floor(elapsedMs / 1000));
  const minutes = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, '0');
  const seconds = (totalSeconds % 60).toString().padStart(2, '0');
  return `${minutes}:${seconds}`;
}

export function FloatingWindow() {
  const floatingApi = window.openwisprFloating;
  const strings = useMemo<FloatingStrings>(() => {
    const fallback = {
      status: {
        idle: 'Ready',
        listening: 'Listening',
        transcribing: 'Transcribing',
        processing: 'Finishing',
        result: 'Transcript ready',
        error: 'Error',
      },
      waitingForSpeech: 'Waiting for speech...',
      actions: {
        cancel: 'Cancel',
        finish: 'Finish',
        close: 'Close',
      },
      resultMeta: {
        transcriptReady: 'Transcript ready',
        livePartialHint: 'Live transcript updates during recording.',
        sessionParagraphHint: 'Live partials stay temporary until stop.',
        genericError: 'Something went wrong.',
      },
    };

    return {
      ...fallback,
      ...(floatingApi?.strings ?? {}),
      status: {
        ...fallback.status,
        ...(floatingApi?.strings?.status ?? {}),
      },
      actions: {
        ...fallback.actions,
        ...(floatingApi?.strings?.actions ?? {}),
      },
      resultMeta: {
        ...fallback.resultMeta,
        ...(floatingApi?.strings?.resultMeta ?? {}),
      },
    };
  }, [floatingApi]);

  const [phase, setPhase] = useState<FloatingPhase>('idle');
  const [mode, setMode] = useState('dictation');
  const [committedText, setCommittedText] = useState('');
  const [partialText, setPartialText] = useState('');
  const [finalText, setFinalText] = useState('');
  const [errorText, setErrorText] = useState<string | null>(null);
  const [audioLevels, setAudioLevels] = useState<number[]>([...EMPTY_LEVELS]);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [isPinnedToBottom, setIsPinnedToBottom] = useState(true);

  const phaseRef = useRef<FloatingPhase>('idle');
  const activeSessionIdRef = useRef<string | null>(null);
  const timerStartRef = useRef<number | null>(null);
  const elapsedMsRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const waveformHistoryRef = useRef<number[][]>([]);
  const transcriptScrollRef = useRef<HTMLDivElement | null>(null);
  const devTraceRef = useRef<string[]>([]);

  const traceEvent = useCallback((label: string, payload?: unknown) => {
    if (!import.meta.env.DEV && !floatingApi?.debugEnabled) {
      return;
    }
    if (label === 'audio-visualizer' || label === 'transcription-update') {
      return;
    }
    const entry = `${label}${payload ? ` ${JSON.stringify(payload).slice(0, 180)}` : ''}`;
    devTraceRef.current = [...devTraceRef.current.slice(-19), entry];
    // eslint-disable-next-line no-console
    console.debug('[floating]', entry);
  }, [floatingApi?.debugEnabled]);

  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  const stopTimer = useCallback((reset = false) => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (reset) {
      timerStartRef.current = null;
      elapsedMsRef.current = 0;
      setElapsedMs(0);
    }
  }, []);

  const startTimer = useCallback(() => {
    if (timerRef.current) {
      return;
    }
    if (timerStartRef.current == null) {
      timerStartRef.current = performance.now();
    }
    timerRef.current = setInterval(() => {
      if (timerStartRef.current == null) {
        return;
      }
      const nextElapsed = Math.max(0, performance.now() - timerStartRef.current);
      elapsedMsRef.current = nextElapsed;
      setElapsedMs(nextElapsed);
    }, TIMER_INTERVAL_MS);
  }, []);

  const flattenWaveform = useCallback(() => {
    waveformHistoryRef.current = [];
    setAudioLevels([...EMPTY_LEVELS]);
  }, []);

  const resetTranscriptState = useCallback(() => {
    setCommittedText('');
    setPartialText('');
    setFinalText('');
    setErrorText(null);
  }, []);

  const beginSession = useCallback(
    (nextSessionId?: string | null) => {
      const resolvedSessionId = nextSessionId ?? null;
      if (!resolvedSessionId) {
        return false;
      }
      if (activeSessionIdRef.current === resolvedSessionId) {
        return false;
      }
      activeSessionIdRef.current = resolvedSessionId;
      stopTimer(true);
      resetTranscriptState();
      flattenWaveform();
      setIsPinnedToBottom(true);
      return true;
    },
    [flattenWaveform, resetTranscriptState, stopTimer],
  );

  const clearSession = useCallback(() => {
    activeSessionIdRef.current = null;
    stopTimer(true);
    flattenWaveform();
  }, [flattenWaveform, stopTimer]);

  const handleCoachResult = useCallback(
    (payload: CoachResultPayload | null | undefined) => {
      traceEvent('coach-result', payload);
      if (payload?.session_id) {
        beginSession(payload.session_id);
      }
      const nextText =
        payload?.coach_result?.polished ||
        payload?.paste_text ||
        payload?.postprocessed_text ||
        payload?.aggregated_clean_text ||
        payload?.final_transcription ||
        '';

      setCommittedText(nextText);
      setPartialText('');
      setFinalText(nextText);
      setErrorText(payload?.coach_error || null);
      phaseRef.current = 'done';
      setPhase('done');
      stopTimer(false);
      flattenWaveform();
      setIsPinnedToBottom(true);
    },
    [beginSession, flattenWaveform, stopTimer, traceEvent],
  );

  const handleCoachResultClear = useCallback(() => {
    traceEvent('coach-result-clear');
    resetTranscriptState();
    phaseRef.current = 'idle';
    setPhase('idle');
    clearSession();
  }, [clearSession, resetTranscriptState, traceEvent]);

  const scrollTranscriptToBottom = useCallback(() => {
    const container = transcriptScrollRef.current;
    if (!container) {
      return;
    }
    container.scrollTop = container.scrollHeight;
  }, []);

  useEffect(() => {
    if (isPinnedToBottom) {
      scrollTranscriptToBottom();
    }
  }, [committedText, partialText, finalText, phase, isPinnedToBottom, scrollTranscriptToBottom]);

  const handleTranscriptScroll = useCallback(() => {
    const container = transcriptScrollRef.current;
    if (!container) {
      return;
    }

    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    setIsPinnedToBottom(distanceFromBottom <= AUTOSCROLL_THRESHOLD_PX);
  }, []);

  const handleRecordingState = useCallback(
    (state: RecordingStatePayload) => {
      traceEvent('recording-state', state);
      const nextMode = state.mode || mode || 'dictation';
      setMode(nextMode);
      const nextSessionId = state.sessionId ?? null;

      if (state.error) {
        if (nextSessionId) {
          beginSession(nextSessionId);
        }
        setErrorText(state.error);
        phaseRef.current = 'error';
        setPhase('error');
        stopTimer(false);
        flattenWaveform();
        return;
      }

      if (state.isRecording) {
        beginSession(nextSessionId);
        phaseRef.current = phaseRef.current === 'transcribing' ? 'transcribing' : 'listening';
        setPhase((current) => (current === 'transcribing' ? 'transcribing' : 'listening'));
        startTimer();
        return;
      }

      if (state.processing) {
        phaseRef.current = 'finalizing';
        setPhase('finalizing');
        flattenWaveform();
        return;
      }

      if (state.finished) {
        phaseRef.current = 'done';
        setPhase('done');
        stopTimer(false);
        flattenWaveform();
        return;
      }

      if (phaseRef.current === 'done' || phaseRef.current === 'error') {
        traceEvent('recording-state-preserved-result', {
          phase: phaseRef.current,
          sessionId: activeSessionIdRef.current,
          incomingSessionId: nextSessionId,
        });
        return;
      }

      phaseRef.current = 'idle';
      setPhase('idle');
      clearSession();
    },
    [beginSession, clearSession, flattenWaveform, mode, startTimer, stopTimer, traceEvent],
  );

  const handleTranscription = useCallback(
    (incoming: TranscriptPayload | string) => {
      traceEvent('transcription-update', incoming);
      const payload: TranscriptPayload =
        typeof incoming === 'string' ? { text: incoming } : incoming || {};

      if (payload.mode) {
        setMode(payload.mode);
      }
      if (payload.sessionId !== undefined) {
        beginSession(payload.sessionId ?? null);
      }

      const nextText = payload.text || '';
      const nextCommitted = payload.committedText ?? (payload.isPartial ? committedText : nextText);
      const nextPartial = payload.partialText ?? (payload.isPartial ? nextText : '');

      if (payload.isPartial) {
        setPartialText(nextPartial);
        if (nextCommitted) {
          setCommittedText(nextCommitted);
        }
        if (phaseRef.current === 'idle' || phaseRef.current === 'listening') {
          phaseRef.current = 'transcribing';
          setPhase('transcribing');
        }
        if (activeSessionIdRef.current) {
          startTimer();
        }
        return;
      }

      if (nextCommitted) {
        setCommittedText(nextCommitted);
      } else if (nextText) {
        setCommittedText(nextText);
      }
      setPartialText('');

      const resolvedFinal =
        payload.mode === 'session_paragraph' || phaseRef.current === 'finalizing'
          ? nextCommitted || nextText
          : '';
      if (resolvedFinal) {
        setFinalText(resolvedFinal);
      }

      if (phaseRef.current === 'idle' || phaseRef.current === 'listening') {
        phaseRef.current = 'transcribing';
        setPhase('transcribing');
      }
    },
    [beginSession, committedText, startTimer, traceEvent],
  );

  const handleAudioVisualizer = useCallback(
    (data: AudioLevelData) => {
      if (phaseRef.current === 'idle' || phaseRef.current === 'finalizing' || phaseRef.current === 'done' || phaseRef.current === 'error') {
        return;
      }
      const levels = sanitizeLevels(data?.levels);
      waveformHistoryRef.current = [...waveformHistoryRef.current.slice(-(WAVEFORM_HISTORY_SIZE - 1)), levels];
      setAudioLevels(averageLevelFrames(waveformHistoryRef.current));
    },
    [],
  );

  useEffect(() => {
    if (!floatingApi) {
      setErrorText('Floating window IPC unavailable.');
      setPhase('error');
      phaseRef.current = 'error';
      return () => {
        stopTimer(true);
      };
    }

    const cleanupRecording = floatingApi.onRecordingState(handleRecordingState);
    const cleanupTranscription = floatingApi.onTranscription(handleTranscription);
    const cleanupAudio = floatingApi.onAudioVisualizer(handleAudioVisualizer);
    const cleanupCoachResult = floatingApi.onCoachResult?.(handleCoachResult);
    const cleanupCoachResultClear = floatingApi.onCoachResultClear?.(handleCoachResultClear);

    return () => {
      cleanupRecording?.();
      cleanupTranscription?.();
      cleanupAudio?.();
      cleanupCoachResult?.();
      cleanupCoachResultClear?.();
      stopTimer(true);
    };
  }, [
    floatingApi,
    handleAudioVisualizer,
    handleCoachResult,
    handleCoachResultClear,
    handleRecordingState,
    handleTranscription,
    stopTimer,
  ]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const isActive = phase === 'listening' || phase === 'transcribing' || phase === 'finalizing';
      if (event.key === 'Escape') {
        event.preventDefault();
        if (isActive) {
          window.openwisprFloating?.cancelRecording?.();
        } else {
          window.openwisprFloating?.dismissResult?.();
        }
      }

      if (event.key === 'Enter' && (phase === 'listening' || phase === 'transcribing')) {
        event.preventDefault();
        window.openwisprFloating?.finishRecording?.();
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [phase]);

  const statusText = useMemo(() => {
    switch (phase) {
      case 'listening':
        return strings?.status?.listening || 'Listening';
      case 'transcribing':
        return strings?.status?.transcribing || 'Transcribing';
      case 'finalizing':
        return strings?.status?.processing || 'Finishing';
      case 'done':
        return strings?.status?.result || 'Transcript ready';
      case 'error':
        return strings?.status?.error || 'Error';
      default:
        return strings?.status?.idle || 'Ready';
    }
  }, [phase, strings]);

  const statusColor = useMemo(() => {
    switch (phase) {
      case 'listening':
        return '#ef4444';
      case 'transcribing':
        return '#4af626';
      case 'finalizing':
        return '#f59e0b';
      case 'done':
        return '#4af626';
      case 'error':
        return '#ef4444';
      default:
        return 'rgba(139, 155, 180, 0.85)';
    }
  }, [phase]);

  const visibleTranscript = useMemo(() => {
    if (phase === 'done') {
      return finalText || committedText;
    }
    return committedText || partialText;
  }, [committedText, finalText, mode, partialText, phase]);

  const waitingLabel = strings?.waitingForSpeech || 'Waiting for speech...';
  const resultMetaLabel =
    phase === 'done'
      ? strings?.resultMeta?.transcriptReady || 'Transcript ready'
      : mode === 'session_paragraph'
        ? strings?.resultMeta?.sessionParagraphHint || 'Live partials stay temporary until stop.'
        : strings?.resultMeta?.livePartialHint || 'Live transcript updates during recording.';

  const showActiveControls = phase === 'listening' || phase === 'transcribing' || phase === 'finalizing';
  const showClose = phase === 'done' || phase === 'error';

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        minHeight: 0,
        maxHeight: '100%',
        background: 'linear-gradient(145deg, rgba(20, 25, 35, 0.98) 0%, rgba(15, 20, 28, 0.99) 100%)',
        borderRadius: 16,
        border: `1px solid ${phase === 'transcribing' ? 'rgba(74, 246, 38, 0.2)' : 'rgba(255, 255, 255, 0.08)'}`,
        boxShadow:
          phase === 'transcribing'
            ? '0 20px 60px rgba(0, 0, 0, 0.5), 0 0 24px rgba(74, 246, 38, 0.12)'
            : '0 20px 60px rgba(0, 0, 0, 0.5)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        color: 'rgba(255,255,255,0.92)',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      }}
    >
      <div
        style={{
          WebkitAppRegion: 'drag',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          padding: '14px 16px 10px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        } as FloatingStyle}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
          <div
            style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              backgroundColor: statusColor,
              boxShadow: phase === 'listening' || phase === 'transcribing' ? `0 0 12px ${statusColor}` : 'none',
              flexShrink: 0,
            }}
          />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: 0.2 }}>{statusText}</div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)' }}>
              {mode === 'session_paragraph' ? 'Session paragraph mode' : mode}
            </div>
          </div>
        </div>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: 'rgba(255,255,255,0.65)',
            fontVariantNumeric: 'tabular-nums',
            fontFeatureSettings: '"tnum"',
            flexShrink: 0,
          }}
        >
          {formatElapsed(elapsedMs)}
        </div>
      </div>

      <div
        style={{
          padding: '12px 16px 8px',
          borderBottom: '1px solid rgba(255,255,255,0.04)',
          WebkitAppRegion: 'no-drag',
        } as FloatingStyle}
      >
        <div
          aria-label="Audio waveform"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 3,
            height: 52,
          }}
        >
          {audioLevels.map((level, index) => {
            const height = Math.max(4, Math.round(6 + Math.pow(level, 0.72) * 42));
            return (
              <div
                key={index}
                className="floating-waveform-bar"
                style={{
                  width: 5,
                  height,
                  borderRadius: 999,
                  background:
                    level > 0.025
                      ? 'linear-gradient(to top, #4af626, rgba(74, 246, 38, 0.55))'
                      : 'linear-gradient(to top, rgba(139, 155, 180, 0.45), rgba(139, 155, 180, 0.18))',
                  boxShadow: level > 0.025 ? '0 0 8px rgba(74, 246, 38, 0.26)' : 'none',
                  transition: 'height 70ms ease-out',
                }}
              />
            );
          })}
        </div>
      </div>

      <div
        ref={transcriptScrollRef}
        onScroll={handleTranscriptScroll}
        data-testid="floating-transcript-scroll"
        style={{
          WebkitAppRegion: 'no-drag',
          flex: 1,
          minHeight: 90,
          overflowY: 'auto',
          padding: '12px 16px',
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        } as FloatingStyle}
      >
        {phase === 'error' ? (
          <div
            style={{
              border: '1px solid rgba(239, 68, 68, 0.3)',
              background: 'rgba(239, 68, 68, 0.08)',
              borderRadius: 12,
              padding: 12,
              fontSize: 13,
              lineHeight: 1.45,
              color: 'rgba(255,255,255,0.9)',
            }}
          >
            {errorText || strings?.resultMeta?.genericError || 'Something went wrong.'}
          </div>
        ) : visibleTranscript ? (
          <>
            {phase !== 'done' && mode !== 'session_paragraph' && committedText ? (
              <div
                style={{
                  fontSize: 14,
                  lineHeight: 1.55,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  color: 'rgba(255,255,255,0.92)',
                }}
              >
                {committedText}
              </div>
            ) : null}

            {phase !== 'done' && partialText ? (
              <div
                style={{
                  fontSize: 14,
                  lineHeight: 1.55,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  color: 'rgba(255,255,255,0.72)',
                  borderLeft: '2px solid rgba(74, 246, 38, 0.55)',
                  paddingLeft: 10,
                }}
              >
                {partialText}
              </div>
            ) : null}

            {phase === 'done' && (finalText || committedText) ? (
              <div
                style={{
                  fontSize: 14,
                  lineHeight: 1.55,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  color: 'rgba(255,255,255,0.92)',
                }}
              >
                {finalText || committedText}
              </div>
            ) : null}
          </>
        ) : (
          <div
            style={{
              margin: 'auto 0',
              fontSize: 14,
              color: 'rgba(139, 155, 180, 0.72)',
              fontStyle: 'italic',
              textAlign: 'center',
            }}
          >
            {waitingLabel}
          </div>
        )}
      </div>

      <div
        style={{
          WebkitAppRegion: 'no-drag',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          padding: '10px 16px 14px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        } as FloatingStyle}
      >
        <div
          style={{
            fontSize: 11,
            color: 'rgba(255,255,255,0.5)',
            lineHeight: 1.4,
            minWidth: 0,
          }}
        >
          {resultMetaLabel}
        </div>

        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          {showActiveControls ? (
            <>
              <button
                type="button"
                onClick={() => window.openwisprFloating?.cancelRecording?.()}
                style={buttonStyle('secondary')}
              >
                {strings?.actions?.cancel || 'Cancel'}
              </button>
              <button
                type="button"
                onClick={() => window.openwisprFloating?.finishRecording?.()}
                disabled={phase === 'finalizing'}
                style={buttonStyle('primary', phase === 'finalizing')}
              >
                {strings?.actions?.finish || 'Finish'}
              </button>
            </>
          ) : null}

          {showClose ? (
            <button
              type="button"
              onClick={() => window.openwisprFloating?.dismissResult?.()}
              style={buttonStyle('primary')}
            >
              {strings?.actions?.close || 'Close'}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function buttonStyle(variant: 'primary' | 'secondary', disabled = false): FloatingStyle {
  if (variant === 'primary') {
    return {
      WebkitAppRegion: 'no-drag',
      border: '1px solid rgba(74, 246, 38, 0.35)',
      background: disabled ? 'rgba(74, 246, 38, 0.15)' : 'rgba(74, 246, 38, 0.22)',
      color: disabled ? 'rgba(255,255,255,0.45)' : '#f5fff2',
      borderRadius: 10,
      padding: '8px 14px',
      fontSize: 13,
      fontWeight: 700,
      cursor: disabled ? 'not-allowed' : 'pointer',
    };
  }

  return {
    WebkitAppRegion: 'no-drag',
    border: '1px solid rgba(255,255,255,0.1)',
    background: 'rgba(255,255,255,0.06)',
    color: 'rgba(255,255,255,0.88)',
    borderRadius: 10,
    padding: '8px 14px',
    fontSize: 13,
    fontWeight: 700,
    cursor: 'pointer',
  };
}

