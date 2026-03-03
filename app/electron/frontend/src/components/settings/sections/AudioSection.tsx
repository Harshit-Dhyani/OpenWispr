import { Volume2, Filter, Layers } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Toggle, Slider, Select } from '../controls';
import type { SectionProps } from '../types';
import { isFakeSetting } from '../../../lib/settingsSchema';
import { SETTINGS_SECTION_TEXT, CAPTURE_MODE_LABELS, AUDIO_BACKEND_LABELS, SAMPLE_RATE_LABELS } from '../../../config/text';

export function AudioSection({
  settings,
  audioDevices,
  isChanged,
  updateSetting,
  resetSetting,
}: SectionProps) {
  const text = SETTINGS_SECTION_TEXT.audio;
  const defaultCaptureSource = settings.audio.default_capture_source ?? settings.audio.captureMode;
  const filteredDevices = audioDevices.filter((device) =>
    defaultCaptureSource === 'system'
      ? Boolean(device.is_loopback || device.supports_loopback)
      : !Boolean(device.is_loopback || device.supports_loopback),
  );

  return (
    <div className="space-y-6">
      <SectionHeader
        title={text.title}
        icon={Volume2}
        description={text.description}
      />

      <div className="grid gap-4">
        <SettingCard
          title={text.default_capture_source_title}
          description={text.default_capture_source_description}
          changed={isChanged('audio', 'default_capture_source') || isChanged('audio', 'captureMode')}
          onReset={() => {
            resetSetting('audio', 'default_capture_source');
            resetSetting('audio', 'captureMode');
          }}
        >
          <Select
            value={defaultCaptureSource}
            options={[
              { value: 'system', label: CAPTURE_MODE_LABELS.system },
              { value: 'microphone', label: CAPTURE_MODE_LABELS.microphone },
            ]}
            onChange={(v) => {
              const captureSource = v as 'system' | 'microphone';
              updateSetting('audio', 'default_capture_source', captureSource);
              updateSetting('audio', 'captureMode', captureSource);
            }}
          />
        </SettingCard>

        <SettingCard
          title={text.default_audio_device_title}
          description={text.default_audio_device_description}
          changed={isChanged('audio', 'defaultDeviceId')}
          onReset={() => resetSetting('audio', 'defaultDeviceId')}
        >
          <Select
            value={settings.audio.defaultDeviceId}
            options={filteredDevices.map((d) => ({
                value: d.id,
                label: `${d.name}${d.is_loopback || d.supports_loopback ? ' [rec]' : ''}`,
              }))}
            onChange={(v) => updateSetting('audio', 'defaultDeviceId', v)}
          />
        </SettingCard>

        <SettingCard
          title={text.audio_backend_title}
          description={text.audio_backend_description}
          changed={isChanged('audio', 'audio_backend')}
          onReset={() => resetSetting('audio', 'audio_backend')}
        >
          <Select
            value={settings.audio.audio_backend}
            options={[
              { value: 'auto', label: AUDIO_BACKEND_LABELS.auto },
              { value: 'pyaudio', label: AUDIO_BACKEND_LABELS.pyaudio },
              { value: 'soundcard', label: AUDIO_BACKEND_LABELS.soundcard },
            ]}
            onChange={(v) => updateSetting('audio', 'audio_backend', v as 'auto' | 'pyaudio' | 'soundcard')}
          />
        </SettingCard>

        <SettingCard
          title={text.sample_rate_title}
          description={text.sample_rate_description}
          changed={isChanged('audio', 'sampleRate')}
          onReset={() => resetSetting('audio', 'sampleRate')}
        >
          <Select
            value={String(settings.audio.sampleRate)}
            options={[
              { value: '8000', label: SAMPLE_RATE_LABELS['8000'] },
              { value: '16000', label: SAMPLE_RATE_LABELS['16000'] },
              { value: '22050', label: SAMPLE_RATE_LABELS['22050'] },
              { value: '44100', label: SAMPLE_RATE_LABELS['44100'] },
              { value: '48000', label: SAMPLE_RATE_LABELS['48000'] },
            ]}
            onChange={(v) => updateSetting('audio', 'sampleRate', parseInt(v))}
          />
        </SettingCard>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Filter className="w-4 h-4 text-lawn-accent" />
            {text.vad_group_title}
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">{text.vad_toggle_title}</span>
                <p className="text-xs text-stone-500">{text.vad_toggle_description}</p>
              </div>
              <Toggle
                checked={settings.transcription.vad_enabled}
                onChange={(v) => updateSetting('transcription', 'vad_enabled', v)}
              />
            </div>
            {settings.transcription.vad_enabled && (
              <SettingCard
                title={text.vad_threshold_title}
                description={text.vad_threshold_description}
                changed={isChanged('transcription', 'vad_threshold_db')}
                onReset={() => resetSetting('transcription', 'vad_threshold_db')}
              >
                <Slider
                  value={settings.transcription.vad_threshold_db}
                  min={-60}
                  max={-20}
                  step={1}
                  onChange={(v) => updateSetting('transcription', 'vad_threshold_db', v)}
                  suffix="dB"
                />
              </SettingCard>
            )}
          </div>
        </div>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Layers className="w-4 h-4 text-lawn-accent" />
            {text.processing_group_title}
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">{text.noise_filtering_title}</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">{text.coming_soon}</span>
                </div>
                <p className="text-xs text-stone-500">{text.noise_filtering_description}</p>
              </div>
              <Toggle
                checked={settings.audio.noiseFiltering}
                onChange={(v) => updateSetting('audio', 'noiseFiltering', v)}
                disabled={isFakeSetting('audio', 'noiseFiltering')}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">{text.echo_cancellation_title}</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">{text.coming_soon}</span>
                </div>
                <p className="text-xs text-stone-500">{text.echo_cancellation_description}</p>
              </div>
              <Toggle
                checked={settings.audio.echoCancellation}
                onChange={(v) => updateSetting('audio', 'echoCancellation', v)}
                disabled={isFakeSetting('audio', 'echoCancellation')}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">{text.auto_gain_control_title}</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">{text.coming_soon}</span>
                </div>
                <p className="text-xs text-stone-500">{text.auto_gain_control_description}</p>
              </div>
              <Toggle
                checked={settings.audio.autoGainControl}
                onChange={(v) => updateSetting('audio', 'autoGainControl', v)}
                disabled={isFakeSetting('audio', 'autoGainControl')}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
