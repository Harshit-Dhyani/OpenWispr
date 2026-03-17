/**
 * FeaturePageShell - Reusable page layout wrapper
 * 
 * Provides consistent header styling for feature pages with eyebrow,
 * title, subtitle, enabled status, action buttons, and summary area.
 */
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
    <div className="flex h-full min-h-0 flex-col overflow-hidden p-2">
      <section className="border-2 border-lawn-border bg-lawn-panel p-3 shadow-brutal">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-3xl border-2 border-lawn-border bg-lawn-bg/60 p-3 shadow-brutal-sm">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-lawn-muted">
              {eyebrow}
            </p>
            <h2 className="mt-1 font-display text-3xl uppercase tracking-tight text-lawn-border">
              {title}
            </h2>
            <p className="mt-2 text-sm leading-5 text-lawn-muted">{subtitle}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {enabledLabel ? (
              <span className="border-2 border-lawn-border bg-lawn-bg px-2 py-1 text-[10px] font-black uppercase tracking-[0.14em] text-lawn-border">
                {enabledLabel}
              </span>
            ) : null}
            {actions}
          </div>
        </div>
        {summary ? <div className="mt-3 border-2 border-lawn-border bg-lawn-bg p-2">{summary}</div> : null}
      </section>
      <div className="mt-2 min-h-0 flex-1 overflow-hidden">{children}</div>
    </div>
  );
}
