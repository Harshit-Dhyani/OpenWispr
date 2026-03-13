---
title: Events and Streaming
audience: developers
last_verified: 2026-03-08
source_of_truth:
  - app/api/websocket_server.py
  - app/electron/frontend/src/hooks/useEventSource.ts
  - app/electron/frontend/src/hooks/useWebSocket.ts
  - app/api/server.py
---

# Events and Streaming

OpenWispr uses multiple real-time streaming mechanisms for communication between the Python backend and Electron frontend: Server-Sent Events (SSE) for unidirectional server-to-client streaming, and WebSockets for bidirectional communication.

## Streaming Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Electron Frontend                            │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │   Main Window    │  │ Floating Window  │  │  Quick Settings  │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │
│           │                     │                     │            │
│  ┌────────┴─────────────────────┴─────────────────────┴─────────┐  │
│  │              React Hooks (hooks/)                           │  │
│  │  ┌─────────────────┐  ┌─────────────────┐                    │  │
│  │  │ useEventSource  │  │  useWebSocket   │                    │  │
│  │  │ (SSE client)    │  │  (WS client)    │                    │  │
│  │  └────────┬────────┘  └────────┬────────┘                    │  │
│  └───────────┼────────────────────┼─────────────────────────────┘  │
└──────────────┼────────────────────┼────────────────────────────────┘
               │                    │
               │ HTTP/SSE           │ WebSocket
               │                    │
┌──────────────┼────────────────────┼────────────────────────────────┐
│              ▼                    ▼                                │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              FastAPI Server (app/api/server.py)              │ │
│  │  ┌───────────────────────────────────┐  ┌──────────────────────────────────┐  │ │
│  │  │ /api/events                       │  │ /api/ws                          │  │ │
│  │  │ /api/transcription/hotkey/events  │  │ /api/ws/settings                 │  │ │
│  │  │ (SSE endpoints)                   │  │ /api/ws/audio                    │  │ │
│  │  │                                   │  │ /api/transcription/hotkey/ws     │  │ │
│  │  │                                   │  │ (WebSocket endpoints)            │  │ │
│  │  └───────────────────────────────────┘  └──────────────────────────────────┘  │ │
│  │  ┌──────────────────────────────────────────────────────────┐ │ │
│  │  │      WebSocketManager (app/api/websocket_server.py)      │ │ │
│  │  │  - Connection pooling    - Rate limiting                 │ │ │
│  │  │  - Heartbeat/ping-pong   - Message queuing               │ │ │
│  │  │  - Compression           - Broadcast                     │ │ │
│  │  └──────────────────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────┘
```

## SSE Endpoints

| Endpoint | Location | Purpose |
|----------|----------|---------|
| `GET /api/events` | server.py:2363 | Main session events stream |
| `GET /api/transcription/hotkey/events` | server.py:2269 | Hotkey transcription events |

### Main Events Stream (`/api/events`)

Primary SSE endpoint for session events. Streams transcription progress, segments, and system status.

**Event Types**: Dynamic based on server events (see MessageType enum for possible values)

**Keepalive**: Sends `:\n\n` (SSE comment) every 15 seconds when no events pending.

**Example Connection**:
```javascript
const es = new EventSource('http://127.0.0.1:8765/api/events');
es.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.type, data.payload);
};
```

### Hotkey Events Stream (`/api/transcription/hotkey/events`)

Dedicated SSE stream for hotkey transcription sessions. Throttles audio level updates to 20fps.

**Event Types**:
- `hotkey_started`: Session began
- `hotkey_stopped`: Session ended with final text
- `hotkey_status`: Recording state and partial text
- `hotkey_audio_level`: Audio level with 36-band frequency data
- `hotkey_partial`: Draft/partial transcription
- `hotkey_commit_final`: Finalized segment
- `hotkey_error`: Session error

**Audio Throttling**: Audio level events limited to 50ms intervals (20fps max) to prevent flooding.

## WebSocket Endpoints

| Endpoint | Location | Purpose |
|----------|----------|---------|
| `WS /api/ws` | server.py:2623 | Main bidirectional communication |
| `WS /api/ws/settings` | server.py:2697 | Settings synchronization |
| `WS /api/ws/audio` | server.py:2762 | Audio visualization stream |
| `WS /api/transcription/hotkey/ws` | server.py:2180 | Hotkey session events |

### Main WebSocket (`/api/ws`)

Primary WebSocket for real-time transcription and bidirectional communication.

**Features**:
- Connection authentication on connect
- Settings synchronization via SettingsSynchronizer
- Transcription event broadcasting
- Heartbeat/ping-pong every 30 seconds

### Settings WebSocket (`/api/ws/settings`)

Dedicated endpoint for bidirectional settings synchronization.

**Message Types**:
- `SETTINGS_REQUEST`: Client requests current settings
- `SETTINGS_UPDATE`: Client sends settings changes
- `SETTINGS_RESPONSE`: Server acknowledges changes

### Audio Visualization WebSocket (`/api/ws/audio`)

Optimized stream for audio visualization data only.

**Features**:
- Throttled to 20fps (50ms intervals)
- Streams `AUDIO_LEVEL` messages with level, peak, and frequency bands
- Minimal overhead for floating window visualizer

### Hotkey WebSocket (`/api/transcription/hotkey/ws`)

Direct WebSocket for hotkey session events. Alternative to hotkey SSE endpoint.

**Features**:
- Initial status sent on connect
- Throttled audio level updates
- Client ping/pong handling

## Message Types

### WebSocket Message Types (app/api/websocket_server.py:35-75)

```python
class MessageType(str, Enum):
    # Transcription
    TRANSCRIPTION_PARTIAL = "transcription_partial"
    TRANSCRIPTION_FINAL = "transcription_final"
    TRANSCRIPTION_SEGMENT = "transcription_segment"
    
    # Audio visualization
    AUDIO_LEVEL = "audio_level"
    AUDIO_SPECTRUM = "audio_spectrum"
    
    # Settings
    SETTINGS_UPDATE = "settings_update"
    SETTINGS_REQUEST = "settings_request"
    SETTINGS_RESPONSE = "settings_response"
    
    # Health metrics
    HEALTH_METRICS = "health_metrics"
    SYSTEM_STATUS = "system_status"
    
    # Session events
    SESSION_STARTED = "session_started"
    SESSION_STOPPED = "session_stopped"
    SESSION_ERROR = "session_error"
    
    # Hotkey events
    HOTKEY_STARTED = "hotkey_started"
    HOTKEY_STOPPED = "hotkey_stopped"
    HOTKEY_PARTIAL = "hotkey_partial"
    HOTKEY_AUDIO_LEVEL = "hotkey_audio_level"
    HOTKEY_STATUS = "hotkey_status"
    
    # Connection management
    PING = "ping"
    PONG = "pong"
    KEEPALIVE = "keepalive"
    ERROR = "error"
    AUTH = "auth"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILED = "auth_failed"
