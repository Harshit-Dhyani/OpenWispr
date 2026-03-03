import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
  applyRefinedSegmentEvent,
  applySegmentEvent,
  applySnapshot,
  applySuppressedSegmentEvent,
  buildInitialSnapshot,
} from './lib/sessionReducer';
import {
  buildStructuredLiveDraft,
  clearLiveDraftForCommit,
  isEventForActiveSession,
  shouldIgnoreLegacyPartial,
  type LiveDraftState,
} from './lib/liveTranscript';
import { resolveSourceModelId, syncInheritedAsrModelIds } from './lib/asrRouting';
import { getEligibleDevices, resolveRequestedDeviceId } from './lib/sessionStart';
import { DEFAULT_SETTINGS, isFakeSetting } from './lib/settingsSchema';
import type { SettingsState } from './lib/settingsSchema';
import { sanitizeSettings } from './lib/settingsMigration';
import type {
  Device,
  Formula,
  Health,
  DraftPartialPayload,
  CommitFinalPayload,
  ModelCatalogPayload,
  ModelPreloadStatus,
  RefineFinalPayload,
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

type TranscriptDebugEvent = {
  id: number;
  type: string;
  sessionId: string | null;
  segmentId: string | null;
  correlationId?: string | null;
  detail?: string | null;
  textLength: number;
};

const DEFAULT_FORM: FormState = {
  sessionTitle: 'Study Session',
  captureMode: 'microphone',
  deviceId: '',
  modelName: 'whisper-medium',
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
  const [liveDraft, setLiveDraft] = useState<LiveDraftState | null>(null);
  const [transcriptDebugEvents, setTranscriptDebugEvents] = useState<TranscriptDebugEvent[]>([]);
  const initializedRef = useRef(false);
  const revisionRef = useRef(0);
  const pollTimerRef = useRef<number | null>(null);
  const startInFlightRef = useRef(false);
  const sseEnabledRef = useRef(false);
  const partialSegmentRef = useRef<Segment | null>(null);
  const dirtyFieldsRef = useRef<Set<keyof FormState>>(new Set());
  const loadSettingsInFlightRef = useRef(false);
  const preloadedModelKeysRef = useRef<Set<string>>(new Set());
  const activeSessionIdRef = useRef<string | null>(null);

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

  const pushDebugEvent = useCallback(
    (
      type: string,
      payload: {
        session_id?: string | null;
        segment_id?: string | null;
        correlation_id?: string | null;
        detail?: string | null;
        text?: string | null;
        committed_text?: string | null;
        draft_suffix?: string | null;
      },
    ) => {
      if (!settings.advanced.debugMode) {
        return;
      }
      const textLength = (payload.text ?? payload.committed_text ?? payload.draft_suffix ?? '').length;
      setTranscriptDebugEvents((current) => [
        ...current.slice(-11),
        {
          id: Date.now() + current.length,
          type,
          sessionId: payload.session_id ?? null,
          segmentId: payload.segment_id ?? null,
          correlationId: payload.correlation_id ?? null,
          detail: payload.detail ?? null,
          textLength,
        },
      ]);
    },
    [settings.advanced.debugMode],
  );

  const pushTranscriptDebugEvent = useCallback(
    (
      type: string,
      payload: {
        session_id?: string | null;
        segment_id?: string | null;
        correlation_id?: string | null;
        text?: string | null;
        committed_text?: string | null;
        draft_suffix?: string | null;
      },
    ) => {
      pushDebugEvent(type, payload);
    },
    [pushDebugEvent],
  );

  const handleEvent = useCallback((event: EventSourceEvent) => {
    switch (event.type) {
      case 'draft_partial': {
        const payload = event.payload as DraftPartialPayload;
        if (!isEventForActiveSession(activeSessionIdRef.current, payload.session_id)) {
          break;
        }
        pushTranscriptDebugEvent(event.type, payload);
        setLiveDraft(buildStructuredLiveDraft(payload));
        break;
      }
      case 'commit_final': {
        const payload = event.payload as CommitFinalPayload;
        if (!isEventForActiveSession(activeSessionIdRef.current, payload.session_id)) {
          break;
        }
        pushTranscriptDebugEvent(event.type, {
          session_id: payload.session_id,
          segment_id: payload.segment_id,
          text: payload.segment?.display_text || payload.segment?.text || payload.text,
        });
        setLiveDraft((current) =>
          clearLiveDraftForCommit(current, activeSessionIdRef.current, payload),
        );
        setSnapshot((current) => applySegmentEvent(current, payload.segment));
        break;
      }
      case 'refine_final': {
        const payload = event.payload as RefineFinalPayload;
        if (!isEventForActiveSession(activeSessionIdRef.current, payload.session_id)) {
          break;
        }
        setSnapshot((current) => applyRefinedSegmentEvent(current, payload.segment));
        break;
      }
      case 'segment': {
        const segment = event.payload as Segment;
        if (segment.is_partial) {
          pushTranscriptDebugEvent(event.type, {
            session_id: activeSessionIdRef.current,
            segment_id: segment.id,
            text: segment.display_text || segment.text,
          });
          partialSegmentRef.current = segment;
          setLiveDraft((current) => {
            if (shouldIgnoreLegacyPartial(current, activeSessionIdRef.current)) {
              return current;
            }
            return {
              sessionId: activeSessionIdRef.current,
              committedText: '',
              draftSuffix: segment.display_text || segment.text,
              revision: revisionRef.current,
              source: 'legacy',
            };
          });
        } else {
          pushTranscriptDebugEvent(event.type, {
            session_id: activeSessionIdRef.current,
            segment_id: segment.id,
            text: segment.display_text || segment.text,
          });
          partialSegmentRef.current = null;
          setLiveDraft(null);
          setSnapshot((current) => applySegmentEvent(current, segment));
        }
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
        activeSessionIdRef.current = payload.session?.session_id ?? null;
        setSnapshot((current) => applySnapshot(current, payload));
        if (payload.session?.status !== 'running') {
          setLiveDraft(null);
        }
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
  }, [pushTranscriptDebugEvent]);

  useEffect(() => {
    activeSessionIdRef.current = snapshot.session?.session_id ?? null;
  }, [snapshot.session?.session_id]);

  const handleSseError = useCallback((error: Error) => {
    console.warn('SSE error:', error);
  }, []);

  const handleSseOpen = useCallback(() => {
    console.log('SSE connected');
  }, []);

  const hasActiveModelDownload = useMemo(
    () =>
      Object.values(modelManager.downloads).some((download) =>
        ['downloading', 'verifying'].includes(download.status),
      ),
    [modelManager.downloads],
  );

  const isSessionRunning = snapshot.session?.status === 'running';

  const livePollInterval = useMemo(() => {
    if (hasActiveModelDownload || isSessionRunning) {
      return 1000;
    }
    return 4000;
  }, [hasActiveModelDownload, isSessionRunning]);

  const { status: sseStatus, connect, disconnect } = useEventSource({
    url: '/api/events',
    maxReconnectAttempts: 3,
    baseReconnectDelay: 1000,
    maxReconnectDelay: 10000,
    pollInterval: livePollInterval,
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
      const defaultCaptureSource =
        (migrated.audio.default_capture_source as FormState['captureMode'] | undefined) ||
        (migrated.audio.captureMode as FormState['captureMode'] | undefined) ||
        'microphone';
      mergeFormDefaults({
        sessionTitle: migrated.general.defaultSessionTitle || undefined,
        captureMode: defaultCaptureSource,
        deviceId: migrated.audio.defaultDeviceId || undefined,
        modelName: resolveSourceModelId(migrated, defaultCaptureSource) || undefined,
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
          capture_source: defaultCaptureSource,
          device_id: migrated.hotkey.device_id,
          default_asr_model_id: migrated.transcription.default_asr_model_id,
          microphone_asr_model_id: migrated.transcription.microphone_asr_model_id,
          system_asr_model_id: migrated.transcription.system_asr_model_id,
          finish_mode_default: migrated.hotkey.finish_mode_default,
          show_floating_window: migrated.hotkey.show_floating_window,
          floating_window_position: migrated.hotkey.floating_window_position,
          record_on_start: migrated.hotkey.record_on_start,
          stop_on_release: migrated.hotkey.stop_on_release,
          copy_to_clipboard: migrated.hotkey.copy_to_clipboard,
        } as any);
      }

      if (migrated.transcription.preload_model) {
        void preloadPreferredModel(
          resolveSourceModelId(migrated, defaultCaptureSource),
          migrated.advanced.experimentalGpuAccel ? 'auto' : 'cpu_only',
        );
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
      const normalizedCaptureSource =
        (newSettings.audio.default_capture_source as FormState['captureMode'] | undefined) ||
        (newSettings.audio.captureMode as FormState['captureMode'] | undefined) ||
        'microphone';
      const normalizedSettings = syncInheritedAsrModelIds(settings, {
        ...newSettings,
        audio: {
          ...newSettings.audio,
          captureMode: normalizedCaptureSource,
          default_capture_source: normalizedCaptureSource,
        },
      });
      // Filter out fake settings before sending to backend
      const cleanedSettings: SettingsState = {
        general: Object.fromEntries(
          Object.entries(normalizedSettings.general).filter(([key]) => !isFakeSetting('general', key))
        ) as SettingsState['general'],
        transcription: Object.fromEntries(
          Object.entries(normalizedSettings.transcription).filter(([key]) => !isFakeSetting('transcription', key))
        ) as SettingsState['transcription'],
        refiner: normalizedSettings.refiner,
        audio: Object.fromEntries(
          Object.entries(normalizedSettings.audio).filter(([key]) => !isFakeSetting('audio', key))
        ) as SettingsState['audio'],
        hotkey: Object.fromEntries(
          Object.entries(normalizedSettings.hotkey).filter(
            ([key]) => key !== 'model_name' && !isFakeSetting('hotkey', key),
          )
        ) as SettingsState['hotkey'],
        advanced: Object.fromEntries(
          Object.entries(normalizedSettings.advanced).filter(([key]) => !isFakeSetting('advanced', key))
        ) as SettingsState['advanced'],
        version: normalizedSettings.version,
      };
      cleanedSettings.audio.captureMode = normalizedCaptureSource;
      cleanedSettings.audio.default_capture_source = normalizedCaptureSource;

      await backendRequest('/api/settings', {
        method: 'POST',
        body: JSON.stringify(cleanedSettings),
      });
      const persistedSettings = sanitizeSettings({
        ...normalizedSettings,
        hotkey: cleanedSettings.hotkey,
        audio: {
          ...normalizedSettings.audio,
          captureMode: normalizedCaptureSource,
          default_capture_source: normalizedCaptureSource,
        },
      } as SettingsState);
      setSettings(persistedSettings);

      // Apply theme from settings
      setTheme((currentTheme) => {
        if (persistedSettings.general.theme !== currentTheme) {
          return persistedSettings.general.theme;
        }
        return currentTheme;
      });

      // Apply settings to form state
      mergeFormDefaults({
        sessionTitle: persistedSettings.general.defaultSessionTitle,
        captureMode: normalizedCaptureSource,
        deviceId: persistedSettings.audio.defaultDeviceId,
        modelName: resolveSourceModelId(persistedSettings, normalizedCaptureSource),
        languageMode: persistedSettings.general.defaultLanguage,
        exportRoot: persistedSettings.general.exportDirectory,
        hotkeyEnabled: persistedSettings.hotkey.enabled,
        hotkeyCombination: persistedSettings.hotkey.key_combination,
        hotkeyHoldMode: persistedSettings.hotkey.hold_mode,
        hotkeyAutoInject: persistedSettings.hotkey.auto_inject,
      });

      // Apply hotkey config to Electron main process
      const hotkeyApi = window.transcriptaDesktop.hotkey;
      if (hotkeyApi) {
        await hotkeyApi.updateConfig({
          enabled: persistedSettings.hotkey.enabled,
          key_combination: persistedSettings.hotkey.key_combination,
          hold_mode: persistedSettings.hotkey.hold_mode,
          auto_inject: persistedSettings.hotkey.auto_inject,
          language: persistedSettings.hotkey.language,
          capture_source: normalizedCaptureSource,
          device_id: persistedSettings.hotkey.device_id,
          default_asr_model_id: persistedSettings.transcription.default_asr_model_id,
          microphone_asr_model_id: persistedSettings.transcription.microphone_asr_model_id,
          system_asr_model_id: persistedSettings.transcription.system_asr_model_id,
          finish_mode_default: persistedSettings.hotkey.finish_mode_default,
          show_floating_window: persistedSettings.hotkey.show_floating_window,
          floating_window_position: persistedSettings.hotkey.floating_window_position,
          record_on_start: persistedSettings.hotkey.record_on_start,
          stop_on_release: persistedSettings.hotkey.stop_on_release,
          copy_to_clipboard: persistedSettings.hotkey.copy_to_clipboard,
        } as any);
      }

      if (persistedSettings.transcription.preload_model) {
        void preloadPreferredModel(
          resolveSourceModelId(persistedSettings, normalizedCaptureSource),
          persistedSettings.advanced.experimentalGpuAccel ? 'auto' : 'cpu_only',
        );
      }

      console.log('Settings saved successfully');
      return true;
    } catch (error) {
      console.error('Failed to save settings:', error);
      return false;
    }
  }, [mergeFormDefaults, settings]);

  const loadModelCatalog = useCallback(async () => {
    try {
      const payload = await backendRequest<ModelCatalogPayload>('/api/models/catalog');
      setModelManager((current) => applyModelCatalogPayload(current, payload));
    } catch (error) {
      console.error('Failed to load model catalog:', error);
    }
  }, []);

  const handleSidebarFieldChange = useCallback(
    <K extends keyof FormState>(key: K, value: FormState[K]) => {
      if (key === 'captureMode') {
        const nextCaptureMode = value as FormState['captureMode'];
        dirtyFieldsRef.current.add('captureMode');
        setForm((current) => ({
          ...current,
          captureMode: nextCaptureMode,
          modelName: resolveSourceModelId(settings, nextCaptureMode),
        }));
        return;
      }
      updateFormField(key, value);
    },
    [settings, updateFormField],
  );

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
      const downloadPayload = eventPayload.payload as import('./types/api').ModelDownloadState & {
        model_id?: string;
      };
      setModelManager((current) =>
        applyModelDownloadEvent(current, eventPayload.event, eventPayload.payload),
      );
      pushDebugEvent(eventPayload.event, {
        correlation_id: downloadPayload.correlation_id ?? downloadPayload.download_id ?? null,
        segment_id: downloadPayload.model_id ?? null,
        detail:
          [
            downloadPayload.status,
            downloadPayload.current_artifact ?? downloadPayload.model_id,
          ]
            .filter(Boolean)
            .join(':') || null,
        text: downloadPayload.error ?? null,
      });
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
  }, [pushDebugEvent]);

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

  async function preloadPreferredModel(modelName?: string, executionMode?: string) {
    if (!modelName) {
      return;
    }

    const normalizedExecutionMode = executionMode || 'auto';
    const preloadKey = `${modelName}:${normalizedExecutionMode}`;
    if (preloadedModelKeysRef.current.has(preloadKey)) {
      return;
    }

    preloadedModelKeysRef.current.add(preloadKey);
    setPreloadStatus({
      loading: true,
      progress: 0,
      message: `Preloading ${modelName}...`,
      model_name: modelName,
    });

    try {
      await backendRequest('/api/models/preload', {
        method: 'POST',
        body: JSON.stringify({
          model_name: modelName,
          execution_mode: normalizedExecutionMode,
        }),
      });
    } catch (error) {
      preloadedModelKeysRef.current.delete(preloadKey);
      setPreloadStatus({ loading: false, progress: 0, message: '' });
      console.warn('Background model preload failed:', error);
    }
  }

  async function loadDevices() {
    try {
      const payload = await backendRequest<{ devices: Device[] }>('/api/devices');
      setDevices(payload.devices);
      setForm((current) => {
        const eligibleDevices = getEligibleDevices(payload.devices, current.captureMode);
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
      const eligibleDevices = getEligibleDevices(devices, current.captureMode);
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
      activeSessionIdRef.current = payload.session?.session_id ?? null;
      setSnapshot((current) => applySnapshot(current, payload));
      if (payload.session?.status !== 'running') {
        setLiveDraft(null);
      }
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
      activeSessionIdRef.current = payload.session?.session_id ?? null;
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
    const resolvedModelName = resolveSourceModelId(settings, form.captureMode) || form.modelName;
    setPreloadStatus({ loading: true, progress: 0, message: 'Starting preload...' });
    try {
      await backendRequest('/api/models/preload', {
        method: 'POST',
        body: JSON.stringify({
          model_name: resolvedModelName,
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
    activeSessionIdRef.current = null;
    setLiveDraft(null);
    setTranscriptDebugEvents([]);
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    disconnect();
    try {
      const requestedDeviceId = resolveRequestedDeviceId(devices, form.captureMode, form.deviceId);
      const resolvedModelName = resolveSourceModelId(settings, form.captureMode) || form.modelName;
      const requestBody: StartSessionRequest = {
        title: form.sessionTitle.trim() || 'Study Session',
        output_root: form.exportRoot.trim() || 'sessions',
        model_name: resolvedModelName,
        language_mode: form.languageMode,
        capture_source: form.captureMode,
        live_mode: form.liveMode,
        execution_mode: form.executionMode,
        device_id: requestedDeviceId,
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
    setLiveDraft(null);
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
          onFieldChange={(key, value) => handleSidebarFieldChange(key, value)}
          onRefreshDevices={() => void loadDevices()}
          onChooseDirectory={() => void chooseDirectory()}
          onPreloadModel={() => void preloadModel()}
          onStart={() => void startSession()}
          onStop={() => void stopSession()}
          onAttachPdf={() => void attachPdf()}
          onOpenSettings={() => setShowSettings(true)}
        />
        
        {activityFeedNode}

        <MainContent
          snapshot={snapshot}
          liveLatency={liveLatency}
          liveDraft={liveDraft}
          transcriptDebugEvents={settings.advanced.debugMode ? transcriptDebugEvents : []}
          activityFeed={activityFeedNode}
        />
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
