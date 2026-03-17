/**
 * TranscriptPanels - Collection of panel components for transcript display
 * 
 * Exports CombinedPanel, CoachPanel, ReviewPanel, FormulasPanel, SuppressedPanel,
 * ErrorsPanel, SessionPanel, and EmptyState for rendering different transcript views.
 * 
 * @component
 */
import { AlertCircle, Filter, Sigma, Sparkles, TriangleAlert } from 'lucide-react';
import type { CoachResult, Formula, Segment, SessionSummary } from '../types/api';
import { RENDERER_STRINGS } from '../strings/en';

const MAIN_CONTENT_STRINGS = RENDERER_STRINGS.mainContent;

export function CombinedTimelineCard({ combinedText }: { combinedText: string }) {
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
}

export function CombinedPanel({ combinedText }: { combinedText: string }) {
  if (!combinedText) {
    return (
      <div className="border-2 border-dashed border-lawn-border bg-lawn-bg/50 p-6 text-center">
        <p className="text-sm font-black text-lawn-border">{MAIN_CONTENT_STRINGS.combined.emptyTitle}</p>
        <p className="mt-2 text-xs font-bold leading-5 text-lawn-muted">{MAIN_CONTENT_STRINGS.combined.emptyBody}</p>
      </div>
    );
  }

  return (
    <article className="border-2 border-lawn-border bg-lawn-bg p-3">
      <div className="mb-2 text-[10px] font-black uppercase tracking-[0.12em] text-lawn-muted">
        {MAIN_CONTENT_STRINGS.combined.panelTitle}
      </div>
      <p className="text-sm font-bold leading-6 text-lawn-border">{combinedText}</p>
    </article>
  );
}

