/**
 * DictationContent - Main content panel for dictation mode
 * 
 * Renders transcript segments, coach results, live draft text, and statistics.
 * Supports inspector panels for combined text and coach output.
 * 
 * @component
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FileText, Waves } from 'lucide-react';
import type { CoachResult, Segment } from '../types/api';
import { RENDERER_STRINGS } from '../strings/en';
import {
  CombinedPanel,
  CoachPanel,
  EmptyState,
} from './TranscriptPanels';
import {
  MemoTranscriptSegment,
  StatCard,
  StatusBadge,
} from './TranscriptComponents';

type Snapshot = {
  transcript: Segment[];
};

type InspectorPanel = 'combined' | 'coach';

const MAIN_CONTENT_STRINGS = RENDERER_STRINGS.mainContent;

function buildCombinedDictationText({
  transcript,
  liveDraft,
  originalText,
  pasteText,
}: {
  transcript: Segment[];
  liveDraft?: { committedText: string; draftSuffix: string } | null;
  originalText: string | null;
  pasteText: string | null;
}): string {
  const transcriptText = transcript
    .map((segment) => segment.display_text || segment.text)
    .filter(Boolean)
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim();

  const draftText = [liveDraft?.committedText?.trim() ?? '', liveDraft?.draftSuffix?.trim() ?? '']
    .filter(Boolean)
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim();

  if (transcriptText && draftText) {
    if (transcriptText.includes(draftText)) {
      return transcriptText;
    }
    if (draftText.includes(transcriptText)) {
      return draftText;
    }
    return `${transcriptText} ${draftText}`.replace(/\s+/g, ' ').trim();
  }

  return (transcriptText || draftText || pasteText || originalText || '').trim();
}

type DictationContentProps = {
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
  coachResult?: CoachResult | null;
  coachStatus?: 'disabled' | 'queued' | 'running' | 'failed' | 'fallback' | 'cache_hit' | 'generated' | 'success' | null;
  coachDisplaySource?: 'coach' | 'fallback' | 'faithful' | null;
  coachError?: string | null;
  originalText?: string | null;
  pasteText?: string | null;
  showCoachDiff?: boolean;
};

export const DictationContent = React.memo(function DictationContent({
  snapshot,
  liveLatency,
  workspaceLabel = 'Workspace',
  workspaceTitle,
  workspaceDescription,
  liveDraft,
  transcriptDebugEvents = [],
  coachResult = null,
  coachStatus = null,
  coachDisplaySource = null,
  coachError = null,
  originalText = null,
  pasteText = null,
  showCoachDiff = false,
}: DictationContentProps) {
  const [activePanel, setActivePanel] = useState<InspectorPanel>('coach');
  const [autoScroll, setAutoScroll] = useState(true);
  const [inspectorCollapsed, setInspectorCollapsed] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const liveTranscript = snapshot.transcript.filter((segment) => !segment.suppressed);
  const acceptedCount = liveTranscript.length;
  const sessionStatus = snapshot.transcript.length > 0 ? 'transcribing' : 'idle';
  const visibleTranscript = useMemo(() => liveTranscript.slice(-200), [liveTranscript]);

  const combinedTranscriptText = useMemo(
    () =>
      buildCombinedDictationText({
        transcript: liveTranscript,
        liveDraft,
        originalText,
        pasteText,
      }),
    [liveDraft, liveTranscript, originalText, pasteText],
  );
  const combinedWordCount = useMemo(
    () => (combinedTranscriptText ? combinedTranscriptText.split(/\s+/).filter(Boolean).length : 0),
    [combinedTranscriptText],
  );

  const panels = useMemo(
    () => [
      {
        key: 'combined' as const,
        label: MAIN_CONTENT_STRINGS.panels.combined,
        count: combinedWordCount,
        accent: Boolean(combinedTranscriptText),
      },
      { key: 'coach' as const, label: MAIN_CONTENT_STRINGS.panels.coach, count: coachResult?.tips.length ?? 0, accent: Boolean(coachResult) },
    ],
    [coachResult, combinedTranscriptText, combinedWordCount],
  );

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [autoScroll, snapshot.transcript]);

  useEffect(() => {
    if (
      coachResult ||
      originalText ||
      pasteText ||
      coachStatus === 'fallback' ||
      coachStatus === 'failed' ||
      coachStatus === 'generated' ||
      coachStatus === 'cache_hit' ||
      coachStatus === 'success' ||
      coachStatus === 'running' ||
      coachStatus === 'queued'
    ) {
      setActivePanel('coach');
      return;
    }
    if (combinedWordCount > 0) {
      setActivePanel('combined');
    }
  }, [coachResult, coachStatus, originalText, pasteText, combinedWordCount]);

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) {
      return;
    }
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 60);
  }, []);

  const latencyValue =
    liveLatency !== null && liveLatency !== undefined && liveLatency > 0
      ? `${Math.round(liveLatency)}ms`
      : '--';

  return (
    <main className="flex min-h-0 flex-col gap-2 overflow-hidden bg-lawn-bg/30 p-2">
      <header className="shrink-0 border-2 border-lawn-border bg-lawn-panel p-2 text-lawn-border shadow-brutal">
        <div className="flex flex-col gap-2 2xl:flex-row 2xl:items-end 2xl:justify-between">
          <div className="min-w-0 flex-1">
            <div className="mb-0.5 flex items-center gap-2">
              <p className="text-[10px] font-black uppercase tracking-[0.15em] text-lawn-muted">
                {workspaceLabel}
              </p>
              <StatusBadge status={sessionStatus} />
            </div>
            <h2 className="font-display text-xl uppercase tracking-tighter leading-none md:text-2xl">
              {workspaceTitle || 'Mic / hotkey timeline'}
            </h2>
            <p className="mt-1.5 max-w-3xl text-[11px] font-bold leading-4 opacity-70 truncate line-clamp-1">
              {workspaceDescription || 'Quick dictation, low-latency feedback, and one shared timeline for recent spoken text.'}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap xl:grid xl:grid-cols-3">
            <StatCard label="Segments" value={String(acceptedCount)} />
            <StatCard label="Words" value={String(combinedWordCount)} />
            <StatCard label="Latency" value={latencyValue} warning={Boolean(liveLatency && liveLatency >= 500)} />
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-col gap-2 overflow-hidden">
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
            {combinedTranscriptText ? <CombinedTimelineCard combinedText={combinedTranscriptText} /> : null}
            {liveTranscript.length === 0 ? (
              <EmptyState
                title="No accepted transcript yet"
                body="Start dictation to see live draft and finalized microphone segments here. Session audio transcripts stay on the Sessions screen."
              />
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

        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => setInspectorCollapsed((current) => !current)}
            className="border-2 border-lawn-border bg-lawn-bg px-3 py-1 text-[10px] font-black uppercase tracking-[0.12em] text-lawn-border"
          >
            {inspectorCollapsed ? 'Show Inspector' : 'Hide Inspector'}
          </button>
        </div>
        {!inspectorCollapsed ? (
          <section className="flex min-h-0 flex-col overflow-hidden border-2 border-lawn-border bg-lawn-panel shadow-brutal">
            <div className="border-b-2 border-lawn-border bg-lawn-bg p-3">
              <div className="mb-3 flex items-center gap-2">
                <Waves size={14} className="text-lawn-accent" />
                <span className="text-[10px] font-black uppercase tracking-[0.12em] text-lawn-border">
                  Inspector
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 md:grid-cols-4 lg:flex lg:flex-wrap">
                {panels.map((panel) => (
                  <button
                    key={panel.key}
                    type="button"
                    onClick={() => setActivePanel(panel.key)}
                    className={[
                      'border-2 px-1.5 py-1.5 text-left shadow-brutal-sm transition-all lg:flex-1',
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
              {activePanel === 'combined' && <CombinedPanel combinedText={combinedTranscriptText} />}
              {activePanel === 'coach' && (
                <CoachPanel
                  coachResult={coachResult}
                  coachStatus={coachStatus}
                  coachDisplaySource={coachDisplaySource}
                  coachError={coachError}
                  originalText={originalText}
                  pasteText={pasteText}
                  showDiff={showCoachDiff}
                />
              )}
            </div>
          </section>
        ) : null}
      </div>
    </main>
  );
});

const CombinedTimelineCard = React.memo(function CombinedTimelineCard({ combinedText }: { combinedText: string }) {
  return (
    <article className="border-2 border-lawn-border bg-lawn-dark/90 p-3 text-lawn-bg">
      <div className="mb-2 text-[9px] font-black uppercase tracking-widest text-lawn-accent">
        {MAIN_CONTENT_STRINGS.combined.inlineLabel}
      </div>
      <p className="text-xs font-bold leading-5">
        {combinedText || MAIN_CONTENT_STRINGS.combined.inlineEmpty}
      </p>
    </article>
  );
});
