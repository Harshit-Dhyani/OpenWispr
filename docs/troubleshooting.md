---
title: Troubleshooting Guide
audience: operators
last_verified: 2026-03-08
source_of_truth:
  - app/core/error_handler.py
  - app/core/recovery_strategies.py
  - AGENTS.md
---

# OpenWispr Troubleshooting Guide

Quick reference for diagnosing and resolving issues using the Symptom → Cause → Fix → Verify format.

---

## Quick Diagnostics

Run these first:

```powershell
# Check backend health
Invoke-RestMethod http://127.0.0.1:8765/api/health

# Check logs
Get-Content sessions\<session>\logs\app.log -Tail 30

# Check GPU
nvidia-smi
```

---

## Performance Optimization Issues

### High Memory Usage (5GB+)

**Symptom:** Application uses excessive RAM, system becomes sluggish.

**Causes:**
- Default model size too large (medium)
- Compute type set to float16 instead of int8
- Model cache TTL too long (30 minutes)
- Chunk size too large (1.6 seconds)

**Fix:**
```powershell
# 1. Use smaller model
$env:OPENWISPR_DEFAULT_MODEL="small"

# 2. Use int8 compute type
$env:OPENWISPR_COMPUTE_TYPE="int8"

# 3. Reduce chunk size
$env:OPENWISPR_CHUNK_SECONDS="0.5"

# 4. Or apply Speed Monster preset (see docs/engineering/performance.md)
```

**Files to modify for permanent fix:**
- `app/config/constants.py` lines 70-71, 28
- `app/stt/model_pool.py` line 179

**Verify:**
```powershell
# Check memory usage
(Invoke-RestMethod http://127.0.0.1:8765/api/health).health.memory_mb

# Should be 1-2GB instead of 5GB+
```

---

### High Latency (500-2000ms)

**Symptom:** Slow transcription, noticeable delay between speech and text.

**Causes:**
- Default chunk size too large (1.6 seconds)
- Model TTL too long (30 minutes) causing cache bloat
- StreamingConfig not optimized for low latency
- Beam size too large

**Fix:**
```powershell
# 1. Reduce chunk duration
$env:OPENWISPR_CHUNK_SECONDS="0.5"

# 2. Use smaller model for speed
$env:OPENWISPR_DEFAULT_MODEL="small"

# 3. Use int8 for faster inference
$env:OPENWISPR_COMPUTE_TYPE="int8"

# 4. Clear model cache
Invoke-RestMethod http://127.0.0.1:8765/api/models/cache -Method DELETE
```

**Files to modify for permanent fix:**
- `app/config/constants.py` - DEFAULT_CHUNK_SECONDS
- `app/stt/streaming_engine.py` - WISPR mode StreamingConfig

**Verify:**
```powershell
# Check latency
$health = Invoke-RestMethod http://127.0.0.1:
$health.health8765/api/health.avg_inter_word_latency_ms

# Should be 300-800ms instead of 500-2000ms
```

---

## Settings Bugs Found

### Settings Ownership Drift

**Symptom:** Frontend settings defaults don't match backend settings.

**Causes:**
- Frontend schema/defaults maintained separately from `app/config/settings.py`
- Generated outputs not synchronized

**Fix:**
```powershell
# Always use backend settings as source of truth
# Compare: backend registry, generated frontend settings, and renderer consumers

# Check current settings
Invoke-RestMethod http://127.0.0.1:8765/api/settings
```

**Prevention:** Backend registry is authoritative; frontend settings schema/defaults must be generated from it.

---

### Model Install State Mismatch

**Symptom:** Models UI shows `completed` downloads but marks same model as `Not Installed`.

**Causes:**
- Electron wrote model files under roaming app-data models directory
- Backend install-state checks defaulted to separate repo-local `./models` path

