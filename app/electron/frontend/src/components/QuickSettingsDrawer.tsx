import type { ReactNode } from 'react';
import { SlidersHorizontal, X } from 'lucide-react';

type QuickSettingsDrawerProps = {
  open: boolean;
  title: string;
  description: string;
  onClose: () => void;
  children: ReactNode;
};

export function QuickSettingsDrawer({
  open,
  title,
  description,
  onClose,
  children,
}: QuickSettingsDrawerProps) {
  return (
    <div
      className={[
        'pointer-events-none fixed inset-y-0 right-0 z-40 flex w-full max-w-[420px] translate-x-full border-l-2 border-lawn-border bg-lawn-panel shadow-brutal transition-transform duration-200 ease-out',
        open ? 'pointer-events-auto translate-x-0' : '',
      ].join(' ')}
    >
      <div className="flex h-full w-full flex-col">
        <div className="flex items-start justify-between gap-3 border-b-2 border-lawn-border bg-lawn-dark p-4 text-white">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.16em] text-lawn-accent">
              <SlidersHorizontal className="h-3.5 w-3.5" />
              Quick settings
            </div>
            <h2 className="mt-2 font-display text-2xl uppercase tracking-tight text-lawn-bg">{title}</h2>
            <p className="mt-2 text-[11px] font-bold leading-5 text-stone-300">{description}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="border-2 border-lawn-bg/20 bg-lawn-bg/10 p-2 text-lawn-bg transition-all hover:bg-lawn-bg hover:text-lawn-border"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4 custom-scrollbar">{children}</div>
      </div>
    </div>
  );
}
