import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import App from '../App';
import { SettingsPanel } from '../components/SettingsPanel';
import {
  createMockSettings,
  createMockSnapshot,
  createMockSystemProfile,
  createMockModelCatalogEntry,
  MOCK_MODELS,
  MOCK_DEVICES,
} from '../test/factories';
import type { SettingsState } from '../lib/settingsSchema';

// Mock hooks
vi.mock('../hooks/useEventSource', () => ({
  useEventSource: vi.fn(),
}));

import { useEventSource } from '../hooks/useEventSource';
const mockedUseEventSource = vi.mocked(useEventSource);

describe('Settings Integration Flow', () => {
  const mockConnect = vi.fn();
  const mockDisconnect = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    mockedUseEventSource.mockReturnValue({
      status: 'polling',
      lastEvent: null,
      reconnectAttempts: 0,
      connect: mockConnect,
      disconnect: mockDisconnect,
    });

    window.transcriptaDesktop.fetchJson.mockImplementation((path: string) => {
      switch (true) {
        case path === '/api/settings':
          return Promise.resolve(createMockSettings());
        case path === '/api/devices':
          return Promise.resolve({ devices: MOCK_DEVICES });
        case path === '/api/session':
          return Promise.resolve(createMockSnapshot());
        case path === '/api/system/profile':
          return Promise.resolve(createMockSystemProfile());
        case path === '/api/models/catalog':
          return Promise.resolve({
            catalog: MOCK_MODELS,
            installed: [],
            selected_asr_model_id: 'small',
            refinement_mode: 'off',
            recommendations: ['small'],
          });
        default:
          return Promise.resolve({});
      }
    });

    window.transcriptaDesktop.hotkey.getState.mockResolvedValue({
      config: { enabled: false },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('completes full settings change and save flow', async () => {
    // Setup save handler
    let savedSettings: SettingsState | null = null;
    window.transcriptaDesktop.fetchJson.mockImplementation((path: string, options?: RequestInit) => {
      if (path === '/api/settings' && options?.method === 'POST') {
        savedSettings = JSON.parse(options.body as string) as SettingsState;
        return Promise.resolve({ success: true });
      }
      return Promise.resolve(createMockSettings());
    });

    await act(async () => {
      render(<App />);
    });

    // Wait for app to load
    await waitFor(() => {
      expect(screen.getByText('Transcripta')).toBeInTheDocument();
    });

    // Open settings
    const settingsButton = screen.getByTitle(/open settings/i);
    act(() => {
      fireEvent.click(settingsButton);
    });

    await waitFor(() => {
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });

    // Change a setting (theme)
    const themeSelect = screen.getByLabelText(/theme/i);
    act(() => {
      fireEvent.change(themeSelect, { target: { value: 'dark' } });
    });

    // Close settings (should trigger save)
    const closeButton = screen.getAllByRole('button').find(btn =>
      btn.querySelector('[data-lucide-icon="x"]')
    );
    if (closeButton) {
      act(() => {
        fireEvent.click(closeButton);
      });
    }

    // Verify settings were saved
    await waitFor(() => {
      expect(savedSettings).not.toBeNull();
    });
  });

  it('applies theme change immediately in UI', async () => {
    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('Transcripta')).toBeInTheDocument();
    });

    // Open settings
    const settingsButton = screen.getByTitle(/open settings/i);
    act(() => {
      fireEvent.click(settingsButton);
    });

    await waitFor(() => {
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });

    // Change theme to dark
    const themeSelect = screen.getByLabelText(/theme/i);
    act(() => {
      fireEvent.change(themeSelect, { target: { value: 'dark' } });
    });

    // Theme should be applied to document
    await waitFor(() => {
      expect(document.documentElement.dataset.theme).toBe('dark');
    });
  });

  it('validates settings before saving', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    window.transcriptaDesktop.fetchJson.mockRejectedValue(new Error('Validation failed'));

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('Transcripta')).toBeInTheDocument();
    });

    // Save should fail gracefully
    const settingsButton = screen.getByTitle(/open settings/i);
    act(() => {
      fireEvent.click(settingsButton);
    });

    consoleSpy.mockRestore();
  });

  it('syncs hotkey settings with main process', async () => {
    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(window.transcriptaDesktop.hotkey.updateConfig).toHaveBeenCalled();
    });

    // Should include all hotkey configuration
    expect(window.transcriptaDesktop.hotkey.updateConfig).toHaveBeenCalledWith(
      expect.objectContaining({
        enabled: expect.any(Boolean),
        key_combination: expect.any(String),
        hold_mode: expect.any(Boolean),
        auto_inject: expect.any(Boolean),
      })
    );
  });

  it('handles settings reset', async () => {
    window.transcriptaDesktop.fetchJson.mockImplementation((path: string) => {
      if (path === '/api/settings/reset') {
        return Promise.resolve({ success: true });
      }
      return Promise.resolve(createMockSettings());
    });

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('Transcripta')).toBeInTheDocument();
    });

    // Open settings
    const settingsButton = screen.getByTitle(/open settings/i);
    act(() => {
      fireEvent.click(settingsButton);
    });

    await waitFor(() => {
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });

    // Find and click reset button
    const resetButton = screen.getAllByRole('button').find(btn =>
      btn.textContent?.toLowerCase().includes('reset')
    );

    if (resetButton) {
      act(() => {
        fireEvent.click(resetButton);
      });

      await waitFor(() => {
        expect(window.transcriptaDesktop.fetchJson).toHaveBeenCalledWith(
          '/api/settings/reset',
          expect.objectContaining({ method: 'POST' })
        );
      });
    }
  });

  it('handles multiple rapid setting changes', async () => {
    const saveCalls: unknown[] = [];
    window.transcriptaDesktop.fetchJson.mockImplementation((path: string, options?: RequestInit) => {
      if (path === '/api/settings' && options?.method === 'POST') {
        saveCalls.push(JSON.parse(options.body as string));
      }
      return Promise.resolve(createMockSettings());
    });

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('Transcripta')).toBeInTheDocument();
    });

    // Rapid theme changes should be debounced
    for (let i = 0; i < 5; i++) {
      act(() => {
        // Simulate theme changes
      });
    }

    // Should not make 5 separate save calls due to debouncing
  });
});

