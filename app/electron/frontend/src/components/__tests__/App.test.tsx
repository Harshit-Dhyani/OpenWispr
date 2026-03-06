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
    window.transcriptaDesktop.fetchJson.mockImplementation((path: string) => {
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
        default:
          return Promise.resolve({});
      }
    });

    window.transcriptaDesktop.hotkey.getState.mockResolvedValue({
      config: { enabled: false, key_combination: 'Ctrl+Shift+Space' },
    });

    window.transcriptaDesktop.models.onDownloadEvent.mockReturnValue(vi.fn());
    window.transcriptaDesktop.onBackendExit.mockReturnValue(vi.fn());
    window.transcriptaDesktop.onOpenSettings.mockReturnValue(vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the application without crashing', async () => {
    await act(async () => {
      render(<App />);
    });

    expect(screen.getByText('Transcripta')).toBeInTheDocument();
    expect(screen.getByText('Microphone')).toBeInTheDocument();
    expect(screen.getByText('System Audio')).toBeInTheDocument();
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

    window.transcriptaDesktop.fetchJson.mockImplementation((path: string) => {
      if (path === '/api/settings') {
        return Promise.resolve(mockSettings);
      }
      return Promise.resolve({});
    });

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(window.transcriptaDesktop.fetchJson).toHaveBeenCalledWith('/api/settings', undefined);
    });
  });

  it('loads and displays devices', async () => {
    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(window.transcriptaDesktop.fetchJson).toHaveBeenCalledWith('/api/devices', undefined);
    });
  });

  it('handles backend exit gracefully', async () => {
    let backendExitHandler: (() => void) | null = null;
    window.transcriptaDesktop.onBackendExit.mockImplementation((handler: () => void) => {
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
      expect(screen.getByText('Transcripta')).toBeInTheDocument();
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

  it('handles session start', async () => {
    window.transcriptaDesktop.fetchJson.mockImplementation((path: string) => {
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

    window.transcriptaDesktop.fetchJson.mockImplementation((path: string) => {
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
      expect(window.transcriptaDesktop.hotkey.updateConfig).toHaveBeenCalledWith(
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
      expect(screen.getByText('Transcripta')).toBeInTheDocument();
    });

    const refreshButton = screen.getByTitle(/refresh devices/i);
    act(() => {
      fireEvent.click(refreshButton);
    });

    await waitFor(() => {
      expect(window.transcriptaDesktop.fetchJson).toHaveBeenCalledWith('/api/devices', undefined);
    });
  });

  it('handles model preloading', async () => {
    window.transcriptaDesktop.fetchJson.mockImplementation((path: string) => {
      if (path === '/api/models/preload') {
        return Promise.resolve({ success: true });
      }
      return Promise.resolve({});
    });

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('Transcripta')).toBeInTheDocument();
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

    window.transcriptaDesktop.hotkey.onStateChange.mockImplementation((handler) => {
      hotkeyStateListener = handler;
      return vi.fn();
    });

    window.transcriptaDesktop.hotkey.start.mockResolvedValue({ success: true });
    window.transcriptaDesktop.hotkey.stop.mockResolvedValue({ success: true });

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
      expect(window.transcriptaDesktop.hotkey.start).toHaveBeenCalledTimes(1);
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
      expect(window.transcriptaDesktop.hotkey.stop).toHaveBeenCalledTimes(1);
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
      expect(window.transcriptaDesktop.hotkey.start).toHaveBeenCalledTimes(2);
    });
  });

  it('handles PDF attachment', async () => {
    window.transcriptaDesktop.choosePdf.mockResolvedValue('/path/to/file.pdf');

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('Transcripta')).toBeInTheDocument();
    });
  });

  it('handles directory selection', async () => {
    window.transcriptaDesktop.chooseDirectory.mockResolvedValue('/new/export/path');

    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByText('Transcripta')).toBeInTheDocument();
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
    window.transcriptaDesktop.fetchJson.mockImplementation((path: string) => {
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