export function CoachPanel({
  coachResult,
  coachStatus,
  coachDisplaySource,
  coachError,
  originalText,
  pasteText,
  showDiff,
}: {
  coachResult: CoachResult | null;
  coachStatus: 'disabled' | 'queued' | 'running' | 'failed' | 'fallback' | 'cache_hit' | 'generated' | 'success' | null;
  coachDisplaySource: 'coach' | 'fallback' | 'faithful' | null;
  coachError: string | null;
  originalText: string | null;
  pasteText: string | null;
  showDiff: boolean;
}) {
  if (!coachResult && !originalText && !pasteText && !coachStatus && !coachError) {
    return (
      <div className="border-2 border-dashed border-lawn-border bg-lawn-bg/50 p-6 text-center">
        <p className="text-sm font-black text-lawn-border">No coach result yet</p>
        <p className="mt-2 text-xs font-bold leading-5 text-lawn-muted">Stop a microphone dictation to generate a polished paragraph and coaching notes here.</p>
      </div>
    );
  }

  const heading =
    coachStatus === 'queued'
      ? 'Coach Queued'
      : coachStatus === 'running'
        ? 'Coach Running'
        : coachStatus === 'generated' || coachStatus === 'cache_hit' || coachStatus === 'success'
          ? 'Coach Result'
          : coachStatus === 'fallback'
            ? 'Fallback Output'
            : coachStatus === 'failed'
              ? 'Coach Failed'
              : 'Transcript Ready';
  const summaryText =
    coachResult?.polished ||
    pasteText ||
    originalText ||
    (coachStatus === 'queued'
      ? 'Coach queued. Preparing prompt and transcript payload.'
      : coachStatus === 'running'
        ? 'Coach is running. This can take a few seconds depending on the local runtime.'
        : coachStatus === 'failed'
          ? 'Coach could not finish. The faithful transcript is still available below.'
          : '');

  return (
    <div className="space-y-3">
      <article className="border-2 border-lawn-border bg-lawn-bg p-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Sparkles size={14} className="text-lawn-accent" />
            <span className="text-[10px] font-black uppercase tracking-[0.12em] text-lawn-border">{heading}</span>
          </div>
          <span className="border border-lawn-border px-2 py-1 text-[9px] font-black uppercase tracking-widest text-lawn-muted">
            {(coachDisplaySource || 'faithful').replace(/_/g, ' ')}
          </span>
        </div>
        <p className="text-sm font-bold leading-6 text-lawn-border">{summaryText}</p>
        {coachStatus === 'fallback' ? (
          <p className="mt-2 text-xs font-bold text-lawn-muted">Coach was unavailable, so this panel is showing deterministic fallback output instead.</p>
        ) : null}
        {coachError ? <p className="mt-2 text-xs font-bold text-theme-warning">Coach error: {coachError}</p> : null}
      </article>
      <article className="border-2 border-lawn-border bg-lawn-panel p-3">
        <div className="mb-2 text-[10px] font-black uppercase tracking-[0.12em] text-lawn-muted">Original</div>
        <p className="text-xs leading-5 text-lawn-border/80">{originalText || coachResult?.original || ''}</p>
      </article>
      {showDiff && coachResult?.diff?.length ? (
        <article className="border-2 border-lawn-border bg-lawn-panel p-3">
          <div className="mb-2 text-[10px] font-black uppercase tracking-[0.12em] text-lawn-muted">
            {MAIN_CONTENT_STRINGS.coach.diffTitle}
          </div>
          <div className="space-y-2">
            {coachResult.diff.map((entry, index) => (
              <div
                key={`${entry.op}-${entry.start}-${entry.end}-${index}`}
                className="border-2 border-lawn-border bg-lawn-bg p-2"
              >
                <div className="text-[9px] font-black uppercase tracking-widest text-lawn-accent">
                  {MAIN_CONTENT_STRINGS.coach.diffOps[entry.op]}
                </div>
                <p className="mt-1 text-[11px] leading-5 text-lawn-muted">
                  {MAIN_CONTENT_STRINGS.coach.fromLabel}:{' '}
                  <span className="font-bold text-lawn-border">{entry.from || MAIN_CONTENT_STRINGS.coach.emptyToken}</span>
                </p>
                <p className="text-[11px] leading-5 text-lawn-muted">
                  {MAIN_CONTENT_STRINGS.coach.toLabel}:{' '}
                  <span className="font-bold text-lawn-border">{entry.to || MAIN_CONTENT_STRINGS.coach.emptyToken}</span>
                </p>
              </div>
            ))}
          </div>
        </article>
      ) : null}
      {coachResult?.tips?.length ? (
        <article className="border-2 border-lawn-border bg-lawn-panel p-3">
          <div className="mb-2 text-[10px] font-black uppercase tracking-[0.12em] text-lawn-muted">Tips</div>
          <div className="space-y-2">
            {coachResult.tips.map((tip, index) => (
              <p key={`${tip}-${index}`} className="text-xs font-bold leading-5 text-lawn-border">{tip}</p>
            ))}
          </div>
        </article>
      ) : null}
      {coachResult?.mistakes?.length ? (
        <article className="border-2 border-lawn-border bg-lawn-panel p-3">
          <div className="mb-2 text-[10px] font-black uppercase tracking-[0.12em] text-lawn-muted">Mistakes</div>
          <div className="space-y-3">
            {coachResult.mistakes.map((mistake, index) => (
              <div key={`${mistake.example}-${index}`} className="border-2 border-lawn-border bg-lawn-bg p-2">
                <div className="text-[10px] font-black uppercase tracking-widest text-lawn-accent">{mistake.type}</div>
                <p className="mt-1 text-xs font-bold text-lawn-border">{mistake.fix}</p>
                <p className="mt-1 text-[11px] leading-5 text-lawn-muted">{mistake.why}</p>
              </div>
            ))}
          </div>
        </article>
      ) : null}
    </div>
  );
}

