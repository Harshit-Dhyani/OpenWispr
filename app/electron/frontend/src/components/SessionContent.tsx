/**
 * SessionContent - Main content panel for session mode
 * 
 * Renders session transcript with inspector panels for review, formulas, suppressed,
 * errors, and session metadata. Displays statistics and live draft state.
 * 
 * @component
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { FileText, Waves } from 'lucide-react';
import type { Formula, Segment, SessionSummary } from '../types/api';
import {
  ErrorsPanel,
  FormulasPanel,
  ReviewPanel,
  SessionPanel,
  SuppressedPanel,
} from './TranscriptPanels';
import {
  MemoTranscriptSegment,
  StatCard,
  StatusBadge,
} from './TranscriptComponents';

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

type InspectorPanel = 'review' | 'formulas' | 'suppressed' | 'errors' | 'session';

type SessionContentProps = {
  snapshot: Snapshot;
  liveLatency?: number | null;
  workspaceLabel?: string;
  workspaceTitle?: string;
  workspaceDescription?: string;
  liveDraft?: {
    committedText: string;
    draftSuffix: string;
  } | null;
  transcriptDebugEvents?: Array<{
    id: number;
    type: string;
    sessionId: string | null;
    segmentId: string | null;
    correlationId?: string | null;
    detail?: string | null;
    textLength: number;
  }>;
};

export function SessionContent({
  snapshot,
  liveLatency,
  workspaceLabel = 'Workspace',
  workspaceTitle,
  workspaceDescription,
  liveDraft,
  transcriptDebugEvents = [],
}: SessionContentProps) {
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
  const visibleTranscript = useMemo(() => liveTranscript.slice(-200), [liveTranscript]);

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
      <header className="shrink-0 border-2 border-lawn-border bg-lawn-panel p-3 text-lawn-border shadow-brutal">
        <div className="flex flex-col gap-2 2xl:flex-row 2xl:items-end 2xl:justify-between">
          <div className="min-w-0 flex-1">
            <div className="mb-0.5 flex items-center gap-2">
              <p className="text-[10px] font-black uppercase tracking-[0.15em] text-lawn-muted">
                {workspaceLabel}
              </p>
              <StatusBadge status={sessionStatus} />
            </div>
            <h2 className="font-display text-2xl uppercase tracking-tighter leading-none md:text-3xl">
              {workspaceTitle || snapshot.session?.title || 'Live Transcript'}
            </h2>
            <p className="mt-1.5 max-w-3xl text-[11px] font-bold leading-4 opacity-70 truncate line-clamp-1">
              {workspaceDescription ||
                snapshot.session?.output_dir ||
                'Transcript, verification, formulas, suppressed segments, and diagnostics stay visible here while capture is running.'}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
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
          <div className="flex items-center justify-between border-b-2 border-lawn-border bg-lawn-bg px-2 py-1.5">
            <div className="flex items-center gap-2">
              <FileText size={14} className="text-lawn-accent" />
              <span className="text-[10px] font-black uppercase tracking-[0.12em] text-lawn-border">
                Live Transcript
              </span>
            </div>
            <span className="text-[10px] font-bold text-lawn-muted">
              {liveTranscript.length} visible
            </span>
          </div>

          <div ref={scrollRef} onScroll={handleScroll} className="min-h-0 flex-1 space-y-2 overflow-y-auto px-2 py-2 custom-scrollbar">
            {liveTranscript.length === 0 ? (
              <div className="border-2 border-dashed border-lawn-border bg-lawn-bg/50 p-6 text-center">
                <p className="text-sm font-black text-lawn-border">No accepted transcript yet</p>
                <p className="mt-2 text-xs font-bold leading-5 text-lawn-muted">Start a session and play system audio. Review, formulas, suppressed segments, and warnings will populate alongside the transcript.</p>
              </div>
            ) : (
              visibleTranscript.map((segment, index, arr) => (
                <MemoTranscriptSegment
                  key={segment.id}
                  segment={segment}
                  isLatest={index === arr.length - 1}
                />
              ))
            )}
            {liveDraft && (liveDraft.committedText || liveDraft.draftSuffix) ? (
              <article className="border-2 border-dashed border-lawn-accent bg-lawn-accent/5 p-3">
                <div className="mb-1 flex items-center gap-2">
                  <span className="text-[9px] font-black uppercase tracking-widest text-lawn-accent">
                    Live Draft
                  </span>
                  <span className="text-[9px] font-bold uppercase tracking-widest text-lawn-muted">
                    committed prefix stays stable
                  </span>
                </div>
                <p className="text-sm font-bold leading-6 text-lawn-border">
                  {liveDraft.committedText ? (
                    <span>{liveDraft.committedText}{liveDraft.draftSuffix ? ' ' : ''}</span>
                  ) : null}
                  {liveDraft.draftSuffix ? (
                    <span className="text-lawn-accent/80">{liveDraft.draftSuffix}</span>
                  ) : null}
                </p>
              </article>
            ) : null}
            {transcriptDebugEvents.length > 0 ? (
              <article className="border-2 border-lawn-border bg-lawn-dark/90 p-3 text-lawn-bg">
                <div className="mb-2 text-[9px] font-black uppercase tracking-widest text-lawn-accent">
                  Runtime Event Debug
                </div>
                <div className="space-y-1 text-[10px] font-mono">
                  {transcriptDebugEvents.map((entry) => (
                    <div key={entry.id} className="flex items-center justify-between gap-3">
                      <span className="truncate text-lawn-accent">{entry.type}</span>
                      <span className="truncate opacity-70">{entry.sessionId ?? 'no-session'}</span>
                      <span className="opacity-60">{entry.segmentId ?? '--'}</span>
                      <span className="truncate opacity-60">{entry.correlationId ?? '--'}</span>
                      <span className="truncate opacity-60">{entry.detail ?? '--'}</span>
                      <span className="opacity-90">{entry.textLength}ch</span>
                    </div>
                  ))}
                </div>
              </article>
            ) : null}
          </div>
        </section>

        <section className="flex min-h-0 flex-col overflow-hidden border-2 border-lawn-border bg-lawn-panel shadow-brutal">
          <div className="border-b-2 border-lawn-border bg-lawn-bg p-3">
            <div className="mb-3 flex items-center gap-2">
              <Waves size={14} className="text-lawn-accent" />
              <span className="text-[10px] font-black uppercase tracking-[0.12em] text-lawn-border">
                Inspector
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 sm:flex sm:flex-wrap xl:grid xl:grid-cols-3 2xl:grid-cols-5">
              {panels.map((panel) => (
                <button
                  key={panel.key}
                  type="button"
                  onClick={() => setActivePanel(panel.key)}
                  className={[
                    'border-2 px-1.5 py-1.5 text-left shadow-brutal-sm transition-all sm:flex-1 xl:flex-none',
                    activePanel === panel.key
                      ? 'border-lawn-border bg-lawn-accent text-lawn-bg'
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
        </section>
      </div>
    </main>
  );
}
