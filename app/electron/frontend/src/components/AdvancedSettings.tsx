import { useState, useEffect } from 'react';
import {
  Activity,
  HardDrive,
  Gauge,
  Zap,
  Brain,
  Mic,
  Sliders,
  Keyboard,
  Check,
  AlertCircle,
  X,
  Settings,
  Monitor,
} from 'lucide-react';
import type {
  HardwareProfile,
  OptimizationResult,
} from '../types/api';
import type { TranscriptionSettings } from '../lib/settingsSchema';
import { HotkeySettings } from './HotkeySettings';
import {
  OPTIMIZATION_PRESET_LABELS,
  PRESET_DESCRIPTIONS,
  SECTION_HEADERS,
  BUTTON_LABELS,
  TAB_LABELS,
  ERROR_MESSAGES,
  HARDWARE_LABELS,
  METRIC_LABELS,
  MODEL_NAMES,
  COMPUTE_TYPE_LABELS,
  UNIT_LABELS,
  SETTING_LABELS,
} from '../config/text';

interface AdvancedSettingsProps {
  isOpen: boolean;
  onClose: () => void;
  onApplySettings: (settings: Partial<TranscriptionSettings>) => void;
  currentSettings?: Partial<TranscriptionSettings>;
}

interface SystemProfile extends HardwareProfile {
  recommended_quality: 'maximum' | 'balanced' | 'fast' | 'low_memory';
  recommended_preset: string;
}

const PRESETS = [
  { id: 'maximum', label: OPTIMIZATION_PRESET_LABELS.maximum, icon: Brain, desc: PRESET_DESCRIPTIONS.maximum },
  { id: 'balanced', label: OPTIMIZATION_PRESET_LABELS.balanced, icon: Gauge, desc: PRESET_DESCRIPTIONS.balanced },
  { id: 'fast', label: OPTIMIZATION_PRESET_LABELS.fast, icon: Zap, desc: PRESET_DESCRIPTIONS.fast },
  { id: 'low_memory', label: OPTIMIZATION_PRESET_LABELS.low_memory, icon: HardDrive, desc: PRESET_DESCRIPTIONS.low_memory },
];



