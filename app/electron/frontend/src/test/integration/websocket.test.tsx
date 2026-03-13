import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useWebSocket } from '../useWebSocket';

describe('useWebSocket Integration', () => {
  let mockWebSocketInstance: {
    onopen: ((ev: Event) => void) | null;
    onclose: ((ev: CloseEvent) => void) | null;
    onmessage: ((ev: MessageEvent) => void) | null;
    onerror: ((ev: Event) => void) | null;
    send: (data: string) => void;
    close: (code?: number, reason?: string) => void;
    readyState: number;
    url: string;
  } | null = null;

  const mockOnMessage = vi.fn();
  const mockOnError = vi.fn();
  const mockOnOpen = vi.fn();
  const mockOnClose = vi.fn();
  const mockOnReconnect = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    // Mock WebSocket
    global.WebSocket = vi.fn().mockImplementation((url: string) => {
      mockWebSocketInstance = {
        url,
        readyState: WebSocket.CONNECTING,
        onopen: null,
        onclose: null,
        onmessage: null,
        onerror: null,
        send: vi.fn(),
        close: vi.fn((code = 1000, reason = '') => {
          mockWebSocketInstance!.readyState = WebSocket.CLOSED;
          if (mockWebSocketInstance?.onclose) {
            mockWebSocketInstance.onclose(new CloseEvent('close', { code, reason }));
          }
        }),
      };

      // Auto-connect after short delay
      setTimeout(() => {
        if (mockWebSocketInstance) {
          mockWebSocketInstance.readyState = WebSocket.OPEN;
          if (mockWebSocketInstance.onopen) {
            mockWebSocketInstance.onopen(new Event('open'));
          }
        }
      }, 10);

      return mockWebSocketInstance;
    }) as unknown as typeof WebSocket;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    mockWebSocketInstance = null;
  });

  it('establishes WebSocket connection', async () => {
    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
        onOpen: mockOnOpen,
      })
    );

    await waitFor(() => {
      expect(mockOnOpen).toHaveBeenCalled();
    });

    expect(global.WebSocket).toHaveBeenCalledWith(
      'ws://localhost:8765/api/ws',
      undefined
    );
  });

  it('sends and receives messages', async () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
        onMessage: mockOnMessage,
        onOpen: mockOnOpen,
      })
    );

    await waitFor(() => {
      expect(mockOnOpen).toHaveBeenCalled();
    });

    const testMessage = {
      type: 'transcription',
      payload: { text: 'Project status update' },
      timestamp: new Date().toISOString(),
    };

    // Send message
    act(() => {
      result.current.sendJson(testMessage);
    });

    expect(mockWebSocketInstance?.send).toHaveBeenCalledWith(
      JSON.stringify(testMessage)
    );

    // Simulate receiving message
    act(() => {
      if (mockWebSocketInstance?.onmessage) {
        mockWebSocketInstance.onmessage(new MessageEvent('message', {
          data: JSON.stringify({
            type: 'ack',
            payload: { received: true },
            timestamp: new Date().toISOString(),
          }),
        }));
      }
    });

    await waitFor(() => {
      expect(mockOnMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'ack',
          payload: { received: true },
        })
      );
    });
  });

  it('handles connection loss and reconnection', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
        onReconnect: mockOnReconnect,
        baseReconnectDelay: 100,
      })
    );

    await waitFor(() => {
      expect(result.current.status).toBe('open');
    });

    // Simulate connection loss
    act(() => {
      if (mockWebSocketInstance?.onclose) {
        mockWebSocketInstance.onclose(new CloseEvent('close', {
          code: 1006,
          reason: 'Connection lost',
        }));
      }
    });

    // Fast-forward past reconnection delay
    act(() => {
      vi.advanceTimersByTime(150);
    });

    await waitFor(() => {
      expect(mockOnReconnect).toHaveBeenCalled();
      expect(result.current.reconnectAttempts).toBeGreaterThan(0);
    });

    vi.useRealTimers();
  });

  it('buffers messages when disconnected', async () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
        bufferMessages: true,
      })
    );

    // Don't wait for connection - send immediately
    act(() => {
      result.current.sendJson({ type: 'test', data: 'buffered' });
    });

    // Message should be buffered
    expect(result.current.bufferedMessages).toHaveLength(1);

    await waitFor(() => {
      expect(result.current.status).toBe('open');
    });

    // Buffered message should be flushed
    expect(result.current.bufferedMessages).toHaveLength(0);
  });

  it('implements heartbeat mechanism', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
        heartbeatInterval: 100,
        heartbeatMessage: JSON.stringify({ type: 'ping' }),
      })
    );

    await waitFor(() => {
      expect(result.current.status).toBe('open');
    });

    // Advance multiple heartbeat intervals
    for (let i = 0; i < 3; i++) {
      act(() => {
        vi.advanceTimersByTime(100);
      });
    }

    // Should have sent heartbeat messages
    const pingCalls = (mockWebSocketInstance?.send as ReturnType<typeof vi.fn>)?.mock?.calls?.filter(
      (call: unknown[]) => call[0] === JSON.stringify({ type: 'ping' })
    );
    expect(pingCalls?.length).toBeGreaterThanOrEqual(2);

    vi.useRealTimers();
  });

  it('handles multiple connection attempts gracefully', async () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
      })
    );

    // Rapid connect/disconnect cycles
    for (let i = 0; i < 5; i++) {
      act(() => {
        result.current.connect();
      });
      act(() => {
        result.current.disconnect();
      });
    }

    // Should handle gracefully without errors
    expect(result.current.status).toBe('closed');
  });

  it('handles protocol specification', async () => {
    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
        protocols: ['transcription-protocol'],
      })
    );

    expect(global.WebSocket).toHaveBeenCalledWith(
      'ws://localhost:8765/api/ws',
      ['transcription-protocol']
    );
  });

  it('provides connection status information', async () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
      })
    );

    // Initial state
    expect(result.current.status).toBe('connecting');
    expect(result.current.reconnectAttempts).toBe(0);

    await waitFor(() => {
      expect(result.current.status).toBe('open');
    });

    // After connection
    expect(result.current.lastMessage).toBeNull();
  });

  it('cleans up on unmount', async () => {
    const { unmount } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
      })
    );

    await waitFor(() => {
      expect(mockWebSocketInstance).not.toBeNull();
    });

    act(() => {
      unmount();
    });

    expect(mockWebSocketInstance?.close).toHaveBeenCalled();
  });

  it('handles binary data', async () => {
    const onMessage = vi.fn();

    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
        onMessage,
      })
    );

    await waitFor(() => {
      expect(mockWebSocketInstance).not.toBeNull();
    });

    // Simulate binary message
    const binaryData = new Uint8Array([1, 2, 3, 4, 5]);
    act(() => {
      if (mockWebSocketInstance?.onmessage) {
        mockWebSocketInstance.onmessage(new MessageEvent('message', {
          data: binaryData,
        }));
      }
    });

    await waitFor(() => {
      expect(onMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'binary',
        })
      );
    });
  });

  it('deduplicates messages by ID', async () => {
    const onMessage = vi.fn();

    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
        onMessage,
      })
    );

    await waitFor(() => {
      expect(mockWebSocketInstance).not.toBeNull();
    });

    const messageId = 'msg-123';
    const message = {
      id: messageId,
      type: 'test',
      payload: { data: 'test' },
      timestamp: new Date().toISOString(),
    };

    // Send same message twice
    act(() => {
      if (mockWebSocketInstance?.onmessage) {
        mockWebSocketInstance.onmessage(new MessageEvent('message', {
          data: JSON.stringify(message),
        }));
        mockWebSocketInstance.onmessage(new MessageEvent('message', {
          data: JSON.stringify(message),
        }));
      }
    });

    await waitFor(() => {
      // Should only receive once due to deduplication
      expect(onMessage).toHaveBeenCalledTimes(1);
    });
  });

  it('manages processed message ID set size', async () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
      })
    );

    await waitFor(() => {
      expect(mockWebSocketInstance).not.toBeNull();
    });

    // Send many messages to test ID set management
    for (let i = 0; i < 1100; i++) {
      act(() => {
        if (mockWebSocketInstance?.onmessage) {
          mockWebSocketInstance.onmessage(new MessageEvent('message', {
            data: JSON.stringify({
              id: `msg-${i}`,
              type: 'test',
              timestamp: new Date().toISOString(),
            }),
          }));
        }
      });
    }

    // System should continue functioning without memory issues
    expect(result.current.status).toBe('open');
  });
});