**Fix:**
```powershell
# Ensure backend and Electron share one canonical models root
# Check download target path matches /api/models/catalog install paths
Invoke-RestMethod http://127.0.0.1:8765/api/models/catalog

# Compare against Electron user-data path
```

**Prevention:** Backend model install-state, runtime loading, and Electron download management must share one canonical models root.

---

### Typecheck Wrapper False Green

**Symptom:** Root `typecheck` passes but package-level validation is missing.

**Causes:**
- Wrapper script allows echo/fallback behavior instead of enforcing real validation

**Fix:**
```powershell
# Run package-level typecheck directly
cd app/electron && npm run typecheck
```

**Prevention:** Never ship required validation wrappers that silently downgrade to fallback behavior.

---

### Icon Asset Transparent Margin Regression

**Symptom:** Windows taskbar icon appears smaller than other desktop apps.

**Causes:**
- Brand asset generator preserved transparent margins from source art
- Thumbnail-style resize never upscaled trimmed artwork

**Fix:**
```powershell
# Rebuild icons with trimmed margins
npm run build:icons
```

**Prevention:** Packaging icons must trim transparent outer margins before resizing.

---

## No Audio Captured

**Symptom:** VU meter shows no activity, transcripts are empty.

**Causes:**
- Wrong capture device selected
- Windows exclusive mode enabled
- Audio playing through different output
- WASAPI permissions denied

**Fix:**
```powershell
# 1. List devices
Invoke-RestMethod http://127.0.0.1:8765/api/devices

# 2. Disable exclusive mode
# Settings > System > Sound > More sound settings > Playback > Device > Advanced > Uncheck "Exclusive Mode"

# 3. Check privacy settings
# Settings > Privacy > Microphone > Allow apps to access microphone

# 4. Restart audio service
Restart-Service audiosrv -Force
```

**Verify:**
```powershell
# Probe device
Invoke-RestMethod "http://127.0.0.1:8765/api/devices/default/probe?duration=5"

# Check meter in health response
(Invoke-RestMethod http://127.0.0.1:8765/api/health).meter_value
```

---

## GPU Not Detected

**Symptom:** Transcription uses CPU (slow), logs show "CUDA not available".

**Causes:**
- NVIDIA drivers outdated
- CUDA toolkit mismatch
- PyTorch installed without CUDA support

**Fix:**
```powershell
# 1. Verify drivers
nvidia-smi

# 2. Force CPU fallback if needed
$env:OPENWISPR_DEVICE="cpu"
$env:OPENWISPR_COMPUTE_TYPE="int8"

# 3. Or reinstall PyTorch with CUDA
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

**Verify:**
```powershell
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
python -c "import ctranslate2; print('CUDA devices:', ctranslate2.get_cuda_device_count())"
Invoke-RestMethod http://127.0.0.1:8765/api/health | Select-Object -ExpandProperty health | Select-Object gpu_mode
```

---

## Transcription Slow / High Latency

**Symptom:** Delay between speech and transcription, backpressure warnings.

**Causes:**
- Model too large for hardware
- Queue depth too high
- GPU memory exhausted
- Other apps using GPU

**Fix:**
```powershell
# 1. Use smaller model
$env:OPENWISPR_DEFAULT_MODEL="small"  # or base, tiny

# 2. Reduce chunk duration
$env:OPENWISPR_CHUNK_SECONDS="1.0"

# 3. Clear model cache
Invoke-RestMethod http://127.0.0.1:8765/api/models/cache -Method DELETE

# 4. Close other GPU apps
```

**Verify:**
```powershell
# Check backpressure state
$health = Invoke-RestMethod http://127.0.0.1:8765/api/health
$health.health.stt_backpressure_state  # Should be "normal"
$health.health.queue_depth             # Should be < 5
$health.health.estimated_backlog_seconds  # Should be < 2
```

---

## Model Download Fails

**Symptom:** "Model not found" error, download progress stuck.

**Causes:**
- No internet connection
- Disk full
- HuggingFace down
- Corporate firewall blocking

**Fix:**
```powershell
# 1. Check internet
ping huggingface.co

