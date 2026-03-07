---
title: Architecture Overview
audience: developers
last_verified: 2026-03-04
source_of_truth:
  - app/electron/main/index.js
  - app/electron/main/main.js
  - app/electron/main/shared/state.js
---

# System Architecture

OpenWispr uses a multi-process Electron architecture with a Python FastAPI backend for transcription services.

## Process Model

```
┌─────────────────────────────────────────────────────────────────┐
│                      Electron Main Process                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Main Window │  │ Floating    │  │  Quick Settings Window  │  │
│  │  (1480x960)  │  │ Window      │  │  (420x520)              │  │
│  │              │  │ (460x300)   │  │                         │  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────────────┘  │
│         │                │                                       │
│  ┌──────┴────────────────┴──────────────────────────────────┐  │
│  │              IPC Handlers (ipc/handlers.js)               │  │
│  └──────┬────────────────┬──────────────────────────────────┘  │
│         │                │                                       │
│  ┌──────┴────────────────┴──────────────────────────────────┐  │
│  │              Global State (shared/state.js)               │  │
│  │  - Window references    - Hotkey state                   │  │
│  │  - Backend process      - WebSocket connections          │  │
│  │  - Model downloads      - Audio feedback state           │  │
│  └──────────────────────────────────────────────────────────┘  │
│         │                                                       │
│  ┌──────┴──────────────────────────────────────────────────┐  │
│  │              Backend Spawn (services/backendSpawn.js)    │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────────────┘
                        │ HTTP/WebSocket on port 8765
┌───────────────────────┴─────────────────────────────────────────┐
│                      Python Backend Service                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              FastAPI Server (api/server.py)              │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │  │
│  │  │ Transcription│  │   Hotkey    │  │ Model Download  │  │  │
│  │  │  Service     │  │  Service    │  │    Service      │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         WebSocket Manager (api/websocket_server.py)      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Main Process

The main process (`index.js`) is the entry point that orchestrates the application lifecycle.

### Startup Flow

1. **Backend Initialization**
   - Spawns Python backend process via `startBackend()`
   - Waits for backend health check via `waitForBackendReady()`
   - Sets `state.backendReady = true`

2. **Service Initialization**
   - Creates `ModelDownloadManager` instance with broadcast callback
   - Initializes text injection capabilities (`initTextInjector()`)
   - Loads user settings (`loadUserSettings()`) and device list (`loadDevicesForDesktop()`)

3. **Window Creation**
   - Creates main application window via `createMainWindow()`
   - Creates system tray icon via `createTray()`

4. **Global Shortcuts**
   - Registers global shortcut for Settings (`CommandOrControl+,`)
   - Sends `open-settings` event to main window when triggered

5. **Hotkey System**
   - Hotkeys start disabled until settings are loaded
   - Applied via `applyHotkeyConfig()` after settings load

### Window Types

| Window | Size | Properties | Purpose |
|--------|------|------------|---------|
| Main | 1480x960 (min: 1220x780) | Frame, menu bar hidden, backgroundColor: #0e141b | Primary application interface |
| Floating | 460x300 | Frameless, always-on-top, skipTaskbar, transparent, hasShadow | Hotkey recording overlay with audio visualizer |
| Quick Settings | 420x520 | Frameless, always-on-top, resizable: false, backgroundColor: #10161f | Tray-accessible quick configuration |

### State Management

Centralized state in `shared/state.js`:

```javascript
// Window references
mainWindow, floatingWindow, quickSettingsWindow, tray, modelDownloadManager

// Backend
backendProcess, API_ORIGIN = "http://127.0.0.1:8765", backendReady
cachedSettings, cachedDevices

// Hotkey state
hotkeyEnabled, isRecording, currentHotkeyAccelerator
currentMicrophoneHotkeyAccelerator, currentSystemHotkeyAccelerator
lastHotkeyPressTime, HOTKEY_DEBOUNCE_MS = 150

