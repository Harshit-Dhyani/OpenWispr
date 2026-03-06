import { Paintbrush } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Select, Toggle } from '../controls';
import type { SectionProps } from '../types';
import { RENDERER_STRINGS } from '../../../strings/en';

export function StyleSection({ settings, isChanged, updateSetting, resetSetting }: SectionProps) {
  const text = RENDERER_STRINGS.settings.style;

  return (
    <div className="space-y-6">
      <SectionHeader title={text.title} icon={Paintbrush} description={text.description} />

      <div className="grid gap-4">
        <SettingCard
          title={text.enableTitle}
          description={text.enableDescription}
          changed={isChanged('style', 'style_apply_enabled')}
          onReset={() => resetSetting('style', 'style_apply_enabled')}
        >
          <Toggle
            checked={settings.style.style_apply_enabled}
            onChange={(value) => updateSetting('style', 'style_apply_enabled', value)}
          />
        </SettingCard>

        <SettingCard
          title={text.defaultProfileTitle}
          description={text.defaultProfileDescription}
          changed={isChanged('style', 'style_default_profile')}
          onReset={() => resetSetting('style', 'style_default_profile')}
        >
          <Select
            value={settings.style.style_default_profile}
            options={[...text.defaultProfileOptions]}
            onChange={(value) => updateSetting('style', 'style_default_profile', value)}
          />
        </SettingCard>
      </div>
    </div>
  );
}
