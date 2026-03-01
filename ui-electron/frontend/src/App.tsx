import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityFeed } from './components/ActivityFeed';
import { SettingsPanel } from './components/SettingsPanel';
import { MainContent } from './components/MainContent';
import { Sidebar } from './components/Sidebar';
import { useEventSource, type EventSourceEvent } from './hooks/useEventSource';
import {
  applyFormulaEvent,
  applyHealthEvent,
  applySegmentEvent,
  applySnapshot,
  applySuppressedSegmentEvent,
  buildInitialSnapshot,
} from './lib/sessionReducer';
import type {
  Device,
  Formula,
  Health,
  ModelPreloadStatus,
  Segment,
  SnapshotPayload,
  SettingsState,
  SystemProfile,
} from './types/api';

type FormState = {
  sessionTitle: string;
  deviceId: string;
  modelName: string;
  languageMode: string;
  liveMode: string;
  executionMode: string;
  exportRoot: string;
  // Hotkey settings
  hotkeyEnabled: boolean;
  hotkeyCombination: string;
  hotkeyHoldMode: boolean;
  hotkeyAutoInject: boolean;
};

const DEFAULT_FORM: FormState = {
  sessionTitle: 'Study Session',
  deviceId: '',
  modelName: 'small',
  languageMode: 'auto',
  liveMode: 'balanced',
  executionMode: 'auto',
  exportRoot: 'sessions',
  hotkeyEnabled: false,
  hotkeyCombination: 'Ctrl+Shift+Space',
  hotkeyHoldMode: true,
  hotkeyAutoInject: true,
};

// Default settings matching backend defaults
const DEFAULT_SETTINGS: SettingsState = {
  general: {
    defaultSessionTitle: 'New Session',
    defaultLanguage: 'auto',
    exportDirectory: '',
    autoSaveInterval: 30,
    showNotifications: true,
    minimizeToTray: true,
    startupWithSystem: false,
    theme: 'light',
  },
  transcription: {
    model_name: 'medium',
    compute_type: 'float16',
    chunk_duration: 1.6,
    overlap_ratio: 0.2,
    vad_enabled: true,
    vad_threshold_db: -40,
    confidence_threshold: 0.6,
    enable_filler_filter: true,
    enable_hallucination_filter: true,
    min_segment_length: 0.5,
    max_workers: 4,
    use_parallel_processing: true,
    preload_model: true,
    hotkey_optimized: false,
    beam_size: 5,
    best_of: 5,
    patience: 1.0,
    temperature: 0.0,
  },
  audio: {
    defaultDeviceId: 'default',
    sampleRate: 16000,
    vadEnabled: true,
    vadThresholdDb: -40,
    noiseFiltering: true,
    echoCancellation: true,
    autoGainControl: true,
  },
  hotkey: {
    enabled: true,
    key_combination: 'Ctrl+Shift+T',
    hold_mode: false,
    auto_inject: true,
    show_floating_window: true,
    floating_window_position: 'bottom-right',
    record_on_start: true,
    stop_on_release: false,
    copy_to_clipboard: true,
  },
  advanced: {
    debugMode: false,
    logLevel: 'INFO',
    enableMetrics: true,
    maxLogFiles: 10,
    experimentalStem: false,
    experimentalGpuAccel: true,
  },
  version: 1,
};

