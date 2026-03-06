import { Settings, Sliders } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Slider, Select } from '../controls';
import type { SectionProps } from '../types';
import { getLanguageLabel } from '../../../lib/languages';
import { RENDERER_STRINGS } from '../../../strings/en';

interface GeneralSectionProps extends SectionProps {
  availableLanguages: string[];
}

export function GeneralSection({
  settings,
  isChanged,
  updateSetting,
  resetSetting,
  availableLanguages,
}: GeneralSectionProps) {
  const text = RENDERER_STRINGS.settings.general;
  const common = RENDERER_STRINGS.settings.common;
  const themeOptions = [...text.themeOptions];

  return (
    <div className="space-y-6">
      <SectionHeader
        title={text.title}
        icon={Settings}
        description={text.description}
      />

      <div className="grid gap-4">
        <SettingCard
          title={text.themeTitle}
          description={text.themeDescription}
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
          title={text.defaultSessionTitle}
          description={text.defaultSessionDescription}
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
          title={text.defaultLanguageTitle}
          description={text.defaultLanguageDescription}
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
          title={text.exportDirectoryTitle}
          description={text.exportDirectoryDescription}
          changed={isChanged('general', 'exportDirectory')}
          onReset={() => resetSetting('general', 'exportDirectory')}
        >
          <div className="flex gap-2">
            <input
              type="text"
              value={settings.general.exportDirectory}
              onChange={(e) => updateSetting('general', 'exportDirectory', e.target.value)}
              placeholder={text.exportDirectoryPlaceholder}
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
              {common.browse}
            </button>
          </div>
        </SettingCard>

        <SettingCard
          title={text.autoSaveTitle}
          description={text.autoSaveDescription}
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
            {text.behaviorTitle}
          </h4>
          <div className="space-y-3">
            <p className="text-xs text-stone-500">
              Runtime-only behavior controls are hidden until they are fully implemented end-to-end.
            </p>
            <div className="flex flex-wrap gap-2">
              {[
                text.showNotificationsTitle,
                text.minimizeToTrayTitle,
                text.startupWithSystemTitle,
              ].map((label) => (
                <span
                  key={label}
                  className="border border-lawn-border bg-lawn-bg px-2 py-1 text-[10px] font-bold uppercase tracking-[0.08em] text-stone-500"
                >
                  {label} · {common.comingSoon}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
