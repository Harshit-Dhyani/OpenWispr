import type { ReactNode } from 'react';
import { useState, useCallback } from 'react';
import { Activity, AlertTriangle, Cpu, FolderOpen, LoaderCircle, Mic2, Play, RefreshCcw, Settings, Square, Upload, Wifi, WifiOff, Download, Volume2, Sparkles } from 'lucide-react';
import type { Device, DeviceProbeResult, Health, ModelCatalogEntry, ModelPreloadStatus } from '../types/api';
import { AppConstants } from '../lib/constants';
import { getLanguageLabel } from '../lib/languages';

type ConnectionStatus = 'sse-connected' | 'sse-reconnecting' | 'polling-fallback';
type GpuStatus = 'gpu-active' | 'cpu-fallback' | 'gpu-only-failed';

type FormState = {
  sessionTitle: string;
  captureMode: 'system' | 'microphone';
  deviceId: string;
  modelName: string;
  languageMode: string;
  liveMode: string;
  executionMode: string;
  exportRoot: string;
};

type SidebarProps = {
  form: FormState;
  devices: Device[];
  models: ModelCatalogEntry[];
  languages: string[];
  liveModes: string[];
  executionModes: string[];
  backendReady: boolean;
  sessionStatus: string;
  health: Health;
  modelLoading?: boolean;
  preloadStatus?: ModelPreloadStatus;
  meterValue: number;
  statusMessage: string;
  busy: boolean;
  connectionStatus?: ConnectionStatus;
  gpuStatus?: GpuStatus;
  onFieldChange: (key: keyof FormState, value: string) => void;
  onRefreshDevices: () => void;
  onChooseDirectory: () => void;
  onPreloadModel: () => void;
  onStart: () => void;
  onStop: () => void;
  onAttachPdf: () => void;
  onOpenSettings?: () => void;
};

