import { Settings, Sliders } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Toggle, Slider, Select } from '../controls';
import type { SectionProps } from '../types';
import { isFakeSetting } from '../../../lib/settingsSchema';
import { getLanguageLabel } from '../../../lib/languages';

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
  const themeOptions = [
    { value: 'light', label: 'Light (Lawn)' },
    { value: 'dark', label: 'Dark (Night)' },
    { value: 'cyber', label: 'Cyberpunk' },
    { value: 'dracula', label: 'Dracula' },
  ];

  return (
    <div className="space-y-6">
      <SectionHeader
        title="General Settings"
        icon={Settings}
        description="Configure default session behavior and application preferences"
      />

      <div className="grid gap-4">
        <SettingCard
          title="Theme"
          description="Application color theme"
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
          title="Default Session Title"
          description="Default name for new transcription sessions"
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
          title="Default Language"
          description="Primary language for transcription (auto-detects if set to Auto)"
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
          title="Export Directory"
          description="Default location for exported transcripts and files"
          changed={isChanged('general', 'exportDirectory')}
          onReset={() => resetSetting('general', 'exportDirectory')}
        >
          <div className="flex gap-2">
            <input
              type="text"
              value={settings.general.exportDirectory}
              onChange={(e) => updateSetting('general', 'exportDirectory', e.target.value)}
              placeholder="Use default documents folder"
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
              Browse
            </button>
          </div>
        </SettingCard>

        <SettingCard
          title="Auto-save Interval"
          description="How often to automatically save session progress (in seconds)"
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
            Application Behavior
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">Show Notifications</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">Coming Soon</span>
                </div>
                <p className="text-xs text-stone-500">Display desktop notifications for events</p>
              </div>
              <Toggle
                checked={settings.general.showNotifications}
                onChange={(v) => updateSetting('general', 'showNotifications', v)}
                disabled={isFakeSetting('general', 'showNotifications')}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">Minimize to Tray</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">Coming Soon</span>
                </div>
                <p className="text-xs text-stone-500">Keep running in system tray when closed</p>
              </div>
              <Toggle
                checked={settings.general.minimizeToTray}
                onChange={(v) => updateSetting('general', 'minimizeToTray', v)}
                disabled={isFakeSetting('general', 'minimizeToTray')}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">Start with System</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">Coming Soon</span>
                </div>
                <p className="text-xs text-stone-500">Launch automatically on Windows startup</p>
              </div>
              <Toggle
                checked={settings.general.startupWithSystem}
                onChange={(v) => updateSetting('general', 'startupWithSystem', v)}
                disabled={isFakeSetting('general', 'startupWithSystem')}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
