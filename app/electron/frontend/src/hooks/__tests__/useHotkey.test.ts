import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useHotkey } from '../useHotkey';
import { createMockHotkeyState } from '../../test/factories';

describe('useHotkey', () => {
  const mockHotkeyApi = {
    getState: vi.fn(),
    toggle: vi.fn(),
    updateConfig: vi.fn(),
    onStateChange: vi.fn(() => vi.fn()),
    removeStateChangeListener: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    
    Object.defineProperty(window, 'openwisprDesktop', {
      writable: true,
      value: {
        hotkey: mockHotkeyApi,
        floatingWindow: {
          show: vi.fn(),
          hide: vi.fn(),
        },
      },
    });

    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState());
  });

  it('initializes with loading state', () => {
    const { result } = renderHook(() => useHotkey());
    
    expect(result.current.isLoading).toBe(true);
    expect(result.current.state).toBeNull();
  });

  it('loads initial hotkey state', async () => {
    const mockState = createMockHotkeyState();
    mockHotkeyApi.getState.mockResolvedValue(mockState);

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.state).toEqual(mockState);
  });

  it('enables hotkey when enableHotkey is called', async () => {
    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState());
    mockHotkeyApi.toggle.mockResolvedValue(undefined);

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.enableHotkey();
    });

    expect(mockHotkeyApi.toggle).toHaveBeenCalledWith(true);
  });

  it('disables hotkey when disableHotkey is called', async () => {
    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState());
    mockHotkeyApi.toggle.mockResolvedValue(undefined);

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.disableHotkey();
    });

    expect(mockHotkeyApi.toggle).toHaveBeenCalledWith(false);
  });

  it('toggles hotkey state', async () => {
    mockHotkeyApi.getState
      .mockResolvedValueOnce(createMockHotkeyState({ config: { enabled: false } }))
      .mockResolvedValue(createMockHotkeyState({ config: { enabled: true } }));
    mockHotkeyApi.toggle.mockResolvedValue(undefined);

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.toggleHotkey();
    });

    expect(mockHotkeyApi.toggle).toHaveBeenCalledWith(true);
  });

  it('updates hotkey config', async () => {
    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState());
    mockHotkeyApi.updateConfig.mockResolvedValue(undefined);

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const newConfig = { enabled: true, key_combination: 'Ctrl+F1' };
    await act(async () => {
      await result.current.updateConfig(newConfig);
    });

    expect(mockHotkeyApi.updateConfig).toHaveBeenCalledWith(newConfig);
  });

  it('shows floating window when showFloatingWindow is called', async () => {
    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState());

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.showFloatingWindow();
    });

    expect(window.openwisprDesktop.floatingWindow.show).toHaveBeenCalled();
  });

  it('hides floating window when hideFloatingWindow is called', async () => {
    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState());

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.hideFloatingWindow();
    });

    expect(window.openwisprDesktop.floatingWindow.hide).toHaveBeenCalled();
  });

  it('handles errors gracefully', async () => {
    const errorMessage = 'Failed to load state';
    mockHotkeyApi.getState.mockRejectedValue(new Error(errorMessage));

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBe(errorMessage);
  });

  it('computes isEnabled correctly', async () => {
    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState({ config: { enabled: true } }));

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isEnabled).toBe(true);
    });
  });

  it('computes isActive correctly', async () => {
    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState({ 
      session: { is_recording: true, status: 'listening', session_id: '1', last_activated_at: null, total_activations: 1, current_text: '', duration_ms: 0 }
    }));

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isActive).toBe(true);
    });
  });

  it('calls onActivated callback when recording starts', async () => {
    const onActivated = vi.fn();
    let stateChangeHandler: ((event: unknown, state: unknown) => void) | null = null;

    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState({ 
      session: { is_recording: false, status: 'idle', session_id: '1', last_activated_at: null, total_activations: 0, current_text: '', duration_ms: 0 }
    }));
    mockHotkeyApi.onStateChange.mockImplementation((handler) => {
      stateChangeHandler = handler;
      return vi.fn();
    });

    renderHook(() => useHotkey({ onActivated }));

    await waitFor(() => {
      expect(mockHotkeyApi.onStateChange).toHaveBeenCalled();
    });

    // Simulate state change to listening
    if (stateChangeHandler) {
      act(() => {
        stateChangeHandler!(null, createMockHotkeyState({
          session: { is_recording: true, status: 'listening', session_id: '1', last_activated_at: new Date().toISOString(), total_activations: 1, current_text: '', duration_ms: 1000 }
        }));
      });
    }

    await waitFor(() => {
      expect(onActivated).toHaveBeenCalled();
    });
  });

  it('calls onTextReady callback when text changes', async () => {
    const onTextReady = vi.fn();
    let stateChangeHandler: ((event: unknown, state: unknown) => void) | null = null;

    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState({ session: { current_text: '' } }));
    mockHotkeyApi.onStateChange.mockImplementation((handler) => {
      stateChangeHandler = handler;
      return vi.fn();
    });

    renderHook(() => useHotkey({ onTextReady }));

    await waitFor(() => {
      expect(mockHotkeyApi.onStateChange).toHaveBeenCalled();
    });

    if (stateChangeHandler) {
      act(() => {
        stateChangeHandler!(null, createMockHotkeyState({
          session: { current_text: 'Transcribed text', is_recording: true, status: 'listening', session_id: '1', last_activated_at: null, total_activations: 1, duration_ms: 1000 }
        }));
      });
    }

    await waitFor(() => {
      expect(onTextReady).toHaveBeenCalledWith('Transcribed text');
    });
  });

  it('follows hotkey lifecycle transitions without activating during processing', async () => {
    const onActivated = vi.fn();
    const onDeactivated = vi.fn();
    let stateChangeHandler: ((event: unknown, state: unknown) => void) | null = null;

    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState());
    mockHotkeyApi.onStateChange.mockImplementation((handler) => {
      stateChangeHandler = handler;
      return vi.fn();
    });

    const { result } = renderHook(() => useHotkey({ onActivated, onDeactivated }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(mockHotkeyApi.onStateChange).toHaveBeenCalled();
    });

    act(() => {
      stateChangeHandler?.(
        null,
        createMockHotkeyState({
          session: {
            is_recording: false,
            status: 'processing',
            session_id: '1',
            last_activated_at: null,
            total_activations: 0,
            current_text: '',
            duration_ms: 50,
          },
        }),
      );
    });

    expect(result.current.status).toBe('processing');
    expect(result.current.isActive).toBe(false);
    expect(onActivated).not.toHaveBeenCalled();

    act(() => {
      stateChangeHandler?.(
        null,
        createMockHotkeyState({
          session: {
            is_recording: true,
            status: 'listening',
            session_id: '1',
            last_activated_at: null,
            total_activations: 1,
            current_text: '',
            duration_ms: 100,
          },
        }),
      );
    });

    expect(result.current.status).toBe('listening');
    expect(result.current.isActive).toBe(true);
    expect(onActivated).toHaveBeenCalledTimes(1);

    act(() => {
      stateChangeHandler?.(
        null,
        createMockHotkeyState({
          session: {
            is_recording: false,
            status: 'idle',
            session_id: '1',
            last_activated_at: null,
            total_activations: 1,
            current_text: '',
            duration_ms: 120,
          },
        }),
      );
    });

    expect(result.current.status).toBe('idle');
    expect(result.current.isActive).toBe(false);
    expect(onDeactivated).toHaveBeenCalledTimes(1);
  });

  it('cleans up event listeners on unmount', async () => {
    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState());

    const { unmount } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(mockHotkeyApi.onStateChange).toHaveBeenCalled();
    });

    unmount();

    expect(mockHotkeyApi.removeStateChangeListener).toHaveBeenCalledTimes(1);
  });
});
