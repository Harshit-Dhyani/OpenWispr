/**
 * useSettingsSync Hook
 *
 * A specialized hook for settings synchronization with optimistic updates,
 * debounced saves, and granular control over specific settings.
 */

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { SettingsState } from '../lib/settingsSchema';
import type { SyncStatus, SettingsChangeEvent, ConflictResolution } from '../lib/settingsApi';
import {
  loadSettings,
  saveSettings,
  saveSettingsCategory,
  resetSettings,
  createSettingsSyncConnection,
  queuePendingChange,
  getPendingChanges,
  removePendingChange,
  clearPendingChanges,
  incrementRetryCount,
  detectConflicts,
  resolveConflicts,
  isApiReachable,
  type SettingsSyncResponse,
  type PendingChange,
} from '../lib/settingsApi';
import { DEFAULT_SETTINGS, validateSettings } from '../lib/settingsSchema';

// ============================================
// Debounce Utility
// ============================================

function debounce(
  fn: (newSettings: SettingsState, category?: keyof SettingsState) => Promise<void>,
  delay: number
): (newSettings: SettingsState, category?: keyof SettingsState) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return (newSettings: SettingsState, category?: keyof SettingsState) => {
    if (timeoutId !== null) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      void fn(newSettings, category);
      timeoutId = null;
    }, delay);
  };
}

// ============================================
// Types
// ============================================

export interface UseSettingsSyncOptions {
  /** Debounce delay for saves in milliseconds (default: 100) */
  debounceMs?: number;
  /** Enable real-time sync via WebSocket/SSE (default: true) */
  enableRealtimeSync?: boolean;
  /** Auto-load settings on mount (default: true) */
  autoLoad?: boolean;
  /** Callback when settings change remotely */
  onRemoteChange?: (event: SettingsChangeEvent) => void;
  /** Callback when sync status changes */
  onStatusChange?: (status: SyncStatus) => void;
  /** Callback for errors */
  onError?: (error: Error) => void;
  /** Callback when conflicts are detected */
  onConflict?: (conflicts: Array<{ path: string; local: unknown; remote: unknown }>) => void;
}

export interface UseSettingsSyncReturn {
  /** Current settings state */
  settings: SettingsState;
  /** Current sync status */
  syncStatus: SyncStatus;
  /** Whether settings are currently loading */
  isLoading: boolean;
  /** Whether initial load is complete */
  isInitialized: boolean;
  /** Current error, if any */
  error: Error | null;
  /** Server revision number for conflict detection */
  revision: number;
  /** Pending changes queued for sync */
  pendingChanges: PendingChange[];
  /** Active conflicts requiring resolution */
  conflicts: Array<{ path: string; local: unknown; remote: unknown }>;

  // Actions
  /** Update a single setting value */
  updateSetting: <K extends keyof SettingsState>(
    category: K,
    key: keyof SettingsState[K],
    value: SettingsState[K][typeof key]
  ) => void;
  /** Update multiple settings in a category */
  updateCategory: <K extends keyof SettingsState>(
    category: K,
    data: Partial<SettingsState[K]>
  ) => Promise<void>;
  /** Replace entire settings object */
  setSettings: (settings: SettingsState) => void;
  /** Reset a category or all settings to defaults */
  reset: (category?: keyof SettingsState) => Promise<void>;
  /** Resolve conflicts with a strategy */
  resolveConflict: (strategy: ConflictResolution) => void;
  /** Load settings from server */
  load: () => Promise<void>;
  /** Force sync pending changes */
  sync: () => Promise<void>;
  /** Clear all pending changes */
  clearPending: () => void;

  // Validation
  /** Validate current settings */
  validate: () => { valid: boolean; errors?: string[] };
  /** Get a specific setting value */
  get: <K extends keyof SettingsState>(category: K, key: keyof SettingsState[K]) => SettingsState[K][typeof key];
}

// ============================================
// Subscribable Store for External Sync
// ============================================

type SettingsListener = (settings: SettingsState) => void;

const settingsStore = {
  settings: DEFAULT_SETTINGS,
  listeners: new Set<SettingsListener>(),

  subscribe(listener: SettingsListener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  },

  notify(settings: SettingsState) {
    this.settings = settings;
    this.listeners.forEach(listener => listener(settings));
  },

  getSnapshot() {
    return this.settings;
  },
};

