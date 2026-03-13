/**
 * Settings Context
 *
 * Provides global settings state with bidirectional synchronization,
 * optimistic updates, conflict resolution, and offline support.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { SettingsState } from '../config/settingsSchema';
import { DEFAULT_SETTINGS, validateSettings } from '../config/settingsSchema';
import {
  queuePendingChange,
  getPendingChanges,
  removePendingChange,
  incrementRetryCount,
  detectConflicts,
  resolveConflicts,
  isApiReachable,
  exportSettings,
  importSettings,
  downloadSettings,
  saveSettings,
  saveSettingsCategory,
  resetSettings,
  createSettingsSyncConnection,
  loadSettings,
  type SettingsExportData,
  type SyncStatus,
  type PendingChange,
  type SettingsSyncResponse,
  type ConflictResolution,
  type SettingsChangeEvent,
} from '../api/settings';

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
// Notification Types
// ============================================

export type NotificationType = 'success' | 'error' | 'info' | 'warning';

export interface SettingsNotification {
  id: string;
  type: NotificationType;
  message: string;
  category?: keyof SettingsState;
  timestamp: number;
}

// ============================================
// Context Types
// ============================================

export interface SettingsContextValue {
  // State
  settings: SettingsState;
  syncStatus: SyncStatus;
  isLoading: boolean;
  isInitialized: boolean;
  error: Error | null;
  notifications: SettingsNotification[];
  pendingChanges: PendingChange[];
  revision: number;

  // Actions
  updateSetting: <K extends keyof SettingsState>(
    category: K,
    key: keyof SettingsState[K],
    value: SettingsState[K][typeof key]
  ) => void;
  updateSettingsCategory: <K extends keyof SettingsState>(
    category: K,
    data: Partial<SettingsState[K]>
  ) => Promise<void>;
  resetSettingsCategory: (category?: keyof SettingsState) => Promise<void>;
  resetAllSettings: () => Promise<void>;

  // Import/Export
  exportSettings: () => Promise<SettingsExportData>;
  downloadSettings: (filename?: string) => Promise<void>;
  importSettings: (file: File) => Promise<SettingsSyncResponse>;

  // Conflict Resolution
  resolveConflict: (strategy: ConflictResolution) => void;
  conflicts: Array<{ path: string; local: unknown; remote: unknown }>;

  // Notifications
  dismissNotification: (id: string) => void;
  clearAllNotifications: () => void;

  // Manual sync
  syncNow: () => Promise<void>;
  refreshSettings: () => Promise<void>;
}

// ============================================
// Context Creation
// ============================================

const SettingsContext = createContext<SettingsContextValue | null>(null);

// ============================================
// Provider Props
// ============================================

export interface SettingsProviderProps {
  children: ReactNode;
  debounceMs?: number;
  enableRealtimeSync?: boolean;
  onError?: (error: Error) => void;
}

// ============================================
// Provider Component
// ============================================

export function SettingsProvider({
  children,
  debounceMs = 100,
  enableRealtimeSync = true,
  onError,
}: SettingsProviderProps) {
  // Core state
  const [settings, setSettings] = useState<SettingsState>(DEFAULT_SETTINGS);
  const [syncStatus, setSyncStatus] = useState<SyncStatus>('syncing');
  const [isLoading, setIsLoading] = useState(true);
  const [isInitialized, setIsInitialized] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [revision, setRevision] = useState(0);

  // Notification state
  const [notifications, setNotifications] = useState<SettingsNotification[]>([]);

  // Conflict state
  const [conflicts, setConflicts] = useState<Array<{ path: string; local: unknown; remote: unknown }>>([]);
  const pendingRemoteSettings = useRef<SettingsState | null>(null);

  // Pending changes for offline support
  const [pendingChanges, setPendingChanges] = useState<PendingChange[]>([]);

  // Refs for internal state management
  const lastSyncedSettings = useRef<SettingsState>(DEFAULT_SETTINGS);
  const syncConnectionRef = useRef<ReturnType<typeof createSettingsSyncConnection> | null>(null);
  const isProcessingRemoteChange = useRef(false);
  const optimisticUpdates = useRef<Map<string, unknown>>(new Map());

  // ============================================
  // Notification Helpers
  // ============================================

  const addNotification = useCallback((notification: Omit<SettingsNotification, 'id' | 'timestamp'>) => {
    const newNotification: SettingsNotification = {
      ...notification,
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: Date.now(),
    };
    setNotifications(prev => [...prev.slice(-9), newNotification]); // Keep last 10
  }, []);

  const dismissNotification = useCallback((id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  }, []);

  const clearAllNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  // ============================================
  // Settings Loading
  // ============================================

  const loadInitialSettings = useCallback(async () => {
    try {
      setIsLoading(true);
      setSyncStatus('syncing');
      setError(null);

      const loadedSettings = await loadSettings();
      const validation = validateSettings(loadedSettings);

      if (validation.success) {
        setSettings(validation.data);
        lastSyncedSettings.current = validation.data;
        setIsInitialized(true);
        setSyncStatus('synced');
      } else {
        throw new Error(`Settings validation failed: ${validation.errors.message}`);
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      setSyncStatus('error');
      onError?.(error);

      // Try to load from localStorage as fallback
      const cached = localStorage.getItem('openwispr:settings:cache');
      if (cached) {
        try {
          const parsed = JSON.parse(cached);
          const validation = validateSettings(parsed);
          if (validation.success) {
            setSettings(validation.data);
            addNotification({
              type: 'warning',
              message: 'Using cached settings. Some changes may not be saved.',
            });
          }
        } catch {
          // Ignore cache errors
        }
      }
    } finally {
      setIsLoading(false);
    }
  }, [onError, addNotification]);

  // ============================================
  // Settings Persistence (Debounced)
  // ============================================

  const persistSettings = useCallback(
    debounce(async (newSettings: SettingsState, category?: keyof SettingsState) => {
      try {
        setSyncStatus('syncing');
        setError(null);

        const isOnline = await isApiReachable();

        if (!isOnline) {
          // Queue the change for later
          if (category) {
            queuePendingChange({
              category,
              path: category,
              value: newSettings[category],
            });
            setPendingChanges(getPendingChanges());
          }
          setSyncStatus('offline');
          addNotification({
            type: 'warning',
            message: 'Changes queued for sync when connection is restored.',
          });
          return;
        }

        let response: SettingsSyncResponse;

        if (category) {
          response = await saveSettingsCategory(category, newSettings[category], {
            revision,
          });
        } else {
          response = await saveSettings(newSettings, { revision });
        }

        if (response.success) {
          lastSyncedSettings.current = newSettings;
          if (response.revision !== undefined) {
            setRevision(response.revision);
          }
          setSyncStatus('synced');

          // Apply hotkey config after saving hotkey settings
          if (category === 'hotkey' || !category) {
            const hotkeyConfig = (newSettings as SettingsState).hotkey;
            if (hotkeyConfig && window.openwisprDesktop?.applyHotkeyConfig) {
              window.openwisprDesktop.applyHotkeyConfig(hotkeyConfig);
            }
          }

          // Cache successful settings
          localStorage.setItem('openwispr:settings:cache', JSON.stringify(newSettings));
        } else if (response.errors) {
          // Validation errors
          throw new Error(response.message || 'Settings validation failed');
        } else {
          // Other error - check for conflicts
          throw new Error(response.message || 'Failed to save settings');
        }
      } catch (err) {
        const error = err instanceof Error ? err : new Error(String(err));
        setError(error);
        setSyncStatus('error');
        onError?.(error);

        addNotification({
          type: 'error',
          message: error.message,
          category,
        });
      }
    }, debounceMs),
    [revision, addNotification, onError, debounceMs]
  );

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

    const cacheKey = `${category}.${String(key)}`;
    optimisticUpdates.current.set(cacheKey, value);

    setSettings(prev => {
      const newSettings = {
        ...prev,
        [category]: {
          ...(prev[category] as Record<string, unknown>),
          [key]: value,
        },
      } as SettingsState;

      // Persist the entire category
      persistSettings(newSettings, category);
      return newSettings;
    });
  }, [persistSettings]);

  const updateSettingsCategory = useCallback(async <K extends keyof SettingsState>(
    category: K,
    data: Partial<SettingsState[K]>
  ) => {
    try {
      setSyncStatus('syncing');

      setSettings(prev => {
        const newSettings = {
          ...prev,
          [category]: {
            ...(prev[category] as Record<string, unknown>),
            ...data,
          },
        } as SettingsState;
        return newSettings;
      });

      // Wait for debounced save
      await new Promise(resolve => setTimeout(resolve, debounceMs + 50));

      addNotification({
        type: 'success',
        message: `${category} settings updated successfully`,
        category,
      });
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      addNotification({
        type: 'error',
        message: error.message,
        category,
      });
      throw error;
    }
  }, [debounceMs, addNotification]);

  // ============================================
  // Reset Functions
  // ============================================

  const resetSettingsCategory = useCallback(async (category?: keyof SettingsState) => {
    try {
      setSyncStatus('syncing');
      const response = await resetSettings(category);

      if (response.success && response.data) {
        setSettings(response.data);
        lastSyncedSettings.current = response.data;
        if (response.revision !== undefined) {
          setRevision(response.revision);
        }
        setSyncStatus('synced');

        addNotification({
          type: 'success',
          message: category
            ? `${category} settings reset to defaults`
            : 'All settings reset to defaults',
          category,
        });
      } else {
        throw new Error(response.message || 'Failed to reset settings');
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      setSyncStatus('error');
      onError?.(error);

      addNotification({
        type: 'error',
        message: error.message,
        category,
      });
    }
  }, [onError, addNotification]);

  const resetAllSettings = useCallback(async () => {
    await resetSettingsCategory(undefined);
  }, [resetSettingsCategory]);

  // ============================================
  // Import/Export Functions
  // ============================================

  const handleExportSettings = useCallback(async () => {
    try {
      const data = await exportSettings();
      return data;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      addNotification({
        type: 'error',
        message: `Export failed: ${error.message}`,
      });
      throw error;
    }
  }, [addNotification]);

  const handleDownloadSettings = useCallback(async (filename?: string) => {
    try {
      const data = await exportSettings();
      downloadSettings(data, filename);
      addNotification({
        type: 'success',
        message: 'Settings exported successfully',
      });
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      addNotification({
        type: 'error',
        message: `Export failed: ${error.message}`,
      });
    }
  }, [addNotification]);

  const handleImportSettings = useCallback(async (file: File) => {
    try {
      setSyncStatus('syncing');
      const response = await importSettings(file);

      if (response.success && response.data) {
        setSettings(response.data);
        lastSyncedSettings.current = response.data;
        if (response.revision !== undefined) {
          setRevision(response.revision);
        }
        setSyncStatus('synced');

        addNotification({
          type: 'success',
          message: 'Settings imported successfully',
        });
      } else {
        throw new Error(response.message || 'Failed to import settings');
      }

      return response;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      addNotification({
        type: 'error',
        message: `Import failed: ${error.message}`,
      });
      throw error;
    }
  }, [addNotification]);

  // ============================================
  // Conflict Resolution
  // ============================================

  const resolveConflict = useCallback((strategy: ConflictResolution) => {
    if (!pendingRemoteSettings.current) {
      return;
    }

    const resolved = resolveConflicts(settings, pendingRemoteSettings.current, strategy);
    setSettings(resolved);
    lastSyncedSettings.current = resolved;
    setConflicts([]);
    pendingRemoteSettings.current = null;
    setSyncStatus('synced');

    // Persist the resolved settings
    persistSettings(resolved);

    addNotification({
      type: 'success',
      message: `Conflicts resolved using ${strategy} strategy`,
    });
  }, [settings, persistSettings, addNotification]);

  // ============================================
  // Remote Change Handling
  // ============================================

  const handleRemoteChange = useCallback((event: SettingsChangeEvent) => {
    if (event.source === 'ui') {
      // Our own change, ignore
      return;
    }

    isProcessingRemoteChange.current = true;

    try {
      switch (event.type) {
        case 'settings-changed':
          if (event.changes) {
            const newSettings = { ...settings, ...event.changes };

            // Check for conflicts
            const detectedConflicts = detectConflicts(
              settings,
              newSettings,
              lastSyncedSettings.current
            );

            if (detectedConflicts.length > 0) {
              setConflicts(detectedConflicts);
              pendingRemoteSettings.current = newSettings;
              setSyncStatus('conflict');

              addNotification({
                type: 'warning',
                message: `Settings conflict detected on ${detectedConflicts.length} setting(s). Please resolve.`,
              });
            } else {
              setSettings(newSettings);
              lastSyncedSettings.current = newSettings;
              if (event.revision !== undefined) {
                setRevision(event.revision);
              }
              setSyncStatus('synced');
            }
          }
          break;

        case 'settings-reset':
          if (event.changes) {
            setSettings(event.changes as SettingsState);
            lastSyncedSettings.current = event.changes as SettingsState;
            setSyncStatus('synced');

            addNotification({
              type: 'info',
              message: 'Settings were reset from another session',
            });
          }
          break;

        case 'settings-imported':
          if (event.changes) {
            setSettings(event.changes as SettingsState);
            lastSyncedSettings.current = event.changes as SettingsState;
            setSyncStatus('synced');

            addNotification({
              type: 'info',
              message: 'Settings were imported from another session',
            });
          }
          break;
      }
    } finally {
      // Reset flag after a short delay to allow state to settle
      setTimeout(() => {
        isProcessingRemoteChange.current = false;
      }, 50);
    }
  }, [settings, addNotification]);

  // ============================================
  // Sync Connection
  // ============================================

  useEffect(() => {
    if (!enableRealtimeSync || !isInitialized) {
      return;
    }

    syncConnectionRef.current = createSettingsSyncConnection({
      onError: (error) => {
        console.error('Settings sync connection error:', error);
        setSyncStatus('error');
      },
      reconnect: true,
    });

    const unsubscribeEvent = syncConnectionRef.current.subscribe(handleRemoteChange);
    const unsubscribeStatus = syncConnectionRef.current.onStatusChange(setSyncStatus);

    return () => {
      unsubscribeEvent();
      unsubscribeStatus();
      syncConnectionRef.current?.disconnect();
      syncConnectionRef.current = null;
    };
  }, [enableRealtimeSync, isInitialized, handleRemoteChange]);

  // ============================================
  // Offline Sync Recovery
  // ============================================

  const syncOfflineChanges = useCallback(async () => {
    const pending = getPendingChanges();
    if (pending.length === 0) {
      return;
    }

    const isOnline = await isApiReachable();
    if (!isOnline) {
      return;
    }

    setSyncStatus('syncing');

    for (const change of pending) {
      try {
        const response = await saveSettingsCategory(change.category, change.value as SettingsState[typeof change.category], {
          revision,
        });

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

    if (remaining.length === 0) {
      setSyncStatus('synced');
      addNotification({
        type: 'success',
        message: 'All pending changes synchronized',
      });
    } else {
      setSyncStatus('error');
      addNotification({
        type: 'warning',
        message: `${remaining.length} changes failed to sync`,
      });
    }
  }, [revision, addNotification]);

  // Check for offline changes periodically
  useEffect(() => {
    if (!isInitialized) {
      return;
    }

    const interval = setInterval(syncOfflineChanges, 30000);
    return () => clearInterval(interval);
  }, [isInitialized, syncOfflineChanges]);

  // ============================================
  // Manual Sync
  // ============================================

  const syncNow = useCallback(async () => {
    await syncOfflineChanges();
  }, [syncOfflineChanges]);

  const refreshSettings = useCallback(async () => {
    await loadInitialSettings();
  }, [loadInitialSettings]);

  // ============================================
  // Initial Load
  // ============================================

  useEffect(() => {
    loadInitialSettings();
  }, [loadInitialSettings]);

  // ============================================
  // Context Value
  // ============================================

  const value: SettingsContextValue = {
    settings,
    syncStatus,
    isLoading,
    isInitialized,
    error,
    notifications,
    pendingChanges,
    revision,
    updateSetting,
    updateSettingsCategory,
    resetSettingsCategory,
    resetAllSettings,
    exportSettings: handleExportSettings,
    downloadSettings: handleDownloadSettings,
    importSettings: handleImportSettings,
    resolveConflict,
    conflicts,
    dismissNotification,
    clearAllNotifications,
    syncNow,
    refreshSettings,
  };

  return (
    <SettingsContext.Provider value={value}>
      {children}
    </SettingsContext.Provider>
  );
}

// ============================================
// Hook
// ============================================

export function useSettings(): SettingsContextValue {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
}

// ============================================
// Re-exports
// ============================================

export type { SyncStatus, SettingsChangeEvent, SettingsExportData, ConflictResolution };
export { DEFAULT_SETTINGS };
