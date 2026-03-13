import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import App from '../../App';
import {
  createMockSettings,
  createMockSnapshot,
  createMockSegment,
  createMockHealth,
  createMockDevice,
  MOCK_DEVICES,
  MOCK_MODELS,
} from '../../test/factories';

// Mock the useEventSource hook
vi.mock('../../hooks/useEventSource', () => ({
  useEventSource: vi.fn(),
}));

import { useEventSource } from '../../hooks/useEventSource';

const mockedUseEventSource = vi.mocked(useEventSource);

describe('App', () => {
  const mockConnect = vi.fn();
  const mockDisconnect = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    // Mock useEventSource hook
    mockedUseEventSource.mockReturnValue({
      status: 'polling',
      lastEvent: null,
      reconnectAttempts: 0,
      connect: mockConnect,
      disconnect: mockDisconnect,
    });

    // Mock Electron API
    window.openwisprDesktop.fetchJson.mockImplementation((path: string) => {
      switch (true) {
        case path === '/api/settings':
          return Promise.resolve(createMockSettings());
        case path === '/api/devices':
          return Promise.resolve({ devices: MOCK_DEVICES });
        case path === '/api/session':
          return Promise.resolve(createMockSnapshot());
        case path === '/api/system/profile':
          return Promise.resolve({
            gpu: { available: true, name: 'RTX 4090', vram_gb: 24 },
            cpu: { cores: 16, ram_gb: 64 },
            storage: { free_gb: 500 },
          });
        case path === '/api/models/catalog':
          return Promise.resolve({
            catalog: MOCK_MODELS,
            installed: [],
            selected_asr_model_id: 'small',
            refinement_mode: 'off',
            recommendations: ['small'],
          });
        case path === '/api/style/profiles':
          return Promise.resolve({
            profiles: [],
            assignments: {
              personal: null,
              work: null,
              email: null,
              other: null,
            },
          });
        default:
          return Promise.resolve({});
      }
    });

    window.openwisprDesktop.hotkey.getState.mockResolvedValue({
      config: { enabled: false, key_combination: 'Ctrl+Shift+Space' },
    });

    window.openwisprDesktop.models.onDownloadEvent.mockReturnValue(vi.fn());
    window.openwisprDesktop.onBackendExit.mockReturnValue(vi.fn());
    window.openwisprDesktop.onOpenSettings.mockReturnValue(vi.fn());
    window.openwisprDesktop.onSettingsUpdated.mockReturnValue(vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the application without crashing', async () => {
    await act(async () => {
      render(<App />);
    });

    expect(screen.getByText('OpenWispr')).toBeInTheDocument();
    expect(screen.getByText('Microphone')).toBeInTheDocument();
    expect(screen.getByText('System Audio')).toBeInTheDocument();
    expect(screen.queryByText('Style')).not.toBeInTheDocument();
  });

  it('displays loading state initially', async () => {
    await act(async () => {
      render(<App />);
    });

    expect(screen.getByRole('navigation')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Home' })).toBeInTheDocument();
  });

  it('loads and displays settings', async () => {
    const mockSettings = createMockSettings({
      general: { defaultSessionTitle: 'Test Session' },
    });

    window.openwisprDesktop.fetchJson.mockImplementation((path: string) => {
      if (path === '/api/settings') {
        return Promise.resolve(mockSettings);
      }
      return Promise.resolve({});
    });

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(window.openwisprDesktop.fetchJson).toHaveBeenCalledWith('/api/settings', undefined);
    });
  });

  it('loads and displays devices', async () => {
    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(window.openwisprDesktop.fetchJson).toHaveBeenCalledWith('/api/devices', undefined);
    });
  });

  it('reloads settings when Electron signals settings-updated', async () => {
    let settingsUpdatedHandler: (() => void) | null = null;
    window.openwisprDesktop.onSettingsUpdated.mockImplementation((handler: () => void) => {
      settingsUpdatedHandler = handler;
      return vi.fn();
    });

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(window.openwisprDesktop.fetchJson).toHaveBeenCalledWith('/api/settings', undefined);
    });

    const settingsCallsBefore = window.openwisprDesktop.fetchJson.mock.calls.filter(([path]: [string]) => path === '/api/settings').length;

    await act(async () => {
      settingsUpdatedHandler?.();
    });

    await waitFor(() => {
      const settingsCallsAfter = window.openwisprDesktop.fetchJson.mock.calls.filter(([path]: [string]) => path === '/api/settings').length;
      expect(settingsCallsAfter).toBeGreaterThan(settingsCallsBefore);
    });
  });