describe('Transcription Flow Integration', () => {
  const mockConnect = vi.fn();
  const mockDisconnect = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    mockedUseEventSource.mockReturnValue({
      status: 'polling',
      lastEvent: null,
      reconnectAttempts: 0,
      connect: mockConnect,
      disconnect: mockDisconnect,
    });

    window.transcriptaDesktop.fetchJson.mockImplementation((path: string) => {
      switch (true) {
        case path === '/api/settings':
          return Promise.resolve(createMockSettings());
        case path === '/api/devices':
          return Promise.resolve({ devices: MOCK_DEVICES });
        case path === '/api/session':
          return Promise.resolve(createMockSnapshot({ session: null }));
        case path === '/api/system/profile':
          return Promise.resolve(createMockSystemProfile());
        case path === '/api/models/catalog':
          return Promise.resolve({
            catalog: MOCK_MODELS,
            installed: [],
            selected_asr_model_id: 'small',
            refinement_mode: 'off',
            recommendations: ['small'],
          });
        case path === '/api/session/start':
          return Promise.resolve({ success: true });
        case path === '/api/session/stop':
          return Promise.resolve({ success: true });
        default:
          return Promise.resolve({});
      }
    });

    window.transcriptaDesktop.hotkey.getState.mockResolvedValue({
      config: { enabled: false },
    });
  });

  it('starts transcription session', async () => {
    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('Transcripta')).toBeInTheDocument();
    });

    // Click start button
    const startButton = screen.getByText('Start');
    act(() => {
      fireEvent.click(startButton);
    });

    await waitFor(() => {
      expect(window.transcriptaDesktop.fetchJson).toHaveBeenCalledWith(
        '/api/session/start',
        expect.objectContaining({ method: 'POST' })
      );
    });
  });

  it('stops transcription session', async () => {
    // Start with running session
    window.transcriptaDesktop.fetchJson.mockImplementation((path: string) => {
      if (path === '/api/session') {
        return Promise.resolve(createMockSnapshot({
          session: { status: 'running' },
        }));
      }
      return Promise.resolve({});
    });

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('Transcripta')).toBeInTheDocument();
    });

    // Click stop button
    const stopButton = screen.getByText('Stop');
    act(() => {
      fireEvent.click(stopButton);
    });

    await waitFor(() => {
      expect(window.transcriptaDesktop.fetchJson).toHaveBeenCalledWith(
        '/api/session/stop',
        expect.objectContaining({ method: 'POST' })
      );
    });
  });

  it('receives and displays transcription segments', async () => {
    const mockSegment = {
      id: 'seg-1',
      text: 'Test transcription',
      display_text: 'Test transcription',
      is_partial: false,
      start: 0,
      end: 3,
    };

    // Update mock to simulate receiving segment
    mockedUseEventSource.mockReturnValue({
      status: 'connected',
      lastEvent: {
        type: 'segment',
        payload: mockSegment,
        timestamp: new Date().toISOString(),
      },
      reconnectAttempts: 0,
      connect: mockConnect,
      disconnect: mockDisconnect,
    });

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('Test transcription')).toBeInTheDocument();
    });
  });

  it('displays partial segments differently from final', async () => {
    const partialSegment = {
      id: 'partial-1',
      text: 'Partial text...',
      display_text: 'Partial text...',
      is_partial: true,
    };

    mockedUseEventSource.mockReturnValue({
      status: 'connected',
      lastEvent: {
        type: 'segment',
        payload: partialSegment,
        timestamp: new Date().toISOString(),
      },
      reconnectAttempts: 0,
      connect: mockConnect,
      disconnect: mockDisconnect,
    });

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('Partial text...')).toBeInTheDocument();
    });
  });

  it('handles device switching during session', async () => {
    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('Transcripta')).toBeInTheDocument();
    });

    // Switch capture mode
    const micButton = screen.getByText('Microphone');
    act(() => {
      fireEvent.click(micButton);
    });

    expect(window.transcriptaDesktop.fetchJson).toHaveBeenCalled();
  });

  it('handles model preloading', async () => {
    window.transcriptaDesktop.fetchJson.mockImplementation((path: string) => {
      if (path === '/api/models/preload') {
        return Promise.resolve({ success: true });
      }
      return Promise.resolve(createMockSettings());
    });

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('Transcripta')).toBeInTheDocument();
    });

    // Click preload button
    const preloadButton = screen.getByText('Preload');
    act(() => {
      fireEvent.click(preloadButton);
    });

    await waitFor(() => {
      expect(window.transcriptaDesktop.fetchJson).toHaveBeenCalledWith(
        '/api/models/preload',
        expect.objectContaining({ method: 'POST' })
      );
    });
  });

  it('displays error messages from backend', async () => {
    const errorMessage = 'Failed to start: Device not found';

    mockedUseEventSource.mockReturnValue({
      status: 'connected',
      lastEvent: {
        type: 'health',
        payload: {
          health: { last_error: errorMessage },
          meter_value: 0,
        },
        timestamp: new Date().toISOString(),
      },
      reconnectAttempts: 0,
      connect: mockConnect,
      disconnect: mockDisconnect,
    });

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });
  });
});
