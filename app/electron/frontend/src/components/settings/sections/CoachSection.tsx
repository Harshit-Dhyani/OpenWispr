import { useEffect, useMemo, useState } from 'react';
import { Sparkles } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Select, Toggle } from '../controls';
import type { SectionProps } from '../types';
import { RENDERER_STRINGS } from '../../../strings/en';

type PromptPreviewResponse = {
  system_prompt: string;
  user_prompt: string;
  resolved_template_id: string;
  resolved_template_version: number;
  variables: Record<string, string>;
  warnings?: string[];
};

export function CoachSection({
  settings,
  isChanged,
  updateSetting,
  resetSetting,
}: SectionProps) {
  const text = RENDERER_STRINGS.settings.coach;
  const common = RENDERER_STRINGS.settings.common;
  const [preview, setPreview] = useState<PromptPreviewResponse | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const templateOptions = useMemo(
    () =>
      settings.coach.coach_prompt_templates.map((template) => ({
        value: template.id,
        label: `${template.name} v${template.version}`,
      })),
    [settings.coach.coach_prompt_templates],
  );

  const selectedTemplate = useMemo(
    () =>
      settings.coach.coach_prompt_templates.find(
        (template) => template.id === settings.coach.coach_template_id_mic,
      ) ?? settings.coach.coach_prompt_templates[0],
    [settings.coach.coach_prompt_templates, settings.coach.coach_template_id_mic],
  );

  useEffect(() => {
    let cancelled = false;

    async function loadPreview() {
      try {
        const response = await window.openwisprDesktop.fetchJson('/api/coach/prompt-preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            capture_source: 'microphone',
            original_text: text.sampleOriginalText,
            language_mode: settings.hotkey.language || settings.general.defaultLanguage || 'auto',
            detail_level: settings.coach.coach_detail_level,
            template_id: settings.coach.coach_template_id_mic,
            custom_user_template: settings.coach.coach_prompt_custom_enabled
              ? settings.coach.coach_prompt_custom_text
              : '',
            overrides: settings.coach.coach_overrides,
            privacy_mode: settings.coach.privacy_mode,
            templates: settings.coach.coach_prompt_templates,
          }),
        });
        if (!cancelled) {
          setPreview(response as PromptPreviewResponse);
          setPreviewError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setPreviewError(error instanceof Error ? error.message : text.previewUnavailable);
        }
      }
    }

    void loadPreview();
    return () => {
      cancelled = true;
    };
  }, [
    settings.coach.coach_detail_level,
    settings.coach.coach_overrides,
    settings.coach.coach_prompt_custom_enabled,
    settings.coach.coach_prompt_custom_text,
    settings.coach.coach_prompt_templates,
    settings.coach.coach_template_id_mic,
    settings.coach.privacy_mode,
    settings.general.defaultLanguage,
    settings.hotkey.language,
  ]);

  return (
    <div className="space-y-6">
        <SectionHeader
        title={text.title}
        icon={Sparkles}
        description={text.description}
      />

      <div className="grid gap-4 md:grid-cols-2">
        <SettingCard
          title={text.enableTitle}
          description={text.enableDescription}
          changed={isChanged('coach', 'coach_enabled')}
          onReset={() => resetSetting('coach', 'coach_enabled')}
        >
          <Toggle
            checked={settings.coach.coach_enabled}
            onChange={(value) => updateSetting('coach', 'coach_enabled', value)}
          />
        </SettingCard>

        <SettingCard
          title={text.privacyModeTitle}
          description={text.privacyModeDescription}
          changed={isChanged('coach', 'privacy_mode')}
          onReset={() => resetSetting('coach', 'privacy_mode')}
        >
          <Select
            value={settings.coach.privacy_mode}
            options={[
              ...text.privacyModeOptions,
            ]}
            onChange={(value) => updateSetting('coach', 'privacy_mode', value)}
          />
        </SettingCard>

        <SettingCard
          title={text.detailLevelTitle}
          description={text.detailLevelDescription}
          changed={isChanged('coach', 'coach_detail_level')}
          onReset={() => resetSetting('coach', 'coach_detail_level')}
        >
          <Select
            value={settings.coach.coach_detail_level}
            options={[
              ...text.detailLevelOptions,
            ]}
            onChange={(value) => updateSetting('coach', 'coach_detail_level', value)}
          />
        </SettingCard>

        <SettingCard
          title={text.templateTitle}
          description={text.templateDescription}
          changed={isChanged('coach', 'coach_template_id_mic')}
          onReset={() => resetSetting('coach', 'coach_template_id_mic')}
        >
          <Select
            value={settings.coach.coach_template_id_mic}
            options={templateOptions}
            onChange={(value) => updateSetting('coach', 'coach_template_id_mic', value)}
          />
        </SettingCard>
      </div>

      <div className="border-2 border-lawn-border bg-lawn-panel p-4">
        <h4 className="mb-4 text-sm font-bold">{text.outputTitle}</h4>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-bold">{text.pastePolishedTitle}</div>
              <p className="text-xs text-stone-500">{text.pastePolishedDescription}</p>
            </div>
            <Toggle
              checked={settings.coach.copy_polished_by_default}
              onChange={(value) => updateSetting('coach', 'copy_polished_by_default', value)}
            />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-bold">{text.showDiffTitle}</div>
              <p className="text-xs text-stone-500">{text.showDiffDescription}</p>
            </div>
            <Toggle
              checked={settings.coach.show_diff_view}
              onChange={(value) => updateSetting('coach', 'show_diff_view', value)}
            />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-bold">{text.showFloatingResultTitle}</div>
              <p className="text-xs text-stone-500">{text.showFloatingResultDescription}</p>
            </div>
            <Toggle
              checked={settings.coach.show_floating_coach_result}
              onChange={(value) => updateSetting('coach', 'show_floating_coach_result', value)}
            />
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <SettingCard
          title={text.toneTitle}
          description={text.toneDescription}
          changed={isChanged('coach', 'coach_overrides')}
        >
          <Select
            value={settings.coach.coach_overrides.tone}
            options={[
              ...text.toneOptions,
            ]}
            onChange={(value) =>
              updateSetting('coach', 'coach_overrides', {
                ...settings.coach.coach_overrides,
                tone: value,
              })
            }
          />
        </SettingCard>

        <SettingCard title={text.aggressivenessTitle} description={text.aggressivenessDescription}>
          <Select
            value={settings.coach.coach_overrides.aggressiveness}
            options={[
              ...text.aggressivenessOptions,
            ]}
            onChange={(value) =>
              updateSetting('coach', 'coach_overrides', {
                ...settings.coach.coach_overrides,
                aggressiveness: value,
              })
            }
          />
        </SettingCard>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <SettingCard title={text.fillerRemovalTitle} description={text.fillerRemovalDescription}>
          <Toggle
            checked={settings.coach.coach_overrides.filler_removal}
            onChange={(value) =>
              updateSetting('coach', 'coach_overrides', {
                ...settings.coach.coach_overrides,
                filler_removal: value,
              })
            }
          />
        </SettingCard>

        <SettingCard title={text.keepSlangTitle} description={text.keepSlangDescription}>
          <Toggle
            checked={settings.coach.coach_overrides.keep_slang}
            onChange={(value) =>
              updateSetting('coach', 'coach_overrides', {
                ...settings.coach.coach_overrides,
                keep_slang: value,
              })
            }
          />
        </SettingCard>
      </div>

      <SettingCard title={text.targetStyleTitle} description={text.targetStyleDescription}>
        <Select
          value={settings.coach.coach_overrides.target_style}
          options={[
            ...text.targetStyleOptions,
          ]}
          onChange={(value) =>
            updateSetting('coach', 'coach_overrides', {
              ...settings.coach.coach_overrides,
              target_style: value,
            })
          }
        />
      </SettingCard>

      <SettingCard
        title={text.customPromptTitle}
        description={text.customPromptDescription}
        changed={isChanged('coach', 'coach_prompt_custom_text') || isChanged('coach', 'coach_prompt_custom_enabled')}
        onReset={() => {
          resetSetting('coach', 'coach_prompt_custom_enabled');
          resetSetting('coach', 'coach_prompt_custom_text');
        }}
      >
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-[0.12em] text-stone-500">{common.enableCustomPrompt}</span>
            <Toggle
              checked={settings.coach.coach_prompt_custom_enabled}
              onChange={(value) => updateSetting('coach', 'coach_prompt_custom_enabled', value)}
            />
          </div>
          <textarea
            value={settings.coach.coach_prompt_custom_text}
            onChange={(event) => updateSetting('coach', 'coach_prompt_custom_text', event.target.value)}
            className="min-h-[180px] w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-medium text-lawn-border outline-none"
            placeholder={selectedTemplate?.user_template ?? ''}
          />
        </div>
      </SettingCard>

      <SettingCard title={text.promptPreviewTitle} description={text.promptPreviewDescription}>
        <div className="space-y-3 text-xs">
          {previewError ? (
            <div className="border-2 border-theme-error bg-theme-error/10 p-3 text-theme-error">{previewError}</div>
          ) : null}
          <div className="grid gap-3 md:grid-cols-2">
            <div className="border-2 border-lawn-border bg-lawn-bg p-3">
              <div className="mb-2 text-[10px] font-black uppercase tracking-[0.12em] text-stone-500">{common.systemPrompt}</div>
              <pre className="whitespace-pre-wrap break-words text-[11px] leading-5 text-lawn-border">{preview?.system_prompt ?? common.loadingPreview}</pre>
            </div>
            <div className="border-2 border-lawn-border bg-lawn-bg p-3">
              <div className="mb-2 text-[10px] font-black uppercase tracking-[0.12em] text-stone-500">{common.userPrompt}</div>
              <pre className="whitespace-pre-wrap break-words text-[11px] leading-5 text-lawn-border">{preview?.user_prompt ?? common.loadingPreview}</pre>
            </div>
          </div>
        </div>
      </SettingCard>
    </div>
  );
}
