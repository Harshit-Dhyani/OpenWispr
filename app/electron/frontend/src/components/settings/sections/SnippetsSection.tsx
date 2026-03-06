import { ScissorsSquareDashedBottom } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Toggle } from '../controls';
import type { SectionProps } from '../types';
import { RENDERER_STRINGS } from '../../../strings/en';

export function SnippetsSection({ settings, isChanged, updateSetting, resetSetting }: SectionProps) {
  const text = RENDERER_STRINGS.settings.snippets;

  return (
    <div className="space-y-6">
      <SectionHeader title={text.title} icon={ScissorsSquareDashedBottom} description={text.description} />

      <div className="grid gap-4">
        <SettingCard
          title={text.enableTitle}
          description={text.enableDescription}
          changed={isChanged('snippets', 'snippets_enabled')}
          onReset={() => resetSetting('snippets', 'snippets_enabled')}
        >
          <Toggle
            checked={settings.snippets.snippets_enabled}
            onChange={(value) => updateSetting('snippets', 'snippets_enabled', value)}
          />
        </SettingCard>

        <SettingCard
          title={text.quickInsertTitle}
          description={text.quickInsertDescription}
          changed={isChanged('snippets', 'snippets_quick_insert')}
          onReset={() => resetSetting('snippets', 'snippets_quick_insert')}
        >
          <Toggle
            checked={settings.snippets.snippets_quick_insert}
            onChange={(value) => updateSetting('snippets', 'snippets_quick_insert', value)}
          />
        </SettingCard>
      </div>
    </div>
  );
}
