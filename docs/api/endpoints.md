# Transcripta API Documentation

## Overview

Transcripta exposes a local REST API for the Electron frontend to communicate with the Python backend.

- **Base URL:** `http://127.0.0.1:8765`
- **Authentication:** None (local-only service)
- **Rate Limiting:** None (local-only service)
- **CORS:** Enabled for all origins (`*`)

---

## Health & Status

### GET /api/health

Health check with system metrics.

**Response:**
```json
{
  "ok": true,
  "health": {
    "status": "healthy",
    "estimated_backlog_seconds": 0.0
  },
  "meter_value": 0.75,
  "model_cache": {
    "small": "loaded",
    "medium": "loaded"
  },
  "hotkey": {
    "is_recording": false,
    "session_id": null,
    "duration_ms": 0
  }
}
```

**Example:**
```bash
curl http://127.0.0.1:8765/api/health
```

---

### GET /api/session

Full session state snapshot.

**Response:**
```json
{
  "session": {
    "id": "session-uuid",
    "title": "Meeting Transcript",
    "started_at": "2026-03-01T12:00:00Z",
    "output_path": "/path/to/output",
    "model_name": "small",
    "language_mode": "auto",
    "segments": []
  },
  "health": {},
  "meter_value": 0.0,
  "model_cache": {},
  "available_models": []
}
```

**Example:**
```bash
curl http://127.0.0.1:8765/api/session
```

---

## Devices

### GET /api/devices

List all audio devices (microphones and system audio).

**Response:**
```json
{
  "devices": [
    {
      "id": "device-1",
      "name": "Microphone (Realtek Audio)",
      "is_input": true,
      "is_output": false,
      "is_loopback": false,
      "supports_loopback": false,
      "is_default": true
    },
    {
      "id": "device-2",
      "name": "Stereo Mix (Realtek Audio)",
      "is_input": true,
      "is_output": false,
      "is_loopback": true,
      "supports_loopback": true,
      "is_default": false
    }
  ]
}
```

**Example:**
```bash
curl http://127.0.0.1:8765/api/devices
```

---

### GET /api/devices/{device_id}/probe

Probe a device to check if it's working and capture audio stats.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| duration | float | 3.0 | Probe duration in seconds |

**Response:**
```json
{
  "ok": true,
  "device_id": "device-1",
  "sample_rate": 16000,
  "channels": 1,
  "rms_level": 0.05,
  "peak_level": 0.12,
  "is_silent": false
}
```

**Example:**
```bash
curl "http://127.0.0.1:8765/api/devices/default/probe?duration=5.0"
```

---

## Models

### GET /api/models/catalog

Get the complete model catalog with categories.

**Response:**
```json
{
  "categories": {
    "asr": [
      {
        "id": "small",
        "name": "Small",
        "size": "466 MB",
        "description": "Fast, good accuracy",
        "recommended": true
      }
    ],
    "refiner": [
      {
        "id": "phi-4",
        "name": "Phi-4",
        "size": "2.4 GB",
        "description": "Local text refinement"
      }
    ]
  }
}
```

**Example:**
```bash
curl http://127.0.0.1:8765/api/models/catalog
```

---

### GET /api/models/cache

Get current model cache status.

**Response:**
```json
{
  "cached_models": {
    "small": "loaded",
    "medium": "loaded"
  },
  "available_models": ["tiny", "small", "medium", "large"]
}
```

**Example:**
```bash
curl http://127.0.0.1:8765/api/models/cache
```

---

### DELETE /api/models/cache

Clear all cached models to free memory.

**Response:**
```json
{
  "status": "cleared",
  "cleared": 2
}
```

**Example:**
```bash
curl -X DELETE http://127.0.0.1:8765/api/models/cache
```

---

### POST /api/models/preload

Preload a model into cache for instant session start.

**Request Body:**
```json
{
  "model_name": "small",
  "execution_mode": "auto"
}
```

