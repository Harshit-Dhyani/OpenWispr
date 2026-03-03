import { Mic, Zap, Gauge, Filter, Activity } from 'lucide-react';
import { useState } from 'react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Toggle, Slider, NumberInput, Select } from '../controls';
import { PRESETS } from '../presets';
import { cn } from '../utils';
import type { SectionProps } from '../types';
import { SETTINGS_SECTION_TEXT, COMPUTE_TYPE_LABELS } from '../../../config/text';

interface TranscriptionSectionProps extends SectionProps {
  selectedPreset: string;
  availableModels: string[];
  onApplyPreset: (presetId: string) => void;
}

export function TranscriptionSection({
  settings,
  modelManager,
  availableModels,
  isChanged,
  updateSetting,
  resetSetting,
  selectedPreset,
  onApplyPreset,
}: TranscriptionSectionProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const text = SETTINGS_SECTION_TEXT.transcription;
  const asrModels = modelManager?.catalog.filter((entry) => entry.category === 'asr') ?? [];
  const asrOptions = (asrModels.length ? asrModels : availableModels.map((m) => ({
    id: m,
    display_name: m.charAt(0).toUpperCase() + m.slice(1),
    installed: true,
  })) as Array<{ id: string; display_name: string; installed: boolean }>).map((m) => ({
    value: m.id,
    label: `${m.display_name}${m.installed ? '' : text.not_installed_suffix}`,
  }));
  const defaultCaptureSource = settings.audio.default_capture_source ?? settings.audio.captureMode;

  const handleSourceModelChange = (captureSource: 'microphone' | 'system', modelId: string) => {
    const field = captureSource === 'system' ? 'system_asr_model_id' : 'microphone_asr_model_id';
    updateSetting('transcription', field, modelId);

    const selectedAsr = asrModels.find((entry) => entry.id === modelId);
    if (defaultCaptureSource === captureSource) {
      updateSetting('transcription', 'default_asr_model_id', modelId);
      if (selectedAsr?.runtime_model_name) {
        updateSetting('transcription', 'model_name', selectedAsr.runtime_model_name);
      }
    }
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        title={text.title}
        icon={Mic}
        description={text.description}
      />

      {/* Preset Selector */}
      <div className="border-2 border-lawn-border bg-lawn-panel p-4">
        <div className="flex items-center gap-2 mb-4">
          <Zap className="w-4 h-4 text-lawn-accent" />
          <h4 className="text-sm font-bold">{text.quick_presets_title}</h4>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {PRESETS.map((preset) => (
            <button
              key={preset.id}
              onClick={() => onApplyPreset(preset.id)}
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
          title={text.microphone_asr_title}
          description={text.microphone_asr_description}
          changed={isChanged('transcription', 'microphone_asr_model_id')}
          onReset={() => resetSetting('transcription', 'microphone_asr_model_id')}
        >
          <Select
            value={settings.transcription.microphone_asr_model_id}
            options={asrOptions}
            onChange={(v) => handleSourceModelChange('microphone', v)}
          />
        </SettingCard>

        <SettingCard
          title={text.system_asr_title}
          description={text.system_asr_description}
          changed={isChanged('transcription', 'system_asr_model_id')}
          onReset={() => resetSetting('transcription', 'system_asr_model_id')}
        >
          <Select
            value={settings.transcription.system_asr_model_id}
            options={asrOptions}
            onChange={(v) => handleSourceModelChange('system', v)}
          />
        </SettingCard>

        <SettingCard
          title={text.fallback_asr_title}
          description={text.fallback_asr_description}
          changed={isChanged('transcription', 'default_asr_model_id')}
          onReset={() => resetSetting('transcription', 'default_asr_model_id')}
        >
          <Select
            value={settings.transcription.default_asr_model_id}
            options={asrOptions}
            onChange={(v) => updateSetting('transcription', 'default_asr_model_id', v)}
          />
        </SettingCard>

        <SettingCard
          title={text.compute_type_title}
          description={text.compute_type_description}
          changed={isChanged('transcription', 'compute_type')}
          onReset={() => resetSetting('transcription', 'compute_type')}
        >
          <Select
            value={settings.transcription.compute_type}
            options={[
              { value: 'float16', label: COMPUTE_TYPE_LABELS.float16 },
              { value: 'int8', label: COMPUTE_TYPE_LABELS.int8 },
              { value: 'int8_float16', label: COMPUTE_TYPE_LABELS.int8_float16 },
            ]}
            onChange={(v) => updateSetting('transcription', 'compute_type', v)}
          />
        </SettingCard>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h4 className="text-sm font-bold">Advanced Tuning</h4>
              <p className="text-xs text-stone-500">
                Keep these on defaults unless you are troubleshooting quality, latency, or memory usage.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowAdvanced((value) => !value)}
              className="border-2 border-lawn-border bg-white px-3 py-1 text-xs font-bold uppercase"
            >
              {showAdvanced ? 'Hide' : 'Show'}
            </button>
          </div>
        </div>

        {showAdvanced ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <SettingCard
                title={text.chunk_duration_title}
                description={text.chunk_duration_description}
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
                title={text.overlap_ratio_title}
                description={text.overlap_ratio_description}
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
                title={text.min_segment_length_title}
                description={text.min_segment_length_description}
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
            {text.beam_group_title}
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="text-xs font-bold text-stone-500 block mb-2">{text.beam_size_label}</label>
              <NumberInput
                value={settings.transcription.beam_size}
                min={1}
                max={20}
                onChange={(v) => updateSetting('transcription', 'beam_size', v)}
              />
            </div>
            <div>
              <label className="text-xs font-bold text-stone-500 block mb-2">{text.best_of_label}</label>
              <NumberInput
                value={settings.transcription.best_of}
                min={1}
                max={20}
                onChange={(v) => updateSetting('transcription', 'best_of', v)}
              />
            </div>
            <div>
              <label className="text-xs font-bold text-stone-500 block mb-2">{text.patience_label}</label>
              <NumberInput
                value={settings.transcription.patience}
                min={0.1}
                max={5}
                step={0.1}
                onChange={(v) => updateSetting('transcription', 'patience', v)}
              />
            </div>
            <div>
              <label className="text-xs font-bold text-stone-500 block mb-2">{text.temperature_label}</label>
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
            {text.quality_group_title}
          </h4>
          <div className="space-y-4">
            <SettingCard
              title={text.confidence_threshold_title}
              description={text.confidence_threshold_description}
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
                <span className="text-sm font-bold block">{text.filler_filter_title}</span>
                <p className="text-xs text-stone-500">{text.filler_filter_description}</p>
              </div>
              <Toggle
                checked={settings.transcription.enable_filler_filter}
                onChange={(v) => updateSetting('transcription', 'enable_filler_filter', v)}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">{text.hallucination_filter_title}</span>
                <p className="text-xs text-stone-500">{text.hallucination_filter_description}</p>
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
            {text.performance_group_title}
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">{text.parallel_processing_title}</span>
                <p className="text-xs text-stone-500">{text.parallel_processing_description}</p>
              </div>
              <Toggle
                checked={settings.transcription.use_parallel_processing}
                onChange={(v) => updateSetting('transcription', 'use_parallel_processing', v)}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">{text.preload_model_title}</span>
                <p className="text-xs text-stone-500">{text.preload_model_description}</p>
              </div>
              <Toggle
                checked={settings.transcription.preload_model}
                onChange={(v) => updateSetting('transcription', 'preload_model', v)}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">{text.hotkey_optimized_title}</span>
                <p className="text-xs text-stone-500">{text.hotkey_optimized_description}</p>
              </div>
              <Toggle
                checked={settings.transcription.hotkey_optimized}
                onChange={(v) => updateSetting('transcription', 'hotkey_optimized', v)}
              />
            </div>
            <SettingCard
              title={text.max_workers_title}
              description={text.max_workers_description}
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
          </>
        ) : null}
      </div>
    </div>
  );
}
