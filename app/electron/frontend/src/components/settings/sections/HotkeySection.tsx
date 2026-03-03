import { Keyboard, Sliders } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Toggle, Select } from '../controls';
import { HotkeyRecorder } from '../HotkeyRecorder';
import type { SectionProps } from '../types';
import type { HotkeySettings } from '../../../lib/settingsSchema';
import { getLanguageLabel } from '../../../lib/languages';

export function HotkeySection({
  settings,
  audioDevices,
  availableLanguages,
  isChanged,
  updateSetting,
  resetSetting,
}: SectionProps) {
  return (
    <div className="space-y-6">
      <SectionHeader
        title="Hotkey Configuration"
        icon={Keyboard}
        description="Configure global keyboard shortcuts for quick access"
      />

      <div className="grid gap-4">
        <div className="flex items-center justify-between p-4 border-2 border-lawn-border bg-lawn-panel">
          <div className="min-w-0 flex-1">
            <span className="text-sm font-bold block">Enable Global Hotkey</span>
            <p className="text-xs text-stone-500">Activate transcription from anywhere</p>
          </div>
          <Toggle
            checked={settings.hotkey.enabled}
            onChange={(v) => updateSetting('hotkey', 'enabled', v)}
          />
        </div>

        {settings.hotkey.enabled && (
          <>
            <SettingCard
              title="Key Combination"
              description="Press the button and enter your desired hotkey"
              changed={isChanged('hotkey', 'key_combination')}
              onReset={() => resetSetting('hotkey', 'key_combination')}
            >
              <HotkeyRecorder
                value={settings.hotkey.key_combination}
                onChange={(v) => updateSetting('hotkey', 'key_combination', v)}
              />
            </SettingCard>

            <div className="grid gap-4 md:grid-cols-2">
              <SettingCard
                title="Dictation Language"
                description="Default language for microphone hotkey dictation"
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
                title="Dictation Finish Action"
                description="Default action when a toggle hotkey session stops"
                changed={isChanged('hotkey', 'finish_mode_default')}
                onReset={() => resetSetting('hotkey', 'finish_mode_default')}
              >
                <Select
                  value={settings.hotkey.finish_mode_default}
                  options={[
                    { value: 'finish', label: 'Finish Only' },
                    { value: 'finish_and_paste', label: 'Finish & Paste' },
                  ]}
                  onChange={(v) => updateSetting('hotkey', 'finish_mode_default', v)}
                />
              </SettingCard>
            </div>

            <SettingCard
              title="Dictation Microphone"
              description="Microphone source used for quick dictation"
              changed={isChanged('hotkey', 'device_id')}
              onReset={() => resetSetting('hotkey', 'device_id')}
            >
              <Select
                value={settings.hotkey.device_id}
                options={[
                  { value: 'default', label: 'Auto-detect microphone' },
                  ...audioDevices
                    .filter((device) => device.is_input && !(device.is_loopback || device.supports_loopback))
                    .map((device) => ({
                      value: device.id,
                      label: device.name,
                    })),
                ]}
                onChange={(v) => updateSetting('hotkey', 'device_id', v)}
              />
            </SettingCard>

            <SettingCard
              title="Floating Window Position"
              description="Where to show the transcription overlay"
              changed={isChanged('hotkey', 'floating_window_position')}
              onReset={() => resetSetting('hotkey', 'floating_window_position')}
            >
              <Select
                value={settings.hotkey.floating_window_position}
                options={[
                  { value: 'top-left', label: 'Top Left' },
                  { value: 'top-right', label: 'Top Right' },
                  { value: 'bottom-left', label: 'Bottom Left' },
                  { value: 'bottom-right', label: 'Bottom Right' },
                  { value: 'center', label: 'Center' },
                ]}
                onChange={(v) => updateSetting('hotkey', 'floating_window_position', v as HotkeySettings['floating_window_position'])}
              />
            </SettingCard>

            <div className="border-2 border-lawn-border bg-lawn-panel p-4">
              <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
                <Sliders className="w-4 h-4 text-lawn-accent" />
                Hotkey Behavior
              </h4>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">Hold Mode</span>
                    <p className="text-xs text-stone-500">Record while holding the hotkey</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.hold_mode}
                    onChange={(v) => updateSetting('hotkey', 'hold_mode', v)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">Auto-inject Text</span>
                    <p className="text-xs text-stone-500">Type transcription into active window</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.auto_inject}
                    onChange={(v) => updateSetting('hotkey', 'auto_inject', v)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">Show Floating Window</span>
                    <p className="text-xs text-stone-500">Display overlay during transcription</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.show_floating_window}
                    onChange={(v) => updateSetting('hotkey', 'show_floating_window', v)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">Copy to Clipboard</span>
                    <p className="text-xs text-stone-500">Automatically copy transcription</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.copy_to_clipboard}
                    onChange={(v) => updateSetting('hotkey', 'copy_to_clipboard', v)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">Record on Start</span>
                    <p className="text-xs text-stone-500">Automatically start recording when hotkey session begins</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.record_on_start}
                    onChange={(v) => updateSetting('hotkey', 'record_on_start', v)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">Stop on Release</span>
                    <p className="text-xs text-stone-500">Stop recording when hotkey is released (hold mode)</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.stop_on_release}
                    onChange={(v) => updateSetting('hotkey', 'stop_on_release', v)}
                  />
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
