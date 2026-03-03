import { RotateCcw } from 'lucide-react';
import { cn } from './utils';

interface SettingCardProps {
  title: string;
  description?: string;
  children: React.ReactNode;
  changed?: boolean;
  onReset?: () => void;
}

export function SettingCard({
  title,
  description,
  children,
  changed = false,
  onReset,
}: SettingCardProps) {
  return (
    <div className={cn(
      'border-2 p-4 transition-all',
      changed ? 'border-lawn-accent bg-lawn-accent/5' : 'border-lawn-border bg-lawn-panel'
    )}>
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className="text-sm font-bold">{title}</h4>
            {changed && (
              <span className="text-[10px] px-1.5 py-0.5 bg-lawn-accent text-lawn-bg font-bold uppercase">
                Modified
              </span>
            )}
          </div>
          {description && (
            <p className="text-xs text-stone-500 mt-1">{description}</p>
          )}
        </div>
        {changed && onReset && (
          <button
            onClick={onReset}
            className="p-1.5 text-stone-400 hover:text-lawn-accent transition-colors flex-shrink-0"
            title="Reset to default"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        )}
      </div>
      {children}
    </div>
  );
}
