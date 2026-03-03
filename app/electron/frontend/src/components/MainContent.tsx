import type React from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, FileText, Filter, Sigma, TriangleAlert, Waves } from 'lucide-react';
import type { Formula, Segment, SessionSummary } from '../types/api';

type Snapshot = {
  session: SessionSummary | null;
  transcript: Segment[];
  suppressed_transcript: Segment[];
  formulas: Formula[];
  needs_review: Segment[];
  health: {
    last_error: string | null;
    last_warning?: string | null;
    last_transcript_at: string | null;
    audio_stream_active?: boolean;
    model_runtime_device?: string | null;
  };
};

type MainContentProps = {
  snapshot: Snapshot;
  liveLatency?: number | null;
  activityFeed?: React.ReactNode;
};

type InspectorPanel = 'review' | 'formulas' | 'suppressed' | 'errors' | 'session';

export function MainContent({ snapshot, liveLatency, activityFeed }: MainContentProps) {
  const [activePanel, setActivePanel] = useState<InspectorPanel>('review');
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const liveTranscript = snapshot.transcript.filter((segment) => !segment.suppressed);
  const acceptedCount = snapshot.session?.segment_count ?? liveTranscript.length;
  const formulaCount = snapshot.session?.formula_count ?? snapshot.formulas.length;
  const reviewCount = snapshot.session?.review_count ?? snapshot.needs_review.length;
  const suppressedCount =
    snapshot.session?.suppressed_count ?? snapshot.suppressed_transcript.length;
  const errorCount = Number(Boolean(snapshot.health.last_error)) + Number(Boolean(snapshot.health.last_warning));
  const sessionStatus = snapshot.session?.status ?? 'idle';

  const panels = useMemo(
    () => [
      { key: 'review' as const, label: 'Review', count: reviewCount, accent: reviewCount > 0 },
      { key: 'formulas' as const, label: 'Formulas', count: formulaCount, accent: formulaCount > 0 },
      { key: 'suppressed' as const, label: 'Suppressed', count: suppressedCount, accent: suppressedCount > 0 },
      { key: 'errors' as const, label: 'Errors', count: errorCount, accent: errorCount > 0 },
      { key: 'session' as const, label: 'Session', count: acceptedCount, accent: false },
    ],
    [acceptedCount, errorCount, formulaCount, reviewCount, suppressedCount],
  );

  useEffect(() => {
    if (reviewCount > 0) {
      setActivePanel('review');
      return;
    }
    if (formulaCount > 0) {
      setActivePanel('formulas');
      return;
    }
    if (suppressedCount > 0) {
      setActivePanel('suppressed');
    }
  }, [formulaCount, reviewCount, suppressedCount]);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [autoScroll, snapshot.transcript]);

  function handleScroll() {
    if (!scrollRef.current) {
      return;
    }
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 60);
  }

  const latencyValue =
    liveLatency !== null && liveLatency !== undefined && liveLatency > 0
      ? `${Math.round(liveLatency)}ms`
      : '--';

  return (
    <main className="flex min-h-0 flex-col gap-4 overflow-hidden bg-lawn-bg/30 p-4">
      {activityFeed && <div className="xl:hidden shrink-0">{activityFeed}</div>}

      <header className="shrink-0 border-2 border-lawn-border bg-lawn-panel p-5 text-lawn-border shadow-brutal">
        <div className="flex flex-col gap-4 2xl:flex-row 2xl:items-end 2xl:justify-between">
          <div className="min-w-0 flex-1">
            <div className="mb-1 flex items-center gap-2">
              <p className="text-[10px] font-black uppercase tracking-[0.15em] text-stone-500">
                Workspace
              </p>
              <StatusBadge status={sessionStatus} />
            </div>
            <h2 className="font-display text-3xl uppercase tracking-tighter leading-none md:text-4xl">
              {snapshot.session?.title || 'Live Workspace'}
            </h2>
            <p className="mt-2 max-w-3xl text-xs font-bold leading-4 opacity-70">
              {snapshot.session?.output_dir ||
                'Session transcript, verification, formulas, suppressed segments, and diagnostics stay visible here while capture is running.'}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
            <StatCard label="Segments" value={String(acceptedCount)} />
            <StatCard label="Review" value={String(reviewCount)} danger={reviewCount > 0} />
            <StatCard label="Formulas" value={String(formulaCount)} accent={formulaCount > 0} />
            <StatCard label="Suppressed" value={String(suppressedCount)} />
            <StatCard label="Latency" value={latencyValue} warning={Boolean(liveLatency && liveLatency >= 500)} />
          </div>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 gap-4 overflow-hidden xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.95fr)]">
        <section className="flex min-h-0 flex-col overflow-hidden border-2 border-lawn-border bg-lawn-panel shadow-brutal">
          <div className="flex items-center justify-between border-b-2 border-lawn-border bg-lawn-bg p-3">
            <div className="flex items-center gap-2">
              <FileText size={14} className="text-lawn-accent" />
              <span className="text-[10px] font-black uppercase tracking-[0.12em] text-lawn-border">
                Live Transcript
              </span>
            </div>
            <span className="text-[10px] font-bold text-stone-500">
              {liveTranscript.length} visible
            </span>
          </div>

          <div ref={scrollRef} onScroll={handleScroll} className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3 custom-scrollbar">
            {liveTranscript.length === 0 ? (
              <EmptyState
                title="No accepted transcript yet"
                body="Start a session and play system audio. Review, formulas, suppressed segments, and warnings will populate alongside the transcript."
              />
            ) : (
              liveTranscript.slice(-120).map((segment, index, arr) => (
                <TranscriptSegment
                  key={segment.id}
                  segment={segment}
                  isLatest={index === arr.length - 1}
                />
              ))
            )}
          </div>
        </section>

        <aside className="flex min-h-0 flex-col overflow-hidden border-2 border-lawn-border bg-lawn-panel shadow-brutal">
          <div className="border-b-2 border-lawn-border bg-lawn-bg p-3">
            <div className="mb-3 flex items-center gap-2">
              <Waves size={14} className="text-lawn-accent" />
              <span className="text-[10px] font-black uppercase tracking-[0.12em] text-lawn-border">
                Inspector
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {panels.map((panel) => (
                <button
                  key={panel.key}
                  type="button"
                  onClick={() => setActivePanel(panel.key)}
                  className={[
                    'border-2 px-2 py-2 text-left shadow-brutal-sm transition-all',
                    activePanel === panel.key
                      ? 'border-lawn-border bg-lawn-accent text-lawn-border'
                      : panel.accent
                        ? 'border-lawn-border bg-lawn-bg text-lawn-border hover:-translate-y-0.5'
                        : 'border-lawn-border bg-lawn-bg/70 text-lawn-border hover:-translate-y-0.5',
                  ].join(' ')}
                >
                  <div className="text-[9px] font-black uppercase tracking-widest opacity-70">{panel.label}</div>
                  <div className="mt-1 text-lg font-black leading-none">{panel.count}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-3 custom-scrollbar">
            {activePanel === 'review' && <ReviewPanel segments={snapshot.needs_review} />}
            {activePanel === 'formulas' && <FormulasPanel formulas={snapshot.formulas} />}
            {activePanel === 'suppressed' && <SuppressedPanel segments={snapshot.suppressed_transcript} />}
            {activePanel === 'errors' && (
              <ErrorsPanel error={snapshot.health.last_error} warning={snapshot.health.last_warning ?? null} />
            )}
            {activePanel === 'session' && (
              <SessionPanel
                session={snapshot.session}
                acceptedCount={acceptedCount}
                reviewCount={reviewCount}
                formulaCount={formulaCount}
                suppressedCount={suppressedCount}
                lastTranscriptAt={snapshot.health.last_transcript_at}
                runtimeDevice={snapshot.health.model_runtime_device ?? null}
                audioActive={snapshot.health.audio_stream_active ?? false}
              />
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}

function ReviewPanel({ segments }: { segments: Segment[] }) {
  if (segments.length === 0) {
    return (
      <EmptyState
        title="No review flags yet"
        body="Segments that look uncertain, contradictory, or formula-heavy will appear here."
      />
    );
  }

  return (
    <div className="space-y-2">
      {segments.slice(-16).reverse().map((segment) => (
        <article key={segment.id} className="border-2 border-theme-warning bg-theme-warning/10 p-3">
          <div className="mb-1 flex items-center gap-2 text-theme-warning">
            <AlertCircle size={12} />
            <span className="text-[9px] font-black uppercase tracking-widest">
              {segment.start.toFixed(1)}s - {segment.end.toFixed(1)}s
            </span>
          </div>
          <p className="text-sm font-bold text-lawn-border">{segment.display_text || segment.text}</p>
          {segment.review_reasons.length > 0 && (
            <p className="mt-2 text-[10px] font-black uppercase tracking-wider text-theme-warning">
              {segment.review_reasons.join(' · ')}
            </p>
          )}
        </article>
      ))}
    </div>
  );
}

function FormulasPanel({ formulas }: { formulas: Formula[] }) {
  if (formulas.length === 0) {
    return (
      <EmptyState
        title="No formulas extracted yet"
        body="Formula-like expressions and symbolic patterns will appear here with context and timestamps."
      />
    );
  }

  return (
    <div className="space-y-2">
      {formulas.slice(-16).reverse().map((formula, index) => (
        <article key={`${formula.expression}-${index}`} className="border-2 border-lawn-border bg-lawn-dark p-3 text-lawn-bg">
          <div className="mb-1 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Sigma size={12} className="text-lawn-accent" />
              <code className="font-mono text-sm font-bold">{formula.expression}</code>
            </div>
            <span className="text-[9px] font-black uppercase tracking-wider opacity-70">
              {formula.timestamp_start.toFixed(1)}s
            </span>
          </div>
          <p className="text-[11px] leading-5 opacity-80">{formula.context || 'Context unavailable.'}</p>
        </article>
      ))}
    </div>
  );
}

function SuppressedPanel({ segments }: { segments: Segment[] }) {
  if (segments.length === 0) {
    return (
      <EmptyState
        title="No suppressed segments"
        body="Low-quality or obviously garbled segments will appear here instead of polluting the main transcript."
      />
    );
  }

  return (
    <div className="space-y-2">
      {segments.slice(-16).reverse().map((segment) => (
        <article key={segment.id} className="border-2 border-stone-300 bg-stone-100 p-3">
          <div className="mb-1 flex items-center gap-2 text-stone-500">
            <Filter size={12} />
            <span className="text-[9px] font-black uppercase tracking-widest">
              {segment.start.toFixed(1)}s - {segment.end.toFixed(1)}s
            </span>
          </div>
          <p className="text-xs font-bold text-stone-700">{segment.display_text || segment.text}</p>
          {segment.suppression_reasons.length > 0 && (
            <p className="mt-2 text-[10px] font-black uppercase tracking-wider text-stone-500">
              {segment.suppression_reasons.join(' · ')}
            </p>
          )}
        </article>
      ))}
    </div>
  );
}

function ErrorsPanel({ error, warning }: { error: string | null; warning: string | null }) {
  if (!error && !warning) {
    return (
      <EmptyState
        title="No active errors"
        body="Runtime warnings and backend errors will appear here with the latest status."
      />
    );
  }

  return (
    <div className="space-y-2">
      {warning && (
        <article className="border-2 border-theme-warning bg-theme-warning/10 p-3">
          <div className="mb-1 flex items-center gap-2 text-theme-warning">
            <TriangleAlert size={12} />
            <span className="text-[9px] font-black uppercase tracking-widest">Warning</span>
          </div>
          <p className="text-sm font-bold text-lawn-border">{warning}</p>
        </article>
      )}
      {error && (
        <article className="border-2 border-theme-error bg-theme-error/10 p-3">
          <div className="mb-1 flex items-center gap-2 text-theme-error">
            <AlertCircle size={12} />
            <span className="text-[9px] font-black uppercase tracking-widest">Error</span>
          </div>
          <p className="text-sm font-bold text-lawn-border">{error}</p>
        </article>
      )}
    </div>
  );
}

function SessionPanel({
  session,
  acceptedCount,
  reviewCount,
  formulaCount,
  suppressedCount,
  lastTranscriptAt,
  runtimeDevice,
  audioActive,
}: {
  session: SessionSummary | null;
  acceptedCount: number;
  reviewCount: number;
  formulaCount: number;
  suppressedCount: number;
  lastTranscriptAt: string | null;
  runtimeDevice: string | null;
  audioActive: boolean;
}) {
  return (
    <div className="space-y-3">
      <InspectorCard label="Session" value={session?.title || 'No active session'} />
      <InspectorCard label="Output" value={session?.output_dir || 'Not started'} />
      <InspectorCard label="Accepted" value={String(acceptedCount)} />
      <InspectorCard label="Review Flags" value={String(reviewCount)} />
      <InspectorCard label="Formulas" value={String(formulaCount)} />
      <InspectorCard label="Suppressed" value={String(suppressedCount)} />
      <InspectorCard label="Runtime" value={runtimeDevice || 'unknown'} />
      <InspectorCard label="Audio Stream" value={audioActive ? 'live' : 'idle'} />
      <InspectorCard label="Last Transcript" value={lastTranscriptAt || 'Waiting for transcript'} />
    </div>
  );
}

function InspectorCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-2 border-lawn-border bg-lawn-bg p-3">
      <div className="text-[9px] font-black uppercase tracking-widest text-stone-500">{label}</div>
      <div className="mt-1 text-sm font-bold leading-5 text-lawn-border break-words">{value}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles =
    status === 'running'
      ? 'bg-theme-success text-lawn-bg border-theme-success'
      : 'bg-stone-200 text-stone-600 border-stone-300';

  return (
    <span className={`border px-1.5 py-0.5 text-[9px] font-black uppercase tracking-widest ${styles}`}>
      {status}
    </span>
  );
}

function TranscriptSegment({ segment, isLatest }: { segment: Segment; isLatest: boolean }) {
  const displayText = segment.display_text || segment.text;
  const words = segment.words ?? (() => {
    const wordArray = displayText.split(/\s+/).filter(Boolean);
    // Guard against empty arrays to prevent division by zero
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
        </div>
        <span className="text-[10px] font-bold text-stone-400">
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

function WordToken({
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

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="border-2 border-dashed border-lawn-border bg-lawn-bg/50 p-6 text-center">
      <p className="text-sm font-black text-lawn-border">{title}</p>
      <p className="mt-2 text-xs font-bold leading-5 text-stone-500">{body}</p>
    </div>
  );
}

function StatCard({
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