export function ReviewPanel({ segments }: { segments: Segment[] }) {
  if (segments.length === 0) {
    return (
      <div className="border-2 border-dashed border-lawn-border bg-lawn-bg/50 p-6 text-center">
        <p className="text-sm font-black text-lawn-border">No review flags yet</p>
        <p className="mt-2 text-xs font-bold leading-5 text-lawn-muted">Segments that look uncertain, contradictory, or formula-heavy will appear here.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {segments.slice(-16).reverse().map((segment) => (
        <article key={segment.id} className="border-2 border-theme-warning bg-theme-warning/10 p-2 overflow-hidden">
          <div className="mb-1 flex items-center gap-2 text-theme-warning truncate">
            <AlertCircle size={12} />
            <span className="text-[9px] font-black uppercase tracking-widest">
              {segment.start.toFixed(1)}s - {segment.end.toFixed(1)}s
            </span>
          </div>
          <p className="text-sm font-bold text-lawn-border break-words">{segment.display_text || segment.text}</p>
          {segment.review_reasons.length > 0 && (
            <p className="mt-2 text-[10px] font-black uppercase tracking-wider text-theme-warning break-words">
              {segment.review_reasons.join(' · ')}
            </p>
          )}
        </article>
      ))}
    </div>
  );
}

export function FormulasPanel({ formulas }: { formulas: Formula[] }) {
  if (formulas.length === 0) {
    return (
      <div className="border-2 border-dashed border-lawn-border bg-lawn-bg/50 p-6 text-center">
        <p className="text-sm font-black text-lawn-border">No formulas extracted yet</p>
        <p className="mt-2 text-xs font-bold leading-5 text-lawn-muted">Formula-like expressions and symbolic patterns will appear here with context and timestamps.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {formulas.slice(-16).reverse().map((formula, index) => (
        <article key={`${formula.expression}-${index}`} className="border-2 border-lawn-border bg-lawn-dark p-2 text-lawn-bg overflow-hidden">
          <div className="mb-1 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <Sigma size={12} className="text-lawn-accent shrink-0" />
              <code className="font-mono text-sm font-bold break-all truncate">{formula.expression}</code>
            </div>
            <span className="text-[9px] font-black uppercase tracking-wider opacity-70 shrink-0">
              {formula.timestamp_start.toFixed(1)}s
            </span>
          </div>
          <p className="text-[11px] leading-5 opacity-80 break-words">{formula.context || 'Context unavailable.'}</p>
        </article>
      ))}
    </div>
  );
}

export function SuppressedPanel({ segments }: { segments: Segment[] }) {
  if (segments.length === 0) {
    return (
      <div className="border-2 border-dashed border-lawn-border bg-lawn-bg/50 p-6 text-center">
        <p className="text-sm font-black text-lawn-border">No suppressed segments</p>
        <p className="mt-2 text-xs font-bold leading-5 text-lawn-muted">Low-quality or obviously garbled segments will appear here instead of polluting the main transcript.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {segments.slice(-16).reverse().map((segment) => (
        <article key={segment.id} className="border-2 border-lawn-soft bg-lawn-soft p-2 overflow-hidden">
          <div className="mb-1 flex items-center gap-2 text-lawn-muted">
            <Filter size={12} />
            <span className="text-[9px] font-black uppercase tracking-widest">
              {segment.start.toFixed(1)}s - {segment.end.toFixed(1)}s
            </span>
          </div>
          <p className="text-xs font-bold text-lawn-muted-strong break-words">{segment.display_text || segment.text}</p>
          {segment.suppression_reasons.length > 0 && (
            <p className="mt-2 text-[10px] font-black uppercase tracking-wider text-lawn-muted break-words">
              {segment.suppression_reasons.join(' · ')}
            </p>
          )}
        </article>
      ))}
    </div>
  );
}

export function ErrorsPanel({ error, warning }: { error: string | null; warning: string | null }) {
  if (!error && !warning) {
    return (
      <div className="border-2 border-dashed border-lawn-border bg-lawn-bg/50 p-6 text-center">
        <p className="text-sm font-black text-lawn-border">No active errors</p>
        <p className="mt-2 text-xs font-bold leading-5 text-lawn-muted">Runtime warnings and backend errors will appear here with the latest status.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {warning && (
        <article className="border-2 border-theme-warning bg-theme-warning/10 p-2 overflow-hidden">
          <div className="mb-1 flex items-center gap-2 text-theme-warning">
            <TriangleAlert size={12} />
            <span className="text-[9px] font-black uppercase tracking-widest">Warning</span>
          </div>
          <p className="text-sm font-bold text-lawn-border break-words">{warning}</p>
        </article>
      )}
      {error && (
        <article className="border-2 border-theme-error bg-theme-error/10 p-2 overflow-hidden">
          <div className="mb-1 flex items-center gap-2 text-theme-error">
            <AlertCircle size={12} />
            <span className="text-[9px] font-black uppercase tracking-widest">Error</span>
          </div>
          <p className="text-sm font-bold text-lawn-border break-words">{error}</p>
        </article>
      )}
    </div>
  );
}

export function SessionPanel({
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

export function InspectorCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-2 border-lawn-border bg-lawn-bg p-3">
      <div className="text-[9px] font-black uppercase tracking-widest text-lawn-muted">{label}</div>
      <div className="mt-1 text-sm font-bold leading-5 text-lawn-border break-words">{value}</div>
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="border-2 border-dashed border-lawn-border bg-lawn-bg/50 p-6 text-center">
      <p className="text-sm font-black text-lawn-border">{title}</p>
      <p className="mt-2 text-xs font-bold leading-5 text-lawn-muted">{body}</p>
    </div>
  );
}