// ============================================
// Hook Implementation
// ============================================

export function useSettingsSync(options: UseSettingsSyncOptions = {}): UseSettingsSyncReturn {
  const {
    debounceMs = 100,
    enableRealtimeSync = true,
    autoLoad = true,
    onRemoteChange,
    onStatusChange,
    onError,
    onConflict,
  } = options;

  // State
  const [settings, setSettingsState] = useState<SettingsState>(DEFAULT_SETTINGS);
  const [syncStatus, setSyncStatus] = useState<SyncStatus>('syncing');
  const [isLoading, setIsLoading] = useState(true);
  const [isInitialized, setIsInitialized] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [revision, setRevision] = useState(0);
  const [pendingChanges, setPendingChanges] = useState<PendingChange[]>([]);
  const [conflicts, setConflicts] = useState<Array<{ path: string; local: unknown; remote: unknown }>>([]);

  // Refs
  const lastSyncedSettings = useRef<SettingsState>(DEFAULT_SETTINGS);
  const pendingRemoteSettings = useRef<SettingsState | null>(null);
  const isProcessingRemoteChange = useRef(false);
  const syncConnectionRef = useRef<ReturnType<typeof createSettingsSyncConnection> | null>(null);
  const saveQueueRef = useRef<Promise<unknown>>(Promise.resolve());

  // Sync with external store
  const settingsFromStore = useSyncExternalStore(
    (callback) => settingsStore.subscribe(callback),
    () => settingsStore.getSnapshot(),
    () => DEFAULT_SETTINGS
  );

  // Update local state when store changes (from other components/hooks)
  useEffect(() => {
    if (settingsFromStore !== settings) {
      setSettingsState(settingsFromStore);
    }
  }, [settingsFromStore, settings]);

  // ============================================
  // Load Settings
  // ============================================

  const load = useCallback(async () => {
    try {
      setIsLoading(true);
      setSyncStatus('syncing');
      setError(null);

      const loadedSettings = await loadSettings();
      const validation = validateSettings(loadedSettings);

      if (validation.success) {
        setSettingsState(validation.data);
        lastSyncedSettings.current = validation.data;
        settingsStore.notify(validation.data);
        setIsInitialized(true);
        setSyncStatus('synced');

        // Update pending changes
        setPendingChanges(getPendingChanges());
      } else {
        throw new Error(`Settings validation failed: ${validation.errors.message}`);
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      setSyncStatus('error');
      onError?.(error);
    } finally {
      setIsLoading(false);
    }
  }, [onError]);

  // ============================================
  // Debounced Save
  // ============================================

  const debouncedSave = useRef(
    debounce(async (newSettings: SettingsState, category?: keyof SettingsState) => {
      try {
        setSyncStatus('syncing');
        setError(null);

        const isOnline = await isApiReachable();

        if (!isOnline) {
          // Queue for later
          if (category) {
            queuePendingChange({
              category,
              path: category,
              value: newSettings[category],
            });
            setPendingChanges(getPendingChanges());
          }
          setSyncStatus('offline');
          return;
        }

        let response: SettingsSyncResponse;

        if (category) {
          response = await saveSettingsCategory(category, newSettings[category], { revision });
        } else {
          response = await saveSettings(newSettings, { revision });
        }

        if (response.success) {
          lastSyncedSettings.current = newSettings;
          if (response.revision !== undefined) {
            setRevision(response.revision);
          }
          setSyncStatus('synced');
        } else {
          throw new Error(response.message || 'Failed to save settings');
        }
      } catch (err) {
        const error = err instanceof Error ? err : new Error(String(err));
        setError(error);
        setSyncStatus('error');
        onError?.(error);
      }
    }, debounceMs)
  ).current;

  // ============================================
  // Update Functions
  // ============================================

  const updateSetting = useCallback(<K extends keyof SettingsState>(
    category: K,
    key: keyof SettingsState[K],
    value: SettingsState[K][typeof key]
  ) => {
    if (isProcessingRemoteChange.current) {
      return;
    }

    setSettingsState(prev => {
      const newSettings = {
        ...prev,
        [category]: {
          ...(prev[category] as Record<string, unknown>),
          [key]: value,
        },
      } as SettingsState;

      settingsStore.notify(newSettings);
      debouncedSave(newSettings, category);
      return newSettings;
    });
  }, [debouncedSave]);

  const updateCategory = useCallback(async <K extends keyof SettingsState>(
    category: K,
    data: Partial<SettingsState[K]>
  ) => {
    return new Promise<void>((resolve, reject) => {
      setSettingsState(prev => {
        const newSettings = {
          ...prev,
          [category]: {
            ...(prev[category] as Record<string, unknown>),
            ...data,
          },
        } as SettingsState;

        settingsStore.notify(newSettings);

        // Chain save to queue
        saveQueueRef.current = saveQueueRef.current
          .then(() => debouncedSave(newSettings, category))
          .then(() => resolve())
          .catch(reject);

        return newSettings;
      });
    });
  }, [debouncedSave]);

  const setSettings = useCallback((newSettings: SettingsState) => {
    const validation = validateSettings(newSettings);
    if (!validation.success) {
      const error = new Error(`Invalid settings: ${validation.errors.message}`);
      setError(error);
      onError?.(error);
      return;
    }

    setSettingsState(newSettings);
    settingsStore.notify(newSettings);
    debouncedSave(newSettings);
  }, [debouncedSave, onError]);

  // ============================================
  // Reset Functions
  // ============================================

  const reset = useCallback(async (category?: keyof SettingsState) => {
    try {
      setSyncStatus('syncing');
      const response = await resetSettings(category);

      if (response.success && response.data) {
        setSettingsState(response.data);
        lastSyncedSettings.current = response.data;
        settingsStore.notify(response.data);
        if (response.revision !== undefined) {
          setRevision(response.revision);
        }
        setSyncStatus('synced');
      } else {
        throw new Error(response.message || 'Failed to reset settings');
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      setSyncStatus('error');
      onError?.(error);
      throw error;
    }
  }, [onError]);

  // ============================================
  // Conflict Resolution
  // ============================================

  const resolveConflict = useCallback((strategy: ConflictResolution) => {
    if (!pendingRemoteSettings.current) {
      return;
    }

    const resolved = resolveConflicts(settings, pendingRemoteSettings.current, strategy);
    setSettingsState(resolved);
    lastSyncedSettings.current = resolved;
    settingsStore.notify(resolved);
    setConflicts([]);
    pendingRemoteSettings.current = null;
    setSyncStatus('synced');

    // Persist resolved settings
    debouncedSave(resolved);
  }, [settings, debouncedSave]);

  // ============================================
  // Remote Change Handling
  // ============================================

  const handleRemoteChange = useCallback((event: SettingsChangeEvent) => {
    onRemoteChange?.(event);

    if (event.source === 'ui') {
      return;
    }

    isProcessingRemoteChange.current = true;

    try {
      switch (event.type) {
        case 'settings-changed':
          if (event.changes) {
            const newSettings = { ...settings, ...event.changes };
            const detectedConflicts = detectConflicts(
              settings,
              newSettings,
              lastSyncedSettings.current
            );

            if (detectedConflicts.length > 0) {
              setConflicts(detectedConflicts);
              pendingRemoteSettings.current = newSettings;
              setSyncStatus('conflict');
              onConflict?.(detectedConflicts);
            } else {
              setSettingsState(newSettings);
              lastSyncedSettings.current = newSettings;
              settingsStore.notify(newSettings);
              if (event.revision !== undefined) {
                setRevision(event.revision);
              }
              setSyncStatus('synced');
            }
          }
          break;

        case 'settings-reset':
        case 'settings-imported':
          if (event.changes) {
            setSettingsState(event.changes as SettingsState);
            lastSyncedSettings.current = event.changes as SettingsState;
            settingsStore.notify(event.changes as SettingsState);
            setSyncStatus('synced');
          }
          break;
      }
    } finally {
      setTimeout(() => {
        isProcessingRemoteChange.current = false;
      }, 50);
    }
  }, [settings, onRemoteChange, onConflict]);

  // ============================================
  // Real-time Sync Connection
  // ============================================

  useEffect(() => {
    if (!enableRealtimeSync || !isInitialized) {
      return;
    }

    syncConnectionRef.current = createSettingsSyncConnection({
      onError: (error) => {
        setSyncStatus('error');
        onError?.(error);
      },
      reconnect: true,
    });

    const unsubscribeEvent = syncConnectionRef.current.subscribe(handleRemoteChange);
    const unsubscribeStatus = syncConnectionRef.current.onStatusChange((status) => {
      setSyncStatus(status);
      onStatusChange?.(status);
    });

    return () => {
      unsubscribeEvent();
      unsubscribeStatus();
      syncConnectionRef.current?.disconnect();
      syncConnectionRef.current = null;
    };
  }, [enableRealtimeSync, isInitialized, handleRemoteChange, onStatusChange, onError]);

  // ============================================
  // Offline Sync
  // ============================================

  const sync = useCallback(async () => {
    const pending = getPendingChanges();
    if (pending.length === 0) {
      return;
    }

    const isOnline = await isApiReachable();
    if (!isOnline) {
      setSyncStatus('offline');
      return;
    }

    setSyncStatus('syncing');

    for (const change of pending) {
      try {
        const response = await saveSettingsCategory(
          change.category,
          change.value as SettingsState[typeof change.category],
          { revision }
        );

        if (response.success) {
          removePendingChange(change.id);
        } else {
          incrementRetryCount(change.id);
        }
      } catch {
        incrementRetryCount(change.id);
      }
    }

    const remaining = getPendingChanges();
    setPendingChanges(remaining);
    setSyncStatus(remaining.length === 0 ? 'synced' : 'error');
  }, [revision]);

  const clearPending = useCallback(() => {
    clearPendingChanges();
    setPendingChanges([]);
  }, []);

  // ============================================
  // Auto-load on mount
  // ============================================

  useEffect(() => {
    if (autoLoad) {
      load();
    }
  }, [autoLoad, load]);

  // ============================================
  // Utility Functions
  // ============================================

  const validate = useCallback(() => {
    const result = validateSettings(settings);
    if (result.success) {
      return { valid: true };
    }
    return {
      valid: false,
      errors: result.errors.issues.map((e) => `${e.path.join('.')}: ${e.message}`),
    };
  }, [settings]);

  const get = useCallback(<K extends keyof SettingsState>(
    category: K,
    key: keyof SettingsState[K]
  ): SettingsState[K][typeof key] => {
    return settings[category][key];
  }, [settings]);

  // ============================================
  // Return Value
  // ============================================

  return {
    settings,
    syncStatus,
    isLoading,
    isInitialized,
    error,
    revision,
    pendingChanges,
    conflicts,
    updateSetting,
    updateCategory,
    setSettings,
    reset,
    resolveConflict,
    load,
    sync,
    clearPending,
    validate,
    get,
  };
}

// ============================================
// Specialized Hooks for Common Use Cases
// ============================================

/**
 * Hook for accessing a single category of settings
 */
export function useSettingsCategory<K extends keyof SettingsState>(category: K) {
  const { settings, updateCategory, get } = useSettingsSync();

  return {
    categorySettings: settings[category],
    update: (data: Partial<SettingsState[K]>) => updateCategory(category, data),
    get: <T extends keyof SettingsState[K]>(key: T) => get(category, key) as SettingsState[K][T],
  };
}

/**
 * Hook for accessing a single setting value
 */
export function useSetting<K extends keyof SettingsState, T extends keyof SettingsState[K]>(
  category: K,
  key: T
) {
  const { settings, updateSetting } = useSettingsSync();

  return {
    value: settings[category][key] as SettingsState[K][T],
    setValue: (value: SettingsState[K][T]) => updateSetting(category, key, value),
  };
}

/**
 * Hook for sync status only (lightweight)
 */
export function useSyncStatus() {
  const { syncStatus, isLoading, isInitialized, error, pendingChanges } = useSettingsSync();

  return {
    syncStatus,
    isLoading,
    isInitialized,
    error,
    pendingChanges,
    isOnline: syncStatus === 'synced' || syncStatus === 'syncing',
    hasConflicts: syncStatus === 'conflict',
  };
}

export default useSettingsSync;
