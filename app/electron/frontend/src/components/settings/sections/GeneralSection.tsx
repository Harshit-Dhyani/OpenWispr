import { Settings } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Slider, Select, Toggle } from '../controls';
import type { SectionProps } from '../types';
import { getLanguageLabel } from '../../../lib/languages';
import { RENDERER_STRINGS } from '../../../strings/en';
import { isFakeSetting } from '../../../config/settingsSchema';

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
                const folder = await window.openwisprDesktop?.chooseDirectory?.();
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

        {isFakeSetting('general', 'showNotifications') && (
          <SettingCard
            title={text.showNotificationsTitle}
            description={text.showNotificationsDescription}
            badge="Coming Soon"
          >
            <Toggle
              checked={Boolean(settings.general.showNotifications)}
              onChange={() => {}}
              disabled
            />
          </SettingCard>
        )}

        {isFakeSetting('general', 'minimizeToTray') && (
          <SettingCard
            title={text.minimizeToTrayTitle}
            description={text.minimizeToTrayDescription}
            badge="Coming Soon"
          >
            <Toggle
              checked={Boolean(settings.general.minimizeToTray)}
              onChange={() => {}}
              disabled
            />
          </SettingCard>
        )}

        {isFakeSetting('general', 'startupWithSystem') && (
          <SettingCard
            title={text.startupWithSystemTitle}
            description={text.startupWithSystemDescription}
            badge="Coming Soon"
          >
            <Toggle
              checked={Boolean(settings.general.startupWithSystem)}
              onChange={() => {}}
              disabled
            />
          </SettingCard>
        )}
      </div>
    </div>
  );
}
