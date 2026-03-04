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
  const hotkeyDeviceOptions = [
    {
      value: 'default',
      label:
        settings.hotkey.capture_source === 'system'
          ? 'Auto-detect system audio'
          : 'Auto-detect microphone',
    },
    ...audioDevices
      .filter((device) =>
        settings.hotkey.capture_source === 'system'
          ? Boolean(device.is_loopback || device.supports_loopback)
          : Boolean(device.is_input && !(device.is_loopback || device.supports_loopback)),
      )
      .map((device) => ({
        value: device.id,
        label: device.name,
      })),
  ];

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
            <div className="grid gap-4 md:grid-cols-2">
              <SettingCard
                title="Microphone Hotkey"
                description="Global shortcut for microphone dictation"
                changed={
                  isChanged('hotkey', 'microphone_key_combination') ||
                  isChanged('hotkey', 'key_combination')
                }
                onReset={() => {
                  resetSetting('hotkey', 'microphone_key_combination');
                  resetSetting('hotkey', 'key_combination');
                }}
              >
                <HotkeyRecorder
                  value={settings.hotkey.microphone_key_combination}
                  onChange={(v) => {
                    updateSetting('hotkey', 'microphone_key_combination', v);
                    updateSetting('hotkey', 'key_combination', v);
                  }}
                />
              </SettingCard>

              <SettingCard
                title="System Audio Hotkey"
                description="Global shortcut for loopback/system audio transcription"
                changed={isChanged('hotkey', 'system_key_combination')}
                onReset={() => resetSetting('hotkey', 'system_key_combination')}
              >
                <HotkeyRecorder
                  value={settings.hotkey.system_key_combination}
                  onChange={(v) => updateSetting('hotkey', 'system_key_combination', v)}
                />
              </SettingCard>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <SettingCard
                title="Hotkey Capture Source"
                description="Choose whether the hotkey records your microphone or system audio"
                changed={isChanged('hotkey', 'capture_source')}
                onReset={() => resetSetting('hotkey', 'capture_source')}
              >
                <Select
                  value={settings.hotkey.capture_source}
                  options={[
                    { value: 'microphone', label: 'Microphone' },
                    { value: 'system', label: 'System Audio' },
                  ]}
                  onChange={(v) => updateSetting('hotkey', 'capture_source', v)}
                />
              </SettingCard>

              <SettingCard
                title="Dictation Language"
                description="Default language for hotkey transcription"
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
              title={settings.hotkey.capture_source === 'system' ? 'System Audio Device' : 'Dictation Microphone'}
              description={
                settings.hotkey.capture_source === 'system'
                  ? 'Loopback device used for quick system-audio transcription'
                  : 'Microphone source used for quick dictation'
              }
              changed={isChanged('hotkey', 'device_id')}
              onReset={() => resetSetting('hotkey', 'device_id')}
            >
              <Select
                value={settings.hotkey.device_id}
                options={hotkeyDeviceOptions}
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
