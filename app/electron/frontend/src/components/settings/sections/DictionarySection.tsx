import { BookText } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Toggle } from '../controls';
import type { SectionProps } from '../types';
import { RENDERER_STRINGS } from '../../../strings/en';

export function DictionarySection({ settings, isChanged, updateSetting, resetSetting }: SectionProps) {
  const text = RENDERER_STRINGS.settings.dictionary;

  return (
    <div className="space-y-6">
      <SectionHeader title={text.title} icon={BookText} description={text.description} />

      <div className="grid gap-4">
        <SettingCard
          title={text.enableTitle}
          description={text.enableDescription}
          changed={isChanged('dictionary', 'dictionary_enabled')}
          onReset={() => resetSetting('dictionary', 'dictionary_enabled')}
        >
          <Toggle
            checked={settings.dictionary.dictionary_enabled}
            onChange={(value) => updateSetting('dictionary', 'dictionary_enabled', value)}
          />
        </SettingCard>
      </div>
    </div>
  );
}
