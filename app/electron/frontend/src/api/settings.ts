/**
 * Settings API Module
 * 
 * Provides HTTP and WebSocket-based API methods for settings synchronization.
 * Includes retry logic, offline queueing, and error handling.
 */

import type { SettingsState } from '../config/settingsSchema';
import { DEFAULT_SETTINGS } from '../config/settingsSchema';
import { AppConstants } from '../lib/constants';

// ============================================
// API Types
// ============================================

export type SyncStatus = 'synced' | 'syncing' | 'offline' | 'error' | 'conflict';

export type SettingsChangeEvent = {
  type: 'settings-changed' | 'settings-reset' | 'settings-imported';
  timestamp: string;
  source: 'ui' | 'backend' | 'import';
  changes: Partial<SettingsState>;
  revision?: number;
};

export type SettingsSyncResponse = {
  success: boolean;
  data?: SettingsState;
  revision?: number;
  message?: string;
  errors?: Array<{ path: string; message: string }>;
};

export type SettingsExportData = {
  settings: SettingsState;
  exportedAt: string;
  version: string;
  source: string;
};

export type ConflictResolution = 'local' | 'remote' | 'merge';

export type PendingChange = {
  id: string;
  timestamp: number;
  category: keyof SettingsState;
  path: string;
  value: unknown;
  retryCount: number;
};

// ============================================
// API Configuration
// ============================================

const API_CONFIG = {
  baseUrl: typeof window !== 'undefined' && typeof window.openwisprDesktop?.getApiOrigin === 'function'
    ? '' // Will be resolved dynamically
    : 'http://127.0.0.1:8765',
  endpoints: {
    settings: '/api/settings',
    settingsReset: '/api/settings/reset',
    settingsExport: '/api/settings/export',
    settingsImport: '/api/settings/import',
    settingsSync: '/api/settings/sync',
  },
  retryConfig: {
    maxRetries: 3,
    baseDelay: 1000,
    maxDelay: 10000,
  },
};

// ============================================
// Retry Utility
// ============================================

async function withRetry<T>(
  operation: () => Promise<T>,
  config: { maxRetries?: number; baseDelay?: number; maxDelay?: number } = {}
): Promise<T> {
  const { maxRetries = 3, baseDelay = 1000, maxDelay = 10000 } = config;
  let lastError: Error | undefined;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      console.error(`Settings API error (attempt ${attempt + 1}/${maxRetries + 1}):`, lastError.message);
      
      if (attempt === maxRetries) {
        throw lastError;
      }

      // Calculate exponential backoff delay
      const delay = Math.min(
        baseDelay * Math.pow(2, attempt),
        maxDelay
      );

      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }

  throw lastError;
}

// ============================================
// HTTP API Methods
// ============================================

async function getApiOrigin(): Promise<string> {
  if (typeof window !== 'undefined' && window.openwisprDesktop?.getApiOrigin) {
    try {
      return await window.openwisprDesktop.getApiOrigin();
    } catch {
      return API_CONFIG.baseUrl;
    }
  }
  return API_CONFIG.baseUrl;
}

async function buildUrl(path: string): Promise<string> {
  const origin = await getApiOrigin();
  return `${origin}${path}`;
}

/**
 * Get storage paths from the backend
 */