// WebSocket
hotkeyWebSocket, webSocketReconnectTimeout, allowHotkeyReconnect
hotkeyLifecycleState: "idle" | "starting" | "recording" | "stopping" | "error"
activeHotkeySessionId, hotkeyCurrentText, hotkeyPendingAction

// Configuration
hotkeyConfigState: {
  enabled, key_combination, microphone_key_combination, system_key_combination,
  hold_mode, auto_inject, language, capture_source, device_id, model_name,
  default_asr_model_id, microphone_asr_model_id, system_asr_model_id,
  finish_mode_default, show_floating_window, record_on_start, stop_on_release,
  enable_refiner_on_stop, copy_to_clipboard
}

// Constants
DEFAULT_HOTKEY = "CommandOrControl+Shift+T"
QUICK_LANGUAGE_OPTIONS // 9 languages including auto-detect
```

## Renderer Process

Each window runs in an isolated renderer process with Node integration disabled.

### Preload Scripts

- **preload.js**: Main window API exposure
- **preload-floating.js**: Floating window API exposure
- **preload-quick-settings.js**: Quick settings window API exposure

### Exposed APIs

```javascript
window.transcriptaDesktop = {
  // File dialogs
  chooseDirectory(), choosePdf(),
  
  // Backend communication
  getApiOrigin(), fetchJson(path, options),
  
  // Hotkey control
  hotkey: {
    register(accelerator), unregister(), validate(accelerator),
    toggle(enabled), start(source), stop(),
    getState(), updateConfig(config), getDefault(),
    onStateChange(callback), onTranscriptEvent(callback)
  },
  
  // Text injection
  text: { inject(text) },
  
  // Tray
  tray: { updateTooltip(tooltip) },
  
  // Model management
  models: {
    getDownloadRoot(), download(modelId), cancel(modelId), remove(modelId),
    onDownloadEvent(callback)
  },
  
  // Platform info
  platform, versions: { node, electron, chrome }
}
```

## Backend Process

Python FastAPI service providing transcription capabilities.

### API Server (port 8765)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check with service snapshot |
| `/api/devices` | GET | List audio devices |
| `/api/devices/{id}/probe` | GET | Probe device functionality |
| `/api/settings` | GET/POST | User settings management |
| `/api/session/start` | POST | Start transcription session |
| `/api/session/stop` | POST | Stop transcription session |
| `/api/session` | GET | Get current session snapshot |
| `/api/models/catalog` | GET | Available models |
| `/api/models/state` | GET | Installed models state |
| `/api/models/preload` | POST | Preload model to cache |
| `/api/models/select` | POST | Select active model |
| `/api/transcription/hotkey/start` | POST | Start hotkey session |
| `/api/transcription/hotkey/stop` | POST | Stop hotkey session |
| `/api/transcription/hotkey/status` | GET | Get hotkey status |
| `/api/transcription/hotkey/ws` | WS | Hotkey WebSocket stream |
| `/api/transcription/hotkey/events` | SSE | Hotkey SSE stream |

### Services

- **BackendService**: Core transcription session management
- **HotkeyTranscriptionService**: Push-to-talk transcription with low-latency processing
- **CoachService**: AI-powered transcript refinement
- **RefinerService**: Local LLM-based text refinement
- **WebSocketManager**: Real-time communication management

## Global Shortcuts

Hotkey registration uses Electron's `globalShortcut` API with 150ms debouncing.

### Default Hotkey
- **Primary**: `CommandOrControl+Shift+T`
- **System audio variant**: `CommandOrControl+Shift+Y`

### Hotkey Modes

1. **Toggle Mode** (default): Press once to start, press again to stop
2. **Hold Mode**: Hold to record, release to stop

### Debouncing

```javascript
const HOTKEY_DEBOUNCE_MS = 150;  // Prevent double-fires within 150ms