# 2. Check disk space
Get-PSDrive C | Select-Object Used,Free

# 3. Use mirror if behind firewall
$env:HF_ENDPOINT="https://hf-mirror.com"

# 4. Manual download
huggingface-cli download Systran/faster-whisper-medium --local-dir ./models
```

**Verify:**
```powershell
# Check model cache
Invoke-RestMethod http://127.0.0.1:8765/api/models/cache

# Preload model
Invoke-RestMethod http://127.0.0.1:8765/api/models/preload -Method POST `
    -Body '{"model_name":"small","execution_mode":"auto"}' `
    -ContentType "application/json"
```

---

## Session Not Saving

**Symptom:** Transcripts lost after closing app, no files in session folder.

**Causes:**
- Permissions denied
- Disk full
- Session directory doesn't exist

**Fix:**
```powershell
# 1. Create directory
mkdir sessions -Force

# 2. Fix permissions
icacls sessions/ /grant "$env:USERNAME:(OI)(CI)F" /T

# 3. Check disk space
Get-PSDrive C | Select-Object Free

# 4. Change export path if needed
$env:OPENWISPR_EXPORT_ROOT="D:\OpenWispr\Sessions"
```

**Verify:**
```powershell
# Check session folder exists
Test-Path sessions -PathType Container

# Check session state
Invoke-RestMethod http://127.0.0.1:8765/api/session

# List session files
Get-ChildItem sessions\<session-name>
```

---

## Backend Fails to Start (Port in Use)

**Symptom:** "Address already in use" error, connection refused.

**Causes:**
- Orphaned Python process holding port
- Another app using port 8765

**Fix:**
```powershell
# 1. Find process on port 8765
Get-NetTCPConnection -LocalPort 8765 | Select-Object OwningProcess

# 2. Kill the process
Stop-Process -Id <PID> -Force

# 3. Or kill all Python
Get-Process python | Stop-Process -Force

# 4. Change port
$env:OPENWISPR_API_PORT="8766"
```

**Verify:**
```powershell
# Check port is free
Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue

# Start backend and check health
python -m app.api_main
Invoke-RestMethod http://127.0.0.1:8765/api/health
```

---

## Out of Memory (OOM)

**Symptom:** "CUDA out of memory", system freeze, GPU memory exhausted.

**Causes:**
- Model too large for GPU
- Batch size too large
- Other apps using GPU memory

**Fix:**
```powershell
# 1. Switch to CPU
$env:OPENWISPR_DEVICE="cpu"
$env:OPENWISPR_COMPUTE_TYPE="int8"

# 2. Use smaller model
$env:OPENWISPR_DEFAULT_MODEL="base"

# 3. Clear model cache
Invoke-RestMethod http://127.0.0.1:8765/api/models/cache -Method DELETE

# 4. Close other GPU apps
```

**Verify:**
```powershell
# Check GPU memory
nvidia-smi --query-gpu=memory.used,memory.total --format=csv

# Check model loaded on CPU
Invoke-RestMethod http://127.0.0.1:8765/api/health | Select-Object -ExpandProperty health | Select-Object gpu_mode
```

---

## Hotkey Not Working

**Symptom:** Push-to-talk doesn't activate recording.

**Causes:**
- App not focused
- Hotkey conflict with other app
- Permissions issue

**Fix:**
```powershell
# 1. Check hotkey status
Invoke-RestMethod http://127.0.0.1:8765/modes/status

# 2. Change hotkey in UI settings
# 3. Run as administrator if needed
```

**Verify:**
```powershell
# Check hotkey in health
(Invoke-RestMethod http://127.0.0.1:8765/api/health).hotkey
```

---

## Session Data Corruption

**Symptom:** Cannot load session, missing transcripts, parse errors.

