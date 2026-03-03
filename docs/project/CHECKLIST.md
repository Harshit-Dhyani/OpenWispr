# Bug Fix Verification Checklist

This document lists all critical bugs that were fixed and how to verify each fix remains in place.

## Quick Verification

Run the verification script:

```powershell
# Python backend verification
python tools/verify_fixes.py

# With strict mode (warnings as errors)
python tools/verify_fixes.py --strict

# JSON output for CI/CD
python tools/verify_fixes.py --json
```

Run the integration tests:

```powershell
# All fix verification tests
pytest tests/test_fixes.py -v

# Specific test category
pytest tests/test_fixes.py::TestCriticalFixes -v
pytest tests/test_fixes.py::TestAudioPipelineInvariants -v
```

## Critical Bugs Fixed

### 1. Iterator Import Bug

**Bug**: `Iterator` was imported from `typing` instead of `collections.abc`, causing runtime errors when used as a return type annotation.

**File**: `app/stt/fast_chunker.py`

**Verification**:
```powershell
# Check import is correct
Select-String -Path app/stt/fast_chunker.py -Pattern "from collections.abc import Iterator"

# Should NOT find this
Select-String -Path app/stt/fast_chunker.py -Pattern "from typing.*Iterator"
```

**Expected Behavior**: Iterator is imported from `collections.abc` for runtime compatibility.

---

### 2. VAD Threshold Duplication

**Bug**: VAD threshold (`-40.0` dB) was hardcoded in multiple places, making it difficult to maintain consistently.

**Files**: `app/core/constants.py`, `app/core/config.py`

**Verification**:
```powershell
# Check constant exists
Select-String -Path app/core/constants.py -Pattern "DEFAULT_THRESHOLD_DB = -40.0"

# Check config uses constant
Select-String -Path app/core/config.py -Pattern "VADConstants.DEFAULT_THRESHOLD_DB"

# Count hardcoded instances (should be minimal)
(Select-String -Path app -Pattern "-40\.0" -Recurse).Count
```

**Expected Behavior**: Single source of truth in `VADConstants.DEFAULT_THRESHOLD_DB`.

---

### 3. Thread Safety in Audio Capture

**Bug**: `LoopbackAudioSource` had race conditions when starting/stopping from different threads.

**File**: `app/audio/capture.py`

**Verification**:
```powershell
# Check for thread lock
Select-String -Path app/audio/capture.py -Pattern "_thread_lock = threading.Lock\(\)"

# Check lock is used in start()
Select-String -Path app/audio/capture.py -Pattern "def start.*\n.*with self._thread_lock" -Multiline

# Check lock is used in stop()
Select-String -Path app/audio/capture.py -Pattern "def stop.*\n.*with self._thread_lock" -Multiline
```

**Expected Behavior**: All thread-sensitive operations protected by `_thread_lock`.

---

### 4. GPU Cache Key Bug

**Bug**: GPU cache key was hardcoded to `float16` even when `compute_type` was `int8`, causing cache misses.

**File**: `app/stt/fast_engine.py`

**Verification**:
```powershell
# Check cache key uses variable
Select-String -Path app/stt/fast_engine.py -Pattern "self.compute_type"

# Should NOT have hardcoded patterns
Select-String -Path app/stt/fast_engine.py -Pattern ":cuda:float16"
Select-String -Path app/stt/fast_engine.py -Pattern ":cuda:int8"
```

**Expected Behavior**: Cache key constructed using `self.compute_type` variable.

---

### 5. Empty Except Blocks

**Bug**: Bare `except: pass` patterns silently swallowed errors, making debugging difficult.

**Files**: Throughout `app/`

**Verification**:
```powershell
# Check for empty except blocks
python -c "
import ast
import sys
from pathlib import Path

issues = []
for file in Path('app').rglob('*.py'):
    try:
        tree = ast.parse(file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for h in node.handlers:
                    if not h.body or (len(h.body) == 1 and isinstance(h.body[0], ast.Pass)):
                        issues.append(f'{file}:{h.lineno}')
    except:
        pass

if issues:
    print('Empty except blocks found:')
    for i in issues:
        print(f'  {i}')
    sys.exit(1)
else:
    print('No empty except blocks found')
"
```

**Expected Behavior**: All except blocks either log, handle, or re-raise errors.

---

### 6. Audio Buffer Capacity Bug

**Bug**: Buffer capacity was less than chunk size, causing deadlock when audio capture couldn't write chunks.

**File**: `app/stt/fast_chunker.py`

**Verification**:
```powershell
# Check buffer capacity is sample_rate * 2
Select-String -Path app/stt/fast_chunker.py -Pattern "buffer_capacity.*sample_rate \* 2"

# Verify chunk size constraint
Select-String -Path app/stt/fast_chunker.py -Pattern "max_chunk_ms = 400"
```

**Invariant**: `buffer_capacity (2s) >= max_chunk (0.4s) * 1.5 = 0.6s` ✓

---

### 7. EventSource Reconnect Storm

**Bug**: Missing reconnect limit caused infinite reconnection loops, draining resources.

**File**: `app/desktop/frontend/src/hooks/useEventSource.ts`

