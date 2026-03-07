import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  loadSettings,
  saveSettings,
  resetSettings,
  exportSettings,
  importSettings,
  validateSettingsOnBackend,
  isApiReachable,
  detectConflicts,
  resolveConflicts,
  queuePendingChange,
  getPendingChanges,
  clearPendingChanges,
  type SettingsExportData,
} from './settingsApi';
import { createMockSettings } from './factories';
import type { SettingsState } from '../config/settingsSchema';

describe('settingsApi', () => {
  const mockFetch = vi.fn();
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = mockFetch;
    localStorage.clear();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  describe('loadSettings', () => {
    it('loads settings from backend', async () => {
      const mockSettings = createMockSettings();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue(mockSettings),
      });

      const result = await loadSettings();

      expect(result).toEqual(mockSettings);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/settings'),
        expect.objectContaining({ method: 'GET' })
      );
    });

    it('retries on failure and succeeds', async () => {
      const mockSettings = createMockSettings();
      mockFetch
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: vi.fn().mockResolvedValue(mockSettings),
        });

      const result = await loadSettings();

      expect(result).toEqual(mockSettings);
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('throws after max retries', async () => {
      mockFetch.mockRejectedValue(new Error('Network error'));

      await expect(loadSettings()).rejects.toThrow();
      expect(mockFetch).toHaveBeenCalledTimes(4); // Initial + 3 retries
    });

    it('handles non-ok response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        text: vi.fn().mockResolvedValue('Server error'),
      });

      await expect(loadSettings()).rejects.toThrow('Failed to load settings');
    });
  });

  describe('saveSettings', () => {
    it('saves settings to backend', async () => {
      const mockSettings = createMockSettings();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({
          success: true,
          data: mockSettings,
          revision: 1,
        }),
      });

      const result = await saveSettings(mockSettings);

      expect(result.success).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/settings'),
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify(mockSettings),
        })
      );
    });

    it('uses PATCH for partial updates', async () => {
      const mockSettings = createMockSettings();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({ success: true }),
      });

      await saveSettings(mockSettings, { partial: true });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: 'PATCH' })
      );
    });

    it('includes revision header when provided', async () => {
      const mockSettings = createMockSettings();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({ success: true }),
      });

      await saveSettings(mockSettings, { revision: 5 });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-Settings-Revision': '5',
          }),
        })
      );
    });

    it('returns error response on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: vi.fn().mockResolvedValue({
          success: false,
          message: 'Validation failed',
          errors: [{ path: 'theme', message: 'Invalid theme' }],
        }),
      });

      const result = await saveSettings(createMockSettings());

      expect(result.success).toBe(false);
      expect(result.errors).toHaveLength(1);
    });
  });

  describe('resetSettings', () => {
    it('resets all settings', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({
          success: true,
          data: createMockSettings(),
        }),
      });

      const result = await resetSettings();

      expect(result.success).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/settings/reset'),
        expect.objectContaining({ method: 'POST' })
      );
    });

    it('resets specific category', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({ success: true }),
      });

      await resetSettings('general');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/settings/reset/general'),
        expect.any(Object)
      );
    });
  });

  describe('exportSettings', () => {
    it('exports settings with metadata', async () => {
      const mockSettings = createMockSettings();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue(mockSettings),
      });

      const result = await exportSettings();

      expect(result.settings).toEqual(mockSettings);
      expect(result.version).toBe('1.0.0');
      expect(result.source).toBe('OpenWispr');
      expect(result.exportedAt).toBeDefined();
    });
  });

  describe('importSettings', () => {
    it('imports settings from file', async () => {
      const mockSettings = createMockSettings();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({ success: true }),
      });

      const fileContent = JSON.stringify({
        settings: mockSettings,
        exportedAt: new Date().toISOString(),
        version: '1.0.0',
        source: 'OpenWispr',
      });

      const blob = new Blob([fileContent], { type: 'application/json' });
      const file = new File([blob], 'settings.json', { type: 'application/json' });

      const result = await importSettings(file);

      expect(result.success).toBe(true);
    });

    it('handles invalid file content', async () => {
      const blob = new Blob(['not valid json'], { type: 'application/json' });
      const file = new File([blob], 'settings.json', { type: 'application/json' });

      const result = await importSettings(file);

      expect(result.success).toBe(false);
      expect(result.message).toContain('Failed to parse');
    });

    it('handles missing settings object', async () => {
      const blob = new Blob([JSON.stringify({ exportedAt: new Date().toISOString() })], {
        type: 'application/json',
      });
      const file = new File([blob], 'settings.json', { type: 'application/json' });

      const result = await importSettings(file);

      expect(result.success).toBe(false);
      expect(result.message).toContain('missing settings');
    });
  });

  describe('validateSettingsOnBackend', () => {
    it('validates settings successfully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({ valid: true }),
      });

      const result = await validateSettingsOnBackend({ theme: 'dark' });

      expect(result.valid).toBe(true);
    });

    it('returns validation errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: vi.fn().mockResolvedValue({
          valid: false,
          errors: [{ path: 'theme', message: 'Invalid value' }],
        }),
      });

      const result = await validateSettingsOnBackend({ theme: 'invalid' });

      expect(result.valid).toBe(false);
      expect(result.errors).toHaveLength(1);
    });

    it('handles network errors', async () => {
      mockFetch.mockRejectedValue(new Error('Network error'));

      const result = await validateSettingsOnBackend({});

      expect(result.valid).toBe(false);
    });
  });

  describe('isApiReachable', () => {
    it('returns true when API is reachable', async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });

      const result = await isApiReachable();

      expect(result).toBe(true);
    });

    it('returns false when API is unreachable', async () => {
      mockFetch.mockRejectedValue(new Error('Network error'));

      const result = await isApiReachable();

      expect(result).toBe(false);
    });

    it('respects timeout', async () => {
      mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves

      const result = await isApiReachable();

      expect(result).toBe(false);
    });
  });

  describe('conflict detection', () => {
    it('detects conflicts between local and remote settings', () => {
      const local = createMockSettings({ general: { theme: 'dark' } });
      const remote = createMockSettings({ general: { theme: 'light' } });
      const lastSynced = createMockSettings({ general: { theme: 'dark' } });

      const conflicts = detectConflicts(local, remote, lastSynced);

      expect(conflicts).toHaveLength(1);
      expect(conflicts[0].path).toContain('theme');
      expect(conflicts[0].local).toBe('dark');
      expect(conflicts[0].remote).toBe('light');
    });

    it('returns empty array when no conflicts', () => {
      const settings = createMockSettings();

      const conflicts = detectConflicts(settings, settings, settings);

      expect(conflicts).toHaveLength(0);
    });

    it('ignores when only one side changed', () => {
      const local = createMockSettings({ general: { theme: 'dark' } });
      const remote = createMockSettings({ general: { theme: 'dark' } });
      const lastSynced = createMockSettings({ general: { theme: 'light' } });

      const conflicts = detectConflicts(local, remote, lastSynced);

      expect(conflicts).toHaveLength(0);
    });
  });

  describe('conflict resolution', () => {
    it('resolves with local settings', () => {
      const local = createMockSettings({ general: { theme: 'dark' } });
      const remote = createMockSettings({ general: { theme: 'light' } });

      const result = resolveConflicts(local, remote, 'local');

      expect(result.general.theme).toBe('dark');
    });

    it('resolves with remote settings', () => {
      const local = createMockSettings({ general: { theme: 'dark' } });
      const remote = createMockSettings({ general: { theme: 'light' } });

      const result = resolveConflicts(local, remote, 'remote');

      expect(result.general.theme).toBe('light');
    });

    it('merges settings correctly', () => {
      const local = createMockSettings({
        general: { theme: 'dark' },
        transcription: { model_name: 'small' },
      });
      const remote = createMockSettings({
        general: { theme: 'light' },
        transcription: { model_name: 'medium' },
      });

      const result = resolveConflicts(local, remote, 'merge');

      // UI settings from local
      expect(result.general.theme).toBe('dark');
      // Backend settings from remote
      expect(result.transcription.model_name).toBe('medium');
    });
  });

  describe('offline queue', () => {
    it('queues pending changes', () => {
      const change = queuePendingChange({
        category: 'general',
        path: 'theme',
        value: 'dark',
      });

      expect(change.id).toBeDefined();
      expect(change.category).toBe('general');
      expect(change.retryCount).toBe(0);
    });

    it('retrieves pending changes', () => {
      queuePendingChange({ category: 'general', path: 'theme', value: 'dark' });

      const changes = getPendingChanges();

      expect(changes).toHaveLength(1);
      expect(changes[0].category).toBe('general');
    });

    it('clears pending changes', () => {
      queuePendingChange({ category: 'general', path: 'theme', value: 'dark' });

      clearPendingChanges();

      expect(getPendingChanges()).toHaveLength(0);
    });
  });
});