**Causes:**
- Crash during write
- Disk full during write
- Power loss

**Fix:**
```powershell
# 1. Check for transcript.jsonl
$lines = Get-Content sessions\<session>\transcript.jsonl

# 2. Recover segments
$segments = $lines | ForEach-Object { 
    try { $_ | ConvertFrom-Json } catch { $null } 
} | Where-Object { $_ -ne $null }

# 3. Rebuild transcript
$segments | ForEach-Object { "[$($_.start) - $($_.end)] $($_.text)" } | Out-File recovered.txt

# 4. Check for backup
$backup = Get-ChildItem sessions\<session>\*.backup -ErrorAction SilentlyContinue
```

**Verify:**
```powershell
# Check recovered data
Get-Content recovered.txt -Head 10

# Validate JSONL
Get-Content sessions\<session>\transcript.jsonl | ForEach-Object {
    try { $_ | ConvertFrom-Json | Out-Null; "Valid" } catch { "Invalid: $_" }
}
```

---

## Electron Won't Start

**Symptom:** UI doesn't appear, "connection refused" errors.

**Causes:**
- Backend not running
- Port conflict
- Orphaned processes

**Fix:**
```powershell
# 1. Check port availability
netstat -ano | findstr 8765

# 2. Kill orphaned Python
taskkill /F /IM python.exe

# 3. Kill by port
Get-NetTCPConnection -LocalPort 8765 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

# 4. Change port in .env
echo "OPENWISPR_PORT=8766" >> .env
```

**Verify:**
```powershell
# Check Python processes
Get-Process python

# Check logs
Get-Content sessions/latest/logs/app.log -Tail 50
```

---

## Error Categories Reference

From `app/core/error_handler.py`:

### Audio Errors

| Error Category | Trigger | User Message |
|----------------|---------|--------------|
| `AUDIO_DEVICE_DISCONNECTED` | Headset/speaker unplugged | "Your audio device was disconnected. Switching to default device." |
| `AUDIO_PERMISSION_DENIED` | Windows privacy settings | "OpenWispr needs microphone access to transcribe audio." |
| `AUDIO_BACKEND_FAILURE` | WASAPI/driver failure | "The audio backend encountered an error." |
| `AUDIO_CAPTURE_ERROR` | Format/channel mismatch | Check audio device properties |

### Model Errors

| Error Category | Trigger | User Message |
|----------------|---------|--------------|
| `MODEL_OOM` | GPU out of memory | "The transcription model ran out of memory. Switching to CPU mode." |
| `MODEL_NOT_FOUND` | Model not downloaded | "The requested transcription model is not available. Downloading now." |
| `MODEL_CORRUPTED` | Bad model file | "The transcription model file appears to be corrupted. Re-downloading." |
| `MODEL_LOAD_FAILED` | Incompatible model | "Failed to load the transcription model. Trying fallback model." |
| `MODEL_INFERENCE_ERROR` | Runtime inference failure | Model error with details |

### Session Errors

| Error Category | Trigger | User Message |
|----------------|---------|--------------|
| `SESSION_DISK_FULL` | No free space | "Your disk is full. Recording has been paused." |
| `SESSION_WRITE_PERMISSION` | Access denied | "Cannot save session to the selected location." |
| `SESSION_CORRUPTED` | File corruption | "Your session file appears to be corrupted. Attempting recovery." |
| `SESSION_NOT_FOUND` | Missing session | Session not found error |

### Network Errors

| Error Category | Trigger | User Message |
|----------------|---------|--------------|
| `NETWORK_BACKEND_UNAVAILABLE` | Backend not responding | "The transcription backend is not responding. Retrying connection." |
| `NETWORK_SYNC_FAILED` | Cloud sync failure | "Could not synchronize your settings with the cloud. Saved locally." |
| `NETWORK_TIMEOUT` | Slow/unstable connection | Connection timeout error |
| `NETWORK_CONNECTION_ERROR` | General connection failure | Connection error |

