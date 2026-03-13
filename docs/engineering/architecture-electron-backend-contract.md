---
title: Electron-Backend Contract
audience: developers
last_verified: 2026-03-08
source_of_truth:
  - app/electron/main/preload/main.js
  - app/api/websocket_server.py
  - app/api/server.py
  - app/electron/main/ipc/handlers.js
---

# Electron-Backend Contract

This document defines the contract between the Electron main process and the Python backend service.

## Base Configuration

| Property | Value |
|----------|-------|
| API Origin | `http://127.0.0.1:8765` |
| WebSocket URL | `ws://127.0.0.1:8765/api/transcription/hotkey/ws` |
| SSE Endpoint | `/api/transcription/hotkey/events` |
| CORS Policy | Allow all origins (`*`) |

## IPC Channels

### File Dialogs

#### `choose-directory`
**Direction**: Renderer → Main (invoke)  
**Returns**: `string | null` - Selected directory path or null if cancelled

```javascript
const path = await window.openwisprDesktop.chooseDirectory();
```

#### `choose-pdf`
**Direction**: Renderer → Main (invoke)  
**Returns**: `string | null` - Selected PDF file path or null if cancelled

```javascript
const path = await window.openwisprDesktop.choosePdf();
```

### Hotkey Control

#### `hotkey:register`
**Direction**: Renderer → Main (invoke)  
**Payload**: `{ accelerator: string }`  
**Returns**: `{ success: boolean, accelerator?: string, error?: string, details?: object }`

Valid accelerators: `CommandOrControl+Shift+T`, `Alt+Space`, `F12`, etc.

```javascript
const result = await window.openwisprDesktop.hotkey.register("CommandOrControl+Shift+T");
```

#### `hotkey:unregister`
**Direction**: Renderer → Main (invoke)  
**Returns**: `{ success: boolean, wasRegistered?: boolean, error?: string }`

#### `hotkey:validate`
**Direction**: Renderer → Main (invoke)  
**Payload**: `{ accelerator: string }`  
**Returns**: `{ valid: boolean, available?: boolean, error?: string }`

#### `hotkey:toggle`
**Direction**: Renderer → Main (invoke)  
**Payload**: `boolean` (enabled state)  
**Returns**: `{ success: boolean, enabled: boolean }`

#### `hotkey:start`
**Direction**: Renderer → Main (invoke)  
**Payload**: `{ source?: 'microphone' | 'system' }`  
**Returns**: Hotkey start result from backend

#### `hotkey:stop`
**Direction**: Renderer → Main (invoke)  
**Returns**: Hotkey stop result from backend

#### `hotkey:get-state`
**Direction**: Renderer → Main (invoke)  
**Returns**: 
```typescript
{
  enabled: boolean;
  isRecording: boolean;
  accelerator: string;
  registered: boolean;
  defaultHotkey: string;
  mode: string;
  audioFeedback: boolean;
  config: HotkeyConfig;
  is_registered: boolean;
  session: {
    is_active: boolean;
    total_activations: number;
    last_activated_at: string | null;
  };
}
```

#### `hotkey:update-config`
**Direction**: Renderer → Main (invoke)  
**Payload**: `HotkeyConfig` object  
**Returns**: `{ success: boolean, config?: object, error?: string }`

#### `hotkey:get-default`
**Direction**: Renderer → Main (invoke)  
**Returns**: `{ accelerator: string, platform: string, note: string }` - Default hotkey for current platform

Config properties:
- `enabled: boolean` - Hotkey system enabled
- `key_combination: string` - Accelerator string
- `microphone_key_combination: string` - Microphone-specific hotkey
- `system_key_combination: string` - System audio hotkey
- `hold_mode: boolean` - Hold-to-record mode
- `auto_inject: boolean` - Auto-paste on finish
- `language: string` - Language code (e.g., "auto", "en")
- `capture_source: 'microphone' | 'system'` - Default capture source
- `device_id: string` - Device identifier
- `model_name: string` - ASR model (tiny, base, small, medium, large-v3)
- `finish_mode_default: 'finish' | 'finish_and_paste'` - Stop button behavior
- `show_floating_window: boolean` - Show overlay during recording
- `record_on_start: boolean` - Auto-start on app launch
- `stop_on_release: boolean` - Stop when hotkey released (hold mode)
- `copy_to_clipboard: boolean` - Copy result to clipboard

### Text Injection

#### `text:inject`
**Direction**: Renderer → Main (invoke)  
**Payload**: `string` (text to inject)  
**Returns**: `{ success: boolean, error?: string, method?: string }`

