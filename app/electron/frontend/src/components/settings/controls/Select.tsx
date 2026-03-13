import { ChevronRight } from 'lucide-react';
import { cn } from '../utils';

interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
}

export function Select({ value, options, onChange, disabled = false }: SelectProps) {
  return (
    <div className="relative">
      <select
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          'w-full h-10 px-3 pr-10 border-2 border-lawn-border bg-lawn-bg text-sm font-bold focus:border-lawn-accent focus:outline-none appearance-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed',
          'text-lawn-border'
        )}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} className="bg-lawn-bg text-lawn-border">
            {opt.label}
          </option>
        ))}
      </select>
      <ChevronRight className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 rotate-90 pointer-events-none" />
    </div>
  );
}