### System Errors

| Error Category | Trigger | User Message |
|----------------|---------|--------------|
| `SYSTEM_RESOURCE_EXHAUSTED` | CPU/RAM exhausted | System resource error |
| `SYSTEM_CONFIG_ERROR` | Invalid configuration | Configuration error |
| `SYSTEM_UNKNOWN` | Unexpected error | "An unexpected error occurred. Please try again." |

---

## Recovery Strategies

From `app/core/recovery_strategies.py`:

| Strategy | Handles | Recovery Action |
|----------|---------|-----------------|
| `audio_device_switch` | `AUDIO_DEVICE_DISCONNECTED` | Switches to default/first available device |
| `audio_permission_guidance` | `AUDIO_PERMISSION_DENIED` | Shows platform-specific guidance (Windows/Mac/Linux) |
| `model_oom_recovery` | `MODEL_OOM` | GPU→CPU fallback, batch size reduction (16→8→4→2→1) |
| `model_auto_download` | `MODEL_NOT_FOUND`, `MODEL_CORRUPTED` | Downloads model with retry (max 2 attempts, 2s base delay) |
| `model_size_fallback` | `MODEL_LOAD_FAILED` | Falls back to smaller model (large→turbo→medium→small→base→tiny) |
| `network_retry` | Network errors | Exponential backoff (1s, 2s, 4s, max 30s) |
| `offline_mode_switch` | `NETWORK_BACKEND_UNAVAILABLE` | Switches to offline mode with periodic retry |
| `disk_full_handler` | `SESSION_DISK_FULL` | Pauses recording, identifies cleanup candidates |
| `session_corruption_recovery` | `SESSION_CORRUPTED` | Attempts partial JSON extraction, then backup restore |

### Fallback Chains

| Chain | Options | When Activated |
|-------|---------|----------------|
| `compute_device` | cuda → cpu | GPU OOM detected |
| `model_size` | large-v3 → turbo → medium → small → base → tiny | Model load failure |
| `batch_size` | 16 → 8 → 4 → 2 → 1 | Memory pressure |

---

## Known Issues (Never Reintroduce)

From `AGENTS.md` - These bugs must not be reintroduced:

### Serialization Issues

| Issue | Prevention |
|-------|------------|
| Numpy scalars/arrays sent raw | Always route payloads through single JSON-safe encoder |
| Dataclasses sent raw | Convert to dict before sending |
| datetime/Path sent raw | Serialize to string/JSON-safe format |

### State Management Issues

| Issue | Prevention |
|-------|------------|
| Live transcript text appended | Draft/final updates must replace by `session_id + segment_index` |
| State shared between Dictation and Sessions | Keep separate scoped slices, render only active mode's data |
| Duplicate hotkey transcript events | One live draft lane and one final lane only |
| Microphone/system model selection drift | Active capture must resolve matching ASR model |

### Progress and UX Issues

| Issue | Prevention |
|-------|------------|
| Fake progress shown | Show percent only when total size known; use truthful state labels |
| Hard-fail on optional artifacts | Missing vocabulary-style files must be skipped gracefully |
| Refiner runtime mandatory | If `llama-cpp-python` unavailable, degrade once, log once, return original |
| Normal disconnects treated as errors | Handle `CancelledError` and clean closes as expected |

### Logging Issues

| Issue | Prevention |
|-------|------------|
| Everything at DEBUG | `debugMode` controls diagnostics; `logLevel` controls verbosity |
| Verbose dev logging default | Default to INFO/WARNING unless `OPENWISPR_LOG_LEVEL=DEBUG` set |

### Data Integrity Issues

| Issue | Prevention |
|-------|------------|
| Trusting legacy class names | Use resolved runtime fields (`capture_source`, resolved device kind, resolved model id) |

---

## Log Locations

