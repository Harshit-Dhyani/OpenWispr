import { History } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Select, Slider, Toggle } from '../controls';
import type { SectionProps } from '../types';
import { RENDERER_STRINGS } from '../../../strings/en';

export function HistorySection({ settings, isChanged, updateSetting, resetSetting }: SectionProps) {
  const text = RENDERER_STRINGS.settings.history;

  return (
    <div className="space-y-6">
      <SectionHeader title={text.title} icon={History} description={text.description} />

      <div className="grid gap-4">
        <SettingCard
          title={text.retentionDaysTitle}
          description={text.retentionDaysDescription}
          changed={isChanged('history', 'retention_days')}
          onReset={() => resetSetting('history', 'retention_days')}
        >
          <Slider
            value={settings.history.retention_days}
            min={1}
            max={3650}
            step={1}
            onChange={(value) => updateSetting('history', 'retention_days', value)}
            suffix="d"
          />
        </SettingCard>

        <SettingCard
          title={text.defaultRangeTitle}
          description={text.defaultRangeDescription}
          changed={isChanged('history', 'default_analytics_range_days')}
          onReset={() => resetSetting('history', 'default_analytics_range_days')}
        >
          <Select
            value={String(settings.history.default_analytics_range_days)}
            options={[...text.defaultRangeOptions]}
            onChange={(value) =>
              updateSetting(
                'history',
                'default_analytics_range_days',
                value === 'all' ? 'all' : Number.parseInt(value, 10),
              )
            }
          />
        </SettingCard>

        <SettingCard
          title={text.persistAudioTitle}
          description={text.persistAudioDescription}
          changed={isChanged('history', 'persist_audio')}
          onReset={() => resetSetting('history', 'persist_audio')}
        >
          <Toggle
            checked={settings.history.persist_audio}
            onChange={(value) => updateSetting('history', 'persist_audio', value)}
          />
        </SettingCard>

        <SettingCard
          title={text.allowRetryTitle}
          description={text.allowRetryDescription}
          changed={isChanged('history', 'allow_retry')}
          onReset={() => resetSetting('history', 'allow_retry')}
        >
          <Toggle
            checked={settings.history.allow_retry}
            onChange={(value) => updateSetting('history', 'allow_retry', value)}
          />
        </SettingCard>
      </div>
    </div>
  );
}
