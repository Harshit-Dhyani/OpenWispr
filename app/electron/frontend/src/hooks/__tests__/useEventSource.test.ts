import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useEventSource } from '../useEventSource';

describe('useEventSource', () => {
  let mockEventSource: EventSource | null = null;
  const mockOnMessage = vi.fn();
  const mockOnError = vi.fn();
  const mockOnOpen = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();

    // Mock EventSource
    class MockEventSource {
      url: string;
      onopen: ((this: EventSource, ev: Event) => unknown) | null = null;
      onmessage: ((this: EventSource, ev: MessageEvent) => unknown) | null = null;
      onerror: ((this: EventSource, ev: Event) => unknown) | null = null;
      readyState = 0;

      constructor(url: string | URL) {
        this.url = url.toString();
        mockEventSource = this as unknown as EventSource;
        
        // Simulate connection
        setTimeout(() => {
          this.readyState = 1;
          if (this.onopen) {
            this.onopen(new Event('open'));
          }
        }, 0);
      }

      close() {
        this.readyState = 2;
        mockEventSource = null;
      }
    }

    global.EventSource = MockEventSource as unknown as typeof EventSource;
  });

  afterEach(() => {
    vi.useRealTimers();
    mockEventSource = null;
  });

  it('initializes with idle status', () => {
    const { result } = renderHook(() =>
      useEventSource({
        url: '/api/events',
        onMessage: mockOnMessage,
      })
    );

    expect(result.current.status).toBe('idle');
    expect(result.current.lastEvent).toBeNull();
    expect(result.current.reconnectAttempts).toBe(0);
  });

  it('connects to EventSource on mount', async () => {
    const { result } = renderHook(() =>
      useEventSource({
        url: '/api/events',
        onMessage: mockOnMessage,
        onOpen: mockOnOpen,
      })
    );

    // Wait for connection
    await waitFor(() => {
      expect(mockOnOpen).toHaveBeenCalled();
    });

    expect(result.current.status).toBe('connected');
  });

  it('receives messages through EventSource', async () => {
    renderHook(() =>
      useEventSource({
        url: '/api/events',
        onMessage: mockOnMessage,
      })
    );

    await waitFor(() => {
      expect(mockEventSource).not.toBeNull();
    });

    const eventData = {
      type: 'segment',
      payload: { id: '1', text: 'Test' },
      timestamp: new Date().toISOString(),
    };

    // Simulate message
    act(() => {
      if (mockEventSource?.onmessage) {
        mockEventSource.onmessage(new MessageEvent('message', {
          data: JSON.stringify(eventData),
        }));
      }
    });

    await waitFor(() => {
      expect(mockOnMessage).toHaveBeenCalledWith(expect.objectContaining({
        type: 'segment',
        payload: { id: '1', text: 'Test' },
      }));
    });
  });

  it('disconnects when disconnect is called', async () => {
    const { result } = renderHook(() =>
      useEventSource({
        url: '/api/events',
        onMessage: mockOnMessage,
      })
    );

    await waitFor(() => {
      expect(mockEventSource).not.toBeNull();
    });

    act(() => {
      result.current.disconnect();
    });

    expect(mockEventSource).toBeNull();
  });

  it('reconnects when connect is called after disconnect', async () => {
    const { result } = renderHook(() =>
      useEventSource({
        url: '/api/events',
        onMessage: mockOnMessage,
        onOpen: mockOnOpen,
      })
    );

    await waitFor(() => {
      expect(mockOnOpen).toHaveBeenCalledTimes(1);
    });

    act(() => {
      result.current.disconnect();
    });

    mockOnOpen.mockClear();

    act(() => {
      result.current.connect();
    });

    await waitFor(() => {
      expect(mockOnOpen).toHaveBeenCalledTimes(1);
    });
  });

  it('tracks last received event', async () => {
    const { result } = renderHook(() =>
      useEventSource({
        url: '/api/events',
        onMessage: mockOnMessage,
      })
    );

    await waitFor(() => {
      expect(mockEventSource).not.toBeNull();
    });

    const eventData = {
      type: 'health',
      payload: { status: 'ok' },
      timestamp: new Date().toISOString(),
    };

    act(() => {
      if (mockEventSource?.onmessage) {
        mockEventSource.onmessage(new MessageEvent('message', {
          data: JSON.stringify(eventData),
        }));
      }
    });

    await waitFor(() => {
      expect(result.current.lastEvent).toEqual(expect.objectContaining({
        type: 'health',
        payload: { status: 'ok' },
      }));
    });
  });

  it('handles connection errors', async () => {
    renderHook(() =>
      useEventSource({
        url: '/api/events',
        onMessage: mockOnMessage,
        onError: mockOnError,
      })
    );

    await waitFor(() => {
      expect(mockEventSource).not.toBeNull();
    });

    act(() => {
      if (mockEventSource?.onerror) {
        mockEventSource.onerror(new Event('error'));
      }
    });

    await waitFor(() => {
      expect(mockOnError).toHaveBeenCalled();
    });
  });

  it('cleans up on unmount', async () => {
    const { unmount } = renderHook(() =>
      useEventSource({
        url: '/api/events',
        onMessage: mockOnMessage,
      })
    );

    await waitFor(() => {
      expect(mockEventSource).not.toBeNull();
    });

    unmount();

    expect(mockEventSource).toBeNull();
  });
});
