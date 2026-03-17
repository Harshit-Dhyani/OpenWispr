---
title: Security Documentation
audience: developers
last_verified: 2026-03-15
source_of_truth:
  - app/api/server.py
  - app/electron/main/preload/main.js
  - app/api/websocket_server.py
---

# OpenWispr Security Documentation

**Scope:** Local-first desktop application (Electron + FastAPI backend)  
**Owner:** Security + Backend Team

---

## 1. Threat Model (Local Application Context)

### 1.1 Trust Boundaries

User System
  Electron Main Process
    Renderer (React UI) <-> FastAPI Backend (localhost:8765)
      contextBridge        Model Files
      IPC APIs             Audio Capture

### 1.2 Threat Actors

| Actor | Capability | Risk Level |
|-------|------------|------------|
| Malicious website/renderer | XSS via loaded content | Medium (CSP mitigates) |
| Local malware | Process injection, keylogging | Low (local app boundary) |
| Compromised model download | Supply chain attack | Medium (verification below) |
| Malicious document import | Path traversal, DoS | Low (validation in place) |

### 1.3 Attack Vectors

1. IPC Abuse - Renderer exploiting ipcRenderer to invoke privileged operations
2. Model Poisoning - Downloaded ASR models containing malicious code
3. Path Traversal - Document/session storage manipulation
4. Audio Eavesdropping - Unauthorized microphone access
5. API Server Exposure - Backend binding to non-localhost interface

---

## 2. CORS Configuration

### 2.1 Current Settings

The FastAPI backend is configured with localhost-only CORS:

