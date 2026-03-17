/**
 * ModeSettings - Settings panel for configuring transcription modes
 * 
 * Provides UI for hotkey mode and system mode settings including model selection,
 * language, audio source, export format, and session save location.
 * 
 * @component
 */
import { useState, useCallback, useEffect } from 'react';
import {
  Mic,
  Monitor,
  HardDrive,
  FileText,
  Languages,
  ToggleRight,
  FolderOpen,
  AlertCircle,
  Loader2,
  Info,
  Keyboard,
} from 'lucide-react';
import type { TranscriptionMode } from './ModeSelector';

// Types for mode-specific settings
export interface HotkeyModeSettings {
  model_name: 'tiny' | 'base' | 'small' | 'medium' | 'large-v3';
  key_combination: string;
  auto_inject: boolean;
  show_floating_window: boolean;
  language: string;
  copy_to_clipboard: boolean;
  hold_mode: boolean;
}

export interface SystemModeSettings {
  model_name: 'tiny' | 'base' | 'small' | 'medium' | 'large-v3';
  audio_source: 'system' | 'microphone' | 'both';
  export_format: 'txt' | 'json' | 'srt' | 'vtt';
  auto_segment: boolean;
  session_save_location: string;
  auto_save_interval: number;
}

interface ModeSettingsProps {
  mode: TranscriptionMode;
  hotkeySettings?: Partial<HotkeyModeSettings>;
  systemSettings?: Partial<SystemModeSettings>;
  onHotkeySettingsChange?: (settings: Partial<HotkeyModeSettings>) => void;
  onSystemSettingsChange?: (settings: Partial<SystemModeSettings>) => void;
  disabled?: boolean;
  className?: string;
}

// Model options
const MODEL_OPTIONS = [
  { value: 'tiny', label: 'Tiny', description: 'Fastest, Lowest Quality', size: '39 MB' },
  { value: 'base', label: 'Base', description: 'Fast', size: '74 MB' },
  { value: 'small', label: 'Small', description: 'Balanced', size: '244 MB' },
  { value: 'medium', label: 'Medium', description: 'Better Quality', size: '769 MB' },
  { value: 'large-v3', label: 'Large v3', description: 'Best Quality', size: '1.55 GB' },
] as const;

// Language options
const LANGUAGE_OPTIONS = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' },
  { value: 'fr', label: 'French' },
  { value: 'de', label: 'German' },
  { value: 'it', label: 'Italian' },
  { value: 'pt', label: 'Portuguese' },
  { value: 'nl', label: 'Dutch' },
  { value: 'ja', label: 'Japanese' },
  { value: 'zh', label: 'Chinese' },
  { value: 'ko', label: 'Korean' },
  { value: 'ru', label: 'Russian' },
];

// Export format options
const EXPORT_FORMATS = [
  { value: 'txt', label: 'Plain Text (.txt)', description: 'Simple text output' },
  { value: 'json', label: 'JSON (.json)', description: 'Structured data with timestamps' },
  { value: 'srt', label: 'Subtitles (.srt)', description: 'Subtitle format with timing' },
  { value: 'vtt', label: 'WebVTT (.vtt)', description: 'Web video text tracks' },
] as const;

// Audio source options
const AUDIO_SOURCES = [
  { value: 'system', label: 'System Audio', description: 'Record computer audio output' },
  { value: 'microphone', label: 'Microphone', description: 'Record from microphone input' },
  { value: 'both', label: 'Both', description: 'Record system audio and microphone' },
] as const;

// Toggle Component
interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
  description?: string;
}

function Toggle({ checked, onChange, disabled, label, description }: ToggleProps) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex-1 min-w-0">
        {label && <div className="text-xs font-bold text-lawn-border">{label}</div>}
        {description && <div className="text-[10px] text-stone-500 mt-0.5">{description}</div>}
      </div>
      <button
        onClick={() => !disabled && onChange(!checked)}
        disabled={disabled}
        role="switch"
        aria-checked={checked}
        aria-label={label}
        className={`
          relative inline-flex h-5 w-9 items-center rounded-full transition-colors flex-shrink-0
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          ${checked ? 'bg-lawn-accent' : 'bg-stone-300'}
        `}
      >
        <span
          className={`
            inline-block h-3 w-3 transform rounded-full bg-white transition-transform
            ${checked ? 'translate-x-5' : 'translate-x-1'}
          `}
        />
      </button>
    </div>
  );
}

