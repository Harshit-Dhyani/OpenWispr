---
title: Latency Playbook
audience: developers
last_verified: 2026-03-08
source_of_truth:
  - app/api/routes/session.py
  - app/api/routes/system.py
  - app/api/service.py
  - app/core/recovery_strategies.py
  - AGENTS.md
---

# OpenWispr Latency Playbook

**Purpose:** "What to do when lag happens" - Diagnostic and remediation guide  
**Owner:** Backend + Performance Team

---

## 1. Quick Diagnosis (30 seconds)

### 1.1 Check Current Latency

```powershell
# Check if backend is responsive
curl http://127.0.0.1:8765/api/health

# Get current session snapshot (includes health metrics)
curl http://127.0.0.1:8765/api/session

# Get streaming metrics
curl http://127.0.0.1:8765/api/metrics/streaming
```

### 1.2 Identify the Bottleneck

| Symptom | Likely Cause | Section |
|---------|--------------|---------|
| 3+ second delay before any text appears | Chunk size too large | 2.1 |
| Text appears, then pauses, then catches up | Queue backlog | 2.2 |
| UI updates feel jerky | Output throttling / polling | 2.3 |
| High CPU during transcription | Model too large for hardware | 2.4 |
| First word fast, then degrades | Memory pressure / no GPU | 2.5 |

---

## 2. Diagnostic Commands

### 2.1 Check Audio Pipeline

```powershell
# View current audio settings
curl http://127.0.0.1:8765/api/settings | jq '.audio'

# Expected: block_size should be < 1000 (samples)
# If 4000+ (250ms), audio buffer is too large
```

**Remediation:**
```python
# In session_manager.py or capture.py
block_size = int(self.settings.sample_rate * 0.02)  # 20ms = 320 samples @ 16kHz
```

### 2.2 Check Queue Status

```powershell
# Get queue depth and processing stats from health endpoint
curl http://127.0.0.1:8765/api/health | jq '.health.queue_depth, .health.real_time_factor, .health.stt_backpressure_state'
```

**Interpretation:**
| queue_depth | RTF | backpressure_state | Status |
|-------------|-----|-------------------|--------|
| 0-5 | < 1.0 | normal | Normal |
| 5-15 | 0.8-1.0 | elevated | Busy |
| 15-30 | > 1.0 | high | Backlogged |
| 30+ | >> 1.0 | critical | Critical - dropping chunks |

**Remediation:**
```powershell
# Option 1: Reduce max queue (faster backpressure)
# In config.py
max_queue_items = 16  # Was 64

# Option 2: Switch to smaller model
$env:TRANSCRIPTA_DEFAULT_MODEL="tiny"  # Was "small"

# Option 3: Use GPU if available
$env:TRANSCRIPTA_DEVICE="cuda"
```

### 2.3 Check UI Refresh Rate

```powershell
# Check output refresh setting
curl http://127.0.0.1:8765/api/settings | jq '.output_refresh_seconds'

# Check polling interval in logs
# Look for: "poll_interval_ms" in renderer logs
```

**Remediation:**
```python
# In config.py
output_refresh_seconds = 0.5  # Was 2.0
```

```typescript
// In frontend - reduce polling interval
scheduleNextPoll(snapshot.session?.status === 'running' ? 300 : 4000);
// Was: 1200ms
```

### 2.4 Check Model Performance

```powershell
# Get model state (includes current model info)
curl http://127.0.0.1:8765/api/models/state | jq '.'

# Check inference latency from session snapshot
curl http://127.0.0.1:8765/api/session | jq '.health.inference_latency_ms'

# Check which device is being used
curl http://127.0.0.1:8765/api/health | jq '.health.gpu_mode, .health.execution_mode'
```

**Expected inference times:**
| Model | GPU | CPU | Status |
|-------|-----|-----|--------|
| tiny | 30-60ms | 100-200ms | Real-time capable |
| base | 80-150ms | 250-400ms | Good |
| small | 150-300ms | 600-1000ms | Borderline on CPU |
| medium | 400-800ms | 2-4s | Too slow for real-time |
| large-v3 | 1-2s | 5-8s | Not real-time |

**Remediation:**
```powershell
# For CPU users - MUST use tiny
$env:TRANSCRIPTA_DEFAULT_MODEL="tiny"
$env:TRANSCRIPTA_DEVICE="cpu"

# For GPU users (in order of speed/quality trade-off)
$env:TRANSCRIPTA_DEFAULT_MODEL="base"  # or "small" for better quality
$env:TRANSCRIPTA_DEVICE="cuda"

# Disable language detection (saves 50-100ms per chunk)
$env:TRANSCRIPTA_DEFAULT_LANGUAGE="en"
```

### 2.5 Check Resource Usage

```powershell
# Windows - check Python process
Get-Process python | Select-Object CPU, WorkingSet, PagedMemorySize

# Check GPU if available
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv
```

**Red flags:**
- CPU > 80% sustained
- Memory > 4GB for Python process
- GPU memory full (causes fallback to CPU)

