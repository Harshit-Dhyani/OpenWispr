/**
 * ModelSection - Model and provider settings
 * 
 * Manages STT/refiner engine preference, provider selection, model catalog,
 * runtime configuration, and provider health display.
 * Props: SectionProps with modelManager and hardwareProfile.
 */
import { Bot } from 'lucide-react';
import { useEffect, useState } from 'react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { HardwareProfileDisplay } from '../HardwareProfileDisplay';
import { ModelCatalogBlock } from '../ModelComponents';
import { ProviderHealthDisplay } from '../ProviderHealthDisplay';
import { Select, Toggle } from '../controls';
import type { SectionProps } from '../types';
import { SETTINGS_SECTION_TEXT, SETTING_DESCRIPTIONS } from '../../../config/text';
import { RENDERER_STRINGS } from '../../../strings/en';
import { VALID_REFINER_ENGINES } from '../../../config/generated/constants';

type ProviderModel = {
  id: string;
  name: string;
  provider: string;
};

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
  
  const [providerModels, setProviderModels] = useState<ProviderModel[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  const enginePref = settings.refiner.engine_preference;
  const isExternalProvider = enginePref === 'ollama' || enginePref === 'lm_studio';

  async function fetchProviderModels() {
    if (!isExternalProvider || !settings.refiner.runtime_enabled) {
      setProviderModels([]);
      return;
    }
    setLoadingModels(true);
    try {
      const response = await window.openwisprDesktop.fetchJson('/api/providers/models');
      setProviderModels(response as ProviderModel[]);
    } catch (error) {
      console.error('Failed to fetch provider models:', error);
      setProviderModels([]);
    } finally {
      setLoadingModels(false);
    }
  }

  useEffect(() => {
    void fetchProviderModels();
  }, [enginePref, settings.refiner.runtime_enabled, settings.refiner.refiner_provider_base_url]);

  return (
    <div className="space-y-6">
      <SectionHeader
        title={text.title}
        icon={Bot}
        description={text.description}
      />

      <HardwareProfileDisplay profile={hardwareProfile} />

      {/* Provider Status - Most Important - Show at Top */}
      <ProviderHealthDisplay />

      <div className="grid gap-4">
        {/* Engine Preference - LLM Inference */}
        <SettingCard
          title={SETTING_DESCRIPTIONS.engine_preference}
          description={SETTING_DESCRIPTIONS.engine_preference}
          changed={isChanged('refiner', 'engine_preference')}
          onReset={() => resetSetting('refiner', 'engine_preference')}
        >
          <Select
            value={settings.refiner.engine_preference}
            onChange={(value: string) => updateSetting('refiner', 'engine_preference', value as 'llamacpp' | 'lm_studio' | 'ollama')}
            options={VALID_REFINER_ENGINES.map((engine) => ({
              value: engine,
              label: engine === 'llamacpp' ? 'Local GGUF Files (llamacpp)' : engine === 'lm_studio' ? 'LM Studio Server' : 'Ollama Server',
            }))}
          />
        </SettingCard>

        {/* Local Refiner Runtime Toggle */}
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

        {/* Model Selection - Show based on engine type */}
        {isExternalProvider && settings.refiner.runtime_enabled && (
          <SettingCard
            title="Select Model"
            description={`Choose a model from your ${enginePref === 'ollama' ? 'Ollama' : 'LM Studio'} server`}
            changed={isChanged('refiner', 'custom_model_id')}
            onReset={() => resetSetting('refiner', 'custom_model_id')}
          >
            <div className="space-y-3">
              {loadingModels ? (
                <div className="text-xs text-stone-500">Loading models...</div>
              ) : providerModels.length > 0 ? (
                <select
                  value={settings.refiner.custom_model_id}
                  onChange={(e) => updateSetting('refiner', 'custom_model_id', e.target.value)}
                  className="w-full h-10 px-3 pr-10 border-2 border-lawn-border bg-lawn-bg text-sm font-bold focus:border-lawn-accent focus:outline-none appearance-none cursor-pointer"
                >
                  <option value="">Select a model...</option>
                  {providerModels.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.name}
                    </option>
                  ))}
                </select>
              ) : (
                <div className="text-xs text-stone-500">
                  No models found. Make sure {enginePref === 'ollama' ? 'Ollama' : 'LM Studio'} is running at {enginePref === 'ollama' ? 'localhost:11434' : 'localhost:1234'} and you have downloaded models.
                </div>
              )}
              
              <button
                onClick={() => void fetchProviderModels()}
                className="text-xs text-lawn-accent hover:underline"
              >
                Refresh models
              </button>
            </div>
          </SettingCard>
        )}

        {/* Catalog Models - Show only for llama.cpp */}
        {!isExternalProvider && (
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
        )}

        {/* Engine Status Cards */}
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

      </div>
    </div>
  );
}