function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light');
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [devices, setDevices] = useState<Device[]>([]);
  const [snapshot, setSnapshot] = useState<SnapshotPayload>(buildInitialSnapshot());
  const [statusMessage, setStatusMessage] = useState('Connecting to the local backend.');
  const [backendReady, setBackendReady] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [modelLoading, setModelLoading] = useState(false);
  const [preloadStatus, setPreloadStatus] = useState<ModelPreloadStatus>({
    loading: false,
    progress: 0,
    message: '',
  });
  const [liveLatency, setLiveLatency] = useState<number | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [settings, setSettings] = useState<SettingsState>(DEFAULT_SETTINGS);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [hardwareProfile, setHardwareProfile] = useState<SystemProfile | undefined>(undefined);
  const initializedRef = useRef(false);
  const revisionRef = useRef(0);
  const pollTimerRef = useRef<number | null>(null);
  const startInFlightRef = useRef(false);
  const processedEventIds = useRef<Set<string>>(new Set());
  const sseEnabledRef = useRef(false);
  const partialSegmentRef = useRef<Segment | null>(null);

  const handleEvent = useCallback((event: EventSourceEvent) => {
    const eventId = `${event.type}-${event.timestamp}`;
    if (processedEventIds.current.has(eventId)) {
      return;
    }
    processedEventIds.current.add(eventId);

    if (processedEventIds.current.size > 1000) {
      const iterator = processedEventIds.current.values();
      const firstValue = iterator.next().value;
      if (firstValue) {
        processedEventIds.current.delete(firstValue);
      }
    }

    switch (event.type) {
      case 'segment': {
        const segment = event.payload as Segment;
        partialSegmentRef.current = segment.is_partial ? segment : null;
        setSnapshot((current) => applySegmentEvent(current, segment));
        if (segment.latency_ms !== undefined && segment.latency_ms !== null) {
          setLiveLatency(segment.latency_ms);
        }
        break;
      }
      case 'suppressed_segment': {
        const segment = event.payload as Segment;
        setSnapshot((current) => applySuppressedSegmentEvent(current, segment));
        break;
      }
      case 'health': {
        const { health, meter_value } = event.payload as { health: Health; meter_value: number };
        setSnapshot((current) => applyHealthEvent(current, { health, meter_value }));
        if (health.last_error) {
          setStatusMessage(health.last_error);
        }
        break;
      }
      case 'state': {
        const payload = event.payload as SnapshotPayload;
        revisionRef.current = payload.runtime_revision;
        setSnapshot((current) => applySnapshot(current, payload));
        break;
      }
      case 'formulas': {
        const formulas = event.payload as Formula[];
        setSnapshot((current) => applyFormulaEvent(current, formulas));
        break;
      }
      case 'loading': {
        const { loading, message } = event.payload as { loading: boolean; message: string };
        setModelLoading(loading);
        if (loading && message) {
          setStatusMessage(message);
        }
        break;
      }
      case 'preload_progress': {
        const { progress, message, model_name } = event.payload as { progress: number; message: string; model_name?: string };
        const normalizedProgress = progress <= 1 ? Math.round(progress * 100) : Math.round(progress);
        setPreloadStatus({
          loading: normalizedProgress < 100,
          progress: normalizedProgress,
          message,
          model_name,
        });
        break;
      }
    }
  }, []);

  const handleSseError = useCallback((error: Error) => {
    console.warn('SSE error:', error);
  }, []);

  const handleSseOpen = useCallback(() => {
    console.log('SSE connected');
  }, []);

  const { status: sseStatus, connect, disconnect } = useEventSource({
    url: '/api/events',
    maxReconnectAttempts: 3,
    baseReconnectDelay: 1000,
    maxReconnectDelay: 10000,
    pollInterval: 300,
    onMessage: handleEvent,
    onError: handleSseError,
    onOpen: handleSseOpen,
  });

  useEffect(() => {
    sseEnabledRef.current = sseStatus === 'connected';
  }, [sseStatus]);

  // Load settings from backend on mount
  const loadSettings = useCallback(async () => {
    try {
      setSettingsLoading(true);
      const response = await backendRequest<SettingsState>('/api/settings');
      setSettings(response);

      // Apply theme from settings
      if (response.general.theme && response.general.theme !== theme) {
        setTheme(response.general.theme);
      }

      // Apply settings to form state
      setForm((current) => ({
        ...current,
        sessionTitle: response.general.defaultSessionTitle || current.sessionTitle,
        deviceId: response.audio.defaultDeviceId || current.deviceId,
        modelName: response.transcription.model_name || current.modelName,
        languageMode: response.general.defaultLanguage || current.languageMode,
        exportRoot: response.general.exportDirectory || current.exportRoot,
        hotkeyEnabled: response.hotkey.enabled ?? current.hotkeyEnabled,
        hotkeyCombination: response.hotkey.key_combination || current.hotkeyCombination,
        hotkeyHoldMode: response.hotkey.hold_mode ?? current.hotkeyHoldMode,
        hotkeyAutoInject: response.hotkey.auto_inject ?? current.hotkeyAutoInject,
      }));

      // Apply hotkey config to Electron main process
      const hotkeyApi = window.transcriptaDesktop.hotkey;
      if (hotkeyApi) {
        await hotkeyApi.updateConfig({
          enabled: response.hotkey.enabled,
          key_combination: response.hotkey.key_combination,
          hold_mode: response.hotkey.hold_mode,
          auto_inject: response.hotkey.auto_inject,
          show_floating_window: response.hotkey.show_floating_window,
          floating_window_position: response.hotkey.floating_window_position,
          record_on_start: response.hotkey.record_on_start,
          stop_on_release: response.hotkey.stop_on_release,
          copy_to_clipboard: response.hotkey.copy_to_clipboard,
        });
      }

      console.log('Settings loaded successfully');
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setSettingsLoading(false);
    }
  }, [theme]);

  // Save settings to backend
  const saveSettings = useCallback(async (newSettings: SettingsState) => {
    try {
      await backendRequest('/api/settings', {
        method: 'POST',
        body: JSON.stringify(newSettings),
      });
      setSettings(newSettings);

      // Apply theme from settings
      setTheme((currentTheme) => {
        if (newSettings.general.theme !== currentTheme) {
          return newSettings.general.theme;
        }
        return currentTheme;
      });

      // Apply settings to form state
      setForm((current) => ({
        ...current,
        sessionTitle: newSettings.general.defaultSessionTitle,
        deviceId: newSettings.audio.defaultDeviceId,
        modelName: newSettings.transcription.model_name,
        languageMode: newSettings.general.defaultLanguage,
        exportRoot: newSettings.general.exportDirectory,
        hotkeyEnabled: newSettings.hotkey.enabled,
        hotkeyCombination: newSettings.hotkey.key_combination,
        hotkeyHoldMode: newSettings.hotkey.hold_mode,
        hotkeyAutoInject: newSettings.hotkey.auto_inject,
      }));

      // Apply hotkey config to Electron main process
      const hotkeyApi = window.transcriptaDesktop.hotkey;
      if (hotkeyApi) {
        await hotkeyApi.updateConfig({
          enabled: newSettings.hotkey.enabled,
          key_combination: newSettings.hotkey.key_combination,
          hold_mode: newSettings.hotkey.hold_mode,
          auto_inject: newSettings.hotkey.auto_inject,
          show_floating_window: newSettings.hotkey.show_floating_window,
          floating_window_position: newSettings.hotkey.floating_window_position,
          record_on_start: newSettings.hotkey.record_on_start,
          stop_on_release: newSettings.hotkey.stop_on_release,
          copy_to_clipboard: newSettings.hotkey.copy_to_clipboard,
        });
      }

      console.log('Settings saved successfully');
      return true;
    } catch (error) {
      console.error('Failed to save settings:', error);
      return false;
    }
  }, []);

  // Load hardware profile from backend
  const loadHardwareProfile = useCallback(async () => {
    try {
      const profile = await backendRequest<SystemProfile>('/api/system/profile');
      setHardwareProfile(profile);
    } catch (error) {
      console.error('Failed to load hardware profile:', error);
    }
  }, []);

  useEffect(() => {
    let disposeBackendExit: (() => void) | undefined;
    let disposeOpenSettings: (() => void) | undefined;
    void loadSettings();
    void loadDevices();
    void loadInitialSnapshot();
    void loadHotkeyConfig();
    void loadHardwareProfile();
    disposeBackendExit = window.transcriptaDesktop.onBackendExit(() => {
      setBackendReady(false);
      setStatusMessage('Backend exited. Restart the desktop app.');
      disconnect();
    });
    disposeOpenSettings = window.transcriptaDesktop.onOpenSettings(() => {
      setShowSettings(true);
    });
    return () => {
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current);
      }
      disposeBackendExit?.();
      disposeOpenSettings?.();
      disconnect();
    };
  }, []);

  useEffect(() => {
    if (isStarting) {
      return;
    }
    if (!backendReady) {
      disconnect();
      return;
    }

    const isRunning = snapshot.session?.status === 'running';
    if (isRunning) {
      connect();
    } else {
      disconnect();
    }
  }, [backendReady, snapshot.session?.status, isStarting, connect, disconnect]);

  useEffect(() => {
    if (isStarting) {
      return;
    }
    if (sseStatus === 'polling' || sseStatus === 'error') {
      scheduleNextPoll(snapshot.session?.status === 'running' ? 300 : 3000);
    } else if (sseStatus === 'connected') {
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    }
    return () => {
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current);
      }
    };
  }, [sseStatus, snapshot.session?.status, isStarting]);

  // Apply theme to document
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('theme', theme);
  }, [theme]);

  // Sync theme to settings when changed from Sidebar
  const saveSettingsRef = useRef(saveSettings);
  saveSettingsRef.current = saveSettings;

  useEffect(() => {
    // Sync theme to settings if different (only when settings are loaded)
    if (!settingsLoading && settings.general.theme !== theme) {
      const newSettings = { ...settings, general: { ...settings.general, theme } };
      setSettings(newSettings);
      // Debounced save to backend
      const timer = setTimeout(() => {
        void saveSettingsRef.current(newSettings);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [theme, settingsLoading]); // Deliberately NOT depending on settings to avoid circular updates

  async function backendRequest<T>(path: string, options?: RequestInit): Promise<T> {
    return window.transcriptaDesktop.fetchJson(path, options) as Promise<T>;
  }

  async function loadDevices() {
    try {
      const payload = await backendRequest<{ devices: Device[] }>('/api/devices');
      setDevices(payload.devices);
      setForm((current) => {
        const currentExists = payload.devices.some((device) => device.id === current.deviceId);
        const preferred = payload.devices.find((device) => device.is_loopback)?.id ?? payload.devices[0]?.id ?? '';
        return {
          ...current,
          deviceId: currentExists ? current.deviceId : preferred,
        };
      });
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : 'Unable to load devices.');
    }
  }

  async function loadHotkeyConfig() {
    try {
      const hotkeyApi = window.transcriptaDesktop.hotkey;
      if (!hotkeyApi) return;
      const state = await hotkeyApi.getState() as
        | {
            config?: {
              enabled?: boolean;
              key_combination?: string;
              hold_mode?: boolean;
              auto_inject?: boolean;
            };
          }
        | null
        | undefined;
      const config = state?.config;
      if (!config) {
        return;
      }
      setForm((current) => ({
        ...current,
        hotkeyEnabled: config.enabled ?? current.hotkeyEnabled,
        hotkeyCombination: config.key_combination ?? current.hotkeyCombination,
        hotkeyHoldMode: config.hold_mode ?? current.hotkeyHoldMode,
        hotkeyAutoInject: config.auto_inject ?? current.hotkeyAutoInject,
      }));
    } catch (error) {
      console.error('Failed to load hotkey config:', error);
    }
  }

  async function loadInitialSnapshot() {
    try {
      const payload = await backendRequest<SnapshotPayload>('/api/session');
      revisionRef.current = payload.runtime_revision;
      setSnapshot((current) => applySnapshot(current, payload));
      setModelLoading(payload.loading ?? false);
      setBackendReady(true);
      initializedRef.current = true;
      setForm((current) => ({
        ...current,
        modelName: payload.available_models.includes(current.modelName)
          ? current.modelName
          : payload.available_models[0] ?? 'small',
        languageMode: payload.available_languages.includes(current.languageMode)
          ? current.languageMode
          : payload.available_languages[0] ?? 'auto',
        liveMode: payload.available_live_modes.includes(current.liveMode)
          ? current.liveMode
          : payload.available_live_modes[0] ?? 'balanced',
        executionMode: payload.available_execution_modes.includes(current.executionMode)
          ? current.executionMode
          : payload.available_execution_modes[0] ?? 'auto',
      }));
      setStatusMessage(
        payload.session?.status === 'running'
          ? payload.health.gpu_mode.startsWith('cuda')
            ? 'Capturing and transcribing locally on GPU.'
            : payload.health.execution_mode === 'gpu_only'
              ? 'GPU-only mode requested but unavailable. Fix CUDA runtime.'
              : 'Capturing locally on CPU fallback. Use hi or en instead of auto for better speed.'
          : 'Ready. Configure a session and start.'
      );
    } catch (error) {
      setBackendReady(false);
      setStatusMessage(error instanceof Error ? error.message : 'Backend unavailable.');
      scheduleNextPoll(2500);
    }
  }

  async function loadSnapshot(isPoll: boolean) {
    if (isStarting && isPoll) {
      return;
    }
    if (sseEnabledRef.current && isPoll) {
      return;
    }

    try {
      const payload = await backendRequest<SnapshotPayload>('/api/session');
      if (isPoll && payload.runtime_revision === revisionRef.current) {
        setBackendReady(true);
        scheduleNextPoll(payload.session?.status === 'running' ? 300 : 3000);
        return;
      }
      revisionRef.current = payload.runtime_revision;
      setSnapshot((current) => applySnapshot(current, payload));
      setModelLoading(payload.loading ?? false);
      setBackendReady(true);

      if (payload.health.last_error) {
        setStatusMessage(payload.health.last_error);
      } else if (!isPoll) {
        setStatusMessage(
          payload.session?.status === 'running'
            ? payload.health.gpu_mode.startsWith('cuda')
              ? 'Capturing and transcribing locally on GPU.'
              : payload.health.execution_mode === 'gpu_only'
                ? 'GPU-only mode requested but unavailable. Fix CUDA runtime.'
                : 'Capturing locally on CPU fallback. Use hi or en instead of auto for better speed.'
            : 'Ready. Configure a session and start.'
        );
      }
      scheduleNextPoll(payload.session?.status === 'running' ? 300 : 3000);
    } catch (error) {
      setBackendReady(false);
      setStatusMessage(error instanceof Error ? error.message : 'Backend unavailable.');
      scheduleNextPoll(2500);
    }
  }

  function scheduleNextPoll(delayMs: number) {
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current);
    }
    pollTimerRef.current = window.setTimeout(() => {
      void loadSnapshot(true);
    }, delayMs);
  }

  async function chooseDirectory() {
    const folder = await window.transcriptaDesktop.chooseDirectory();
    if (folder) {
      setForm((current) => ({ ...current, exportRoot: folder }));
    }
  }

  async function preloadModel() {
    setPreloadStatus({ loading: true, progress: 0, message: 'Starting preload...' });
    try {
      await backendRequest('/api/models/preload', {
        method: 'POST',
        body: JSON.stringify({
          model_name: form.modelName,
          execution_mode: form.executionMode,
        }),
      });
    } catch (error) {
      setPreloadStatus({ loading: false, progress: 0, message: '' });
      setStatusMessage(error instanceof Error ? error.message : 'Failed to preload model.');
    }
  }

  async function startSession() {
    if (startInFlightRef.current || isStarting || snapshot.session?.status === 'running') {
      return;
    }
    startInFlightRef.current = true;
    setIsStarting(true);
    setStatusMessage('Starting session...');
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    disconnect();
    try {
      await backendRequest('/api/session/start', {
        method: 'POST',
        body: JSON.stringify({
          title: form.sessionTitle.trim() || 'Study Session',
          output_root: form.exportRoot.trim() || 'sessions',
          model_name: form.modelName,
          language_mode: form.languageMode,
          live_mode: form.liveMode,
          execution_mode: form.executionMode,
          device_id: form.deviceId || null,
        }),
      });
      await loadSnapshot(false);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : 'Unable to start session.');
    } finally {
      setIsStarting(false);
      startInFlightRef.current = false;
    }
  }

  async function stopSession() {
    setIsStopping(true);
    setStatusMessage('Stopping session...');
    try {
      await backendRequest('/api/session/stop', { method: 'POST' });
      await loadSnapshot(false);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : 'Unable to stop session.');
    } finally {
      setIsStopping(false);
    }
  }

  async function attachPdf() {
    const file = await window.transcriptaDesktop.choosePdf();
    if (!file) {
      return;
    }
    try {
      await backendRequest('/api/session/attach-pdf', {
        method: 'POST',
        body: JSON.stringify({ path: file }),
      });
      await loadSnapshot(false);
      setStatusMessage(`Attached ${file.split(/[\\/]/).pop()}`);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : 'Unable to attach PDF.');
    }
  }

  const busy = isStarting || isStopping;
  const connectionStatus =
    sseStatus === 'connected'
      ? 'sse-connected'
      : sseStatus === 'reconnecting'
        ? 'sse-reconnecting'
        : 'polling-fallback';
  const gpuStatus =
    snapshot.health.gpu_mode.startsWith('cuda')
      ? 'gpu-active'
      : snapshot.health.execution_mode === 'gpu_only' && !snapshot.health.gpu_mode.startsWith('cuda')
        ? 'gpu-only-failed'
        : 'cpu-fallback';

  return (
    <div className="h-screen w-screen bg-lawn-bg text-lawn-border font-mono selection:bg-lawn-accent selection:text-lawn-bg transition-colors duration-300 overflow-hidden">
      <div className="grid h-full grid-cols-1 lg:grid-cols-[320px_280px_1fr] lg:h-full lg:overflow-hidden">
        <Sidebar
          theme={theme}
          onThemeChange={setTheme}
          form={form}
          devices={devices}
          models={snapshot.available_models}
          languages={snapshot.available_languages}
          liveModes={snapshot.available_live_modes}
          executionModes={snapshot.available_execution_modes}
          backendReady={backendReady}
          sessionStatus={snapshot.session?.status ?? 'idle'}
          health={snapshot.health}
          meterValue={snapshot.meter_value}
          statusMessage={statusMessage}
          busy={busy}
          modelLoading={modelLoading}
          preloadStatus={preloadStatus}
          connectionStatus={connectionStatus}
          gpuStatus={gpuStatus}
          onFieldChange={(key, value) => setForm((current) => ({ ...current, [key]: value }))}
          onRefreshDevices={() => void loadDevices()}
          onChooseDirectory={() => void chooseDirectory()}
          onPreloadModel={() => void preloadModel()}
          onStart={() => void startSession()}
          onStop={() => void stopSession()}
          onAttachPdf={() => void attachPdf()}
          onOpenSettings={() => setShowSettings(true)}
        />
        
        <ActivityFeed 
          session={snapshot.session} 
          transcript={snapshot.transcript} 
          health={snapshot.health}
        />
        
        <MainContent snapshot={snapshot} liveLatency={liveLatency} />
      </div>

      {showSettings && (
        <SettingsPanel
          isOpen={showSettings}
          onClose={() => setShowSettings(false)}
          initialSettings={settings}
          onSettingsChange={async (newSettings) => {
            const success = await saveSettings(newSettings);
            if (success) {
              console.log("Settings saved successfully");
            } else {
              console.error("Failed to save settings");
            }
          }}
          onSettingsReset={async () => {
            try {
              await backendRequest('/api/settings/reset', { method: 'POST' });
              await loadSettings();
              console.log("Settings reset to defaults");
            } catch (error) {
              console.error("Failed to reset settings:", error);
            }
          }}
          hardwareProfile={hardwareProfile}
          availableModels={snapshot.available_models}
          availableLanguages={snapshot.available_languages}
          audioDevices={devices.map(d => ({ id: d.id, name: d.name }))}
        />
      )}
    </div>
  );
}

export default App;
