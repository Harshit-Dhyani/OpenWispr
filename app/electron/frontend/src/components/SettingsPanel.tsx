import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Settings,
  Search,
  X,
  Download,
  Upload,
  Save,
  ChevronRight,
  Loader2,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import type { SettingsState } from '../lib/settingsSchema';
import { DEFAULT_SETTINGS, validateSettings } from '../lib/settingsSchema';
import { sanitizeSettings } from '../lib/settingsMigration';
import { LANGUAGE_OPTIONS } from '../lib/languages';
import type { Device, SystemProfile, ModelManagerState } from './settings/types';
import type { SettingsCategory, SaveStatus } from './settings/types';
import { CATEGORIES } from './settings/categories';
import { PRESETS } from './settings/presets';
import { cn } from './settings/utils';
import {
  GeneralSection,
  ModelSection,
  TranscriptionSection,
  AudioSection,
  HotkeySection,
  AdvancedSection,
} from './settings/sections';

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  inline?: boolean;
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
  inline = false,
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
      setSaveStatus('idle');
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

  // Section props
  const sectionProps = {
    settings,
    originalSettings,
    hardwareProfile,
    availableModels,
    modelManager,
    audioDevices,
    availableLanguages,
    isChanged,
    updateSetting,
    resetSetting,
    onDownloadModel,
    onCancelModelDownload,
    onRemoveModel,
  };

  if (!isOpen && !inline) return null;

  const panelBody = (
    <div
      className={
        inline
          ? "w-full bg-lawn-bg border-2 border-lawn-border shadow-brutal flex min-h-0 flex-1 flex-col"
          : "w-full max-w-5xl h-[85vh] bg-lawn-bg border-2 border-lawn-border shadow-brutal flex flex-col"
      }
    >
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

            {!inline ? (
              <button
                onClick={onClose}
                className="p-2 border-2 border-lawn-border bg-lawn-bg hover:bg-theme-error/10 hover:border-theme-error transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            ) : null}
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
              {activeCategory === 'general' && (
                <GeneralSection {...sectionProps} />
              )}
              {activeCategory === 'models' && (
                <ModelSection {...sectionProps} />
              )}
              {activeCategory === 'transcription' && (
                <TranscriptionSection
                  {...sectionProps}
                  selectedPreset={selectedPreset}
                  onApplyPreset={applyPreset}
                />
              )}
              {activeCategory === 'audio' && (
                <AudioSection {...sectionProps} />
              )}
              {activeCategory === 'hotkey' && (
                <HotkeySection {...sectionProps} />
              )}
              {activeCategory === 'advanced' && (
                <AdvancedSection {...sectionProps} saveError={saveError} />
              )}
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
  );

  if (inline) {
    return panelBody;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      {panelBody}
    </div>
  );
}

export default SettingsPanel;