**Response:**
```json
{
  "status": "loaded",
  "model_name": "small",
  "load_time_ms": 1500
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8765/api/models/preload \
  -H "Content-Type: application/json" \
  -d '{"model_name": "small", "execution_mode": "auto"}'
```

---

### GET /api/models/state

Get model installation state.

**Response:**
```json
{
  "installed": {
    "small": true,
    "medium": false
  }
}
```

**Example:**
```bash
curl http://127.0.0.1:8765/api/models/state
```

---

### POST /api/models/select

Select a model for a specific category.

**Request Body:**
```json
{
  "category": "asr",
  "model_id": "small"
}
```

Categories: `asr`, `refiner`

**Response:**
```json
{
  "ok": true,
  "selected_asr_model_id": "small",
  "selected_refiner_model_id": "phi-4"
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8765/api/models/select \
  -H "Content-Type: application/json" \
  -d '{"category": "asr", "model_id": "small"}'
```

---

### POST /api/models/refinement-mode

Set the text refinement mode.

**Request Body:**
```json
{
  "mode": "polished"
}
```

Modes: `off`, `strict`, `polished`

**Response:**
```json
{
  "ok": true,
  "refinement_mode": "polished"
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8765/api/models/refinement-mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "polished"}'
```

---

## Session Management

### POST /api/session/start

Start a new transcription session.

**Request Body (StartSessionRequest):**
```json
{
  "title": "Meeting Transcript",
  "output_root": "/path/to/output",
  "model_name": "small",
  "language_mode": "auto",
  "capture_source": "microphone",
  "device_id": "device-1",
  "live_mode": "balanced",
  "execution_mode": "auto",
  "vad_threshold": 0.5,
  "vad_min_silence_ms": 500,
  "vad_speech_pad_ms": 300
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| title | string | Yes | Session title |
| output_root | string | Yes | Output directory path |
| model_name | string | Yes | ASR model to use |
| language_mode | string | Yes | Language code or "auto" |
| capture_source | string | No | "microphone" or "system" |
| device_id | string | No | Specific device ID |
| live_mode | string | No | "balanced", "quality", "speed" |
| execution_mode | string | No | "auto", "cpu_only", "gpu_only" |
| vad_threshold | float | No | VAD threshold (0-1) |
| vad_min_silence_ms | int | No | Min silence before split |
| vad_speech_pad_ms | int | No | Padding around speech |

**Response:**
```json
{
  "session": {
    "id": "session-uuid",
    "title": "Meeting Transcript",
    "started_at": "2026-03-01T12:00:00Z"
  }
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8765/api/session/start \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Meeting Transcript",
    "output_root": "./output",
    "model_name": "small",
    "language_mode": "auto"
  }'
