import { Mic, Monitor, Check, Info, Loader2 } from 'lucide-react';
import { useState, useCallback } from 'react';

export type TranscriptionMode = 'hotkey' | 'system';

interface ModeOption {
  id: TranscriptionMode;
  label: string;
  description: string;
  icon: typeof Mic;
  features: string[];
  color: string;
}

const MODE_OPTIONS: ModeOption[] = [
  {
    id: 'hotkey',
    label: 'Hotkey Mode',
    description: 'Activate transcription with a keyboard shortcut. Perfect for quick dictation while working in any application.',
    icon: Mic,
    features: ['Keyboard shortcut activation', 'Auto-inject to any app', 'Floating window preview', 'Instant transcription'],
    color: 'hotkey',
  },
  {
    id: 'system',
    label: 'System Mode',
    description: 'Continuous recording with session management. Ideal for meetings, interviews, and long-form content.',
    icon: Monitor,
    features: ['Continuous recording', 'Session management', 'Multi-format export', 'Auto-segmentation'],
    color: 'system',
  },
];

const MODE_COLOR_CLASSES: Record<string, { border: string; bg: string; bgLight: string; text: string }> = {
  hotkey: {
    border: 'border-lawn-accent',
    bg: 'bg-lawn-accent',
    bgLight: 'bg-lawn-accent/10',
    text: 'text-lawn-accent',
  },
  system: {
    border: 'border-theme-info',
    bg: 'bg-theme-info',
    bgLight: 'bg-theme-info/10',
    text: 'text-theme-info',
  },
};

interface ModeSelectorProps {
  currentMode: TranscriptionMode;
  onModeChange: (mode: TranscriptionMode) => void;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
}

export function ModeSelector({
  currentMode,
  onModeChange,
  disabled = false,
  loading = false,
  className = '',
}: ModeSelectorProps) {
  const [hoveredMode, setHoveredMode] = useState<TranscriptionMode | null>(null);

  const handleModeSelect = useCallback(
    (mode: TranscriptionMode) => {
      if (!disabled && !loading && mode !== currentMode) {
        onModeChange(mode);
      }
    },
    [disabled, loading, currentMode, onModeChange]
  );

  return (
    <div className={`space-y-4 ${className}`} data-testid="mode-selector">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-black uppercase tracking-wider text-lawn-border">
            Transcription Mode
          </h3>
          {loading && (
            <Loader2 className="w-4 h-4 text-lawn-accent animate-spin" />
          )}
        </div>
        <div className="flex items-center gap-1 text-xs text-stone-500">
          <Info className="w-3 h-3" />
          <span>Select your preferred mode</span>
        </div>
      </div>

      {/* Mode Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {MODE_OPTIONS.map((mode) => {
          const Icon = mode.icon;
          const isSelected = currentMode === mode.id;
          const isHovered = hoveredMode === mode.id;

          return (
            <button
              key={mode.id}
              onClick={() => handleModeSelect(mode.id)}
              onMouseEnter={() => setHoveredMode(mode.id)}
              onMouseLeave={() => setHoveredMode(null)}
              disabled={disabled || loading}
              className={`
                relative border-2 p-4 text-left transition-all duration-200
                ${disabled || loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                ${
                  isSelected
                    ? `${MODE_COLOR_CLASSES[mode.color].border} ${MODE_COLOR_CLASSES[mode.color].bgLight}`
                    : 'border-lawn-border bg-lawn-bg hover:border-lawn-border/60'
                }
                ${isHovered && !isSelected && !disabled ? 'shadow-brutal-sm' : ''}
              `}
              aria-pressed={isSelected}
              aria-label={`Select ${mode.label}`}
              data-testid={`mode-option-${mode.id}`}
            >
              {/* Selection Indicator */}
              <div
                className={`
                  absolute top-3 right-3 w-5 h-5 border-2 rounded-full
                  flex items-center justify-center transition-all
                  ${
                    isSelected
                      ? `${MODE_COLOR_CLASSES[mode.color].border} ${MODE_COLOR_CLASSES[mode.color].bg}`
                      : 'border-stone-300 bg-transparent'
                  }
                `}
              >
                {isSelected && <Check className="w-3 h-3 text-lawn-bg" />}
              </div>

              {/* Icon */}
              <div
                className={`
                  w-10 h-10 mb-3 flex items-center justify-center
                  border-2 rounded-sm transition-colors
                  ${
                    isSelected
                      ? `${MODE_COLOR_CLASSES[mode.color].border} ${MODE_COLOR_CLASSES[mode.color].bgLight}`
                      : 'border-lawn-border bg-lawn-panel'
                  }
                `}
              >
                <Icon
                  className={`w-5 h-5 ${
                    isSelected ? MODE_COLOR_CLASSES[mode.color].text : 'text-stone-500'
                  }`}
                />
              </div>

              {/* Label */}
              <h4 className="text-sm font-black uppercase tracking-wide text-lawn-border mb-1">
                {mode.label}
              </h4>

              {/* Description */}
              <p className="text-xs text-stone-500 mb-3 line-clamp-2">
                {mode.description}
              </p>

              {/* Features List */}
              <ul className="space-y-1">
                {mode.features.map((feature, index) => (
                  <li
                    key={index}
                    className={`
                      flex items-center gap-1.5 text-[10px]
                      ${isSelected ? 'text-lawn-border' : 'text-stone-500'}
                    `}
                  >
                    <span
                      className={`
                        w-1 h-1 rounded-full flex-shrink-0
                        ${isSelected ? MODE_COLOR_CLASSES[mode.color].bg : 'bg-stone-300'}
                      `}
                    />
                    {feature}
                  </li>
                ))}
              </ul>

              {/* Active Badge */}
              {isSelected && (
                <div
                  className={`
                    absolute bottom-3 right-3 px-2 py-0.5
                    text-[9px] font-black uppercase
                    ${MODE_COLOR_CLASSES[mode.color].bg} text-lawn-bg
                  `}
                >
                  Active
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Mode Comparison Hint */}
      <div className="flex items-start gap-2 p-3 border border-lawn-border bg-lawn-bg/50">
        <Info className="w-4 h-4 text-stone-500 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-stone-500">
          <strong>Hotkey Mode</strong> is best for quick voice notes and dictation.
          <strong> System Mode</strong> is better for long recordings like meetings or interviews.
          You can switch modes at any time without losing your settings.
        </p>
      </div>
    </div>
  );
}

// Compact version for smaller spaces
interface ModeSelectorCompactProps {
  currentMode: TranscriptionMode;
  onModeChange: (mode: TranscriptionMode) => void;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
}

export function ModeSelectorCompact({
  currentMode,
  onModeChange,
  disabled = false,
  loading = false,
  className = '',
}: ModeSelectorCompactProps) {
  return (
    <div className={`flex items-center gap-2 ${className}`} data-testid="mode-selector-compact">
      {MODE_OPTIONS.map((mode) => {
        const Icon = mode.icon;
        const isSelected = currentMode === mode.id;

        return (
          <button
            key={mode.id}
            onClick={() => !disabled && !loading && onModeChange(mode.id)}
            disabled={disabled || loading}
            className={`
              flex items-center gap-2 px-3 py-2 border-2 text-xs font-bold
              transition-all duration-200
              ${disabled || loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
              ${
                isSelected
                  ? `${MODE_COLOR_CLASSES[mode.color].border} ${MODE_COLOR_CLASSES[mode.color].bgLight} ${MODE_COLOR_CLASSES[mode.color].text}`
                  : 'border-lawn-border bg-lawn-bg text-stone-500 hover:border-lawn-border/60'
              }
            `}
            aria-pressed={isSelected}
            data-testid={`mode-option-compact-${mode.id}`}
          >
            {loading && isSelected ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Icon className="w-3.5 h-3.5" />
            )}
            <span className="uppercase tracking-wide">{mode.label}</span>
            {isSelected && <Check className="w-3 h-3 ml-1" />}
          </button>
        );
      })}
    </div>
  );
}