```

### Message Format

```json
{
  "type": "transcription_partial",
  "payload": {
    "text": "hello world",
    "is_final": false
  },
  "timestamp": "2026-03-04T12:34:56.789Z"
}
```

## Frontend Hooks

### useEventSource (hooks/useEventSource.ts)

React hook for SSE connections with automatic reconnection.

```typescript
const {
  status,           // 'connected' | 'reconnecting' | 'polling' | 'error' | 'idle'
  lastEvent,        // Most recent event
  reconnectAttempts,// Number of reconnection attempts
  connect,          // Manual connect
  disconnect        // Manual disconnect
} = useEventSource({
  url: '/api/events',
  enabled: true,
  maxReconnectAttempts: 10,
  baseReconnectDelay: 1000,   // 1s initial
  maxReconnectDelay: 30000,   // 30s max
  pollInterval: 3000,         // Polling fallback every 3s
  onMessage: (event) => { },
  onError: (error) => { },
});
```

**Reconnection Strategy** (lines 231-239):
- Exponential backoff: `delay = min(1000 * 2^(attempt-1), 30000)`
- Polling fallback after max attempts: polls `/api/session` endpoint
- Deduplication via event IDs (sequence number + timestamp)

### useWebSocket (hooks/useWebSocket.ts)

React hook for WebSocket connections with heartbeat and buffering.

```typescript
const {
  status,           // 'connecting' | 'open' | 'closing' | 'closed' | 'reconnecting' | 'error'
  lastMessage,      // Most recent message
  reconnectAttempts,// Number of reconnection attempts
  bufferedMessages, // Messages queued while disconnected
  connect,
  disconnect,
  send,             // Send raw data
  sendJson,         // Send JSON object
  clearBuffer
} = useWebSocket({
  url: '/api/ws',
  protocols: undefined,       // Optional string or string[] for subprotocols
  maxReconnectAttempts: 10,
  baseReconnectDelay: 1000,
  maxReconnectDelay: 30000,
  heartbeatInterval: 30000,   // Send ping every 30s
  heartbeatMessage: JSON.stringify({ type: 'ping' }),
  bufferMessages: true,       // Queue while disconnected
  onMessage: (msg) => { },
  onError: (err) => { },
  onOpen: () => { },
  onClose: (event) => { },
  onReconnect: (attempt) => { },
});
```

**Heartbeat**: Sends `{ type: 'ping' }` every 30 seconds; expects server `pong`.

**Buffering**: Messages sent while disconnected are queued and flushed on reconnect.

**Message Deduplication** (lines 218-237):
```typescript
// Generate unique message ID
const messageId = data.id || `${data.type}-${data.timestamp}-${sequence}`;
if (processedMessageIds.has(messageId)) return;
// Limit set size to prevent unbounded growth
if (processedMessageIds.size > 1000) { /* clear half */ }
```

## Reconnection Strategy

### WebSocket Reconnection

Both frontend hooks implement consistent reconnection logic:

| Attempt | Delay | Total Wait |
|---------|-------|------------|
| 1 | 1s | 1s |
| 2 | 2s | 3s |
| 3 | 4s | 7s |
| 4 | 8s | 15s |
| 5+ | 16s → 30s cap | - |

**Conditions that trigger reconnect**:
- Connection error or unexpected close
- Heartbeat timeout (no pong within 60s)
- Manual disconnect followed by connect()

**Conditions that do NOT trigger reconnect**:
- Normal close (code 1000)
- Going away (code 1001)
- Manual disconnect without reconnect intent

### SSE Reconnection with Polling Fallback

The SSE hook adds a polling fallback after max reconnection attempts:

1. **SSE Mode**: Normal EventSource connection
2. **Reconnection**: Exponential backoff up to 10 attempts
3. **Polling Mode**: After 10 failed attempts, polls `/api/session` every 3 seconds
4. **Revision Tracking**: Uses `runtime_revision` to detect changes and emit events

## WebSocket Manager (app/api/websocket_server.py)

Server-side connection management with production-grade features.

### ConnectionConfig (lines 78-92)

```python
@dataclass
class ConnectionConfig:
    heartbeat_interval: float = 30.0      # Send ping every 30s
    heartbeat_timeout: float = 60.0       # Disconnect if no pong
    max_message_size: int = 1024 * 1024   # 1MB message limit
    compression_threshold: int = 1024     # Compress >1KB
    compression_level: int = 6            # gzip level
    rate_limit_messages: int = 100        # Per window
    rate_limit_window: float = 60.0       # 60 seconds
    message_queue_size: int = 1000        # Max queued messages
    max_connections_per_ip: int = 5       # IP-based limit
    allowed_origins: list[str] | None = None
    auth_required: bool = False
