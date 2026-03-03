import { Cpu, Activity, Zap, Info, AlertCircle } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Toggle, Select, NumberInput } from '../controls';
import type { SectionProps } from '../types';
import { isFakeSetting } from '../../../lib/settingsSchema';

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
  return (
    <div className="space-y-6">
      <SectionHeader
        title="Advanced Settings"
        icon={Cpu}
        description="Expert configuration and developer options"
      />

      <div className="border-2 border-theme-error/30 bg-theme-error/5 p-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-theme-error flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-bold text-theme-error">Warning</h4>
            <p className="text-xs text-stone-600 mt-1">
              These settings are intended for advanced users. Incorrect values may cause instability or poor performance.
            </p>
          </div>
        </div>
      </div>

      {saveError && (
        <div className="border-2 border-theme-error/30 bg-theme-error/5 p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-theme-error flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-bold text-theme-error">Error</h4>
              <p className="text-xs text-stone-600 mt-1">{saveError}</p>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-4">
        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-lawn-accent" />
            Debugging
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Debug Mode</span>
                <p className="text-xs text-stone-500">Enable verbose logging and diagnostics</p>
              </div>
              <Toggle
                checked={settings.advanced.debugMode}
                onChange={(v) => updateSetting('advanced', 'debugMode', v)}
              />
            </div>
            <SettingCard
              title="Log Level"
              description="Minimum severity for log messages"
              changed={isChanged('advanced', 'logLevel')}
              onReset={() => resetSetting('advanced', 'logLevel')}
            >
              <Select
                value={settings.advanced.logLevel}
                options={[
                  { value: 'DEBUG', label: 'Debug (Most Verbose)' },
                  { value: 'INFO', label: 'Info' },
                  { value: 'WARN', label: 'Warning' },
                  { value: 'ERROR', label: 'Error (Least Verbose)' },
                ]}
                onChange={(v) => updateSetting('advanced', 'logLevel', v)}
              />
            </SettingCard>
            <SettingCard
              title="Max Log Files"
              description="Number of log files to retain"
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
            Experimental Features
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">Enhanced STEM Detection</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">Coming Soon</span>
                </div>
                <p className="text-xs text-stone-500">Advanced formula and equation recognition</p>
              </div>
              <Toggle
                checked={settings.advanced.experimentalStem}
                onChange={(v) => updateSetting('advanced', 'experimentalStem', v)}
                disabled={isFakeSetting('advanced', 'experimentalStem')}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold block">GPU Acceleration</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-stone-300 text-stone-600 font-bold">Coming Soon</span>
                </div>
                <p className="text-xs text-stone-500">Use GPU for pre-processing when available</p>
              </div>
              <Toggle
                checked={settings.advanced.experimentalGpuAccel}
                onChange={(v) => updateSetting('advanced', 'experimentalGpuAccel', v)}
                disabled={isFakeSetting('advanced', 'experimentalGpuAccel')}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-bold block">Enable Metrics</span>
                <p className="text-xs text-stone-500">Collect and report performance metrics</p>
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
            Application Info
          </h4>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="border border-lawn-border bg-lawn-bg p-3">
              <span className="text-stone-500 text-xs block">Version</span>
              <span className="font-bold">1.0.0</span>
            </div>
            <div className="border border-lawn-border bg-lawn-bg p-3">
              <span className="text-stone-500 text-xs block">Platform</span>
              <span className="font-bold">{hardwareProfile?.platform || 'Unknown'}</span>
            </div>
            <div className="border border-lawn-border bg-lawn-bg p-3">
              <span className="text-stone-500 text-xs block">Build</span>
              <span className="font-bold">Release</span>
            </div>
            <div className="border border-lawn-border bg-lawn-bg p-3">
              <span className="text-stone-500 text-xs block">Electron</span>
              <span className="font-bold">Latest</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
