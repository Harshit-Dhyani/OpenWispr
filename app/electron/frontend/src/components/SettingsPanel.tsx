import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Settings,
  Mic,
  Bot,
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
  Device,
  ModelCatalogEntry,
  SystemProfile,
  OptimizationPreset,
} from '../types/api';
import { DEFAULT_SETTINGS, isFakeSetting, validateSettings } from '../lib/settingsSchema';
import type { SettingsState, HotkeySettings } from '../lib/settingsSchema';
import { sanitizeSettings } from '../lib/settingsMigration';
import { getLanguageLabel, LANGUAGE_OPTIONS } from '../lib/languages';
import type { ModelManagerState } from '../lib/modelRegistry';

// Utility for Tailwind class merging
function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ============================================
// Types
// ============================================

type SettingsCategory = 'general' | 'models' | 'transcription' | 'audio' | 'hotkey' | 'advanced';

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

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
    id: 'models',
    label: 'Models',
    icon: Bot,
    description: 'Download, verify, and select ASR and refiner models',
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

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unit]}`;
}

function normalizeProgressPercent(progress: number): number {
  if (!Number.isFinite(progress)) {
    return 0;
  }
  const normalized = progress <= 1 ? progress * 100 : progress;
  return Math.max(0, Math.min(100, normalized));
}

function ModelStatusBadge({
  installed,
  verified,
  recommended,
}: {
  installed: boolean;
  verified: boolean;
  recommended: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-1">
      <span
        className={cn(
          'text-[9px] px-1.5 py-0.5 font-bold uppercase',
          installed ? 'bg-theme-success text-lawn-bg' : 'bg-stone-300 text-stone-700'
        )}
      >
        {installed ? 'Installed' : 'Not Installed'}
      </span>
      {verified && (
        <span className="text-[9px] px-1.5 py-0.5 bg-theme-info text-lawn-bg font-bold uppercase">
          Verified
        </span>
      )}
      {recommended && (
        <span className="text-[9px] px-1.5 py-0.5 bg-lawn-accent text-lawn-bg font-bold uppercase">
          Recommended
        </span>
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
  modelManager?: ModelManagerState;
  onDownloadModel?: (modelId: string) => void | Promise<void>;
  onCancelModelDownload?: (modelId: string) => void | Promise<void>;
  onRemoveModel?: (modelId: string) => void | Promise<void>;
  availableLanguages?: string[];
  audioDevices?: Device[];
}

export function SettingsPanel({
  isOpen,
  onClose,
  initialSettings,
  onSettingsChange,
  onSettingsReset,
  hardwareProfile,
  availableModels = ['tiny', 'base', 'small', 'medium', 'large-v3'],
  modelManager,
  onDownloadModel,
  onCancelModelDownload,
  onRemoveModel,
  availableLanguages = LANGUAGE_OPTIONS.map((language) => language.code),
  audioDevices = [
    {
      id: 'default',
      name: 'Default Microphone',
      kind: 'microphone',
      is_loopback: false,
      channels: 1,
      sample_rate: 16000,
    },
  ],
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
        ...preset.settings_override as Partial<SettingsState['transcription']>,
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

        // Validate imported settings
        const validation = validateSettings(imported);
        if (validation.success) {
          setSettings(validation.data);
          setHasChanges(true);
          setSaveStatus('idle');
          setSaveError(null);
        } else {
          // Try sanitization as fallback
          const sanitized = sanitizeSettings(imported);
          setSettings(sanitized);
          setHasChanges(true);
          setSaveError('Some settings were invalid and reset to defaults');
        }
      } catch (err) {
        setSaveError('Failed to import: Invalid JSON');
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

  const asrModels = modelManager?.catalog.filter((entry) => entry.category === 'asr') ?? [];
  const refinerModels = modelManager?.catalog.filter((entry) => entry.category === 'refiner') ?? [];
  const installStateById = useMemo(
    () => new Map((modelManager?.installed ?? []).map((entry) => [entry.model_id, entry])),
    [modelManager?.installed]
  );

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
              { value: 'auto', label: getLanguageLabel('auto') },
              ...availableLanguages.filter(l => l !== 'auto').map((l) => ({
                value: l,
                label: getLanguageLabel(l),
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
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">Show Notifications</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">Coming Soon</span>
                </div>
                <p className="text-xs text-stone-500">Display desktop notifications for events</p>
              </div>
              <Toggle
                checked={settings.general.showNotifications}
                onChange={(v) => updateSetting('general', 'showNotifications', v)}
                disabled={isFakeSetting('general', 'showNotifications')}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">Minimize to Tray</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">Coming Soon</span>
                </div>
                <p className="text-xs text-stone-500">Keep running in system tray when closed</p>
              </div>
              <Toggle
                checked={settings.general.minimizeToTray}
                onChange={(v) => updateSetting('general', 'minimizeToTray', v)}
                disabled={isFakeSetting('general', 'minimizeToTray')}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">Start with System</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">Coming Soon</span>
                </div>
                <p className="text-xs text-stone-500">Launch automatically on Windows startup</p>
              </div>
              <Toggle
                checked={settings.general.startupWithSystem}
                onChange={(v) => updateSetting('general', 'startupWithSystem', v)}
                disabled={isFakeSetting('general', 'startupWithSystem')}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderCatalogBlock = (
    title: string,
    description: string,
    category: 'asr' | 'refiner',
    models: ModelCatalogEntry[]
  ) => {
    const selectedModelId =
      category === 'asr'
        ? settings.transcription.default_asr_model_id
        : settings.refiner.selected_model_id;

    return (
      <div className="border-2 border-lawn-border bg-lawn-panel p-4">
        <div className="mb-4">
          <h4 className="text-sm font-bold">{title}</h4>
          <p className="text-xs text-stone-500 mt-1">{description}</p>
        </div>

        <div className="mb-4">
          <Select
            value={selectedModelId}
            options={models.map((model) => ({
              value: model.id,
              label: `${model.display_name}${model.installed ? '' : ' (not installed)'}`,
            }))}
            onChange={(value) => {
              if (category === 'asr') {
                updateSetting('transcription', 'default_asr_model_id', value);
              } else {
                updateSetting('refiner', 'selected_model_id', value);
              }
            }}
          />
        </div>

        <div className="space-y-3">
          {models.map((model) => {
            const installState = installStateById.get(model.id);
            const downloadState = modelManager?.downloads[model.id];
            const isSelected = selectedModelId === model.id;
            const isDownloading =
              downloadState && ['downloading', 'verifying'].includes(downloadState.status);
            const canActivate = model.installed && model.enabled_runtime;
            const progressPercent = downloadState ? normalizeProgressPercent(downloadState.progress) : 0;

            return (
              <div
                key={model.id}
                className={cn(
                  'border-2 p-3',
                  isSelected ? 'border-lawn-accent bg-lawn-accent/5' : 'border-lawn-border bg-lawn-bg'
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-bold">{model.display_name}</span>
                      <ModelStatusBadge
                        installed={model.installed}
                        verified={model.verified}
                        recommended={model.recommended}
                      />
                      {!model.enabled_runtime && (
                        <span className="text-[9px] px-1.5 py-0.5 bg-theme-warning text-lawn-bg font-bold uppercase">
                          Runtime Stub
                        </span>
                      )}
                      {isSelected && (
                        <span className="text-[9px] px-1.5 py-0.5 bg-lawn-border text-lawn-bg font-bold uppercase">
                          Selected
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-stone-500">{model.description_short}</p>
                    <p className="mt-2 text-xs text-lawn-border">
                      <span className="font-bold">Why choose this:</span> {model.why_choose_this}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-stone-500">
                      <span>{model.size_gb_estimate.toFixed(1)} GB</span>
                      <span>{model.speed_tier}</span>
                      <span>{model.engine}</span>
                      <span>VRAM {model.recommended_vram_gb}+ GB</span>
                      {installState?.size_bytes ? <span>{formatBytes(installState.size_bytes)}</span> : null}
                    </div>
                    {downloadState ? (
                      <div className="mt-3">
                        <div className="mb-1 flex items-center justify-between text-[10px] font-bold">
                          <span className="uppercase text-stone-500">{downloadState.status}</span>
                          <span>{progressPercent.toFixed(progressPercent >= 10 ? 0 : 1)}%</span>
                        </div>
                        <div className="h-2 border border-lawn-border bg-white overflow-hidden">
                          <div
                            className="h-full bg-lawn-accent transition-all"
                            style={{ width: `${progressPercent}%` }}
                          />
                        </div>
                        <div className="mt-1 text-[10px] text-stone-500">
                          {formatBytes(downloadState.bytes_downloaded)} / {formatBytes(downloadState.total_bytes)} · {formatBytes(downloadState.speed_bytes_per_sec)}/s
                        </div>
                        {downloadState.error ? (
                          <div className="mt-1 text-[10px] font-bold text-theme-error">{downloadState.error}</div>
                        ) : null}
                      </div>
                    ) : null}
                    {category === 'refiner' && isSelected && !settings.refiner.runtime_enabled ? (
                      <div className="mt-2 text-[10px] font-bold text-theme-warning">
                        Installed and configurable, but local refiner runtime is not enabled yet.
                      </div>
                    ) : null}
                    {category === 'asr' && isSelected && !canActivate ? (
                      <div className="mt-2 text-[10px] font-bold text-theme-warning">
                        This model is selected as the default but cannot run until it is installed.
                      </div>
                    ) : null}
                  </div>

                  <div className="flex shrink-0 flex-col gap-2">
                    {!model.installed && onDownloadModel ? (
                      <button
                        onClick={() => void onDownloadModel(model.id)}
                        disabled={Boolean(isDownloading)}
                        className="px-3 py-2 border-2 border-lawn-border bg-lawn-accent text-lawn-bg text-xs font-bold disabled:opacity-50"
                      >
                        {isDownloading ? 'Downloading…' : 'Download'}
                      </button>
                    ) : null}

                    {isDownloading && onCancelModelDownload ? (
                      <button
                        onClick={() => void onCancelModelDownload(model.id)}
                        className="px-3 py-2 border-2 border-lawn-border bg-lawn-bg text-xs font-bold"
                      >
                        Cancel
                      </button>
                    ) : null}

                    {model.installed && onRemoveModel ? (
                      <button
                        onClick={() => void onRemoveModel(model.id)}
                        className="px-3 py-2 border-2 border-lawn-border bg-lawn-bg text-xs font-bold"
                      >
                        Remove
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderModelSettings = () => (
    <div className="space-y-6">
      <SectionHeader
        title="Model Manager"
        icon={Bot}
        description="Install, verify, and choose speech-to-text and transcript refiner models."
      />

      <HardwareProfileDisplay profile={hardwareProfile} />

      <div className="grid gap-4">
        {renderCatalogBlock(
          'Speech-to-Text',
          'Choose the default ASR model for new sessions. Session Setup still lets you override the current run.',
          'asr',
          asrModels
        )}

        {renderCatalogBlock(
          'Transcript Refiner',
          'Choose a local cleanup/refiner model. Runtime remains explicitly disabled until the refiner pipeline is fully enabled.',
          'refiner',
          refinerModels
        )}

        <SettingCard
          title="Refinement Mode"
          description="Off disables cleanup beyond built-in heuristics. Strict preserves meaning. Polished allows minor rephrasing."
          changed={isChanged('transcription', 'refinement_mode')}
          onReset={() => resetSetting('transcription', 'refinement_mode')}
        >
          <Select
            value={settings.transcription.refinement_mode}
            options={[
              { value: 'off', label: 'Off' },
              { value: 'strict', label: 'Strict' },
              { value: 'polished', label: 'Polished' },
            ]}
            onChange={(v) => updateSetting('transcription', 'refinement_mode', v)}
          />
        </SettingCard>
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
          title="Default Session ASR Model"
          description="Default model for new sessions. Installed state and downloads are managed in the Models tab."
          changed={isChanged('transcription', 'default_asr_model_id')}
          onReset={() => resetSetting('transcription', 'default_asr_model_id')}
        >
          <Select
            value={settings.transcription.default_asr_model_id}
            options={(asrModels.length ? asrModels : availableModels.map((m) => ({
              id: m,
              display_name: m.charAt(0).toUpperCase() + m.slice(1),
              installed: true,
            })) as Array<{ id: string; display_name: string; installed: boolean }>).map((m) => ({
              value: m.id,
              label: `${m.display_name}${m.installed ? '' : ' (not installed)'}`,
            }))}
            onChange={(v) => {
              updateSetting('transcription', 'default_asr_model_id', v);
              const selectedAsr = asrModels.find((entry) => entry.id === v);
              if (selectedAsr?.runtime_model_name) {
                updateSetting('transcription', 'model_name', selectedAsr.runtime_model_name);
              }
            }}
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

          <SettingCard
            title="Min Segment Length"
            description="Minimum duration for a valid segment"
            changed={isChanged('transcription', 'min_segment_length')}
            onReset={() => resetSetting('transcription', 'min_segment_length')}
          >
            <Slider
              value={settings.transcription.min_segment_length}
              min={0.1}
              max={2.0}
              step={0.1}
              onChange={(v) => updateSetting('transcription', 'min_segment_length', v)}
              suffix="s"
            />
          </SettingCard>
        </div>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Gauge className="w-4 h-4 text-lawn-accent" />
            Beam Search Parameters
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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
            <div>
              <label className="text-xs font-bold text-stone-500 block mb-2">Temperature</label>
              <NumberInput
                value={settings.transcription.temperature}
                min={0}
                max={1}
                step={0.1}
                onChange={(v) => updateSetting('transcription', 'temperature', v)}
              />
            </div>
          </div>
        </div>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Filter className="w-4 h-4 text-lawn-accent" />
            Quality Filters
          </h4>
          <div className="space-y-4">
            <SettingCard
              title="Confidence Threshold"
              description="Minimum confidence score for transcription segments"
              changed={isChanged('transcription', 'confidence_threshold')}
              onReset={() => resetSetting('transcription', 'confidence_threshold')}
            >
              <Slider
                value={settings.transcription.confidence_threshold}
                min={0}
                max={1}
                step={0.05}
                onChange={(v) => updateSetting('transcription', 'confidence_threshold', v)}
                suffix=""
              />
            </SettingCard>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Filter Filler Words</span>
                <p className="text-xs text-stone-500">Remove um, uh, and other filler words</p>
              </div>
              <Toggle
                checked={settings.transcription.enable_filler_filter}
                onChange={(v) => updateSetting('transcription', 'enable_filler_filter', v)}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Filter Hallucinations</span>
                <p className="text-xs text-stone-500">Suppress likely model hallucinations</p>
              </div>
              <Toggle
                checked={settings.transcription.enable_hallucination_filter}
                onChange={(v) => updateSetting('transcription', 'enable_hallucination_filter', v)}
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
            <SettingCard
              title="Max Workers"
              description="Number of parallel transcription workers"
              changed={isChanged('transcription', 'max_workers')}
              onReset={() => resetSetting('transcription', 'max_workers')}
            >
              <NumberInput
                value={settings.transcription.max_workers}
                min={1}
                max={16}
                onChange={(v) => updateSetting('transcription', 'max_workers', v)}
              />
            </SettingCard>
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
          title="Capture Mode"
          description="Choose between microphone dictation and system-audio transcription"
          changed={isChanged('audio', 'captureMode')}
          onReset={() => resetSetting('audio', 'captureMode')}
        >
          <Select
            value={settings.audio.captureMode}
            options={[
              { value: 'system', label: 'System Audio' },
              { value: 'microphone', label: 'Microphone' },
            ]}
            onChange={(v) => updateSetting('audio', 'captureMode', v as 'system' | 'microphone')}
          />
        </SettingCard>

        <SettingCard
          title="Default Audio Device"
          description="Primary device for the selected capture mode"
          changed={isChanged('audio', 'defaultDeviceId')}
          onReset={() => resetSetting('audio', 'defaultDeviceId')}
        >
          <Select
            value={settings.audio.defaultDeviceId}
            options={audioDevices
              .filter((device) =>
                settings.audio.captureMode === 'system'
                  ? Boolean(device.is_loopback || device.supports_loopback)
                  : !Boolean(device.is_loopback || device.supports_loopback),
              )
              .map((d) => ({
                value: d.id,
                label: `${d.name}${d.is_loopback || d.supports_loopback ? ' [rec]' : ''}`,
              }))}
            onChange={(v) => updateSetting('audio', 'defaultDeviceId', v)}
          />
        </SettingCard>

        <SettingCard
          title="Audio Backend"
          description="Choose which Windows capture backend Transcripta should prefer"
          changed={isChanged('audio', 'audio_backend')}
          onReset={() => resetSetting('audio', 'audio_backend')}
        >
          <Select
            value={settings.audio.audio_backend}
            options={[
              { value: 'auto', label: 'Auto (PyAudio first)' },
              { value: 'pyaudio', label: 'PyAudio WASAPI' },
              { value: 'soundcard', label: 'Soundcard (Legacy)' },
            ]}
            onChange={(v) => updateSetting('audio', 'audio_backend', v as 'auto' | 'pyaudio' | 'soundcard')}
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
                checked={settings.transcription.vad_enabled}
                onChange={(v) => updateSetting('transcription', 'vad_enabled', v)}
              />
            </div>
            {settings.transcription.vad_enabled && (
              <SettingCard
                title="VAD Threshold"
                description="Energy threshold for speech detection (dB)"
                changed={isChanged('transcription', 'vad_threshold_db')}
                onReset={() => resetSetting('transcription', 'vad_threshold_db')}
              >
                <Slider
                  value={settings.transcription.vad_threshold_db}
                  min={-60}
                  max={-20}
                  step={1}
                  onChange={(v) => updateSetting('transcription', 'vad_threshold_db', v)}
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
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">Noise Filtering</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">Coming Soon</span>
                </div>
                <p className="text-xs text-stone-500">Reduce background noise</p>
              </div>
              <Toggle
                checked={settings.audio.noiseFiltering}
                onChange={(v) => updateSetting('audio', 'noiseFiltering', v)}
                disabled={isFakeSetting('audio', 'noiseFiltering')}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">Echo Cancellation</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">Coming Soon</span>
                </div>
                <p className="text-xs text-stone-500">Remove echo from speakers</p>
              </div>
              <Toggle
                checked={settings.audio.echoCancellation}
                onChange={(v) => updateSetting('audio', 'echoCancellation', v)}
                disabled={isFakeSetting('audio', 'echoCancellation')}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">Auto Gain Control</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">Coming Soon</span>
                </div>
                <p className="text-xs text-stone-500">Automatically adjust input volume</p>
              </div>
              <Toggle
                checked={settings.audio.autoGainControl}
                onChange={(v) => updateSetting('audio', 'autoGainControl', v)}
                disabled={isFakeSetting('audio', 'autoGainControl')}
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

            <div className="grid gap-4 md:grid-cols-2">
              <SettingCard
                title="Dictation Language"
                description="Default language for microphone hotkey dictation"
                changed={isChanged('hotkey', 'language')}
                onReset={() => resetSetting('hotkey', 'language')}
              >
                <Select
                  value={settings.hotkey.language}
                  options={availableLanguages.map((language) => ({
                    value: language,
                    label: getLanguageLabel(language),
                  }))}
                  onChange={(v) => updateSetting('hotkey', 'language', v)}
                />
              </SettingCard>

              <SettingCard
                title="Dictation Finish Action"
                description="Default action when a toggle hotkey session stops"
                changed={isChanged('hotkey', 'finish_mode_default')}
                onReset={() => resetSetting('hotkey', 'finish_mode_default')}
              >
                <Select
                  value={settings.hotkey.finish_mode_default}
                  options={[
                    { value: 'finish', label: 'Finish Only' },
                    { value: 'finish_and_paste', label: 'Finish & Paste' },
                  ]}
                  onChange={(v) => updateSetting('hotkey', 'finish_mode_default', v)}
                />
              </SettingCard>
            </div>

            <SettingCard
              title="Dictation Microphone"
              description="Microphone source used for quick dictation"
              changed={isChanged('hotkey', 'device_id')}
              onReset={() => resetSetting('hotkey', 'device_id')}
            >
              <Select
                value={settings.hotkey.device_id}
                options={[
                  { value: 'default', label: 'Auto-detect microphone' },
                  ...audioDevices
                    .filter((device) => device.is_input && !(device.is_loopback || device.supports_loopback))
                    .map((device) => ({
                      value: device.id,
                      label: device.name,
                    })),
                ]}
                onChange={(v) => updateSetting('hotkey', 'device_id', v)}
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
                onChange={(v) => updateSetting('hotkey', 'floating_window_position', v as HotkeySettings['floating_window_position'])}
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
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">Record on Start</span>
                    <p className="text-xs text-stone-500">Automatically start recording when hotkey session begins</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.record_on_start}
                    onChange={(v) => updateSetting('hotkey', 'record_on_start', v)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">Stop on Release</span>
                    <p className="text-xs text-stone-500">Stop recording when hotkey is released (hold mode)</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.stop_on_release}
                    onChange={(v) => updateSetting('hotkey', 'stop_on_release', v)}
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
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">Enhanced STEM Detection</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">Coming Soon</span>
                </div>
                <p className="text-xs text-stone-500">Advanced formula and equation recognition</p>
              </div>
              <Toggle
                checked={settings.advanced.experimentalStem}
                onChange={(v) => updateSetting('advanced', 'experimentalStem', v)}
                disabled={isFakeSetting('advanced', 'experimentalStem')}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">GPU Acceleration</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">Coming Soon</span>
                </div>
                <p className="text-xs text-stone-500">Use GPU for pre-processing when available</p>
              </div>
              <Toggle
                checked={settings.advanced.experimentalGpuAccel}
                onChange={(v) => updateSetting('advanced', 'experimentalGpuAccel', v)}
                disabled={isFakeSetting('advanced', 'experimentalGpuAccel')}
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
              {activeCategory === 'models' && renderModelSettings()}
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