```

### Rate Limiting (lines 109-137)

Sliding window rate limiter per connection:
- 100 messages per 60-second window default
- Automatic cleanup of expired timestamps
- Returns `retry_after` seconds when limited

### Message Compression

Automatic gzip compression for messages >1KB:
```python
if len(data_bytes) > config.compression_threshold:
    compressed = gzip.compress(data_bytes, compresslevel=6)
    message["_compressed"] = True
    message["_data"] = compressed.hex()
```

Client must decompress using the `_data` hex field when `_compressed: true`.

### Broadcast Methods

```python
manager = get_websocket_manager()

# Broadcast to all connected clients
await manager.broadcast(MessageType.TRANSCRIPTION_PARTIAL, payload)

# Broadcast transcription updates
await manager.broadcast_transcription_partial(text, is_final)
await manager.broadcast_transcription_final(text, confidence, segments)

# Broadcast audio levels
await manager.broadcast_audio_level(level, peak, levels)

# Get connection stats
stats = manager.get_stats()
```

## Health Metrics Broadcast

Background task broadcasts health metrics every 5 seconds (app/api/server.py:3097-3135):

```python
metrics = {
    "timestamp": "2026-03-04T12:34:56.789Z",
    "health": { /* service health */ },
    "meter_value": 0.75,
    "model_cache": { /* cached models */ },
    "hotkey": {
        "is_recording": True,
        "session_id": "hotkey-abc123",
        "duration_ms": 5000
    },
    "websocket_stats": { /* connection stats */ }
}
```

## Security Considerations

1. **Origin Validation**: Configurable `allowed_origins` in ConnectionConfig
2. **Rate Limiting**: Per-connection message limits prevent flooding
3. **Message Size Limits**: 1MB max prevents memory exhaustion
4. **Connection Limits**: Max 5 connections per IP address
5. **Authentication**: Optional token-based auth via `AUTH` message type

## Error Handling

### SSE Error Handling

- `ConnectionResetError`, `CancelledError`: Graceful disconnect, no retry
- `asyncio.TimeoutError`: Send keepalive, continue
- Queue full: Drop event, log debug

### WebSocket Error Handling

- `WebSocketDisconnect`: Clean up connection, remove from pool
- Message parse error: Send `ERROR` type message to client
- Handler exception: Log, continue processing other handlers
- Heartbeat timeout: Close connection with code 1001
