---
title: Security Documentation
audience: security
last_verified: 2026-03-05
source_of_truth:
  - app/api/server.py
  - app/electron/main/preload.js
  - app/core/logging_utils.py
---

# OpenWispr Security Documentation

**Scope:** Local-first desktop application (Electron + FastAPI backend)  
**Owner:** Security + Backend Team

---

## 1. Threat Model (Local Application Context)

### 1.1 Trust Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                      User System                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Electron Main Process                  │   │
│  │  ┌──────────────┐  ┌─────────────────────────────┐ │   │
│  │  │  Renderer    │  │    FastAPI Backend          │ │   │
│  │  │  (React UI)  │◄─┤    (localhost:8765)         │ │   │
│  │  └──────────────┘  └─────────────────────────────┘ │   │
│  │           │                    │                   │   │
│  │           ▼                    ▼                   │   │
│  │     contextBridge          Model Files            │   │
│  │     IPC APIs               Audio Capture          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Threat Actors

| Actor | Capability | Risk Level |
|-------|------------|------------|
| Malicious website/renderer | XSS via loaded content | Medium (CSP mitigates) |
| Local malware | Process injection, keylogging | Low (local app boundary) |
| Compromised model download | Supply chain attack | Medium (verification below) |
| Malicious document import | Path traversal, DoS | Low (validation in place) |

### 1.3 Attack Vectors

1. **IPC Abuse** - Renderer exploiting `ipcRenderer` to invoke privileged operations
2. **Model Poisoning** - Downloaded ASR models containing malicious code
3. **Path Traversal** - Document/session storage manipulation
4. **Audio Eavesdropping** - Unauthorized microphone access
5. **API Server Exposure** - Backend binding to non-localhost interface

---

## 2. Audio Permission Handling

### 2.1 Permission Model

OpenWispr requires audio capture permissions for:
- Microphone input (dictation mode)
- System audio loopback (system transcription)

### 2.2 Permission Flow

```
User Action → Settings Check → OS Permission Prompt → Backend Initialization
                ↓
         Permission Denied → Graceful Degradation
                ↓
         Permission Granted → Audio Backend Start
```

### 2.3 Security Controls

| Control | Implementation | Location |
|---------|---------------|----------|
| User consent | Settings UI with explicit toggle | `Settings > Audio` |
| OS integration | Windows WASAPI / macOS CoreAudio | `app/audio/backends/` |
| No background capture | Audio stops when UI not active | `session_manager.py` |
| Visual indicator | Recording status in tray/UI | `MainContent.tsx` |

---

## 3. IPC Security (contextBridge Usage)

### 3.1 Context Isolation Architecture

The preload script (`app/electron/main/preload.js`) uses `contextBridge` to expose only explicitly defined APIs to the renderer:

