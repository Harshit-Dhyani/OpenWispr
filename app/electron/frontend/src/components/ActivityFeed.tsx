import type { Health, Segment, SessionSummary } from '../types/api';

type ActivityFeedProps = {
  session: SessionSummary | null;
  transcript: Segment[];
  health?: Health;
  variant?: 'sidebar' | 'inline';
};

export function ActivityFeed({ session, transcript, health, variant = 'sidebar' }: ActivityFeedProps) {
  const acceptedTranscript = transcript
    .filter((segment) => !segment.suppressed && !segment.is_partial)
  const recent = acceptedTranscript.slice(-8).reverse();

  const isInline = variant === 'inline';

  return (
    <aside className={[
      "flex shrink-0 transition-all duration-300",
      isInline
        ? "flex-row h-auto w-full border-b-2 border-lawn-border bg-lawn-bg p-3 gap-3 overflow-x-auto"
        : "flex-col h-full min-h-0 border-lawn-border bg-lawn-bg p-4 w-full overflow-hidden"
    ].join(' ')}>
      {/* Session Pulse - Inline: horizontal card, Sidebar: vertical block */}
      <section className={[
        "border-2 border-lawn-border bg-lawn-panel shadow-brutal text-lawn-border",
        isInline ? "p-3 min-w-[200px] max-w-[280px]" : "p-5 mb-6"
      ].join(' ')}>
        <p className={["font-bold uppercase tracking-[0.2em] text-stone-500", isInline ? "mb-1 text-[10px]" : "mb-2 text-[11px]"].join(' ')}>
          Session Pulse
        </p>
        <h2 className={["font-display uppercase tracking-tighter text-lawn-border truncate", isInline ? "text-xl" : "text-4xl"].join(' ')}>
          {session?.title ?? 'No Session'}
        </h2>
        <p className={["font-bold text-stone-600 truncate", isInline ? "mt-1 text-[10px] leading-4" : "mt-3 text-sm leading-6"].join(' ')}>
          {session
            ? `Writing to ${session.output_dir}`
            : (isInline ? 'Start a session to begin.' : 'Start a session to stream transcript, review flags, and notes.')}
        </p>
        {health && health.stt_backpressure_state !== 'normal' && !isInline ? (
          <p className="mt-4 border-[3px] border-theme-warning bg-theme-warning/20 p-3 text-xs font-black uppercase tracking-[0.1em] text-theme-warning shadow-brutal-sm">
            STT backpressure: {health.stt_backpressure_state} · dropped {health.dropped_stt_chunks}
          </p>
        ) : null}
      </section>

      {/* Recent Activity - Inline: horizontal scroll, Sidebar: vertical scroll */}
      <section className={[
        "border-2 border-lawn-border bg-lawn-panel shadow-brutal text-lawn-border",
        isInline ? "flex-1 p-3 min-w-0" : "flex-1 flex flex-col p-5 overflow-hidden"
      ].join(' ')}>
        <div className={["flex items-center justify-between border-b-2 border-lawn-border", isInline ? "mb-2 pb-2" : "mb-4 pb-3"].join(' ')}>
          <span className={["font-black uppercase tracking-[0.1em]", isInline ? "text-[10px]" : "text-[12px]"].join(' ')}>
            Recent Activity
          </span>
          <span className="border-2 border-lawn-border bg-lawn-bg px-2 py-0.5 text-[9px] font-black uppercase tracking-widest text-lawn-border">
            {acceptedTranscript.length}
          </span>
        </div>

        <div className={[
          isInline ? "flex gap-2 overflow-x-auto pr-2 custom-scrollbar" : "space-y-3 overflow-y-auto pr-2 custom-scrollbar flex-1"
        ].join(' ')}>
          {recent.length === 0 ? (
            <Empty message={isInline ? "No activity yet." : "Transcript events will appear here once capture starts."} isInline={isInline} />
          ) : (
            recent.map((segment) => (
              <article
                key={segment.id}
                className={[
                  "border-2 p-3 transition-transform hover:-translate-y-0.5 hover:shadow-brutal-sm shrink-0",
                  segment.quality_label === 'weak'
                    ? 'border-lawn-border bg-theme-warning/20 text-theme-warning'
                    : 'border-lawn-border bg-lawn-bg',
                  isInline ? "min-w-[180px] max-w-[240px]" : ""
                ].join(' ')}
              >
                <div className="mb-1 text-[9px] font-black uppercase tracking-widest text-stone-500">
                  {segment.start.toFixed(1)}s - {segment.end.toFixed(1)}s
                </div>
                <div className={["font-bold leading-5 text-lawn-border", isInline ? "line-clamp-1 text-[11px]" : "line-clamp-2 text-xs"].join(' ')}>
                  {segment.display_text || segment.text}
                </div>
              </article>
            ))
          )}
        </div>
      </section>
    </aside>
  );
}

function Empty({ message, isInline = false }: { message: string; isInline?: boolean }) {
  return (
    <div className={[
      "border-2 border-lawn-border bg-lawn-bg/50 text-center text-xs font-bold text-stone-500",
      isInline ? "p-3 min-w-[150px]" : "p-6 py-10"
    ].join(' ')}>
      {message}
    </div>
  );
}