export function Sidebar({
  form,
  devices,
  models,
  languages,
  liveModes,
  executionModes,
  backendReady,
  sessionStatus,
  health,
  modelLoading = false,
  preloadStatus,
  meterValue,
  statusMessage,
  busy,
  connectionStatus = 'polling-fallback',
  gpuStatus = 'cpu-fallback',
  onFieldChange,
  onRefreshDevices,
  onChooseDirectory,
  onPreloadModel,
  onStart,
  onStop,
  onAttachPdf,
  onOpenSettings,
}: SidebarProps) {
  const meterPercent = Math.max(0, Math.min(100, Math.round(meterValue * 220)));
  const hasError = Boolean(health.last_error);
  const loopbackDevices = devices.filter((device) => device.is_loopback || device.supports_loopback);
  const microphoneDevices = devices.filter(
    (device) => !loopbackDevices.some((candidate) => candidate.id === device.id),
  );
  const visibleDevices = form.captureMode === 'system' ? loopbackDevices : microphoneDevices;
  const selectedModel = models.find((entry) => entry.id === form.modelName);
  const [probeLoading, setProbeLoading] = useState(false);
  const [probeResult, setProbeResult] = useState<DeviceProbeResult | null>(null);
  const [probeError, setProbeError] = useState<string | null>(null);

  const handleDeviceTest = useCallback(async () => {
    if (!form.deviceId) return;
    setProbeLoading(true);
    setProbeError(null);
    setProbeResult(null);
    try {
      const result = (await window.transcriptaDesktop.fetchJson(
        `/api/devices/${encodeURIComponent(form.deviceId)}/probe`,
      )) as DeviceProbeResult & { ok?: boolean; error?: string };
      if (result.ok === false) {
        setProbeError(result.error || 'Probe failed');
        return;
      }
      setProbeResult(result);
    } catch (err) {
      setProbeError(err instanceof Error ? err.message : 'Probe failed');
    } finally {
      setProbeLoading(false);
    }
  }, [form.deviceId]);

  const getConnectionBadge = () => {
    switch (connectionStatus) {
      case 'sse-connected':
        return { text: 'SSE Connected', color: 'bg-theme-success text-lawn-bg', icon: Wifi };
      case 'sse-reconnecting':
        return { text: 'SSE Reconnecting', color: 'bg-theme-warning text-lawn-bg', icon: WifiOff };
      case 'polling-fallback':
      default:
        return { text: 'Polling Fallback', color: 'bg-theme-info text-lawn-bg', icon: Activity };
    }
  };

  const getGpuBadge = () => {
    switch (gpuStatus) {
      case 'gpu-active':
        return { text: 'GPU Active', color: 'bg-theme-success text-lawn-bg', icon: Cpu };
      case 'gpu-only-failed':
        return { text: 'GPU-Only Failed', color: 'bg-theme-error text-lawn-bg', icon: AlertTriangle };
      case 'cpu-fallback':
      default:
        return { text: 'CPU Fallback', color: 'bg-theme-warning text-lawn-bg', icon: Cpu };
    }
  };

  const getModelLoadTime = (modelName: string): number => {
    const runtimeName = models.find((entry) => entry.id === modelName)?.runtime_model_name ?? modelName;
    switch (runtimeName) {
      case 'tiny':
        return 5;
      case 'base':
        return 10;
      case 'small':
        return 20;
      case 'medium':
        return 40;
      case 'large-v3':
        return 90;
      default:
        return 20;
    }
  };

  const getLiveModeLabel = (mode: string): string => {
    const labels: Record<string, string> = {
      realtime: 'Real-time',
      low_latency: 'Low Latency',
      balanced: 'Balanced',
      high_accuracy: 'High Accuracy',
    };
    return labels[mode] || mode;
  };

  const getDeviceLabel = (device: Device): string => {
    const suffix = device.is_loopback || device.supports_loopback ? ' [rec]' : '';
    return `${device.name}${suffix}`;
  };

  const connBadge = getConnectionBadge();
  const gpuBadge = getGpuBadge();
  const ConnIcon = connBadge.icon;
  const GpuIcon = gpuBadge.icon;

  const isPreloading = preloadStatus?.loading ?? false;
  const preloadProgress = preloadStatus?.progress ?? 0;
  const preloadStage = preloadStatus?.stage ?? 'idle';
  const preloadStageLabel =
    preloadStage === 'warming'
      ? 'Warming Up'
      : preloadStage === 'loading'
        ? 'Loading Model'
        : preloadStage === 'downloading'
          ? 'Preparing'
          : preloadStage === 'ready'
            ? 'Ready'
            : preloadStage === 'failed'
              ? 'Failed'
              : 'Idle';

  return (
    <aside className="flex h-full w-full shrink-0 flex-col border-b-2 border-lawn-border bg-lawn-bg p-4 lg:h-full lg:overflow-hidden xl:border-b-0 xl:border-r-2">
      {/* Header with Settings Button */}
      <section className="border-2 border-lawn-border bg-lawn-dark p-4 shadow-brutal text-white mb-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.15em] text-lawn-accent">
              Local Transcription
            </p>
            <h1 className="font-display text-2xl uppercase tracking-tighter text-lawn-bg leading-none">
              {AppConstants.APP_NAME}
            </h1>
            <p className="mt-1 text-[10px] leading-4 text-stone-300 font-mono">
              Local audio capture and transcription
            </p>
          </div>
          <button
            onClick={onOpenSettings}
            className="flex items-center justify-center w-10 h-10 border-2 border-lawn-bg/40 bg-lawn-accent text-lawn-border hover:bg-lawn-bg hover:text-lawn-border hover:border-lawn-accent transition-all duration-200 shadow-brutal-sm"
            title="Open Settings"
            type="button"
          >
            <Settings size={20} strokeWidth={2.5} />
          </button>
        </div>
      </section>

      <div className="flex-1 overflow-y-auto pr-1 custom-scrollbar space-y-4">
        {/* Session Setup */}
        <section className="border-2 border-lawn-border bg-lawn-panel p-4 shadow-brutal flex flex-col gap-4">
          <div className="flex items-center justify-between border-b-2 border-lawn-border pb-2">
            <span className="text-[11px] font-black uppercase tracking-[0.1em] text-lawn-border">
              Session Setup
            </span>
            <span
              className={[
                'px-2 py-0.5 text-[9px] font-black uppercase tracking-widest border border-lawn-border',
                hasError
                  ? 'bg-theme-error text-lawn-bg'
                  : backendReady
                    ? 'bg-theme-success text-lawn-bg'
                    : 'bg-theme-info text-lawn-bg',
              ].join(' ')}
            >
              {hasError ? 'Error' : backendReady ? 'Ready' : 'Connecting'}
            </span>
          </div>

          <div className="space-y-4">
            <button
              type="button"
              onClick={onOpenSettings}
              className="flex w-full items-center justify-center gap-2 border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-[10px] font-black uppercase tracking-[0.12em] text-lawn-border transition-all hover:-translate-y-0.5 hover:bg-lawn-accent hover:text-lawn-border"
            >
              <Settings size={14} strokeWidth={2.5} />
              Open Full Settings
            </button>

            {/* Session Title */}
            <Field
              label="Session Title"
              control={
                <input
                  type="text"
                  value={form.sessionTitle}
                  onChange={(event) => onFieldChange('sessionTitle', event.target.value)}
                  className={inputClass}
                  placeholder="Study Session"
                />
              }
            />

            {/* Audio Device */}
            <Field
              label="Capture Mode"
              control={
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => onFieldChange('captureMode', 'system')}
                    className={[
                      sideButtonClass,
                      form.captureMode === 'system'
                        ? 'bg-lawn-accent text-lawn-bg border-lawn-accent'
                        : 'bg-lawn-bg text-lawn-border',
                    ].join(' ')}
                  >
                    <Volume2 size={14} strokeWidth={2.5} />
                    System Audio
                  </button>
                  <button
                    type="button"
                    onClick={() => onFieldChange('captureMode', 'microphone')}
                    className={[
                      sideButtonClass,
                      form.captureMode === 'microphone'
                        ? 'bg-lawn-accent text-lawn-bg border-lawn-accent'
                        : 'bg-lawn-bg text-lawn-border',
                    ].join(' ')}
                  >
                    <Mic2 size={14} strokeWidth={2.5} />
                    Microphone
                  </button>
                </div>
              }
            />

            <Field
              label="ASR Model"
              control={
                <div className="space-y-2">
                  <select
                    value={form.modelName}
                    onChange={(event) => onFieldChange('modelName', event.target.value)}
                    className={inputClass}
                  >
                    {models.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.display_name}
                        {model.installed ? '' : ' (not installed)'}
                        {model.recommended ? ' [recommended]' : ''}
                      </option>
                    ))}
                  </select>
                  {selectedModel ? (
                    <div className="border-2 border-lawn-border bg-lawn-bg p-2 text-[10px] leading-4">
                      <div className="mb-1 flex flex-wrap items-center gap-1.5">
                        <span className="font-black text-lawn-border">{selectedModel.display_name}</span>
                        <span
                          className={`px-1.5 py-0.5 text-[9px] font-black uppercase tracking-widest ${
                            selectedModel.installed
                              ? 'bg-theme-success text-lawn-bg'
                              : 'bg-theme-warning text-lawn-bg'
                          }`}
                        >
                          {selectedModel.installed ? 'Installed' : 'Not Installed'}
                        </span>
                        {selectedModel.recommended && (
                          <span className="flex items-center gap-1 bg-lawn-accent px-1.5 py-0.5 text-[9px] font-black uppercase tracking-widest text-lawn-bg">
                            <Sparkles size={10} strokeWidth={3} />
                            Recommended
                          </span>
                        )}
                      </div>
                      <p className="text-stone-500">{selectedModel.why_choose_this}</p>
                    </div>
                  ) : null}
                </div>
              }
            />

            <Field
              label="Audio Device"
              control={
                <div className="flex gap-2">
                  <select
                    value={form.deviceId}
                    onChange={(event) => onFieldChange('deviceId', event.target.value)}
                    className={`${inputClass} flex-1`}
                  >
                    {visibleDevices.length > 0 ? (
                      <optgroup label={form.captureMode === 'system' ? 'System Audio / Loopback' : 'Microphones'}>
                        {visibleDevices.map((device) => (
                          <option key={device.id} value={device.id}>
                            {getDeviceLabel(device)}
                          </option>
                        ))}
                      </optgroup>
                    ) : (
                      <option value="" disabled>
                        No {form.captureMode === 'system' ? 'loopback' : 'microphone'} devices available
                      </option>
                    )}
                  </select>
                  <button 
                    type="button" 
                    onClick={onRefreshDevices} 
                    className={sideButtonClass}
                    title="Refresh devices"
                  >
                    <RefreshCcw size={16} strokeWidth={3} />
                  </button>
                </div>
              }
            />

            {/* Model Preload Section */}
            <div className="border-2 border-lawn-border bg-lawn-bg p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-black uppercase tracking-[0.1em] text-lawn-border">
                  Model Preload
                </span>
                {isPreloading && (
                  <span className="text-[9px] font-black text-theme-warning animate-pulse">
                    Loading...
                  </span>
                )}
              </div>

              {isPreloading ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <LoaderCircle size={16} strokeWidth={3} className="animate-spin text-theme-warning" />
                    <div className="flex-1 min-w-0">
                      <p className="text-[10px] font-bold text-lawn-border truncate">
                        {preloadStatus?.message || 'Loading model...'}
                      </p>
                      <p className="text-[9px] text-stone-500">
                        {preloadStageLabel} · {form.modelName} (~{getModelLoadTime(form.modelName)}s)
                      </p>
                    </div>
                    {preloadStage === 'downloading' ? (
                      <span className="text-xs font-black text-theme-warning">{preloadProgress}%</span>
                    ) : (
                      <span className="text-[10px] font-black uppercase tracking-[0.12em] text-theme-warning">
                        {preloadStageLabel}
                      </span>
                    )}
                  </div>
                  {preloadStage === 'downloading' ? (
                    <div className="h-2 overflow-hidden border-[2px] border-lawn-border bg-lawn-bg">
                      <div
                        className="h-full border-r-2 border-lawn-border bg-theme-warning transition-all duration-300 ease-out"
                        style={{ width: `${preloadProgress}%` }}
                      />
                    </div>
                  ) : (
                    <div className="h-2 overflow-hidden border-[2px] border-lawn-border bg-lawn-bg">
                      <div className="h-full w-2/3 animate-pulse bg-theme-warning/70" />
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="text-stone-500">Current:</span>
                    <span className="font-bold text-lawn-border">{selectedModel?.display_name ?? form.modelName}</span>
                  </div>
                  <button
                    type="button"
                    onClick={onPreloadModel}
                    disabled={!backendReady || sessionStatus === 'running' || modelLoading}
                    className="w-full flex h-9 items-center justify-center gap-1.5 border-2 border-lawn-border bg-lawn-accent px-3 text-[10px] font-black uppercase tracking-[0.08em] text-lawn-border transition hover:-translate-y-[1px] hover:shadow-brutal-sm active:translate-y-0 active:shadow-none disabled:cursor-not-allowed disabled:bg-stone-300 disabled:shadow-none disabled:translate-y-0"
                  >
                    <Download size={12} strokeWidth={3} />
                    Preload
                  </button>
                </div>
              )}
            </div>

            {modelLoading && (
              <div className="border-2 border-theme-warning bg-theme-warning/10 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <LoaderCircle size={16} strokeWidth={3} className="animate-spin text-theme-warning" />
                  <span className="text-xs font-black text-theme-warning">Loading Model...</span>
                </div>
                <p className="text-[10px] text-theme-warning leading-4">
                  Loading {form.modelName} model (~{getModelLoadTime(form.modelName)}s)
                </p>
              </div>
            )}

            {/* Language & Live Mode */}
            <div className="grid grid-cols-2 gap-3">
              <Field
                label="Language"
                control={
                  <select
                    value={form.languageMode}
                    onChange={(event) => onFieldChange('languageMode', event.target.value)}
                    className={inputClass}
                  >
                    {languages.map((language) => (
                      <option key={language} value={language}>
                        {getLanguageLabel(language)}
                      </option>
                    ))}
                  </select>
                }
              />
              <Field
                label="Live Mode"
                control={
                  <select
                    value={form.liveMode}
                    onChange={(event) => onFieldChange('liveMode', event.target.value)}
                    className={inputClass}
                  >
                    {liveModes.map((mode) => (
                      <option key={mode} value={mode}>
                        {getLiveModeLabel(mode)}
                      </option>
                    ))}
                  </select>
                }
              />
            </div>

            {/* Execution Mode */}
            <Field
              label="Execution Mode"
              control={
                <select
                  value={form.executionMode}
                  onChange={(event) => onFieldChange('executionMode', event.target.value)}
                  className={inputClass}
                >
                  {executionModes.map((mode) => (
                    <option key={mode} value={mode}>
                      {mode}
                    </option>
                  ))}
                </select>
              }
            />

            {/* Export Folder */}
            <Field
              label="Export Folder"
              control={
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={form.exportRoot}
                    onChange={(event) => onFieldChange('exportRoot', event.target.value)}
                    className={`${inputClass} flex-1`}
                    placeholder="sessions"
                  />
                  <button 
                    type="button" 
                    onClick={onChooseDirectory} 
                    className={sideButtonClass}
                    title="Choose folder"
                  >
                    <FolderOpen size={16} strokeWidth={3} />
                  </button>
                </div>
              }
            />

            {/* Input Level Meter */}
            <div className="border-2 border-lawn-border bg-lawn-bg p-3">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-[10px] font-black uppercase tracking-[0.08em] text-lawn-border">
                  Input Level
                </span>
                <span className="text-xs font-black text-lawn-border">{meterPercent}%</span>
              </div>
              <div className="h-3 border-[2px] border-lawn-border bg-lawn-bg overflow-hidden">
                <div
                  className="h-full bg-lawn-accent transition-all duration-100 border-r-2 border-lawn-border"
                  style={{ width: `${meterPercent}%` }}
                />
              </div>
            </div>

            {/* Start/Stop Buttons */}
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                disabled={busy || sessionStatus === 'running' || modelLoading}
                onClick={onStart}
                className="flex h-10 items-center justify-center gap-1.5 border-2 border-lawn-border bg-lawn-accent px-3 text-[10px] font-black uppercase tracking-[0.08em] text-lawn-border transition hover:-translate-y-[2px] hover:shadow-brutal-sm active:translate-y-0 active:shadow-none disabled:cursor-not-allowed disabled:bg-stone-300 disabled:shadow-none disabled:translate-y-0"
              >
                {busy && sessionStatus !== 'running' ? <LoaderCircle size={14} strokeWidth={3} className="animate-spin" /> : <Play size={14} strokeWidth={3} />}
                Start
              </button>
              <button
                type="button"
                disabled={busy || sessionStatus !== 'running'}
                onClick={onStop}
                className="flex h-10 items-center justify-center gap-1.5 border-2 border-lawn-border bg-lawn-bg px-3 text-[10px] font-black uppercase tracking-[0.08em] text-lawn-border transition hover:-translate-y-[2px] hover:shadow-brutal-sm active:translate-y-0 active:shadow-none disabled:cursor-not-allowed disabled:bg-stone-200 disabled:shadow-none disabled:translate-y-0"
              >
                <Square size={14} strokeWidth={3} />
                Stop
              </button>
            </div>

            {/* Attach PDF */}
            <button
              type="button"
              onClick={onAttachPdf}
              className="flex h-10 w-full items-center justify-center gap-1.5 border-2 border-lawn-border bg-lawn-panel px-3 text-[10px] font-black uppercase tracking-[0.08em] text-lawn-border transition hover:-translate-y-[2px] hover:shadow-brutal-sm active:translate-y-0 active:shadow-none"
            >
              <Upload size={14} strokeWidth={3} />
              Attach PDF Context
            </button>
          </div>
        </section>

        {/* Runtime Section */}
        <section className="border-2 border-lawn-border bg-lawn-panel p-4 shadow-brutal flex flex-col gap-3">
          <div className="flex items-center justify-between border-b-2 border-lawn-border pb-2">
            <span className="text-[11px] font-black uppercase tracking-[0.1em] text-lawn-border">
              Runtime
            </span>
            <span className="px-2 py-0.5 border border-lawn-border bg-lawn-bg text-[9px] font-black uppercase tracking-widest text-lawn-border">
              {sessionStatus}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <Metric label="GPU" value={health.gpu_mode || 'unknown'} />
            <Metric label="Runtime" value={health.model_runtime_device || 'unknown'} />
            <Metric label="Queue" value={String(health.queue_depth ?? 0)} />
            <Metric label="STT Drops" value={String(health.dropped_stt_chunks ?? 0)} />
          </div>

          <div className="border-2 border-lawn-border bg-lawn-bg/50 p-3">
            <div className="mb-1.5 flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest text-stone-500">
              <Mic2 size={11} strokeWidth={3} />
              Status
            </div>
            <p className={`text-[11px] font-bold leading-4 ${hasError ? 'text-theme-error' : 'text-lawn-border'}`}>
              {statusMessage}
            </p>
          </div>
        </section>

        {/* Diagnostics Section */}
        <section className="border-2 border-lawn-border bg-lawn-panel p-4 shadow-brutal flex flex-col gap-3">
          <div className="flex items-center justify-between border-b-2 border-lawn-border pb-2">
            <span className="text-[11px] font-black uppercase tracking-[0.1em] text-lawn-border">
              Diagnostics
            </span>
            <div className="flex gap-1">
              <div className={`w-2 h-2 rounded-full ${connBadge.color}`} />
              <div className={`w-2 h-2 rounded-full ${gpuBadge.color}`} />
            </div>
          </div>

          {/* Connection Badge */}
          <div className="flex items-center gap-2 border-2 border-lawn-border bg-lawn-bg p-2">
            <div className={`p-1.5 ${connBadge.color}`}>
              <ConnIcon size={14} strokeWidth={3} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[9px] font-black uppercase tracking-widest text-stone-500">
                Connection
              </div>
              <div className="text-xs font-black text-lawn-border truncate">{connBadge.text}</div>
            </div>
          </div>

          {/* GPU Badge */}
          <div className="flex items-center gap-2 border-2 border-lawn-border bg-lawn-bg p-2">
            <div className={`p-1.5 ${gpuBadge.color}`}>
              <GpuIcon size={14} strokeWidth={3} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[9px] font-black uppercase tracking-widest text-stone-500">
                Compute
              </div>
              <div className="text-xs font-black text-lawn-border truncate">{gpuBadge.text}</div>
            </div>
          </div>

          {/* Device Test */}
          <div className="border-2 border-lawn-border bg-lawn-bg p-2">
            <button
              type="button"
              onClick={handleDeviceTest}
              disabled={probeLoading || !form.deviceId}
              className="w-full flex h-9 items-center justify-center gap-1.5 border-2 border-lawn-border bg-lawn-panel px-3 text-[10px] font-black uppercase tracking-[0.08em] text-lawn-border transition hover:-translate-y-[1px] hover:shadow-brutal-sm active:translate-y-0 active:shadow-none disabled:cursor-not-allowed disabled:bg-stone-300 disabled:shadow-none disabled:translate-y-0"
            >
              {probeLoading ? (
                <LoaderCircle size={14} strokeWidth={3} className="animate-spin" />
              ) : (
                <Mic2 size={14} strokeWidth={3} />
              )}
              {probeLoading ? 'Testing...' : 'Device Test'}
            </button>

            {probeResult && (
              <div className="mt-2 border-2 border-lawn-border bg-lawn-panel p-2 space-y-1.5">
                <div className="text-[9px] font-black uppercase tracking-widest text-stone-500 border-b border-lawn-border pb-1">
                  Probe Results
                </div>
                <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[10px]">
                  {probeResult.backend && (
                    <div className="col-span-2">
                      <span className="text-stone-500">Backend:</span>{' '}
                      <span className="font-bold uppercase">{probeResult.backend}</span>
                    </div>
                  )}
                  <div><span className="text-stone-500">RMS:</span> <span className="font-bold">{typeof probeResult.rms_mean === 'number' ? probeResult.rms_mean.toFixed(4) : 'n/a'}</span></div>
                  <div><span className="text-stone-500">Peak:</span> <span className="font-bold">{typeof probeResult.rms_peak === 'number' ? probeResult.rms_peak.toFixed(4) : 'n/a'}</span></div>
                  <div><span className="text-stone-500">Signal:</span> <span className={`font-bold ${probeResult.has_signal ? 'text-theme-success' : 'text-theme-error'}`}>{probeResult.has_signal ? 'Yes' : 'No'}</span></div>
                  <div><span className="text-stone-500">Channels:</span> <span className="font-bold">{probeResult.channels ?? 'n/a'}</span></div>
                  <div className="col-span-2"><span className="text-stone-500">Sample Rate:</span> <span className="font-bold">{probeResult.sample_rate ? `${probeResult.sample_rate} Hz` : 'n/a'}</span></div>
                </div>
              </div>
            )}

            {probeError && (
              <div className="mt-2 border-2 border-theme-error bg-theme-error/10 p-2">
                <div className="text-[10px] font-bold text-theme-error">{probeError}</div>
              </div>
            )}
          </div>

          {/* Backpressure */}
          <div className="border-2 border-lawn-border bg-lawn-bg p-2">
            <div className="text-[9px] font-black uppercase tracking-widest text-stone-500 mb-1.5">
              Backpressure
            </div>
            <div className="space-y-1">
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-lawn-border">State</span>
                <span className={`font-black px-1.5 py-0.5 border text-[9px] ${health.stt_backpressure_state === 'normal'
                  ? 'bg-theme-success/20 text-theme-success border-theme-success/30'
                  : health.stt_backpressure_state === 'elevated'
                    ? 'bg-theme-warning/20 text-theme-warning border-theme-warning/30'
                    : 'bg-theme-error/20 text-theme-error border-theme-error/30'
                  }`}>
                  {health.stt_backpressure_state || 'normal'}
                </span>
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-lawn-border">Queue</span>
                <span className="font-black text-lawn-border">{health.queue_depth ?? 0}</span>
              </div>
            </div>
          </div>

          {/* Warning */}
          {health.last_warning && (
            <div className="border-2 border-theme-warning bg-theme-warning/10 p-2">
              <div className="flex items-center gap-1.5 mb-1">
                <AlertTriangle size={12} strokeWidth={3} className="text-theme-warning" />
                <span className="text-[9px] font-black uppercase tracking-widest text-theme-warning">Warning</span>
              </div>
              <p className="text-[10px] font-bold text-theme-warning leading-4">{health.last_warning}</p>
            </div>
          )}
        </section>
      </div>
    </aside>
  );
}

