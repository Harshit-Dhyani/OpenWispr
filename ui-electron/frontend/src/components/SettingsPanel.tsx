import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Settings,
  Mic,
  Volume2,
  Keyboard,
  Cpu,
  Search,
  X,
  RotateCcw,
  Download,
  Upload,
  Save,
  AlertCircle,
  Info,
  ChevronRight,
  Monitor,
  HardDrive,
  Zap,
  Sliders,
  Activity,
  Filter,
  Gauge,
  Layers,
  Loader2,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import type {
  SettingsState,
  HotkeyConfig,
  SystemProfile,
  OptimizationPreset,
} from '../types/api';

// Utility for Tailwind class merging
function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ============================================
// Types
// ============================================

type SettingsCategory = 'general' | 'transcription' | 'audio' | 'hotkey' | 'advanced';

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

// ============================================
// Default Settings
// ============================================

const DEFAULT_SETTINGS: SettingsState = {
  general: {
    defaultSessionTitle: 'New Session',
    defaultLanguage: 'auto',
    exportDirectory: '',
    autoSaveInterval: 30,
    showNotifications: true,
    minimizeToTray: true,
    startupWithSystem: false,
    theme: 'light',
  },
  transcription: {
    model_name: 'medium',
    compute_type: 'float16',
    chunk_duration: 1.6,
    overlap_ratio: 0.2,
    vad_enabled: true,
    vad_threshold_db: -40,
    confidence_threshold: 0.6,
    enable_filler_filter: true,
    enable_hallucination_filter: true,
    min_segment_length: 0.5,
    max_workers: 4,
    use_parallel_processing: true,
    preload_model: true,
    hotkey_optimized: false,
    beam_size: 5,
    best_of: 5,
    patience: 1.0,
    temperature: 0.0,
  },
  audio: {
    defaultDeviceId: 'default',
    sampleRate: 16000,
    vadEnabled: true,
    vadThresholdDb: -40,
    noiseFiltering: true,
    echoCancellation: true,
    autoGainControl: true,
  },
  hotkey: {
    enabled: true,
    key_combination: 'Ctrl+Shift+T',
    hold_mode: false,
    auto_inject: true,
    show_floating_window: true,
    floating_window_position: 'bottom-right',
    record_on_start: true,
    stop_on_release: false,
    copy_to_clipboard: true,
  },
  advanced: {
    debugMode: false,
    logLevel: 'INFO',
    enableMetrics: true,
    maxLogFiles: 10,
    experimentalStem: false,
    experimentalGpuAccel: true,
  },
  version: 1,
};

// ============================================
// Presets
// ============================================

const PRESETS: OptimizationPreset[] = [
  {
    id: 'maximum',
    name: 'Maximum Quality',
    description: 'Best accuracy with largest model, slower processing',
    icon: 'award',
    recommended_for: ['High-end GPU', 'Accuracy critical'],
    settings_override: {
      model_name: 'large-v3',
      compute_type: 'float16',
      beam_size: 10,
      best_of: 10,
      patience: 2.0,
      temperature: 0.0,
      vad_threshold_db: -45,
      confidence_threshold: 0.7,
    },
  },
  {
    id: 'balanced',
    name: 'Balanced',
    description: 'Good balance of speed and accuracy',
    icon: 'scale',
    recommended_for: ['Most systems', 'General use'],
    settings_override: {
      model_name: 'medium',
      compute_type: 'float16',
      beam_size: 5,
      best_of: 5,
      patience: 1.0,
      temperature: 0.0,
      vad_threshold_db: -40,
      confidence_threshold: 0.6,
    },
  },
  {
    id: 'fast',
    name: 'Fast',
    description: 'Prioritizes speed over accuracy',
    icon: 'zap',
    recommended_for: ['Real-time use', 'Lower-end hardware'],
    settings_override: {
      model_name: 'small',
      compute_type: 'int8',
      beam_size: 3,
      best_of: 3,
      patience: 0.8,
      temperature: 0.2,
      vad_threshold_db: -35,
      confidence_threshold: 0.5,
      chunk_duration: 1.0,
    },
  },
  {
    id: 'low_memory',
    name: 'Low Memory',
    description: 'Minimal resource usage for limited systems',
    icon: 'feather',
    recommended_for: ['8GB RAM or less', 'CPU only'],
    settings_override: {
      model_name: 'tiny',
      compute_type: 'int8',
      beam_size: 1,
      best_of: 1,
      patience: 0.5,
      temperature: 0.4,
      vad_threshold_db: -30,
      confidence_threshold: 0.4,
      chunk_duration: 0.8,
      use_parallel_processing: false,
      preload_model: false,
    },
  },
];

// ============================================
// Categories Configuration
// ============================================

const CATEGORIES: {
  id: SettingsCategory;
  label: string;
  icon: React.ElementType;
  description: string;
}[] = [
  {
    id: 'general',
    label: 'General',
    icon: Settings,
    description: 'Session defaults, language, export location',
  },
  {
    id: 'transcription',
    label: 'Transcription',
    icon: Mic,
    description: 'Model, quality, performance settings',
  },
  {
    id: 'audio',
    label: 'Audio',
    icon: Volume2,
    description: 'VAD, noise filtering, audio devices',
  },
  {
    id: 'hotkey',
    label: 'Hotkey',
    icon: Keyboard,
    description: 'Global hotkey configuration',
  },
  {
    id: 'advanced',
    label: 'Advanced',
    icon: Cpu,
    description: 'Expert settings, developer options',
  },
];

