/**
 * TranscriptionSection - Transcription and refinement settings
 * 
 * Manages transcription language, punctation, formatting, refinement options,
 * text filters, coaching settings, and preset management.
 * Props: SectionProps with selectedPreset, availableModels, onApplyPreset callback.
 */
import { Mic, Zap, Gauge, Filter, Activity, Keyboard } from 'lucide-react';
import { useState } from 'react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Toggle, Slider, NumberInput, Select } from '../controls';
import { PRESETS } from '../presets';
import { cn } from '../utils';
import type { SectionProps } from '../types';
import {
  SETTINGS_SECTION_TEXT,
  REFINEMENT_MODE_LABELS,
  REFINEMENT_PROFILE_LABELS,
} from '../../../config/text';
import { getLanguageLabel } from '../../../lib/languages';
import { RENDERER_STRINGS } from '../../../strings/en';
import { isFakeSetting } from '../../../config/settingsSchema';

interface TranscriptionSectionProps extends SectionProps {
  selectedPreset: string;
  availableModels: string[];
  onApplyPreset: (presetId: string) => void;
}

export function TranscriptionSection({
  settings,
  modelManager,
  availableModels,
  availableLanguages,
  isChanged,
  updateSetting,
  resetSetting,
  selectedPreset,
  onApplyPreset,
}: TranscriptionSectionProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const text = SETTINGS_SECTION_TEXT.transcription;
  const transcriptionText = RENDERER_STRINGS.settings.transcription;
  const common = RENDERER_STRINGS.settings.common;
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
  const refinementModeKey = String(settings.transcription.refinement_mode) as keyof typeof REFINEMENT_MODE_LABELS;
  const refinementProfileKey = String(settings.transcription.refinement_profile) as keyof typeof REFINEMENT_PROFILE_LABELS;
  const activeProfileSummary = {
    preset: PRESETS.find((preset) => preset.id === selectedPreset)?.name ?? common.custom,
    language: getLanguageLabel(settings.hotkey.language),
    finishMode: settings.hotkey.finish_mode_default.replace(/_/g, ' '),
    refinementMode: REFINEMENT_MODE_LABELS[refinementModeKey] ?? String(settings.transcription.refinement_mode),
    refinementProfile: REFINEMENT_PROFILE_LABELS[refinementProfileKey] ?? String(settings.transcription.refinement_profile),
    microphoneHotkey: settings.hotkey.microphone_key_combination || common.unassigned,
    systemHotkey: settings.hotkey.system_key_combination || common.unassigned,
  };

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
          title={transcriptionText.micLanguageTitle}
          description={transcriptionText.micLanguageDescription}
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
          title={transcriptionText.modeTitle}
          description={transcriptionText.modeDescription}
          changed={isChanged('transcription', 'transcription_mode')}
          onReset={() => resetSetting('transcription', 'transcription_mode')}
        >
          <Select
            value={settings.transcription.transcription_mode}
            options={[
              ...transcriptionText.modeOptions,
            ]}
            onChange={(v) => updateSetting('transcription', 'transcription_mode', v)}
          />
        </SettingCard>

        <SettingCard
          title={text.profile_summary_title}
          description={text.profile_summary_description}
        >
          <div className="grid gap-2 text-xs font-bold text-lawn-border sm:grid-cols-2">
            <div className="border-2 border-lawn-border bg-lawn-bg px-3 py-2">
                <div className="text-[10px] uppercase tracking-[0.12em] text-stone-500">{transcriptionText.profileSummaryLabels.preset}</div>
              <div className="mt-1">{activeProfileSummary.preset}</div>
            </div>
            <div className="border-2 border-lawn-border bg-lawn-bg px-3 py-2">
                <div className="text-[10px] uppercase tracking-[0.12em] text-stone-500">{transcriptionText.profileSummaryLabels.language}</div>
              <div className="mt-1">{activeProfileSummary.language}</div>
            </div>
            <div className="border-2 border-lawn-border bg-lawn-bg px-3 py-2">
                <div className="text-[10px] uppercase tracking-[0.12em] text-stone-500">{transcriptionText.profileSummaryLabels.finish}</div>
              <div className="mt-1">{activeProfileSummary.finishMode}</div>
            </div>
            <div className="border-2 border-lawn-border bg-lawn-bg px-3 py-2">
                <div className="text-[10px] uppercase tracking-[0.12em] text-stone-500">{transcriptionText.profileSummaryLabels.refinement}</div>
              <div className="mt-1">{activeProfileSummary.refinementMode} · {activeProfileSummary.refinementProfile}</div>
            </div>
          </div>
        </SettingCard>

        <SettingCard
          title={text.refinement_mode_title}
          description={text.refinement_mode_description}
          changed={isChanged('transcription', 'refinement_mode')}
          onReset={() => resetSetting('transcription', 'refinement_mode')}
        >
          <Select
            value={settings.transcription.refinement_mode}
            options={[
              ...transcriptionText.refinementModeOptions,
            ]}
            onChange={(v) => updateSetting('transcription', 'refinement_mode', v)}
          />
        </SettingCard>

        <SettingCard
          title={text.refinement_profile_title}
          description={text.refinement_profile_description}
          changed={isChanged('transcription', 'refinement_profile')}
          onReset={() => resetSetting('transcription', 'refinement_profile')}
        >
          <Select
            value={settings.transcription.refinement_profile}
            options={[
              ...transcriptionText.refinementProfileOptions,
            ]}
            onChange={(v) => updateSetting('transcription', 'refinement_profile', v)}
          />
        </SettingCard>

        <SettingCard
          title={text.finish_mode_title}
          description={text.finish_mode_description}
          changed={isChanged('hotkey', 'finish_mode_default')}
          onReset={() => resetSetting('hotkey', 'finish_mode_default')}
        >
          <Select
            value={settings.hotkey.finish_mode_default}
            options={[
              ...transcriptionText.finishModeOptions,
            ]}
            onChange={(v) => updateSetting('hotkey', 'finish_mode_default', v)}
          />
        </SettingCard>

        <SettingCard
          title={text.refinement_toggle_title}
          description={text.refinement_toggle_description}
          changed={isChanged('hotkey', 'enable_refiner_on_stop')}
          onReset={() => resetSetting('hotkey', 'enable_refiner_on_stop')}
        >
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs text-stone-500">
              {settings.refiner.runtime_enabled
                ? transcriptionText.refinerEnabledHint(settings.refiner.selected_model_id)
                : transcriptionText.refinerDisabledHint}
            </div>
            <Toggle
              checked={settings.hotkey.enable_refiner_on_stop}
              onChange={(checked) => updateSetting('hotkey', 'enable_refiner_on_stop', checked)}
            />
          </div>
        </SettingCard>

        <SettingCard
          title={text.cleanup_instructions_title}
          description={text.cleanup_instructions_description}
          changed={isChanged('refiner', 'cleanup_instructions')}
          onReset={() => resetSetting('refiner', 'cleanup_instructions')}
        >
          <textarea
            value={settings.refiner.cleanup_instructions}
            onChange={(event) => updateSetting('refiner', 'cleanup_instructions', event.target.value)}
            rows={4}
            placeholder={transcriptionText.cleanupPlaceholder}
            className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm text-lawn-border outline-none focus:border-lawn-accent"
          />
        </SettingCard>

        <SettingCard
          title={text.hotkey_summary_title}
          description={text.hotkey_summary_description}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="border-2 border-lawn-border bg-lawn-bg px-3 py-2">
              <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.12em] text-stone-500">
                <Keyboard className="h-3.5 w-3.5 text-lawn-accent" />
                {transcriptionText.profileSummaryLabels.microphone}
              </div>
              <div className="mt-1 text-sm font-bold text-lawn-border">{activeProfileSummary.microphoneHotkey}</div>
            </div>
            <div className="border-2 border-lawn-border bg-lawn-bg px-3 py-2">
              <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.12em] text-stone-500">
                <Keyboard className="h-3.5 w-3.5 text-lawn-accent" />
                {transcriptionText.profileSummaryLabels.systemAudio}
              </div>
              <div className="mt-1 text-sm font-bold text-lawn-border">{activeProfileSummary.systemHotkey}</div>
            </div>
          </div>
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
              ...transcriptionText.computeTypeOptions,
            ]}
            onChange={(v) => updateSetting('transcription', 'compute_type', v)}
          />
        </SettingCard>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h4 className="text-sm font-bold">{transcriptionText.advancedTuningTitle}</h4>
              <p className="text-xs text-stone-500">
                {transcriptionText.advancedTuningDescription}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowAdvanced((value) => !value)}
              className="border-2 border-lawn-border bg-lawn-bg px-3 py-1 text-xs font-bold uppercase text-lawn-border hover:bg-lawn-accent hover:text-lawn-bg"
            >
              {showAdvanced ? transcriptionText.hideAdvanced : transcriptionText.showAdvanced}
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
            {!isFakeSetting('transcription', 'patience') && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <label className="text-xs font-bold text-stone-500">{text.patience_label}</label>
              </div>
              <NumberInput
                value={settings.transcription.patience}
                min={0.1}
                max={5}
                step={0.1}
                onChange={(v) => updateSetting('transcription', 'patience', v)}
              />
            </div>
            )}
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
            {!isFakeSetting('transcription', 'use_parallel_processing') && (
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
            )}
            {!isFakeSetting('transcription', 'preload_model') && (
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
            )}
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
            {!isFakeSetting('transcription', 'max_workers') && (
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
            )}
          </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
