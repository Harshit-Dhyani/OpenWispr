import { Bot } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { HardwareProfileDisplay } from '../HardwareProfileDisplay';
import { ModelCatalogBlock } from '../ModelComponents';
import { Toggle } from '../controls';
import type { SectionProps } from '../types';
import { SETTINGS_SECTION_TEXT } from '../../../config/text';
import { RENDERER_STRINGS } from '../../../strings/en';

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
  const modelText = RENDERER_STRINGS.settings.models;
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
            <div className="text-xs font-bold uppercase text-stone-500">{modelText.engineCards.asrTitle}</div>
            <div className="mt-1 text-sm font-bold">{modelText.engineCards.asrRuntime}</div>
            <p className="mt-2 text-xs text-stone-500">
              {modelText.engineCards.asrDescription}
            </p>
          </div>
          <div className="border-2 border-lawn-border bg-lawn-panel p-4">
            <div className="text-xs font-bold uppercase text-stone-500">{modelText.engineCards.refinerTitle}</div>
            <div className="mt-1 text-sm font-bold">{modelText.engineCards.refinerRuntime}</div>
            <p className="mt-2 text-xs text-stone-500">
              {modelText.engineCards.refinerDescription}
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

      </div>
    </div>
  );
}
