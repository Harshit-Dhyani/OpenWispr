import { Volume2, Filter, Layers } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Toggle, Slider, Select } from '../controls';
import type { SectionProps } from '../types';
import { SETTINGS_SECTION_TEXT, CAPTURE_MODE_LABELS, AUDIO_BACKEND_LABELS, SAMPLE_RATE_LABELS } from '../../../config/text';
import { RENDERER_STRINGS } from '../../../strings/en';

export function AudioSection({
  settings,
  audioDevices,
  isChanged,
  updateSetting,
  resetSetting,
}: SectionProps) {
  const text = SETTINGS_SECTION_TEXT.audio;
  const audioText = RENDERER_STRINGS.settings.audio;
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
                label: `${d.name}${d.is_loopback || d.supports_loopback ? audioText.recordingDeviceSuffix : ''}`,
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

        <SettingCard
          title={audioText.muteOpenWisprAudioDuringDictationTitle}
          description={audioText.muteOpenWisprAudioDuringDictationDescription}
          changed={isChanged('audio', 'mute_openwispr_audio_during_dictation')}
          onReset={() => resetSetting('audio', 'mute_openwispr_audio_during_dictation')}
        >
          <Toggle
            checked={Boolean(settings.audio.mute_openwispr_audio_during_dictation)}
            onChange={(value) => updateSetting('audio', 'mute_openwispr_audio_during_dictation', value)}
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
          <div className="space-y-3">
            <p className="text-xs text-stone-500">
              Advanced audio post-processing is hidden by default until it has verified runtime support.
            </p>
            <div className="flex flex-wrap gap-2">
              {[
                text.noise_filtering_title,
                text.echo_cancellation_title,
                text.auto_gain_control_title,
              ].map((label) => (
                <span
                  key={label}
                  className="border border-lawn-border bg-lawn-bg px-2 py-1 text-[10px] font-bold uppercase tracking-[0.08em] text-stone-500"
                >
                  {label} · {text.coming_soon}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
