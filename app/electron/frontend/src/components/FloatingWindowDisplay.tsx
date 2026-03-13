import type { CSSProperties } from 'react';

type FloatingStyle = CSSProperties & { WebkitAppRegion?: string };

interface FloatingTranscriptDisplayProps {
  phase: string;
  mode: string;
  committedText: string;
  partialText: string;
  finalText: string;
  errorText: string | null;
  showModelPreparationPanel: boolean;
  waitingLabel: string;
  strings?: {
    resultMeta?: {
      genericError?: string;
    };
  };
}

export function FloatingTranscriptDisplay({
  phase,
  mode,
  committedText,
  partialText,
  finalText,
  errorText,
  showModelPreparationPanel,
  waitingLabel,
  strings,
}: FloatingTranscriptDisplayProps) {
  const visibleTranscript = phase === 'done' ? finalText || committedText : committedText || partialText;

  return (
    <div
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
      ) : showModelPreparationPanel ? (
        <div style={{ flex: 1 }} />
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
  );
}

export function FloatingFooter({
  resultMetaLabel,
  showActiveControls,
  showClose,
  effectivePhase,
  strings,
  onCancel,
  onFinish,
  onClose,
}: {
  resultMetaLabel: string;
  showActiveControls: boolean;
  showClose: boolean;
  effectivePhase: string;
  strings?: {
    actions?: {
      cancel?: string;
      finish?: string;
      close?: string;
    };
  };
  onCancel: () => void;
  onFinish: () => void;
  onClose: () => void;
}) {
  const buttonStyleFn = (variant: 'primary' | 'secondary', disabled = false) => {
    if (variant === 'primary') {
      return {
        WebkitAppRegion: 'no-drag' as const,
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
      WebkitAppRegion: 'no-drag' as const,
      border: '1px solid rgba(255,255,255,0.1)',
      background: 'rgba(255,255,255,0.06)',
      color: 'rgba(255,255,255,0.88)',
      borderRadius: 10,
      padding: '8px 14px',
      fontSize: 13,
      fontWeight: 700,
      cursor: 'pointer',
    };
  };

  return (
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
              onClick={onCancel}
              style={buttonStyleFn('secondary')}
            >
              {strings?.actions?.cancel || 'Cancel'}
            </button>
            <button
              type="button"
              onClick={onFinish}
              disabled={effectivePhase === 'preparing' || effectivePhase === 'finalizing'}
              style={buttonStyleFn('primary', effectivePhase === 'preparing' || effectivePhase === 'finalizing')}
            >
              {strings?.actions?.finish || 'Finish'}
            </button>
          </>
        ) : null}

        {showClose ? (
          <button
            type="button"
            onClick={onClose}
            style={buttonStyleFn('primary')}
          >
            {strings?.actions?.close || 'Close'}
          </button>
        ) : null}
      </div>
    </div>
  );
}