export async function getStoragePaths(): Promise<{
  download_root: string;
  models_path: string;
  refiner_models_path: string;
  app_data: string;
  settings_file: string;
}> {
  const url = await buildUrl('/api/system/storage');
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to get storage paths: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Load settings from the backend
 */
export async function loadSettings(): Promise<SettingsState> {
  return withRetry(async () => {
    const url = await buildUrl(API_CONFIG.endpoints.settings);
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Failed to load settings: ${error}`);
    }

    const data = await response.json() as SettingsState;
    return data;
  }, API_CONFIG.retryConfig);
}

/**
 * Save settings to the backend
 */
export async function saveSettings(
  settings: SettingsState,
  options: { partial?: boolean; revision?: number } = {}
): Promise<SettingsSyncResponse> {
  return withRetry(async () => {
    const url = await buildUrl(API_CONFIG.endpoints.settings);
    const response = await fetch(url, {
      method: options.partial ? 'PATCH' : 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...(options.revision !== undefined && { 'X-Settings-Revision': String(options.revision) }),
      },
      body: JSON.stringify(settings),
    });

    const data = await response.json() as SettingsSyncResponse;

    if (!response.ok) {
      return {
        success: false,
        message: data.message || `Failed to save settings: ${response.statusText}`,
        errors: data.errors,
      };
    }

    return {
      success: true,
      data: data.data,
      revision: data.revision,
      message: data.message,
    };
  }, API_CONFIG.retryConfig);
}

/**
 * Save a specific category of settings
 */
export async function saveSettingsCategory<K extends keyof SettingsState>(
  category: K,
  data: SettingsState[K],
  options: { revision?: number } = {}
): Promise<SettingsSyncResponse> {
  return withRetry(async () => {
    const url = await buildUrl(`${API_CONFIG.endpoints.settings}/${category}`);
    const response = await fetch(url, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...(options.revision !== undefined && { 'X-Settings-Revision': String(options.revision) }),
      },
      body: JSON.stringify(data),
    });

    const result = await response.json() as SettingsSyncResponse;

    if (!response.ok) {
      return {
        success: false,
        message: result.message || `Failed to save ${category} settings`,
        errors: result.errors,
      };
    }

    return {
      success: true,
      data: result.data,
      revision: result.revision,
      message: result.message,
    };
  }, API_CONFIG.retryConfig);
}

/**
 * Reset settings to defaults
 */
export async function resetSettings(
  category?: keyof SettingsState
): Promise<SettingsSyncResponse> {
  return withRetry(async () => {
    const url = category
      ? await buildUrl(`${API_CONFIG.endpoints.settingsReset}/${category}`)
      : await buildUrl(API_CONFIG.endpoints.settingsReset);

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
      },
    });

    const data = await response.json() as SettingsSyncResponse;

    if (!response.ok) {
      return {
        success: false,
        message: data.message || 'Failed to reset settings',
      };
    }

    return {
      success: true,
      data: data.data,
      revision: data.revision,
      message: data.message || 'Settings reset successfully',
    };
  }, API_CONFIG.retryConfig);
}

/**
 * Export settings to a file
 */
export async function exportSettings(): Promise<SettingsExportData> {
  const settings = await loadSettings();
  
  return {
    settings,
    exportedAt: new Date().toISOString(),
    version: '1.0.0',
    source: AppConstants.APP_NAME,
  };
}

/**
 * Download settings as a JSON file
 */
export function downloadSettings(exportData: SettingsExportData, filename?: string): void {
  const blob = new Blob([JSON.stringify(exportData, null, 2)], {
    type: 'application/json',
  });
  
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download =
    filename || `${AppConstants.APP_SLUG}-settings-${new Date().toISOString().split('T')[0]}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Import settings from a file
 */
export async function importSettings(file: File): Promise<SettingsSyncResponse> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    
    reader.onload = async (event) => {
      try {
        const content = event.target?.result as string;
        const importData = JSON.parse(content) as SettingsExportData;
        
        // Validate imported data structure
        if (!importData.settings || typeof importData.settings !== 'object') {
          resolve({
            success: false,
            message: 'Invalid settings file: missing settings object',
          });
          return;
        }

        // Save imported settings
        const result = await saveSettings(importData.settings);
        resolve(result);
      } catch (error) {
        resolve({
          success: false,
          message: `Failed to parse settings file: ${error instanceof Error ? error.message : String(error)}`,
        });
      }
    };

    reader.onerror = () => {
      resolve({
        success: false,
        message: 'Failed to read settings file',
      });
    };

    reader.readAsText(file);
  });
}

/**
 * Validate settings on the backend
 */
export async function validateSettingsOnBackend(
  settings: Partial<SettingsState>
): Promise<{ valid: boolean; errors?: Array<{ path: string; message: string }> }> {
  try {
    const url = await buildUrl(`${API_CONFIG.endpoints.settings}/validate`);
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(settings),
    });

    const data = await response.json();
    return {
      valid: data.valid ?? response.ok,
      errors: data.errors,
    };
  } catch (error) {
    console.error('Settings validation error:', error instanceof Error ? error.message : String(error));
    return {
      valid: false,
      errors: [{ path: '', message: String(error) }],
    };
  }
}

// ============================================
// WebSocket/SSE Methods
// ============================================

export type SettingsEventHandler = (event: SettingsChangeEvent) => void;
export type ConnectionStatusHandler = (status: SyncStatus) => void;

export interface SettingsSyncConnection {
  subscribe(handler: SettingsEventHandler): () => void;
  onStatusChange(handler: ConnectionStatusHandler): () => void;
  disconnect(): void;
}

/**
 * Create a WebSocket-based settings sync connection
 * Falls back to SSE if WebSocket is not available
 */
