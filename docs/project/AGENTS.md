# Transcripta Agent Guidance

## Ownership

Owned files for documentation maintenance:

- `README.md`
- `LICENSE`
- `docs/project/AGENTS.md`
- `skills/transcripta-maintainer/SKILL.md`
- `skills/transcripta-maintainer/agents/openai.yaml`

Do not edit application code or tests unless the user explicitly expands scope.

## Operating Rules

- Treat this repository as a Windows 11 local desktop transcription project.
- Preserve the privacy-first product position.
- Keep all capture, inference, and storage guidance local-first unless the user requests otherwise.
- Treat the primary desktop shell as Electron with a local Python backend.
- Ignore unrelated edits made by others outside the owned files.
- Do not refactor, rename, or restructure `app/` as part of documentation work.
- Do not invent cloud features as if they already exist.
- If code is missing, document the intended contract clearly and avoid claiming implemented behavior that has not been verified.

## Documentation Standard

- Write concise, production-grade docs.
- Include exact PowerShell commands for setup, run, verification, and packaging.
- Prefer Windows-native instructions first.
- Call out GPU and CPU execution paths separately where relevant.
- Include practical troubleshooting, not generic filler.
- Keep legal language minimal and non-advisory.

## Maintainer Skill

If `skills/transcripta-maintainer/` exists, follow it for documentation-only maintenance tasks. If it is missing or incomplete, continue with the constraints in this file.

## Debug Logging

### Enable DEBUG Mode

Set in `.env`:

```env
TRANSCRIPTA_LOG_LEVEL=DEBUG
```

Restart the application after changing.

### DEBUG Level Coverage

| Component | Logged Events |
|-----------|---------------|
| Audio Capture | Input levels, probe results, device selection, queue status, buffer overflows |
| Session Management | Start/stop events, settings changes, callback registrations, state transitions |
| Transcription | Model loading/unloading, segment generation, latency per segment, backpressure warnings, queue depth |
| STEM Processing | Formula detection, STEM reviews, contradiction identification, fallback triggers |
| API Endpoints | Request/response payloads, SSE connection open/close, heartbeat events, error responses |
| Quality Filtering | Suppression decisions, filler word detection, low-confidence filtering, punctuation handling |

### Log Format

JSON structured logging with consistent fields:

```json
{
  "timestamp": "2026-03-01T14:32:15.123Z",
  "level": "DEBUG",
  "logger": "transcripta.audio.capture",
  "message": "Audio buffer queue depth: 3 frames",
  "session_id": "team-meeting-2026-03-01",
  "extra": {
    "queue_depth": 3,
    "buffer_ms": 120
  }
}
```

### Log Locations

- **Console**: Output to terminal during `npm run dev`
- **Per-session file**: `sessions/<session-slug>/logs/app.log`

### Viewing Logs

Real-time console (development):
```powershell
npm run dev
```

Tail session log file:
```powershell
Get-Content sessions/team-meeting-2026-03-01/logs/app.log -Wait
```

Search for specific events:
```powershell
Select-String -Path sessions/team-meeting-2026-03-01/logs/app.log -Pattern "segment"
```

Filter by log level:
```powershell
Select-String -Path sessions/team-meeting-2026-03-01/logs/app.log -Pattern '"level":"WARN"'
```

### Performance Considerations

DEBUG mode increases I/O overhead significantly. Use only for troubleshooting:

- Log files grow rapidly during long sessions
- JSON serialization adds CPU overhead
- File writes may cause micro-stutters on slower disks

Switch back to `TRANSCRIPTA_LOG_LEVEL=INFO` for normal operation.

### Example Log Entries

Session start:
```json
{"timestamp":"2026-03-01T14:30:00.000Z","level":"DEBUG","logger":"transcripta.session","message":"Session started","session_id":"demo-session","extra":{"device":"Microphone (Realtek)","sample_rate":16000}}
```

Transcription segment:
```json
{"timestamp":"2026-03-01T14:30:05.456Z","level":"DEBUG","logger":"transcripta.transcription","message":"Segment transcribed","session_id":"demo-session","extra":{"segment_id":12,"latency_ms":245,"text":"The quick brown fox","confidence":0.94}}
```

STEM formula detected:
```json
{"timestamp":"2026-03-01T14:30:12.789Z","level":"DEBUG","logger":"transcripta.stem","message":"Formula detected","session_id":"demo-session","extra":{"formula":"E=mc²","context":"physics discussion","review_triggered":true}}
```

Quality filter suppression:
```json
{"timestamp":"2026-03-01T14:30:15.012Z","level":"DEBUG","logger":"transcripta.quality","message":"Segment suppressed","session_id":"demo-session","extra":{"reason":"filler_word","text":"um","confidence":0.32}}
```

## Audio Pipeline Debugging Guide

### Critical Invariants (MUST CHECK)

When modifying audio processing code, verify these invariants or the pipeline will silently fail:

| Invariant | Constraint | Why It Matters |
|-----------|------------|----------------|
| Buffer Capacity | `buffer_capacity >= max_chunk_samples * 1.5` | Prevents deadlock when chunk size exceeds buffer |
| Chunk Size | `chunk_samples <= sample_rate * 2.0` | Keeps latency under 2 seconds |
| Sample Rate | `16000 Hz` throughout pipeline | Mismatches cause pitch/speed errors |
| VAD Threshold | `-40 dB` default | Too high = misses speech; too low = noise triggers |

### Common Silent Failures

#### Symptom: `chunks_submitted: 0` but audio is capturing
**Root Cause**: Buffer capacity < required chunk size
**Fix**: Increase buffer capacity to at least `max_expected_chunk * 1.5`
**Location**: `app/stt/fast_chunker.py` line ~404

#### Symptom: `emit_early` never true
**Root Cause**: Checking dead/uninitialized variables (e.g., `_pending_samples` that is never populated)
**Fix**: Remove dead code or populate the variable
**Pattern**: Never check `len(self._pending_samples)` if it's never updated

#### Symptom: High memory usage / crashes
**Root Cause**: Numpy int32 overflow in array indexing
**Fix**: Cast to int64 before arithmetic: `int64(samples) * int64(multiplier)`
**Location**: `app/audio/capture.py` offset calculations

#### Symptom: SSE disconnect storms
**Root Cause**: Missing error handling in EventSource reconnection
**Fix**: Add 1s delay and max retry limit
**Location**: `app/electron/frontend/src/hooks/useEventSource.ts`

### Debugging Workflow

When audio captures but no transcription appears:

1. **Check buffer vs chunk size**:
   ```python
   print(f"[DEBUG] buffer={buffer.available}, chunk_size={adaptive_size}")
   ```
   If `buffer < chunk_size`, increase buffer capacity.

2. **Check VAD state**:
   ```python
   print(f"[DEBUG] vad_state={vad.state}, energy={energy_db}dB")
   ```
   If energy is always below threshold, adjust `vad_threshold_db`.

3. **Check chunk production**:
   ```python
   print(f"[DEBUG] chunks_created={len(chunks)}, samples_in_chunk={len(chunk.samples)}")
   ```
   If chunks are created but not submitted, check transcriber queue.

### Code Review Checklist

Before committing audio pipeline changes:

- [ ] Buffer capacity is at least 1.5x max chunk size
- [ ] No dead variables checked in conditions
- [ ] All numpy array operations use appropriate dtypes
- [ ] Sample rate is consistent throughout (16kHz)
- [ ] Added debug prints for new pipeline stages
- [ ] Tested with "balanced" live mode (1.6s chunks)