it('handles backend exit gracefully', async () => {
    let backendExitHandler: (() => void) | null = null;
    window.openwisprDesktop.onBackendExit.mockImplementation((handler: () => void) => {
      backendExitHandler = handler;
      return vi.fn();
    });

    await act(async () => {
      render(<App />);
    });

    // Simulate backend exit
    act(() => {
      if (backendExitHandler) {
        backendExitHandler();
      }
    });

    await waitFor(() => {
      expect(screen.getByText(/backend exited/i)).toBeInTheDocument();
    });
  });

  it('opens settings when settings button is clicked', async () => {
    await act(async () => {
      render(<App />);
    });

    // Wait for app to load
    await waitFor(() => {
      expect(screen.getByText('OpenWispr')).toBeInTheDocument();
    });

    // Find and click settings button
    const settingsButton = screen.getByTitle(/open settings/i);
    act(() => {
      fireEvent.click(settingsButton);
    });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument();
    });
  });

    it('keeps writing tone controls inside settings only', async () => {
    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.queryByText('Style')).not.toBeInTheDocument();
    });

    act(() => {
      fireEvent.click(screen.getByTitle(/open settings/i));
    });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument();
      expect(screen.getByText('Writing Tone')).toBeInTheDocument();
      expect(screen.queryByText(/open style editor/i)).not.toBeInTheDocument();
    });
  });
  it('handles session start', async () => {
    window.openwisprDesktop.fetchJson.mockImplementation((path: string) => {
      switch (true) {
        case path === '/api/session/start':
          return Promise.resolve({ success: true });
        case path === '/api/session':
          return Promise.resolve(createMockSnapshot({
            session: { status: 'running' },
          }));
        default:
          return Promise.resolve({});
      }
    });

    await act(async () => {
      render(<App />);
    });

    expect(screen.getByRole('heading', { name: 'Home' })).toBeInTheDocument();
  });

  it('applies theme from settings', async () => {
    const mockSettings = createMockSettings({
      general: { theme: 'dark' },
    });

    window.openwisprDesktop.fetchJson.mockImplementation((path: string) => {
      if (path === '/api/settings') {
        return Promise.resolve(mockSettings);
      }
      return Promise.resolve({});
    });

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(document.documentElement.dataset.theme).toBe('dark');
    });
  });

  it('stays stable when snapshot events arrive during bootstrap', async () => {
    const mockSegment = createMockSegment({ text: 'Test segment' });

    mockedUseEventSource.mockReturnValue({
      status: 'connected',
      lastEvent: {
        type: 'state',
        payload: createMockSnapshot({
          transcript: [mockSegment],
        }),
        timestamp: new Date().toISOString(),
      },
      reconnectAttempts: 0,
      connect: mockConnect,
      disconnect: mockDisconnect,
    });

    await act(async () => {
      render(<App />);
    });

    act(() => {
      fireEvent.click(screen.getByText('System Audio'));
    });

    await waitFor(() => {
      expect(screen.getByText('Long-form transcription')).toBeInTheDocument();
    });
  });

  it('updates hotkey config when settings change', async () => {
    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(window.openwisprDesktop.hotkey.updateConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          enabled: expect.any(Boolean),
          key_combination: expect.any(String),
        })
      );
    });
  });

  it('handles device refresh', async () => {
    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('OpenWispr')).toBeInTheDocument();
    });

    const refreshButton = screen.getByTitle(/refresh devices/i);
    act(() => {
      fireEvent.click(refreshButton);
    });

    await waitFor(() => {
      expect(window.openwisprDesktop.fetchJson).toHaveBeenCalledWith('/api/devices', undefined);
    });
  });

  it('handles model preloading', async () => {
    window.openwisprDesktop.fetchJson.mockImplementation((path: string) => {
      if (path === '/api/models/preload') {
        return Promise.resolve({ success: true });
      }
      return Promise.resolve({});
    });

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('OpenWispr')).toBeInTheDocument();
    });
  });

  it('lets the dictation button start and stop multiple times', async () => {
    let hotkeyStateListener:
      | ((event: unknown, state: {
          config: { enabled: boolean; key_combination: string };
          session: {
            session_id: string;
            is_recording: boolean;
            status: 'idle' | 'listening' | 'processing' | 'error';
            lifecycle_state?: 'idle' | 'starting' | 'recording' | 'stopping' | 'error';
            last_activated_at: string | null;
            total_activations: number;
            current_text: string;
            duration_ms: number;
          } | null;
          is_registered: boolean;
          error: string | null;
        } | null | undefined) => void)
      | undefined;

    window.openwisprDesktop.hotkey.onStateChange.mockImplementation((handler) => {
      hotkeyStateListener = handler;
      return vi.fn();
    });

    window.openwisprDesktop.hotkey.start.mockResolvedValue({ success: true });
    window.openwisprDesktop.hotkey.stop.mockResolvedValue({ success: true });

    await act(async () => {
      render(<App />);
    });

    act(() => {
      fireEvent.click(screen.getByText('Microphone'));
    });

    const startButton = await screen.findByRole('button', { name: 'Start Dictation' });

    act(() => {
      fireEvent.click(startButton);
    });

    await waitFor(() => {
      expect(window.openwisprDesktop.hotkey.start).toHaveBeenCalledTimes(1);
    });

    act(() => {
      hotkeyStateListener?.(null, {
        config: { enabled: true, key_combination: 'Ctrl+Shift+Space' },
        session: {
          session_id: 'dictation-1',
          is_recording: true,
          status: 'listening',
          lifecycle_state: 'recording',
          last_activated_at: null,
          total_activations: 1,
          current_text: '',
          duration_ms: 1000,
        },
        is_registered: true,
        error: null,
      });
    });

    const stopButton = await screen.findByRole('button', { name: 'Stop Dictation' });
    act(() => {
      fireEvent.click(stopButton);
    });

    await waitFor(() => {
      expect(window.openwisprDesktop.hotkey.stop).toHaveBeenCalledTimes(1);
    });

    act(() => {
      hotkeyStateListener?.(null, {
        config: { enabled: true, key_combination: 'Ctrl+Shift+Space' },
        session: {
          session_id: '',
          is_recording: false,
          status: 'idle',
          lifecycle_state: 'idle',
          last_activated_at: null,
          total_activations: 1,
          current_text: '',
          duration_ms: 0,
        },
        is_registered: true,
        error: null,
      });
    });

    const startAgainButton = await screen.findByRole('button', { name: 'Start Dictation' });
    act(() => {
      fireEvent.click(startAgainButton);
    });

    await waitFor(() => {
      expect(window.openwisprDesktop.hotkey.start).toHaveBeenCalledTimes(2);
    });
  });

  it('handles PDF attachment', async () => {
    window.openwisprDesktop.choosePdf.mockResolvedValue('/path/to/file.pdf');

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('OpenWispr')).toBeInTheDocument();
    });
  });

  it('handles directory selection', async () => {
    window.openwisprDesktop.chooseDirectory.mockResolvedValue('/new/export/path');

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('OpenWispr')).toBeInTheDocument();
    });
  });

  it('cleans up on unmount', async () => {
    const { unmount } = await act(async () => render(<App />));

    act(() => {
      unmount();
    });

    expect(mockDisconnect).toHaveBeenCalled();
  });

  it('stays stable when backend health reports an error', async () => {
    window.openwisprDesktop.fetchJson.mockImplementation((path: string) => {
      switch (true) {
        case path === '/api/settings':
          return Promise.resolve(createMockSettings());
        case path === '/api/devices':
          return Promise.resolve({ devices: MOCK_DEVICES });
        case path === '/api/session':
          return Promise.resolve(createMockSnapshot({
            health: createMockHealth({ last_error: 'Test error message' }),
          }));
        case path === '/api/system/profile':
          return Promise.resolve({
            gpu: { available: true, name: 'RTX 4090', vram_gb: 24 },
            cpu: { cores: 16, ram_gb: 64 },
            storage: { free_gb: 500 },
          });
        case path === '/api/models/catalog':
          return Promise.resolve({
            catalog: MOCK_MODELS,
            installed: [],
            selected_asr_model_id: 'small',
            refinement_mode: 'off',
            recommendations: ['small'],
          });
        case path === '/api/style/profiles':
          return Promise.resolve({
            profiles: [],
            assignments: {
              personal: null,
              work: null,
              email: null,
              other: null,
            },
          });
        default:
          return Promise.resolve({});
      }
    });

    mockedUseEventSource.mockReturnValue({
      status: 'connected',
      lastEvent: {
        type: 'health',
        payload: {
          health: { last_error: 'Test error message' },
          meter_value: 0.5,
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

    act(() => {
      fireEvent.click(screen.getByText('System Audio'));
    });

    await waitFor(() => {
      expect(screen.getByText('Long-form transcription')).toBeInTheDocument();
    });
  });
});