```javascript
const result = await window.openwisprDesktop.text.inject("Hello world");
```

### Tray

#### `tray:update-tooltip`
**Direction**: Renderer → Main (invoke)  
**Payload**: `string` (tooltip text)  
**Returns**: `{ success: boolean }`

### Model Management

#### `models:get-download-root`
**Direction**: Renderer → Main (invoke)  
**Returns**: `{ root: string }` - Path to models directory

#### `models:download`
**Direction**: Renderer → Main (invoke)  
**Payload**: `{ modelId: string }`  
**Returns**: Download result object

#### `models:cancel`
**Direction**: Renderer → Main (invoke)  
**Payload**: `{ modelId: string }`  
**Returns**: `{ ok: boolean, error?: string }`

#### `models:remove`
**Direction**: Renderer → Main (invoke)  
**Payload**: `{ modelId: string }`  
**Returns**: Removal result object

#### `model-download-event` (main → renderer)
**Direction**: Main → Renderer  
**Payload**: `{ event: string, payload: any }`

```javascript
const unsubscribe = window.openwisprDesktop.models.onDownloadEvent((data) => {
  console.log(data.event, data.payload);
});
```

#### `model-service:download`
**Direction**: Renderer → Main (invoke)  
**Payload**: `{ modelId: string, modelType: string, sourceUrl?: string, options?: object }`  
**Returns**: Download result with progress tracking

#### `model-service:get-target-path`
**Direction**: Renderer → Main (invoke)  
**Payload**: `{ modelId: string, modelType: string }`  **Returns**: `{ path: string }` - Target download path

### Quick Settings

**Note**: Quick Settings APIs are exposed via a separate preload script (`preload-quick-settings.js`) under `window.transcriptaQuickSettings`, not `window.openwisprDesktop`.

#### `quick-settings:get-data`
**Direction**: Renderer → Main (invoke)  
**Returns**: 
```typescript
{
  appName: string;
  settings: UserSettings;
  devices: AudioDevice[];
  languages: Array<{ code: string; label: string }>;
  hotkeyState: {
    enabled: boolean;
    accelerator: string;
    isRecording: boolean;
  };
}
```

```javascript
const data = await window.transcriptaQuickSettings.getData();
```

#### `quick-settings:update`
**Direction**: Renderer → Main (invoke)  
**Payload**: `UserSettings`  
**Returns**: `{ success: boolean }`

```javascript
await window.transcriptaQuickSettings.update({ language: "en", ... });
```

#### `quick-settings:open-full`
**Direction**: Renderer → Main (invoke)  
**Returns**: `{ success: boolean }`

```javascript
await window.transcriptaQuickSettings.openFullSettings();
```

#### `quick-settings:close`
**Direction**: Renderer → Main (invoke)  
**Returns**: `{ success: boolean }`

```javascript
await window.transcriptaQuickSettings.close();
```

### Main-to-Renderer Events

#### `backend-exit`
**Direction**: Main → Renderer  
Called when Python backend process exits unexpectedly.

```javascript
const unsubscribe = window.openwisprDesktop.onBackendExit((event) => {
  console.log("Backend exited");
});
```

#### `open-settings`
**Direction**: Main → Renderer  
Triggered by global shortcut (Ctrl+,) or tray menu.

```javascript
const unsubscribe = window.openwisprDesktop.onOpenSettings((event) => {
  // Navigate to settings page
});
```

#### `settings-updated`
**Direction**: Main → Renderer  
Broadcast when settings are changed via quick settings or tray.

#### `hotkey-state-change`
**Direction**: Main → Renderer  
**Payload**: `{ isRecording: boolean, hotkeyEnabled: boolean, accelerator: string }`

#### `hotkey-transcript-event`
**Direction**: Main → Renderer  
**Payload**: Transcript event data

#### `hotkey-registration-failed`
**Direction**: Main → Renderer  
**Payload**: `{ accelerator: string, error: string, details?: object }`  
Called when hotkey registration fails on startup.

#### `transcription-update`
**Direction**: Main → Floating Window  
**Payload**: `{ text: string, isPartial: boolean }`

#### `recording-state`
**Direction**: Main → Floating Window  
**Payload**: `{ isRecording: boolean, processing?: boolean, finished?: boolean }`

#### `audio-visualizer`
**Direction**: Main → Floating Window  
**Payload**: `{ levels: number[], peak: number }`