async function toggleRecording(forceState) {
  const now = Date.now();
  if (now - lastHotkeyPressTime < HOTKEY_DEBOUNCE_MS) {
    return;  // Debounced
  }
  lastHotkeyPressTime = now;
  // ... handle toggle
}
```

## Inter-Process Communication

### IPC Channel Categories

| Category | Channels | Direction |
|----------|----------|-----------|
| File Dialogs | `choose-directory`, `choose-pdf` | Renderer → Main |
| Hotkey Control | `hotkey:register`, `hotkey:unregister`, `hotkey:validate`, `hotkey:toggle`, `hotkey:start`, `hotkey:stop`, `hotkey:get-state`, `hotkey:get-default`, `hotkey:update-config` | Renderer ↔ Main |
| Text Injection | `text:inject` | Renderer → Main |
| Tray | `tray:update-tooltip` | Renderer → Main |
| Models | `models:get-download-root`, `models:download`, `models:cancel`, `models:remove`, `model-service:download`, `model-service:get-target-path` | Renderer ↔ Main |
| Quick Settings | `quick-settings:get-data`, `quick-settings:update`, `quick-settings:open-full`, `quick-settings:close` | Renderer ↔ Main |
| Floating Window | `floating-window-action`, `transcription-update`, `recording-state`, `audio-visualizer` | Both |
| Backend Events | `backend-exit`, `settings-updated`, `open-settings` | Main → Renderer |
| Hotkey Events | `hotkey-state-change`, `transcription-result` | Main → Renderer |
| Model Events | `model-download-event` | Main → Renderer |

### Security

- Context isolation enabled on all windows
- Node integration disabled
- Preload scripts use `contextBridge` for controlled API exposure
- Backend CORS allows all origins for local development

## Audio Flow

```
Microphone/System Audio
    ↓
LoopbackAudioSource (app/audio/capture.py)
    ↓
AudioChunk → FastTranscriber (app/stt/fast_engine.py)
    ↓
TranscriptionSegment
    ↓
├─→ WebSocket/SSE → Floating Window (audio visualizer)
├─→ IPC → Main Window (transcript display)
└─→ TextInjector (optional paste)
```

## Text Injection

Native text injection uses fallback chain:

1. **robotjs** (preferred): Native key simulation
2. **node-key-sender**: Alternative key simulation
3. **Clipboard fallback**: Copy to clipboard if native injection unavailable

```javascript
async function injectText(text) {
  if (textInjector) {
    return await textInjector.typeString(text);
  }
  return { success: false, error: "No text injection method available" };
}
```

## WebSocket Communication

### Connection Management

- Single WebSocket connection per hotkey session
- Exponential backoff reconnection (max 30s delay)
- Error debouncing (5s between error logs)
- Auto-cleanup on session stop

### Message Types

```python
class MessageType(str, Enum):
    # Transcription
    TRANSCRIPTION_PARTIAL = "transcription_partial"
    TRANSCRIPTION_FINAL = "transcription_final"
    TRANSCRIPTION_SEGMENT = "transcription_segment"
    
    # Hotkey-specific
    HOTKEY_STARTED = "hotkey_started"
    HOTKEY_STOPPED = "hotkey_stopped"
    HOTKEY_PARTIAL = "hotkey_partial"
    HOTKEY_AUDIO_LEVEL = "hotkey_audio_level"
    HOTKEY_STATUS = "hotkey_status"
    
    # Connection
    PING = "ping", PONG = "pong", KEEPALIVE = "keepalive"
    ERROR = "error"
```

## Tray Integration

### Tray Icons

- **Idle**: Green circle (#10b981)
- **Recording**: Red circle (#ef4444)

### Tray Menu Features

- Show/Hide main window
- Recent transcripts (last 8 sessions)
- Quick language selection (9 languages)
- Microphone device selection
- Recording controls
- Quick settings toggle

## Model Download Management

Downloads are managed through `ModelDownloadManager` with:
- Progress events broadcast to all windows
- Resume capability for interrupted downloads
- Cancel and remove operations
- Storage in `userData/models` directory

## Shutdown Sequence

1. Unregister global hotkey
2. Stop backend process
3. Clear WebSocket reconnect timeout
4. Close WebSocket connections
5. Unregister all global shortcuts
6. Quit application
