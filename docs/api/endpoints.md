# API Documentation

## Overview

Transcripta exposes a local REST API for the Electron frontend to communicate with the Python backend.

Base URL: `http://127.0.0.1:8765`

## Endpoints

### Health Check

```
GET /api/health
```

Returns the health status of the backend.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### Sessions

#### List Sessions

```
GET /api/sessions
```

Returns a list of all saved sessions.

**Response:**
```json
{
  "sessions": [
    {
      "id": "session-uuid",
      "name": "Meeting Transcript",
      "created_at": "2026-03-01T12:00:00Z",
      "updated_at": "2026-03-01T13:30:00Z"
    }
  ]
}
```

#### Get Session

```
GET /api/sessions/{session_id}
```

Returns details for a specific session.

#### Create Session

```
POST /api/sessions
```

Creates a new transcription session.

**Request Body:**
```json
{
  "name": "New Session",
  "settings": {
    "model": "small",
    "language": "en"
  }
}
```

### Transcription

#### Start Transcription

```
POST /api/transcribe/start
```

Starts the transcription process for the current session.

**Request Body:**
```json
{
  "session_id": "session-uuid",
  "device_id": "audio-device-id",
  "settings": {
    "live_mode": "balanced"
  }
}
```

#### Stop Transcription

```
POST /api/transcribe/stop
```

Stops the transcription process.

#### Get Transcript

```
GET /api/sessions/{session_id}/transcript
```

Returns the transcript for a session.

**Response:**
```json
{
  "segments": [
    {
      "id": 1,
      "text": "Hello world",
      "start": 0.0,
      "end": 2.5,
      "confidence": 0.95
    }
  ]
}
```

### Server-Sent Events (SSE)

```
GET /api/events
```

Subscribe to real-time transcription events.

**Event Types:**

- `transcript.segment` - New transcription segment
- `transcript.stem` - STEM content detected
- `audio.level` - Audio level update
- `status.change` - Recording status change

### Devices

#### List Audio Devices

```
GET /api/devices
```

Returns available audio input and output devices.

**Response:**
```json
{
  "devices": [
    {
      "id": "device-id",
      "name": "Microphone (Realtek)",
      "type": "input",
      "is_default": true
    }
  ]
}
```

### Models

#### List Available Models

```
GET /api/models
```

Returns available transcription models.

**Response:**
```json
{
  "models": [
    {
      "id": "small",
      "name": "Small (recommended)",
      "size": "466 MB",
      "downloaded": true
    }
  ]
}
```

#### Download Model

```
POST /api/models/download
```

Downloads a transcription model.

**Request Body:**
```json
{
  "model_id": "medium"
}
```

### Export

#### Export Session

```
POST /api/sessions/{session_id}/export
```

Exports a session to various formats.

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

## WebSocket

Real-time audio level updates are available via WebSocket:

```
ws://127.0.0.1:8765/ws/audio-levels
```

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "MODEL_NOT_FOUND",
    "message": "The requested model is not available",
    "details": {}
  }
}
```

**Common Error Codes:**

- `SESSION_NOT_FOUND` - Requested session does not exist
- `MODEL_NOT_FOUND` - Requested model is not available
- `DEVICE_NOT_FOUND` - Audio device is not available
- `TRANSCRIPTION_ACTIVE` - Action cannot be performed while transcribing
- `INVALID_SETTINGS` - Provided settings are invalid
