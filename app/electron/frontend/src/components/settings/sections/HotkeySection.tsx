import { Keyboard, Sliders } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Toggle, Select } from '../controls';
import { HotkeyRecorder } from '../HotkeyRecorder';
import type { SectionProps } from '../types';
import type { HotkeySettings } from '../../../config/settingsSchema';
import { RENDERER_STRINGS } from '../../../strings/en';

export function HotkeySection({
  settings,
  audioDevices,
  isChanged,
  updateSetting,
  resetSetting,
}: SectionProps) {
  const text = RENDERER_STRINGS.settings.hotkey;
  const hotkeyDeviceOptions = [
    {
      value: 'default',
      label:
        settings.hotkey.capture_source === 'system'
          ? text.autoDetectSystemAudio
          : text.autoDetectMicrophone,
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
        title={text.title}
        icon={Keyboard}
        description={text.description}
      />

      <div className="grid gap-4">
        <div className="flex items-center justify-between p-4 border-2 border-lawn-border bg-lawn-panel">
          <div className="min-w-0 flex-1">
            <span className="text-sm font-bold block">{text.enableTitle}</span>
            <p className="text-xs text-stone-500">{text.enableDescription}</p>
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
                title={text.microphoneHotkeyTitle}
                description={text.microphoneHotkeyDescription}
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
                title={text.systemHotkeyTitle}
                description={text.systemHotkeyDescription}
                changed={isChanged('hotkey', 'system_key_combination')}
                onReset={() => resetSetting('hotkey', 'system_key_combination')}
              >
                <HotkeyRecorder
                  value={settings.hotkey.system_key_combination}
                  onChange={(v) => updateSetting('hotkey', 'system_key_combination', v)}
                />
              </SettingCard>
            </div>

            <SettingCard
              title={text.captureSourceTitle}
              description={text.captureSourceDescription}
              changed={isChanged('hotkey', 'capture_source')}
              onReset={() => resetSetting('hotkey', 'capture_source')}
            >
              <Select
                value={settings.hotkey.capture_source}
                options={[
                  ...text.captureSourceOptions,
                ]}
                onChange={(v) => updateSetting('hotkey', 'capture_source', v)}
              />
            </SettingCard>

            <SettingCard
              title={settings.hotkey.capture_source === 'system' ? text.systemDeviceTitle : text.microphoneDeviceTitle}
              description={
                settings.hotkey.capture_source === 'system'
                  ? text.systemDeviceDescription
                  : text.microphoneDeviceDescription
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
              title={text.floatingPositionTitle}
              description={text.floatingPositionDescription}
              changed={isChanged('hotkey', 'floating_window_position')}
              onReset={() => resetSetting('hotkey', 'floating_window_position')}
            >
              <Select
                value={settings.hotkey.floating_window_position}
                options={[
                  ...text.floatingPositionOptions,
                ]}
                onChange={(v) => updateSetting('hotkey', 'floating_window_position', v as HotkeySettings['floating_window_position'])}
              />
            </SettingCard>

            <div className="border-2 border-lawn-border bg-lawn-panel p-4">
              <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
                <Sliders className="w-4 h-4 text-lawn-accent" />
                {text.behaviorTitle}
              </h4>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">{text.behavior.holdMode.title}</span>
                    <p className="text-xs text-stone-500">{text.behavior.holdMode.description}</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.hold_mode}
                    onChange={(v) => updateSetting('hotkey', 'hold_mode', v)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">{text.behavior.autoInject.title}</span>
                    <p className="text-xs text-stone-500">{text.behavior.autoInject.description}</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.auto_inject}
                    onChange={(v) => updateSetting('hotkey', 'auto_inject', v)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">{text.behavior.showFloatingWindow.title}</span>
                    <p className="text-xs text-stone-500">{text.behavior.showFloatingWindow.description}</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.show_floating_window}
                    onChange={(v) => updateSetting('hotkey', 'show_floating_window', v)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">{text.behavior.saveDebugWav.title}</span>
                    <p className="text-xs text-stone-500">{text.behavior.saveDebugWav.description}</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.save_debug_wav}
                    onChange={(v) => updateSetting('hotkey', 'save_debug_wav', v)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-bold block">{text.behavior.copyToClipboard.title}</span>
                    <p className="text-xs text-stone-500">{text.behavior.copyToClipboard.description}</p>
                  </div>
                  <Toggle
                    checked={settings.hotkey.copy_to_clipboard}
                    onChange={(v) => updateSetting('hotkey', 'copy_to_clipboard', v)}
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
