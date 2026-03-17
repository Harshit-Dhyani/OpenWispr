---
audience: developers
last_verified: 2026-03-15
source_of_truth:
  - app/api/server.py
  - app/core/session_manager.py
  - app/audio/capture/capture.py
  - app/stt/streaming_engine.py
---

# Architecture Overview

> High-level system design and components for OpenWispr desktop transcription application.

## System Overview

OpenWispr is a hybrid Electron + React + Python desktop application for real-time system-audio transcription. The architecture follows a client-server model where the Electron renderer communicates with a FastAPI backend running locally.

```
┌─────────────────────────────────────────────────────────────┐
│                     Electron Renderer                        │
│  (React UI + State Management + Settings)                 │
└─────────────────────────────────────────────────────────────┘
                              │
                    IPC / WebSocket / SSE
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Electron Main Process                    │
│  (Window Management, Hotkeys, System Tray, Text Injection) │
└─────────────────────────────────────────────────────────────┘
                              │
                    HTTP / WebSocket
                              │
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                          │
│  (REST API + WebSocket + SSE + STT Engine)                 │
└─────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Audio Capture  │  │   STT Engine    │  │   LLM Services  │
│  (WASAPI etc.)  │  │  (Faster-Whisper│  │ (Coach/Refiner) │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Core Components

### Electron Shell (`app/electron/main/`)

| Component | Responsibility |
|-----------|----------------|
| `index.js` | Main entry point, app lifecycle |
| `ipc/handlers.js` | IPC message routing |
| `ipc/hotkeyHandlers.js` | Global hotkey registration |
| `windows/mainWindow.js` | Main window management |
| `windows/floatingWindow.js` | Floating transcription window |
| `windows/quickSettingsWindow.js` | Quick settings UI |
| `services/backendSpawn.js` | Backend process spawning |
| `services/textInjector.js` | System-wide text injection |

### Backend API (`app/api/`)

| Component | Responsibility |
|-----------|----------------|
| `server.py` | FastAPI app, routes, WebSocket handlers |
| `routes/` | REST endpoint handlers (session, settings, history, etc.) |
| `services/` | Business logic (coach, refiner, style services) |
| `transport/` | Settings sync, event transport |
| `websocket_server.py` | Real-time transcription streaming |

### STT Engine (`app/stt/`)

| Component | Responsibility |
|-----------|----------------|
| `streaming_engine.py` | Dual-mode (Wispr/System) transcription |
| `fast_whisper_backend.py` | Faster-Whisper model wrapper |
| `model_pool.py` | GPU memory pooling and model management |
| `fast_chunker.py` | VAD-based audio chunking |
| `quality.py` | Transcript quality assessment |
| `repetition_guard.py` | Repetition filtering |

### Audio Pipeline (`app/audio/`)

| Component | Responsibility |
|-----------|----------------|
| `capture/capture.py` | LoopbackAudioSource for system audio |
| `backends/` | Audio backend abstraction (WASAPI, PyAudio, soundcard) |
| `devices/` | Device discovery and resolution |
| `vad/` | Voice activity detection |

### Core Services (`app/core/`)

| Component | Responsibility |
|-----------|----------------|
| `session_manager.py` | Session lifecycle and transcription orchestration |
| `hotkey_session.py` | Hotkey-triggered dictation mode |
| `settings/config.py` | Runtime Pydantic settings |
| `model_catalog.py` | Model registry and metadata |
| `error_handler.py` | Error classification and recovery |

### Storage (`app/storage/`)

| Component | Responsibility |
|-----------|----------------|
| `history_db.py` | SQLite persistence for history, dictionary, snippets |
| `session_store.py` | Session output to disk |
| `document_store.py` | Document context for refinement |

## Data Flows

### Session Transcription Flow

1. Frontend calls `/api/session/start` endpoint
2. Backend creates `SessionManager` with settings
3. `SessionManager.start_session()` initializes:
   - `LoopbackAudioSource` for audio capture
   - `FastChunker` for VAD-based chunking
   - `FastTranscriber` for STT
4. Audio flows: capture → chunker → transcriber → segments
5. Segments sent to frontend via WebSocket
6. Final transcript via SSE event stream

### Hotkey Dictation Flow

1. User presses global hotkey (default: Ctrl+Shift+T)
2. Electron `hotkeyHandlers.js` invokes `/api/hotkey/start`
3. Backend creates `HotkeySession` for in-memory dictation
4. Audio processed similarly to session flow
5. Text injected into focused application via `textInjector.js`

### Coach/Refiner Flow

1. Transcript segment sent to `/api/text/transform/coach` or `/api/text/transform/refine`
2. Service checks cache first (coach only)
3. If cache miss, request sent to LLM provider
4. Result cached and returned to frontend

## Settings Architecture

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│ app/config/settings │     │ app/core/settings/  │     │ Electron Frontend   │
│ (SettingDefinition) │────▶│ config.py           │────▶│ (Generated Config)  │
│ (Source of Truth)   │     │ (Pydantic Model)   │     │ (TypeScript)        │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

- **Declarative**: `app/config/settings.py` defines all settings with metadata
- **Runtime**: `app/core/settings/config.py` provides Pydantic-based runtime settings
- **Generated**: `python -m app.config.generate_ts` generates frontend TypeScript config

## Key Contracts

### Backend-Frontend Contract

- Settings sync via `/api/settings` endpoints
- Transcript events via WebSocket (`/ws/transcribe`)
- Final transcripts via SSE (`/sse/transcript/{session_id}`)
- All payloads JSON-serialized

### Electron-Backend Contract

- Backend spawns on app start, terminates on quit
- Health check via `/api/system/health`
- Settings sync on change
- Model download events via IPC

## Platform Support

- **Primary**: Windows 11 (WASAPI loopback audio)
- **Experimental**: macOS, Linux (alternate audio backends)

## Security

- Loopback-only binding (127.0.0.1)
- No CORS wildcard with credentials
- Input validation at transport boundary
- Allowlisted IPC operations

---

*Last verified: March 15, 2026*
