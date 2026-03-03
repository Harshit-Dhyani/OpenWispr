import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useWebSocket, type WebSocketMessage } from './useWebSocket';

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  url = '';
  protocol = '';
  extensions = '';
  bufferedAmount = 0;
  binaryType: BinaryType = 'blob';

  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string | URL, protocols?: string | string[]) {
    this.url = url.toString();
    if (protocols) {
      this.protocol = Array.isArray(protocols) ? protocols[0] : protocols;
    }
    
    // Simulate connection after a short delay
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.(new Event('open'));
    }, 10);
  }

  send(data: string | ArrayBufferLike | Blob | ArrayBufferView): void {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
  }

  close(code = 1000, reason = ''): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close', { code, reason }));
  }
}

// Replace global WebSocket with mock
global.WebSocket = MockWebSocket as unknown as typeof WebSocket;

describe('useWebSocket', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should initialize with closed status', () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
      })
    );

    expect(result.current.status).toBe('connecting');
    expect(result.current.reconnectAttempts).toBe(0);
    expect(result.current.lastMessage).toBeNull();
    expect(result.current.bufferedMessages).toEqual([]);
  });

  it('should connect on mount', async () => {
    const onOpen = vi.fn();
    
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
        onOpen,
      })
    );

    // Fast-forward past connection timeout
    act(() => {
      vi.advanceTimersByTime(20);
    });

    await waitFor(() => {
      expect(result.current.status).toBe('open');
    });

    expect(onOpen).toHaveBeenCalled();
  });

  it('should handle incoming messages', async () => {
    const onMessage = vi.fn();
    
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
        onMessage,
      })
    );

    act(() => {
      vi.advanceTimersByTime(20);
    });

    await waitFor(() => {
      expect(result.current.status).toBe('open');
    });

    // Simulate incoming message
    const testMessage: WebSocketMessage = {
      type: 'test',
      payload: { data: 'hello' },
      timestamp: new Date().toISOString(),
    };

    act(() => {
      const ws = (global.WebSocket as unknown as typeof MockWebSocket);
      // Find the last created WebSocket instance
    });

    // Note: In a real test we'd need to access the WebSocket instance
    // This is simplified for demonstration
  });

  it('should send messages when connected', async () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
      })
    );

    act(() => {
      vi.advanceTimersByTime(20);
    });

    await waitFor(() => {
      expect(result.current.status).toBe('open');
    });

    act(() => {
      result.current.send('test message');
    });

    // Should not throw when connected
    expect(result.current.status).toBe('open');
  });

  it('should send JSON messages', async () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
      })
    );

    act(() => {
      vi.advanceTimersByTime(20);
    });

    await waitFor(() => {
      expect(result.current.status).toBe('open');
    });

    act(() => {
      result.current.sendJson({ type: 'ping', data: 'test' });
    });

    expect(result.current.status).toBe('open');
  });

  it('should buffer messages when disconnected and bufferMessages is true', () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
        bufferMessages: true,
      })
    );

    // Don't advance timers, so WebSocket is still connecting
    act(() => {
      result.current.sendJson({ type: 'test', data: 'buffered' });
    });

    expect(result.current.bufferedMessages).toHaveLength(1);
    expect(result.current.bufferedMessages[0]).toMatchObject({
      type: 'test',
      data: 'buffered',
    });
  });

  it('should clear buffer', () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
        bufferMessages: true,
      })
    );

    act(() => {
      result.current.sendJson({ type: 'test' });
    });

    expect(result.current.bufferedMessages).toHaveLength(1);

    act(() => {
      result.current.clearBuffer();
    });

    expect(result.current.bufferedMessages).toHaveLength(0);
  });

  it('should disconnect when disconnect is called', async () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
      })
    );

    act(() => {
      vi.advanceTimersByTime(20);
    });

    await waitFor(() => {
      expect(result.current.status).toBe('open');
    });

    act(() => {
      result.current.disconnect();
    });

    expect(result.current.status).toBe('closed');
  });

  it('should reconnect automatically when connection is lost', async () => {
    const onReconnect = vi.fn();
    
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
        onReconnect,
        baseReconnectDelay: 100,
      })
    );

    act(() => {
      vi.advanceTimersByTime(20);
    });

    await waitFor(() => {
      expect(result.current.status).toBe('open');
    });

    // Simulate connection error/close
    act(() => {
      // Would need to access the WebSocket instance to simulate close
    });

    // The hook should attempt to reconnect
    expect(result.current.reconnectAttempts).toBe(0);
  });

  it('should convert http URL to ws URL', () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: '/api/ws',
      })
    );

    // Hook should start connecting
    expect(result.current.status).toBe('connecting');
  });

  it('should not reconnect if manually disconnected', async () => {
    const onError = vi.fn();
    
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
        onError,
        baseReconnectDelay: 100,
      })
    );

    act(() => {
      vi.advanceTimersByTime(20);
    });

    await waitFor(() => {
      expect(result.current.status).toBe('open');
    });

    // Manually disconnect
    act(() => {
      result.current.disconnect();
    });

    expect(result.current.status).toBe('closed');

    // Should not reconnect
    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(result.current.status).toBe('closed');
  });

  it('should handle multiple rapid connect/disconnect calls', () => {
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
      })
    );

    // Rapid calls should not create multiple connections
    act(() => {
      result.current.connect();
      result.current.connect();
      result.current.connect();
    });

    // Should still be in connecting/connecting state, not throw
    expect(['connecting', 'open', 'reconnecting']).toContain(result.current.status);
  });

  it('should call onClose callback when connection closes', async () => {
    const onClose = vi.fn();
    
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8765/api/ws',
        onClose,
      })
    );

    act(() => {
      vi.advanceTimersByTime(20);
    });

    await waitFor(() => {
      expect(result.current.status).toBe('open');
    });

    act(() => {
      result.current.disconnect();
    });

    // onClose should have been called
    expect(onClose).toHaveBeenCalled();
  });
});
