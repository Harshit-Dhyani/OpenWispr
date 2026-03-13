import type { Device, ModelCatalogEntry } from '../types/api';

type Snapshot = {
  available_languages: string[];
  available_live_modes: string[];
  available_execution_modes: string[];
};

type ModelManager = {
  catalog: ModelCatalogEntry[];
};

type FormType = {
  sessionTitle: string;
  captureMode: 'system' | 'microphone';
  deviceId: string;
  modelName: string;
  languageMode: string;
  liveMode: string;
  executionMode: string;
  exportRoot: string;
};

type QuickSettingsContentProps = {
  mode: 'dictation' | 'sessions';
  dictationCaptureSource: 'system' | 'microphone';
  dictationDevices: Device[];
  dictationLanguage: string;
  dictationModelId: string;
  settingsHotkey: {
    device_id: string;
    finish_mode_default: string;
  };
  settingsTranscription: {
    refinement_mode: string;
  };
  snapshot: Snapshot;
  form: FormType;
  sessionDevices: Device[];
  sessionModelId: string;
  modelManager: ModelManager;
  onDictationSettingChange: (field: 'capture_source' | 'device_id' | 'language' | 'finish_mode_default' | 'refinement_mode' | 'model_id', value: string) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onFieldChange: (key: any, value: any) => void;
  onSessionModelChange: (modelId: string) => void;
  onChooseDirectory: () => void;
  onAttachPdf: () => void;
};

export function QuickSettingsContent({
  mode,
  dictationCaptureSource,
  dictationDevices,
  dictationLanguage,
  dictationModelId,
  settingsHotkey,
  settingsTranscription,
  snapshot,
  form,
  sessionDevices,
  sessionModelId,
  modelManager,
  onDictationSettingChange,
  onFieldChange,
  onSessionModelChange,
  onChooseDirectory,
  onAttachPdf,
}: QuickSettingsContentProps) {
  if (mode === 'dictation') {
    return (
      <div className="space-y-4">
        <label className="block space-y-2">
          <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Source</span>
          <select
            value={dictationCaptureSource}
            onChange={(event) => void onDictationSettingChange('capture_source', event.target.value)}
            className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
          >
            <option value="microphone">Microphone</option>
            <option value="system">System Audio</option>
          </select>
        </label>
        <label className="block space-y-2">
          <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Device</span>
          <select
            value={settingsHotkey.device_id || dictationDevices[0]?.id || ''}
            onChange={(event) => void onDictationSettingChange('device_id', event.target.value)}
            className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
          >
            {dictationDevices.map((device) => (
              <option key={device.id} value={device.id}>
                {device.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block space-y-2">
          <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Language</span>
          <select
            value={dictationLanguage}
            onChange={(event) => void onDictationSettingChange('language', event.target.value)}
            className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
          >
            {snapshot.available_languages.map((language) => (
              <option key={language} value={language}>
                {language}
              </option>
            ))}
          </select>
        </label>
        <label className="block space-y-2">
          <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Dictation model</span>
          <select
            value={dictationModelId}
            onChange={(event) => void onDictationSettingChange('model_id', event.target.value)}
            className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
          >
            {modelManager.catalog
              .filter((entry) => entry.category === 'asr')
              .map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.display_name}
                </option>
              ))}
          </select>
        </label>
        <label className="block space-y-2">
          <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Finish action</span>
          <select
            value={settingsHotkey.finish_mode_default}
            onChange={(event) => void onDictationSettingChange('finish_mode_default', event.target.value)}
            className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
          >
            <option value="finish_and_paste">Finish &amp; Paste</option>
            <option value="finish">Finish only</option>
            <option value="cancel">Cancel</option>
          </select>
        </label>
        <label className="block space-y-2">
          <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Refiner mode</span>
          <select
            value={settingsTranscription.refinement_mode}
            onChange={(event) => void onDictationSettingChange('refinement_mode', event.target.value)}
            className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
          >
            <option value="off">Off</option>
            <option value="strict">Strict</option>
            <option value="polished">Polished</option>
          </select>
        </label>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <label className="block space-y-2">
        <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Session title</span>
        <input
          value={form.sessionTitle}
          onChange={(event) => onFieldChange('sessionTitle', event.target.value)}
          className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
        />
      </label>
      <label className="block space-y-2">
        <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Source</span>
        <select
          value={form.captureMode}
          onChange={(event) => onFieldChange('captureMode', event.target.value as typeof form.captureMode)}
          className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
        >
          <option value="system">System Audio</option>
          <option value="microphone">Microphone</option>
        </select>
      </label>
      <label className="block space-y-2">
        <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Device</span>
        <select
          value={form.deviceId}
          onChange={(event) => onFieldChange('deviceId', event.target.value)}
          className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
        >
          {sessionDevices.map((device) => (
            <option key={device.id} value={device.id}>
              {device.name}
            </option>
          ))}
        </select>
      </label>
      <label className="block space-y-2">
        <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">ASR model</span>
        <select
          value={sessionModelId}
          onChange={(event) => void onSessionModelChange(event.target.value)}
          className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
        >
          {modelManager.catalog
            .filter((entry) => entry.category === 'asr')
            .map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.display_name}
              </option>
            ))}
        </select>
      </label>
      <label className="block space-y-2">
        <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Quality mode</span>
        <select
          value={form.liveMode}
          onChange={(event) => onFieldChange('liveMode', event.target.value)}
          className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
        >
          {snapshot.available_live_modes.map((mode) => (
            <option key={mode} value={mode}>
              {mode}
            </option>
          ))}
        </select>
      </label>
      <label className="block space-y-2">
        <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Execution mode</span>
        <select
          value={form.executionMode}
          onChange={(event) => onFieldChange('executionMode', event.target.value)}
          className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
        >
          {snapshot.available_execution_modes.map((mode) => (
            <option key={mode} value={mode}>
              {mode}
            </option>
          ))}
        </select>
      </label>
      <label className="block space-y-2">
        <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Export folder</span>
        <div className="flex gap-2">
          <input
            value={form.exportRoot}
            onChange={(event) => onFieldChange('exportRoot', event.target.value)}
            className="min-w-0 flex-1 border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
          />
          <button
            type="button"
            onClick={() => void onChooseDirectory()}
            className="border-2 border-lawn-border bg-lawn-dark px-3 py-2 text-[10px] font-black uppercase tracking-[0.14em] text-lawn-bg"
          >
            Browse
          </button>
        </div>
      </label>
      <button
        type="button"
        onClick={() => void onAttachPdf()}
        className="w-full border-2 border-lawn-accent bg-lawn-accent px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-bg"
      >
        Attach PDF context
      </button>
    </div>
  );
}