| Location | Description |
|----------|-------------|
| `sessions/<session_id>/logs/app.log` | Session-specific logs (JSON format) |
| `~/.transcripta/reports/crash_*.json` | Crash dumps with full context |
| `~/.transcripta/app.log` | Legacy global log (if configured) |
| Console output | Real-time logs when running in terminal |

### Log Format

```json
{
  "time": "2026-01-15T10:30:00",
  "level": "ERROR",
  "logger": "transcripta.errors",
  "message": "Model load failed",
  "error_id": "abc123",
  "category": "model_load_failed"
}
```

### Finding Error IDs

Error IDs are 8-character codes (e.g., `abc123`) in log messages:

```powershell
# Find recent errors with IDs
Get-Content sessions\<session>\logs\app.log | 
    ConvertFrom-Json | 
    Where-Object { $_.level -eq "ERROR" } |
    Select-Object time, message, error_id, category
```

---

## PowerShell Quick Fixes

### Complete Reset

```powershell
# Kill all Python processes
taskkill /F /IM python.exe 2>$null

# Clear cache
Remove-Item -Recurse -Force ~/.transcripta/cache -ErrorAction SilentlyContinue

# Clear temp files
Remove-Item -Recurse -Force ~/.transcripta/temp -ErrorAction SilentlyContinue

# Restart with fresh logs
python run.py
```

### Fix Permissions

```powershell
# Fix sessions directory
$path = "sessions"
if (-not (Test-Path $path)) { New-Item -ItemType Directory -Path $path }
icacls $path /grant "$env:USERNAME:(OI)(CI)F" /T

# Fix models directory
$path = "models"
if (-not (Test-Path $path)) { New-Item -ItemType Directory -Path $path }
icacls $path /grant "$env:USERNAME:(OI)(CI)F" /T
```

### Force CPU Mode

```powershell
# Create/toggle .env
echo "OPENWISPR_DEVICE=cpu" >> .env
echo "OPENWISPR_COMPUTE_TYPE=int8" >> .env
```

### Emergency Session Export

```powershell
$exportDir = "$env:USERPROFILE\Desktop\OpenWispr-Emergency-$(Get-Date -Format 'yyyyMMdd')"
New-Item -ItemType Directory -Path $exportDir -Force

Get-ChildItem sessions | ForEach-Object {
    $dest = "$exportDir\$($_.Name)"
    New-Item -ItemType Directory -Path $dest -Force
    @("session.json", "transcript.jsonl", "transcript.txt", "notes.md") | ForEach-Object {
        $src = "$($_.FullName)\$_"
        if (Test-Path $src) { Copy-Item $src $dest -Force }
    }
}

Compress-Archive -Path $exportDir -DestinationPath "$exportDir.zip"
Write-Host "Export complete: $exportDir.zip"
```

---

## Environment Variables Quick Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENWISPR_DEVICE` | auto | Compute device (auto/cpu/cuda) |
| `OPENWISPR_DEFAULT_MODEL` | medium | Model size (tiny/base/small/medium/large-v3) |
| `OPENWISPR_LOG_LEVEL` | INFO | Logging verbosity |
| `OPENWISPR_CAPTURE_DEVICE_ID` | (auto) | Audio device to capture |
| `OPENWISPR_CHUNK_SECONDS` | 3.2 | Processing chunk size |
| `OPENWISPR_MAX_QUEUE_ITEMS` | 16 | Backpressure threshold |
| `OPENWISPR_AUTO_OPTIMIZE` | true | Auto performance tuning |
| `OPENWISPR_HOST` | 127.0.0.1 | API bind address |
| `OPENWISPR_PORT` | 8765 | API port |

---

## Getting Help

If issues persist:

1. Run diagnostics and collect error IDs from logs
2. Check crash dumps in `~/.transcripta/reports/`
3. Include error IDs (8-character codes) when reporting issues
4. Verify against known issues in this guide

Error IDs help trace specific failures through the error handling system.
