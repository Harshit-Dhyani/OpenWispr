import { Bot } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { HardwareProfileDisplay } from '../HardwareProfileDisplay';
import { ModelCatalogBlock } from '../ModelComponents';
import { Select, Toggle } from '../controls';
import type { SectionProps } from '../types';
import { SETTINGS_SECTION_TEXT, REFINEMENT_MODE_LABELS } from '../../../config/text';

export function ModelSection({
  settings,
  hardwareProfile,
  modelManager,
  isChanged,
  updateSetting,
  resetSetting,
  onDownloadModel,
  onCancelModelDownload,
  onRemoveModel,
}: SectionProps) {
  const text = SETTINGS_SECTION_TEXT.models;
  const asrModels = modelManager?.catalog.filter((entry) => entry.category === 'asr') ?? [];
  const refinerModels = modelManager?.catalog.filter((entry) => entry.category === 'refiner') ?? [];

  return (
    <div className="space-y-6">
      <SectionHeader
        title={text.title}
        icon={Bot}
        description={text.description}
      />

      <HardwareProfileDisplay profile={hardwareProfile} />

      <div className="grid gap-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="border-2 border-lawn-border bg-lawn-panel p-4">
            <div className="text-xs font-bold uppercase text-stone-500">ASR Engine</div>
            <div className="mt-1 text-sm font-bold">faster-whisper (local)</div>
            <p className="mt-2 text-xs text-stone-500">
              Whisper checkpoints run through the faster-whisper engine for local speech-to-text.
            </p>
          </div>
          <div className="border-2 border-lawn-border bg-lawn-panel p-4">
            <div className="text-xs font-bold uppercase text-stone-500">Refiner Runtime</div>
            <div className="mt-1 text-sm font-bold">llama.cpp (local)</div>
            <p className="mt-2 text-xs text-stone-500">
              Used only for final cleanup. Partial text never goes through the refiner.
            </p>
          </div>
        </div>

        <ModelCatalogBlock
          title={text.asr_title}
          description={text.asr_description}
          category="asr"
          models={asrModels}
          selectedModelId={settings.transcription.default_asr_model_id}
          modelManager={modelManager}
          runtimeEnabled={true}
          onSelect={(value) => updateSetting('transcription', 'default_asr_model_id', value)}
          onDownload={onDownloadModel}
          onCancelDownload={onCancelModelDownload}
          onRemove={onRemoveModel}
        />

        <ModelCatalogBlock
          title={text.refiner_title}
          description={text.refiner_description}
          category="refiner"
          models={refinerModels}
          selectedModelId={settings.refiner.selected_model_id}
          modelManager={modelManager}
          runtimeEnabled={settings.refiner.runtime_enabled}
          onSelect={(value) => updateSetting('refiner', 'selected_model_id', value)}
          onDownload={onDownloadModel}
          onCancelDownload={onCancelModelDownload}
          onRemove={onRemoveModel}
        />

        <SettingCard
          title={text.runtime_title}
          description={text.runtime_description}
          changed={isChanged('refiner', 'runtime_enabled')}
          onReset={() => resetSetting('refiner', 'runtime_enabled')}
        >
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs text-stone-500">
              {text.runtime_hint}
            </div>
            <Toggle
              checked={settings.refiner.runtime_enabled}
              onChange={(checked) => updateSetting('refiner', 'runtime_enabled', checked)}
            />
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
              { value: 'off', label: REFINEMENT_MODE_LABELS.off },
              { value: 'strict', label: REFINEMENT_MODE_LABELS.strict },
              { value: 'polished', label: REFINEMENT_MODE_LABELS.polished },
            ]}
            onChange={(v) => updateSetting('transcription', 'refinement_mode', v)}
          />
        </SettingCard>

        <SettingCard
          title="Cleanup Instructions"
          description="Optional extra instructions for the final refiner pass. Applied only after final transcription, never to partials."
          changed={isChanged('refiner', 'cleanup_instructions')}
          onReset={() => resetSetting('refiner', 'cleanup_instructions')}
        >
          <textarea
            value={settings.refiner.cleanup_instructions}
            onChange={(event) => updateSetting('refiner', 'cleanup_instructions', event.target.value)}
            rows={4}
            placeholder="Example: keep technical terms exactly, add punctuation, and preserve speaker intent."
            className="w-full border-2 border-lawn-border bg-white px-3 py-2 text-sm outline-none focus:border-lawn-accent"
          />
          <p className="mt-2 text-[11px] text-stone-500">
            Strict mode keeps meaning locked. Polished mode allows cleanup while still preserving facts.
          </p>
        </SettingCard>
      </div>
    </div>
  );
}