// Toggle switch version for inline use
interface ModeToggleProps {
  currentMode: TranscriptionMode;
  onModeChange: (mode: TranscriptionMode) => void;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
}

export function ModeToggle({
  currentMode,
  onModeChange,
  disabled = false,
  loading = false,
  className = '',
}: ModeToggleProps) {
  const isHotkey = currentMode === 'hotkey';

  return (
    <div
      className={`flex items-center gap-3 ${className}`}
      data-testid="mode-toggle"
    >
      <span
        className={`text-xs font-bold uppercase tracking-wide ${
          isHotkey ? 'text-lawn-border' : 'text-stone-400'
        }`}
      >
        Hotkey
      </span>

      <button
        onClick={() =>
          !disabled && !loading && onModeChange(isHotkey ? 'system' : 'hotkey')
        }
        disabled={disabled || loading}
        className={`
          relative inline-flex h-6 w-11 items-center rounded-full
          transition-colors focus:outline-none focus:ring-2 focus:ring-lawn-accent focus:ring-offset-2
          ${disabled || loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          ${isHotkey ? 'bg-lawn-accent' : 'bg-theme-info'}
        `}
        aria-label={`Switch to ${isHotkey ? 'System' : 'Hotkey'} mode`}
        data-testid="mode-toggle-button"
      >
        {loading ? (
          <Loader2 className="w-4 h-4 text-white animate-spin mx-auto" />
        ) : (
          <span
            className={`
              inline-block h-4 w-4 transform rounded-full bg-white transition-transform
              ${isHotkey ? 'translate-x-1' : 'translate-x-6'}
            `}
          />
        )}
      </button>

      <span
        className={`text-xs font-bold uppercase tracking-wide ${
          !isHotkey ? 'text-lawn-border' : 'text-stone-400'
        }`}
      >
        System
      </span>
    </div>
  );
}

export default ModeSelector;