export function createSettingsSyncConnection(
  options: {
    onError?: (error: Error) => void;
    reconnect?: boolean;
  } = {}
): SettingsSyncConnection {
  const { onError, reconnect = true } = options;
  const eventHandlers = new Set<SettingsEventHandler>();
  const statusHandlers = new Set<ConnectionStatusHandler>();
  
  let ws: WebSocket | null = null;
  let eventSource: EventSource | null = null;
  let reconnectAttempts = 0;
  let reconnectTimeout: number | null = null;
  const maxReconnectAttempts = 10;
  const baseReconnectDelay = 1000;

  const notifyStatus = (status: SyncStatus) => {
    statusHandlers.forEach(handler => {
      try {
        handler(status);
      } catch (error) {
        console.error('Error in status handler:', error);
      }
    });
  };

  const notifyEvent = (event: SettingsChangeEvent) => {
    eventHandlers.forEach(handler => {
      try {
        handler(event);
      } catch (error) {
        console.error('Error in event handler:', error);
      }
    });
  };

  const connectWebSocket = async () => {
    try {
      const origin = await getApiOrigin();
      const wsUrl = origin.replace(/^http/, 'ws') + '/ws/settings';
      
      ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        reconnectAttempts = 0;
        notifyStatus('synced');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as SettingsChangeEvent;
          notifyEvent(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onerror = () => {
        notifyStatus('error');
        onError?.(new Error('WebSocket error'));
      };

      ws.onclose = () => {
        if (reconnect && reconnectAttempts < maxReconnectAttempts) {
          reconnectAttempts++;
          const delay = Math.min(
            baseReconnectDelay * Math.pow(2, reconnectAttempts - 1),
            30000
          );
          notifyStatus('syncing');
          reconnectTimeout = window.setTimeout(connectWebSocket, delay);
        } else {
          notifyStatus('offline');
          // Fall back to SSE
          connectSSE();
        }
      };
    } catch (error) {
      console.error('WebSocket connection error, falling back to SSE:', error instanceof Error ? error.message : String(error));
      connectSSE();
    }
  };

  const connectSSE = async () => {
    try {
      const url = await buildUrl('/api/settings/events');
      eventSource = new EventSource(url);

      eventSource.onopen = () => {
        reconnectAttempts = 0;
        notifyStatus('synced');
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as SettingsChangeEvent;
          notifyEvent(data);
        } catch (error) {
          console.error('Failed to parse SSE message:', error);
        }
      };

      eventSource.onerror = () => {
        notifyStatus('error');
        eventSource?.close();
        
        if (reconnect && reconnectAttempts < maxReconnectAttempts) {
          reconnectAttempts++;
          const delay = Math.min(
            baseReconnectDelay * Math.pow(2, reconnectAttempts - 1),
            30000
          );
          notifyStatus('syncing');
          reconnectTimeout = window.setTimeout(connectSSE, delay);
        } else {
          notifyStatus('offline');
        }
      };
    } catch (error) {
      console.error('SSE connection error:', error instanceof Error ? error.message : String(error));
      notifyStatus('error');
      onError?.(error instanceof Error ? error : new Error(String(error)));
    }
  };

  // Start connection
  connectWebSocket();

  return {
    subscribe(handler) {
      eventHandlers.add(handler);
      return () => eventHandlers.delete(handler);
    },
    onStatusChange(handler) {
      statusHandlers.add(handler);
      return () => statusHandlers.delete(handler);
    },
    disconnect() {
      if (reconnectTimeout !== null) {
        window.clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
      }
      ws?.close();
      eventSource?.close();
      eventHandlers.clear();
      statusHandlers.clear();
    },
  };
}

// ============================================
// Offline Queue Management
// ============================================

const OFFLINE_QUEUE_KEY = 'openwispr:settings:pending';

/**
 * Queue a settings change for later sync
 */
export function queuePendingChange(change: Omit<PendingChange, 'id' | 'timestamp' | 'retryCount'>): PendingChange {
  const pending = getPendingChanges();
  const newChange: PendingChange = {
    ...change,
    id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    timestamp: Date.now(),
    retryCount: 0,
  };
  
  pending.push(newChange);
  localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(pending));
  
  return newChange;
}

/**
 * Get all pending changes
 */
