interface NumberInputProps {
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}

export function NumberInput({ value, min, max, step = 1, onChange, disabled = false }: NumberInputProps) {
  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => min !== undefined && value > min && onChange(value - step)}
        disabled={disabled || (min !== undefined && value <= min)}
        className="w-8 h-8 flex items-center justify-center border-2 border-lawn-border bg-lawn-bg hover:bg-lawn-accent/10 disabled:opacity-30 font-bold"
      >
        -
      </button>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        disabled={disabled}
        className="w-20 h-8 text-center border-2 border-lawn-border bg-lawn-bg font-mono text-sm focus:border-lawn-accent focus:outline-none disabled:opacity-50"
      />
      <button
        onClick={() => max !== undefined && value < max && onChange(value + step)}
        disabled={disabled || (max !== undefined && value >= max)}
        className="w-8 h-8 flex items-center justify-center border-2 border-lawn-border bg-lawn-bg hover:bg-lawn-accent/10 disabled:opacity-30 font-bold"
      >
        +
      </button>
    </div>
  );
}
