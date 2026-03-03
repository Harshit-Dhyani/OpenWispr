import { useEffect, useRef, useState, useCallback } from 'react';

type RecordingState = 'idle' | 'listening' | 'processing';

interface AudioLevelData {
  levels: number[];
  peak: number;
}

export function FloatingWindow() {
  const [recordingState, setRecordingState] = useState<RecordingState>('idle');
  const [transcriptionText, setTranscriptionText] = useState('');
  const [audioLevels, setAudioLevels] = useState<number[]>(new Array(36).fill(0));
  const [timer, setTimer] = useState('00:00');

  const animationRef = useRef<number | null>(null);
  const audioDataRef = useRef<AudioLevelData>({ levels: new Array(36).fill(0), peak: 0 });
  const recordingStartTime = useRef<number | null>(null);
  const timerIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const targetLevelsRef = useRef<number[]>(new Array(36).fill(0));
  const currentLevelsRef = useRef<number[]>(new Array(36).fill(0));
  const recordingStateRef = useRef(recordingState);

  // Keep ref in sync with state to avoid dependency issues
  useEffect(() => {
    recordingStateRef.current = recordingState;
  }, [recordingState]);

  // Smooth animation for waveform bars - memoized to prevent excessive re-runs
  const animateWaveform = useCallback(() => {
    const SMOOTHING_FACTOR = 0.25;

    // Interpolate towards target levels
    const newLevels = currentLevelsRef.current.map((current, i) => {
      const target = targetLevelsRef.current[i] || 0;
      return current + (target - current) * SMOOTHING_FACTOR;
    });

    currentLevelsRef.current = newLevels;
    setAudioLevels([...newLevels]);

    animationRef.current = requestAnimationFrame(animateWaveform);
  }, []);

  // Update timer display
  const updateTimer = useCallback(() => {
    if (!recordingStartTime.current) {
      setTimer('00:00');
      return;
    }
    const elapsed = Math.floor((Date.now() - recordingStartTime.current) / 1000);
    const minutes = Math.floor(elapsed / 60).toString().padStart(2, '0');
    const seconds = (elapsed % 60).toString().padStart(2, '0');
    setTimer(`${minutes}:${seconds}`);
  }, []);

  // Simulate audio data when no real data is coming
  // Uses ref to avoid recreating callback on state changes
  const simulateAudioData = useCallback(() => {
    const currentState = recordingStateRef.current;

    if (currentState === 'listening') {
      const time = Date.now() / 150;
      const voiceActivity = Math.sin(time * 0.5) * 0.5 + 0.5;

      const simulated = Array.from({ length: 36 }, (_, i) => {
        const freqResponse = Math.exp(-Math.pow((i - 18) / 8, 2) * 0.5);
        const wave = Math.sin(time + i * 0.4) * 0.5 + 0.5;
        const noise = Math.random() * 0.3;

        let level = (wave * 0.4 + noise * 0.6) * freqResponse * voiceActivity;

        // Add occasional peaks
        if (Math.random() > 0.95) {
          level *= 1.5;
        }

        return Math.max(0, Math.min(1, level * 1.2));
      });

      targetLevelsRef.current = simulated;
    } else if (currentState === 'processing') {
      // Gentle processing animation
      const time = Date.now() / 300;
      targetLevelsRef.current = Array.from({ length: 36 }, (_, i) =>
        0.1 + Math.sin(time + i * 0.2) * 0.05
      );
    } else {
      // Idle state - very low levels
      targetLevelsRef.current = new Array(36).fill(0.05);
    }
  }, []); // No dependencies - uses ref instead

  // Start animation loop once on mount
  useEffect(() => {
    animationRef.current = requestAnimationFrame(animateWaveform);

    // Start simulation interval - stable reference prevents excessive re-runs
    const simulationInterval = setInterval(() => {
      simulateAudioData();
    }, 50);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
      clearInterval(simulationInterval);
    };
  }, []); // Empty deps - animation runs continuously, uses refs for state

  useEffect(() => {
    // Handle IPC events
    const handleAudioLevel = (data: { levels?: number[]; peak?: number }) => {
      if (data && data.levels) {
        targetLevelsRef.current = data.levels.map(v => Math.min(1, Math.max(0, v)));
        audioDataRef.current = {
          levels: data.levels,
          peak: data.peak || Math.max(...data.levels)
        };
      }
    };

    const handleTranscription = (data: { text?: string; isPartial?: boolean } | string) => {
      const text = typeof data === 'string' ? data : data.text || '';
      setTranscriptionText(text);
    };

    const handleStateChange = (state: { isRecording: boolean; processing?: boolean; finished?: boolean }) => {
      if (state.isRecording) {
        setRecordingState('listening');
        recordingStartTime.current = Date.now();

        // Start timer
        if (timerIntervalRef.current) {
          clearInterval(timerIntervalRef.current);
        }
        timerIntervalRef.current = setInterval(updateTimer, 1000);
        updateTimer();
      } else if (state.processing) {
        setRecordingState('processing');
        if (timerIntervalRef.current) {
          clearInterval(timerIntervalRef.current);
          timerIntervalRef.current = null;
        }
      } else if (state.finished) {
        setRecordingState('idle');
        recordingStartTime.current = null;
        setTimer('00:00');
        if (timerIntervalRef.current) {
          clearInterval(timerIntervalRef.current);
          timerIntervalRef.current = null;
        }
      }
    };

    // Register IPC handlers if available
    if (window.transcriptaFloating) {
      const cleanupRecording = window.transcriptaFloating.onRecordingState(handleStateChange);
      const cleanupTranscription = window.transcriptaFloating.onTranscription(handleTranscription);
      const cleanupAudio = window.transcriptaFloating.onAudioVisualizer(handleAudioLevel);

      return () => {
        cleanupRecording?.();
        cleanupTranscription?.();
        cleanupAudio?.();
        if (timerIntervalRef.current) {
          clearInterval(timerIntervalRef.current);
        }
      };
    }

    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    };
  }, [updateTimer]);

  const getStatusText = () => {
    switch (recordingState) {
      case 'listening':
        return 'Listening...';
      case 'processing':
        return (
          <>
            Processing
            <span className="processing-dots">
              <span className="processing-dot" />
              <span className="processing-dot" />
              <span className="processing-dot" />
            </span>
          </>
        );
      default:
        return 'Ready';
    }
  };

  const getStatusColor = () => {
    switch (recordingState) {
      case 'listening':
        return '#ef4444';
      case 'processing':
        return '#f59e0b';
      default:
        return '#4af626';
    }
  };

  const getBarClass = (level: number) => {
    if (recordingState === 'processing') {
      return 'waveform-bar processing';
    }
    if (level < 0.05) {
      return 'waveform-bar inactive';
    }
    return 'waveform-bar';
  };

  return (
    <div
      className={`window-container ${recordingState === 'listening' ? 'recording' : ''}`}
      style={{
        width: '420px',
        height: '140px',
        background: 'linear-gradient(145deg, rgba(20, 25, 35, 0.98) 0%, rgba(15, 20, 28, 0.99) 100%)',
        borderRadius: '16px',
        border: recordingState === 'listening'
          ? '1px solid rgba(74, 246, 38, 0.2)'
          : '1px solid rgba(255, 255, 255, 0.08)',
        boxShadow: recordingState === 'listening'
          ? '0 20px 60px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(0, 0, 0, 0.3), 0 0 30px rgba(74, 246, 38, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.05)'
          : '0 20px 60px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        position: 'relative',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        userSelect: 'none',
      }}
    >
      {/* Glow overlay */}
      {recordingState === 'listening' && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '16px',
            pointerEvents: 'none',
            background: 'radial-gradient(ellipse at center top, rgba(74, 246, 38, 0.1) 0%, transparent 70%)',
          }}
        />
      )}

      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 20px 8px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Status indicator */}
          <div style={{ position: 'relative', width: '10px', height: '10px' }}>
            {recordingState === 'listening' && (
              <>
                <div
                  style={{
                    position: 'absolute',
                    inset: '-4px',
                    borderRadius: '50%',
                    border: `2px solid ${getStatusColor()}`,
                    animation: 'pulse-ring 1.5s ease-out infinite',
                  }}
                />
                <div
                  style={{
                    position: 'absolute',
                    inset: '-4px',
                    borderRadius: '50%',
                    border: `2px solid ${getStatusColor()}`,
                    animation: 'pulse-ring 1.5s ease-out infinite',
                    animationDelay: '0.5s',
                  }}
                />
              </>
            )}
            <div
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor: getStatusColor(),
                position: 'relative',
                zIndex: 2,
              }}
            />
          </div>

          <span
            style={{
              fontSize: '13px',
              fontWeight: 600,
              color: 'rgba(255, 255, 255, 0.9)',
              letterSpacing: '0.3px',
            }}
          >
            {getStatusText()}
          </span>
        </div>

        <div
          style={{
            fontSize: '13px',
            fontWeight: 500,
            color: 'rgba(255, 255, 255, 0.5)',
            fontVariantNumeric: 'tabular-nums',
            fontFeatureSettings: '"tnum"',
          }}
        >
          {timer}
        </div>
      </div>

      {/* Waveform */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '8px 24px',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '3px',
            height: '60px',
            width: '100%',
          }}
        >
          {audioLevels.map((level, i) => {
            const scaledLevel = Math.pow(level, 0.7); // Non-linear scaling
            const height = Math.max(3, Math.min(60, 3 + scaledLevel * 57));

            return (
              <div
                key={i}
                className={getBarClass(level)}
                style={{
                  width: '5px',
                  height: `${height}px`,
                  borderRadius: '3px',
                  background: recordingState === 'processing'
                    ? 'linear-gradient(to top, #f59e0b, rgba(245, 158, 11, 0.6))'
                    : level < 0.05
                      ? 'linear-gradient(to top, rgba(139, 155, 180, 0.5), rgba(139, 155, 180, 0.2))'
                      : 'linear-gradient(to top, #4af626, rgba(74, 246, 38, 0.6))',
                  boxShadow: recordingState === 'processing'
                    ? '0 0 8px rgba(245, 158, 11, 0.3)'
                    : level >= 0.05
                      ? '0 0 8px rgba(74, 246, 38, 0.3)'
                      : 'none',
                  transition: 'height 60ms cubic-bezier(0.4, 0, 0.2, 1)',
                }}
              />
            );
          })}
        </div>
      </div>

      {/* Footer with transcription */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '8px 20px 16px',
        }}
      >
        <span
          style={{
            fontSize: '14px',
            color: transcriptionText ? 'rgba(255, 255, 255, 0.85)' : 'rgba(139, 155, 180, 0.5)',
            textAlign: 'center',
            maxWidth: '100%',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            fontWeight: 400,
            fontStyle: transcriptionText ? 'normal' : 'italic',
          }}
        >
          {transcriptionText || 'Waiting for speech...'}
        </span>
      </div>

      {/* Animations */}
      <style>{`
        @keyframes pulse-ring {
          0% { transform: scale(1); opacity: 0.8; }
          100% { transform: scale(1.5); opacity: 0; }
        }

        @keyframes processing-bounce {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
          40% { transform: scale(1); opacity: 1; }
        }

        .processing-dots {
          display: inline-flex;
          gap: 4px;
          align-items: center;
          margin-left: 4px;
        }

        .processing-dot {
          width: 4px;
          height: 4px;
          border-radius: 50%;
          background: #f59e0b;
          animation: processing-bounce 1.4s ease-in-out infinite both;
        }

        .processing-dot:nth-child(1) { animation-delay: -0.32s; }
        .processing-dot:nth-child(2) { animation-delay: -0.16s; }
      `}</style>
    </div>
  );
}
