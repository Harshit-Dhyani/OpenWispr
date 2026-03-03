import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityFeed } from './components/ActivityFeed';
import { SettingsPanel } from './components/SettingsPanel';
import { MainContent } from './components/MainContent';
import { Sidebar } from './components/Sidebar';
import { useEventSource, type EventSourceEvent } from './hooks/useEventSource';
import {
  applyModelCatalogPayload,
  applyModelDownloadEvent,
  EMPTY_MODEL_MANAGER_STATE,
} from './lib/modelRegistry';
import {
  applyFormulaEvent,
  applyHealthEvent,
  applySegmentEvent,
  applySnapshot,
  applySuppressedSegmentEvent,
  buildInitialSnapshot,
} from './lib/sessionReducer';
import { DEFAULT_SETTINGS, isFakeSetting } from './lib/settingsSchema';
import type { SettingsState } from './lib/settingsSchema';
import { sanitizeSettings } from './lib/settingsMigration';
import type {
  Device,
  Formula,
  Health,
  ModelCatalogPayload,
  ModelPreloadStatus,
  Segment,
  SnapshotPayload,
  SystemProfile,
  StartSessionRequest,
} from './types/api';

type FormState = {
  sessionTitle: string;
  captureMode: 'system' | 'microphone';
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
  captureMode: 'system',
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
  const [modelManager, setModelManager] = useState(EMPTY_MODEL_MANAGER_STATE);
  const initializedRef = useRef(false);
  const revisionRef = useRef(0);
  const pollTimerRef = useRef<number | null>(null);
  const startInFlightRef = useRef(false);
  const processedEventIds = useRef<Set<string>>(new Set());
  const sseEnabledRef = useRef(false);
  const partialSegmentRef = useRef<Segment | null>(null);
  const dirtyFieldsRef = useRef<Set<keyof FormState>>(new Set());
  const loadSettingsInFlightRef = useRef(false);

  const updateFormField = useCallback(
    <K extends keyof FormState>(key: K, value: FormState[K]) => {
      dirtyFieldsRef.current.add(key);
      setForm((current) => ({ ...current, [key]: value }));
    },
    [],
  );

  const mergeFormDefaults = useCallback((defaults: Partial<FormState>) => {
    setForm((current) => {
      const next = { ...current };
      for (const [rawKey, rawValue] of Object.entries(defaults)) {
        const key = rawKey as keyof FormState;
        const value = rawValue as FormState[keyof FormState] | undefined;
        if (value === undefined || dirtyFieldsRef.current.has(key)) {
          continue;
        }
        (next as any)[key] = value;
      }
      return next;
    });
  }, []);

  const handleEvent = useCallback((event: EventSourceEvent) => {
    const eventId = `${event.type}-${event.timestamp}`;
    if (processedEventIds.current.has(eventId)) {
      return;
    }
    processedEventIds.current.add(eventId);

    // Fix unbounded growth - clear half the set when limit exceeded
    if (processedEventIds.current.size > 1000) {
      const iterator = processedEventIds.current.values();
      const itemsToDelete = Math.floor(processedEventIds.current.size / 2);
      for (let i = 0; i < itemsToDelete; i++) {
        const value = iterator.next().value;
        if (value) {
          processedEventIds.current.delete(value);
        }
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
    // Prevent duplicate requests
    if (loadSettingsInFlightRef.current) {
      console.log('Settings load already in progress, skipping duplicate request');
      return;
    }

    loadSettingsInFlightRef.current = true;

    try {
      setSettingsLoading(true);
      const response = await backendRequest<SettingsState>('/api/settings');
      const migrated = sanitizeSettings(response);
      setSettings(migrated);

      // Apply theme from settings
      if (migrated.general.theme && migrated.general.theme !== theme) {
        setTheme(migrated.general.theme);
      }

      // Apply settings to form state
      mergeFormDefaults({
        sessionTitle: migrated.general.defaultSessionTitle || undefined,
        captureMode: (migrated.audio.captureMode as FormState['captureMode']) || undefined,
        deviceId: migrated.audio.defaultDeviceId || undefined,
        modelName: migrated.transcription.default_asr_model_id || migrated.transcription.model_name || undefined,
        languageMode: migrated.general.defaultLanguage || undefined,
        exportRoot: migrated.general.exportDirectory || undefined,
        hotkeyEnabled: migrated.hotkey.enabled,
        hotkeyCombination: migrated.hotkey.key_combination || undefined,
        hotkeyHoldMode: migrated.hotkey.hold_mode,
        hotkeyAutoInject: migrated.hotkey.auto_inject,
      });

      // Apply hotkey config to Electron main process
      const hotkeyApi = window.transcriptaDesktop?.hotkey;
      if (hotkeyApi) {
        await hotkeyApi.updateConfig({
          enabled: migrated.hotkey.enabled,
          key_combination: migrated.hotkey.key_combination,
          hold_mode: migrated.hotkey.hold_mode,
          auto_inject: migrated.hotkey.auto_inject,
          language: migrated.hotkey.language,
          device_id: migrated.hotkey.device_id,
          finish_mode_default: migrated.hotkey.finish_mode_default,
          show_floating_window: migrated.hotkey.show_floating_window,
          floating_window_position: migrated.hotkey.floating_window_position,
          record_on_start: migrated.hotkey.record_on_start,
          stop_on_release: migrated.hotkey.stop_on_release,
          copy_to_clipboard: migrated.hotkey.copy_to_clipboard,
        });
      }

      console.log('Settings loaded successfully');
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setSettingsLoading(false);
      loadSettingsInFlightRef.current = false;
    }
  }, [mergeFormDefaults, theme]);

  // Save settings to backend
  const saveSettings = useCallback(async (newSettings: SettingsState) => {
    try {
      // Filter out fake settings before sending to backend
      const cleanedSettings: SettingsState = {
        general: Object.fromEntries(
          Object.entries(newSettings.general).filter(([key]) => !isFakeSetting('general', key))
        ) as SettingsState['general'],
        transcription: Object.fromEntries(
          Object.entries(newSettings.transcription).filter(([key]) => !isFakeSetting('transcription', key))
        ) as SettingsState['transcription'],
        refiner: newSettings.refiner,
        audio: Object.fromEntries(
          Object.entries(newSettings.audio).filter(([key]) => !isFakeSetting('audio', key))
        ) as SettingsState['audio'],
        hotkey: Object.fromEntries(
          Object.entries(newSettings.hotkey).filter(([key]) => !isFakeSetting('hotkey', key))
        ) as SettingsState['hotkey'],
        advanced: Object.fromEntries(
          Object.entries(newSettings.advanced).filter(([key]) => !isFakeSetting('advanced', key))
        ) as SettingsState['advanced'],
        version: newSettings.version,
      };

      await backendRequest('/api/settings', {
        method: 'POST',
        body: JSON.stringify(cleanedSettings),
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
      mergeFormDefaults({
        sessionTitle: newSettings.general.defaultSessionTitle,
        captureMode: newSettings.audio.captureMode as FormState['captureMode'],
        deviceId: newSettings.audio.defaultDeviceId,
        modelName: newSettings.transcription.default_asr_model_id,
        languageMode: newSettings.general.defaultLanguage,
        exportRoot: newSettings.general.exportDirectory,
        hotkeyEnabled: newSettings.hotkey.enabled,
        hotkeyCombination: newSettings.hotkey.key_combination,
        hotkeyHoldMode: newSettings.hotkey.hold_mode,
        hotkeyAutoInject: newSettings.hotkey.auto_inject,
      });

      // Apply hotkey config to Electron main process
      const hotkeyApi = window.transcriptaDesktop.hotkey;
      if (hotkeyApi) {
        await hotkeyApi.updateConfig({
          enabled: newSettings.hotkey.enabled,
          key_combination: newSettings.hotkey.key_combination,
          hold_mode: newSettings.hotkey.hold_mode,
          auto_inject: newSettings.hotkey.auto_inject,
          language: newSettings.hotkey.language,
          device_id: newSettings.hotkey.device_id,
          finish_mode_default: newSettings.hotkey.finish_mode_default,
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
  }, [mergeFormDefaults]);

  const loadModelCatalog = useCallback(async () => {
    try {
      const payload = await backendRequest<ModelCatalogPayload>('/api/models/catalog');
      setModelManager((current) => applyModelCatalogPayload(current, payload));
    } catch (error) {
      console.error('Failed to load model catalog:', error);
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
    void loadModelCatalog();
    const disposeModelDownloads = window.transcriptaDesktop.models.onDownloadEvent((eventPayload) => {
      setModelManager((current) =>
        applyModelDownloadEvent(current, eventPayload.event, eventPayload.payload),
      );
      if (eventPayload.event === 'model-download-completed') {
        void loadModelCatalog();
      }
    });
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
      disposeModelDownloads?.();
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
  const pendingTimerRef = useRef<number | null>(null);

  useEffect(() => {
    // Sync theme to settings if different (only when settings are loaded)
    if (!settingsLoading && settings.general.theme !== theme) {
      const newSettings = {
        ...settings,
        general: { ...settings.general, theme: theme as SettingsState['general']['theme'] },
      };
      setSettings(newSettings);
      // Cancel any pending save
      if (pendingTimerRef.current !== null) {
        window.clearTimeout(pendingTimerRef.current);
      }
      // Debounced save to backend
      pendingTimerRef.current = window.setTimeout(() => {
        pendingTimerRef.current = null;
        void saveSettingsRef.current(newSettings);
      }, 500);
      return () => {
        if (pendingTimerRef.current !== null) {
          window.clearTimeout(pendingTimerRef.current);
        }
      };
    }
  }, [theme, settingsLoading, settings]); // Include settings dependency to fix stale closure

  async function backendRequest<T>(path: string, options?: RequestInit): Promise<T> {
    return window.transcriptaDesktop.fetchJson(path, options) as Promise<T>;
  }

  async function loadDevices() {
    try {
      const payload = await backendRequest<{ devices: Device[] }>('/api/devices');
      setDevices(payload.devices);
      setForm((current) => {
        const eligibleDevices = payload.devices.filter((device) =>
          current.captureMode === 'system'
            ? Boolean(device.is_loopback || device.supports_loopback)
            : !Boolean(device.is_loopback || device.supports_loopback),
        );
        const currentExists = payload.devices.some((device) => device.id === current.deviceId);
        const preferred =
          eligibleDevices[0]?.id ??
          payload.devices.find((device) => device.is_loopback)?.id ??
          payload.devices[0]?.id ??
          '';
        return {
          ...current,
          deviceId: currentExists || dirtyFieldsRef.current.has('deviceId') ? current.deviceId : preferred,
        };
      });
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : 'Unable to load devices.');
    }
  }

  useEffect(() => {
    if (!devices.length) {
      return;
    }
    setForm((current) => {
      const eligibleDevices = devices.filter((device) =>
        current.captureMode === 'system'
          ? Boolean(device.is_loopback || device.supports_loopback)
          : !Boolean(device.is_loopback || device.supports_loopback),
      );
      if (!eligibleDevices.length) {
        return current;
      }
      const currentStillEligible = eligibleDevices.some((device) => device.id === current.deviceId);
      if (currentStillEligible) {
        return current;
      }
      return {
        ...current,
        deviceId: eligibleDevices[0]?.id ?? current.deviceId,
      };
    });
  }, [devices, form.captureMode]);

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
              language?: string;
              device_id?: string;
              finish_mode_default?: 'finish' | 'finish_and_paste';
            };
          }
        | null
        | undefined;
      const config = state?.config;
      if (!config) {
        return;
      }
      mergeFormDefaults({
        hotkeyEnabled: config.enabled,
        hotkeyCombination: config.key_combination ?? undefined,
        hotkeyHoldMode: config.hold_mode,
        hotkeyAutoInject: config.auto_inject,
      });
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
        modelName:
          dirtyFieldsRef.current.has('modelName') || payload.available_models.includes(current.modelName) || modelManager.catalog.some((entry) => entry.id === current.modelName)
            ? current.modelName
            : modelManager.selectedAsrModelId ?? payload.available_models[0] ?? 'whisper-medium',
        languageMode:
          dirtyFieldsRef.current.has('languageMode') || payload.available_languages.includes(current.languageMode)
            ? current.languageMode
            : payload.available_languages[0] ?? 'auto',
        liveMode:
          dirtyFieldsRef.current.has('liveMode') || payload.available_live_modes.includes(current.liveMode)
            ? current.liveMode
            : payload.available_live_modes[0] ?? 'balanced',
        executionMode:
          dirtyFieldsRef.current.has('executionMode') ||
          payload.available_execution_modes.includes(current.executionMode)
            ? current.executionMode
            : payload.available_execution_modes[0] ?? 'auto',
      }));
      setStatusMessage(
        payload.session?.status === 'running'
          ? payload.health?.gpu_mode?.startsWith('cuda')
            ? 'Capturing and transcribing locally on GPU.'
            : payload.health?.execution_mode === 'gpu_only'
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
          ? payload.health?.gpu_mode?.startsWith('cuda')
            ? 'Capturing and transcribing locally on GPU.'
            : payload.health?.execution_mode === 'gpu_only'
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
      updateFormField('exportRoot', folder);
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
      const requestBody: StartSessionRequest = {
        title: form.sessionTitle.trim() || 'Study Session',
        output_root: form.exportRoot.trim() || 'sessions',
        model_name: form.modelName,
        language_mode: form.languageMode,
        live_mode: form.liveMode,
        execution_mode: form.executionMode,
        device_id: form.deviceId || null,
        // VAD parameters from settings
        vad_threshold: settings.transcription.vad_threshold_db,
        vad_min_silence_ms: settings.transcription.vad_min_silence_ms,
        vad_speech_pad_ms: settings.transcription.vad_speech_pad_ms,
      };
      await backendRequest('/api/session/start', {
        method: 'POST',
        body: JSON.stringify(requestBody),
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
    snapshot.health?.gpu_mode?.startsWith('cuda')
      ? 'gpu-active'
      : snapshot.health?.execution_mode === 'gpu_only' && !snapshot.health?.gpu_mode?.startsWith('cuda')
        ? 'gpu-only-failed'
        : 'cpu-fallback';

  const activityFeedNode = (
    <ActivityFeed
      session={snapshot.session}
      transcript={snapshot.transcript}
      health={snapshot.health}
    />
  );

  return (
    <div className="h-screen w-screen bg-lawn-bg text-lawn-border font-mono selection:bg-lawn-accent selection:text-lawn-bg transition-colors duration-300 overflow-hidden">
      <div className="grid h-full grid-cols-1 xl:grid-cols-[minmax(320px,360px)_minmax(280px,360px)_minmax(0,1fr)] 2xl:grid-cols-[minmax(340px,400px)_minmax(300px,420px)_minmax(0,1.2fr)] xl:h-full xl:overflow-hidden">
        <Sidebar
          form={form}
          devices={devices}
          models={modelManager.catalog.filter((entry) => entry.category === 'asr')}
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
          onFieldChange={(key, value) => updateFormField(key, value)}
          onRefreshDevices={() => void loadDevices()}
          onChooseDirectory={() => void chooseDirectory()}
          onPreloadModel={() => void preloadModel()}
          onStart={() => void startSession()}
          onStop={() => void stopSession()}
          onAttachPdf={() => void attachPdf()}
          onOpenSettings={() => setShowSettings(true)}
        />
        
        {activityFeedNode}

        <MainContent snapshot={snapshot} liveLatency={liveLatency} activityFeed={activityFeedNode} />
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
          modelManager={modelManager}
          onDownloadModel={async (modelId) => {
            await window.transcriptaDesktop.models.download(modelId);
            await loadModelCatalog();
          }}
          onCancelModelDownload={async (modelId) => {
            await window.transcriptaDesktop.models.cancel(modelId);
          }}
          onRemoveModel={async (modelId) => {
            await window.transcriptaDesktop.models.remove(modelId);
            await loadModelCatalog();
          }}
          availableLanguages={snapshot.available_languages}
          audioDevices={devices}
        />
      )}
    </div>
  );
}

export default App;