export function AdvancedSettings({ isOpen, onClose, onApplySettings, currentSettings }: AdvancedSettingsProps) {
  // System Profile State
  const [profile, setProfile] = useState<SystemProfile | null>(null);
  
  // Optimization State
  const [optimizationResult, setOptimizationResult] = useState<OptimizationResult | null>(null);
  const [selectedPreset, setSelectedPreset] = useState('balanced');
  const [optimizing, setOptimizing] = useState(false);
  
  // Manual Settings State - using TranscriptionSettings for full coverage
  const [manualSettings, setManualSettings] = useState<Partial<TranscriptionSettings>>({});
  const [activeTab, setActiveTab] = useState<'presets' | 'manual' | 'hotkey'>('presets');
  
      
  // Loading State
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load initial data
  useEffect(() => {
    if (isOpen) {
      void loadInitialData();
    }
  }, [isOpen]);

  const loadInitialData = async () => {
    setLoading(true);
    setError(null);
    try {
      await Promise.all([
        loadSystemProfile(),
        loadOptimizedSettings('balanced'),
      ]);
    } catch (err) {
      setError(ERROR_MESSAGES.failed_to_load_settings);
    } finally {
      setLoading(false);
    }
  };

  const loadSystemProfile = async () => {
    try {
      const data = await window.openwisprDesktop.fetchJson('/api/system/profile') as SystemProfile;
      setProfile(data);
    } catch (error) {
      console.error('Failed to load system profile:', error);
      throw error;
    }
  };

  const loadOptimizedSettings = async (mode: string, hotkey = false) => {
    setOptimizing(true);
    try {
      const data = await window.openwisprDesktop.fetchJson(
        `/api/system/optimize?mode=${encodeURIComponent(mode)}&hotkey=${String(hotkey)}`
      ) as OptimizationResult;
      setOptimizationResult(data);
      setManualSettings({ ...data.settings, ...currentSettings } as Partial<TranscriptionSettings>);
    } catch (error) {
      console.error(ERROR_MESSAGES.failed_to_optimize + ':', error);
      throw error;
    } finally {
      setOptimizing(false);
    }
  };


  // Preset Selection
  const handlePresetSelect = async (presetId: string) => {
    setSelectedPreset(presetId);
    await loadOptimizedSettings(presetId, false);
  };

  // Manual Settings Handlers
  const handleManualChange = (key: keyof TranscriptionSettings, value: unknown) => {
    setManualSettings(prev => ({ ...prev, [key]: value }));
  };

  const applyManualSettings = () => {
    if (manualSettings) {
      onApplySettings(manualSettings);
    }
  };
// Get recommended preset indicator
  const getRecommendedPreset = () => {
    if (!profile) return 'balanced';
    return profile.recommended_preset || 'balanced';
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-[800px] max-h-[90vh] bg-lawn-bg border-2 border-lawn-border shadow-brutal flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b-2 border-lawn-border bg-lawn-panel">
          <div className="flex items-center gap-3">
            <Settings className="w-5 h-5 text-lawn-accent" />
            <h2 className="text-lg font-black uppercase tracking-wider text-lawn-border">
              {SECTION_HEADERS.advancedSettings}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 border-2 border-lawn-border bg-lawn-bg hover:bg-lawn-accent transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b-2 border-lawn-border">
          {[
            { id: 'presets', label: TAB_LABELS.presets, icon: Gauge },
            { id: 'manual', label: TAB_LABELS.manual, icon: Sliders },
            { id: 'hotkey', label: TAB_LABELS.hotkey, icon: Keyboard },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={`flex-1 flex items-center justify-center gap-2 py-3 text-xs font-black uppercase tracking-wider transition-colors ${
                  activeTab === tab.id
                    ? 'bg-lawn-accent text-lawn-bg'
                    : 'bg-lawn-panel text-lawn-border hover:bg-lawn-bg'
                }`}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Activity className="w-8 h-8 animate-spin text-lawn-accent" />
              <p className="mt-4 text-sm text-stone-500">Loading settings...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12 text-error">
              <AlertCircle className="w-8 h-8" />
              <p className="mt-4 text-sm">{error}</p>
            </div>
          ) : (
            <>
              {/* System Profile (shown in all tabs) */}
              {profile && (
                <section className="mb-6 border-2 border-lawn-border bg-lawn-panel p-4">
                  <h3 className="text-xs font-black uppercase tracking-wider text-lawn-border mb-3 flex items-center gap-2">
                    <Monitor size={14} />
                    {SECTION_HEADERS.systemProfile}
                  </h3>
                  <div className="grid grid-cols-4 gap-3 text-xs">
                    <div className="border border-lawn-border bg-lawn-bg p-2">
                      <span className="text-stone-500 block">{HARDWARE_LABELS.gpu}</span>
                      <span className="font-bold">
                        {profile.gpu.available ? profile.gpu.name : HARDWARE_LABELS.not_available}
                      </span>
                      {profile.gpu.available && (
                        <span className="block text-stone-500">
                          {profile.gpu.vram_gb.toFixed(1)}{UNIT_LABELS.gigabytes} {HARDWARE_LABELS.vram}
                        </span>
                      )}
                    </div>
                    <div className="border border-lawn-border bg-lawn-bg p-2">
                      <span className="text-stone-500 block">{HARDWARE_LABELS.cpu}</span>
                      <span className="font-bold">{profile.cpu.cores} {HARDWARE_LABELS.cores}</span>
                      <span className="block text-stone-500">
                        {profile.cpu.ram_gb.toFixed(0)}{UNIT_LABELS.gigabytes} {HARDWARE_LABELS.ram}
                      </span>
                    </div>
                    <div className="border border-lawn-border bg-lawn-bg p-2">
                      <span className="text-stone-500 block">{HARDWARE_LABELS.storage}</span>
                      <span className="font-bold">{profile.storage.free_gb.toFixed(0)}{UNIT_LABELS.gigabytes} {HARDWARE_LABELS.free_space}</span>
                      <span className="block text-stone-500">
                        {profile.storage.ssd_available ? HARDWARE_LABELS.ssd : HARDWARE_LABELS.hdd}
                      </span>
                    </div>
                    <div className="border border-lawn-border bg-lawn-bg p-2">
                      <span className="text-stone-500 block">{BUTTON_LABELS.recommended}</span>
                      <span className="font-bold text-theme-success uppercase">
                        {profile.recommended_quality}
                      </span>
                    </div>
                  </div>
                </section>
              )}

              {/* Presets Tab */}
              {activeTab === 'presets' && (
                <section className="space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    {PRESETS.map((preset) => {
                      const Icon = preset.icon;
                      const isSelected = selectedPreset === preset.id;
                      const isRecommended = getRecommendedPreset() === preset.id;
                      
                      return (
                        <button
                          key={preset.id}
                          onClick={() => handlePresetSelect(preset.id)}
                          disabled={optimizing}
                          className={`relative border-2 p-4 text-left transition-all ${
                            isSelected
                              ? 'border-lawn-accent bg-lawn-accent/10'
                              : 'border-lawn-border bg-lawn-panel hover:border-lawn-accent/50'
                          } ${optimizing ? 'opacity-50 cursor-not-allowed' : ''}`}
                        >
                          <div className="flex items-center gap-3">
                            <div className={`p-2 ${isSelected ? 'bg-lawn-accent text-lawn-bg' : 'bg-lawn-bg'}`}>
                              <Icon size={20} />
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <span className="font-black text-sm">{preset.label}</span>
                                {isRecommended && (
                                  <span className="text-[10px] bg-theme-success text-lawn-bg px-1.5 py-0.5 uppercase font-bold">
                                    {BUTTON_LABELS.recommended}
                                  </span>
                                )}
                              </div>
                              <p className="text-xs text-stone-500 mt-0.5">{preset.desc}</p>
                            </div>
                          </div>
                          {isSelected && optimizing && (
                            <div className="absolute inset-0 flex items-center justify-center bg-lawn-bg/80">
                              <Activity className="w-6 h-6 animate-spin text-lawn-accent" />
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>

                  {/* Optimization Results */}
                  {optimizationResult && (
                    <div className="border-2 border-lawn-border bg-lawn-panel p-4">
                      <h4 className="text-xs font-black uppercase tracking-wider text-lawn-border mb-3 flex items-center gap-2">
                        <Check size={14} />
                        {SECTION_HEADERS.optimizationResults}
                      </h4>
                      <p className="text-xs text-stone-600 mb-4 leading-relaxed">
                        {optimizationResult.metadata.optimization_reason}
                      </p>
                      <div className="grid grid-cols-3 gap-3">
                        <div className="bg-lawn-bg border border-lawn-border p-3">
                          <span className="text-[10px] text-stone-500 uppercase">{METRIC_LABELS.quality_level}</span>
                          <span className="block font-bold text-sm capitalize">
                            {optimizationResult.metadata.quality_level}
                          </span>
                        </div>
                        <div className="bg-lawn-bg border border-lawn-border p-3">
                          <span className="text-[10px] text-stone-500 uppercase">{METRIC_LABELS.vram_usage}</span>
                          <span className="block font-bold text-sm">
                            {optimizationResult.metadata.estimated_vram_usage_gb.toFixed(1)}{UNIT_LABELS.gigabytes}
                          </span>
                        </div>
                        <div className="bg-lawn-bg border border-lawn-border p-3">
                          <span className="text-[10px] text-stone-500 uppercase">{METRIC_LABELS.latency}</span>
                          <span className="block font-bold text-sm">
                            {optimizationResult.metadata.estimated_latency_ms}{UNIT_LABELS.milliseconds}
                          </span>
                        </div>
                      </div>
                      {optimizationResult.metadata.tradeoffs.length > 0 && (
                        <div className="mt-4">
                          <span className="text-[10px] text-stone-500 uppercase">{METRIC_LABELS.tradeoffs}</span>
                          <ul className="mt-2 space-y-1">
                            {optimizationResult.metadata.tradeoffs.map((tradeoff, i) => (
                              <li key={i} className="text-xs text-stone-600 flex items-start gap-2">
                                <AlertCircle size={12} className="mt-0.5 flex-shrink-0" />
                                {tradeoff}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      <button
                        onClick={() => onApplySettings(optimizationResult.settings as Partial<TranscriptionSettings>)}
                        className="w-full mt-4 border-2 border-lawn-accent bg-lawn-accent text-lawn-bg py-2 text-xs font-black uppercase tracking-wider hover:shadow-brutal-sm transition-all"
                      >
                        {BUTTON_LABELS.applyOptimizedSettings}
                      </button>
                    </div>
                  )}
                </section>
              )}

              {/* Manual Tab */}
              {activeTab === 'manual' && optimizationResult && (
                <section className="space-y-6">
                  {/* Model Settings */}
                  <div className="border-2 border-lawn-border bg-lawn-panel p-4">
                    <h4 className="text-xs font-black uppercase tracking-wider text-lawn-border mb-4 flex items-center gap-2">
                      <Brain size={14} />
                      {SECTION_HEADERS.modelSettings}
                    </h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-[10px] font-bold uppercase text-stone-500 mb-2">
                          {SETTING_LABELS.model_name}
                        </label>
                        <select
                          value={manualSettings.model_name}
                          onChange={(e) => handleManualChange('model_name', e.target.value)}
                          className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-xs font-bold"
                        >
                          <option value="tiny">{MODEL_NAMES.tiny}</option>
                          <option value="base">{MODEL_NAMES.base}</option>
                          <option value="small">{MODEL_NAMES.small}</option>
                          <option value="medium">{MODEL_NAMES.medium}</option>
                          <option value="large-v3">{MODEL_NAMES['large-v3']}</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] font-bold uppercase text-stone-500 mb-2">
                          {SETTING_LABELS.compute_type}
                        </label>
                        <select
                          value={manualSettings.compute_type}
                          onChange={(e) => handleManualChange('compute_type', e.target.value)}
                          className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-xs font-bold"
                        >
                          <option value="int8">{COMPUTE_TYPE_LABELS.int8}</option>
                          <option value="float16">{COMPUTE_TYPE_LABELS.float16}</option>
                          <option value="float32">{COMPUTE_TYPE_LABELS.float32}</option>
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* Audio Pipeline */}
                  <div className="border-2 border-lawn-border bg-lawn-panel p-4">
                    <h4 className="text-xs font-black uppercase tracking-wider text-lawn-border mb-4 flex items-center gap-2">
                      <Mic size={14} />
                      {SECTION_HEADERS.audioPipeline}
                    </h4>
                    <div className="space-y-4">
                      <div>
                        <label className="flex justify-between text-[10px] font-bold uppercase text-stone-500 mb-2">
                          <span>Chunk Duration</span>
                          <span>{manualSettings.chunk_duration}s</span>
                        </label>
                        <input
                          type="range"
                          min="0.1"
                          max="2.0"
                          step="0.1"
                          value={manualSettings.chunk_duration}
                          onChange={(e) => handleManualChange('chunk_duration', parseFloat(e.target.value))}
                          className="w-full"
                        />
                      </div>
                      <div>
                        <label className="flex justify-between text-[10px] font-bold uppercase text-stone-500 mb-2">
                          <span>Overlap Ratio</span>
                          <span>{Math.round((manualSettings.overlap_ratio || 0) * 100)}%</span>
                        </label>
                        <input
                          type="range"
                          min="0"
                          max="0.5"
                          step="0.05"
                          value={manualSettings.overlap_ratio}
                          onChange={(e) => handleManualChange('overlap_ratio', parseFloat(e.target.value))}
                          className="w-full"
                        />
                      </div>
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={manualSettings.vad_enabled}
                          onChange={(e) => handleManualChange('vad_enabled', e.target.checked)}
                          className="w-4 h-4 border-2 border-lawn-border"
                        />
                        <span className="text-xs font-bold">Enable Voice Activity Detection</span>
                      </div>
                      {manualSettings.vad_enabled && (
                        <div>
                          <label className="flex justify-between text-[10px] font-bold uppercase text-stone-500 mb-2">
                            <span>VAD Threshold</span>
                            <span>{manualSettings.vad_threshold_db}dB</span>
                          </label>
                          <input
                            type="range"
                            min="-60"
                            max="-20"
                            step="5"
                            value={manualSettings.vad_threshold_db}
                            onChange={(e) => handleManualChange('vad_threshold_db', parseInt(e.target.value))}
                            className="w-full"
                          />
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Quality Filtering */}
                  <div className="border-2 border-lawn-border bg-lawn-panel p-4">
                    <h4 className="text-xs font-black uppercase tracking-wider text-lawn-border mb-4 flex items-center gap-2">
                      <Sliders size={14} />
                      {SECTION_HEADERS.qualityFiltering}
                    </h4>
                    <div className="space-y-4">
                      <div>
                        <label className="flex justify-between text-[10px] font-bold uppercase text-stone-500 mb-2">
                          <span>{SETTING_LABELS.confidence_threshold}</span>
                          <span>{Math.round((manualSettings.confidence_threshold || 0) * 100)}%</span>
                        </label>
                        <input
                          type="range"
                          min="0.5"
                          max="0.95"
                          step="0.05"
                          value={manualSettings.confidence_threshold}
                          onChange={(e) => handleManualChange('confidence_threshold', parseFloat(e.target.value))}
                          className="w-full"
                        />
                      </div>
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={manualSettings.enable_filler_filter}
                          onChange={(e) => handleManualChange('enable_filler_filter', e.target.checked)}
                          className="w-4 h-4 border-2 border-lawn-border"
                        />
                        <span className="text-xs font-bold">{SETTING_LABELS.enable_filler_filter} (um, uh)</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={manualSettings.enable_hallucination_filter}
                          onChange={(e) => handleManualChange('enable_hallucination_filter', e.target.checked)}
                          className="w-4 h-4 border-2 border-lawn-border"
                        />
                        <span className="text-xs font-bold">{SETTING_LABELS.enable_hallucination_filter}</span>
                      </div>
                    </div>
                  </div>

                  {/* Performance */}
                  <div className="border-2 border-lawn-border bg-lawn-panel p-4">
                    <h4 className="text-xs font-black uppercase tracking-wider text-lawn-border mb-4 flex items-center gap-2">
                      <Zap size={14} />
                      {SECTION_HEADERS.performance}
                    </h4>
                    <div className="space-y-4">
                      <div>
                        <label className="flex justify-between text-[10px] font-bold uppercase text-stone-500 mb-2">
                          <span>{SETTING_LABELS.max_workers}</span>
                          <span>{manualSettings.max_workers}</span>
                        </label>
                        <input
                          type="range"
                          min="1"
                          max="8"
                          step="1"
                          value={manualSettings.max_workers}
                          onChange={(e) => handleManualChange('max_workers', parseInt(e.target.value))}
                          className="w-full"
                        />
                      </div>
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={manualSettings.use_parallel_processing}
                          onChange={(e) => handleManualChange('use_parallel_processing', e.target.checked)}
                          className="w-4 h-4 border-2 border-lawn-border"
                        />
                        <span className="text-xs font-bold">{SETTING_LABELS.use_parallel_processing}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={manualSettings.preload_model}
                          onChange={(e) => handleManualChange('preload_model', e.target.checked)}
                          className="w-4 h-4 border-2 border-lawn-border"
                        />
                        <span className="text-xs font-bold">{SETTING_LABELS.preload_model}</span>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={applyManualSettings}
                    className="w-full border-2 border-lawn-accent bg-lawn-accent text-lawn-bg py-3 text-xs font-black uppercase tracking-wider hover:shadow-brutal-sm transition-all"
                  >
                    {BUTTON_LABELS.applyManualSettings}
                  </button>
                </section>
              )}

              {activeTab === 'hotkey' && (
                <section className="space-y-6">
                  <HotkeySettings />
                </section>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t-2 border-lawn-border bg-lawn-panel">
          <span className="text-xs text-stone-500">
            Changes are applied immediately except for manual settings
          </span>
          <button
            onClick={onClose}
            className="border-2 border-lawn-border bg-lawn-bg px-6 py-2 text-xs font-black uppercase tracking-wider hover:bg-lawn-accent hover:text-lawn-bg transition-colors"
          >
            {BUTTON_LABELS.close}
          </button>
        </div>
      </div>
    </div>
  );
}
