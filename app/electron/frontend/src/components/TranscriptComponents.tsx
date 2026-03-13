import React from 'react';
import type { Segment } from '../types/api';

export const MemoTranscriptSegment = React.memo(TranscriptSegment);

export function TranscriptSegment({ segment, isLatest }: { segment: Segment; isLatest: boolean }) {
  const displayText = segment.display_text || segment.text;
  const words = segment.words ?? (() => {
    const wordArray = displayText.split(/\s+/).filter(Boolean);
    if (wordArray.length === 0) {
      return [{
        text: displayText || '',
        start: segment.start,
        end: segment.end,
        confidence: segment.confidence,
      }];
    }
    const wordCount = wordArray.length;
    const duration = segment.end - segment.start;
    return wordArray.map((text, i) => ({
      text,
      start: segment.start + (i / wordCount) * duration,
      end: segment.start + ((i + 1) / wordCount) * duration,
      confidence: segment.confidence,
    }));
  })();

  const isHindi = segment.language === 'hi';
  const isWeak = segment.quality_label === 'weak';

  return (
    <article
      className={[
        'border-2 p-2.5 transition-all duration-200',
        'hover:-translate-y-0.5 hover:shadow-brutal-sm',
        isWeak ? 'border-theme-warning bg-theme-warning/10' : 'border-lawn-border bg-lawn-bg',
        isLatest && !segment.is_partial ? 'animate-slide-in' : '',
        segment.is_partial ? 'border-dashed opacity-70' : '',
      ].join(' ')}
    >
      <div className="mb-1.5 flex items-center justify-between border-b border-lawn-border/20 pb-1.5">
        <div className="flex items-center gap-1.5">
          <span
            className={[
              'border px-1 py-0.5 text-[8px] font-black uppercase tracking-wider',
              isHindi
                ? 'border-theme-warning/30 bg-theme-warning/20 text-theme-warning'
                : 'border-theme-info/30 bg-theme-info/20 text-theme-info',
            ].join(' ')}
          >
            {segment.language === 'hi' ? 'हि' : segment.language.toUpperCase()}
          </span>
          <div className={`h-1.5 w-1.5 rounded-full ${getConfidenceColor(segment.confidence)}`} />
          <span className="text-[10px] font-black text-lawn-border">
            {(segment.confidence * 100).toFixed(0)}%
          </span>
          {segment.was_refined ? (
            <span className="border border-lawn-accent/40 bg-lawn-accent/10 px-1 py-0.5 text-[8px] font-black uppercase tracking-wider text-lawn-accent">
              Refined
            </span>
          ) : null}
        </div>
        <span className="text-[10px] font-bold text-lawn-muted">
          {segment.start.toFixed(1)}s - {segment.end.toFixed(1)}s
        </span>
      </div>

      <div className={['text-sm font-bold leading-6 text-lawn-border', isHindi ? 'font-sans' : ''].join(' ')}>
        {words.map((word, wordIndex) => (
          <WordToken
            key={`${segment.id}-${wordIndex}`}
            word={word}
            isLatest={isLatest && wordIndex >= words.length - 3}
            wordIndex={wordIndex}
          />
        ))}
        {segment.is_partial && (
          <span className="ml-1 inline-flex h-4 items-center">
            <span className="h-3 w-1 animate-pulse bg-lawn-accent" />
          </span>
        )}
      </div>

      {(isWeak || segment.review_flag) && (
        <div className="mt-1.5 flex items-center gap-1.5">
          <span className="text-[9px] font-black uppercase tracking-wider text-theme-warning">
            {segment.review_flag ? 'needs review' : 'weak decode'}
            {segment.script_mismatch ? ' · script mismatch' : ''}
          </span>
        </div>
      )}
    </article>
  );
}

export function WordToken({
  word,
  isLatest,
  wordIndex,
}: {
  word: { text: string; confidence: number };
  isLatest: boolean;
  wordIndex: number;
}) {
  return (
    <span
      className={['mr-1 inline-block text-lawn-border transition-all duration-200', isLatest ? 'animate-word-in' : ''].join(' ')}
      style={{
        opacity: getWordOpacity(word.confidence),
        animationDelay: isLatest ? `${wordIndex * 30}ms` : '0ms',
      }}
    >
      {word.text}
    </span>
  );
}

export function StatCard({
  label,
  value,
  danger,
  accent,
  warning,
}: {
  label: string;
  value: string;
  danger?: boolean;
  accent?: boolean;
  warning?: boolean;
}) {
  return (
    <div
      className={[
        'border-2 border-lawn-border bg-lawn-bg p-2 text-center shadow-brutal-sm transition-transform hover:-translate-y-0.5',
        danger ? 'border-theme-error bg-theme-error text-lawn-bg' : '',
        accent ? 'border-theme-success bg-theme-success text-lawn-bg' : '',
        warning ? 'border-theme-warning bg-theme-warning text-lawn-bg' : '',
      ].join(' ')}
    >
      <div className="mb-0.5 text-[9px] font-black uppercase tracking-widest opacity-70">{label}</div>
      <div className="text-lg font-black leading-tight">{value}</div>
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const styles =
    status === 'running' || status === 'transcribing'
      ? 'bg-theme-success text-lawn-bg border-theme-success'
      : 'bg-lawn-soft text-lawn-muted-strong border-lawn-soft';

  return (
    <span className={`border px-1.5 py-0.5 text-[9px] font-black uppercase tracking-widest ${styles}`}>
      {status}
    </span>
  );
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.85) return 'bg-theme-success';
  if (confidence >= 0.7) return 'bg-theme-warning';
  return 'bg-theme-error';
}

function getWordOpacity(confidence: number): number {
  if (confidence >= 0.9) return 1;
  if (confidence >= 0.7) return 0.85;
  if (confidence >= 0.5) return 0.7;
  return 0.5;
}
