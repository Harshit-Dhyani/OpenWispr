const WAVEFORM_BAR_COUNT = 36;

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

interface AudioVisualizerProps {
  audioLevels: number[];
}

export function FloatingAudioVisualizer({ audioLevels }: AudioVisualizerProps) {
  const levels = sanitizeLevels(audioLevels);

  return (
    <div
      aria-label="Audio waveform"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 3,
        height: 52,
      }}
    >
      {levels.map((level, index) => {
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
  );
}

export function FloatingModelPreparation({
  stage,
  message,
}: {
  stage: string;
  message: string;
}) {
  return (
    <div
      data-testid="floating-model-preparation"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        padding: '4px 0',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'rgba(240, 249, 255, 0.96)' }}>
            Preparing speech model
          </div>
          <div style={{ fontSize: 12, color: 'rgba(186, 230, 253, 0.78)', marginTop: 2 }}>
            {message || 'Loading transcription runtime...'}
          </div>
        </div>
        <div
          style={{
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: 0.3,
            color: 'rgba(125, 211, 252, 0.92)',
            textTransform: 'uppercase',
            flexShrink: 0,
          }}
        >
          {stage || 'loading'}
        </div>
      </div>
      <div
        aria-label="Model loading progress"
        style={{
          position: 'relative',
          overflow: 'hidden',
          height: 10,
          borderRadius: 999,
          background: 'rgba(125, 211, 252, 0.12)',
          border: '1px solid rgba(125, 211, 252, 0.18)',
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            width: '42%',
            borderRadius: 999,
            background: 'linear-gradient(90deg, rgba(56, 189, 248, 0.2) 0%, rgba(125, 211, 252, 0.95) 50%, rgba(34, 197, 94, 0.25) 100%)',
            boxShadow: '0 0 18px rgba(56, 189, 248, 0.28)',
            animation: 'floating-model-progress 1.35s ease-in-out infinite',
          }}
        />
      </div>
    </div>
  );
}
