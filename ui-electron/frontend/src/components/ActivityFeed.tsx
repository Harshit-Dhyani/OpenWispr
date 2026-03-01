import type { Health, Segment, SessionSummary } from '../types/api';

type ActivityFeedProps = {
  session: SessionSummary | null;
  transcript: Segment[];
  health?: Health;
};

export function ActivityFeed({ session, transcript, health }: ActivityFeedProps) {
  const acceptedTranscript = transcript
    .filter((segment) => !segment.suppressed && !segment.is_partial)
  const recent = acceptedTranscript.slice(-8).reverse();

  return (
    <aside className="flex flex-col h-auto lg:h-full lg:overflow-hidden border-b-2 lg:border-r-2 lg:border-b-0 border-lawn-border bg-lawn-bg p-4 w-full lg:w-[280px] shrink-0">
      <section className="border-2 border-lawn-border bg-lawn-panel p-5 shadow-brutal text-lawn-border mb-6">
        <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.2em] text-stone-500">
          Session Pulse
        </p>
        <h2 className="font-display text-4xl uppercase tracking-tighter text-lawn-border">
          {session?.title ?? 'No Session'}
        </h2>
        <p className="mt-3 text-sm font-bold leading-6 text-stone-600">
          {session
            ? `Writing to ${session.output_dir}`
            : 'Start a session to stream transcript, review flags, and notes.'}
        </p>
        {health && health.stt_backpressure_state !== 'normal' ? (
          <p className="mt-4 border-[3px] border-theme-warning bg-theme-warning/20 p-3 text-xs font-black uppercase tracking-[0.1em] text-theme-warning shadow-brutal-sm">
            STT backpressure: {health.stt_backpressure_state} · dropped {health.dropped_stt_chunks}
          </p>
        ) : null}
      </section>

      <section className="flex-1 flex flex-col border-2 border-lawn-border bg-lawn-panel p-5 shadow-brutal text-lawn-border overflow-hidden">
        <div className="mb-4 flex items-center justify-between border-b-2 border-lawn-border pb-3">
          <span className="text-[12px] font-black uppercase tracking-[0.1em]">
            Recent Activity
          </span>
          <span className="border-2 border-lawn-border bg-lawn-bg px-2 py-0.5 text-[9px] font-black uppercase tracking-widest text-lawn-border">
            {acceptedTranscript.length}
          </span>
        </div>

        <div className="space-y-3 overflow-y-auto pr-2 custom-scrollbar flex-1">
          {recent.length === 0 ? (
            <Empty message="Transcript events will appear here once capture starts." />
          ) : (
            recent.map((segment) => (
              <article
                key={segment.id}
                className={`border-2 p-3 transition-transform hover:-translate-y-0.5 hover:shadow-brutal-sm ${segment.quality_label === 'weak'
                  ? 'border-lawn-border bg-theme-warning/20 text-theme-warning'
                  : 'border-lawn-border bg-lawn-bg'
                  }`}
              >
                <div className="mb-1 text-[9px] font-black uppercase tracking-widest text-stone-500">
                  {segment.start.toFixed(1)}s - {segment.end.toFixed(1)}s
                </div>
                <div className="line-clamp-2 text-xs font-bold leading-5 text-lawn-border">
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

function Empty({ message }: { message: string }) {
  return (
    <div className="border-2 border-lawn-border bg-lawn-bg/50 p-6 py-10 text-center text-xs font-bold text-stone-500">
      {message}
    </div>
  );
}
