import { useRef, useEffect, useState } from 'react';
import { FileText, AlertCircle, Filter, Zap, ChevronDown, ChevronUp } from 'lucide-react';
import type { Formula, Segment, SessionSummary } from '../types/api';

type Snapshot = {
  session: SessionSummary | null;
  transcript: Segment[];
  suppressed_transcript: Segment[];
  formulas: Formula[];
  needs_review: Segment[];
  health: {
    last_error: string | null;
    last_transcript_at: string | null;
  };
};

type MainContentProps = {
  snapshot: Snapshot;
  liveLatency?: number | null;
};

export function MainContent({ snapshot, liveLatency }: MainContentProps) {
  const liveTranscript = snapshot.transcript.filter((segment) => !segment.suppressed);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [insightsOpen, setInsightsOpen] = useState(false);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [snapshot.transcript, autoScroll]);

  const handleScroll = () => {
    if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 50;
      setAutoScroll(isNearBottom);
    }
  };

  const sessionStatus = snapshot.session?.status ?? 'idle';

  // Calculate stats
  const segmentCount = snapshot.session?.segment_count ?? liveTranscript.length;
  const formulaCount = snapshot.session?.formula_count ?? snapshot.formulas.length;
  const reviewCount = snapshot.session?.review_count ?? snapshot.needs_review.length;
  const suppressedCount = snapshot.session?.suppressed_count ?? snapshot.suppressed_transcript.length;

  // Format latency
  const latencyValue = liveLatency !== null && liveLatency !== undefined && liveLatency > 0
    ? `${Math.round(liveLatency)}ms`
    : '--';
  const latencyAccent = liveLatency !== null && liveLatency !== undefined && liveLatency > 0 && liveLatency < 500;
  const latencyWarning = liveLatency !== null && liveLatency !== undefined && liveLatency >= 500;

  return (
    <main className="flex flex-col h-full bg-lawn-bg/30 overflow-hidden">
      {/* FIXED HEADER - Contains stat cards, does NOT scroll */}
      <header className="border-b-2 border-lawn-border bg-lawn-accent p-4 text-lawn-border shadow-brutal shrink-0">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          {/* Title Section */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <p className="text-[10px] font-black uppercase tracking-[0.15em] text-lawn-border/70">
                Active Output
              </p>
              <StatusBadge status={sessionStatus} />
            </div>
            <h2 className="font-display text-3xl md:text-4xl uppercase tracking-tighter leading-none truncate">
              {snapshot.session?.title || 'Idle'}
            </h2>
            <p className="mt-2 max-w-xl text-xs font-bold leading-4 opacity-70 truncate">
              {snapshot.session?.output_dir || 'Start a session to generate local transcript files, notes, and review flags.'}
            </p>
          </div>

          {/* Stat Cards - Always visible in header */}
          <div className="grid grid-cols-5 gap-2 xl:min-w-[400px] xl:max-w-[500px]">
            <StatCard label="Segments" value={String(segmentCount)} />
            <StatCard label="Formulas" value={String(formulaCount)} />
            <StatCard label="Review" value={String(reviewCount)} danger={reviewCount > 0} />
            <StatCard label="Suppressed" value={String(suppressedCount)} />
            <StatCard label="Latency" value={latencyValue} accent={latencyAccent} warning={latencyWarning} />
          </div>
        </div>
      </header>

      {/* SCROLLABLE CONTENT AREA */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-4"
      >
        {/* Live Transcript Section */}
        <section className="border-2 border-lawn-border bg-lawn-panel shadow-brutal flex flex-col">
          <div className="flex items-center justify-between p-3 border-b-2 border-lawn-border bg-lawn-bg shrink-0">
            <div className="flex items-center gap-2">
              <FileText size={14} className="text-lawn-accent" />
              <span className="text-[10px] font-black uppercase tracking-[0.12em] text-lawn-border">
                Live Transcript
              </span>
            </div>
            <span className="text-[10px] font-bold text-stone-500">
              {liveTranscript.length} segments
            </span>
          </div>
          <div className="p-3 min-h-[200px]">
            {liveTranscript.length === 0 ? (
              <Empty message="No transcript yet. Start capture and play audio from your system." />
            ) : (
              <div className="space-y-2">
                {liveTranscript.slice(-100).map((segment, index) => (
                  <TranscriptSegment
                    key={segment.id}
                    segment={segment}
                    isLatest={index === liveTranscript.slice(-100).length - 1}
                  />
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Insights Section - Collapsible */}
        <section className="border-2 border-lawn-border bg-lawn-panel shadow-brutal">
          <button
            onClick={() => setInsightsOpen(!insightsOpen)}
            className="w-full flex items-center justify-between p-3 border-b-2 border-lawn-border bg-lawn-bg hover:bg-lawn-bg/80 transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className="text-[10px] font-black uppercase tracking-[0.12em] text-lawn-border">
                Insights
              </span>
              <div className="flex gap-1.5">
                {snapshot.formulas.length > 0 && (
                  <span className="px-1.5 py-0.5 text-[9px] font-bold bg-theme-info/20 text-theme-info border border-theme-info/30">
                    {snapshot.formulas.length} formula{snapshot.formulas.length !== 1 ? 's' : ''}
                  </span>
                )}
                {snapshot.needs_review.length > 0 && (
                  <span className="px-1.5 py-0.5 text-[9px] font-bold bg-theme-warning/20 text-theme-warning border border-theme-warning/30">
                    {snapshot.needs_review.length} review
                  </span>
                )}
                {snapshot.suppressed_transcript.length > 0 && (
                  <span className="px-1.5 py-0.5 text-[9px] font-bold bg-stone-200 text-stone-600 border border-stone-300">
                    {snapshot.suppressed_transcript.length} suppressed
                  </span>
                )}
              </div>
            </div>
            {insightsOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>

          {insightsOpen && (
            <div className="p-3 space-y-4">
              {/* Formulas */}
              {snapshot.formulas.length > 0 && (
                <div>
                  <h4 className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest text-lawn-accent mb-2">
                    <Zap size={12} />
                    Formulas Detected
                  </h4>
                  <div className="space-y-2">
                    {snapshot.formulas.slice(-10).reverse().map((formula, index) => (
                      <div
                        key={`${formula.expression}-${index}`}
                        className="border-2 border-lawn-border bg-lawn-dark p-3 text-lawn-bg"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <code className="font-mono text-sm font-bold">{formula.expression}</code>
                          <span className="text-[9px] opacity-60">
                            {formula.timestamp_start.toFixed(1)}s
                          </span>
                        </div>
                        {formula.context && (
                          <p className="text-[11px] opacity-80">{formula.context}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Review Flags */}
              {snapshot.needs_review.length > 0 && (
                <div>
                  <h4 className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest text-theme-warning mb-2">
                    <AlertCircle size={12} />
                    Needs Review
                  </h4>
                  <div className="space-y-2">
                    {snapshot.needs_review.slice(-10).reverse().map((segment) => (
                      <div
                        key={segment.id}
                        className="border-2 border-theme-warning bg-theme-warning/10 p-3"
                      >
                        <p className="text-sm font-bold text-lawn-border">
                          {segment.display_text || segment.text}
                        </p>
                        {segment.review_reasons.length > 0 && (
                          <p className="mt-1 text-[10px] font-bold uppercase tracking-wider text-theme-warning">
                            {segment.review_reasons.join(' · ')}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Suppressed */}
              {snapshot.suppressed_transcript.length > 0 && (
                <div>
                  <h4 className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest text-stone-500 mb-2">
                    <Filter size={12} />
                    Suppressed Segments
                  </h4>
                  <div className="space-y-2">
                    {snapshot.suppressed_transcript.slice(-10).reverse().map((segment) => (
                      <div
                        key={segment.id}
                        className="border border-stone-300 bg-stone-100 p-2 opacity-60"
                      >
                        <p className="text-xs text-stone-600">{segment.display_text || segment.text}</p>
                        {segment.suppression_reasons.length > 0 && (
                          <p className="mt-1 text-[9px] uppercase text-stone-400">
                            {segment.suppression_reasons.join(' · ')}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {snapshot.formulas.length === 0 && snapshot.needs_review.length === 0 && snapshot.suppressed_transcript.length === 0 && (
                <p className="text-sm text-stone-400 text-center py-4">No insights available yet</p>
              )}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function StatusBadge({ status }: { status: string }) {
  const getStyles = () => {
    switch (status) {
      case 'running':
        return 'bg-theme-success text-lawn-bg border-theme-success';
      case 'idle':
      default:
        return 'bg-stone-200 text-stone-600 border-stone-300';
    }
  };

  return (
    <span className={`px-1.5 py-0.5 text-[9px] font-black uppercase tracking-widest border ${getStyles()}`}>
      {status}
    </span>
  );
}

function TranscriptSegment({ segment, isLatest }: { segment: Segment; isLatest: boolean }) {
  const words = segment.words ?? segment.display_text.split(/\s+/).map((text, i, arr) => ({
    text,
    start: segment.start + (i / arr.length) * (segment.end - segment.start),
    end: segment.start + ((i + 1) / arr.length) * (segment.end - segment.start),
    confidence: segment.confidence,
  }));

  const getLanguageLabel = (code: string): string => {
    const labels: Record<string, string> = {
      hi: 'हि',
      en: 'EN',
      auto: 'AUTO',
    };
    return labels[code] || code.toUpperCase();
  };

  const getLanguageName = (code: string): string => {
    const names: Record<string, string> = {
      hi: 'Hindi',
      en: 'English',
      auto: 'Auto-detect',
    };
    return names[code] || code;
  };

  const getConfidenceColor = (confidence: number): string => {
    if (confidence >= 0.85) return 'bg-theme-success';
    if (confidence >= 0.7) return 'bg-theme-warning';
    return 'bg-theme-error';
  };

  const isHindi = segment.language === 'hi';
  const isWeak = segment.quality_label === 'weak';

  return (
    <article
      className={[
        'border-2 p-2.5 transition-all duration-200',
        'hover:-translate-y-0.5 hover:shadow-brutal-sm',
        isWeak ? 'border-theme-warning bg-theme-warning/10' : 'border-lawn-border bg-lawn-bg',
        isLatest && !segment.is_partial ? 'animate-slide-in' : '',
        segment.is_partial ? 'opacity-70 border-dashed' : '',
      ].join(' ')}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-1.5 pb-1.5 border-b border-lawn-border/20">
        <div className="flex items-center gap-1.5">
          <span
            className={[
              'px-1 py-0.5 text-[8px] font-black uppercase tracking-wider border',
              isHindi ? 'bg-theme-warning/20 text-theme-warning border-theme-warning/30' : 'bg-theme-info/20 text-theme-info border-theme-info/30',
            ].join(' ')}
            title={getLanguageName(segment.language)}
          >
            {getLanguageLabel(segment.language)}
          </span>
          <div className={`w-1.5 h-1.5 rounded-full ${getConfidenceColor(segment.confidence)}`} />
          <span className="text-[10px] font-black text-lawn-border">
            {(segment.confidence * 100).toFixed(0)}%
          </span>
        </div>
        <span className="text-[10px] font-bold text-stone-400">
          {segment.start.toFixed(1)}s - {segment.end.toFixed(1)}s
        </span>
      </div>

      {/* Text */}
      <div className={[
        'text-sm font-bold leading-6 text-lawn-border',
        isHindi ? 'font-sans' : '',
      ].join(' ')}>
        {words.map((word, wordIndex) => (
          <WordToken
            key={`${segment.id}-${wordIndex}`}
            word={word}
            isLatest={isLatest && wordIndex >= words.length - 3}
            wordIndex={wordIndex}
          />
        ))}
        {segment.is_partial && (
          <span className="inline-flex items-center h-4">
            <span className="w-1 h-3 bg-lawn-accent animate-pulse ml-1" />
          </span>
        )}
      </div>

      {isWeak && (
        <div className="mt-1.5 flex items-center gap-1.5">
          <span className="text-[9px] font-black uppercase tracking-wider text-theme-warning">
            weak decode{segment.script_mismatch ? ' · script mismatch' : ''}
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
  const getWordOpacity = (confidence: number): number => {
    if (confidence >= 0.9) return 1;
    if (confidence >= 0.7) return 0.85;
    if (confidence >= 0.5) return 0.7;
    return 0.5;
  };

  return (
    <span
      className={[
        'inline-block transition-all duration-200 text-lawn-border mr-1',
        isLatest ? 'animate-word-in' : '',
      ].join(' ')}
      style={{
        opacity: getWordOpacity(word.confidence),
        animationDelay: isLatest ? `${wordIndex * 30}ms` : '0ms',
      }}
    >
      {word.text}
    </span>
  );
}

function Empty({ message }: { message: string }) {
  return (
    <div className="border-2 border-lawn-border border-dashed bg-lawn-bg/50 p-8 text-center">
      <p className="text-sm font-bold text-stone-400">{message}</p>
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
        danger ? 'bg-theme-error text-lawn-bg border-theme-error' : '',
        accent ? 'bg-theme-success text-lawn-bg border-theme-success' : '',
        warning ? 'bg-theme-warning text-lawn-bg border-theme-warning' : '',
      ].join(' ')}
    >
      <div className="text-[9px] font-black uppercase tracking-widest opacity-70 mb-0.5">{label}</div>
      <div className="text-lg font-black leading-tight">{value}</div>
    </div>
  );
}
