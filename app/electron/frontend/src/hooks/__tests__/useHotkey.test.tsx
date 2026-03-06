import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useHotkey } from '../useHotkey';
import { createMockHotkeyState } from '../../test/factories';

describe('useHotkey', () => {
  const mockHotkeyApi = {
    getState: vi.fn(),
    toggle: vi.fn(),
    updateConfig: vi.fn(),
    onStateChange: vi.fn(),
    removeStateChangeListener: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Setup mock hotkey API
    window.transcriptaDesktop.hotkey = mockHotkeyApi;

    // Default mock implementations
    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState());
    mockHotkeyApi.toggle.mockResolvedValue(undefined);
    mockHotkeyApi.updateConfig.mockResolvedValue(undefined);
    mockHotkeyApi.onStateChange.mockReturnValue(vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('initializes with loading state', () => {
    const { result } = renderHook(() => useHotkey());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.state).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('loads initial hotkey state', async () => {
    const mockState = createMockHotkeyState({
      config: { enabled: true, key_combination: 'Ctrl+Shift+Space' },
    });
    mockHotkeyApi.getState.mockResolvedValue(mockState);

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.state).toEqual(mockState);
    expect(result.current.isEnabled).toBe(true);
  });

  it('handles error during state loading', async () => {
    mockHotkeyApi.getState.mockRejectedValue(new Error('Failed to load'));

    const { result } = await act(async () => renderHook(() => useHotkey()));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBe('Failed to load');
  });

  it('enables hotkey when enableHotkey is called', async () => {
    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState());

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
    mockHotkeyApi.getState.mockResolvedValue(
      createMockHotkeyState({ config: { enabled: true } })
    );

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.disableHotkey();
    });

    expect(mockHotkeyApi.toggle).toHaveBeenCalledWith(false);
  });

  it('toggles hotkey based on current state', async () => {
    mockHotkeyApi.getState.mockResolvedValue(
      createMockHotkeyState({ config: { enabled: false } })
    );

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.toggleHotkey();
    });

    expect(mockHotkeyApi.toggle).toHaveBeenCalledWith(true);
  });

  it('updates config successfully', async () => {
    const newConfig = { enabled: true, hold_mode: true };
    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState());

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.updateConfig(newConfig);
    });

    expect(mockHotkeyApi.updateConfig).toHaveBeenCalledWith(newConfig);
  });

  it('shows floating window', async () => {
    window.transcriptaDesktop.floatingWindow = {
      show: vi.fn().mockResolvedValue(undefined),
      hide: vi.fn().mockResolvedValue(undefined),
    };

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.showFloatingWindow();
    });

    expect(window.transcriptaDesktop.floatingWindow.show).toHaveBeenCalled();
  });

  it('hides floating window', async () => {
    window.transcriptaDesktop.floatingWindow = {
      show: vi.fn().mockResolvedValue(undefined),
      hide: vi.fn().mockResolvedValue(undefined),
    };

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.hideFloatingWindow();
    });

    expect(window.transcriptaDesktop.floatingWindow.hide).toHaveBeenCalled();
  });

  it('triggers onActivated callback when hotkey activates', async () => {
    const onActivated = vi.fn();
    let stateChangeHandler: ((event: unknown, state: unknown) => void) | null = null;

    mockHotkeyApi.onStateChange.mockImplementation((handler) => {
      stateChangeHandler = handler;
      return vi.fn();
    });

    mockHotkeyApi.getState.mockResolvedValue(
      createMockHotkeyState({ session: { status: 'idle' } })
    );

    renderHook(() => useHotkey({ onActivated }));

    await waitFor(() => {
      expect(mockHotkeyApi.onStateChange).toHaveBeenCalled();
    });

    // Simulate state change to listening
    act(() => {
      if (stateChangeHandler) {
        stateChangeHandler({}, createMockHotkeyState({ session: { status: 'listening' } }));
      }
    });

    expect(onActivated).toHaveBeenCalled();
  });

  it('triggers onDeactivated callback when hotkey deactivates', async () => {
    const onDeactivated = vi.fn();
    let stateChangeHandler: ((event: unknown, state: unknown) => void) | null = null;

    mockHotkeyApi.onStateChange.mockImplementation((handler) => {
      stateChangeHandler = handler;
      return vi.fn();
    });

    mockHotkeyApi.getState.mockResolvedValue(
      createMockHotkeyState({ session: { status: 'listening' } })
    );

    renderHook(() => useHotkey({ onDeactivated }));

    await waitFor(() => {
      expect(mockHotkeyApi.onStateChange).toHaveBeenCalled();
    });

    // Simulate state change from listening to idle
    act(() => {
      if (stateChangeHandler) {
        stateChangeHandler({}, createMockHotkeyState({ session: { status: 'idle' } }));
      }
    });

    expect(onDeactivated).toHaveBeenCalled();
  });

  it('triggers onTextReady callback when text is available', async () => {
    const onTextReady = vi.fn();
    let stateChangeHandler: ((event: unknown, state: unknown) => void) | null = null;

    mockHotkeyApi.onStateChange.mockImplementation((handler) => {
      stateChangeHandler = handler;
      return vi.fn();
    });

    mockHotkeyApi.getState.mockResolvedValue(
      createMockHotkeyState({ session: { current_text: '' } })
    );

    renderHook(() => useHotkey({ onTextReady }));

    await waitFor(() => {
      expect(mockHotkeyApi.onStateChange).toHaveBeenCalled();
    });

    // Simulate state change with new text
    act(() => {
      if (stateChangeHandler) {
        stateChangeHandler({}, createMockHotkeyState({ session: { current_text: 'Project status update' } }));
      }
    });

    expect(onTextReady).toHaveBeenCalledWith('Project status update');
  });

  it('triggers onError callback when error occurs', async () => {
    const onError = vi.fn();
    let stateChangeHandler: ((event: unknown, state: unknown) => void) | null = null;

    mockHotkeyApi.onStateChange.mockImplementation((handler) => {
      stateChangeHandler = handler;
      return vi.fn();
    });

    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState());

    renderHook(() => useHotkey({ onError }));

    await waitFor(() => {
      expect(mockHotkeyApi.onStateChange).toHaveBeenCalled();
    });

    // Simulate state change with error
    act(() => {
      if (stateChangeHandler) {
        stateChangeHandler({}, createMockHotkeyState({ error: 'Test error' }));
      }
    });

    expect(onError).toHaveBeenCalledWith('Test error');
  });

  it('computes isActive correctly', async () => {
    mockHotkeyApi.getState.mockResolvedValue(
      createMockHotkeyState({ session: { is_recording: true } })
    );

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isActive).toBe(true);
  });

  it('computes status correctly', async () => {
    mockHotkeyApi.getState.mockResolvedValue(
      createMockHotkeyState({ session: { status: 'listening' } })
    );

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.status).toBe('listening');
  });

  it('computes currentText correctly', async () => {
    mockHotkeyApi.getState.mockResolvedValue(
      createMockHotkeyState({ session: { current_text: 'Transcribed text' } })
    );

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.currentText).toBe('Transcribed text');
  });

  it('cleans up state change listener on unmount', async () => {
    const cleanup = vi.fn();
    mockHotkeyApi.onStateChange.mockReturnValue(cleanup);
    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState());

    const { result, unmount } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    act(() => {
      unmount();
    });

    // Cleanup should be handled by useEffect cleanup
    expect(cleanup).toHaveBeenCalled();
  });

  it('handles test hotkey flow', async () => {
    window.transcriptaDesktop.floatingWindow = {
      show: vi.fn().mockResolvedValue(undefined),
      hide: vi.fn().mockResolvedValue(undefined),
    };

    vi.useFakeTimers();

    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState());

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.testHotkey();
    });

    expect(mockHotkeyApi.toggle).toHaveBeenCalledWith(true);
    expect(window.transcriptaDesktop.floatingWindow.show).toHaveBeenCalled();

    // Fast-forward timers to trigger hide
    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(window.transcriptaDesktop.floatingWindow.hide).toHaveBeenCalled();

    vi.useRealTimers();
  });

  it('refreshes state after toggle', async () => {
    mockHotkeyApi.getState.mockResolvedValue(createMockHotkeyState());

    const { result } = renderHook(() => useHotkey());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.enableHotkey();
    });

    // Should reload state after toggle
    expect(mockHotkeyApi.getState).toHaveBeenCalledTimes(2);
  });

  it('handles missing hotkey API gracefully', async () => {
    // Remove hotkey API temporarily
    const originalHotkey = window.transcriptaDesktop.hotkey;
    window.transcriptaDesktop.hotkey = undefined as unknown as typeof window.transcriptaDesktop.hotkey;

    const { result } = renderHook(() => useHotkey());

    // Should handle gracefully without crashing
    expect(result.current.isLoading).toBe(true);

    // Restore
    window.transcriptaDesktop.hotkey = originalHotkey;
  });
});
