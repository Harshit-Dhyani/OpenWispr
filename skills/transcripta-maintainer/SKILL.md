# Transcripta Maintainer

Use this skill when maintaining repository-owned documentation for Transcripta.

## Scope

Allowed files:

- `README.md`
- `LICENSE`
- `AGENTS.md`
- `skills/transcripta-maintainer/SKILL.md`
- `skills/transcripta-maintainer/agents/openai.yaml`

Do not touch `app/` or `tests/` unless the user explicitly changes scope. You may reference app/ code locations in documentation and debugging guidance.

## Product Baseline

- Platform: Windows 11
- UI: Electron desktop shell over a local Python backend
- Speech engine: faster-whisper
- Audio capture: WASAPI loopback
- Positioning: local, privacy-first, system-audio transcription

## Workflow

1. Read `AGENTS.md` first.
2. Update only owned files.
3. Prefer exact PowerShell commands.
4. Distinguish verified behavior from intended repo contract when code is absent.
5. Keep docs concise and operational.

## Debugging & Diagnostics

When troubleshooting audio/transcription issues:

### Quick Diagnostics

Check these common failure modes first:

| Check | Command/Location | Expected Result |
|-------|------------------|-----------------|
| Buffer vs chunk size | Add print in `fast_chunker.py` | `buffer >= 1.5 * chunk_size` |
| Chunks produced | Search logs for `chunks_submitted` | Should increment > 0 |
| Audio capture | Check `stream_time` increases | Should increase by ~1s per second |
| VAD triggering | Check `meter_value` in logs | Should be > 0.01 during speech |
| Model loaded | Search logs for `model_loaded` | Should show GPU/CPU device |

### Common Bug Patterns

1. **Buffer Undersizing**: Buffer capacity < chunk size = zero chunks forever
   - Fix: `buffer_capacity = sample_rate * 2` minimum
   
2. **Dead Variable References**: Variables that are checked but never updated
   - Example: `_pending_samples` checked but never populated
   - Fix: Remove dead code or implement proper state management
   
3. **Type Overflow**: Numpy int32 overflow on large array indexing
   - Fix: Cast to int64: `np.int64(samples) * np.int64(multiplier)`
   
4. **SSE Reconnection Loops**: Missing error handling causes infinite reconnect
   - Fix: Add delay + max retry count

### Adding Debug Traces

When adding debug prints to trace audio flow:

```python
# In FastChunker.push():
print(f"[FAST_CHUNKER] pushed {len(samples)} samples, buffer: {self._buffer.available}, adaptive: {self._adaptive_size}")

# In _process_available():
print(f"[FAST_CHUNKER] processing: buffer={self._buffer.available}, adaptive={self._adaptive_size}, condition={self._buffer.available >= self._adaptive_size}")
```

Remove debug prints before committing production code.

### Preventing Regressions

When modifying audio pipeline code:
- Always verify buffer capacity >= max expected chunk
- Never reference variables that aren't populated
- Test with all live modes: realtime, low_latency, balanced, high_accuracy
- Run with DEBUG logging and verify chunks_submitted increments

## Required README Coverage

- Product summary
- Stack summary
- Exact setup commands
- Exact local run commands
- GPU verification commands
- Packaging instructions
- Troubleshooting
- Legal note
- V2 roadmap

## Style

- Use short sections and flat lists.
- Avoid marketing language.
- Avoid speculative implementation detail unless labeled as roadmap or contract.
