import { useCallback, useEffect, useRef, useState } from 'react';

export type ConnectionStatus = 'connected' | 'reconnecting' | 'polling' | 'error' | 'idle';

export type EventSourceEvent = {
  type: string;
  payload: unknown;
  timestamp: string;
};

type UseEventSourceOptions = {
  url: string;
  maxReconnectAttempts?: number;
  baseReconnectDelay?: number;
  maxReconnectDelay?: number;
  pollInterval?: number;
  onMessage?: (event: EventSourceEvent) => void;
  onError?: (error: Error) => void;
  onOpen?: () => void;
};

type UseEventSourceReturn = {
  status: ConnectionStatus;
  lastEvent: EventSourceEvent | null;
  reconnectAttempts: number;
  connect: () => void;
  disconnect: () => void;
};

export function useEventSource(options: UseEventSourceOptions): UseEventSourceReturn {
  const {
    url,
    maxReconnectAttempts = 10,
    baseReconnectDelay = 1000,
    maxReconnectDelay = 30000,
    pollInterval = 3000,
    onMessage,
    onError,
    onOpen,
  } = options;

  const [status, setStatus] = useState<ConnectionStatus>('idle');
  const [lastEvent, setLastEvent] = useState<EventSourceEvent | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  const eventSourceRef = useRef<EventSource | null>(null);
  const pollIntervalRef = useRef<number | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const isManuallyClosedRef = useRef(false);
  const isConnectingRef = useRef(false);
  const processedEventIds = useRef<Set<string>>(new Set());
  const apiOriginRef = useRef<string>('http://127.0.0.1:8765');
  const reconnectAttemptsRef = useRef(0);

  const resolveUrl = useCallback((path: string) => {
    if (path.startsWith('http')) {
      return path;
    }
    return `${apiOriginRef.current}${path}`;
  }, []);

  const disconnect = useCallback(() => {
    isManuallyClosedRef.current = true;
    isConnectingRef.current = false;

    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (pollIntervalRef.current !== null) {
      window.clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const startPolling = useCallback(() => {
    if (pollIntervalRef.current !== null) {
      window.clearInterval(pollIntervalRef.current);
    }

    setStatus('polling');

    pollIntervalRef.current = window.setInterval(async () => {
      try {
        const response = await fetch(resolveUrl(url).replace('/events', '/session'));
        if (response.ok) {
          const data = await response.json();
          const event: EventSourceEvent = {
            type: 'state',
            payload: data,
            timestamp: new Date().toISOString(),
          };
          setLastEvent(event);
          onMessage?.(event);
        }
      } catch (error) {
        const err = error instanceof Error ? error : new Error('Polling failed');
        onError?.(err);
      }
    }, pollInterval);
  }, [resolveUrl, url, pollInterval, onMessage, onError]);

  const connect = useCallback(() => {
    if (isConnectingRef.current) {
      return;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    isManuallyClosedRef.current = false;

    if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
      startPolling();
      return;
    }

    isConnectingRef.current = true;
    setStatus('reconnecting');

    try {
      const es = new EventSource(resolveUrl(url));
      eventSourceRef.current = es;

      es.onopen = () => {
        if (pollIntervalRef.current !== null) {
          window.clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
        reconnectAttemptsRef.current = 0;
        setReconnectAttempts(0);
        setStatus('connected');
        isConnectingRef.current = false;
        onOpen?.();
      };

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as EventSourceEvent;

          const eventId = `${data.type}-${data.timestamp}`;
          if (processedEventIds.current.has(eventId)) {
            return;
          }
          processedEventIds.current.add(eventId);

          if (processedEventIds.current.size > 1000) {
            const iterator = processedEventIds.current.values();
            const firstValue = iterator.next().value;
            if (firstValue) {
              processedEventIds.current.delete(firstValue);
            }
          }

          setLastEvent(data);
          onMessage?.(data);
        } catch (error) {
          const err = error instanceof Error ? error : new Error('Failed to parse event');
          onError?.(err);
        }
      };

      es.onerror = () => {
        es.close();
        eventSourceRef.current = null;
        isConnectingRef.current = false;

        if (isManuallyClosedRef.current) {
          return;
        }

        reconnectAttemptsRef.current += 1;
        const nextAttempt = reconnectAttemptsRef.current;
        setReconnectAttempts(nextAttempt);

        if (nextAttempt >= maxReconnectAttempts) {
          startPolling();
          return;
        }

        const delay = Math.min(
          baseReconnectDelay * Math.pow(2, nextAttempt - 1),
          maxReconnectDelay
        );

        reconnectTimeoutRef.current = window.setTimeout(() => {
          reconnectTimeoutRef.current = null;
          connect();
        }, delay);
      };
    } catch (error) {
      isConnectingRef.current = false;
      reconnectAttemptsRef.current += 1;
      const nextAttempt = reconnectAttemptsRef.current;
      setReconnectAttempts(nextAttempt);

      if (nextAttempt >= maxReconnectAttempts) {
        startPolling();
        return;
      }

      const delay = Math.min(
        baseReconnectDelay * Math.pow(2, nextAttempt - 1),
        maxReconnectDelay
      );

      reconnectTimeoutRef.current = window.setTimeout(() => {
        reconnectTimeoutRef.current = null;
        connect();
      }, delay);
    }
  }, [
    resolveUrl,
    url,
    maxReconnectAttempts,
    baseReconnectDelay,
    maxReconnectDelay,
    onMessage,
    onError,
    onOpen,
    startPolling,
  ]);

  useEffect(() => {
    let cancelled = false;

    const start = async () => {
      if (window.transcriptaDesktop?.getApiOrigin) {
        try {
          apiOriginRef.current = await window.transcriptaDesktop.getApiOrigin();
        } catch {
          apiOriginRef.current = 'http://127.0.0.1:8765';
        }
      }
      if (cancelled) {
        return;
      }

      reconnectAttemptsRef.current = 0;
      isManuallyClosedRef.current = false;
      isConnectingRef.current = false;
      connect();
    };

    void start();

    return () => {
      cancelled = true;
      isManuallyClosedRef.current = true;
      isConnectingRef.current = false;

      if (reconnectTimeoutRef.current !== null) {
        window.clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      if (pollIntervalRef.current !== null) {
        window.clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }

      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [connect]);

  return {
    status,
    lastEvent,
    reconnectAttempts,
    connect,
    disconnect,
  };
}