```python
# app/api/server.py:465-475
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2.2 Security Assessment

| Control | Status | Notes |
|---------|--------|-------|
| Wildcard CORS | Not used | Only localhost origins allowed |
| Credentials allowed | No | allow_credentials=False |
| Origin validation | Enabled | Strict origin list |

**Note:** Per AGENTS.md, CORS must be localhost-only. Current configuration complies.

---

## 3. Audio Permission Handling

### 3.1 Permission Model

OpenWispr requires audio capture permissions for:
- Microphone input (dictation mode)
- System audio loopback (system transcription)

### 3.2 Security Controls

| Control | Implementation | Location |
|---------|---------------|----------|
| User consent | Settings UI with explicit toggle | Settings > Audio |
| OS integration | Windows WASAPI / macOS CoreAudio | app/audio/backends/ |
| No background capture | Audio stops when UI not active | session_manager.py |
| Visual indicator | Recording status in tray/UI | MainContent.tsx |

---

## 4. IPC Security (contextBridge Usage)

### 4.1 Context Isolation Architecture

The preload script uses contextBridge to expose only explicitly defined APIs to the renderer. Key exposed APIs include:

- File dialogs: chooseDirectory, choosePdf
- Backend communication: fetchJson (with retry logic), getApiOrigin
- Hotkey control: register, unregister, validate, toggle, start, stop
- Text injection: text.inject
- Model management: download, cancel, remove
- Platform info: platform, versions

### 4.2 IPC Channel Whitelist

All IPC channels are explicitly enumerated in the preload script:

| Channel | Direction | Purpose |
|---------|-----------|---------|
| choose-directory | R->M | Directory picker |
| choose-pdf | R->M | PDF import |
| backend-exit | M->R | Backend crash notification |
| open-settings | M->R | Open settings UI |
| hotkey:* | R->M/M->R | Hotkey control and events |
| text:inject | R->M | Type transcribed text |
| tray:update-tooltip | R->M | Tray tooltip |
| models:* | R->M/M->R | Model download management |

### 4.3 Security Properties

- Context Isolation: Enabled (Electron default)
- Node Integration: Disabled in renderer
- Remote Module: Not used
- IPC Filtering: All channels explicitly enumerated in preload

---

## 5. WebSocket Security

### 5.1 Connection Configuration

WebSocket connections are managed by app/api/websocket_server.py:

| Control | Value | Status |
|---------|-------|--------|
| Heartbeat interval | 30s | Enabled |
| Heartbeat timeout | 60s | Enabled |
| Max message size | 1MB | Enabled |
| Rate limit | 1000 msgs/60s | Enabled |
| allowed_origins | None | Needs restriction |
| auth_required | False | Local IP auto-auth |

The WebSocket manager validates origins but currently accepts all origins. However, local IP addresses (127.0.0.1) are automatically authenticated without requiring tokens (see websocket_server.py:220-232).

**Security Note:** For production deployment, restrict allowed_origins to specific origins.

---

## 6. Model Download Verification

### 6.1 Download Security

Model downloads are handled by app/electron/main/services/modelDownloadManager.js:

| Security Measure | Implementation |
|-----------------|----------------|
| HTTPS only | All download URLs use HTTPS |
| Resume support | Range header for partial downloads |
| Integrity check | File size validation post-download |
| Optional artifacts | Missing vocabulary files skipped gracefully |
| Path sandboxing | Models written to models/ subdirectory only |

### 6.2 Model Trust

ASR models (Whisper) are loaded via faster-whisper which:
- Loads weights as read-only tensors
- Does not execute arbitrary code from model files
- Runs in isolated Python process

---

## 7. Secrets Handling

### 7.1 No External Secrets

OpenWispr is a fully local application with no cloud services requiring:
- No API keys stored
- No authentication tokens
- No remote credentials

### 7.2 Local Storage

| Data | Storage Location | Encryption |
|------|-----------------|------------|
| Transcription sessions | ~/.openwispr/sessions/ | OS filesystem |
| Settings | ~/.openwispr/settings.json | OS filesystem |
| Models | ./models/ | None (public weights) |

### 7.3 Sensitive Data in Memory

- Audio buffers: Cleared on session end
- Transcript segments: Memory-managed by Python GC
- No password/key material in memory

---

## 8. Security Audit Findings

### 8.1 Critical Issues Status

| # | Issue | File:Line | Status | Notes |
|---|-------|-----------|--------|-------|
| 1 | STEM formula parse check | app/stem/formula_extractor.py:49 | Open | all(isinstance(node, ALLOWED_AST_NODES)) check |
| 2 | PyAudio instance not cleaned up | app/audio/backends/pyaudio_wasapi.py:99,159-163 | Open | Resource leak on startup failure |
| 3 | UI thread safety violations | app/ui/main_window.py:191-219 | Open | Background thread -> Qt widget access |
| 4 | SSE queue memory leak | app/api/server.py:145,182 | Fixed | Queue now bounded with maxsize=100 |
| 5 | Contradiction detection logic | app/stem/postprocess.py:151 | Open | Float comparison in dict keys |
| 6 | Wrong attribute name | app/audio/capture.py:208 | Open | backend_name vs backend |
| 7 | log_level None check missing | app/api_main.py:12 | Fixed | Safe fallback with or "INFO" |
| 8 | GPU mode check AttributeError | app/stt/engine.py:141 | Open | _gpu_mode.startswith() on None |
| 9 | QApplication instance not checked | app/main.py:13 | Open | Multiple instance crash |
| 10 | SessionState mutable lists | app/core/models.py:140-144 | Open | No sync on segments, formulas |

### 8.2 High Severity Issues Status

| Category | Issues | Fixed | Remaining |
|----------|--------|-------|-----------|
| Audio Backends | 4 | 0 | 4 |
| API Server | 4 | 2 | 2 |
| Storage | 3 | 0 | 3 |
| STT Engine | 3 | 0 | 3 |
| Core Modules | 4 | 0 | 4 |

**Total: 35 High severity issues verified, 2 resolved**

### 8.3 Medium/Low Issues Summary

- Error handling gaps: 15 issues
- Race conditions: 12 issues
- Missing validation: 18 issues
- Resource cleanup: 14 issues
- Type safety: 11 issues

---

## 9. Security Best Practices

### 9.1 Development Guidelines

1. Never expose ipcRenderer directly - Always use contextBridge
2. Validate all IPC inputs - Assume renderer is compromised
3. No shell execution - Use explicit APIs only
4. Path traversal protection - Validate all file paths
5. No eval/Function - Static code analysis enforced

### 9.2 Deployment Guidelines

1. Disable DevTools in production builds
2. Enable CSP with strict policy
3. Code signing for all releases
4. Sandbox enabled for renderer processes
5. Restrict WebSocket origins - Change allowed_origins=["*"] to specific origins

---

## 10. Incident Response

### 10.1 Security Contact

Report security issues to: openwispr-security@proton.me

### 10.2 Response Timeline

| Severity | Response | Fix Target |
|----------|----------|------------|
| Critical | 24 hours | 72 hours |
| High | 48 hours | 1 week |
| Medium | 1 week | 1 month |
| Low | 2 weeks | Next release |

---

*Generated from security audit 2026-03-02. Last verified 2026-03-15. This document should be updated when findings are resolved.*