**Verification**:
```powershell
# Check for max reconnect attempts
Select-String -Path app/desktop/frontend/src/hooks/useEventSource.ts -Pattern "maxReconnectAttempts"

# Check for limit check
Select-String -Path app/desktop/frontend/src/hooks/useEventSource.ts -Pattern "maxReconnectAttempts"
```

**Expected Behavior**: Reconnects limited to `maxReconnectAttempts` (default: 10) before falling back to polling.

---

### 8. EventSource Resource Leak

**Bug**: EventSource and timers were not cleaned up on component unmount, causing memory leaks.

**File**: `app/desktop/frontend/src/hooks/useEventSource.ts`

**Verification**:
```powershell
# Check for EventSource close
Select-String -Path app/desktop/frontend/src/hooks/useEventSource.ts -Pattern "\.close\(\)"

# Check for timer cleanup
Select-String -Path app/desktop/frontend/src/hooks/useEventSource.ts -Pattern "clearTimeout"
Select-String -Path app/desktop/frontend/src/hooks/useEventSource.ts -Pattern "clearInterval"

# Check useEffect cleanup
Select-String -Path app/desktop/frontend/src/hooks/useEventSource.ts -Pattern "return \(\) =>"
```

**Expected Behavior**: All subscriptions, timers, and connections cleaned up in useEffect return function.

---

### 9. Soundcard Backend Resource Leak

**Bug**: Audio backend resources weren't released on `stop()`.

**File**: `app/audio/backends/soundcard_backend.py`

**Verification**:
```powershell
# Check resources are cleared
Select-String -Path app/audio/backends/soundcard_backend.py -Pattern "self._recorder_context = None"
Select-String -Path app/audio/backends/soundcard_backend.py -Pattern "self._recorder = None"
Select-String -Path app/audio/backends/soundcard_backend.py -Pattern "self._running = False"
```

**Expected Behavior**: All internal state cleared in `stop()` method.

---

### 10. Numpy Int32 Overflow

**Bug**: Numpy int32 overflow in array indexing calculations caused crashes on large arrays.

**File**: `app/audio/capture.py`, `app/stt/fast_chunker.py`

**Verification**:
```powershell
# Check for int64 casting in offset calculations
Select-String -Path app/audio/capture.py -Pattern "int64"
Select-String -Path app/stt/fast_chunker.py -Pattern "int64"
```

**Expected Behavior**: Large arithmetic operations use `np.int64` to prevent overflow.

---

## Audio Pipeline Invariants

These invariants must hold for the audio pipeline to function correctly:

| Invariant | Constraint | Verification |
|-----------|------------|--------------|
| Buffer Capacity | `>= max_chunk_samples * 1.5` | `buffer_capacity = sample_rate * 2` |
| Chunk Size | `<= sample_rate * 2.0` (2s max) | `max_chunk_ms = 400.0` (0.4s) |
| Sample Rate | `16000 Hz` throughout | `DEFAULT_SAMPLE_RATE = 16000` |
| VAD Threshold | `-40 dB` default | `DEFAULT_THRESHOLD_DB = -40.0` |

Verify invariants:
```powershell
pytest tests/test_fixes.py::TestAudioPipelineInvariants -v
```

---

## Pre-Commit Checklist

Before committing code, verify:

- [ ] Run `python tools/verify_fixes.py` - all checks pass
- [ ] Run `pytest tests/test_fixes.py` - all tests pass
- [ ] No new empty except blocks introduced
- [ ] Iterator imported from `collections.abc` if used at runtime
- [ ] Magic numbers use constants from `constants.py`
- [ ] Thread-sensitive code uses proper locking
- [ ] Resources cleaned up in `finally` blocks or context managers
- [ ] GPU cache keys use variables, not hardcoded values

---

## CI/CD Integration

Add to your CI pipeline:

```yaml
# .github/workflows/verify.yml
name: Bug Fix Verification

on: [push, pull_request]

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install pytest numpy

      - name: Run verification script
        run: python tools/verify_fixes.py --strict

      - name: Run fix tests
        run: pytest tests/test_fixes.py -v
```

---

## Debugging Failed Verifications

### If `test_no_duplicate_vad_threshold` fails

1. Check `app/core/constants.py` has `VADConstants.DEFAULT_THRESHOLD_DB`
2. Ensure `app/core/config.py` imports and uses this constant
3. Remove any hardcoded `-40.0` values in config files

### If `test_thread_safety_in_capture` fails

1. Add `self._thread_lock = threading.Lock()` to `__init__`
2. Wrap `start()` method body with `with self._thread_lock:`
3. Wrap `stop()` method body with `with self._thread_lock:`

### If `test_eventsource_has_cleanup` fails

1. Add `eventSource.close()` in useEffect cleanup function
2. Add `clearTimeout(timeoutRef.current)` for all setTimeout calls
3. Add `clearInterval(intervalRef.current)` for all setInterval calls

---

## Additional Resources

- Debug logging guide: See `AGENTS.md` section "Debug Logging"
- Audio pipeline debugging: See `AGENTS.md` section "Audio Pipeline Debugging Guide"
- Common silent failures: See `AGENTS.md` table "Common Silent Failures"
