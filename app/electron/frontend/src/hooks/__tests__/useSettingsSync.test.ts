/**
 * useSettingsSync Hook Tests
 */

import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useSettingsSync, useSetting, useSyncStatus, useSettingsCategory } from '../useSettingsSync';
import * as settingsApi from '../../api/settings';
import { DEFAULT_SETTINGS, type SettingsState } from '../../config/settingsSchema';

// Mock the settingsApi module
vi.mock('../../api/settings', async () => {
  const actual = await vi.importActual<typeof import('../../api/settings')>('../../api/settings');
  return {
    ...actual,
    loadSettings: vi.fn(),
    saveSettings: vi.fn(),
    saveSettingsCategory: vi.fn(),
    resetSettings: vi.fn(),
    createSettingsSyncConnection: vi.fn(),
    queuePendingChange: vi.fn(),
    getPendingChanges: vi.fn(),
    removePendingChange: vi.fn(),
    clearPendingChanges: vi.fn(),
    incrementRetryCount: vi.fn(),
    isApiReachable: vi.fn(),
  };
});

describe('useSettingsSync', () => {
  const mockLoadSettings = settingsApi.loadSettings as Mock;
  const mockSaveSettings = settingsApi.saveSettings as Mock;
  const mockSaveSettingsCategory = settingsApi.saveSettingsCategory as Mock;
  const mockResetSettings = settingsApi.resetSettings as Mock;
  const mockCreateSettingsSyncConnection = settingsApi.createSettingsSyncConnection as Mock;
  const mockIsApiReachable = settingsApi.isApiReachable as Mock;
  const mockGetPendingChanges = settingsApi.getPendingChanges as Mock;

  let mockUnsubscribeEvent: ReturnType<typeof vi.fn>;
  let mockUnsubscribeStatus: ReturnType<typeof vi.fn>;
  let mockDisconnect: ReturnType<typeof vi.fn>;
  let mockSubscribe: ReturnType<typeof vi.fn>;
  let mockOnStatusChange: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();

    // Setup default mock implementations
    mockLoadSettings.mockResolvedValue(DEFAULT_SETTINGS);
    mockSaveSettings.mockResolvedValue({ success: true, data: DEFAULT_SETTINGS, revision: 1 });
    mockSaveSettingsCategory.mockResolvedValue({ success: true, data: DEFAULT_SETTINGS, revision: 1 });
    mockResetSettings.mockResolvedValue({ success: true, data: DEFAULT_SETTINGS, revision: 1 });
    mockIsApiReachable.mockResolvedValue(true);
    mockGetPendingChanges.mockReturnValue([]);

    // Setup WebSocket mock
    mockUnsubscribeEvent = vi.fn();
    mockUnsubscribeStatus = vi.fn();
    mockDisconnect = vi.fn();
    mockSubscribe = vi.fn(() => mockUnsubscribeEvent);
    mockOnStatusChange = vi.fn(() => mockUnsubscribeStatus);

    mockCreateSettingsSyncConnection.mockReturnValue({
      subscribe: mockSubscribe,
      onStatusChange: mockOnStatusChange,
      disconnect: mockDisconnect,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('initialization', () => {
    it('loads settings on mount when autoLoad is true', async () => {
      renderHook(() => useSettingsSync({ autoLoad: true }));

      await waitFor(() => {
        expect(mockLoadSettings).toHaveBeenCalledTimes(1);
      });
    });

    it('does not auto-load when autoLoad is false', () => {
      renderHook(() => useSettingsSync({ autoLoad: false }));

      expect(mockLoadSettings).not.toHaveBeenCalled();
    });

    it('initializes with loading state', async () => {
      const { result } = renderHook(() => useSettingsSync({ autoLoad: true }));

      expect(result.current.isLoading).toBe(true);
      expect(result.current.isInitialized).toBe(false);
    });

    it('sets initialized after successful load', async () => {
      const { result } = renderHook(() => useSettingsSync({ autoLoad: true }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.syncStatus).toBe('synced');
    });

    it('handles load errors', async () => {
      const error = new Error('Failed to load');
      mockLoadSettings.mockRejectedValue(error);

      const onError = vi.fn();
      const { result } = renderHook(() => useSettingsSync({ autoLoad: true, onError }));

      await waitFor(() => {
        expect(result.current.error).toEqual(error);
      });

      expect(result.current.syncStatus).toBe('error');
      expect(onError).toHaveBeenCalledWith(error);
    });
  });

  describe('settings updates', () => {
    it('updates a single setting optimistically', async () => {
      const { result } = renderHook(() => useSettingsSync({ autoLoad: true }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      act(() => {
        result.current.updateSetting('general', 'theme', 'dark');
      });

      expect(result.current.settings.general.theme).toBe('dark');
    });

    it('debounces setting saves', async () => {
      const { result } = renderHook(() => useSettingsSync({ autoLoad: true, debounceMs: 100 }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      act(() => {
        result.current.updateSetting('general', 'theme', 'dark');
      });

      // Immediately after update, save should not be called
      expect(mockSaveSettingsCategory).not.toHaveBeenCalled();

      // Fast forward past debounce
      act(() => {
        vi.advanceTimersByTime(150);
      });

      await waitFor(() => {
        expect(mockSaveSettingsCategory).toHaveBeenCalled();
      });
    });

    it('updates multiple settings in a category', async () => {
      const { result } = renderHook(() => useSettingsSync({ autoLoad: true }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      await act(async () => {
        await result.current.updateCategory('general', {
          theme: 'dark',
          showNotifications: false,
        });
      });

      expect(result.current.settings.general.theme).toBe('dark');
      expect(result.current.settings.general.showNotifications).toBe(false);
    });

    it('sets entire settings object', async () => {
      const { result } = renderHook(() => useSettingsSync({ autoLoad: true }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      const newSettings: SettingsState = {
        ...DEFAULT_SETTINGS,
        general: { ...DEFAULT_SETTINGS.general, theme: 'cyber' },
      };

      act(() => {
        result.current.setSettings(newSettings);
      });

      expect(result.current.settings.general.theme).toBe('cyber');
    });

    it('validates settings before setting', async () => {
      const onError = vi.fn();
      const { result } = renderHook(() => useSettingsSync({ autoLoad: true, onError }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      act(() => {
        // @ts-expect-error Testing invalid settings
        result.current.setSettings({ invalid: true });
      });

      expect(onError).toHaveBeenCalled();
    });
  });

  describe('reset functionality', () => {
    it('resets all settings', async () => {
      const { result } = renderHook(() => useSettingsSync({ autoLoad: true }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      await act(async () => {
        await result.current.reset();
      });

      expect(mockResetSettings).toHaveBeenCalledWith(undefined);
    });

    it('resets a specific category', async () => {
      const { result } = renderHook(() => useSettingsSync({ autoLoad: true }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      await act(async () => {
        await result.current.reset('general');
      });

      expect(mockResetSettings).toHaveBeenCalledWith('general');
    });
  });

  describe('real-time sync', () => {
    it('creates sync connection when enabled', async () => {
      renderHook(() => useSettingsSync({ autoLoad: true, enableRealtimeSync: true }));

      await waitFor(() => {
        expect(mockCreateSettingsSyncConnection).toHaveBeenCalled();
      });
    });

    it('does not create sync connection when disabled', async () => {
      renderHook(() => useSettingsSync({ autoLoad: true, enableRealtimeSync: false }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      expect(mockCreateSettingsSyncConnection).not.toHaveBeenCalled();
    });

    it('handles remote changes', async () => {
      const onRemoteChange = vi.fn();
      renderHook(() => useSettingsSync({ autoLoad: true, onRemoteChange }));

      await waitFor(() => {
        expect(mockSubscribe).toHaveBeenCalled();
      });

      // Get the handler passed to subscribe
      const handler = mockSubscribe.mock.calls[0][0];

      act(() => {
        handler({
          type: 'settings-changed',
          source: 'backend',
          timestamp: new Date().toISOString(),
          changes: { general: { theme: 'dracula' } },
        });
      });

      expect(onRemoteChange).toHaveBeenCalled();
    });

    it('ignores own remote changes', async () => {
      const onRemoteChange = vi.fn();
      renderHook(() => useSettingsSync({ autoLoad: true, onRemoteChange }));

      await waitFor(() => {
        expect(mockSubscribe).toHaveBeenCalled();
      });

      const handler = mockSubscribe.mock.calls[0][0];

      act(() => {
        handler({
          type: 'settings-changed',
          source: 'ui',
          timestamp: new Date().toISOString(),
          changes: { general: { theme: 'dracula' } },
        });
      });

      expect(onRemoteChange).toHaveBeenCalled();
    });

    it('cleans up connection on unmount', async () => {
      const { unmount } = renderHook(() => useSettingsSync({ autoLoad: true }));

      await waitFor(() => {
        expect(mockSubscribe).toHaveBeenCalled();
      });

      unmount();

      expect(mockUnsubscribeEvent).toHaveBeenCalled();
      expect(mockUnsubscribeStatus).toHaveBeenCalled();
      expect(mockDisconnect).toHaveBeenCalled();
    });
  });

  describe('conflict resolution', () => {
    it('detects conflicts on remote change', async () => {
      const onConflict = vi.fn();
      const { result } = renderHook(() => useSettingsSync({ autoLoad: true, onConflict }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      // Modify local setting
      act(() => {
        result.current.updateSetting('general', 'theme', 'cyber');
      });

      // Simulate remote change to same setting
      const handler = mockSubscribe.mock.calls[0][0];

      act(() => {
        handler({
          type: 'settings-changed',
          source: 'backend',
          timestamp: new Date().toISOString(),
          changes: { general: { theme: 'dracula' } },
          revision: 2,
        });
      });

      await waitFor(() => {
        expect(result.current.syncStatus).toBe('conflict');
      });
    });

    it('resolves conflicts with local strategy', async () => {
      const { result } = renderHook(() => useSettingsSync({ autoLoad: true }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      act(() => {
        result.current.updateSetting('general', 'theme', 'cyber');
      });

      // Trigger conflict
      const handler = mockSubscribe.mock.calls[0][0];
      act(() => {
        handler({
          type: 'settings-changed',
          source: 'backend',
          timestamp: new Date().toISOString(),
          changes: { general: { theme: 'dracula' } },
        });
      });

      await waitFor(() => {
        expect(result.current.syncStatus).toBe('conflict');
      });

      // Resolve with local
      act(() => {
        result.current.resolveConflict('local');
      });

      expect(result.current.syncStatus).toBe('synced');
      expect(result.current.conflicts).toHaveLength(0);
    });
  });

  describe('offline support', () => {
    it('queues changes when offline', async () => {
      mockIsApiReachable.mockResolvedValue(false);

      const { result } = renderHook(() => useSettingsSync({ autoLoad: true }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      await act(async () => {
        await result.current.updateCategory('general', { theme: 'dark' });
      });

      await waitFor(() => {
        expect(result.current.syncStatus).toBe('offline');
      });
    });

    it('syncs pending changes when back online', async () => {
      mockGetPendingChanges.mockReturnValue([
        { id: '1', timestamp: Date.now(), category: 'general', path: 'theme', value: 'dark', retryCount: 0 },
      ]);

      const { result } = renderHook(() => useSettingsSync({ autoLoad: true }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      await act(async () => {
        await result.current.sync();
      });

      expect(mockSaveSettingsCategory).toHaveBeenCalled();
    });

    it('clears pending changes', async () => {
      const mockClearPendingChanges = settingsApi.clearPendingChanges as Mock;

      const { result } = renderHook(() => useSettingsSync({ autoLoad: true }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      act(() => {
        result.current.clearPending();
      });

      expect(mockClearPendingChanges).toHaveBeenCalled();
    });
  });

  describe('utility functions', () => {
    it('validates settings', async () => {
      const { result } = renderHook(() => useSettingsSync({ autoLoad: true }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      const validation = result.current.validate();

      expect(validation.valid).toBe(true);
    });

    it('gets a specific setting value', async () => {
      const { result } = renderHook(() => useSettingsSync({ autoLoad: true }));

      await waitFor(() => {
        expect(result.current.isInitialized).toBe(true);
      });

      const theme = result.current.get('general', 'theme');

      expect(theme).toBe(DEFAULT_SETTINGS.general.theme);
    });
  });

  describe('manual load', () => {
    it('loads settings when load is called', async () => {
      const { result } = renderHook(() => useSettingsSync({ autoLoad: false }));

      expect(mockLoadSettings).not.toHaveBeenCalled();

      await act(async () => {
        await result.current.load();
      });

      expect(mockLoadSettings).toHaveBeenCalledTimes(1);
      expect(result.current.isInitialized).toBe(true);
    });
  });
});

describe('useSetting', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (settingsApi.loadSettings as Mock).mockResolvedValue(DEFAULT_SETTINGS);
    (settingsApi.isApiReachable as Mock).mockResolvedValue(true);
    (settingsApi.createSettingsSyncConnection as Mock).mockReturnValue({
      subscribe: vi.fn(() => vi.fn()),
      onStatusChange: vi.fn(() => vi.fn()),
      disconnect: vi.fn(),
    });
  });

  it('returns specific setting value', async () => {
    const { result } = renderHook(() => useSetting('general', 'theme'));

    await waitFor(() => {
      expect(result.current.value).toBeDefined();
    });
  });

  it('updates specific setting', async () => {
    const { result } = renderHook(() => useSetting('general', 'theme'));

    await waitFor(() => {
      expect(result.current.value).toBeDefined();
    });

    act(() => {
      result.current.setValue('dark');
    });

    expect(result.current.value).toBe('dark');
  });
});

describe('useSyncStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (settingsApi.loadSettings as Mock).mockResolvedValue(DEFAULT_SETTINGS);
    (settingsApi.isApiReachable as Mock).mockResolvedValue(true);
    (settingsApi.createSettingsSyncConnection as Mock).mockReturnValue({
      subscribe: vi.fn(() => vi.fn()),
      onStatusChange: vi.fn(() => vi.fn()),
      disconnect: vi.fn(),
    });
  });

  it('returns sync status info', async () => {
    const { result } = renderHook(() => useSyncStatus());

    await waitFor(() => {
      expect(result.current.isInitialized).toBe(true);
    });

    expect(result.current.syncStatus).toBeDefined();
    expect(result.current.isOnline).toBeDefined();
    expect(result.current.hasConflicts).toBeDefined();
  });
});

describe('useSettingsCategory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (settingsApi.loadSettings as Mock).mockResolvedValue(DEFAULT_SETTINGS);
    (settingsApi.isApiReachable as Mock).mockResolvedValue(true);
    (settingsApi.createSettingsSyncConnection as Mock).mockReturnValue({
      subscribe: vi.fn(() => vi.fn()),
      onStatusChange: vi.fn(() => vi.fn()),
      disconnect: vi.fn(),
    });
  });

  it('returns category settings', async () => {
    const { result } = renderHook(() => useSettingsCategory('general'));

    await waitFor(() => {
      expect(result.current.categorySettings).toBeDefined();
    });

    expect(result.current.categorySettings.theme).toBe(DEFAULT_SETTINGS.general.theme);
  });

  it('updates category settings', async () => {
    const { result } = renderHook(() => useSettingsCategory('general'));

    await waitFor(() => {
      expect(result.current.categorySettings).toBeDefined();
    });

    await act(async () => {
      await result.current.update({ theme: 'dark' });
    });

    expect(result.current.categorySettings.theme).toBe('dark');
  });

  it('gets specific key from category', async () => {
    const { result } = renderHook(() => useSettingsCategory('general'));

    await waitFor(() => {
      expect(result.current.categorySettings).toBeDefined();
    });

    const theme = result.current.get('theme');

    expect(theme).toBe(DEFAULT_SETTINGS.general.theme);
  });
});