```

---

### POST /api/session/stop

Stop the current transcription session.

**Response:**
```json
{
  "session": {
    "id": "session-uuid",
    "title": "Meeting Transcript",
    "stopped_at": "2026-03-01T13:00:00Z"
  }
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8765/api/session/stop
```

---

### POST /api/session/attach-pdf

Attach a PDF for context-aware transcription.

**Request Body:**
```json
{
  "path": "/path/to/document.pdf"
}
```

**Response:**
```json
{
  "session": {
    "pdf": {
      "path": "/path/to/document.pdf",
      "pages": 10,
      "title": "Document Title"
    }
  }
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8765/api/session/attach-pdf \
  -H "Content-Type: application/json" \
  -d '{"path": "./document.pdf"}'
```

---

## Hotkey Mode (Push-to-Talk)

### POST /api/transcription/hotkey/start

Start hotkey push-to-talk transcription.

**Request Body (HotkeyStartRequest):**
```json
{
  "capture_source": "microphone",
  "device_id": "device-1",
  "model_name": "small",
  "language_mode": "auto",
  "execution_mode": "auto"
}
```

**Response (HotkeyStartResponse):**
```json
{
  "session_id": "hotkey-a1b2c3d4e5f6",
  "status": "recording",
  "message": "Hotkey session started"
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8765/api/transcription/hotkey/start \
  -H "Content-Type: application/json" \
  -d '{
    "capture_source": "microphone",
    "model_name": "small",
    "language_mode": "auto"
  }'
```

---

### POST /api/transcription/hotkey/stop

Stop hotkey transcription and return final transcription.

**Request Body (HotkeyStopRequest):**
```json
{
  "mode": "finish_and_paste"
}
```

Modes: `finish`, `finish_and_paste`, `cancel`

**Response (HotkeyStopResponse):**
```json
{
  "final_transcription": "This is the refined transcription text.",
  "raw_transcription": "this is the raw transcription text",
  "refined_transcription": "This is the refined transcription text.",
  "duration_ms": 5000,
  "segment_count": 3,
  "source_backend": "wasapi",
  "language_used": "en",
  "refinement_mode": "polished",
  "refiner_model_id": "phi-4"
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8765/api/transcription/hotkey/stop \
  -H "Content-Type: application/json" \
  -d '{"mode": "finish_and_paste"}'
```

---

### GET /api/transcription/hotkey/status

Get current hotkey session status.

**Response (HotkeyStatusResponse):**
```json
{
  "state": "recording",
  "is_recording": true,
  "partial_text": "This is what I'm saying...",
  "raw_partial_text": "this is what i'm saying",
  "display_partial_text": "This is what I'm saying...",
  "audio_level": 0.75,
  "session_id": "hotkey-a1b2c3d4e5f6",
  "correlation_id": "hotkey-a1b2c3d4e5f6",
  "duration_ms": 3200,
  "levels": [0.5, 0.6, 0.7, ...]
}
```

**Example:**
```bash
curl http://127.0.0.1:8765/api/transcription/hotkey/status
```

---

### POST /api/hotkey/config

Configure hotkey transcription settings.

**Request Body (HotkeyConfigRequest):**
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

**Response (HotkeyConfigResponse):**
```json
{
  "success": true,
  "config": {
    "chunk_seconds": 1.4,
    "overlap_seconds": 0.25,
    "vad_threshold_db": -40.0,
    "vad_min_silence_ms": 200,
    "vad_speech_pad_ms": 200,
    "confidence_threshold": 0.35,
    "enable_filler_filter": false
  },
  "message": "Hotkey configuration updated"
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8765/api/hotkey/config \
  -H "Content-Type: application/json" \
  -d '{"chunk_seconds": 1.2, "confidence_threshold": 0.4}'
```

---

### POST /api/transcription/hotkey/inject

Inject text into active window (placeholder for Electron).

**Request Body (HotkeyInjectRequest):**
```json
{
  "text": "Text to inject"
}
```

**Response (HotkeyInjectResponse):**
```json
{
  "success": true,
  "message": "Text ready for injection (handled by Electron)"
}
```

---

## System

### GET /api/system/profile

Get current system hardware profile.

**Response:**
```json
{
  "cpu": {
    "cores": 8,
    "threads": 16,
    "architecture": "x86_64"
  },
  "memory": {
    "total_gb": 16,
    "available_gb": 8
  },
  "gpu": {
    "available": true,
    "name": "NVIDIA GeForce RTX 3060",
    "vram_gb": 12
  },
  "platform": "windows"
}
```

**Example:**
```bash
curl http://127.0.0.1:8765/api/system/profile
```

---

### GET /api/system/optimize

Get auto-optimized settings for current hardware.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| mode | string | "balanced" | "maximum", "balanced", "speed", "low_memory" |
| hotkey | bool | false | Optimize for hotkey mode |

**Response:**
```json
{
  "settings": {
    "model_name": "small",
    "compute_type": "float16",
    "chunk_duration": 1.4,
    "overlap_ratio": 0.25,
    "vad_enabled": true,
    "vad_threshold_db": -40.0,
    "confidence_threshold": 0.35,
    "enable_filler_filter": false,
    "enable_hallucination_filter": true,
    "min_segment_length": 3,
    "max_workers": 4,
    "use_parallel_processing": true,
    "preload_model": true,
    "hotkey_optimized": false
  },
  "metadata": {
    "quality_level": "high",
    "optimization_reason": "GPU available with sufficient VRAM",
    "estimated_vram_usage_gb": 2.5,
    "estimated_latency_ms": 150
  },
  "mode": "balanced",
  "hotkey_mode": false
}
```

**Example:**
```bash
curl "http://127.0.0.1:8765/api/system/optimize?mode=balanced&hotkey=false"
```

---

### GET /api/system/presets

Get all preset configurations.

**Response:**
```json
{
  "presets": {
    "maximum_quality": {
      "model_name": "large",
      "compute_type": "float16",
      "chunk_duration": 2.0,
      "confidence_threshold": 0.5,
      "estimated_vram_usage_gb": 6.0,
      "estimated_latency_ms": 300
    },
    "balanced": { ... },
    "maximum_speed": { ... },
    "low_memory": { ... },
    "hotkey_mode": { ... }
  }
}
```

**Example:**
```bash
curl http://127.0.0.1:8765/api/system/presets
```

---

### GET /api/metrics/streaming

Get streaming performance metrics.

**Response:**
```json
{
  "latency_ms": 150,
  "throughput_chars_per_sec": 45,
  "queue_depth": 2,
  "dropped_chunks": 0,
  "total_chunks": 150
}
```

**Example:**
```bash
curl http://127.0.0.1:8765/api/metrics/streaming
```

---

## Settings

### GET /api/settings

Get all user settings.

**Response:**
```json
{
  "transcription": {
    "default_asr_model_id": "small",
    "microphone_asr_model_id": "small",
    "system_asr_model_id": "small",
    "refinement_mode": "polished",
    "language_mode": "auto"
  },
  "audio": {
    "default_capture_source": "microphone",
    "defaultDeviceId": "device-1"
  },
  "refiner": {
    "selected_model_id": "phi-4",
    "runtime_enabled": true
  },
  "advanced": {
    "debugMode": false,
    "logLevel": "INFO"
  }
}
```

**Example:**
```bash
curl http://127.0.0.1:8765/api/settings
```

---

### POST /api/settings

Save all user settings.

**Request Body:**
```json
{
  "transcription": {
    "default_asr_model_id": "small"
  },
  "advanced": {
    "logLevel": "DEBUG"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Settings saved successfully"
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8765/api/settings \
  -H "Content-Type: application/json" \
  -d '{"transcription": {"default_asr_model_id": "small"}}'
```

---

### POST /api/settings/reset

Reset all settings to defaults.

**Response:**
```json
{
  "success": true,
  "message": "Settings reset to defaults"
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8765/api/settings/reset
```

---

## Export

### POST /api/sessions/{session_id}/export

Export a session to various formats.

**Request Body:**
```json
{
  "format": "txt",
  "include_timestamps": true
}
```

**Supported Formats:**
- `txt` - Plain text
- `json` - JSON with metadata
- `md` - Markdown
- `srt` - SubRip subtitles
- `vtt` - WebVTT subtitles

**Response:**
```json
{
  "success": true,
  "file_path": "/path/to/export.txt",
  "format": "txt"
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8765/api/sessions/session-uuid/export \
  -H "Content-Type: application/json" \
  -d '{"format": "txt", "include_timestamps": true}'
```

---

## Refiner

### GET /api/refiner/status

Get refiner runtime status.

**Response:**
```json
{
  "runtime_enabled": true,
  "import_available": true,
  "selected_model_id": "phi-4",
  "model_installed": true,
  "available": true,
  "reason": null
}
```

Reasons when unavailable:
- `runtime_disabled` - Runtime is disabled in settings
- `llama_cpp_missing` - llama-cpp-python not installed
- `no_model_selected` - No model selected
- `model_not_installed` - Selected model not installed

**Example:**
```bash
curl http://127.0.0.1:8765/api/refiner/status
```

---

### POST /api/refiner/refine

Refine text (handled by RefinerService).

**Request Body:**
```json
{
  "text": "raw transcription text",
  "mode": "polished",
  "language_hint": "en"
}
```

**Response:**
```json
{
  "text": "Refined transcription text.",
  "mode": "polished",
  "model_id": "phi-4",
  "used_runtime": true,
  "error": null
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8765/api/refiner/refine \
  -H "Content-Type: application/json" \
  -d '{"text": "hello world", "mode": "polished"}'
```

---

## Server-Sent Events (SSE)

### GET /api/events

Main SSE endpoint for real-time transcription events.

**Event Format:**
```
data: {"type": "event_name", "payload": {...}, "timestamp": "2026-03-01T12:00:00Z"}
```

**Event Types:**

| Event | Description |
|-------|-------------|
| `segment` | New transcription segment completed |
| `transcription` | Full transcription update |
| `meter` | Audio level update |
| `session_started` | Session started |
| `session_stopped` | Session stopped |
| `error` | Error occurred |
| `status.change` | Recording status changed |
| `preload_progress` | Model preload progress |

**Example:**
```bash
curl -N http://127.0.0.1:8765/api/events
```

---

### GET /api/transcription/hotkey/events

SSE endpoint for hotkey-specific events.

**Hotkey Event Types:**

| Event | Description |
|-------|-------------|
| `hotkey_started` | Hotkey session started |
| `hotkey_stopped` | Hotkey session stopped |
| `hotkey_stopping` | Hotkey session stopping |
| `hotkey_stop_ack` | Stop acknowledged |
| `hotkey_status` | Status update |
| `hotkey_partial` | Partial transcription |
| `hotkey_draft_partial` | Draft partial text |
| `hotkey_commit_final` | Final segment committed |
| `hotkey_audio_level` | Audio level for visualizer |
| `hotkey_error` | Error occurred |

**Example:**
```bash
curl -N http://127.0.0.1:8765/api/transcription/hotkey/events
```

---

## WebSocket

### Main Endpoint: `ws://127.0.0.1:8765/api/ws`

Primary WebSocket for real-time transcription and events.

**Features:**
- Auto-reconnect with exponential backoff
- Heartbeat/ping-pong (30s interval, 60s timeout)
- Message compression for large messages
- Rate limiting (1000 messages per 60s window)

**Client Messages:**
```json
{"type": "ping"}
{"type": "settings_request"}
{"type": "settings_update", "payload": {...}}
```

**Server Message Types:**

| Type | Description |
|------|-------------|
| `transcription_partial` | Partial transcription text |
| `transcription_final` | Final transcription with confidence |
| `transcription_segment` | Individual segment |
| `audio_level` | Audio level (0.0-1.0) |
| `audio_spectrum` | Frequency spectrum data |
| `health_metrics` | System health metrics |
| `system_status` | System status update |
| `session_started` | Session started |
| `session_stopped` | Session stopped |
| `session_error` | Session error |
| `hotkey_started` | Hotkey started |
| `hotkey_stopped` | Hotkey stopped |
| `hotkey_partial` | Hotkey partial text |
| `hotkey_audio_level` | Hotkey audio level |
| `hotkey_status` | Hotkey status |
| `ping` / `pong` | Heartbeat |
| `keepalive` | Keepalive message |
| `error` | Error message |
| `auth_success` | Authentication success |

**Example (JavaScript):**
```javascript
const ws = new WebSocket('ws://127.0.0.1:8765/api/ws');

ws.onopen = () => console.log('Connected');
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log('Received:', msg.type, msg.payload);
};
ws.onerror = (error) => console.error('WebSocket error:', error);
ws.onclose = () => console.log('Disconnected');
```

---

### Settings Sync: `ws://127.0.0.1:8765/api/ws/settings`

Dedicated WebSocket for bidirectional settings synchronization.

**Features:**
- Receive settings updates immediately
- Send settings changes that apply immediately
- Request current settings state

**Message Types:**
- `settings_update` - Send settings changes
- `settings_request` - Request current settings
- `settings_response` - Response with current settings

---

### Audio Visualization: `ws://127.0.0.1:8765/api/ws/audio`

WebSocket for real-time audio visualization data.

**Streams:**
- `audio_level` - Current audio level (0.0 to 1.0)
- `audio_spectrum` - Frequency spectrum data for visualization

---

### Hotkey WebSocket: `ws://127.0.0.1:8765/api/transcription/hotkey/ws`

WebSocket endpoint for real-time hotkey updates.

**Streams:**
- Partial transcriptions
- Audio levels (throttled to 20fps)
- Status updates

**Client Messages:**
```json
{"action": "ping"}
```

**Server Messages:**
```json
{"type": "hotkey_status", "payload": {...}}
{"type": "hotkey_audio_level", "payload": {...}}
{"type": "pong"}
{"type": "keepalive"}
```

---

### WebSocket Statistics

### GET /api/ws/stats

Get WebSocket connection statistics.

**Response:**
```json
{
  "websocket": {
    "total_connections": 5,
    "active_connections": 2,
    "messages_sent": 1500,
    "messages_received": 50
  },
  "settings_sync": {
    "subscribed_connections": 2,
    "updates_sent": 10
  }
}
```

**Example:**
```bash
curl http://127.0.0.1:8765/api/ws/stats
```

---

### POST /api/ws/broadcast

Broadcast a message to all connected WebSocket clients (admin use).

**Request Body:**
```json
{
  "type": "custom",
  "payload": {"message": "Hello all clients"}
}
```

**Response:**
```json
{
  "success": true,
  "clients_notified": 3
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8765/api/ws/broadcast \
  -H "Content-Type: application/json" \
  -d '{"type": "custom", "payload": {"message": "test"}}'
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message description"
}
```

**HTTP Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request - Invalid parameters |
| 409 | Conflict - Session already active |
| 503 | Service Unavailable - Backend not ready |

**Example Error:**
```bash
curl -X POST http://127.0.0.1:8765/api/session/start \
  -H "Content-Type: application/json" \
  -d '{}'
```

Response (400):
```json
{
  "detail": "Field required: title"
}
```

---

## Legacy Endpoints

### POST /api/transcribe/start

Alias for `/api/session/start`.

### POST /api/transcribe/stop

Alias for `/api/session/stop`.

---

## Data Models

### HotkeyStartRequest
```json
{
  "capture_source": "microphone | system | null",
  "device_id": "string | null",
  "model_name": "string | null",
  "language_mode": "string (default: 'auto')",
  "execution_mode": "string (default: 'auto')"
}
```

### HotkeyStopRequest
```json
{
  "mode": "finish | finish_and_paste | cancel (default: 'finish_and_paste')"
}
```

### HotkeyConfig
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

### StartSessionRequest
```json
{
  "title": "string (required)",
  "output_root": "string (required)",
  "model_name": "string (required)",
  "language_mode": "string (required)",
  "capture_source": "microphone | system | null",
  "device_id": "string | null",
  "live_mode": "string (default: 'balanced')",
  "execution_mode": "string (default: 'auto')",
  "vad_threshold": "number | null",
  "vad_min_silence_ms": "integer | null",
  "vad_speech_pad_ms": "integer | null"
}
```

### PreloadModelRequest
```json
{
  "model_name": "string (required)",
  "execution_mode": "string (default: 'auto')"
}
```

### ModelSelectionRequest
```json
{
  "category": "asr | refiner",
  "model_id": "string"
}
```

### RefinementModeRequest
```json
{
  "mode": "off | strict | polished"
}
```

### AttachPdfRequest
```json
{
  "path": "string"
}
```

---

## Notes

- **Authentication:** None required - API is local-only
- **Rate Limiting:** None implemented for local use
- **CORS:** All origins allowed (`*`)
- **WebSocket Compression:** Enabled for messages > 1KB
- **SSE Keepalive:** Sent every 15 seconds
- **WebSocket Heartbeat:** 30s interval, 60s timeout
