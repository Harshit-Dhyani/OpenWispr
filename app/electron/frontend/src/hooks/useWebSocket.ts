/**
 * useWebSocket - Hook for WebSocket connection management
 * 
 * Provides reactive WebSocket connection with auto-reconnect, heartbeat,
 * and message buffering capabilities.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

export type WebSocketStatus = 'connecting' | 'open' | 'closing' | 'closed' | 'reconnecting' | 'error';

export type WebSocketMessage = {
  type: string;
  payload: unknown;
  timestamp: string;
  id?: string;
};

type UseWebSocketOptions = {
  url: string;
  protocols?: string | string[];
  maxReconnectAttempts?: number;
  baseReconnectDelay?: number;
  maxReconnectDelay?: number;
  heartbeatInterval?: number;
  heartbeatMessage?: string;
  bufferMessages?: boolean;
  onMessage?: (message: WebSocketMessage) => void;
  onError?: (error: Error) => void;
  onOpen?: () => void;
  onClose?: (event: CloseEvent) => void;
  onReconnect?: (attempt: number) => void;
};

type UseWebSocketReturn = {
  status: WebSocketStatus;
  lastMessage: WebSocketMessage | null;
  reconnectAttempts: number;
  connect: () => void;
  disconnect: () => void;
  send: (data: string | ArrayBufferLike | Blob | ArrayBufferView) => void;
  sendJson: (data: unknown) => void;
  bufferedMessages: WebSocketMessage[];
  clearBuffer: () => void;
};

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const {
    url,
    protocols,
    maxReconnectAttempts = 10,
    baseReconnectDelay = 1000,
    maxReconnectDelay = 30000,
    heartbeatInterval = 30000,
    heartbeatMessage = JSON.stringify({ type: 'ping' }),
    bufferMessages = true,
    onMessage,
    onError,
    onOpen,
    onClose,
    onReconnect,
  } = options;

  const [status, setStatus] = useState<WebSocketStatus>('closed');
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [bufferedMessages, setBufferedMessages] = useState<WebSocketMessage[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const heartbeatIntervalRef = useRef<number | null>(null);
  const isManuallyClosedRef = useRef(false);
  const isConnectingRef = useRef(false);
  const reconnectAttemptsRef = useRef(0);
  const messageSequenceRef = useRef(0);
  const processedMessageIds = useRef<Set<string>>(new Set());
  const bufferRef = useRef<WebSocketMessage[]>([]);

  const resolveUrl = useCallback((path: string) => {
    if (path.startsWith('ws://') || path.startsWith('wss://')) {
      return path;
    }
    
    // Try to get API origin from Electron API
    const apiOrigin = typeof window !== 'undefined' && 
      (window as unknown as { openwisprDesktop?: { getApiOrigin?: () => Promise<string> } })?.openwisprDesktop?.getApiOrigin
      ? 'http://127.0.0.1:8765'
      : '';
    
    // Convert http to ws
    const baseUrl = apiOrigin.replace(/^http/, 'ws');
    return `${baseUrl}${path}`;
  }, []);

  const clearHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current !== null) {
      window.clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
  }, []);

  const startHeartbeat = useCallback(() => {
    clearHeartbeat();
    heartbeatIntervalRef.current = window.setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(heartbeatMessage);
      }
    }, heartbeatInterval);
  }, [clearHeartbeat, heartbeatInterval, heartbeatMessage]);

  const disconnect = useCallback(() => {
    isManuallyClosedRef.current = true;
    isConnectingRef.current = false;
    clearHeartbeat();

    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close(1000, 'Manual disconnect');
      }
      wsRef.current = null;
    }

    setStatus('closed');
  }, [clearHeartbeat]);

  const flushBuffer = useCallback(() => {
    if (bufferRef.current.length > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
      bufferRef.current.forEach((msg) => {
        try {
          wsRef.current?.send(JSON.stringify(msg));
        } catch {
          // Message failed to send, keep in buffer
        }
      });
      bufferRef.current = [];
      setBufferedMessages([]);
    }
  }, []);

  const send = useCallback((data: string | ArrayBufferLike | Blob | ArrayBufferView) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    } else if (bufferMessages && typeof data === 'string') {
      try {
        const parsed = JSON.parse(data);
        bufferRef.current.push(parsed);
        setBufferedMessages([...bufferRef.current]);
      } catch {
        // Non-JSON data can't be buffered
      }
    }
  }, [bufferMessages]);

  const sendJson = useCallback((data: unknown) => {
    send(JSON.stringify(data));
  }, [send]);

  const clearBuffer = useCallback(() => {
    bufferRef.current = [];
    setBufferedMessages([]);
  }, []);

  const connect = useCallback(() => {
    if (isConnectingRef.current || wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    isManuallyClosedRef.current = false;

    if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
      setStatus('error');
      onError?.(new Error(`Max reconnection attempts (${maxReconnectAttempts}) reached`));
      return;
    }

    isConnectingRef.current = true;
    setStatus(reconnectAttemptsRef.current > 0 ? 'reconnecting' : 'connecting');

    try {
      const wsUrl = resolveUrl(url);
      const ws = protocols ? new WebSocket(wsUrl, protocols) : new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttemptsRef.current = 0;
        setReconnectAttempts(0);
        setStatus('open');
        isConnectingRef.current = false;
        startHeartbeat();
        flushBuffer();
        onOpen?.();
      };

      ws.onmessage = (event) => {
        try {
          let data: WebSocketMessage;
          
          if (typeof event.data === 'string') {
            data = JSON.parse(event.data) as WebSocketMessage;
          } else {
            // Handle binary data
            data = {
              type: 'binary',
              payload: event.data,
              timestamp: new Date().toISOString(),
            };
          }

          // Generate unique message ID
          messageSequenceRef.current += 1;
          const messageId = data.id || `${data.type}-${data.timestamp}-${messageSequenceRef.current}`;
          
          if (processedMessageIds.current.has(messageId)) {
            return;
          }
          processedMessageIds.current.add(messageId);
          data.id = messageId;

          // Prevent unbounded growth
          if (processedMessageIds.current.size > 1000) {
            const iterator = processedMessageIds.current.values();
            const itemsToDelete = Math.floor(processedMessageIds.current.size / 2);
            for (let i = 0; i < itemsToDelete; i++) {
              const value = iterator.next().value;
              if (value) {
                processedMessageIds.current.delete(value);
              }
            }
          }

          setLastMessage(data);
          onMessage?.(data);
        } catch (error) {
          const err = error instanceof Error ? error : new Error('Failed to parse message');
          onError?.(err);
        }
      };

      ws.onclose = (event) => {
        wsRef.current = null;
        clearHeartbeat();
        isConnectingRef.current = false;
        setStatus('closed');
        onClose?.(event);

        if (isManuallyClosedRef.current) {
          return;
        }

        // Don't reconnect on normal close or going away
        if (event.code === 1000 || event.code === 1001) {
          return;
        }

        reconnectAttemptsRef.current += 1;
        const nextAttempt = reconnectAttemptsRef.current;
        setReconnectAttempts(nextAttempt);
        onReconnect?.(nextAttempt);

        const delay = Math.min(
          baseReconnectDelay * Math.pow(2, nextAttempt - 1),
          maxReconnectDelay
        );

        setStatus('reconnecting');
        reconnectTimeoutRef.current = window.setTimeout(() => {
          reconnectTimeoutRef.current = null;
          connect();
        }, delay);
      };

      ws.onerror = () => {
        isConnectingRef.current = false;
        setStatus('error');
        // Error handling is done in onclose
      };
    } catch (error) {
      isConnectingRef.current = false;
      setStatus('error');
      reconnectAttemptsRef.current += 1;
      const nextAttempt = reconnectAttemptsRef.current;
      setReconnectAttempts(nextAttempt);
      onError?.(error instanceof Error ? error : new Error('Failed to create WebSocket'));

      if (nextAttempt < maxReconnectAttempts) {
        const delay = Math.min(
          baseReconnectDelay * Math.pow(2, nextAttempt - 1),
          maxReconnectDelay
        );
        
        setStatus('reconnecting');
        reconnectTimeoutRef.current = window.setTimeout(() => {
          reconnectTimeoutRef.current = null;
          connect();
        }, delay);
      }
    }
  }, [
    url,
    protocols,
    maxReconnectAttempts,
    baseReconnectDelay,
    maxReconnectDelay,
    resolveUrl,
    startHeartbeat,
    clearHeartbeat,
    flushBuffer,
    onMessage,
    onError,
    onOpen,
    onClose,
    onReconnect,
  ]);

  useEffect(() => {
    connect();

    return () => {
      isManuallyClosedRef.current = true;
      isConnectingRef.current = false;
      clearHeartbeat();

      if (reconnectTimeoutRef.current !== null) {
        window.clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmount');
        wsRef.current = null;
      }
    };
  }, [connect, clearHeartbeat]);

  return {
    status,
    lastMessage,
    reconnectAttempts,
    connect,
    disconnect,
    send,
    sendJson,
    bufferedMessages,
    clearBuffer,
  };
}

export default useWebSocket;
