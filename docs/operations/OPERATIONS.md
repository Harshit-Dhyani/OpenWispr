---
title: Operations Guide
audience: operators
last_verified: 2026-03-08
source_of_truth:
  - app/api/server.py
  - app/api/routes/system.py
  - app/core/logging_utils.py
  - app/storage/session_store.py
  - app/api/streaming_metrics.py
---

# OpenWispr Operations Guide

Production operations guide for running and maintaining the OpenWispr desktop transcription application on Windows 11.

## Table of Contents

1. [Starting/Stopping the Application](#1-startingstopping-the-application)
2. [Log Locations](#2-log-locations)
3. [Performance Monitoring](#3-performance-monitoring)
4. [Common Issues and Solutions](#4-common-issues-and-solutions)
5. [Backup and Recovery](#5-backup-and-recovery)
6. [Health Check Endpoints](#6-health-check-endpoints)
7. [Emergency Procedures](#7-emergency-procedures)

---

## Legacy Naming Note

> **Note:** The codebase currently uses legacy naming in some places:
> - Data directory: `.transcripta` (instead of `.openwispr`)
> - Environment variables: `TRANSCRIPTA_*` prefix
> - Logger name: `transcripta`
> 
> This is a known migration issue. Future releases will align to `OpenWispr` naming. Currently, operations should use the `.transcripta` path for data storage.

---

## 1. Starting/Stopping the Application

### Development Mode

Start the application from source:

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Start the backend API only
python -m app.api_main

# Start the Electron shell (starts backend automatically)
cd app/electron
npm run dev
```

### Production Mode

After packaging with electron-builder:

```powershell
# Start the packaged application
.\dist\OpenWispr.exe

# Or install and run via shortcut
# Located at: %LOCALAPPDATA%\Programs\OpenWispr\OpenWispr.exe
```

### Environment Variables

Configure before starting:

| Variable | Description | Default |
|----------|-------------|---------|
| `TRANSCRIPTA_DEVICE` | Execution device | `cuda` or `cpu` |
| `TRANSCRIPTA_COMPUTE_TYPE` | GPU compute precision | `float16` or `int8` |
| `TRANSCRIPTA_DEFAULT_MODEL` | Default ASR model | `small` |
| `TRANSCRIPTA_LOG_LEVEL` | Logging verbosity | `INFO` |
| `TRANSCRIPTA_API_HOST` | API bind address | `127.0.0.1` |
| `TRANSCRIPTA_API_PORT` | API port | `8765` |

```powershell
# GPU/CPU configuration
$env:TRANSCRIPTA_DEVICE="cuda"          # or "cpu"
$env:TRANSCRIPTA_COMPUTE_TYPE="float16" # or "int8" for CPU

# Model selection
$env:TRANSCRIPTA_DEFAULT_MODEL="small"  # tiny, base, small, medium, large-v3

# Logging
$env:TRANSCRIPTA_LOG_LEVEL="INFO"       # DEBUG, INFO, WARNING, ERROR
```

### Graceful Shutdown

```powershell
# Via API (preferred for clean session finalization)
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/session/stop" -Method POST

# Or close the Electron window
# Session data is auto-saved every 500ms
```

### Force Stop (If Frozen)

```powershell
# Find Python backend process
Get-Process python | Where-Object {$_.CommandLine -like "*api_main*"} | Select-Object Id, ProcessName

# Kill specific PID
Stop-Process -Id <PID> -Force

# Or kill all related processes
Get-Process | Where-Object {$_.ProcessName -in @("python","electron","OpenWispr")} | Stop-Process -Force
```

---

## 2. Log Locations

### Application Logs

| Location | Description |
|----------|-------------|
| `sessions/<session-slug>/logs/app.log` | Per-session structured logs (JSON Lines format) |
| `sessions/<session-slug>/logs/app.log.1` ... `app.log.5` | Rotated log files (1MB per file, 5 backups) |
| Console | Real-time backend API output |

Log rotation is configured in `app/core/logging_utils.py`:
- Max size: 1MB per file
- Backup count: 5 files
- Format: JSON Lines

### Log Format

Logs are structured JSON (JSON Lines format):

```json
{"time": "2024-01-15T09:23:45", "level": "INFO", "logger": "transcripta", "message": "Session started"}
```

Standard fields:
- `time`: Timestamp in ISO format (`%Y-%m-%dT%H:%M:%S`)
- `level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `logger`: Logger name (e.g., `transcripta`)
- `message`: Log message
- `exception`: Exception info (if an exception occurred)

### Log Levels

- `DEBUG` - Detailed diagnostic information
- `INFO` - General operational information
- `WARNING` - Warning messages
- `ERROR` - Error messages
- `CRITICAL` - Critical errors

### Viewing Logs

```powershell
# View current session logs
Get-Content sessions\<session-name>\logs\app.log -Tail 50 -Wait

# Parse JSON logs for errors
Get-Content sessions\<session-name>\logs\app.log | 
    ConvertFrom-Json | 
    Where-Object { $_.level -eq "ERROR" }

# Search all sessions for errors
Get-ChildItem sessions -Recurse -Filter "app.log" | 
    ForEach-Object { Get-Content $_.FullName | ConvertFrom-Json } |
    Where-Object { $_.level -in @("ERROR", "WARNING") } |
    Select-Object time, level, message

# Export logs for analysis
Get-ChildItem sessions -Recurse -Filter "app.log" |
    ForEach-Object { Get-Content $_.FullName } |
    Out-File transcripta-logs-export.jsonl

# Tail with filtering
Get-Content sessions\study-session\logs\app.log -Wait -Tail 50 | 
    Where-Object { $_ -match '"level":"(ERROR|WARNING)"' }
```

---

## 3. Performance Monitoring

### GPU Memory Monitoring

```powershell
# NVIDIA GPU monitoring
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv -l 1

# Or use in PowerShell loop
while ($true) {
    nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
    Start-Sleep -Seconds 5
}

# One-time GPU check
& "C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe" --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv
```

### Health Endpoint Metrics

Query via health endpoint:

```powershell
# Get current health metrics
$response = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health"
$response.health
```

**Health Response Fields**:

| Field | Description |
|-------|-------------|
| `ok` | Overall health status boolean |
| `health` | Health metrics dict (gpu_mode, queue_depth, dropped_stt_chunks, stt_backpressure_state, estimated_backlog_seconds) |
| `meter_value` | Current audio input level |
| `model_cache` | Cached model information |
| `hotkey` | Hotkey recording status (is_recording, session_id, duration_ms) |

**Example Response**:

```json
{
  "ok": true,
  "health": {
    "gpu_mode": "cuda/float16",
    "queue_depth": 2,
    "dropped_stt_chunks": 0,
    "stt_backpressure_state": "normal",
    "estimated_backlog_seconds": 0.0
  },
  "meter_value": 0.75,
  "model_cache": {
    "small": {
      "gpu_mode": "cuda/float16",
      "runtime_device": "cuda",
      "loaded_at": 1699999999.0
    }
  },
  "hotkey": {
    "is_recording": false,
    "session_id": null,
    "duration_ms": 0
  }
}
```

### Model Cache Management

```powershell
# Check cached models
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/models/cache"

# Clear cache if memory pressure
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/models/cache" -Method DELETE

# Preload model for faster startup
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/models/preload" -Method POST -Body '{"model_name":"small","execution_mode":"auto"}' -ContentType "application/json"
```

### Metrics Endpoints

Available metrics endpoint:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/metrics/streaming` | GET | Streaming transcription metrics |

**Streaming Metrics** (`app/api/streaming_metrics.py`):

| Metric | Description |
|--------|-------------|
| `draft_emit_ms_avg` | Average draft transcript emit latency |
| `commit_emit_ms_avg` | Average final transcript emit latency |
| `refine_ms_avg` | Average text refinement latency |
| `superseded_refines` | Count of superseded refinement operations |
| `draft_samples` | Number of draft samples collected |
| `commit_samples` | Number of commit samples collected |
| `refine_samples` | Number of refine samples collected |

### System Resource Monitoring

```powershell
# CPU and memory usage
Get-Process | Where-Object { $_.ProcessName -match "python|electron" } |
    Select-Object Name, CPU, WorkingSet, PagedMemorySize

# Disk usage for sessions
Get-ChildItem sessions | 
    ForEach-Object { 
        $size = (Get-ChildItem $_.FullName -Recurse | Measure-Object -Property Length -Sum).Sum
        [PSCustomObject]@{ Session = $_.Name; SizeMB = [math]::Round($size/1MB,2) }
    }

# Check available disk space
Get-Volume | Where-Object { $_.DriveLetter -eq 'C' } | Select-Object DriveLetter, SizeRemaining, Size
```

### Automated Health Monitoring Script

```powershell
# health-check.ps1
while ($true) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health" -TimeoutSec 5
        
        if ($health.health.stt_backpressure_state -eq "critical") {
            Write-Warning "$(Get-Date -Format 'HH:mm:ss') CRITICAL: Backpressure detected"
        }
        elseif ($health.health.dropped_stt_chunks -gt 10) {
            Write-Warning "$(Get-Date -Format 'HH:mm:ss') WARNING: Dropped chunks: $($health.health.dropped_stt_chunks)"
        }
        else {
            Write-Host "$(Get-Date -Format 'HH:mm:ss') OK - Queue: $($health.health.queue_depth), Backlog: $($health.health.estimated_backlog_seconds)s"
        }
    }
    catch {
        Write-Error "$(Get-Date -Format 'HH:mm:ss') Health check failed: $_"
    }
    
    Start-Sleep -Seconds 10
}
```

---

## 4. Common Issues and Solutions

### GPU Not Detected

**Symptoms:** Falls back to CPU mode, slow transcription.

```powershell
# Check CUDA device availability
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
python -c "import ctranslate2; print('CUDA devices:', ctranslate2.get_cuda_device_count())"

# Check NVIDIA driver
nvidia-smi
```

**Solution:**
- Update NVIDIA drivers to latest
- Verify CUDA toolkit matches PyTorch expectations
- Use CPU fallback: `$env:TRANSCRIPTA_DEVICE="cpu"`

### Backend Fails to Start (Port 8765 in Use)

**Symptom:** `Address already in use` error.

```powershell
# Find process using port 8765
Get-NetTCPConnection -LocalPort 8765 | 
    Select-Object LocalPort, OwningProcess, @{N="ProcessName";E={(Get-Process -Id $_.OwningProcess).ProcessName}}

# Kill the process
Stop-Process -Id <OwningProcess> -Force
```

### Audio Capture Fails

**Symptoms:** No transcription output, meter shows no activity.

```powershell
# List available devices
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/devices"

# Probe specific device
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/devices/default/probe?duration=5"
```

**Solutions:**
- Disable exclusive mode: Settings > System > Sound > More sound settings > Playback > Properties > Advanced > Uncheck "Exclusive Mode"
- Set correct default playback device
- Ensure audio is playing through speakers/headphones (not muted)
- Restart Windows Audio service: `Restart-Service audiosrv -Force`
- Check Windows privacy settings allow microphone access (loopback requires this)

### High Latency / Backpressure

**Symptoms:** `stt_backpressure_state` shows "elevated" or "critical".

```powershell
# Check current health metrics
(Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health").health
```

**Solutions:**
- Reduce model size (tiny/base for CPU, small for GPU)
- Switch to lower latency profile via settings
- Close other GPU-intensive applications
- Clear model cache: `Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/models/cache" -Method DELETE`

### Out of Memory (OOM)

**Symptom:** `CUDA out of memory` or system freeze.

**Solutions:**

```powershell
# Use smaller model
$env:TRANSCRIPTA_DEFAULT_MODEL="base"

# Use CPU
$env:TRANSCRIPTA_DEVICE="cpu"
$env:TRANSCRIPTA_COMPUTE_TYPE="int8"

# Clear model cache
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/models/cache" -Method DELETE
```

### Session Data Not Saving

**Symptom:** No files in `sessions\<slug>\`.

**Diagnosis:**

```powershell
# Check permissions
Test-Path sessions -PathType Container
Get-Acl sessions | Format-List

# Verify session state
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/session" -Method GET
```

### Session Data Corruption

**Symptoms:** Cannot load session, missing transcripts.

```powershell
# Verify session integrity
Test-Path sessions\<session-name>\session.json
Test-Path sessions\<session-name>\transcript.jsonl

# Recover from transcript.jsonl (line-delimited JSON)
Get-Content sessions\<session-name>\transcript.jsonl | 
    ConvertFrom-Json | 
    ForEach-Object { $_.text } | 
    Out-File recovered-transcript.txt
```

---

## 5. Backup and Recovery

### Settings Storage Location

Settings are stored in `user_settings.json`:

| Location | Description |
|----------|-------------|
| `user_settings.json` | Application root directory (default) |
| `<custom>/user_settings.json` | Custom settings directory (if specified) |

### Session Storage Paths

Session data structure (`app/storage/session_store.py`):

| File | Purpose |
|------|---------|
| `sessions/<slug>/session.json` | Session metadata and configuration |
| `sessions/<slug>/transcript.jsonl` | Raw transcript segments (JSON Lines, append-only) |
| `sessions/<slug>/transcript.txt` | Human-readable transcript |
| `sessions/<slug>/notes.md` | Extracted notes and formulas |
| `sessions/<slug>/formulas.json` | Structured formula data |
| `sessions/<slug>/highlights.txt` | Key highlights |
| `sessions/<slug>/logs/app.log` | Session logs |

### Automated Backup Script

```powershell
# backup-transcripta.ps1
$source = "$PWD\sessions"
$backupRoot = "$env:USERPROFILE\Backups\OpenWispr"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = "$backupRoot\$timestamp"

# Create backup
New-Item -ItemType Directory -Path $backupDir -Force
Copy-Item -Path $source -Destination $backupDir -Recurse -Force

# Keep only last 10 backups
Get-ChildItem $backupRoot | 
    Sort-Object CreationTime -Descending | 
    Select-Object -Skip 10 | 
    Remove-Item -Recurse -Force

Write-Host "Backup completed: $backupDir"
```

### Robocopy Backup (Recommended)

```powershell
# backup-sessions.ps1 - Production-grade backup
$date = Get-Date -Format "yyyyMMdd"
$source = "$PWD\sessions"
$dest = "D:\Backups\OpenWispr\$date"

if (!(Test-Path $dest)) {
    New-Item -ItemType Directory -Path $dest -Force
}

robocopy $source $dest /MIR /R:3 /W:5 /LOG:$dest\backup.log

# Keep only last 30 days
Get-ChildItem "D:\Backups\OpenWispr" | 
    Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-30)} | 
    Remove-Item -Recurse -Force
```

### Session Recovery Procedures

#### Recover from Partial Session

```powershell
# If session.json is corrupted but transcript.jsonl exists
$lines = Get-Content sessions\<session>\transcript.jsonl
$segments = $lines | ConvertFrom-Json

# Rebuild transcript
$segments | ForEach-Object { "[$($_.start) - $($_.end)] $($_.text)" } | Out-File recovered.txt

# Regenerate session metadata
if ($segments) {
    $first = $segments[0]
    $last = $segments[-1]
    $metadata = @{
        id = (Split-Path (Get-Location) -Leaf)
        title = "Recovered Session"
        created_at = $first.timestamp
        updated_at = $last.timestamp
        is_active = $false
    }
    $metadata | ConvertTo-Json | Set-Content sessions\<session>\session.json
}
```

#### Restore from Backup

```powershell
# Restore specific session
Copy-Item -Path "$backupDir\sessions\<session>" -Destination "sessions\" -Recurse -Force

# Or restore all sessions
Copy-Item -Path "$backupDir\sessions\*" -Destination "sessions\" -Recurse -Force

# Verify restored sessions
Get-ChildItem sessions | ForEach-Object {
    $hasJson = Test-Path "$($_.FullName)\session.json"
    $hasTranscript = Test-Path "$($_.FullName)\transcript.jsonl"
    [PSCustomObject]@{
        Session = $_.Name
        Metadata = $hasJson
        Transcript = $hasTranscript
        Status = if ($hasJson -and $hasTranscript) { "OK" } else { "INCOMPLETE" }
    }
}
```

---

## 6. Health Check Endpoints

### API Health Endpoint

```powershell
# Basic health check
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health"
```

**Response Format**:

```json
{
  "ok": true,
  "health": {
    "gpu_mode": "cuda/float16",
    "queue_depth": 2,
    "dropped_stt_chunks": 0,
    "stt_backpressure_state": "normal",
    "estimated_backlog_seconds": 0.0
  },
  "meter_value": 0.75,
  "model_cache": {
    "small": {
      "gpu_mode": "cuda/float16",
      "runtime_device": "cuda",
      "loaded_at": 1699999999.0
    }
  },
  "hotkey": {
    "is_recording": false,
    "session_id": null,
    "duration_ms": 0
  }
}
```

### Available Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | System health and metrics |
| `/api/session` | GET | Full session state |
| `/api/devices` | GET | List audio devices |
| `/api/devices/{id}/probe` | GET | Test device capture |
| `/api/models/cache` | GET/DELETE | Model cache status/clear |
| `/api/models/preload` | POST | Preload model into cache |
| `/api/events` | GET | SSE event stream |
| `/api/system/profile` | GET | Hardware profile |
| `/api/system/optimize` | GET | Auto-optimized settings |
| `/api/metrics/streaming` | GET | Streaming transcription metrics |

### Session Status

```powershell
# Get full session snapshot
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/session"
```

### Expected Health States

| State | Meaning | Action |
|-------|---------|--------|
| `ok: true` | All systems operational | None |
| `stt_backpressure_state: normal` | Processing keeping up | None |
| `stt_backpressure_state: elevated` | Queue building | Monitor closely |
| `stt_backpressure_state: critical` | Falling behind | Reduce load or restart |
| `ok: false` | API unreachable | Check if app is running |

### Automated Health Check Script

```powershell
# health-check.ps1
$health = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health" -Method GET -ErrorAction SilentlyContinue

if ($null -eq $health -or $health.ok -ne $true) {
    Write-Error "Health check failed"
    exit 1
}

if ($health.health.stt_backpressure_state -eq "critical") {
    Write-Error "CRITICAL: System under severe load"
    exit 1
}

if ($health.health.dropped_stt_chunks -gt 0) {
    Write-Warning "WARNING: Dropped chunks: $($health.health.dropped_stt_chunks)"
}

Write-Host "System healthy - meter: $($health.meter_value), queue: $($health.health.queue_depth)"
```

---

## 7. Emergency Procedures

### Error Categories and Recovery

Error categories defined in `app/core/error_handler.py`:

| Category | Error Type | Recovery Action |
|----------|-----------|-----------------|
| `AUDIO_DEVICE_DISCONNECTED` | Device unplugged | Switches to default device |
| `AUDIO_PERMISSION_DENIED` | No mic access | Shows guidance dialog |
| `AUDIO_BACKEND_FAILURE` | Driver issue | Restarts backend with fallback |
| `AUDIO_CAPTURE_ERROR` | Format/channel mismatch | Tries fallback formats |
| `MODEL_OOM` | GPU out of memory | GPU→CPU fallback, reduces batch |
| `MODEL_NOT_FOUND` | Missing model | Auto-download with retry |
| `MODEL_CORRUPTED` | Bad model file | Re-downloads model |
| `MODEL_LOAD_FAILED` | Incompatible model | Falls back to smaller model |
| `NETWORK_BACKEND_UNAVAILABLE` | Backend not responding | Retries with backoff |
| `NETWORK_SYNC_FAILED` | Cloud sync failure | Saves locally, retries later |
| `NETWORK_TIMEOUT` | Slow/unstable connection | Exponential backoff |
| `SESSION_DISK_FULL` | No disk space | Pauses recording, suggests cleanup |
| `SESSION_WRITE_PERMISSION` | Access denied | Prompts for new location |
| `SESSION_CORRUPTED` | Data corruption | Attempts partial recovery |
| `SYSTEM_RESOURCE_EXHAUSTED` | CPU/RAM exhausted | Reduces load |
| `SYSTEM_CONFIG_ERROR` | Invalid configuration | Uses defaults |
| `SYSTEM_UNKNOWN` | Unexpected error | Logs and notifies |

### Recovery Strategies

Recovery strategies from `app/core/recovery_strategies.py`:

| Strategy | Category | Action |
|----------|----------|--------|
| `audio_device_switch` | `AUDIO_DEVICE_DISCONNECTED` | Switches to default/first available |
| `audio_permission_guidance` | `AUDIO_PERMISSION_DENIED` | Shows platform-specific guidance |
| `model_oom_recovery` | `MODEL_OOM` | GPU→CPU, batch size reduction |
| `model_auto_download` | `MODEL_NOT_FOUND`/`CORRUPTED` | Downloads with retry |
| `model_size_fallback` | `MODEL_LOAD_FAILED` | Falls back to smaller model |
| `network_retry` | Network errors | Exponential backoff retry |
| `offline_mode_switch` | `NETWORK_BACKEND_UNAVAILABLE` | Switches to offline mode |
| `disk_full_handler` | `SESSION_DISK_FULL` | Pauses, suggests cleanup |
| `session_corruption_recovery` | `SESSION_CORRUPTED` | Attempts partial JSON recovery |

### Fallback Chains

| Chain | Options | Purpose |
|-------|---------|---------|
| `compute_device` | cuda → cpu | GPU OOM recovery |
| `model_size` | large-v3 → turbo → medium → small → base → tiny | Model load failure |
| `batch_size` | 16 → 8 → 4 → 2 → 1 | Memory reduction |

### Application Freeze

```powershell
# Kill all OpenWispr processes
Get-Process | Where-Object { $_.ProcessName -match "python|electron|OpenWispr" } | Stop-Process -Force

# Verify cleanup
Get-Process | Where-Object { $_.ProcessName -match "python|electron|OpenWispr" }
```

### Session Recovery After Crash

```powershell
# List all sessions with status
Get-ChildItem sessions | ForEach-Object {
    $sessionFile = "$($_.FullName)\session.json"
    if (Test-Path $sessionFile) {
        $session = Get-Content $sessionFile | ConvertFrom-Json
        [PSCustomObject]@{
            Name = $_.Name
            Status = $session.status
            Started = $session.created_at
            Segments = (Get-Content "$($_.FullName)\transcript.jsonl" | Measure-Object).Count
        }
    }
}

# Recover crashed session data
$crashedSession = "sessions\<crashed-session>"
if (Test-Path "$crashedSession\transcript.jsonl") {
    Get-Content "$crashedSession\transcript.jsonl" |
        ConvertFrom-Json |
        Select-Object start, end, text, confidence |
        Export-Csv "$crashedSession\recovered.csv"
}
```

### Audio System Reset

```powershell
# Restart Windows Audio services
Stop-Service audiosrv -Force
Stop-Service AudioEndpointBuilder -Force
Start-Service AudioEndpointBuilder
Start-Service audiosrv
```

### Emergency Data Export

```powershell
# Export all session data for emergency backup
$exportDir = "$env:USERPROFILE\Desktop\OpenWispr-Emergency-Export-$(Get-Date -Format 'yyyyMMdd')"
New-Item -ItemType Directory -Path $exportDir -Force

Get-ChildItem sessions | ForEach-Object {
    $dest = "$exportDir\$($_.Name)"
    New-Item -ItemType Directory -Path $dest -Force
    
    # Copy critical files only
    @("session.json", "transcript.jsonl", "transcript.txt", "notes.md") |
        ForEach-Object {
            $src = "$($_.FullName)\$_"
            if (Test-Path $src) {
                Copy-Item $src $dest -Force
            }
        }
}

Compress-Archive -Path $exportDir -DestinationPath "$exportDir.zip"
Write-Host "Emergency export complete: $exportDir.zip"
```

### Full System Recovery

```powershell
# 1. Kill all processes
Get-Process | Where-Object {$_.ProcessName -in @("python","electron","OpenWispr")} | Stop-Process -Force -ErrorAction SilentlyContinue

# 2. Check disk space
Get-Volume | Where-Object {$_.DriveLetter -eq 'C'} | Select-Object DriveLetter, SizeRemaining, Size

# 3. Clear temp files
Remove-Item -Path $env:TEMP\transcripta* -Recurse -Force -ErrorAction SilentlyContinue

# 4. Verify session data integrity
Get-ChildItem sessions -Directory | ForEach-Object {
    $session = $_.Name
    $files = @("session.json", "transcript.jsonl", "transcript.txt")
    foreach ($file in $files) {
        $path = Join-Path $_.FullName $file
        if (!(Test-Path $path)) {
            Write-Warning "Missing $file in $session"
        }
    }
}

# 5. Restart application
.\venv\Scripts\Activate.ps1
cd app/electron
npm run dev
```

### Escalation Matrix

| Issue | Action |
|-------|--------|
| GPU errors | Check NVIDIA drivers, fallback to CPU mode |
| Audio errors | Reset audio services, check default device |
| Data corruption | Restore from backup, use JSONL recovery |
| App won't start | Check port 8765, kill orphaned processes |
| High memory usage | Clear model cache, restart application |
| Model download fails | Check disk space, verify internet connection |
| Session corruption | Use backup restore or partial recovery |

---

## Quick Reference

```powershell
# Start application
.\venv\Scripts\Activate.ps1; cd app/electron; npm run dev

# Check health
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health"

# View recent logs
Get-Content sessions\<name>\logs\app.log -Tail 20

# Stop gracefully
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/session/stop" -Method POST

# Kill all processes
Get-Process | Where-Object {$_.ProcessName -in @("python","electron")} | Stop-Process -Force

# GPU status
nvidia-smi --query-gpu=name,memory.used --format=csv

# Clear model cache
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/models/cache" -Method DELETE

# List devices
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/devices"

# Backup sessions
robocopy sessions backups\$(Get-Date -Format yyyyMMdd) /MIR
```

| Task | Command |
|------|---------|
| Start dev mode | `npm run dev` (in app/electron) |
| Start backend only | `python -m app.api_main` |
| Check health | `Invoke-RestMethod http://127.0.0.1:8765/api/health` |
| View logs | `Get-Content sessions\<slug>\logs\app.log -Wait -Tail 50` |
| GPU status | `nvidia-smi --query-gpu=name,memory.used --format=csv` |
| Clear models | `Invoke-RestMethod http://127.0.0.1:8765/api/models/cache -Method DELETE` |
| List devices | `Invoke-RestMethod http://127.0.0.1:8765/api/devices` |
| Kill all | `Get-Process \| ?{$_.ProcessName -in @("python","electron")} \| Stop-Process -Force` |
| Backup sessions | `robocopy sessions backups\$(Get-Date -Format yyyyMMdd) /MIR` |
