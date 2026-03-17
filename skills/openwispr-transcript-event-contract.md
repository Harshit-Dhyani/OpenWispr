# Skill: OpenWispr Transcript Event Contract

## Purpose
Verify transcript events follow contract - ensuring SSE/WebSocket event formats are consistent, JSON-safe, and properly structured.

## When to Use
- When changing transcript streaming
- When modifying event payloads
- During code reviews of transcript/websocket changes
- When debugging streaming issues

## Verification Steps

### 1. Check event format consistency
Transcript events should use consistent JSON structure:
- Draft updates: replace by stable segment key, never append duplicate
- Final transcripts: single canonical final form (`aggregated_clean_text`)
- Command to find event emitters:
  ```bash
  grep -rn "emit\|send\|broadcast" app/ --include="*.py" | grep -i "transcript"
  ```

### 2. Verify JSON-safe encoding
All transcript payloads must be JSON-safe (no functions, circular refs, raw objects):
- Command to find transcript event construction:
  ```bash
  grep -rn "transcript\|Transcript" app/api/ --include="*.py"
  ```

### 3. Check SSE/WebSocket handling
- Events route through single JSON-safe encoder
- No raw transcript in logs (must be redacted)
- Commands:
  ```bash
  # Find SSE endpoints
  grep -rn "sse\|StreamingResponse" app/api/
  
  # Find WebSocket handlers
  grep -rn "websocket\|WebSocket" app/api/
  ```

### 4. Validate segment key stability
- Draft updates must replace by stable segment key
- No duplicate live text accumulation
- Command to verify:
  ```bash
  grep -rn "segment.*key\|segment_key" app/stt/ --include="*.py"
  ```

### 5. Check transcript state isolation
- Dictation and session transcript state must be isolated
- No shared live draft or snapshot state between modes
- Commands:
  ```bash
  # Find transcript state
  grep -rn "transcript.*state\|live.*transcript" app/ --include="*.py"
  
  # Check for shared state
  grep -rn "self.transcript\|shared.*transcript" app/stt/
  ```

### 6. Verify paste_text is sole copy source
- `paste_text` is the only Electron injection/copy source
- `aggregated_clean_text` is canonical final transcript
- Command:
  ```bash
  grep -rn "paste_text\|aggregated_clean_text" app/ --include="*.py"
  ```

## Files to Check

| Component | Path | What to Check |
|-----------|------|---------------|
| API Routes | `app/api/routes/*.py` | SSE/WebSocket endpoints |
| STT Modules | `app/stt/**/*.py` | Event construction, encoding |
| Frontend | `app/electron/frontend/src/` | Event handling, display |

## Event Contract Rules

1. **Single encoder**: All transcript events use one JSON-safe encoder
2. **Segment keys**: Draft updates replace by stable key, never append
3. **Isolation**: Dictation and session states are separate
4. **Copy source**: `paste_text` for Electron, `aggregated_clean_text` for final
5. **No secrets in logs**: Raw transcript never logged

## Example Commands

```bash
# Find transcript event emitters
grep -rn "emit.*transcript\|send_event" app/stt/ --include="*.py"

# Check SSE response format
grep -A20 "StreamingResponse" app/api/routes/transcribe.py

# Verify JSON encoding
python -c "import json; json.dumps(get_transcript_payload())"

# Find transcript tests
pytest tests/ -v -k "transcript"
```

## Common Issues to Detect

1. Duplicate live text accumulation (should replace by key)
2. Raw transcript logged without redaction
3. Multiple encoders causing inconsistent formats
4. Shared state between dictation and session modes
5. Non-JSON-safe payloads causing WebSocket failures
