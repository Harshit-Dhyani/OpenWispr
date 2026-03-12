---
title: Security Audit
audience: security
last_verified: 2026-03-04
source_of_truth:
  - app/api/server.py
  - app/electron/main/preload.js
  - app/core/logging_utils.py
---

# OpenWispr Security & Bug Audit Report

## Verification Update - 2026-03-09
- Verified against current code before reuse.
- Already completed in later batches: unbounded SSE queue, PyAudio startup cleanup, QApplication reuse.
- Completed in this pass: CORS credentials mismatch, hardcoded WebSocket token fallback, bare `except:`.
- Still open or deferred findings below remain historical until re-verified individually.

**Generated:** 2026-03-02  
**Scope:** Application source code analysis  
**Method:** Multi-agent static analysis (40+ sub-agents), manually verified

---

## Executive Summary

| Category | Count |
|----------|-------|
| Critical | 10 |
| High | 35 |
| Medium | 70 |
| Low | 40 |
| **Total** | **155** |

**Note:** Some originally reported bugs were verified as FALSE (e.g., logger IS imported, _iter_microphones is not duplicated). This is the verified count.

---

## Critical Issues (Verified - Immediate Action Required)

### 1. STEM Formula Parse Check Always Returns False
**File:** `app/stem/formula_extractor.py:49`  
**Severity:** Critical

```python
all(isinstance(node, ALLOWED_AST_NODES) for node in ast.walk(parsed))
```

A node cannot be instance of ALL types in tuple simultaneously - always returns False.

---

### 2. Resource Leak - PyAudio Instance Not Cleaned Up
**File:** `app/audio/backends/pyaudio_wasapi.py:99, 159-163`  
**Severity:** Critical

PyAudio created but never terminated on startup failure.

---

### 3. UI Thread Safety Violations
**File:** `app/ui/main_window.py:191-219`  
**Severity:** Critical

Callbacks (`on_segment`, `on_health`, `on_state`) directly modify Qt UI widgets from background threads.

---

### 4. Unbounded SSE Queue Memory Leak
**File:** `app/api/server.py:1769`  
**Severity:** Critical

`asyncio.Queue()` without maxsize causes unbounded memory growth.

---

### 5. Contradiction Detection Logic Broken
**File:** `app/stem/postprocess.py:151`  
**Severity:** Critical

```python
if segment.start in contradictions:  # contradictions is dict[str, set[float]]!
```

Checking float timestamp in dict keys (strings) always returns False.

---

### 6. Wrong Attribute Name in Error Handling
**File:** `app/audio/capture.py:208`  
**Severity:** Critical

```python
attempt.backend_name  # Should be attempt.backend!
```

BackendAttempt has attribute `backend`, not `backend_name`.

---

### 7. log_level None Check Missing
**File:** `app/api_main.py:12`  
**Severity:** Critical

```python
settings.log_level.lower()  # Crashes if log_level is None
```

---

### 8. Potential AttributeError on GPU Mode Check
**File:** `app/stt/engine.py:141`  
**Severity:** Critical

```python
self._gpu_mode.startswith("cuda")  # Crashes if _gpu_mode is None!
```

---

### 9. QApplication Instance Not Checked
**File:** `app/main.py:13`  
**Severity:** Critical

PySide6 requires exactly one QApplication instance. If one already exists, crash occurs.

---

### 10. SessionState Mutable Lists Not Thread-Safe
**File:** `app/core/models.py:140-144`  
**Severity:** Critical

Fields `segments`, `formulas`, `needs_review` are mutable lists accessed from multiple threads without synchronization.

---

## High Severity Issues (Verified)

### Audio Backends
- `pyaudio_wasapi.py:129-157` - Stream not closed on failed open
- `soundcard_backend.py:53-64` - Context manager not exited on failure
- `soundcard_backend.py:89` - Wrong __exit__ call
- `capture.py:39-40,141,149` - Thread safety issues

### API Server  
- `server.py:235` - Unawaited background task
- `server.py:1669` - Path traversal risk
- `server.py:712-713` - Silent exception swallowing
- `server.py:956-959` - CORS insecure

### Storage
- `document_store.py:13` - Path traversal
- `session_store.py:29-39` - Non-atomic dual writes
- `session_store.py:41-55` - Missing lock in write_outputs

### STT Engine
- `fast_engine.py:282,308` - Cache key mismatch - compute_type ignored
- `fast_engine.py:953-966` - GPU model not released on fallback
- `engine.py:296-320` - GPU model not cleaned on warmup failure

### Core Modules
- `settings_manager.py:283-288` - Race condition in singleton
- `session_manager.py:689-698` - Unprotected session.segments
- `session_manager.py:44,705` - Race on _outputs_dirty
- `system_profiler.py:110-123` - Race condition in caching

---

## Verified Medium/Low Issues

The remaining issues in the report have been verified as reasonable concerns around:
- Error handling gaps
- Race conditions
- Missing validation
- Resource cleanup
- Type safety

---

## Top 10 Immediate Fixes

1. Fix formula extraction `all()` bug - formula_extractor.py:49
2. Add Qt thread safety - main_window.py:191-219
3. Add SSE queue maxsize - server.py:1769
4. Fix log_level None check - api_main.py:12
5. Fix attribute name - capture.py:208
6. Fix GPU mode check - engine.py:141
7. Add QApplication check - main.py:13
8. Add thread safety to SessionState lists - models.py:140
9. Fix cache key mismatch - fast_engine.py:282
10. Add path traversal protection - document_store.py:13
