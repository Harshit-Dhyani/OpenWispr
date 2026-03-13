import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityFeed } from './components/ActivityFeed';
import { AppSidebar } from './components/AppSidebar';
import { DictionaryPage } from './pages/DictionaryPage';
import { HomePage } from './pages/HomePage';
import { ModeCardsRow } from './components/ModeCardsRow';
import { QuickSettingsDrawer } from './components/QuickSettingsDrawer';
import { SettingsPanel } from './components/SettingsPanel';
import { MainContent } from './components/MainContent';
import { SnippetsPage } from './pages/SnippetsPage';
import { useEventSource, type EventSourceEvent } from './hooks/useEventSource';
import {
  applyModelCatalogPayload,
  applyModelDownloadEvent,
  EMPTY_MODEL_MANAGER_STATE,
} from './lib/modelRegistry';
import { AppConstants } from './lib/constants';
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
import { DEFAULT_SETTINGS, isFakeSetting } from './config/settingsSchema';
import type { SettingsState } from './config/settingsSchema';
import { sanitizeSettings } from './config/settingsMigration';
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
  HotkeyState,
  HotkeyStopResponse,
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

type AppPage = 'home' | 'microphone' | 'systemAudio' | 'dictionary' | 'snippets' | 'settings';
type QuickSettingsMode = 'dictation' | 'sessions' | null;

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
  const [dictationSnapshot, setDictationSnapshot] = useState<SnapshotPayload>(buildInitialSnapshot());
  const [statusMessage, setStatusMessage] = useState('Connecting to the local backend.');
  const [backendReady, setBackendReady] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [modelLoading, setModelLoading] = useState(false);
  const [preloadStatus, setPreloadStatus] = useState<ModelPreloadStatus>({
    loading: false,
    progress: 0,
    message: '',
    stage: 'idle',
  });
  const [activePage, setActivePage] = useState<AppPage>('home');
  const [liveLatency, setLiveLatency] = useState<number | null>(null);
  const [quickSettingsMode, setQuickSettingsMode] = useState<QuickSettingsMode>(null);
  const [settings, setSettings] = useState<SettingsState>(DEFAULT_SETTINGS);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [hardwareProfile, setHardwareProfile] = useState<SystemProfile | undefined>(undefined);
  const [modelManager, setModelManager] = useState(EMPTY_MODEL_MANAGER_STATE);
  const [liveDraft, setLiveDraft] = useState<LiveDraftState | null>(null);
  const [dictationLiveDraft, setDictationLiveDraft] = useState<LiveDraftState | null>(null);
  const [dictationCoachResult, setDictationCoachResult] = useState<HotkeyStopResponse['coach_result'] | null>(null);
  const [dictationAggregatedText, setDictationAggregatedText] = useState('');
  const [dictationPostprocessedText, setDictationPostprocessedText] = useState('');
  const [dictationPasteText, setDictationPasteText] = useState('');
  const [dictationCoachStatus, setDictationCoachStatus] = useState<HotkeyStopResponse['coach_status'] | null>(null);
  const [dictationCoachDisplaySource, setDictationCoachDisplaySource] = useState<HotkeyStopResponse['coach_display_source'] | null>(null);
  const [dictationCoachError, setDictationCoachError] = useState<string | null>(null);
  const [hotkeyState, setHotkeyState] = useState<HotkeyState | null>(null);
  const [transcriptDebugEvents, setTranscriptDebugEvents] = useState<TranscriptDebugEvent[]>([]);
  const initializedRef = useRef(false);
  const revisionRef = useRef(0);
  const pollTimerRef = useRef<number | null>(null);
  const startInFlightRef = useRef(false);
  const sseEnabledRef = useRef(false);
  const partialSegmentRef = useRef<Segment | null>(null);
  const dirtyFieldsRef = useRef<Set<keyof FormState>>(new Set());
  const loadSettingsInFlightRef = useRef(false);
  const loadDevicesInFlightRef = useRef(false);
  const preloadedModelKeysRef = useRef<Set<string>>(new Set());
  const activeSessionIdRef = useRef<string | null>(null);
  const activeDictationSessionIdRef = useRef<string | null>(null);
  const bootstrapStartedRef = useRef(false);

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

  const pushDebugEventRef = useRef(pushDebugEvent);

  useEffect(() => {
    pushDebugEventRef.current = pushDebugEvent;
  }, [pushDebugEvent]);

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
        const {
          progress,
          message,
          model_name,
          stage,
        } = event.payload as {
          progress: number;
          message: string;
          model_name?: string;
          stage?: ModelPreloadStatus['stage'] | 'complete';
        };
        const normalizedProgress = progress <= 1 ? Math.round(progress * 100) : Math.round(progress);
        const normalizedStage =
          stage === 'complete'
            ? 'ready'
            : stage ?? (normalizedProgress >= 100 ? 'ready' : 'loading');
        setPreloadStatus({
          loading: !['ready', 'failed', 'idle'].includes(normalizedStage),
          progress: normalizedStage === 'downloading' ? normalizedProgress : 0,
          message,
          model_name,
          stage: normalizedStage as ModelPreloadStatus['stage'],
        });
        break;
      }
    }
  }, [pushTranscriptDebugEvent]);

  useEffect(() => {
    activeSessionIdRef.current = snapshot.session?.session_id ?? null;
  }, [snapshot.session?.session_id]);

  const handleSseError = useCallback((error: Error) => {
    if (settings.advanced.debugMode) {
      console.warn('SSE error:', error);
    }
  }, [settings.advanced.debugMode]);

  const handleSseOpen = useCallback(() => {
    return;
  }, []);

  const hasActiveModelDownload = useMemo(
    () =>
      Object.values(modelManager.downloads).some((download) =>
        ['downloading', 'verifying'].includes(download.status),
      ),
    [modelManager.downloads],
  );

  const isSessionRunning = snapshot.session?.status === 'running';
  const shouldSubscribeToSessionEvents =
    backendReady &&
    !isStarting &&
    (activePage === 'home' || activePage === 'microphone' || activePage === 'systemAudio' || isSessionRunning);

  const livePollInterval = useMemo(() => {
    if (hasActiveModelDownload || isSessionRunning) {
      return 1000;
    }
    return 4000;
  }, [hasActiveModelDownload, isSessionRunning]);

  const { status: sseStatus, disconnect } = useEventSource({
    url: '/api/events',
    enabled: shouldSubscribeToSessionEvents,
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
      const hotkeyCaptureSource =
        (migrated.hotkey.capture_source as FormState['captureMode'] | undefined) ||
        defaultCaptureSource;
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
      const hotkeyApi = window.openwisprDesktop?.hotkey;
      if (hotkeyApi) {
        await hotkeyApi.updateConfig({
          enabled: migrated.hotkey.enabled,
          key_combination: migrated.hotkey.key_combination,
          microphone_key_combination: migrated.hotkey.microphone_key_combination,
          system_key_combination: migrated.hotkey.system_key_combination,
          hold_mode: migrated.hotkey.hold_mode,
          auto_inject: migrated.hotkey.auto_inject,
          language: migrated.hotkey.language,
          capture_source: hotkeyCaptureSource,
          device_id: migrated.hotkey.device_id,
          default_asr_model_id: migrated.transcription.default_asr_model_id,
          microphone_asr_model_id: migrated.transcription.microphone_asr_model_id,
          system_asr_model_id: migrated.transcription.system_asr_model_id,
          finish_mode_default: migrated.hotkey.finish_mode_default,
          enable_refiner_on_stop: migrated.hotkey.enable_refiner_on_stop,
          save_debug_wav: migrated.hotkey.save_debug_wav,
          mute_openwispr_audio_during_dictation:
            migrated.audio.mute_openwispr_audio_during_dictation,
          show_floating_window: migrated.hotkey.show_floating_window,
          show_floating_coach_result: migrated.coach.show_floating_coach_result,
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
      const hotkeyCaptureSource =
        (newSettings.hotkey.capture_source as FormState['captureMode'] | undefined) ||
        normalizedCaptureSource;
      const normalizedSettings = syncInheritedAsrModelIds(settings, {
        ...newSettings,
        audio: {
          ...newSettings.audio,
          captureMode: normalizedCaptureSource,
          default_capture_source: normalizedCaptureSource,
        },
        hotkey: {
          ...newSettings.hotkey,
          capture_source: hotkeyCaptureSource,
        },
      });
      const settingsWithDefaults: SettingsState = {
        ...DEFAULT_SETTINGS,
        ...normalizedSettings,
        general: { ...DEFAULT_SETTINGS.general, ...normalizedSettings.general },
        transcription: { ...DEFAULT_SETTINGS.transcription, ...normalizedSettings.transcription },
        refiner: { ...DEFAULT_SETTINGS.refiner, ...normalizedSettings.refiner },
        coach: { ...DEFAULT_SETTINGS.coach, ...normalizedSettings.coach },
        audio: { ...DEFAULT_SETTINGS.audio, ...normalizedSettings.audio },
        hotkey: { ...DEFAULT_SETTINGS.hotkey, ...normalizedSettings.hotkey },
        history: { ...DEFAULT_SETTINGS.history, ...normalizedSettings.history },
        dictionary: { ...DEFAULT_SETTINGS.dictionary, ...normalizedSettings.dictionary },
        snippets: { ...DEFAULT_SETTINGS.snippets, ...normalizedSettings.snippets },
        style: { ...DEFAULT_SETTINGS.style, ...normalizedSettings.style },
        advanced: { ...DEFAULT_SETTINGS.advanced, ...normalizedSettings.advanced },
      };
      // Filter out fake settings before sending to backend
      const cleanedSettings: SettingsState = {
        general: Object.fromEntries(
          Object.entries(settingsWithDefaults.general).filter(([key]) => !isFakeSetting('general', key))
        ) as SettingsState['general'],
        transcription: Object.fromEntries(
          Object.entries(settingsWithDefaults.transcription).filter(([key]) => !isFakeSetting('transcription', key))
        ) as SettingsState['transcription'],
        refiner: settingsWithDefaults.refiner,
        coach: settingsWithDefaults.coach,
        audio: Object.fromEntries(
          Object.entries(settingsWithDefaults.audio).filter(([key]) => !isFakeSetting('audio', key))
        ) as SettingsState['audio'],
        hotkey: Object.fromEntries(
          Object.entries(settingsWithDefaults.hotkey).filter(
            ([key]) => key !== 'model_name' && !isFakeSetting('hotkey', key),
          )
        ) as SettingsState['hotkey'],
        history: Object.fromEntries(
          Object.entries(settingsWithDefaults.history).filter(([key]) => !isFakeSetting('history', key))
        ) as SettingsState['history'],
        dictionary: Object.fromEntries(
          Object.entries(settingsWithDefaults.dictionary).filter(([key]) => !isFakeSetting('dictionary', key))
        ) as SettingsState['dictionary'],
        snippets: Object.fromEntries(
          Object.entries(settingsWithDefaults.snippets).filter(([key]) => !isFakeSetting('snippets', key))
        ) as SettingsState['snippets'],
        style: Object.fromEntries(
          Object.entries(settingsWithDefaults.style).filter(([key]) => !isFakeSetting('style', key))
        ) as SettingsState['style'],
        advanced: Object.fromEntries(
          Object.entries(settingsWithDefaults.advanced).filter(([key]) => !isFakeSetting('advanced', key))
        ) as SettingsState['advanced'],
        version: settingsWithDefaults.version,
      };
      cleanedSettings.audio.captureMode = normalizedCaptureSource;
      cleanedSettings.audio.default_capture_source = normalizedCaptureSource;

      await backendRequest('/api/settings', {
        method: 'POST',
        body: JSON.stringify(cleanedSettings),
      });
      const persistedSettings = sanitizeSettings({
        ...settingsWithDefaults,
        hotkey: cleanedSettings.hotkey,
        audio: {
          ...settingsWithDefaults.audio,
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
      const hotkeyApi = window.openwisprDesktop.hotkey;
      if (hotkeyApi) {
        const hotkeyResult = await hotkeyApi.updateConfig({
          enabled: persistedSettings.hotkey.enabled,
          key_combination: persistedSettings.hotkey.key_combination,
          microphone_key_combination: persistedSettings.hotkey.microphone_key_combination,
          system_key_combination: persistedSettings.hotkey.system_key_combination,
          hold_mode: persistedSettings.hotkey.hold_mode,
          auto_inject: persistedSettings.hotkey.auto_inject,
          language: persistedSettings.hotkey.language,
          capture_source:
            (persistedSettings.hotkey.capture_source as FormState['captureMode'] | undefined) ||
            normalizedCaptureSource,
          device_id: persistedSettings.hotkey.device_id,
          default_asr_model_id: persistedSettings.transcription.default_asr_model_id,
          microphone_asr_model_id: persistedSettings.transcription.microphone_asr_model_id,
          system_asr_model_id: persistedSettings.transcription.system_asr_model_id,
          finish_mode_default: persistedSettings.hotkey.finish_mode_default,
          enable_refiner_on_stop: persistedSettings.hotkey.enable_refiner_on_stop,
          save_debug_wav: persistedSettings.hotkey.save_debug_wav,
          mute_openwispr_audio_during_dictation:
            persistedSettings.audio.mute_openwispr_audio_during_dictation,
          show_floating_window: persistedSettings.hotkey.show_floating_window,
          show_floating_coach_result: persistedSettings.coach.show_floating_coach_result,
          floating_window_position: persistedSettings.hotkey.floating_window_position,
          record_on_start: persistedSettings.hotkey.record_on_start,
          stop_on_release: persistedSettings.hotkey.stop_on_release,
          copy_to_clipboard: persistedSettings.hotkey.copy_to_clipboard,
        } as any);
        if (!hotkeyResult?.success) {
          throw new Error(hotkeyResult?.error || 'Unable to apply hotkey settings.');
        }
      }

      if (persistedSettings.transcription.preload_model) {
        void preloadPreferredModel(
          resolveSourceModelId(persistedSettings, normalizedCaptureSource),
          persistedSettings.advanced.experimentalGpuAccel ? 'auto' : 'cpu_only',
        );
      }

      return true;
    } catch (error) {
      console.error('Failed to save settings:', error);
      setStatusMessage(error instanceof Error ? error.message : 'Unable to save settings.');
      return false;
    }
  }, [mergeFormDefaults, settings]);

  const loadModelCatalog = useCallback(async () => {
    try {
      const payload = await backendRequest<ModelCatalogPayload>('/api/models/catalog');
      setModelManager((current) =>
        applyModelCatalogPayload(current, {
          catalog: Array.isArray(payload?.catalog) ? payload.catalog : current.catalog,
          installed: Array.isArray(payload?.installed) ? payload.installed : current.installed,
          selected_asr_model_id: payload?.selected_asr_model_id ?? current.selectedAsrModelId,
          selected_refiner_model_id:
            payload?.selected_refiner_model_id ?? current.selectedRefinerModelId,
          refinement_mode: payload?.refinement_mode ?? current.refinementMode,
        } as ModelCatalogPayload),
      );
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

  const loadDevices = useCallback(async () => {
    if (loadDevicesInFlightRef.current) {
      return;
    }

    loadDevicesInFlightRef.current = true;
    try {
      const payload = await backendRequest<{ devices: Device[] }>('/api/devices');
      const nextDevices = Array.isArray(payload?.devices) ? payload.devices : [];
      setDevices(nextDevices);
      setForm((current) => {
        const eligibleDevices = getEligibleDevices(nextDevices, current.captureMode);
        const currentExists = nextDevices.some((device) => device.id === current.deviceId);
        const preferred =
          eligibleDevices[0]?.id ??
          nextDevices.find((device) => device.is_loopback)?.id ??
          nextDevices[0]?.id ??
          '';
        return {
          ...current,
          deviceId: currentExists || dirtyFieldsRef.current.has('deviceId') ? current.deviceId : preferred,
        };
      });
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : 'Unable to load devices.');
    } finally {
      loadDevicesInFlightRef.current = false;
    }
  }, []);

  const loadHotkeyConfig = useCallback(async () => {
    try {
      const hotkeyApi = window.openwisprDesktop.hotkey;
      if (!hotkeyApi) return;
      const hotkeyStatePayload = (await hotkeyApi.getState()) as HotkeyState | null | undefined;
      setHotkeyState(hotkeyStatePayload ?? null);
      const config = hotkeyStatePayload?.config;
      if (!config) {
        return;
      }
      mergeFormDefaults({
        hotkeyEnabled: config.enabled,
        hotkeyCombination:
          config.microphone_key_combination ??
          config.key_combination ??
          undefined,
        hotkeyHoldMode: config.hold_mode,
        hotkeyAutoInject: config.auto_inject,
      });
    } catch (error) {
      console.error('Failed to load hotkey config:', error);
    }
  }, [mergeFormDefaults]);

  const loadInitialSnapshot = useCallback(async () => {
    try {
      const payload = await backendRequest<SnapshotPayload>('/api/session');
      const normalizedPayload: SnapshotPayload = {
        ...buildInitialSnapshot(),
        ...payload,
        transcript: Array.isArray(payload?.transcript) ? payload.transcript : [],
        suppressed_transcript: Array.isArray(payload?.suppressed_transcript)
          ? payload.suppressed_transcript
          : [],
        formulas: Array.isArray(payload?.formulas) ? payload.formulas : [],
        needs_review: Array.isArray(payload?.needs_review) ? payload.needs_review : [],
        available_models: Array.isArray(payload?.available_models) ? payload.available_models : [],
        available_languages: Array.isArray(payload?.available_languages)
          ? payload.available_languages
          : [],
        available_live_modes: Array.isArray(payload?.available_live_modes)
          ? payload.available_live_modes
          : [],
        available_execution_modes: Array.isArray(payload?.available_execution_modes)
          ? payload.available_execution_modes
          : [],
      };
      revisionRef.current = normalizedPayload.runtime_revision;
      activeSessionIdRef.current = normalizedPayload.session?.session_id ?? null;
      setSnapshot((current) => applySnapshot(current, normalizedPayload));
      if (normalizedPayload.session?.status !== 'running') {
        setLiveDraft(null);
      }
      setModelLoading(normalizedPayload.loading ?? false);
      setBackendReady(true);
      initializedRef.current = true;
      setForm((current) => ({
        ...current,
        modelName:
          dirtyFieldsRef.current.has('modelName') ||
          normalizedPayload.available_models.includes(current.modelName) ||
          modelManager.catalog.some((entry) => entry.id === current.modelName)
            ? current.modelName
            : modelManager.selectedAsrModelId ?? normalizedPayload.available_models[0] ?? 'whisper-medium',
        languageMode:
          dirtyFieldsRef.current.has('languageMode') ||
          normalizedPayload.available_languages.includes(current.languageMode)
            ? current.languageMode
            : normalizedPayload.available_languages[0] ?? 'auto',
        liveMode:
          dirtyFieldsRef.current.has('liveMode') ||
          normalizedPayload.available_live_modes.includes(current.liveMode)
            ? current.liveMode
            : normalizedPayload.available_live_modes[0] ?? 'balanced',
        executionMode:
          dirtyFieldsRef.current.has('executionMode') ||
          normalizedPayload.available_execution_modes.includes(current.executionMode)
            ? current.executionMode
            : normalizedPayload.available_execution_modes[0] ?? 'auto',
      }));
      setStatusMessage(
        normalizedPayload.session?.status === 'running'
          ? normalizedPayload.health?.gpu_mode?.startsWith('cuda')
            ? 'Capturing and transcribing locally on GPU.'
            : normalizedPayload.health?.execution_mode === 'gpu_only'
              ? 'GPU-only mode requested but unavailable. Fix CUDA runtime.'
              : 'Capturing locally on CPU fallback. Use hi or en instead of auto for better speed.'
          : 'Ready. Configure a session and start.'
      );
    } catch (error) {
      setBackendReady(false);
      setStatusMessage(error instanceof Error ? error.message : 'Backend unavailable.');
      scheduleNextPoll(2500);
    }
  }, [modelManager.catalog, modelManager.selectedAsrModelId]);
  const availableModels = useMemo(
    () => modelManager.catalog.map((entry) => entry.id),
    [modelManager.catalog],
  );

  useEffect(() => {
    if (bootstrapStartedRef.current) {
      return;
    }
    bootstrapStartedRef.current = true;
    void loadSettings();
    void loadDevices();
    void loadInitialSnapshot();
    void loadHotkeyConfig();
    void loadHardwareProfile();
    void loadModelCatalog();
  }, [
    loadDevices,
    loadHardwareProfile,
    loadHotkeyConfig,
    loadInitialSnapshot,
    loadModelCatalog,
    loadSettings,
  ]);

  useEffect(() => {
    let disposeBackendExit: (() => void) | undefined;
    let disposeOpenSettings: (() => void) | undefined;
    let disposeSettingsUpdated: (() => void) | undefined;
    let hotkeyStateListener:
      | ((event: unknown, state: HotkeyState | null | undefined) => void)
      | undefined;
    const disposeModelDownloads = window.openwisprDesktop.models.onDownloadEvent((eventPayload) => {
      const downloadPayload = eventPayload.payload as import('./types/api').ModelDownloadState & {
        model_id?: string;
      };
      setModelManager((current) =>
        applyModelDownloadEvent(current, eventPayload.event, eventPayload.payload),
      );
      pushDebugEventRef.current(eventPayload.event, {
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
    const disposeHotkeyTranscriptEvents = window.openwisprDesktop.hotkey.onTranscriptEvent?.(
      ({ type, payload }) => {
        if (!payload || typeof payload !== 'object') {
          return;
        }
        const transcriptPayload = payload as DraftPartialPayload &
          CommitFinalPayload & {
            correlation_id?: string;
            state?: string;
            final_transcription?: string;
          };

        if (type === 'hotkey_draft_partial') {
          activeDictationSessionIdRef.current =
            transcriptPayload.session_id ?? activeDictationSessionIdRef.current;
          pushTranscriptDebugEvent(type, transcriptPayload);
          setDictationLiveDraft(buildStructuredLiveDraft(transcriptPayload));
          return;
        }

        if (type === 'hotkey_commit_final' && transcriptPayload.segment) {
          activeDictationSessionIdRef.current =
            transcriptPayload.session_id ?? activeDictationSessionIdRef.current;
          pushTranscriptDebugEvent(type, {
            session_id: transcriptPayload.session_id,
            segment_id: transcriptPayload.segment_id,
            correlation_id: transcriptPayload.correlation_id,
            text:
              transcriptPayload.segment.display_text ||
              transcriptPayload.segment.text ||
              transcriptPayload.text,
          });
          setDictationLiveDraft((current) =>
            clearLiveDraftForCommit(current, activeDictationSessionIdRef.current, transcriptPayload),
          );
          setDictationSnapshot((current) => applySegmentEvent(current, transcriptPayload.segment));
          return;
        }

        if (type === 'hotkey_status') {
          if (transcriptPayload.session_id) {
            activeDictationSessionIdRef.current = transcriptPayload.session_id;
          }
          if (transcriptPayload.state === 'processing') {
            setDictationCoachStatus((current) => (current === 'queued' ? 'running' : current));
          }
          if (transcriptPayload.state === 'idle') {
            setDictationLiveDraft(null);
          }
          return;
        }

        if (type === 'hotkey_stopped') {
          const stopPayload = payload as HotkeyStopResponse;
          setDictationLiveDraft(null);
          setHotkeyState((current) =>
            current
              ? {
                  ...current,
                  error: null,
                  session: current.session
                    ? {
                        ...current.session,
                        session_id: stopPayload.session_id || '',
                        is_recording: false,
                        status: 'idle',
                        lifecycle_state: 'idle',
                      }
                    : current.session,
                }
              : current,
          );
          setDictationCoachResult(stopPayload.coach_result ?? null);
          setDictationAggregatedText(
            stopPayload.aggregated_clean_text ||
              stopPayload.composed_text ||
              stopPayload.final_transcription ||
              '',
          );
          setDictationPostprocessedText(
            stopPayload.postprocessed_text ||
              stopPayload.refined_transcription ||
              stopPayload.final_transcription ||
              '',
          );
          setDictationPasteText(
            stopPayload.paste_text ||
              stopPayload.postprocessed_text ||
              stopPayload.aggregated_clean_text ||
              stopPayload.final_transcription ||
              '',
          );
          const resolvedCoachStatus =
            stopPayload.coach_status === 'generated' || stopPayload.coach_status === 'cache_hit'
              ? 'success'
              : stopPayload.coach_status ?? null;
          setDictationCoachStatus(resolvedCoachStatus);
          setDictationCoachDisplaySource(stopPayload.coach_display_source ?? (resolvedCoachStatus === 'fallback' ? 'fallback' : 'faithful'));
          setDictationCoachError(stopPayload.coach_error ?? null);
        }
      },
    );
    disposeBackendExit = window.openwisprDesktop.onBackendExit(() => {
      setBackendReady(false);
      setStatusMessage('Backend exited. Reconnecting…');
      disconnect();
      scheduleNextPoll(1000);
    });
    disposeOpenSettings = window.openwisprDesktop.onOpenSettings(() => {
      setActivePage('settings');
      setQuickSettingsMode(null);
    });
    disposeSettingsUpdated = window.openwisprDesktop.onSettingsUpdated?.(() => {
      void loadSettings();
      void loadDevices();
      void loadHotkeyConfig();
      void loadModelCatalog();
    });
    hotkeyStateListener = (_event, state) => {
      setHotkeyState(state ?? null);
    };
    window.openwisprDesktop.hotkey.onStateChange?.(hotkeyStateListener);
    return () => {
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current);
      }
      disposeBackendExit?.();
      disposeOpenSettings?.();
      disposeSettingsUpdated?.();
      if (hotkeyStateListener) {
        window.openwisprDesktop.hotkey.removeStateChangeListener?.(hotkeyStateListener);
      }
      disposeModelDownloads?.();
      disposeHotkeyTranscriptEvents?.();
      disconnect();
    };
  }, [disconnect, loadDevices, loadHotkeyConfig, loadModelCatalog, loadSettings]);

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

  useEffect(() => {
    if (!settings.advanced.debugMode || !dictationCoachStatus) {
      return;
    }
    console.debug('[renderer] Coach panel state', {
      coachStatus: dictationCoachStatus,
      coachDisplaySource: dictationCoachDisplaySource,
      hasResult: Boolean(dictationCoachResult),
      coachError: dictationCoachError,
      pasteTextChars: dictationPasteText.length,
    });
  }, [
    dictationCoachDisplaySource,
    dictationCoachError,
    dictationCoachResult,
    dictationCoachStatus,
    dictationPasteText.length,
    settings.advanced.debugMode,
  ]);

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

  const backendRequest = useCallback(async <T,>(path: string, options?: RequestInit): Promise<T> => {
    return window.openwisprDesktop.fetchJson(path, options) as Promise<T>;
  }, []);

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
        stage: 'preparing',
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
      setPreloadStatus({ loading: false, progress: 0, message: '', stage: 'failed' });
      console.warn('Background model preload failed:', error);
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
    const folder = await window.openwisprDesktop.chooseDirectory();
    if (folder) {
      updateFormField('exportRoot', folder);
    }
  }

  async function downloadModel(modelId: string) {
    await window.openwisprDesktop.models.download(modelId);
    setStatusMessage(`Queued download for ${modelId}.`);
    await loadModelCatalog();
  }

  async function cancelModelDownload(modelId: string) {
    await window.openwisprDesktop.models.cancel(modelId);
    setStatusMessage(`Cancelled download for ${modelId}.`);
    await loadModelCatalog();
  }

  async function removeModel(modelId: string) {
    await window.openwisprDesktop.models.remove(modelId);
    setStatusMessage(`Removed ${modelId}.`);
    await loadModelCatalog();
  }
  async function preloadModel() {
    const resolvedModelName = resolveSourceModelId(settings, form.captureMode) || form.modelName;
    setPreloadStatus({
      loading: true,
      progress: 0,
      message: 'Preparing preload...',
      stage: 'preparing',
      model_name: resolvedModelName,
    });
    try {
      const response = await backendRequest<{
        status?: 'loading' | 'ready' | 'warming' | 'error';
        model_name?: string;
        message?: string;
      }>('/api/models/preload', {
        method: 'POST',
        body: JSON.stringify({
          model_name: resolvedModelName,
          execution_mode: form.executionMode,
        }),
      });
      const nextStage: ModelPreloadStatus['stage'] =
        response.status === 'ready'
          ? 'ready'
          : response.status === 'warming'
            ? 'warming'
            : response.status === 'error'
              ? 'failed'
              : 'loading';
      setPreloadStatus({
        loading: !['ready', 'failed'].includes(nextStage),
        progress: 0,
        message: response.message || (nextStage === 'ready' ? 'Model ready.' : 'Loading model...'),
        stage: nextStage,
        model_name: response.model_name ?? resolvedModelName,
      });
    } catch (error) {
      setPreloadStatus({ loading: false, progress: 0, message: '', stage: 'failed' });
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
    const file = await window.openwisprDesktop.choosePdf();
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
  const dictationCaptureSource =
    (settings.hotkey.capture_source as FormState['captureMode'] | undefined) || 'microphone';
  const dictationDevices = useMemo(
    () => getEligibleDevices(devices, dictationCaptureSource),
    [devices, dictationCaptureSource],
  );
  const sessionDevices = useMemo(
    () => getEligibleDevices(devices, form.captureMode),
    [devices, form.captureMode],
  );
  const dictationModelId =
    resolveSourceModelId(settings, dictationCaptureSource) || settings.transcription.default_asr_model_id;
  const sessionModelId = resolveSourceModelId(settings, form.captureMode) || form.modelName;
  const dictationLanguage = settings.hotkey.language || settings.general.defaultLanguage || 'auto';
  const dictationHotkeyLabel =
    dictationCaptureSource === 'system'
      ? settings.hotkey.system_key_combination || settings.hotkey.key_combination
      : settings.hotkey.microphone_key_combination || settings.hotkey.key_combination;
  const dictationLifecycleState =
    hotkeyState?.session?.lifecycle_state ??
    (hotkeyState?.session?.is_recording ? 'recording' : 'idle');
  const isDictationRecording =
    dictationLifecycleState === 'recording' || dictationLifecycleState === 'starting';
  const isDictationTransitioning =
    dictationLifecycleState === 'starting' || dictationLifecycleState === 'stopping';
  const activeRuntimeStatus =
    dictationLifecycleState === 'starting'
      ? `Starting ${dictationCaptureSource} dictation`
      : dictationLifecycleState === 'stopping'
        ? 'Finishing dictation'
        : isDictationRecording
          ? `Hotkey ${dictationCaptureSource} recording`
          : snapshot.session?.status === 'running'
            ? `${form.captureMode === 'system' ? 'System' : 'Microphone'} session running`
            : 'Ready';
  const preloadHeadline =
    modelLoading && preloadStatus.stage === 'idle'
      ? 'Loading model'
      : preloadStatus.stage === 'downloading'
      ? `${preloadStatus.progress}% downloaded`
      : preloadStatus.stage === 'ready'
        ? 'Model ready'
        : preloadStatus.stage === 'warming'
          ? 'Warming up model'
          : preloadStatus.stage === 'loading'
            ? 'Loading model'
            : preloadStatus.stage === 'preparing'
              ? 'Preparing model'
              : preloadStatus.stage === 'failed'
                ? 'Preload failed'
                : 'Preload off';
  const persistSettingsUpdate = useCallback(
    async (updater: (current: SettingsState) => SettingsState) => {
      const nextSettings = sanitizeSettings(updater(settings));
      setSettings(nextSettings);
      await saveSettings(nextSettings);
    },
    [saveSettings, settings],
  );

  const updateDictationSetting = useCallback(
    async (field: 'capture_source' | 'device_id' | 'language' | 'finish_mode_default' | 'refinement_mode' | 'model_id', value: string) => {
      if (field === 'model_id') {
        await persistSettingsUpdate((current) => ({
          ...current,
          transcription: {
            ...current.transcription,
            [dictationCaptureSource === 'system' ? 'system_asr_model_id' : 'microphone_asr_model_id']: value,
          },
        }));
        return;
      }
      if (field === 'refinement_mode') {
        await persistSettingsUpdate((current) => ({
          ...current,
          transcription: {
            ...current.transcription,
            refinement_mode: value as SettingsState['transcription']['refinement_mode'],
          },
        }));
        return;
      }
      await persistSettingsUpdate((current) => ({
        ...current,
        hotkey: {
          ...current.hotkey,
          [field]: value,
        },
      }));
    },
    [dictationCaptureSource, persistSettingsUpdate],
  );

  const updateSessionModelSetting = useCallback(
    async (modelId: string) => {
      handleSidebarFieldChange('modelName', modelId);
      await persistSettingsUpdate((current) => ({
        ...current,
        transcription: {
          ...current.transcription,
          [form.captureMode === 'system' ? 'system_asr_model_id' : 'microphone_asr_model_id']: modelId,
        },
      }));
    },
    [form.captureMode, handleSidebarFieldChange, persistSettingsUpdate],
  );

  const startDictation = useCallback(async () => {
    setStatusMessage(`Starting ${dictationCaptureSource === 'system' ? 'system audio' : 'microphone'} dictation...`);
    try {
      setHotkeyState((current) =>
        current
          ? {
              ...current,
              error: null,
              session: {
                ...(current.session ?? {
                  session_id: '',
                  last_activated_at: null,
                  total_activations: 0,
                  current_text: '',
                  duration_ms: 0,
                }),
                is_recording: true,
                status: 'processing',
                lifecycle_state: 'starting',
                capture_source: dictationCaptureSource,
              },
            }
          : current,
      );
      setDictationSnapshot(buildInitialSnapshot());
      setDictationLiveDraft(null);
      setDictationCoachResult(null);
      setDictationAggregatedText('');
      setDictationPostprocessedText('');
      setDictationPasteText('');
      setDictationCoachStatus(null);
      setDictationCoachDisplaySource(null);
      setDictationCoachError(null);
      activeDictationSessionIdRef.current = null;
      await window.openwisprDesktop.hotkey.start?.(dictationCaptureSource);
    } catch (error) {
      setHotkeyState((current) =>
        current
          ? {
              ...current,
              session: current.session
                ? {
                    ...current.session,
                    is_recording: false,
                    status: 'idle',
                    lifecycle_state: 'idle',
                  }
                : current.session,
            }
          : current,
      );
      setStatusMessage(error instanceof Error ? error.message : 'Unable to start dictation.');
    }
  }, [dictationCaptureSource]);

  const stopDictation = useCallback(async () => {
    setStatusMessage('Stopping dictation...');
    try {
      setHotkeyState((current) =>
        current
          ? {
              ...current,
              session: current.session
                ? {
                    ...current.session,
                    is_recording: false,
                    status: 'processing',
                    lifecycle_state: 'stopping',
                  }
                : current.session,
            }
          : current,
      );
      if (settings.coach.coach_enabled) {
        setDictationCoachStatus('queued');
        setDictationCoachDisplaySource('faithful');
        setDictationCoachError(null);
      } else {
        setDictationCoachStatus('disabled');
        setDictationCoachDisplaySource('faithful');
      }
      await window.openwisprDesktop.hotkey.stop?.();
    } catch (error) {
      setHotkeyState((current) =>
        current
          ? {
              ...current,
              session: current.session
                ? {
                    ...current.session,
                    is_recording: true,
                    status: 'listening',
                    lifecycle_state: 'recording',
                  }
                : current.session,
            }
          : current,
      );
      setStatusMessage(error instanceof Error ? error.message : 'Unable to stop dictation.');
      setDictationCoachStatus('failed');
      setDictationCoachDisplaySource('faithful');
      setDictationCoachError(error instanceof Error ? error.message : 'stop_failed');
    }
  }, [settings.coach.coach_enabled]);

  const homeView = (
    <HomePage
      request={backendRequest}
      onOpenSettings={() => setActivePage('settings')}
      onStatus={setStatusMessage}
      defaultRangeDays={settings.history.default_analytics_range_days}
      allowRetry={settings.history.allow_retry}
      persistAudio={settings.history.persist_audio}
    />
  );
  const dictationView = (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="border-b-2 border-lawn-border bg-lawn-panel p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl border-2 border-lawn-border bg-lawn-bg/60 p-4 shadow-brutal-sm">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-lawn-muted">
              Dictation workspace
            </p>
            <h2 className="mt-2 font-display text-4xl uppercase tracking-tight text-lawn-border">
              Talk, clean up, paste
            </h2>
            <p className="mt-3 text-sm leading-6 text-lawn-muted">
              Mic and hotkey dictation stay lightweight here. Use the quick drawer for language, finish action,
              and source-aware model choices without opening the full settings panel.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => {
                if (isDictationTransitioning) {
                  return;
                }
                void (isDictationRecording ? stopDictation() : startDictation());
              }}
              disabled={isDictationTransitioning}
              className="border-2 border-lawn-accent bg-lawn-accent px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-bg"
            >
              {dictationLifecycleState === 'starting'
                ? 'Starting…'
                : dictationLifecycleState === 'stopping'
                  ? 'Stopping…'
                  : isDictationRecording
                    ? 'Stop Dictation'
                    : 'Start Dictation'}
            </button>
            <button
              type="button"
              onClick={() => setQuickSettingsMode('dictation')}
              className="border-2 border-lawn-border bg-lawn-bg px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-border"
            >
              Quick settings
            </button>
            <button
              type="button"
              onClick={() => setActivePage('settings')}
              className="border-2 border-lawn-border bg-lawn-dark px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-bg"
            >
              Open settings
            </button>
          </div>
        </div>
        <div className="mt-4 border-2 border-lawn-border bg-lawn-bg p-3">
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            <div className="border border-lawn-border bg-lawn-panel px-3 py-2">
              <span className="text-[9px] font-black uppercase tracking-[0.14em] text-lawn-muted">Language</span>
              <p className="mt-1 text-xs font-bold uppercase text-lawn-border">{dictationLanguage || 'auto'}</p>
            </div>
            <div className="border border-lawn-border bg-lawn-panel px-3 py-2">
              <span className="text-[9px] font-black uppercase tracking-[0.14em] text-lawn-muted">Model</span>
              <p className="mt-1 text-xs font-bold text-lawn-border">{dictationModelId}</p>
            </div>
            <div className="border border-lawn-border bg-lawn-panel px-3 py-2">
              <span className="text-[9px] font-black uppercase tracking-[0.14em] text-lawn-muted">Finish</span>
              <p className="mt-1 text-xs font-bold uppercase text-lawn-border">
                {settings.hotkey.finish_mode_default.replace(/_/g, ' ')}
              </p>
            </div>
            <div className="border border-lawn-border bg-lawn-panel px-3 py-2">
              <span className="text-[9px] font-black uppercase tracking-[0.14em] text-lawn-muted">Device</span>
              <p className="mt-1 text-xs font-bold text-lawn-border">
                {dictationDevices.find((device) => device.id === settings.hotkey.device_id)?.name ||
                  dictationDevices[0]?.name ||
                  'Default device'}
              </p>
            </div>
            <div className="border border-lawn-border bg-lawn-panel px-3 py-2">
              <span className="text-[9px] font-black uppercase tracking-[0.14em] text-lawn-muted">Runtime</span>
              <p className="mt-1 text-xs font-bold text-lawn-border">{activeRuntimeStatus}</p>
            </div>
            <div className="border border-lawn-border bg-lawn-panel px-3 py-2">
              <span className="text-[9px] font-black uppercase tracking-[0.14em] text-lawn-muted">Refiner</span>
              <p className="mt-1 text-xs font-bold uppercase text-lawn-border">
                {settings.hotkey.enable_refiner_on_stop ? 'Enabled' : 'Disabled'}
              </p>
            </div>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <span className="border border-lawn-border px-2 py-1 text-[10px] font-black uppercase text-lawn-border">
              {connectionStatus}
            </span>
            <span className="border border-lawn-border px-2 py-1 text-[10px] font-black uppercase text-lawn-border">
              {gpuStatus}
            </span>
            <span className="border border-lawn-border px-2 py-1 text-[10px] font-black uppercase text-lawn-border">
              {dictationHotkeyLabel || 'No hotkey set'}
            </span>
          </div>
        </div>
      </div>
      <div className="grid min-h-0 flex-1 gap-4 p-4 2xl:grid-cols-[minmax(0,1.1fr)_340px]">
        <div className="min-h-0 overflow-hidden">
          <MainContent
            scope="dictation"
            snapshot={dictationSnapshot}
            liveLatency={liveLatency}
            liveDraft={dictationLiveDraft}
            transcriptDebugEvents={settings.advanced.debugMode ? transcriptDebugEvents : []}
            coachResult={dictationCoachResult ?? null}
            coachStatus={dictationCoachStatus ?? null}
            coachDisplaySource={dictationCoachDisplaySource ?? null}
            coachError={dictationCoachError}
            originalText={dictationAggregatedText}
            pasteText={dictationPasteText || dictationPostprocessedText}
            showCoachDiff={settings.coach.show_diff_view}
            workspaceLabel="Dictation"
            workspaceTitle="Mic / hotkey timeline"
            workspaceDescription="Quick dictation, low-latency feedback, and one shared timeline for recent spoken text."
          />
        </div>
        <div className="min-h-0 overflow-hidden">
          <div className="h-full min-h-0 overflow-hidden">
            <ActivityFeed
              session={dictationSnapshot.session}
              transcript={dictationSnapshot.transcript}
              health={dictationSnapshot.health}
              variant="sidebar"
            />
          </div>
        </div>
      </div>
    </div>
  );

  const sessionsView = (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="border-b-2 border-lawn-border bg-lawn-panel p-4">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_auto]">
          <div className="space-y-4">
            <div className="border-2 border-lawn-border bg-lawn-bg/60 p-4 shadow-brutal-sm">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-lawn-muted">
                Session workspace
              </p>
              <h2 className="mt-2 font-display text-4xl uppercase tracking-tight text-lawn-border">
                Long-form transcription
              </h2>
              <p className="mt-3 text-sm leading-6 text-lawn-muted">
                System audio is the default here. Use the session controls for meetings, videos, exports, and review.
              </p>
            </div>
            <ModeCardsRow
              cards={[
                {
                  title: 'Session Workspace',
                  description: `${form.sessionTitle || 'Untitled session'} · ${snapshot.session?.status ?? 'ready'}`,
                  controls: (
                    <input
                      value={form.sessionTitle}
                      onChange={(event) => handleSidebarFieldChange('sessionTitle', event.target.value)}
                      className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
                    />
                  ),
                },
                {
                  title: 'Long-form Transcription',
                  description: `${form.captureMode === 'system' ? 'System audio' : 'Microphone'} · ${sessionModelId}`,
                  controls: (
                    <div className="grid gap-2 sm:grid-cols-2">
                      <select
                        value={form.captureMode}
                        onChange={(event) => handleSidebarFieldChange('captureMode', event.target.value as FormState['captureMode'])}
                        className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
                      >
                        <option value="system">System Audio</option>
                        <option value="microphone">Microphone</option>
                      </select>
                      <select
                        value={form.deviceId}
                        onChange={(event) => handleSidebarFieldChange('deviceId', event.target.value)}
                        className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
                      >
                        {sessionDevices.map((device) => (
                          <option key={device.id} value={device.id}>
                            {device.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ),
                },
                {
                  title: 'Session Export + Notes',
                  description: `${form.exportRoot || 'sessions'} · PDF context and exports stay attached to this session`,
                  controls: (
                    <div className="grid gap-2 sm:grid-cols-2">
                      <select
                        value={form.languageMode}
                        onChange={(event) => handleSidebarFieldChange('languageMode', event.target.value)}
                        className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
                      >
                        {snapshot.available_languages.map((language) => (
                          <option key={language} value={language}>
                            {language}
                          </option>
                        ))}
                      </select>
                      <div className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border">
                        {form.exportRoot || 'sessions'}
                      </div>
                    </div>
                  ),
                },
              ]}
            />
          </div>
          <div className="flex flex-wrap gap-3 xl:flex-col xl:items-stretch">
            <button
              type="button"
              onClick={() => void (snapshot.session?.status === 'running' ? stopSession() : startSession())}
              disabled={busy}
              className="border-2 border-lawn-accent bg-lawn-accent px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-bg disabled:cursor-not-allowed disabled:opacity-60"
            >
              {snapshot.session?.status === 'running' ? 'Stop Session' : 'Start Session'}
            </button>
            <button
              type="button"
              onClick={() => setQuickSettingsMode('sessions')}
              className="border-2 border-lawn-border bg-lawn-bg px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-border"
            >
              Quick settings
            </button>
            <button
              type="button"
              onClick={() => void preloadModel()}
              className="border-2 border-lawn-border bg-lawn-dark px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-bg"
            >
              {preloadStatus.loading ? preloadHeadline : 'Prepare model'}
            </button>
            <button
              type="button"
              onClick={() => void attachPdf()}
              className="border-2 border-lawn-border bg-lawn-bg px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-border"
            >
              Attach PDF context
            </button>
          </div>
        </div>
      </div>
      <div className="min-h-0 flex-1 p-4">
        <MainContent
          scope="session"
          snapshot={snapshot}
          liveLatency={liveLatency}
          liveDraft={liveDraft}
          transcriptDebugEvents={settings.advanced.debugMode ? transcriptDebugEvents : []}
          workspaceLabel="Sessions"
          workspaceTitle={form.sessionTitle || 'System Audio Session'}
          workspaceDescription={`Source: ${form.captureMode === 'system' ? 'system audio' : 'microphone'} · Model: ${sessionModelId} · Execution: ${form.executionMode}`}
        />
      </div>
    </div>
  );

  const settingsView = (
    <div className="flex h-full min-h-0 flex-col p-4">
      <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden border-2 border-lawn-border bg-lawn-panel shadow-brutal">
        <SettingsPanel
          inline
          isOpen
          onClose={() => setActivePage('home')}
          initialSettings={settings}
          onSettingsChange={async (newSettings) => {
            await saveSettings(newSettings);
          }}
          onSettingsReset={async () => {
            await saveSettings(DEFAULT_SETTINGS);
          }}
          hardwareProfile={hardwareProfile}
          availableModels={availableModels}
          modelManager={modelManager}
          onDownloadModel={async (modelId) => {
            await downloadModel(modelId);
          }}
          onCancelModelDownload={async (modelId) => {
            await cancelModelDownload(modelId);
          }}
          onRemoveModel={async (modelId) => {
            await removeModel(modelId);
          }}
          availableLanguages={snapshot.available_languages}
          audioDevices={devices}
          request={backendRequest}
        />
      </div>
    </div>
  );
  const microphoneView = dictationView;
  const systemAudioView = sessionsView;

  const dictionaryView = (
    <DictionaryPage
      request={backendRequest}
      enabled={settings.dictionary.dictionary_enabled}
    />
  );

  const snippetsView = (
    <SnippetsPage
      request={backendRequest}
      enabled={settings.snippets.snippets_enabled}
    />
  );

  const quickSettingsDrawer =
    quickSettingsMode === 'dictation' ? (
      <QuickSettingsDrawer
        open
        title="Dictation Quick Settings"
        description="Only the everyday controls for microphone or hotkey dictation live here."
        onClose={() => setQuickSettingsMode(null)}
      >
        <div className="space-y-4">
          <label className="block space-y-2">
            <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Source</span>
            <select
              value={dictationCaptureSource}
              onChange={(event) => void updateDictationSetting('capture_source', event.target.value)}
              className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
            >
              <option value="microphone">Microphone</option>
              <option value="system">System Audio</option>
            </select>
          </label>
          <label className="block space-y-2">
            <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Device</span>
            <select
              value={settings.hotkey.device_id || dictationDevices[0]?.id || ''}
              onChange={(event) => void updateDictationSetting('device_id', event.target.value)}
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
              onChange={(event) => void updateDictationSetting('language', event.target.value)}
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
              onChange={(event) => void updateDictationSetting('model_id', event.target.value)}
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
              value={settings.hotkey.finish_mode_default}
              onChange={(event) => void updateDictationSetting('finish_mode_default', event.target.value)}
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
              value={settings.transcription.refinement_mode}
              onChange={(event) => void updateDictationSetting('refinement_mode', event.target.value)}
              className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
            >
              <option value="off">Off</option>
              <option value="strict">Strict</option>
              <option value="polished">Polished</option>
            </select>
          </label>
        </div>
      </QuickSettingsDrawer>
    ) : quickSettingsMode === 'sessions' ? (
      <QuickSettingsDrawer
        open
        title="Session Quick Settings"
        description="Use the essentials here. Deeper tuning stays in the Settings page."
        onClose={() => setQuickSettingsMode(null)}
      >
        <div className="space-y-4">
          <label className="block space-y-2">
            <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Session title</span>
            <input
              value={form.sessionTitle}
              onChange={(event) => handleSidebarFieldChange('sessionTitle', event.target.value)}
              className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
            />
          </label>
          <label className="block space-y-2">
            <span className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Source</span>
            <select
              value={form.captureMode}
              onChange={(event) => handleSidebarFieldChange('captureMode', event.target.value as FormState['captureMode'])}
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
              onChange={(event) => handleSidebarFieldChange('deviceId', event.target.value)}
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
              onChange={(event) => void updateSessionModelSetting(event.target.value)}
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
              onChange={(event) => handleSidebarFieldChange('liveMode', event.target.value)}
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
              onChange={(event) => handleSidebarFieldChange('executionMode', event.target.value)}
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
                onChange={(event) => handleSidebarFieldChange('exportRoot', event.target.value)}
                className="min-w-0 flex-1 border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
              />
              <button
                type="button"
                onClick={() => void chooseDirectory()}
                className="border-2 border-lawn-border bg-lawn-dark px-3 py-2 text-[10px] font-black uppercase tracking-[0.14em] text-lawn-bg"
              >
                Browse
              </button>
            </div>
          </label>
          <button
            type="button"
            onClick={() => void attachPdf()}
            className="w-full border-2 border-lawn-accent bg-lawn-accent px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-bg"
          >
            Attach PDF context
          </button>
        </div>
      </QuickSettingsDrawer>
    ) : null;

  return (
    <div className="h-screen w-screen overflow-hidden bg-lawn-bg font-mono text-lawn-border transition-colors duration-300 selection:bg-lawn-accent selection:text-lawn-bg">
      <div className="flex h-full min-h-0 flex-col overflow-hidden xl:flex-row">
        <AppSidebar
          activePage={activePage}
          onNavigate={(page) => {
            setActivePage(page);
            setQuickSettingsMode(null);
          }}
          onRefreshDevices={() => {
            void loadDevices();
          }}
          appName={AppConstants.APP_NAME}
          statusMessage={statusMessage}
          connectionStatus={connectionStatus}
          gpuStatus={gpuStatus}
          sessionStatus={activeRuntimeStatus}
        />
        <div className="min-h-0 flex-1 overflow-hidden">
          {activePage === 'home'
            ? homeView
            : activePage === 'microphone'
              ? microphoneView
              : activePage === 'systemAudio'
              ? systemAudioView
            : activePage === 'dictionary'
              ? dictionaryView
              : activePage === 'snippets'
                ? snippetsView
                : settingsView}
        </div>
      </div>
      {quickSettingsDrawer}
    </div>
  );
}

export default App;