// Select Component
interface SelectProps<T extends string> {
  value: T;
  onChange: (value: T) => void;
  options: readonly { value: T; label: string; description?: string; size?: string }[];
  disabled?: boolean;
  icon?: React.ReactNode;
}

function Select<T extends string>({ value, onChange, options, disabled, icon, 'aria-label': ariaLabel }: SelectProps<T> & { 'aria-label'?: string }) {
  return (
    <div className="relative">
      {icon && (
        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400">
          {icon}
        </div>
      )}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        disabled={disabled}
        aria-label={ariaLabel}
        className={`
          w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2.5
          text-sm font-bold text-lawn-border focus:border-lawn-accent focus:outline-none
          disabled:opacity-50 disabled:cursor-not-allowed
          ${icon ? 'pl-10' : ''}
        `}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
            {opt.size ? ` — ${opt.size}` : ''}
          </option>
        ))}
      </select>
    </div>
  );
}

// Setting Section Component
interface SettingSectionProps {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
  className?: string;
}

function SettingSection({ icon, title, children, className = '' }: SettingSectionProps) {
  return (
    <div className={`border border-lawn-border bg-lawn-bg p-3 space-y-3 ${className}`}>
      <div className="flex items-center gap-2 text-lawn-border">
        {icon}
        <h5 className="text-xs font-black uppercase tracking-wide">{title}</h5>
      </div>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

// Hotkey Mode Settings Panel
function HotkeyModePanel({
  settings,
  onChange,
  disabled,
}: {
  settings: Partial<HotkeyModeSettings>;
  onChange: (settings: Partial<HotkeyModeSettings>) => void;
  disabled?: boolean;
}) {
  const [validationError, setValidationError] = useState<string | null>(null);

  const validateHotkey = (combo: string): string | null => {
    if (!combo) return 'Key combination is required';
    const parts = combo.split('+');
    const hasModifier = parts.some(
      (p) => p === 'Control' || p === 'Alt' || p === 'Shift' || p === 'Meta'
    );
    if (!hasModifier) {
      return 'Must include a modifier key (Ctrl, Alt, Shift, or Win)';
    }
    return null;
  };

  const handleHotkeyChange = (value: string) => {
    const error = validateHotkey(value);
    setValidationError(error);
    onChange({ ...settings, key_combination: value });
  };

  return (
    <div className="space-y-4" data-testid="hotkey-mode-panel">
      {/* Model Selection */}
      <SettingSection
        icon={<Mic className="w-4 h-4" />}
        title="Transcription Model"
      >
        <Select
          value={settings.model_name || 'small'}
          onChange={(value) => onChange({ ...settings, model_name: value })}
          options={MODEL_OPTIONS}
          disabled={disabled}
          icon={<Mic className="w-4 h-4" />}
          aria-label="Transcription Model"
        />
        <p className="text-[10px] text-stone-500">
          Choose the speech-to-text model. Larger models provide better accuracy but use more VRAM.
        </p>
      </SettingSection>

      {/* Language Selection */}
      <SettingSection
        icon={<Languages className="w-4 h-4" />}
        title="Language"
      >
        <Select
          value={settings.language || 'auto'}
          onChange={(value) => onChange({ ...settings, language: value })}
          options={LANGUAGE_OPTIONS}
          disabled={disabled}
          icon={<Languages className="w-4 h-4" />}
          aria-label="Language"
        />
      </SettingSection>

      {/* Hotkey Configuration */}
      <SettingSection
        icon={<Keyboard className="w-4 h-4" />}
        title="Activation Hotkey"
      >
        <input
          type="text"
          value={settings.key_combination || ''}
          onChange={(e) => handleHotkeyChange(e.target.value)}
          placeholder="e.g., Ctrl+Shift+T"
          disabled={disabled}
          className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-mono focus:border-lawn-accent focus:outline-none disabled:opacity-50"
        />
        {validationError && (
          <div className="flex items-start gap-1.5 text-error text-xs">
            <AlertCircle className="w-3 h-3 flex-shrink-0 mt-0.5" />
            <span>{validationError}</span>
          </div>
        )}
        <p className="text-[10px] text-stone-500">
          Press this key combination to activate transcription. Include a modifier key (Ctrl, Alt, Shift, or Win).
        </p>
      </SettingSection>

      {/* Quick Toggles */}
      <SettingSection
        icon={<ToggleRight className="w-4 h-4" />}
        title="Quick Settings"
      >
        <div className="space-y-3">
          <Toggle
            checked={settings.auto_inject ?? true}
            onChange={(checked) => onChange({ ...settings, auto_inject: checked })}
            disabled={disabled}
            label="Auto-inject transcription"
            description="Automatically type the transcription into the active application"
          />
          <Toggle
            checked={settings.show_floating_window ?? true}
            onChange={(checked) => onChange({ ...settings, show_floating_window: checked })}
            disabled={disabled}
            label="Show floating window"
            description="Display a preview window during transcription"
          />
          <Toggle
            checked={settings.copy_to_clipboard ?? true}
            onChange={(checked) => onChange({ ...settings, copy_to_clipboard: checked })}
            disabled={disabled}
            label="Copy to clipboard"
            description="Copy transcription to clipboard when finished"
          />
          <Toggle
            checked={settings.hold_mode ?? false}
            onChange={(checked) => onChange({ ...settings, hold_mode: checked })}
            disabled={disabled}
            label="Hold mode"
            description="Hold the hotkey to record, release to stop"
          />
        </div>
      </SettingSection>
    </div>
  );
}

// System Mode Settings Panel
function SystemModePanel({
  settings,
  onChange,
  disabled,
}: {
  settings: Partial<SystemModeSettings>;
  onChange: (settings: Partial<SystemModeSettings>) => void;
  disabled?: boolean;
}) {
  const [saveLocationError, setSaveLocationError] = useState<string | null>(null);
  const [isSelectingFolder, setIsSelectingFolder] = useState(false);

  const handleSelectFolder = async () => {
    if (disabled) return;

    setIsSelectingFolder(true);
    setSaveLocationError(null);

    try {
      // Check if electron API is available
      const electronApi = (window as unknown as { electron?: { showOpenDialog: (options: { properties: string[] }) => Promise<{ canceled: boolean; filePaths: string[] }> } }).electron;
      
      if (electronApi?.showOpenDialog) {
        const result = await electronApi.showOpenDialog({
          properties: ['openDirectory'],
        });

        if (!result.canceled && result.filePaths.length > 0) {
          onChange({ ...settings, session_save_location: result.filePaths[0] });
        }
      } else {
        // Fallback: use a default path or show an error
        setSaveLocationError('Folder selection not available in this environment');
      }
    } catch (err) {
      console.error('Failed to select folder:', err);
      setSaveLocationError('Failed to select folder. Please try again.');
    } finally {
      setIsSelectingFolder(false);
    }
  };

  return (
    <div className="space-y-4" data-testid="system-mode-panel">
      {/* Model Selection */}
      <SettingSection
        icon={<Mic className="w-4 h-4" />}
        title="Transcription Model"
      >
        <Select
          value={settings.model_name || 'small'}
          onChange={(value) => onChange({ ...settings, model_name: value })}
          options={MODEL_OPTIONS}
          disabled={disabled}
          icon={<Mic className="w-4 h-4" />}
          aria-label="Transcription Model"
        />
        <p className="text-[10px] text-stone-500">
          Choose the speech-to-text model for continuous transcription.
        </p>
      </SettingSection>

      {/* Audio Source */}
      <SettingSection
        icon={<HardDrive className="w-4 h-4" />}
        title="Audio Source"
      >
        <div className="grid grid-cols-1 gap-2">
          {AUDIO_SOURCES.map((source) => (
            <button
              key={source.value}
              onClick={() =>
                onChange({ ...settings, audio_source: source.value })
              }
              disabled={disabled}
              className={`
                flex items-center gap-3 p-3 border-2 text-left transition-all
                ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                ${
                  settings.audio_source === source.value
                    ? 'border-lawn-accent bg-lawn-accent/10'
                    : 'border-lawn-border bg-lawn-bg hover:border-lawn-accent/50'
                }
              `}
            >
              <div
                className={`
                  w-4 h-4 rounded-full border-2 flex items-center justify-center
                  ${
                    settings.audio_source === source.value
                      ? 'border-lawn-accent'
                      : 'border-stone-300'
                  }
                `}
              >
                {settings.audio_source === source.value && (
                  <div className="w-2 h-2 rounded-full bg-lawn-accent" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-bold text-lawn-border">
                  {source.label}
                </div>
                <div className="text-[10px] text-stone-500">{source.description}</div>
              </div>
            </button>
          ))}
        </div>
      </SettingSection>

      {/* Export Format */}
      <SettingSection
        icon={<FileText className="w-4 h-4" />}
        title="Export Format"
      >
        <div className="grid grid-cols-2 gap-2">
          {EXPORT_FORMATS.map((format) => (
            <button
              key={format.value}
              onClick={() =>
                onChange({ ...settings, export_format: format.value })
              }
              disabled={disabled}
              className={`
                p-3 border-2 text-left transition-all
                ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                ${
                  settings.export_format === format.value
                    ? 'border-lawn-accent bg-lawn-accent/10'
                    : 'border-lawn-border bg-lawn-bg hover:border-lawn-accent/50'
                }
              `}
            >
              <div className="text-xs font-bold text-lawn-border">
                {format.label}
              </div>
              <div className="text-[10px] text-stone-500">{format.description}</div>
            </button>
          ))}
        </div>
      </SettingSection>

      {/* Session Save Location */}
      <SettingSection
        icon={<FolderOpen className="w-4 h-4" />}
        title="Session Save Location"
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={settings.session_save_location || ''}
            onChange={(e) =>
              onChange({ ...settings, session_save_location: e.target.value })
            }
            placeholder="Select a folder..."
            disabled={disabled}
            className="flex-1 border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm focus:border-lawn-accent focus:outline-none disabled:opacity-50"
          />
          <button
            onClick={handleSelectFolder}
            disabled={disabled || isSelectingFolder}
            className="px-4 py-2 border-2 border-lawn-border bg-lawn-bg hover:bg-lawn-accent hover:text-lawn-bg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSelectingFolder ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <FolderOpen className="w-4 h-4" />
            )}
          </button>
        </div>
        {saveLocationError && (
          <div className="flex items-start gap-1.5 text-error text-xs">
            <AlertCircle className="w-3 h-3 flex-shrink-0 mt-0.5" />
            <span>{saveLocationError}</span>
          </div>
        )}
      </SettingSection>

      {/* Auto-segment Toggle */}
      <SettingSection
        icon={<ToggleRight className="w-4 h-4" />}
        title="Processing Options"
      >
        <div className="space-y-3">
          <Toggle
            checked={settings.auto_segment ?? true}
            onChange={(checked) => onChange({ ...settings, auto_segment: checked })}
            disabled={disabled}
            label="Auto-segment"
            description="Automatically split transcription into logical segments"
          />
        </div>
      </SettingSection>
    </div>
  );
}

// Main ModeSettings Component
export function ModeSettings({
  mode,
  hotkeySettings = {},
  systemSettings = {},
  onHotkeySettingsChange,
  onSystemSettingsChange,
  disabled = false,
  className = '',
}: ModeSettingsProps) {
  const [isTransitioning, setIsTransitioning] = useState(false);

  // Handle mode transition animation
  useEffect(() => {
    setIsTransitioning(true);
    const timer = setTimeout(() => setIsTransitioning(false), 150);
    return () => clearTimeout(timer);
  }, [mode]);

  const handleHotkeyChange = useCallback(
    (settings: Partial<HotkeyModeSettings>) => {
      onHotkeySettingsChange?.(settings);
    },
    [onHotkeySettingsChange]
  );

  const handleSystemChange = useCallback(
    (settings: Partial<SystemModeSettings>) => {
      onSystemSettingsChange?.(settings);
    },
    [onSystemSettingsChange]
  );

  return (
    <div
      className={`
        border-2 border-lawn-border bg-lawn-panel p-4
        transition-opacity duration-150
        ${isTransitioning ? 'opacity-50' : 'opacity-100'}
        ${className}
      `}
      data-testid="mode-settings"
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        {mode === 'hotkey' ? (
          <Mic className="w-5 h-5 text-lawn-accent" />
        ) : (
          <Monitor className="w-5 h-5 text-theme-info" />
        )}
        <h3 className="text-sm font-black uppercase tracking-wider text-lawn-border">
          {mode === 'hotkey' ? 'Hotkey Mode Settings' : 'System Mode Settings'}
        </h3>
      </div>

      {/* Mode-specific panels */}
      {mode === 'hotkey' ? (
        <HotkeyModePanel
          settings={hotkeySettings}
          onChange={handleHotkeyChange}
          disabled={disabled}
        />
      ) : (
        <SystemModePanel
          settings={systemSettings}
          onChange={handleSystemChange}
          disabled={disabled}
        />
      )}

      {/* Footer note */}
      <div className="mt-4 pt-3 border-t border-lawn-border">
        <div className="flex items-start gap-2 text-xs text-stone-500">
          <Info className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <p>
            These settings are saved automatically. Changes will take effect on your next
            transcription session.
          </p>
        </div>
      </div>
    </div>
  );
}

export default ModeSettings;