---

## 3. Quick Fixes

### 3.1 Immediate Actions (No Restart)

| Action | Command | Effect |
|--------|---------|--------|
| Switch to realtime mode | Settings UI → Mode: "Realtime" | -1.6 to -2.8s latency |
| Reduce beam size | `beam_size = 1` | -20-50ms per chunk |
| Disable VAD | `vad_filter = False` | -10-30ms per chunk |
| Fixed language | `language = "en"` | -50-100ms per chunk |

### 3.2 Configuration Changes (Requires Restart)

**Create `~/.transcripta/config.json`:**

```json
{
  "audio": {
    "block_size_ms": 20,
    "sample_rate": 16000
  },
  "transcription": {
    "live_mode": "realtime",
    "chunk_seconds": 0.4,
    "overlap_seconds": 0.08,
    "output_refresh_seconds": 0.5
  },
  "model": {
    "default_model": "tiny",
    "device": "cpu",
    "compute_type": "int8",
    "default_language": "en"
  },
  "vad": {
    "threshold": 0.35,
    "min_silence_duration_ms": 200
  }
}
```

### 3.3 Environment Variables

```powershell
# Windows PowerShell - Set before starting OpenWispr
$env:TRANSCRIPTA_DEFAULT_MODEL="tiny"
$env:TRANSCRIPTA_DEVICE="cpu"
$env:TRANSCRIPTA_DEFAULT_LANGUAGE="en"
$env:TRANSCRIPTA_LOG_LEVEL="INFO"  # Reduce log noise

# Then launch
.\OpenWispr.exe
```

---

## 4. Common Scenarios

### 4.1 "It was working, now it's slow"

**Checklist:**
1. [ ] Has a larger model been selected recently?
2. [ ] Is GPU being used? (Check `nvidia-smi`)
3. [ ] Has queue depth increased? (Check metrics)
4. [ ] System under memory pressure? (Check Task Manager)

**Most likely:** Model fallback to CPU due to GPU memory pressure.

**Fix:**
```powershell
# Clear model cache
Invoke-RestMethod http://127.0.0.1:8765/api/models/cache -Method DELETE

# Or force model reload via environment
$env:TRANSCRIPTA_FORCE_MODEL_RELOAD="1"
# Restart OpenWispr
```

### 4.2 "First word is fast, then it lags"

**Root cause:** Queue accumulation (RTF > 1.0)

**Fix:**
```python
# Add flow control in session_manager.py audio loop
for chunk in chunks:
    success = self.transcriber.submit(chunk)
    if not success:
        time.sleep(0.1)  # Let STT catch up
```

### 4.3 "UI feels unresponsive during recording"

**Root cause:** Renderer churn from audio-level updates

**Fix:**
```typescript
// Cap update frequency in frontend
const THROTTLE_MS = 50;  // Max 20 updates/sec
let lastUpdate = 0;

onAudioLevel((level) => {
  const now = Date.now();
  if (now - lastUpdate < THROTTLE_MS) return;
  lastUpdate = now;
  updateWaveform(level);
});
```

### 4.4 "Text appears in bursts instead of streaming"

**Root cause:** Output throttling (2.0s) + UI polling (1.2s) = 3.2s worst case

**Fix:**
```python
# config.py
output_refresh_seconds = 0.5  # Was 2.0
```

```typescript
// Frontend polling
scheduleNextPoll(running ? 300 : 4000);  // Was 1200ms
```

---

## 5. Profiling Tools

### 5.1 Enable Detailed Logging

```powershell
$env:TRANSCRIPTA_LOG_LEVEL="DEBUG"
$env:TRANSCRIPTA_PROFILE="1"
```

### 5.2 Latency Breakdown

```python
# In your code
from app.core.performance_monitor import get_monitor

monitor = get_monitor()
monitor.start_latency_profile("session_123")
monitor.record_latency_phase("session_123", "audio_capture")
# ... processing ...
monitor.record_latency_phase("session_123", "model_inference")
# ... more processing ...
breakdown = monitor.end_latency_profile("session_123")
print(breakdown)
```

### 5.3 Export Metrics

```python
# Export to file for analysis
monitor.export_metrics("performance_dump.json", format="json")
```

---

## 6. Escalation

If latency issues persist after applying fixes:

1. **Collect evidence:**
   ```powershell
   curl http://127.0.0.1:8765/api/metrics/snapshot > metrics.json
   curl http://127.0.0.1:8765/api/settings > settings.json
   ```

2. **Check logs:**
   - Windows: `%APPDATA%\OpenWispr\logs\`
   - Look for: `latency`, `queue`, `inference`, `rtf`

3. **Create issue with:**
   - Hardware specs (CPU, RAM, GPU)
   - Model being used
   - Mode settings
   - Metrics snapshot
   - Log excerpt

---

*Generated from performance audit 2026-03-01 and OPTIMIZATION_ROADMAP.md.*