```javascript
// Exposed API surface (from preload.js:3-181)
contextBridge.exposeInMainWorld("transcriptaDesktop", {
  chooseDirectory: () => ipcRenderer.invoke("choose-directory"),
  choosePdf: () => ipcRenderer.invoke("choose-pdf"),
  onBackendExit: (callback) => { /* event listener */ },
  onOpenSettings: (callback) => { /* event listener */ },
  getApiOrigin: () => "http://127.0.0.1:8765",
  fetchJson: async (path, options) => { /* retry logic with 5 retries */ },
  hotkey: {
    register: (accelerator) => ipcRenderer.invoke("hotkey:register", { accelerator }),
    unregister: () => ipcRenderer.invoke("hotkey:unregister"),
    validate: (accelerator) => ipcRenderer.invoke("hotkey:validate", { accelerator }),
    toggle: (enabled) => ipcRenderer.invoke("hotkey:toggle", enabled),
    start: (source) => ipcRenderer.invoke("hotkey:start", { source }),
    stop: () => ipcRenderer.invoke("hotkey:stop"),
    getState: () => ipcRenderer.invoke("hotkey:get-state"),
    updateConfig: (config) => ipcRenderer.invoke("hotkey:update-config", config),
    getDefault: () => ipcRenderer.invoke("hotkey:get-default"),
    onStateChange: (callback) => ipcRenderer.on("hotkey-state-change", callback),
    onTranscriptEvent: (callback) => { /* transcript event listener */ },
    onRegistrationFailed: (callback) => ipcRenderer.on("hotkey-registration-failed", callback),
    removeStateChangeListener: (callback) => { /* remove listener */ },
    removeRegistrationFailedListener: (callback) => { /* remove listener */ }
  },
  text: { inject: (text) => ipcRenderer.invoke("text:inject", text) },
  tray: { updateTooltip: (tooltip) => ipcRenderer.invoke("tray:update-tooltip", tooltip) },
  models: {
    getDownloadRoot: () => ipcRenderer.invoke("models:get-download-root"),
    download: (modelId) => ipcRenderer.invoke("models:download", { modelId }),
    cancel: (modelId) => ipcRenderer.invoke("models:cancel", { modelId }),
    remove: (modelId) => ipcRenderer.invoke("models:remove", { modelId }),
    onDownloadEvent: (callback) => { /* download progress listener */ }
  },
  platform: process.platform,
  versions: { node: process.versions.node, electron: process.versions.electron, chrome: process.versions.chrome }
});
```

### 3.2 IPC Channel Whitelist

| Channel | Direction | Purpose | Validation |
|---------|-----------|---------|------------|
| `choose-directory` | R→M | Directory picker | Returns path only, no execution |
| `choose-pdf` | R→M | PDF import | File extension validation |
| `backend-exit` | M→R | Backend crash notification | Event only, no data |
| `open-settings` | M→R | Open settings UI | Event only, no data |
| `hotkey:register` | R→M | Register global hotkey | Accelerator format validation |
| `hotkey:unregister` | R→M | Unregister hotkey | None |
| `hotkey:validate` | R→M | Validate hotkey format | Accelerator format validation |
| `hotkey:toggle` | R→M | Enable/disable hotkey | Boolean validation |
| `hotkey:start` | R→M | Start hotkey recording | Source validation |
| `hotkey:stop` | R→M | Stop hotkey recording | None |
| `hotkey:get-state` | R→M | Get hotkey status | None |
| `hotkey:update-config` | R→M | Update hotkey config | Schema validation |
| `hotkey:get-default` | R→M | Get platform default | None |
| `hotkey-state-change` | M→R | Hotkey state changed | Event with state payload |
| `hotkey-transcript-event` | M→R | Transcript ready | Event with transcript payload |
| `hotkey-registration-failed` | M→R | Registration failed | Event with error payload |
| `text:inject` | R→M | Type transcribed text | No shell execution |
| `tray:update-tooltip` | R→M | Tray tooltip | String sanitization |
| `models:get-download-root` | R→M | Get model download path | Returns path only |
| `models:download` | R→M | Download model | Model ID whitelist |
| `models:cancel` | R→M | Cancel download | Model ID validation |
| `models:remove` | R→M | Remove model | Model ID validation |
| `model-download-event` | M→R | Download progress | Event with progress payload |

### 3.3 Security Properties

- **Context Isolation**: Enabled (Electron default)
- **Node Integration**: Disabled in renderer
- **Remote Module**: Not used
- **IPC Filtering**: All channels explicitly enumerated in preload

---

## 4. Model Download Verification

### 4.1 Download Security

Model downloads are handled by `app/electron/main/model-download-manager.js`:

| Security Measure | Implementation |
|-----------------|----------------|
| HTTPS only | All download URLs use HTTPS |
| Resume support | `Range` header for partial downloads |
| Integrity check | File size validation post-download |
| Optional artifacts | Missing vocabulary files skipped gracefully |
| Path sandboxing | Models written to `models/` subdirectory only |

### 4.2 Model Trust

ASR models (Whisper) are loaded via `faster-whisper` which:
- Loads weights as read-only tensors
- Does not execute arbitrary code from model files
- Runs in isolated Python process

