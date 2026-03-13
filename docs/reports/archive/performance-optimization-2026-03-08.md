# Performance Optimization Report - 2026-03-08

## Summary
13 performance issues found.

## P0 - Must Fix (5 issues)

### P0-1: O(n²) Segment Deduplication
- **File**: app/core/session_manager.py
- **Line**: 742-759
- **Code**:
```python
for previous in reversed(self.session.segments[:-1]):
```
- **Why**: Every segment iterates ALL previous segments = O(n²)
- **Fix**: Use hash-based lookup

### P0-2: Unbounded Debug Audio
- **File**: app/api/server.py
- **Line**: 1600-1603
- **Code**:
```python
session.debug_audio_chunks.append(
    np.asarray(audio, dtype=np.float32, order="C").copy()
)
```
- **Why**: Grows unbounded during debug sessions
- **Fix**: Add max size limit

### P0-3: Unbounded Processing Times
- **File**: app/stt/engine.py
- **Line**: 86
- **Code**: `self._processing_times: list[float] = []`
- **Why**: List grows forever
- **Fix**: Use deque with maxlen

### P0-4: MODEL_TTL Too Long
- **File**: app/stt/model_pool.py
- **Line**: 179
- **Code**: `MODEL_TTL_SECONDS = 1800`
- **Why**: 30 minutes - models stay loaded too long
- **Fix**: Change to 300

### P0-5: max_models Too High
- **File**: app/stt/model_pool.py
- **Line**: 67,183
- **Code**: `max_models: int = 2` and `max_models: int = 3`
- **Why**: Can hold 15GB+ in memory
- **Fix**: Change to 1

## P1 - Should Fix (5 issues)

### P1-1: Inefficient LRU deque.remove()
- **File**: app/stt/model_pool.py
- **Line**: 286-288
- **Code**:
```python
if cache_key in self._access_queue:
    self._access_queue.remove(cache_key)
```
- **Why**: deque.remove() is O(n)

### P1-2: list.pop(0) in Audio Pipeline
- **File**: app/audio/wispr_pipeline.py
- **Line**: 294-296
- **Code**: `self._pre_buffer.pop(0)`
- **Why**: pop(0) shifts all elements - O(n)

### P1-3: Blocking time.sleep
- **File**: app/stt/model_pool.py
- **Line**: 396
- **Code**: `time.sleep(delay)`
- **Why**: Blocks thread during retries

### P1-4: Deep Copy Settings Sync
- **File**: app/api/transport/settings_sync.py
- **Line**: 243,257
- **Code**: `copy.deepcopy(current)`
- **Why**: Expensive on every sync

### P1-5: Default Model Too Large
- **File**: app/config/constants.py
- **Line**: 70
- **Code**: `DEFAULT_MODEL_NAME = "medium"`
- **Why**: Uses 5GB VRAM
- **Fix**: Change to "small"

### P1-6: Default Compute Type
- **File**: app/config/constants.py
- **Line**: 71
- **Code**: `DEFAULT_COMPUTE_TYPE = "float16"`
- **Why**: int8 is 40% faster
- **Fix**: Change to "int8"

## P2 - Nice to Have (2 issues)

### P2-1: Queue Maxsize Too Small
- **File**: app/audio/pipeline_base.py
- **Line**: 139-141
- **Code**: `maxsize=max(1, config.max_buffer_size // 800)`

### P2-2: Audio Copies
- **File**: app/audio/system_pipeline.py
- **Line**: 162
- **Code**: `self._buffers[self._write_idx] = data.copy()`

## Quick Wins
1. MODEL_TTL_SECONDS: 1800 → 300
2. max_models: 3 → 1
3. DEFAULT_MODEL_NAME: medium → small
4. DEFAULT_COMPUTE_TYPE: float16 → int8

## Done-When
- [ ] All P0 fixed