// ============================================
// Utility Components
// ============================================

function Toggle({
  checked,
  onChange,
  disabled = false,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={() => !disabled && onChange(!checked)}
      disabled={disabled}
      className={cn(
        'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-lawn-accent focus:ring-offset-2',
        checked ? 'bg-lawn-accent' : 'bg-stone-300',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
    >
      <span
        className={cn(
          'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
          checked ? 'translate-x-6' : 'translate-x-1'
        )}
      />
    </button>
  );
}

function Slider({
  value,
  min,
  max,
  step = 1,
  onChange,
  suffix = '',
}: {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
  suffix?: string;
}) {
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

function NumberInput({
  value,
  min,
  max,
  step = 1,
  onChange,
}: {
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => min !== undefined && value > min && onChange(value - step)}
        disabled={min !== undefined && value <= min}
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
        className="w-20 h-8 text-center border-2 border-lawn-border bg-lawn-bg font-mono text-sm focus:border-lawn-accent focus:outline-none"
      />
      <button
        onClick={() => max !== undefined && value < max && onChange(value + step)}
        disabled={max !== undefined && value >= max}
        className="w-8 h-8 flex items-center justify-center border-2 border-lawn-border bg-lawn-bg hover:bg-lawn-accent/10 disabled:opacity-30 font-bold"
      >
        +
      </button>
    </div>
  );
}

function Select({
  value,
  options,
  onChange,
  disabled = false,
}: {
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
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

function SettingCard({
  title,
  description,
  children,
  changed = false,
  onReset,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  changed?: boolean;
  onReset?: () => void;
}) {
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

function SectionHeader({
  title,
  icon: Icon,
  description,
}: {
  title: string;
  icon: React.ElementType;
  description?: string;
}) {
  return (
    <div className="mb-6 pb-4 border-b-2 border-lawn-border">
      <div className="flex items-center gap-3 mb-2">
        <Icon className="w-5 h-5 text-lawn-accent" />
        <h3 className="text-lg font-black uppercase tracking-wider">{title}</h3>
      </div>
      {description && (
        <p className="text-sm text-stone-500">{description}</p>
      )}
    </div>
  );
}

// ============================================
// Hardware Profile Display
// ============================================

function HardwareProfileDisplay({ profile }: { profile?: SystemProfile }) {
  if (!profile) {
    return (
      <div className="border-2 border-lawn-border bg-lawn-panel p-4">
        <div className="flex items-center gap-2 text-stone-500">
          <Monitor className="w-5 h-5" />
          <span className="text-sm">No hardware profile available</span>
        </div>
      </div>
    );
  }

  return (
    <div className="border-2 border-lawn-border bg-lawn-panel p-4">
      <div className="flex items-center gap-2 mb-4">
        <Monitor className="w-5 h-5 text-lawn-accent" />
        <h4 className="text-sm font-black uppercase">System Profile</h4>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="border border-lawn-border bg-lawn-bg p-3">
          <div className="flex items-center gap-2 text-stone-500 mb-1">
            <Cpu className="w-3 h-3" />
            <span className="text-[10px] uppercase font-bold">GPU</span>
          </div>
          <span className="text-xs font-bold block truncate">
            {profile.gpu.available ? profile.gpu.name : 'CPU Only'}
          </span>
          {profile.gpu.available && (
            <span className="text-[10px] text-stone-500">{profile.gpu.vram_gb}GB VRAM</span>
          )}
        </div>
        <div className="border border-lawn-border bg-lawn-bg p-3">
          <div className="flex items-center gap-2 text-stone-500 mb-1">
            <Activity className="w-3 h-3" />
            <span className="text-[10px] uppercase font-bold">CPU</span>
          </div>
          <span className="text-xs font-bold block">{profile.cpu.cores} Cores</span>
          <span className="text-[10px] text-stone-500">{profile.cpu.ram_gb}GB RAM</span>
        </div>
        <div className="border border-lawn-border bg-lawn-bg p-3">
          <div className="flex items-center gap-2 text-stone-500 mb-1">
            <HardDrive className="w-3 h-3" />
            <span className="text-[10px] uppercase font-bold">Storage</span>
          </div>
          <span className="text-xs font-bold block">{profile.storage.free_gb}GB Free</span>
          <span className="text-[10px] text-stone-500">
            {profile.storage.ssd_available ? 'SSD' : 'HDD'}
          </span>
        </div>
        <div className="border border-lawn-border bg-lawn-bg p-3">
          <div className="flex items-center gap-2 text-stone-500 mb-1">
            <Zap className="w-3 h-3" />
            <span className="text-[10px] uppercase font-bold">Recommended</span>
          </div>
          <span className="text-xs font-bold block capitalize">{profile.recommended_quality}</span>
          <span className="text-[10px] text-lawn-accent">Preset: {profile.recommended_preset}</span>
        </div>
      </div>
    </div>
  );
}

// ============================================
// Hotkey Recorder Component
// ============================================

function HotkeyRecorder({
  value,
  onChange,
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const [isRecording, setIsRecording] = useState(false);

  const formatKeyCombo = (combo: string): string => {
    if (!combo) return 'None';
    const displayMap: Record<string, string> = {
      Control: 'Ctrl',
      Shift: 'Shift',
      Alt: 'Alt',
      Meta: 'Win',
      ' ': 'Space',
    };
    return combo
      .split('+')
      .map((key) => displayMap[key] || key)
      .join(' + ');
  };

  const startRecording = () => {
    if (disabled) return;
    setIsRecording(true);
    const keysPressed = new Set<string>();

    const handleKeyDown = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (e.ctrlKey) keysPressed.add('Control');
      if (e.shiftKey) keysPressed.add('Shift');
      if (e.altKey) keysPressed.add('Alt');
      if (e.metaKey) keysPressed.add('Meta');

      if (!['Control', 'Shift', 'Alt', 'Meta'].includes(e.key)) {
        keysPressed.add(e.key);
      }

      const hasModifier = e.ctrlKey || e.shiftKey || e.altKey || e.metaKey;
      const isFKey = /^F\d+$/.test(e.key);

      if ((hasModifier && keysPressed.size >= 2) || isFKey) {
        const combo = Array.from(keysPressed).join('+');
        stopRecording(combo);
      }
    };

    const handleKeyUp = () => {
      stopRecording();
    };

    const stopRecording = (capturedCombo?: string) => {
      setIsRecording(false);
      window.removeEventListener('keydown', handleKeyDown, true);
      window.removeEventListener('keyup', handleKeyUp, true);
      if (capturedCombo) {
        onChange(capturedCombo);
      }
    };

    window.addEventListener('keydown', handleKeyDown, true);
    window.addEventListener('keyup', handleKeyUp, true);

    setTimeout(() => stopRecording(), 10000);
  };

  return (
    <button
      onClick={isRecording ? undefined : startRecording}
      disabled={disabled}
      className={cn(
        'w-full border-2 px-4 py-3 text-center transition-all disabled:opacity-50 disabled:cursor-not-allowed',
        isRecording
          ? 'border-lawn-accent bg-lawn-accent/10 animate-pulse'
          : 'border-lawn-border bg-lawn-bg hover:border-lawn-accent/50'
      )}
    >
      {isRecording ? (
        <span className="text-sm font-bold text-lawn-accent">Press key combination...</span>
      ) : (
        <span className="text-sm font-mono font-bold">{formatKeyCombo(value)}</span>
      )}
    </button>
  );
}

// ============================================
// Main Settings Panel
// ============================================

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  initialSettings?: SettingsState;
  onSettingsChange?: (settings: SettingsState) => void | Promise<void>;
  onSettingsReset?: () => void | Promise<void>;
  hardwareProfile?: SystemProfile;
  availableModels?: string[];
  availableLanguages?: string[];
  audioDevices?: { id: string; name: string }[];
}

export function SettingsPanel({
  isOpen,
  onClose,
  initialSettings,
  onSettingsChange,
  onSettingsReset,
  hardwareProfile,
  availableModels = ['tiny', 'base', 'small', 'medium', 'large-v3'],
  availableLanguages = ['auto', 'en', 'es', 'fr', 'de', 'it', 'pt', 'nl', 'ja', 'zh', 'ko', 'ar', 'hi'],
  audioDevices = [{ id: 'default', name: 'Default Microphone' }],
}: SettingsPanelProps) {
  const [activeCategory, setActiveCategory] = useState<SettingsCategory>('general');
  const [searchQuery, setSearchQuery] = useState('');
  const [settings, setSettings] = useState<SettingsState>(initialSettings || DEFAULT_SETTINGS);
  const [originalSettings, setOriginalSettings] = useState<SettingsState>(initialSettings || DEFAULT_SETTINGS);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [selectedPreset, setSelectedPreset] = useState<string>('');
  const [hasChanges, setHasChanges] = useState(false);

  // Update settings when initialSettings changes
  useEffect(() => {
    if (initialSettings) {
      setSettings(initialSettings);
      setOriginalSettings(initialSettings);
    }
  }, [initialSettings]);

  // Check if a setting has been modified
  const isChanged = useCallback((category: keyof SettingsState, key: string): boolean => {
    const current = settings[category] as Record<string, unknown>;
    const original = originalSettings[category] as Record<string, unknown>;
    return JSON.stringify(current[key]) !== JSON.stringify(original[key]);
  }, [settings, originalSettings]);

  // Update a specific setting
  const updateSetting = useCallback(
    (category: keyof SettingsState, key: string, value: unknown) => {
      setSettings((prev) => {
        const categoryData = prev[category] as Record<string, unknown>;
        return {
          ...prev,
          [category]: {
            ...categoryData,
            [key]: value,
          },
        } as SettingsState;
      });
      setHasChanges(true);
      setSaveStatus("idle");
      setSaveError(null);
    },
    []
  );

  // Reset a specific setting to default
  const resetSetting = useCallback(
    (category: keyof SettingsState, key: string) => {
      const defaultValue = (DEFAULT_SETTINGS[category] as Record<string, unknown>)[key];
      updateSetting(category, key, defaultValue);
    },
    [updateSetting]
  );

  // Apply a preset
  const applyPreset = useCallback((presetId: string) => {
    const preset = PRESETS.find((p) => p.id === presetId);
    if (!preset) return;

    setSelectedPreset(presetId);
    setSettings((prev) => ({
      ...prev,
      transcription: {
        ...prev.transcription,
        ...preset.settings_override,
      },
    }));
    setHasChanges(true);
    setSaveStatus('idle');
  }, []);

  // Export settings to JSON
  const exportSettings = useCallback(() => {
    const blob = new Blob([JSON.stringify(settings, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transcripta-settings-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [settings]);

  // Import settings from JSON
  const importSettings = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const imported = JSON.parse(e.target?.result as string);
        // Validate and merge with defaults
        setSettings((prev) => ({
          general: { ...prev.general, ...imported.general },
          transcription: { ...prev.transcription, ...imported.transcription },
          audio: { ...prev.audio, ...imported.audio },
          hotkey: { ...prev.hotkey, ...imported.hotkey },
          advanced: { ...prev.advanced, ...imported.advanced },
          version: imported.version || prev.version,
        }));
        setHasChanges(true);
        setSaveStatus('idle');
        setSaveError(null);
      } catch (err) {
        console.error('Failed to import settings:', err);
        setSaveError('Failed to import settings: Invalid file format');
        setSaveStatus('error');
      }
    };
    reader.readAsText(file);
    event.target.value = '';
  }, []);

  // Save settings to backend
  const saveSettings = useCallback(async () => {
    if (!onSettingsChange) return;

    setSaveStatus('saving');
    setSaveError(null);

    try {
      await onSettingsChange(settings);
      setOriginalSettings(settings);
      setHasChanges(false);
      setSaveStatus('saved');

      // Clear success status after 3 seconds
      setTimeout(() => {
        setSaveStatus((current) => current === 'saved' ? 'idle' : current);
      }, 3000);
    } catch (err) {
      console.error('Failed to save settings:', err);
      setSaveError(err instanceof Error ? err.message : 'Failed to save settings');
      setSaveStatus('error');
    }
  }, [onSettingsChange, settings]);

  // Reset all settings to defaults
  const handleResetAll = useCallback(async () => {
    if (window.confirm('Are you sure you want to reset all settings to defaults?')) {
      setSettings(DEFAULT_SETTINGS);
      setHasChanges(true);
      setSaveStatus('idle');

      if (onSettingsReset) {
        try {
          await onSettingsReset();
        } catch (err) {
          console.error('Failed to reset settings:', err);
        }
      }
    }
  }, [onSettingsReset]);

  // Auto-save with debounce
  const saveTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    if (hasChanges && onSettingsChange) {
      // Clear existing timeout
      if (saveTimeoutRef.current) {
        window.clearTimeout(saveTimeoutRef.current);
      }

      // Set new timeout for auto-save
      saveTimeoutRef.current = window.setTimeout(() => {
        void saveSettings();
      }, 1500);
    }

    return () => {
      if (saveTimeoutRef.current) {
        window.clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [settings, hasChanges, onSettingsChange, saveSettings]);

  // Filter settings based on search
  const filteredCategories = useMemo(() => {
    if (!searchQuery.trim()) return CATEGORIES;

    const query = searchQuery.toLowerCase();
    return CATEGORIES.filter((cat) =>
      cat.label.toLowerCase().includes(query) ||
      cat.description.toLowerCase().includes(query)
    );
  }, [searchQuery]);

  // Theme options with proper display
  const themeOptions = [
    { value: 'light', label: 'Light (Lawn)' },
    { value: 'dark', label: 'Dark (Night)' },
    { value: 'cyber', label: 'Cyberpunk' },
    { value: 'dracula', label: 'Dracula' },
  ];

  // Render General Settings
  const renderGeneralSettings = () => (
    <div className="space-y-6">
      <SectionHeader
        title="General Settings"
        icon={Settings}
        description="Configure default session behavior and application preferences"
      />

      <div className="grid gap-4">
        <SettingCard
          title="Theme"
          description="Application color theme"
          changed={isChanged('general', 'theme')}
          onReset={() => resetSetting('general', 'theme')}
        >
          <Select
            value={settings.general.theme}
            options={themeOptions}
            onChange={(v) => updateSetting('general', 'theme', v)}
          />
        </SettingCard>

        <SettingCard
          title="Default Session Title"
          description="Default name for new transcription sessions"
          changed={isChanged('general', 'defaultSessionTitle')}
          onReset={() => resetSetting('general', 'defaultSessionTitle')}
        >
          <input
            type="text"
            value={settings.general.defaultSessionTitle}
            onChange={(e) => updateSetting('general', 'defaultSessionTitle', e.target.value)}
            className="w-full h-10 px-3 border-2 border-lawn-border bg-lawn-bg text-sm focus:border-lawn-accent focus:outline-none text-lawn-border"
          />
        </SettingCard>

        <SettingCard
          title="Default Language"
          description="Primary language for transcription (auto-detects if set to Auto)"
          changed={isChanged('general', 'defaultLanguage')}
          onReset={() => resetSetting('general', 'defaultLanguage')}
        >
          <Select
            value={settings.general.defaultLanguage}
            options={[
              { value: 'auto', label: 'Auto-detect' },
              ...availableLanguages.filter(l => l !== 'auto').map((l) => ({
                value: l,
                label: l.toUpperCase(),
              })),
            ]}
            onChange={(v) => updateSetting('general', 'defaultLanguage', v)}
          />
        </SettingCard>

        <SettingCard
          title="Export Directory"
          description="Default location for exported transcripts and files"
          changed={isChanged('general', 'exportDirectory')}
          onReset={() => resetSetting('general', 'exportDirectory')}
        >
          <div className="flex gap-2">
            <input
              type="text"
              value={settings.general.exportDirectory}
              onChange={(e) => updateSetting('general', 'exportDirectory', e.target.value)}
              placeholder="Use default documents folder"
              className="flex-1 h-10 px-3 border-2 border-lawn-border bg-lawn-bg text-sm focus:border-lawn-accent focus:outline-none text-lawn-border"
            />
            <button
              onClick={async () => {
                const folder = await window.transcriptaDesktop?.chooseDirectory?.();
                if (folder) {
                  updateSetting('general', 'exportDirectory', folder);
                }
              }}
              className="px-4 h-10 border-2 border-lawn-border bg-lawn-bg hover:bg-lawn-accent/10 font-bold text-sm transition-colors"
            >
              Browse
            </button>
          </div>
        </SettingCard>

        <SettingCard
          title="Auto-save Interval"
          description="How often to automatically save session progress (in seconds)"
          changed={isChanged('general', 'autoSaveInterval')}
          onReset={() => resetSetting('general', 'autoSaveInterval')}
        >
          <Slider
            value={settings.general.autoSaveInterval}
            min={10}
            max={300}
            step={10}
            onChange={(v) => updateSetting('general', 'autoSaveInterval', v)}
            suffix="s"
          />
        </SettingCard>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Sliders className="w-4 h-4 text-lawn-accent" />
            Application Behavior
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Show Notifications</span>
                <p className="text-xs text-stone-500">Display desktop notifications for events</p>
              </div>
              <Toggle
                checked={settings.general.showNotifications}
                onChange={(v) => updateSetting('general', 'showNotifications', v)}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Minimize to Tray</span>
                <p className="text-xs text-stone-500">Keep running in system tray when closed</p>
              </div>
              <Toggle
                checked={settings.general.minimizeToTray}
                onChange={(v) => updateSetting('general', 'minimizeToTray', v)}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Start with System</span>
                <p className="text-xs text-stone-500">Launch automatically on Windows startup</p>
              </div>
              <Toggle
                checked={settings.general.startupWithSystem}
                onChange={(v) => updateSetting('general', 'startupWithSystem', v)}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Render Transcription Settings
  const renderTranscriptionSettings = () => (
    <div className="space-y-6">
      <SectionHeader
        title="Transcription Settings"
        icon={Mic}
        description="Configure model selection, quality, and performance parameters"
      />

      <HardwareProfileDisplay profile={hardwareProfile} />

      {/* Preset Selector */}
      <div className="border-2 border-lawn-border bg-lawn-panel p-4">
        <div className="flex items-center gap-2 mb-4">
          <Zap className="w-4 h-4 text-lawn-accent" />
          <h4 className="text-sm font-bold">Quick Presets</h4>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {PRESETS.map((preset) => (
            <button
              key={preset.id}
              onClick={() => applyPreset(preset.id)}
              className={cn(
                'border-2 p-3 text-left transition-all',
                selectedPreset === preset.id
                  ? 'border-lawn-accent bg-lawn-accent/10'
                  : 'border-lawn-border bg-lawn-bg hover:border-lawn-accent/50'
              )}
            >
              <span className="text-sm font-bold block">{preset.name}</span>
              <span className="text-xs text-stone-500 block mt-1">{preset.description}</span>
              <div className="flex flex-wrap gap-1 mt-2">
                {preset.recommended_for.map((tag) => (
                  <span
                    key={tag}
                    className="text-[9px] px-1.5 py-0.5 bg-stone-200 text-stone-600 font-bold"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4">
        <SettingCard
          title="Model"
          description="Whisper model size - larger models are more accurate but slower"
          changed={isChanged('transcription', 'model_name')}
          onReset={() => resetSetting('transcription', 'model_name')}
        >
          <Select
            value={settings.transcription.model_name}
            options={availableModels.map((m) => ({
              value: m,
              label: m.charAt(0).toUpperCase() + m.slice(1),
            }))}
            onChange={(v) => updateSetting('transcription', 'model_name', v)}
          />
        </SettingCard>

        <SettingCard
          title="Compute Type"
          description="Precision mode - float16 for quality, int8 for speed"
          changed={isChanged('transcription', 'compute_type')}
          onReset={() => resetSetting('transcription', 'compute_type')}
        >
          <Select
            value={settings.transcription.compute_type}
            options={[
              { value: 'float16', label: 'Float16 (Best Quality)' },
              { value: 'int8', label: 'Int8 (Fast)' },
              { value: 'int8_float16', label: 'Int8_Float16 (Balanced)' },
            ]}
            onChange={(v) => updateSetting('transcription', 'compute_type', v)}
          />
        </SettingCard>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SettingCard
            title="Chunk Duration"
            description="Audio chunk size in seconds"
            changed={isChanged('transcription', 'chunk_duration')}
            onReset={() => resetSetting('transcription', 'chunk_duration')}
          >
            <Slider
              value={settings.transcription.chunk_duration}
              min={0.5}
              max={5.0}
              step={0.1}
              onChange={(v) => updateSetting('transcription', 'chunk_duration', v)}
              suffix="s"
            />
          </SettingCard>

          <SettingCard
            title="Overlap Ratio"
            description="Audio overlap between chunks"
            changed={isChanged('transcription', 'overlap_ratio')}
            onReset={() => resetSetting('transcription', 'overlap_ratio')}
          >
            <Slider
              value={settings.transcription.overlap_ratio}
              min={0}
              max={0.5}
              step={0.05}
              onChange={(v) => updateSetting('transcription', 'overlap_ratio', v)}
              suffix=""
            />
          </SettingCard>
        </div>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Gauge className="w-4 h-4 text-lawn-accent" />
            Beam Search Parameters
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-xs font-bold text-stone-500 block mb-2">Beam Size</label>
              <NumberInput
                value={settings.transcription.beam_size}
                min={1}
                max={20}
                onChange={(v) => updateSetting('transcription', 'beam_size', v)}
              />
            </div>
            <div>
              <label className="text-xs font-bold text-stone-500 block mb-2">Best Of</label>
              <NumberInput
                value={settings.transcription.best_of}
                min={1}
                max={20}
                onChange={(v) => updateSetting('transcription', 'best_of', v)}
              />
            </div>
            <div>
              <label className="text-xs font-bold text-stone-500 block mb-2">Patience</label>
              <NumberInput
                value={settings.transcription.patience}
                min={0.1}
                max={5}
                step={0.1}
                onChange={(v) => updateSetting('transcription', 'patience', v)}
              />
            </div>
          </div>
        </div>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-lawn-accent" />
            Performance Options
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Parallel Processing</span>
                <p className="text-xs text-stone-500">Use multiple workers for faster transcription</p>
              </div>
              <Toggle
                checked={settings.transcription.use_parallel_processing}
                onChange={(v) => updateSetting('transcription', 'use_parallel_processing', v)}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Preload Model</span>
                <p className="text-xs text-stone-500">Keep model loaded in memory for faster startup</p>
              </div>
              <Toggle
                checked={settings.transcription.preload_model}
                onChange={(v) => updateSetting('transcription', 'preload_model', v)}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Hotkey Optimized</span>
                <p className="text-xs text-stone-500">Optimize for quick hotkey-triggered sessions</p>
              </div>
              <Toggle
                checked={settings.transcription.hotkey_optimized}
                onChange={(v) => updateSetting('transcription', 'hotkey_optimized', v)}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Render Audio Settings
  const renderAudioSettings = () => (
    <div className="space-y-6">
      <SectionHeader
        title="Audio Settings"
        icon={Volume2}
        description="Configure audio capture, VAD, and noise filtering"
      />

      <div className="grid gap-4">
        <SettingCard
          title="Default Audio Device"
          description="Primary microphone for transcription"
          changed={isChanged('audio', 'defaultDeviceId')}
          onReset={() => resetSetting('audio', 'defaultDeviceId')}
        >
          <Select
            value={settings.audio.defaultDeviceId}
            options={audioDevices.map((d) => ({ value: d.id, label: d.name }))}
            onChange={(v) => updateSetting('audio', 'defaultDeviceId', v)}
          />
        </SettingCard>

        <SettingCard
          title="Sample Rate"
          description="Audio sample rate - 16kHz is recommended for Whisper"
          changed={isChanged('audio', 'sampleRate')}
          onReset={() => resetSetting('audio', 'sampleRate')}
        >
          <Select
            value={String(settings.audio.sampleRate)}
            options={[
              { value: '8000', label: '8 kHz' },
              { value: '16000', label: '16 kHz (Recommended)' },
              { value: '22050', label: '22.05 kHz' },
              { value: '44100', label: '44.1 kHz' },
              { value: '48000', label: '48 kHz' },
            ]}
            onChange={(v) => updateSetting('audio', 'sampleRate', parseInt(v))}
          />
        </SettingCard>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Filter className="w-4 h-4 text-lawn-accent" />
            Voice Activity Detection
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Enable VAD</span>
                <p className="text-xs text-stone-500">Automatically detect speech vs silence</p>
              </div>
              <Toggle
                checked={settings.audio.vadEnabled}
                onChange={(v) => updateSetting('audio', 'vadEnabled', v)}
              />
            </div>
            {settings.audio.vadEnabled && (
              <SettingCard
                title="VAD Threshold"
                description="Energy threshold for speech detection (dB)"
                changed={isChanged('audio', 'vadThresholdDb')}
                onReset={() => resetSetting('audio', 'vadThresholdDb')}
              >
                <Slider
                  value={settings.audio.vadThresholdDb}
                  min={-60}
                  max={-20}
                  step={1}
                  onChange={(v) => updateSetting('audio', 'vadThresholdDb', v)}
                  suffix="dB"
                />
              </SettingCard>
            )}
          </div>
        </div>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Layers className="w-4 h-4 text-lawn-accent" />
            Audio Processing
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Noise Filtering</span>
                <p className="text-xs text-stone-500">Reduce background noise</p>
              </div>
              <Toggle
                checked={settings.audio.noiseFiltering}
                onChange={(v) => updateSetting('audio', 'noiseFiltering', v)}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Echo Cancellation</span>
                <p className="text-xs text-stone-500">Remove echo from speakers</p>
              </div>
              <Toggle
                checked={settings.audio.echoCancellation}
                onChange={(v) => updateSetting('audio', 'echoCancellation', v)}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Auto Gain Control</span>
                <p className="text-xs text-stone-500">Automatically adjust input volume</p>
              </div>
              <Toggle
                checked={settings.audio.autoGainControl}
                onChange={(v) => updateSetting('audio', 'autoGainControl', v)}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Render Hotkey Settings
  const renderHotkeySettings = () => (
    <div className="space-y-6">
      <SectionHeader
        title="Hotkey Configuration"
        icon={Keyboard}
        description="Configure global keyboard shortcuts for quick access"
      />

      <div className="grid gap-4">
        <div className="flex items-center justify-between p-4 border-2 border-lawn-border bg-lawn-panel">
          <div className="min-w-0 flex-1">
            <span className="text-sm font-bold block">Enable Global Hotkey</span>
            <p className="text-xs text-stone-500">Activate transcription from anywhere</p>
          </div>
          <Toggle
            checked={settings.hotkey.enabled}
            onChange={(v) => updateSetting('hotkey', 'enabled', v)}
          />
        </div>

        {settings.hotkey.enabled && (
          <>
            <SettingCard
              title="Key Combination"
              description="Press the button and enter your desired hotkey"
              changed={isChanged('hotkey', 'key_combination')}
              onReset={() => resetSetting('hotkey', 'key_combination')}
            >
              <HotkeyRecorder
                value={settings.hotkey.key_combination}
                onChange={(v) => updateSetting('hotkey', 'key_combination', v)}
              />
            </SettingCard>

            <SettingCard
              title="Floating Window Position"
              description="Where to show the transcription overlay"
              changed={isChanged('hotkey', 'floating_window_position')}
              onReset={() => resetSetting('hotkey', 'floating_window_position')}
            >
              <Select
                value={settings.hotkey.floating_window_position}
                options={[
                  { value: 'top-left', label: 'Top Left' },
                  { value: 'top-right', label: 'Top Right' },
                  { value: 'bottom-left', label: 'Bottom Left' },
                  { value: 'bottom-right', label: 'Bottom Right' },
                  { value: 'center', label: 'Center' },
                ]}
                onChange={(v) => updateSetting('hotkey', 'floating_window_position', v as HotkeyConfig['floating_window_position'])}
              />
            </SettingCard>

            <div className="border-2 border-lawn-border bg-lawn-panel p-4">
              <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
                <Sliders className="w-4 h-4 text-lawn-accent" />
                Hotkey Behavior
              </h4>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">Hold Mode</span>
                    <p className="text-xs text-stone-500">Record while holding the hotkey</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.hold_mode}
                    onChange={(v) => updateSetting('hotkey', 'hold_mode', v)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">Auto-inject Text</span>
                    <p className="text-xs text-stone-500">Type transcription into active window</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.auto_inject}
                    onChange={(v) => updateSetting('hotkey', 'auto_inject', v)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">Show Floating Window</span>
                    <p className="text-xs text-stone-500">Display overlay during transcription</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.show_floating_window}
                    onChange={(v) => updateSetting('hotkey', 'show_floating_window', v)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">Copy to Clipboard</span>
                    <p className="text-xs text-stone-500">Automatically copy transcription</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.copy_to_clipboard}
                    onChange={(v) => updateSetting('hotkey', 'copy_to_clipboard', v)}
                  />
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );

  // Render Advanced Settings
  const renderAdvancedSettings = () => (
    <div className="space-y-6">
      <SectionHeader
        title="Advanced Settings"
        icon={Cpu}
        description="Expert configuration and developer options"
      />

      <div className="border-2 border-theme-error/30 bg-theme-error/5 p-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-theme-error flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-bold text-theme-error">Warning</h4>
            <p className="text-xs text-stone-600 mt-1">
              These settings are intended for advanced users. Incorrect values may cause instability or poor performance.
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-4">
        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-lawn-accent" />
            Debugging
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Debug Mode</span>
                <p className="text-xs text-stone-500">Enable verbose logging and diagnostics</p>
              </div>
              <Toggle
                checked={settings.advanced.debugMode}
                onChange={(v) => updateSetting('advanced', 'debugMode', v)}
              />
            </div>
            <SettingCard
              title="Log Level"
              description="Minimum severity for log messages"
              changed={isChanged('advanced', 'logLevel')}
              onReset={() => resetSetting('advanced', 'logLevel')}
            >
              <Select
                value={settings.advanced.logLevel}
                options={[
                  { value: 'DEBUG', label: 'Debug (Most Verbose)' },
                  { value: 'INFO', label: 'Info' },
                  { value: 'WARN', label: 'Warning' },
                  { value: 'ERROR', label: 'Error (Least Verbose)' },
                ]}
                onChange={(v) => updateSetting('advanced', 'logLevel', v)}
              />
            </SettingCard>
            <SettingCard
              title="Max Log Files"
              description="Number of log files to retain"
              changed={isChanged('advanced', 'maxLogFiles')}
              onReset={() => resetSetting('advanced', 'maxLogFiles')}
            >
              <NumberInput
                value={settings.advanced.maxLogFiles}
                min={1}
                max={100}
                onChange={(v) => updateSetting('advanced', 'maxLogFiles', v)}
              />
            </SettingCard>
          </div>
        </div>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Zap className="w-4 h-4 text-lawn-accent" />
            Experimental Features
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Enhanced STEM Detection</span>
                <p className="text-xs text-stone-500">Advanced formula and equation recognition</p>
              </div>
              <Toggle
                checked={settings.advanced.experimentalStem}
                onChange={(v) => updateSetting('advanced', 'experimentalStem', v)}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">GPU Acceleration</span>
                <p className="text-xs text-stone-500">Use GPU for pre-processing when available</p>
              </div>
              <Toggle
                checked={settings.advanced.experimentalGpuAccel}
                onChange={(v) => updateSetting('advanced', 'experimentalGpuAccel', v)}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Enable Metrics</span>
                <p className="text-xs text-stone-500">Collect and report performance metrics</p>
              </div>
              <Toggle
                checked={settings.advanced.enableMetrics}
                onChange={(v) => updateSetting('advanced', 'enableMetrics', v)}
              />
            </div>
          </div>
        </div>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Info className="w-4 h-4 text-lawn-accent" />
            Application Info
          </h4>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="border border-lawn-border bg-lawn-bg p-3">
              <span className="text-stone-500 text-xs block">Version</span>
              <span className="font-bold">1.0.0</span>
            </div>
            <div className="border border-lawn-border bg-lawn-bg p-3">
              <span className="text-stone-500 text-xs block">Platform</span>
              <span className="font-bold">{hardwareProfile?.platform || 'Unknown'}</span>
            </div>
            <div className="border border-lawn-border bg-lawn-bg p-3">
              <span className="text-stone-500 text-xs block">Build</span>
              <span className="font-bold">Release</span>
            </div>
            <div className="border border-lawn-border bg-lawn-bg p-3">
              <span className="text-stone-500 text-xs block">Electron</span>
              <span className="font-bold">Latest</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-5xl h-[85vh] bg-lawn-bg border-2 border-lawn-border shadow-brutal flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b-2 border-lawn-border bg-lawn-panel">
          <div className="flex items-center gap-4 flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-shrink-0">
              <Settings className="w-6 h-6 text-lawn-accent" />
              <h2 className="text-xl font-black uppercase tracking-wider hidden sm:block">Settings</h2>
            </div>
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search settings..."
                className="w-full h-10 pl-10 pr-4 border-2 border-lawn-border bg-lawn-bg text-sm focus:border-lawn-accent focus:outline-none text-lawn-border"
              />
            </div>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            {/* Save Status */}
            <div className="flex items-center gap-2 text-sm">
              {saveStatus === 'saving' && (
                <>
                  <Loader2 className="w-4 h-4 text-lawn-accent animate-spin" />
                  <span className="text-stone-500 hidden sm:inline">Saving...</span>
                </>
              )}
              {saveStatus === 'saved' && (
                <>
                  <CheckCircle2 className="w-4 h-4 text-theme-success" />
                  <span className="text-theme-success hidden sm:inline">Saved</span>
                </>
              )}
              {saveStatus === 'error' && (
                <>
                  <XCircle className="w-4 h-4 text-theme-error" />
                  <span className="text-theme-error hidden sm:inline" title={saveError || ''}>Error</span>
                </>
              )}
            </div>

            {/* Import/Export */}
            <div className="flex items-center gap-2">
              <button
                onClick={exportSettings}
                className="p-2 border-2 border-lawn-border bg-lawn-bg hover:bg-lawn-accent/10 transition-colors"
                title="Export settings"
              >
                <Download className="w-4 h-4" />
              </button>
              <label className="p-2 border-2 border-lawn-border bg-lawn-bg hover:bg-lawn-accent/10 transition-colors cursor-pointer">
                <Upload className="w-4 h-4" />
                <input
                  type="file"
                  accept=".json"
                  onChange={importSettings}
                  className="hidden"
                />
              </label>
            </div>

            <button
              onClick={onClose}
              className="p-2 border-2 border-lawn-border bg-lawn-bg hover:bg-theme-error/10 hover:border-theme-error transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Sidebar */}
          <div className="w-[200px] sm:w-[240px] border-r-2 border-lawn-border bg-lawn-panel overflow-y-auto flex-shrink-0">
            <nav className="p-2">
              {filteredCategories.map((category) => {
                const Icon = category.icon;
                const isActive = activeCategory === category.id;

                return (
                  <button
                    key={category.id}
                    onClick={() => setActiveCategory(category.id)}
                    className={cn(
                      'w-full flex items-center gap-3 px-3 py-3 text-left transition-all mb-1',
                      isActive
                        ? 'bg-lawn-accent text-lawn-bg'
                        : 'hover:bg-lawn-accent/10 text-lawn-border'
                    )}
                  >
                    <Icon className="w-5 h-5 flex-shrink-0" />
                    <div className="flex-1 min-w-0 overflow-hidden">
                      <span className="block text-sm font-bold truncate">{category.label}</span>
                      <span className={cn(
                        'block text-[10px] truncate',
                        isActive ? 'text-lawn-bg/70' : 'text-stone-500'
                      )}>
                        {category.description}
                      </span>
                    </div>
                    {isActive && <ChevronRight className="w-4 h-4 flex-shrink-0" />}
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Main Content */}
          <div className="flex-1 overflow-y-auto min-w-0">
            <div className="p-4 sm:p-6 max-w-3xl">
              {activeCategory === 'general' && renderGeneralSettings()}
              {activeCategory === 'transcription' && renderTranscriptionSettings()}
              {activeCategory === 'audio' && renderAudioSettings()}
              {activeCategory === 'hotkey' && renderHotkeySettings()}
              {activeCategory === 'advanced' && renderAdvancedSettings()}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 border-t-2 border-lawn-border bg-lawn-panel">
          <div className="flex flex-wrap items-center gap-4 text-xs text-stone-500">
            <span>Auto-save enabled</span>
            <span className="w-px h-4 bg-stone-300 hidden sm:block" />
            <button
              onClick={handleResetAll}
              className="hover:text-lawn-accent transition-colors"
            >
              Reset All to Defaults
            </button>
          </div>
          <div className="flex items-center gap-3 w-full sm:w-auto">
            <button
              onClick={onClose}
              className="flex-1 sm:flex-none px-6 py-2 border-2 border-lawn-border bg-lawn-bg hover:bg-stone-100 text-sm font-bold transition-colors"
            >
              Close
            </button>
            <button
              onClick={() => void saveSettings()}
              disabled={saveStatus === 'saving' || !hasChanges}
              className="flex-1 sm:flex-none px-6 py-2 border-2 border-lawn-accent bg-lawn-accent text-lawn-bg hover:shadow-brutal-sm text-sm font-bold transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saveStatus === 'saving' ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              {saveStatus === 'saving' ? 'Saving...' : 'Save Now'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SettingsPanel;