---

## 5. Secrets Handling

### 5.1 No External Secrets

OpenWispr is a fully local application with no cloud services requiring:
- No API keys stored
- No authentication tokens
- No remote credentials

### 5.2 Local Storage

| Data | Storage Location | Encryption |
|------|-----------------|------------|
| Transcription sessions | `~/.transcripta/sessions/` | OS filesystem |
| Settings | `~/.transcripta/settings.json` | OS filesystem |
| Models | `./models/` | None (public weights) |

### 5.3 Sensitive Data in Memory

- Audio buffers: Cleared on session end
- Transcript segments: Memory-managed by Python GC
- No password/key material in memory

---

## 6. Security Audit Findings

### 6.1 Critical Issues Status

| # | Issue | File:Line | Status | Notes |
|---|-------|-----------|--------|-------|
| 1 | STEM formula parse check always False | `app/stem/formula_extractor.py:49` | 🔴 Open | `all(isinstance(node, ALLOWED_AST_NODES))` bug |
| 2 | PyAudio instance not cleaned up | `app/audio/backends/pyaudio_wasapi.py:99,159-163` | 🔴 Open | Resource leak on startup failure |
| 3 | UI thread safety violations | `app/ui/main_window.py:191-219` | 🔴 Open | Background thread → Qt widget access |
| 4 | Unbounded SSE queue memory leak | `app/api/server.py:2381` | 🔴 Open | `asyncio.Queue()` without maxsize |
| 5 | Contradiction detection logic broken | `app/stem/postprocess.py:151` | 🔴 Open | Float in dict keys (strings) check |
| 6 | Wrong attribute name | `app/audio/capture.py:208` | 🔴 Open | `backend_name` vs `backend` |
| 7 | log_level None check missing | `app/api_main.py:12` | 🟢 Fixed | Safe fallback with `or "INFO"` |
| 8 | GPU mode check AttributeError | `app/stt/engine.py:141` | 🔴 Open | `_gpu_mode.startswith()` on None |
| 9 | QApplication instance not checked | `app/main.py:13` | 🔴 Open | Multiple instance crash |
| 10 | SessionState mutable lists not thread-safe | `app/core/models.py:140-144` | 🔴 Open | No sync on `segments`, `formulas` |

### 6.2 High Severity Issues Status

| Category | Issues | Fixed | Remaining |
|----------|--------|-------|-----------|
| Audio Backends | 4 | 0 | 4 |
| API Server | 4 | 1 | 3 |
| Storage | 3 | 0 | 3 |
| STT Engine | 3 | 0 | 3 |
| Core Modules | 4 | 0 | 4 |

**Total: 35 High severity issues verified, 1 resolved**

### 6.3 Medium/Low Issues Summary

- Error handling gaps: 15 issues
- Race conditions: 12 issues
- Missing validation: 18 issues
- Resource cleanup: 14 issues
- Type safety: 11 issues

---

## 7. Security Best Practices

### 7.1 Development Guidelines

1. **Never expose `ipcRenderer` directly** - Always use `contextBridge`
2. **Validate all IPC inputs** - Assume renderer is compromised
3. **No shell execution** - Use explicit APIs only
4. **Path traversal protection** - Validate all file paths
5. **No eval/Function** - Static code analysis enforced

### 7.2 Deployment Guidelines

1. **Disable DevTools** in production builds
2. **Enable CSP** with strict policy
3. **Code signing** for all releases
4. **Sandbox** enabled for renderer processes

---

## 8. Incident Response

### 8.1 Security Contact

Report security issues to: security@transcripta.app

### 8.2 Response Timeline

| Severity | Response | Fix Target |
|----------|----------|------------|
| Critical | 24 hours | 72 hours |
| High | 48 hours | 1 week |
| Medium | 1 week | 1 month |
| Low | 2 weeks | Next release |

---

*Generated from security audit 2026-03-02. Last verified 2026-03-05. This document should be updated when findings are resolved.*
