/**
 * AdvancedSection - Advanced and experimental settings
 * 
 * Manages CPU threads, logging levels, debugging options, and experimental features.
 * Props: SectionProps with saveError for displaying save failures.
 */
import { Cpu, Activity, Zap, Info, AlertCircle } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Toggle, Select, NumberInput } from '../controls';
import type { SectionProps } from '../types';
import { AppConstants } from '../../../config/generated/constants';
import { RENDERER_STRINGS } from '../../../strings/en';

interface AdvancedSectionProps extends SectionProps {
  saveError: string | null;
}

export function AdvancedSection({
  settings,
  hardwareProfile,
  isChanged,
  updateSetting,
  resetSetting,
  saveError,
}: AdvancedSectionProps) {
  const text = RENDERER_STRINGS.settings.advanced;
  return (
    <div className="space-y-6">
      <SectionHeader
        title={text.title}
        icon={Cpu}
        description={text.description}
      />

      <div className="border-2 border-theme-error/30 bg-theme-error/5 p-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-theme-error flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-bold text-theme-error">{text.warningTitle}</h4>
            <p className="text-xs text-stone-600 mt-1">
              {text.warningDescription}
            </p>
          </div>
        </div>
      </div>

      {saveError && (
        <div className="border-2 border-theme-error/30 bg-theme-error/5 p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-theme-error flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-bold text-theme-error">{text.errorTitle}</h4>
              <p className="text-xs text-stone-600 mt-1">{saveError}</p>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-4">
        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-lawn-accent" />
            {text.debuggingTitle}
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">{text.debugModeTitle}</span>
                <p className="text-xs text-stone-500">{text.debugModeDescription}</p>
              </div>
              <Toggle
                checked={settings.advanced.debugMode}
                onChange={(v) => updateSetting('advanced', 'debugMode', v)}
              />
            </div>
            <SettingCard
              title={text.logLevelTitle}
              description={text.logLevelDescription}
              changed={isChanged('advanced', 'logLevel')}
              onReset={() => resetSetting('advanced', 'logLevel')}
            >
              <Select
                value={settings.advanced.logLevel}
                options={[
                  ...text.logLevelOptions,
                ]}
                onChange={(v) => updateSetting('advanced', 'logLevel', v)}
              />
            </SettingCard>
            <SettingCard
              title={text.maxLogFilesTitle}
              description={text.maxLogFilesDescription}
              changed={isChanged('advanced', 'maxLogFiles')}
              onReset={() => resetSetting('advanced', 'maxLogFiles')}
            >
              <NumberInput
                value={settings.advanced.maxLogFiles}
                min={1}
                max={100}
                onChange={(v) => updateSetting('advanced', 'maxLogFiles', v)}
              />
            </SettingCard>
          </div>
        </div>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Zap className="w-4 h-4 text-lawn-accent" />
            {text.experimentalTitle}
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">{text.metricsTitle}</span>
                <p className="text-xs text-stone-500">{text.metricsDescription}</p>
              </div>
              <Toggle
                checked={settings.advanced.enableMetrics}
                onChange={(v) => updateSetting('advanced', 'enableMetrics', v)}
              />
            </div>
          </div>
        </div>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Info className="w-4 h-4 text-lawn-accent" />
            {text.appInfoTitle}
          </h4>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="border border-lawn-border bg-lawn-bg p-3">
              <span className="text-stone-500 text-xs block">{text.appInfoLabels.version}</span>
              <span className="font-bold">1.0.0</span>
            </div>
            <div className="border border-lawn-border bg-lawn-bg p-3">
              <span className="text-stone-500 text-xs block">{text.appInfoLabels.platform}</span>
              <span className="font-bold">{hardwareProfile?.platform || RENDERER_STRINGS.settings.common.unknown}</span>
            </div>
            <div className="border border-lawn-border bg-lawn-bg p-3">
              <span className="text-stone-500 text-xs block">{text.appInfoLabels.build}</span>
              <span className="font-bold">{RENDERER_STRINGS.settings.common.release}</span>
            </div>
            <div className="border border-lawn-border bg-lawn-bg p-3">
              <span className="text-stone-500 text-xs block">{AppConstants.APP_NAME}</span>
              <span className="font-bold">{RENDERER_STRINGS.settings.common.latest}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