#### `hotkey-event`
**Direction**: Main → Floating Window  
**Payload**: `{ type: 'start' | 'stop' }` - Audio feedback trigger

## HTTP API Endpoints

### Health & Status

#### GET `/api/health`
**Response**:
```json
{
  "ok": true,
  "health": {
    "status": "healthy",
    "estimated_backlog_seconds": 0.0
  },
  "meter_value": 0.5,
  "model_cache": {},
  "hotkey": {
    "is_recording": false,
    "session_id": null,
    "duration_ms": 0
  }
}
```

### Device Management

#### GET `/api/devices`
**Response**:
```json
{
  "devices": [
    {
      "id": "device-uuid",
      "name": "Microphone Name",
      "is_input": true,
      "is_loopback": false,
      "supports_loopback": true,
      "kind": "microphone"
    }
  ]
}
```

#### GET `/api/devices/{device_id}/probe?duration=3.0`
**Response**:
```json
{
  "ok": true,
  "device_id": "device-uuid",
  "audio_stats": {
    "rms": 0.05,
    "peak": 0.8,
    "duration_ms": 3000
  }
}
```

### Settings

#### GET `/api/settings`
**Response**: Full user settings object

#### POST `/api/settings`
**Request**: Settings object to update  
**Response**: Updated settings

### Sessions

#### POST `/api/session/start`
**Request**:
```json
{
  "title": "Session Title",
  "output_root": "/path/to/output",
  "model_name": "small",
  "language_mode": "auto",
  "capture_source": "microphone",
  "device_id": "device-uuid",
  "live_mode": "balanced",
  "execution_mode": "auto"
}
```

#### POST `/api/session/stop`
**Response**: Session summary with transcript

#### GET `/api/session`
**Response**: Current session snapshot

### Hotkey Transcription

#### POST `/api/transcription/hotkey/start`
**Request**:
```json
{
  "capture_source": "microphone",
  "device_id": "device-uuid",
  "model_name": "small",
  "language_mode": "auto",
  "execution_mode": "auto"
}
```
**Response**:
```json
{
  "session_id": "hotkey-abc123",
  "status": "recording",
  "message": "Hotkey session started"
}
```

#### POST `/api/transcription/hotkey/stop`
**Request**:
```json
{
  "mode": "finish_and_paste"
}
```
**Response**:
```json
{
  "session_id": "hotkey-abc123",
  "status": "idle",
  "final_transcription": "Transcribed text",
  "aggregated_raw_text": "Raw text",
  "aggregated_clean_text": "Cleaned text",
  "postprocessed_text": "Post-processed text",
  "paste_text": "Text to paste",
  "coach_result": null,
  "coach_status": "disabled",
  "duration_ms": 5000,
  "segment_count": 3,
  "source_backend": "wasapi"
}
```

#### GET `/api/transcription/hotkey/status`
**Response**:
```json
{
  "state": "recording",
  "is_recording": true,
  "partial_text": "Current partial...",
  "raw_partial_text": "Raw partial...",
  "display_partial_text": "Display partial...",
  "audio_level": 0.5,
  "session_id": "hotkey-abc123",
  "correlation_id": "hotkey-abc123",
  "duration_ms": 3000,
  "levels": [0.1, 0.2, ...]  // 36 frequency bars
}
```

#### POST `/api/transcription/hotkey/inject`
**Request**: `{ "text": "Text to inject" }`  
**Response**: `{ "success": true, "message": "..." }`

#### POST `/api/hotkey/config`
**Request**:
```json
{
  "chunk_seconds": 1.4,
  "overlap_seconds": 0.25,
  "vad_threshold_db": -40.0,
  "vad_min_silence_ms": 200,
  "vad_speech_pad_ms": 200,
  "confidence_threshold": 0.35,
  "enable_filler_filter": false
}
```

### Models

#### GET `/api/models/catalog`
**Response**: Available models catalog

#### GET `/api/models/state`
**Response**: `{ "installed": { ... } }`

#### POST `/api/models/preload`
**Request**: `{ "model_name": "small", "execution_mode": "auto" }`  
**Response**: Preload status

#### POST `/api/models/select`
**Request**: `{ "category": "asr", "model_id": "whisper-medium" }`

#### POST `/api/models/refinement-mode`
**Request**: `{ "mode": "polished" }`  
Valid modes: `off`, `strict`, `polished`

### Coach & Refiner

#### GET `/api/refiner/status`
**Response**:
```json
{
  "runtime_enabled": true,
  "import_available": true,
  "selected_model_id": "model-id",
  "model_installed": true,
  "available": true,
  "reason": null
}
```

