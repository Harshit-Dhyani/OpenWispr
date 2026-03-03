# Transcripta Troubleshooting Guide

Comprehensive guide for diagnosing and resolving common issues in Transcripta.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Error Categories & Recovery](#error-categories--recovery)
- [Common Issues](#common-issues)
- [Diagnostic Commands](#diagnostic-commands)
- [Log Locations](#log-locations)
- [PowerShell Quick Fixes](#powershell-quick-fixes)

---

## Quick Diagnostics

Run these commands first to identify your issue:

```powershell
# Audio diagnostics
python tools/diagnostics/check-audio.py --verbose

# System/GPU diagnostics  
python tools/diagnostics/check-system.py --verbose

# Check if backend is responding
curl http://127.0.0.1:8765/health
```

---

## Error Categories & Recovery

### Audio Errors

| Error | Cause | Automatic Recovery | Manual Fix |
|-------|-------|-------------------|------------|
| `AUDIO_DEVICE_DISCONNECTED` | Headset/speaker unplugged | Switches to default device | Reconnect device or select new device |
| `AUDIO_PERMISSION_DENIED` | Windows privacy settings | Shows guidance dialog | Grant microphone permissions in Settings |
| `AUDIO_BACKEND_FAILURE` | WASAPI/driver failure | Restarts backend | Restart app or update drivers |
| `AUDIO_CAPTURE_ERROR` | Format/channel mismatch | Tries fallback formats | Check audio device properties |

**Recovery Strategy** (`app/core/recovery_strategies.py:331-411`):
- Audio device recovery switches to default/first available device
- Permission errors show platform-specific guidance
- Backend failures trigger automatic restart with format fallback

### Model Errors

| Error | Cause | Automatic Recovery | Manual Fix |
|-------|-------|-------------------|------------|
| `MODEL_OOM` | GPU out of memory | Falls back to CPU + reduces batch size | Close GPU apps or use smaller model |
| `MODEL_NOT_FOUND` | Model not downloaded | Auto-downloads model | Check internet/disk space |
| `MODEL_CORRUPTED` | Bad model file | Re-downloads model | Clear `~/.transcripta/models/` |
| `MODEL_LOAD_FAILED` | Incompatible model | Falls back to smaller model | Check model compatibility |

**Recovery Strategy** (`app/core/recovery_strategies.py:417-589`):
- OOM: GPU → CPU fallback chain with batch size reduction (16→8→4→2→1)
- Missing/corrupted: Auto-download with retry (max 3 attempts)
- Load failure: Model size fallback (large-v3 → turbo → medium → small → base → tiny)

### Session Errors

| Error | Cause | Automatic Recovery | Manual Fix |
|-------|-------|-------------------|------------|
| `SESSION_DISK_FULL` | No free space | Pauses recording, suggests cleanup | Free disk space |
| `SESSION_WRITE_PERMISSION` | Access denied | Prompts for new location | Check folder permissions |
| `SESSION_CORRUPTED` | File corruption | Attempts partial recovery | Restore from backup |

**Recovery Strategy** (`app/core/recovery_strategies.py:701-867`):
- Disk full: Pauses recording, identifies temp/cache files for cleanup
- Corruption: Attempts partial JSON extraction, then backup restore

### Network Errors

| Error | Cause | Automatic Recovery | Manual Fix |
|-------|-------|-------------------|------------|
| `NETWORK_BACKEND_UNAVAILABLE` | Backend not responding | Retries with backoff | Check if backend is running |
| `NETWORK_SYNC_FAILED` | Cloud sync failure | Saves locally, retries later | Check internet connection |
| `NETWORK_TIMEOUT` | Slow/unstable connection | Exponential backoff | Check network stability |

**Recovery Strategy** (`app/core/recovery_strategies.py:594-696`):
- Retry with exponential backoff (1s, 2s, 4s, max 30s)
- After exhaustion: Switches to offline mode

---

## Common Issues

### 1. No Audio Captured

**Symptoms:** VU meter shows no activity, transcripts are empty

**Diagnostic:**
```powershell
python tools/diagnostics/check-audio.py --verbose --test <device_id>
```

**Causes & Fixes:**

| Cause | Fix |
|-------|-----|
| Wrong capture device selected | Run diagnostic to find correct loopback device |
| Windows exclusive mode enabled | Disable: Sound → Playback → Device → Advanced → Uncheck "Exclusive Mode" |
| Audio playing through different output | Ensure audio plays through the captured device |
| WASAPI permissions | Check Windows Privacy → Microphone permissions |

**Backend Fallback** (`app/audio/backends/factory.py:34-83`):
- Primary: PyAudioWASAPI (supports loopback)
- Fallback: Soundcard (if installed)
- Both fail: Check `tools/diagnostics/check-audio.py` output

---

### 2. GPU Not Detected

**Symptoms:** Transcription uses CPU (slow), logs show "CUDA not available"

**Diagnostic:**
```powershell
# Check PyTorch CUDA
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}'); print(f'Devices: {torch.cuda.device_count()}')"

# Full system check
python tools/diagnostics/check-system.py
```

**Fixes:**

| Step | Command/Action |
|------|----------------|
| 1. Verify NVIDIA drivers | `nvidia-smi` - should show driver version |
| 2. Check CUDA toolkit | `python -c "import torch; print(torch.version.cuda)"` |
| 3. Force CPU fallback | Set `TRANSCRIPTA_DEVICE=cpu` in `.env` |
| 4. Reinstall PyTorch with CUDA | `pip install torch --index-url https://download.pytorch.org/whl/cu121` |

**Compute Fallback Chain** (`app/core/recovery_strategies.py:163-188`):
- Primary: CUDA (if `torch.cuda.is_available()`)
- Fallback: CPU (always available)

---

### 3. Transcription Slow

**Symptoms:** High latency, falling behind real-time

**Diagnostic:**
```powershell
# Check GPU usage
nvidia-smi

# Check queue depth (via API)
curl http://127.0.0.1:8765/health
```

**Fixes:**

| Solution | How |
|----------|-----|
| Use smaller model | Set `TRANSCRIPTA_DEFAULT_MODEL=small` or `base` |
| Reduce chunk duration | Set `TRANSCRIPTA_CHUNK_SECONDS=1.0` |
| Enable auto-optimization | Set `TRANSCRIPTA_AUTO_OPTIMIZE=true` |
| Check GPU memory | `nvidia-smi` - ensure < 90% VRAM used |
| Close other GPU apps | Close games, video editors, browsers |

**Live Mode Profiles** (`app/core/config.py:373-379`):
- `ultra`: 100ms chunks (fastest, lowest quality)
- `realtime`: 200ms chunks (fast)
- `low_latency`: 500ms chunks
- `balanced`: 1s chunks (default)
- `high_accuracy`: 2s chunks (slowest, best quality)

---

### 4. Model Download Fails

**Symptoms:** "Model not found" error, download progress stuck

**Diagnostic:**
```powershell
# Check internet
ping huggingface.co

# Check disk space
Get-PSDrive C | Select-Object Used,Free
```

**Fixes:**

| Cause | Fix |
|-------|-----|
| No internet | Connect to internet or use offline mode |
| Disk full | Free up space in `TRANSCRIPTA_DOWNLOAD_ROOT` (default: `./models`) |
| HuggingFace down | Try again later or use mirror |
| Corporate firewall | Set `HF_ENDPOINT=https://hf-mirror.com` |

**Manual Download**:
```powershell
# Download manually to cache
huggingface-cli download Systran/faster-whisper-medium --local-dir ./models
```

---

### 5. High Latency / Backpressure

**Symptoms:** Delay between speech and transcription, queue warnings

**Diagnostic:**
```powershell
# Check queue depth
curl http://127.0.0.1:8765/health | ConvertFrom-Json | Select queue_depth

# Check processing time in logs
Get-Content sessions/<session>/logs/app.log | Select-String "processing_time"
```

**Fixes:**

| Setting | Default | Reduce To |
|---------|---------|-----------|
| `TRANSCRIPTA_CHUNK_SECONDS` | 3.2 | 1.0 or 0.5 |
| `TRANSCRIPTA_DEFAULT_MODEL` | medium | small |
| `TRANSCRIPTA_MAX_QUEUE_ITEMS` | 16 | 8 |
| `TRANSCRIPTA_BEAM_SIZE` | 5 | 1 |

---

### 6. Session Not Saving

**Symptoms:** Transcripts lost after closing app

**Diagnostic:**
```powershell
# Check sessions directory
Get-ChildItem sessions/ -ErrorAction SilentlyContinue

# Check permissions
Get-Acl sessions/ | Format-List

# Check disk space
Get-PSDrive C | Select-Object Free
```

**Fixes:**

| Cause | Fix |
|-------|-----|
| Permissions | Run: `icacls sessions/ /grant "$env:USERNAME:(OI)(CI)F"` |
| Disk full | Free up space or change `TRANSCRIPTA_EXPORT_ROOT` |
| Path doesn't exist | Create directory: `mkdir sessions` |

---

### 7. Hotkey Not Working

**Symptoms:** Push-to-talk doesn't activate recording

**Diagnostic:**
```powershell
# Check if hotkey service is running
curl http://127.0.0.1:8765/modes/status
```

**Fixes:**

| Cause | Fix |
|-------|-----|
| App not focused | Click on app window first |
| Hotkey conflict | Change hotkey in settings |
| Permissions | Run app as administrator (Windows) |

---

### 8. Electron Won't Start

**Symptoms:** UI doesn't appear, "connection refused" errors

**Diagnostic:**
```powershell
# Check port availability
netstat -ano | findstr 8765

# Check Python processes
Get-Process python -ErrorAction SilentlyContinue

# Check logs
Get-Content sessions/latest/logs/app.log -Tail 50
```

**Fixes:**

| Step | Command |
|------|---------|
| Kill orphaned Python | `taskkill /F /IM python.exe` |
| Kill by port | `netstat -ano \| findstr 8765` then `taskkill /PID <pid> /F` |
| Verify venv | `.\venv\Scripts\activate` |
| Check port conflict | Change `TRANSCRIPTA_PORT` in `.env` |

---

## Diagnostic Commands

### Audio Diagnostics

```powershell
# List all devices
python tools/diagnostics/check-audio.py --verbose

# Test specific device
python tools/diagnostics/check-audio.py --test <device_id>

# JSON output for scripting
python tools/diagnostics/check-audio.py --json
```

### System Diagnostics

```powershell
# Full system check
python tools/diagnostics/check-system.py --verbose

# JSON output
python tools/diagnostics/check-system.py --json
```

### API Health Check

```powershell
# Check backend health
curl http://127.0.0.1:8765/health

# Check current modes
curl http://127.0.0.1:8765/modes/status

# Check active config
curl http://127.0.0.1:8765/config
```

### GPU Diagnostics

```powershell
# NVIDIA GPU status
nvidia-smi

# NVIDIA GPU every 1 second
nvidia-smi -l 1

# PyTorch CUDA check
python -c "import torch; print(torch.cuda.is_available())"

# CTranslate2 check
python -c "import ctranslate2; print(ctranslate2.get_cuda_device_count())"
```

---

## Log Locations

### Application Logs

| Location | Description |
|----------|-------------|
| `sessions/<session_id>/logs/app.log` | Session-specific logs (JSON format) |
| `~/.transcripta/reports/crash_*.json` | Crash dumps with full context |
| Console output | Real-time logs when running in terminal |

### Log Format

Logs use JSON format (`app/core/logging_utils.py:10-48`):
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

### Log Rotation

- Max size: 1MB (`TRANSCRIPTA_LOG_MAX_BYTES`)
- Backup count: 5 files (`TRANSCRIPTA_LOG_BACKUP_COUNT`)
- Location: `sessions/<session>/logs/app.log`

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
echo "TRANSCRIPTA_DEVICE=cpu" >> .env
echo "TRANSCRIPTA_COMPUTE_TYPE=int8" >> .env
```

### Download Model Manually

```powershell
# Using huggingface-cli
huggingface-cli download Systran/faster-whisper-medium --local-dir ./models

# Or using Python
python -c "from faster_whisper import WhisperModel; WhisperModel('medium', device='cpu')"
```

### Check System Resources

```powershell
# Disk space
Get-PSDrive C | Select-Object Used,Free,@{N="Used%";E={[math]::Round($_.Used/($_.Used+$_.Free)*100,2)}}

# Memory
Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory

# CPU
Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors
```

---

## Environment Variables Reference

Key variables from `.env.example`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `TRANSCRIPTA_DEVICE` | auto | Compute device (auto/cpu/cuda) |
| `TRANSCRIPTA_DEFAULT_MODEL` | medium | Model size (tiny/base/small/medium/large-v3) |
| `TRANSCRIPTA_LOG_LEVEL` | INFO | Logging verbosity |
| `TRANSCRIPTA_CAPTURE_DEVICE_ID` | (auto) | Audio device to capture |
| `TRANSCRIPTA_CHUNK_SECONDS` | 3.2 | Processing chunk size |
| `TRANSCRIPTA_MAX_QUEUE_ITEMS` | 16 | Backpressure threshold |
| `TRANSCRIPTA_AUTO_OPTIMIZE` | true | Auto performance tuning |
| `TRANSCRIPTA_HOST` | 127.0.0.1 | API bind address |
| `TRANSCRIPTA_PORT` | 8765 | API port |

---

## Getting Help

If issues persist:

1. Run full diagnostics: `python tools/diagnostics/check-system.py --json > diagnostics.json`
2. Collect logs from `sessions/*/logs/app.log`
3. Check crash dumps in `~/.transcripta/reports/`
4. Include error IDs from log messages when reporting issues

Error IDs (8-character codes like `abc123`) help trace specific failures in the error handling system (`app/core/error_handler.py:90`).
