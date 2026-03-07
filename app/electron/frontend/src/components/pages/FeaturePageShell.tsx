import type { ReactNode } from 'react';

type FeaturePageShellProps = {
  eyebrow: string;
  title: string;
  subtitle: string;
  enabledLabel?: string;
  actions?: ReactNode;
  summary?: ReactNode;
  children: ReactNode;
};

export function FeaturePageShell({
  eyebrow,
  title,
  subtitle,
  enabledLabel,
  actions,
  summary,
  children,
}: FeaturePageShellProps) {
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden p-4">
      <section className="border-2 border-lawn-border bg-lawn-panel p-4 shadow-brutal">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl border-2 border-lawn-border bg-lawn-bg/60 p-4 shadow-brutal-sm">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-lawn-muted">
              {eyebrow}
            </p>
            <h2 className="mt-2 font-display text-4xl uppercase tracking-tight text-lawn-border">
              {title}
            </h2>
            <p className="mt-3 text-sm leading-6 text-lawn-muted">{subtitle}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {enabledLabel ? (
              <span className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-border">
                {enabledLabel}
              </span>
            ) : null}
            {actions}
          </div>
        </div>
        {summary ? <div className="mt-4 border-2 border-lawn-border bg-lawn-bg p-3">{summary}</div> : null}
      </section>
      <div className="mt-4 min-h-0 flex-1 overflow-hidden">{children}</div>
    </div>
  );
}