#### POST `/api/coach/prompt-preview`
**Request**: Coach preview context  
**Response**: Compiled prompt preview

## WebSocket Endpoints

### `/api/ws`

Main WebSocket endpoint for real-time transcription and system events.

**Connection URL**: `ws://127.0.0.1:8765/api/ws`

**Features**:
- Auto-reconnect with exponential backoff
- Heartbeat/ping-pong (30s interval, 60s timeout)
- Message queuing during reconnect
- Compression for messages > 1KB
- Connection pooling and rate limiting

**Protocol**:
1. Client connects and receives `auth_success` with `{ connected: true }`
2. Server sends current session state via `session_started`
3. Server sends current settings
4. Server streams: `transcription_partial`, `transcription_final`, `audio_level`, `health_metrics`
5. Client sends: `ping`, `settings_request`, `settings_update`
6. Heartbeat every 30s with ping/pong

**Message Types**: See [Message Types Reference](#message-types-reference)

---

### `/api/ws/settings`

Dedicated WebSocket for bidirectional settings synchronization.

**Connection URL**: `ws://127.0.0.1:8765/api/ws/settings`

**Capabilities**:
- Receive settings updates immediately when they change
- Send settings changes that apply immediately
- Request current settings state via `settings_request`

**Client → Server Messages**:
```json
{ "type": "settings_request", "payload": {} }
{ "type": "settings_update", "payload": { "category": "general", ... } }
```

**Server → Client Messages**:
```json
{ "type": "settings_response", "payload": { "settings": {...}, "success": true } }
```

---

### `/api/ws/audio`

WebSocket endpoint for real-time audio visualization data.

**Connection URL**: `ws://127.0.0.1:8765/api/ws/audio`

**Streams**:
- `audio_level` - Current audio level (0.0 to 1.0)
- `audio_spectrum` - Frequency spectrum data (36 bands)

**Throttling**: Updates throttled to 20fps (50ms) to reduce bandwidth.

---

### `/api/transcription/hotkey/ws`

Bidirectional WebSocket for real-time hotkey updates.

**Connection URL**: `ws://127.0.0.1:8765/api/transcription/hotkey/ws`

#### Connection Flow

1. Client connects
2. Server accepts and sends initial `hotkey_status`
3. Server streams events during recording
4. Connection closes on session end or client disconnect

#### Client → Server Messages

**Ping**:
```json
{ "action": "ping" }
```

#### Server → Client Messages

All messages use format:
```json
{
  "type": "message_type",
  "payload": { ... },
  "timestamp": "2026-03-04T12:00:00+00:00"
}
```

**Hotkey-Specific Message Types**:

| Type | Payload | Description |
|------|---------|-------------|
| `hotkey_status` | Full status object | Initial and periodic status |
| `hotkey_started` | `{ session_id, started_at, state, is_recording }` | Recording started |
| `hotkey_stopped` | Full stop response | Recording stopped with results |
| `hotkey_partial` | `{ partial_text, audio_level }` | Partial transcription |
| `hotkey_draft_partial` | Draft stream payload | In-progress draft text |
| `hotkey_commit_final` | Stream payload with segment | Finalized segment |
| `hotkey_audio_level` | `{ audio_level, levels[], peak }` | Audio visualization data (36 bars) |
| `hotkey_stop_ack` | `{ session_id, duration_ms, reason }` | Stop acknowledged |
| `hotkey_stopping` | `{ session_id, duration_ms, state }` | Finalizing in progress |
| `hotkey_error` | `{ session_id, error, state }` | Error occurred |
| `pong` | `{}` | Ping response |
| `keepalive` | `{}` | Connection keepalive |

**Audio Level Payload**:
```json
{
  "session_id": "hotkey-abc123",
  "audio_level": 0.5,
  "levels": [0.1, 0.3, 0.5, 0.8, 0.6, ...],  // 36 frequency bands
  "peak": 0.85
}
```

## SSE Endpoints

### `/api/events`

Main SSE endpoint for transcription and session events.

#### Connection

```javascript
const eventSource = new EventSource('http://127.0.0.1:8765/api/events');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.type, data.payload);
};
```

#### Event Types

Streams all transcription events including:
- `transcription_partial` - Live partial transcription
- `transcription_final` - Final transcription segment
- `segment` - Completed segment
- `meter` - Audio level data
- `session` - Session state changes

---

### `/api/transcription/hotkey/events`

Server-Sent Events alternative to WebSocket for hotkey updates.

#### Connection

```javascript
const eventSource = new EventSource('http://127.0.0.1:8765/api/transcription/hotkey/events');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.type, data.payload);
};
```

#### Event Format

```
data: {"type": "hotkey_status", "payload": {...}}

data: {"type": "hotkey_audio_level", "payload": {...}, "timestamp": "..."}

:  // keepalive comment
```

**Throttling**: Audio level updates are throttled to 20fps (50ms) to reduce bandwidth.

**Headers**:
```
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

## Global Shortcuts

### Registration

Global shortcuts are registered via Electron's `globalShortcut` API:

```javascript
globalShortcut.register("CommandOrControl+Shift+T", () => {
  void toggleRecording();
});
```

### Debouncing

All hotkey presses are debounced with 150ms threshold to prevent double-fires:

```javascript
const HOTKEY_DEBOUNCE_MS = 150;

if (now - lastHotkeyPressTime < HOTKEY_DEBOUNCE_MS) {
  return; // Ignored
}
lastHotkeyPressTime = now;
```

### Valid Accelerators

**Modifiers**: `Command`, `Cmd`, `Control`, `Ctrl`, `CommandOrControl`, `CmdOrCtrl`, `Alt`, `Option`, `Shift`, `Super`, `Meta`

**Special Keys**: `F1-F24`, `Plus`, `Space`, `Tab`, `Backspace`, `Delete`, `Insert`, `Return`, `Enter`, `Up`, `Down`, `Left`, `Right`, `Home`, `End`, `PageUp`, `PageDown`, `Escape`, `Esc`, `VolumeUp`, `VolumeDown`, `VolumeMute`, `MediaNextTrack`, `MediaPreviousTrack`, `MediaStop`, `MediaPlayPause`, `PrintScreen`

**Key Codes**: Single alphanumeric characters `a-z`, `A-Z`, `0-9`

## Port Configuration

| Port | Purpose | Configurable |
|------|---------|--------------|
| 8765 | Backend HTTP API | No (hardcoded) |
| 8765 | WebSocket | No (shares HTTP port) |
| 8765 | SSE | No (shares HTTP port) |

## Message Types Reference

### WebSocket MessageType Enum

```python
class MessageType(str, Enum):
    # Transcription
    TRANSCRIPTION_PARTIAL = "transcription_partial"
    TRANSCRIPTION_FINAL = "transcription_final"
    TRANSCRIPTION_SEGMENT = "transcription_segment"
    
    # Audio
    AUDIO_LEVEL = "audio_level"
    AUDIO_SPECTRUM = "audio_spectrum"
    
    # Settings
    SETTINGS_UPDATE = "settings_update"
    SETTINGS_REQUEST = "settings_request"
    SETTINGS_RESPONSE = "settings_response"
    
    # System
    HEALTH_METRICS = "health_metrics"
    SYSTEM_STATUS = "system_status"
    
    # Sessions
    SESSION_STARTED = "session_started"
    SESSION_STOPPED = "session_stopped"
    SESSION_ERROR = "session_error"
    
    # Hotkey
    HOTKEY_STARTED = "hotkey_started"
    HOTKEY_STOPPED = "hotkey_stopped"
    HOTKEY_PARTIAL = "hotkey_partial"
    HOTKEY_AUDIO_LEVEL = "hotkey_audio_level"
    HOTKEY_STATUS = "hotkey_status"
    
    # Connection
    PING = "ping"
    PONG = "pong"
    KEEPALIVE = "keepalive"
    ERROR = "error"
    AUTH = "auth"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILED = "auth_failed"
```

## Error Handling

### HTTP Errors

All HTTP errors return consistent format:
```json
{
  "detail": "Error message"
}
```

Common status codes:
- `503`: Service not ready
- `400`: Bad request / validation error
- `500`: Internal server error
- `404`: Endpoint not found

### WebSocket Errors

Errors sent as typed messages:
```json
{
  "type": "error",
  "payload": {
    "message": "Error description",
    "code": "ERROR_CODE"
  }
}
```

### IPC Errors

IPC handlers return error objects:
```javascript
{
  success: false,
  error: "Error message",
  details: { /* additional context */ }
}
```

## Data Safety

All payload data is passed through `make_json_safe()` to handle:
- NumPy scalars/arrays
- Python dataclasses
- datetime objects
- Path objects
- Other non-JSON-serializable types

This ensures WebSocket/SSE messages are always valid JSON.