export function getPendingChanges(): PendingChange[] {
  if (typeof window === 'undefined') return [];
  
  try {
    const stored = localStorage.getItem(OFFLINE_QUEUE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

/**
 * Remove a pending change by ID
 */
export function removePendingChange(id: string): void {
  const pending = getPendingChanges().filter(c => c.id !== id);
  localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(pending));
}

/**
 * Clear all pending changes
 */
export function clearPendingChanges(): void {
  localStorage.removeItem(OFFLINE_QUEUE_KEY);
}

/**
 * Update retry count for a pending change
 */
export function incrementRetryCount(id: string): void {
  const pending = getPendingChanges().map(c => 
    c.id === id ? { ...c, retryCount: c.retryCount + 1 } : c
  );
  localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(pending));
}

// ============================================
// Conflict Resolution
// ============================================

/**
 * Detect conflicts between local and remote settings
 */
export function detectConflicts(
  local: SettingsState,
  remote: SettingsState,
  lastSynced?: SettingsState
): Array<{ path: string; local: unknown; remote: unknown }> {
  const conflicts: Array<{ path: string; local: unknown; remote: unknown }> = [];

  function compareObjects(localObj: unknown, remoteObj: unknown, path: string) {
    if (typeof localObj !== 'object' || localObj === null) {
      if (localObj !== remoteObj) {
        // Check if this is actually a conflict or just a new change
        const lastValue = lastSynced 
          ? getValueAtPath(lastSynced, path)
          : undefined;
        
        // If both changed from last synced value, it's a conflict
        if (lastValue !== undefined && localObj !== lastValue && remoteObj !== lastValue) {
          conflicts.push({ path, local: localObj, remote: remoteObj });
        }
      }
      return;
    }

    const localKeys = Object.keys(localObj as Record<string, unknown>);
    const remoteKeys = Object.keys(remoteObj as Record<string, unknown>);
    const allKeys = new Set([...localKeys, ...remoteKeys]);

    for (const key of allKeys) {
      const newPath = path ? `${path}.${key}` : key;
      compareObjects(
        (localObj as Record<string, unknown>)[key],
        (remoteObj as Record<string, unknown>)[key],
        newPath
      );
    }
  }

  compareObjects(local, remote, '');
  return conflicts;
}

function getValueAtPath(obj: SettingsState, path: string): unknown {
  const parts = path.split('.');
  let current: unknown = obj;
  
  for (const part of parts) {
    if (current === null || typeof current !== 'object') {
      return undefined;
    }
    current = (current as Record<string, unknown>)[part];
  }
  
  return current;
}

/**
 * Resolve conflicts using the specified strategy
 */
export function resolveConflicts(
  local: SettingsState,
  remote: SettingsState,
  strategy: ConflictResolution
): SettingsState {
  switch (strategy) {
    case 'local':
      return local;
    case 'remote':
      return remote;
    case 'merge':
      // Merge: prefer local for UI-related, remote for backend-related
      return mergeSettings(local, remote);
    default:
      return remote;
  }
}

function mergeSettings(local: SettingsState, remote: SettingsState): SettingsState {
  return {
    ...remote,
    // UI preferences from local
    general: local.general,
    // Backend settings from remote (source of truth)
    transcription: remote.transcription,
    refiner: remote.refiner,
    audio: remote.audio,
    // Hotkey configuration - merge carefully
    hotkey: {
      ...remote.hotkey,
      // Keep local UI preferences
      show_floating_window: local.hotkey.show_floating_window,
      floating_window_position: local.hotkey.floating_window_position,
    },
    // Advanced from remote
    advanced: remote.advanced,
    version: remote.version,
  };
}

// ============================================
// Utility Functions
// ============================================

/**
 * Check if the API is reachable
 */
export async function isApiReachable(): Promise<boolean> {
  try {
    const url = await buildUrl('/api/health');
    const response = await fetch(url, {
      method: 'HEAD',
      signal: AbortSignal.timeout(5000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Debounce utility for settings saves
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  
  return (...args: Parameters<T>) => {
    if (timeoutId !== null) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      fn(...args);
      timeoutId = null;
    }, delay);
  };
}

/**
 * Get default settings for a specific category
 */
export function getDefaultSettingsForCategory<K extends keyof SettingsState>(
  category: K
): SettingsState[K] {
  return DEFAULT_SETTINGS[category];
}

// ============================================
// Sync Helper Methods
// ============================================

/**
 * Synchronize settings with the backend.
 * Fetches latest settings and merges with local if needed.
 */
export async function syncSettings(
  localSettings: SettingsState,
  options: { preferRemote?: boolean; revision?: number } = {}
): Promise<SettingsSyncResponse> {
  try {
    // Fetch remote settings
    const remoteSettings = await loadSettings();

    // Check for conflicts
    const conflicts = detectConflicts(localSettings, remoteSettings);

    if (conflicts.length > 0) {
      if (options.preferRemote) {
        return {
          success: true,
          data: remoteSettings,
          message: 'Resolved conflicts using remote settings',
        };
      }
      return {
        success: false,
        message: `Sync conflict detected: ${conflicts.length} setting(s) changed on both sides`,
        errors: conflicts.map(c => ({ path: c.path, message: 'Conflict detected' })),
      };
    }

    // Save local settings to remote
    const result = await saveSettings(localSettings, { revision: options.revision });
    return result;
  } catch (error) {
    return {
      success: false,
      message: error instanceof Error ? error.message : 'Sync failed',
    };
  }
}

/**
 * Watch for settings changes with a callback.
 * Returns an unsubscribe function.
 */
export function watchSettings(
  onChange: (event: SettingsChangeEvent) => void,
  onStatusChange?: (status: SyncStatus) => void
): { unsubscribe: () => void; status: () => SyncStatus } {
  let currentStatus: SyncStatus = 'syncing';

  const connection = createSettingsSyncConnection({
    onError: () => {
      currentStatus = 'error';
    },
    reconnect: true,
  });

  const unsubscribeEvent = connection.subscribe(onChange);
  const unsubscribeStatus = connection.onStatusChange((status) => {
    currentStatus = status;
    onStatusChange?.(status);
  });

  return {
    unsubscribe: () => {
      unsubscribeEvent();
      unsubscribeStatus();
      connection.disconnect();
    },
    status: () => currentStatus,
  };
}

/**
 * Create a settings patch for partial updates.
 * Only includes changed values.
 */
export function createSettingsPatch(
  original: SettingsState,
  updated: SettingsState
): Partial<SettingsState> {
  const patch: Partial<SettingsState> = {};

  (Object.keys(updated) as Array<keyof SettingsState>).forEach((key) => {
    if (key === 'version') return;

    const originalValue = original[key];
    const updatedValue = updated[key];

    if (JSON.stringify(originalValue) !== JSON.stringify(updatedValue)) {
      (patch as Record<string, unknown>)[key] = updatedValue;
    }
  });

  return patch;
}

/**
 * Apply a settings patch to existing settings.
 */
export function applySettingsPatch(
  settings: SettingsState,
  patch: Partial<SettingsState>
): SettingsState {
  return {
    ...settings,
    ...patch,
  };
}

/**
 * Get the current sync status from localStorage cache.
 */
export function getCachedSyncStatus(): SyncStatus {
  if (typeof window === 'undefined') return 'offline';

  try {
    const cached = localStorage.getItem('openwispr:settings:syncStatus');
    return (cached as SyncStatus) || 'synced';
  } catch {
    return 'synced';
  }
}

/**
 * Cache the current sync status.
 */
export function cacheSyncStatus(status: SyncStatus): void {
  if (typeof window === 'undefined') return;

  try {
    localStorage.setItem('openwispr:settings:syncStatus', status);
  } catch {
    // Ignore storage errors
  }
}

/**
 * Get cached settings from localStorage.
 */
export function getCachedSettings(): SettingsState | null {
  if (typeof window === 'undefined') return null;

  try {
    const cached = localStorage.getItem('openwispr:settings:cache');
    if (cached) {
      const parsed = JSON.parse(cached);
      return parsed as SettingsState;
    }
  } catch {
    // Ignore parse errors
  }
  return null;
}

/**
 * Cache settings to localStorage.
 */
export function cacheSettings(settings: SettingsState): void {
  if (typeof window === 'undefined') return;

  try {
    localStorage.setItem('openwispr:settings:cache', JSON.stringify(settings));
  } catch {
    // Ignore storage errors
  }
}

// ============================================
// Batch Operations
// ============================================

/**
 * Batch multiple settings updates into a single save.
 */
export async function batchUpdateSettings(
  updates: Array<{
    category: keyof SettingsState;
    path: string;
    value: unknown;
  }>,
  currentSettings: SettingsState
): Promise<SettingsSyncResponse> {
  let newSettings = { ...currentSettings };

  // Apply all updates
  updates.forEach(({ category, path, value }) => {
    if (path.includes('.')) {
      // Nested path
      const parts = path.split('.');
      const key = parts.pop()!;
      let target: Record<string, unknown> = newSettings[category] as Record<string, unknown>;

      for (const part of parts) {
        target = target[part] as Record<string, unknown>;
      }
      target[key] = value;
    } else {
      // Direct category key
      (newSettings[category] as Record<string, unknown>)[path] = value;
    }
  });

  return saveSettings(newSettings);
}