function Field({ label, control }: { label: string; control: ReactNode }) {
  return (
    <label className="block">
      <div className="mb-1.5 text-[10px] font-black uppercase tracking-wider text-lawn-border truncate">
        {label}
      </div>
      {control}
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-lawn-border bg-lawn-bg p-2 flex flex-col justify-center">
      <div className="mb-0.5 text-[9px] font-black uppercase tracking-widest text-stone-500">
        {label}
      </div>
      <div className="text-xs font-black text-lawn-border truncate">{value}</div>
    </div>
  );
}

const inputClass =
  'h-9 w-full border-2 border-lawn-border bg-lawn-bg px-2.5 py-1 text-[11px] font-bold text-lawn-border outline-none transition focus:ring-2 focus:ring-lawn-accent/50 focus:shadow-brutal-sm hover:-translate-y-[1px] hover:shadow-brutal-sm placeholder:text-stone-400 rounded-none cursor-pointer';

const sideButtonClass =
  'flex h-9 w-9 flex-shrink-0 items-center justify-center border-2 border-lawn-border bg-lawn-panel text-lawn-border transition hover:-translate-y-[1px] hover:shadow-brutal-sm active:translate-y-0 active:shadow-none focus-visible:ring-2 focus-visible:ring-lawn-accent/50 rounded-none cursor-pointer';
