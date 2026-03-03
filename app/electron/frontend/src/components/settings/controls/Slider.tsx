interface SliderProps {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
  suffix?: string;
}

export function Slider({ value, min, max, step = 1, onChange, suffix = '' }: SliderProps) {
  const percentage = ((value - min) / (max - min)) * 100;

  return (
    <div className="flex items-center gap-3">
      <div className="relative flex-1 h-2 bg-stone-200 rounded-full">
        <div
          className="absolute h-full bg-lawn-accent rounded-full"
          style={{ width: `${percentage}%` }}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
      </div>
      <span className="text-sm font-mono font-bold min-w-[60px] text-right">
        {value}{suffix}
      </span>
    </div>
  );
}
