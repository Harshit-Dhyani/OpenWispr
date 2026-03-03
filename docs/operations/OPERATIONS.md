# Transcripta Operations Guide

Production operations guide for running and maintaining the Transcripta desktop transcription application on Windows 11.

## Table of Contents

1. [Starting/Stopping the Application](#1-startingstopping-the-application)
2. [Log Locations](#2-log-locations)
3. [Performance Monitoring](#3-performance-monitoring)
4. [Common Issues and Solutions](#4-common-issues-and-solutions)
5. [Backup and Recovery](#5-backup-and-recovery)
6. [Updating the Application](#6-updating-the-application)
7. [Health Check Endpoints](#7-health-check-endpoints)
8. [Emergency Procedures](#8-emergency-procedures)

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
cd app/desktop
npm run dev
```

### Production Mode

After packaging with electron-builder:

```powershell
# Start the packaged application
.\dist\Transcripta.exe

# Or install and run via shortcut
# Located at: %LOCALAPPDATA%\Programs\Transcripta\Transcripta.exe
```

### Environment Variables

Configure before starting:

```powershell
# GPU/CPU configuration
$env:TRANSCRIPTA_DEVICE="cuda"          # or "cpu"
$env:TRANSCRIPTA_COMPUTE_TYPE="float16" # or "int8" for CPU

# Model selection
$env:TRANSCRIPTA_DEFAULT_MODEL="small"  # tiny, base, small, medium, large-v3

# Logging
$env:TRANSCRIPTA_LOG_LEVEL="INFO"       # DEBUG, INFO, WARNING, ERROR

# Storage location
$env:TRANSCRIPTA_EXPORT_ROOT="D:\\TranscriptaSessions"
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
Get-Process | Where-Object {$_.ProcessName -in @("python","electron","Transcripta")} | Stop-Process -Force
```

---

## 2. Log Locations

### Application Logs

| Location | Description |
|----------|-------------|
| `sessions/<session-slug>/logs/app.log` | Per-session structured logs (JSON) |
| `app/desktop/` | Electron console output (dev mode) |
| Console | Real-time backend API output |

### Log Format

Logs are structured JSON (JSON Lines format):

```json
{"time": "2024-01-15T09:23:45", "level": "INFO", "logger": "transcripta", "message": "Session started", "session_id": "abc123"}
```

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
    Select-Object time, level, message, session_id

# Export logs for analysis
Get-ChildItem sessions -Recurse -Filter "app.log" |
    ForEach-Object { Get-Content $_.FullName } |
    Out-File transcripta-logs-export.jsonl

# Tail with filtering
Get-Content sessions\study-session\logs\app.log -Wait -Tail 50 | 
    Where-Object { $_ -match '"level":"(ERROR|WARNING)"' }
```

### Log Rotation

Logs rotate at 1MB per file with 5 backups (`app.log.1` through `app.log.5`).

### Electron Logs

```powershell
# View Electron console (DevTools)
# In running app: Ctrl+Shift+I or F12
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

# Check CUDA device availability
python -c "import ctranslate2; print('CUDA devices:', ctranslate2.get_cuda_device_count())"

# One-time GPU check
& "C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe" --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv
```

### Latency Metrics

Query via health endpoint:

```powershell
# Get current health metrics
$response = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health"
$response.health

# Key metrics to monitor:
# - queue_depth: Pending transcription chunks
# - dropped_stt_chunks: Lost audio due to backlog
# - stt_backpressure_state: "normal", "warning", or "critical"
# - estimated_backlog_seconds: Processing delay
# - dropped_frames: Audio capture issues
```

**Expected Response:**
```json
{
  "ok": true,
  "health": {
    "audio_stream_active": true,
    "gpu_mode": "cuda/float16",
    "execution_mode": "auto",
    "queue_depth": 2,
    "dropped_stt_chunks": 0,
    "stt_backpressure_state": "normal",
    "estimated_backlog_seconds": 0.5
  },
  "meter_value": 0.75,
  "model_cache": {
    "small": {
      "gpu_mode": "cuda/float16",
      "runtime_device": "cuda",
      "loaded_at": 1699999999.0
    }
  }
}
```

### Model Cache Status

```powershell
# Check cached models
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/models/cache"

# Clear cache if memory pressure
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/models/cache" -Method DELETE

# Preload model for faster startup
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/models/preload" -Method POST -Body '{"model_name":"small","execution_mode":"auto"}' -ContentType "application/json"
```

### System Resource Monitoring

```powershell
# CPU and memory usage
Get-Process | Where-Object { $_.ProcessName -match "transcripta|python|electron" } |
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

### Session Snapshot

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/session" -Method GET | ConvertTo-Json -Depth 10
```

### Event Stream (SSE) Monitoring

```powershell
# Connect to SSE endpoint for real-time events
$client = New-Object System.Net.WebClient
$stream = $client.OpenRead("http://127.0.0.1:8765/api/events")
$reader = New-Object System.IO.StreamReader($stream)

while ($null -ne ($line = $reader.ReadLine())) {
    if ($line -match "^data:") {
        $data = $line.Substring(5) | ConvertFrom-Json
        Write-Host "[$($data.type)] $($data.payload)"
    }
}
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
# Verify CUDA installation
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
python -c "import ctranslate2; print('CUDA devices:', ctranslate2.get_cuda_device_count())"

# Reinstall GPU dependencies
pip install --force-reinstall ctranslate2 faster-whisper

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

**Symptoms:** `stt_backpressure_state` shows "warning" or "critical".

```powershell
# Check current performance mode
(Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/session").session.live_mode

# Check queue depth
(Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health").health.queue_depth
```

**Solutions:**
- Reduce model size (tiny/base for CPU, small for GPU)
- Switch to lower latency mode: `live_mode="realtime"` or `"low_latency"`
- Close other GPU-intensive applications
- Verify GPU is being used: `(Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health").health.gpu_mode`

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

### Critical Files to Backup

| File | Purpose |
|------|---------|
| `sessions/<slug>/session.json` | Session metadata and configuration |
| `sessions/<slug>/transcript.jsonl` | Raw transcript segments (JSON Lines) |
| `sessions/<slug>/transcript.txt` | Human-readable transcript |
| `sessions/<slug>/notes.md` | Extracted notes and formulas |
| `sessions/<slug>/formulas.json` | Structured formula data |
| `sessions/<slug>/highlights.txt` | Key highlights |
| `sessions/<slug>/logs/app.log` | Session logs |

### Automated Backup Script

```powershell
# backup-transcripta.ps1
$source = "$PWD\sessions"
$backupRoot = "$env:USERPROFILE\Backups\Transcripta"
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

### Scheduled Backup with Task Scheduler

```powershell
# Register daily backup
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-File $PWD\backup-transcripta.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At "02:00"
Register-ScheduledTask -TaskName "TranscriptaBackup" -Action $action -Trigger $trigger
```

### Robocopy Backup (Recommended)

```powershell
# backup-sessions.ps1 - Production-grade backup
$date = Get-Date -Format "yyyyMMdd"
$source = "$PWD\sessions"
$dest = "D:\Backups\Transcripta\$date"

if (!(Test-Path $dest)) {
    New-Item -ItemType Directory -Path $dest -Force
}

robocopy $source $dest /MIR /R:3 /W:5 /LOG:$dest\backup.log

# Keep only last 30 days
Get-ChildItem "D:\Backups\Transcripta" | 
    Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-30)} | 
    Remove-Item -Recurse -Force
```

### Recovery Procedures

#### Recover from Partial Session

```powershell
# If session.json is corrupted but transcript.jsonl exists
$lines = Get-Content sessions\<session>\transcript.jsonl
$segments = $lines | ConvertFrom-Json

# Rebuild transcript
$segments | ForEach-Object { "$($_.start): $($_.text)" } | Out-File recovered.txt

# Regenerate session metadata
if ($segments) {
    $first = $segments[0]
    $last = $segments[-1]
    $metadata = @{
        id = (Split-Path (Get-Location) -Leaf)
        title = "Recovered Session"
        created_at = $first.timestamp
        updated_at = $last.timestamp
        duration_seconds = $last.end
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

## 6. Updating the Application

### Update Process

```powershell
# 1. Stop all running sessions
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/session/stop" -Method POST

# 2. Backup current installation
$version = (Get-Content package.json | ConvertFrom-Json).version
Compress-Archive -Path . -DestinationPath "..\transcripta-backup-$version.zip"

# 3. Pull latest code
git pull origin main

# 4. Update Python dependencies
.\venv\Scripts\Activate.ps1
pip install -e .[dev] --upgrade

# 5. Update Electron dependencies
cd app/desktop
npm install

# 6. Run tests
pytest tests\ -q

# 7. Restart application
npm run dev
```

### Version Verification

```powershell
# Python backend version
python -c "import app; print(app.__version__)"

# Electron version
node -e "console.log(require('./package.json').version)"

# Check all component versions
Write-Host "Python packages:"
pip list | Select-String -Pattern "faster-whisper|ctranslate2|fastapi|uvicorn"

Write-Host "Node packages:"
npm list electron electron-builder
```

### Model Updates

Models are cached in `models/` directory. To refresh:

```powershell
# Clear model cache via API
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/models/cache" -Method DELETE

# Remove model files (forces re-download)
Remove-Item -Path models -Recurse -Force
New-Item -ItemType Directory -Path models

# Preload updated model
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/models/preload" -Method POST -Body '{"model_name":"small","execution_mode":"auto"}' -ContentType "application/json"

# Check model download progress
# Monitor via SSE events on /api/events or check logs
Get-Content sessions\*\logs\app.log -Tail 20 | Select-String -Pattern "model|download"
```

---

## 7. Health Check Endpoints

### API Health Endpoint

```powershell
# Basic health check
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health"
```

**Expected Response:**
```json
{
  "ok": true,
  "health": {
    "audio_stream_active": true,
    "gpu_mode": "cuda/float16",
    "execution_mode": "auto",
    "queue_depth": 2,
    "dropped_stt_chunks": 0,
    "stt_backpressure_state": "normal",
    "estimated_backlog_seconds": 0.5
  },
  "meter_value": 0.75,
  "model_cache": {
    "small": {
      "gpu_mode": "cuda/float16",
      "runtime_device": "cuda",
      "loaded_at": 1699999999.0
    }
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

### Session Status

```powershell
# Get full session snapshot
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/session"

# Key fields:
# - session.status: "idle", "running", "stopped", "error"
# - health.audio_stream_active: Boolean
# - health.last_error: Last error message
# - runtime_revision: Incrementing counter for changes
```

### Expected Health States

| State | Meaning | Action |
|-------|---------|--------|
| `ok: true` | All systems operational | None |
| `stt_backpressure_state: normal` | Processing keeping up | None |
| `stt_backpressure_state: warning` | Queue building | Monitor closely |
| `stt_backpressure_state: critical` | Falling behind | Reduce load or restart |
| `ok: false` | API unreachable | Check if app is running |

### Automated Health Check Script

```powershell
# health-check.ps1
$health = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health" -Method GET -ErrorAction SilentlyContinue

if ($null -eq $health -or $health.ok -ne $true) {
    Write-Error "Health check failed"
    # Restart logic here
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

---

## 8. Emergency Procedures

### Application Freeze

```powershell
# Kill all Transcripta processes
Get-Process | Where-Object { $_.ProcessName -match "transcripta|electron|python" } | Stop-Process -Force

# Verify cleanup
Get-Process | Where-Object { $_.ProcessName -match "transcripta|electron" }
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
            Started = $session.started_at
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

### GPU Recovery

```powershell
# Reset NVIDIA GPU (requires admin)
nvidia-smi --gpu-reset -i 0

# Or restart display driver
# WARNING: Will cause screen flicker
# devcon restart "PCI\VEN_10DE*"
```

### Audio System Reset

```powershell
# Restart Windows Audio services
Stop-Service audiosrv -Force
Stop-Service AudioEndpointBuilder -Force
Start-Service AudioEndpointBuilder
Start-Service audiosrv

# Clear audio device cache
Remove-Item -Path "$env:LOCALAPPDATA\Microsoft\Windows\INetCache\counters.dat" -Force -ErrorAction SilentlyContinue
```

### Emergency Data Export

```powershell
# Export all session data for emergency backup
$exportDir = "$env:USERPROFILE\Desktop\Transcripta-Emergency-Export-$(Get-Date -Format 'yyyyMMdd')"
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
Get-Process | Where-Object {$_.ProcessName -in @("python","electron","Transcripta")} | Stop-Process -Force -ErrorAction SilentlyContinue

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
cd app/desktop
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

---

## Quick Reference

```powershell
# Start application
.\venv\Scripts\Activate.ps1; cd app/desktop; npm run dev

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
| Start dev mode | `npm run dev` (in app/desktop) |
| Start backend only | `python -m app.api_main` |
| Check health | `Invoke-RestMethod http://127.0.0.1:8765/api/health` |
| View logs | `Get-Content sessions\<slug>\logs\app.log -Wait -Tail 50` |
| GPU status | `nvidia-smi --query-gpu=name,memory.used --format=csv` |
| Clear models | `Invoke-RestMethod http://127.0.0.1:8765/api/models/cache -Method DELETE` |
| List devices | `Invoke-RestMethod http://127.0.0.1:8765/api/devices` |
| Kill all | `Get-Process \| ?{$_.ProcessName -in @("python","electron")} \| Stop-Process -Force` |
| Backup sessions | `robocopy sessions backups\$(Get-Date -Format yyyyMMdd) /MIR` |
