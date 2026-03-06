---
title: Performance Documentation
audience: developers
last_verified: 2026-03-04
source_of_truth:
  - app/core/performance_monitor.py
  - app/stt/streaming_engine.py
---

# Transcripta Performance Documentation

**Scope:** Real-time transcription performance tuning  
**Owner:** Backend + Performance Team

---

## 1. Current Tunables (from Code)

### 1.1 StreamingConfig (`app/stt/streaming_engine.py:119-140`)

```python
@dataclass(slots=True)
class StreamingConfig:
    window_ms: int = 400
    overlap_ms: int = 80
    min_chunk_ms: int = 200
    target_latency_ms: float = 200.0
    min_beam_size: int = 1
    max_beam_size: int = 5
    latency_history_size: int = 10
    prefix_context_enabled: bool = True
    max_prefix_words: int = 5
    context_decay_factor: float = 0.8
    partial_threshold_ms: float = 150.0
    stabilization_window: int = 3
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `window_ms` | 400 | Audio window size in milliseconds |
| `overlap_ms` | 80 | Overlap between consecutive windows |
| `min_chunk_ms` | 200 | Minimum chunk size for processing |
| `target_latency_ms` | 200.0 | Target latency for beam adaptation |
| `min_beam_size` | 1 | Minimum beam search width |
| `max_beam_size` | 5 | Maximum beam search width |
| `latency_history_size` | 10 | Samples for latency trend analysis |
| `prefix_context_enabled` | True | Enable context carryover between chunks |
| `max_prefix_words` | 5 | Maximum words to carry as prefix |
| `context_decay_factor` | 0.8 | Reliability decay for context |
| `partial_threshold_ms` | 150.0 | Threshold for partial result emission |
| `stabilization_window` | 3 | Windows to check for result stability |

### 1.2 Mode-Specific Configurations (`streaming_engine.py:720-746`)

**WISPR Mode (fast, low-latency):**
```python
wispr_config = StreamingConfig(
    window_ms=400,
    overlap_ms=80,
    target_latency_ms=200.0,
    min_beam_size=1,
    max_beam_size=3,
)
```

**SYSTEM Mode (accurate, batched):**
```python
system_config = StreamingConfig(
    window_ms=1000,
    overlap_ms=200,
    target_latency_ms=1000.0,
    min_beam_size=1,
    max_beam_size=5,
)
```

### 1.3 Queue Configuration (`streaming_engine.py:666`)

```python
self._queue: asyncio.Queue[AudioChunk] = asyncio.Queue(maxsize=64)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `maxsize` | 64 | Maximum queue depth for audio chunks |

### 1.4 Profiling Tunables (`performance_monitor.py`)

```python
# LatencyProfiler (line 93)
max_samples: int = 1000

# ResourceMonitor (line 208)
history_size: int = 3600  # 1 hour at 1s intervals
_interval: float = 1.0    # seconds between samples

# PerformanceDashboard (line 390)
_stream_interval: float = 1.0  # WebSocket broadcast interval
```

---

## 2. AdaptiveBeamController Logic

### 2.1 Algorithm (`app/stt/streaming_engine.py:202-262`)

```python
class AdaptiveBeamController:
    """Dynamically adjusts beam size based on latency targets."""

    def __init__(
        self,
        target_latency_ms: float,
        min_beam_size: int = 1,
        max_beam_size: int = 5,
        history_size: int = 10,
    ) -> None:
        self.target_latency_ms = target_latency_ms
        self.min_beam_size = min_beam_size
        self.max_beam_size = max_beam_size
        self._latency_history: deque[float] = deque(maxlen=history_size)
        self._current_beam_size = min_beam_size
        self._lock = threading.Lock()
```

### 2.2 Adaptation Logic (`streaming_engine.py:225-249`)

```python
def _adapt_beam_size(self) -> None:
    """Adjust beam size based on recent latency trends."""
    if len(self._latency_history) < 3:
        return

    recent_avg = sum(self._latency_history) / len(self._latency_history)
    p95 = sorted(self._latency_history)[int(len(self._latency_history) * 0.95)]

    # If consistently over target, reduce beam size
    if p95 > self.target_latency_ms * 1.2:
        if self._current_beam_size > self.min_beam_size:
            self._current_beam_size -= 1

    # If consistently under target, can increase for better quality
    elif recent_avg < self.target_latency_ms * 0.6:
        if self._current_beam_size < self.max_beam_size:
            self._current_beam_size += 1
```

**Adaptation Thresholds:**
- Reduce beam: p95 latency > target × 1.2
- Increase beam: avg latency < target × 0.6
- Minimum history: 3 samples before adaptation

### 2.3 Mode-Specific Targets (`streaming_engine.py:325-331`)

| Mode | Target Latency | Min Beam | Max Beam | Config Source |
|------|---------------|----------|----------|---------------|
| WISPR | 200ms | 1 | 3 | `StreamingConfig` (line 725) |
| SYSTEM | 1000ms | 1 | 5 | `StreamingConfig` (line 733) |

---

## 3. VAD Settings

### 3.1 Default Configuration (`streaming_engine.py:469-473`)

```python
vad_parameters = {
    "threshold": 0.35 if self.mode == TranscriptionMode.WISPR else 0.4,
    "min_silence_duration_ms": 200,
    "speech_pad_ms": 200,
}
```

### 3.2 VAD Parameters

| Parameter | WISPR | SYSTEM | Description |
|-----------|-------|--------|-------------|
| `threshold` | 0.35 | 0.40 | Voice detection sensitivity (lower = more sensitive) |
| `min_silence_duration_ms` | 200ms | 200ms | Silence to trigger segmentation |
| `speech_pad_ms` | 200ms | 200ms | Padding around speech segments |

### 3.3 VAD Usage Context

VAD is enabled in `_transcribe_window()` (line 468):
```python
transcribe_kwargs: dict[str, Any] = {
    "vad_filter": True,
    "vad_parameters": {
        "threshold": 0.35 if self.mode == TranscriptionMode.WISPR else 0.4,
        "min_silence_duration_ms": 200,
        "speech_pad_ms": 200,
    },
    # ... other params
}
```

### 3.4 Performance Impact

- VAD latency cost: ~10-30ms per chunk
- False positive rate: Tune threshold for environment
- Aggressive settings (160ms silence) may cut fast speakers

---

## 4. Queue Depths and Backpressure

### 4.1 Async Queue (`streaming_engine.py:666`)

```python
self._queue: asyncio.Queue[AudioChunk] = asyncio.Queue(maxsize=64)
```

### 4.2 Backpressure States

| State | Trigger | Action |
|-------|---------|--------|
| `normal` | Queue has space | Accept chunk |
| `dropping_newest` | Queue Full | Drop incoming chunk, return False |

### 4.3 Submission Flow Control (`streaming_engine.py:834-846`)

```python
async def submit(self, chunk: AudioChunk) -> bool:
    """Submit audio chunk for transcription with backpressure handling."""
    if self._state != EngineState.READY:
        logger.warning(f"Cannot submit chunk: engine state is {self._state.name}")
        return False

    try:
        self._queue.put_nowait(chunk)
        self._metrics.queue_depth = self._queue.qsize()
        return True
    except asyncio.QueueFull:
        logger.warning("Queue full, chunk dropped")
        return False
```

---

## 5. Profiling Hooks

### 5.1 LatencyProfiler (`app/core/performance_monitor.py:90-203`)

```python
class LatencyProfiler:
    """Detailed latency profiling with phase breakdown."""

    def __init__(self, max_samples: int = 1000):
        self._samples: deque = deque(maxlen=max_samples)
        self._active_profiles: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._phase_times: Dict[str, deque] = {
            "audio_capture": deque(maxlen=max_samples),
            "preprocessing": deque(maxlen=max_samples),
            "vad_detection": deque(maxlen=max_samples),
            "model_inference": deque(maxlen=max_samples),
            "postprocessing": deque(maxlen=max_samples),
            "websocket_emit": deque(maxlen=max_samples),
        }
```

### 5.2 Recording Metrics (`performance_monitor.py:621-631`)

```python
# Start profiling
def start_latency_profile(self, profile_id: str) -> None:
    self._latency_profiler.start_profile(profile_id)

# Record phase transition
def record_latency_phase(self, profile_id: str, phase: str) -> None:
    self._latency_profiler.record_phase(profile_id, phase)

# End and get breakdown
def end_latency_profile(self, profile_id: str) -> Optional[LatencyBreakdown]:
    return self._latency_profiler.end_profile(profile_id)
```

### 5.3 PerformanceDashboard Metrics (`performance_monitor.py:458-494`)

| Metric | Type | Description |
|--------|------|-------------|
| `first_word_latency_ms` | Gauge | Time to first transcription |
| `avg_inter_word_latency_ms` | Gauge | Between-word latency |
| `end_to_end_latency_ms` | Gauge | Total pipeline latency |
| `real_time_factor` | Gauge | RTF (processing time / audio duration) |
| `words_per_minute` | Gauge | Throughput rate |
| `cache_hit_rate` | Gauge | Model cache efficiency |
| `queue_depth` | Gauge | Current queue size |
| `buffer_health_percent` | Gauge | Audio buffer fill level |
| `audio_drop_rate` | Gauge | Dropped audio percentage |
| `vad_accuracy` | Gauge | VAD detection accuracy |
| `session_duration_seconds` | Counter | Active session duration |
| `segment_count` | Counter | Total segments produced |
| `total_words` | Counter | Total words transcribed |

### 5.4 Resource Monitoring (`performance_monitor.py:205-373`)

```python
class ResourceMonitor:
    def __init__(self, history_size: int = 3600):
        self._history: deque = deque(maxlen=history_size)
        self._interval = 1.0  # seconds between samples
```

Monitored resources (from `_collect_snapshot()`):
- CPU percent (process-specific via psutil)
- Memory MB / percent
- GPU utilization (via pynvml, if available)
- GPU memory MB
- Thread count
- Open file count
- Disk I/O (read/write MB)

### 5.5 Alert Thresholds (`performance_monitor.py:662-688`)

```python
def _setup_default_thresholds(self) -> None:
    self._alert_manager.set_threshold(
        "resource.cpu_percent",
        max_value=80.0,
        severity=AlertSeverity.WARNING,
    )
    self._alert_manager.set_threshold(
        "resource.memory_mb",
        max_value=4096.0,
        severity=AlertSeverity.WARNING,
    )
    self._alert_manager.set_threshold(
        "latency.end_to_end",
        max_value=500.0,
        severity=AlertSeverity.WARNING,
    )
    self._alert_manager.set_threshold(
        "audio.drop_rate",
        max_value=0.05,
        severity=AlertSeverity.ERROR,
    )
    self._alert_manager.set_threshold(
        "audio.buffer_health",
        min_value=20.0,
        severity=AlertSeverity.ERROR,
    )
```

| Metric | Threshold | Severity |
|--------|-----------|----------|
| `resource.cpu_percent` | max=80.0 | WARNING |
| `resource.memory_mb` | max=4096.0 | WARNING |
| `latency.end_to_end` | max=500.0 | WARNING |
| `audio.drop_rate` | max=0.05 | ERROR |
| `audio.buffer_health` | min=20.0 | ERROR |

---

## 6. Performance Tuning Quick Reference

### 6.1 For Minimum Latency

```python
# streaming_engine.py - WISPR mode config (line 720-726)
wispr_config = StreamingConfig(
    window_ms=200,        # Was 400
    overlap_ms=40,        # Was 80
    target_latency_ms=100.0,  # Was 200.0
    min_beam_size=1,
    max_beam_size=2,      # Was 3
)

# Environment
TRANSCRIPTA_WISPR_MODEL="tiny"
TRANSCRIPTA_DEVICE="cpu"
TRANSCRIPTA_COMPUTE_TYPE="int8"
```

### 6.2 For Maximum Accuracy

```python
# streaming_engine.py - SYSTEM mode config (line 728-734)
system_config = StreamingConfig(
    window_ms=2000,       # Was 1000
    overlap_ms=400,       # Was 200
    target_latency_ms=2000.0,  # Was 1000.0
    min_beam_size=3,      # Was 1
    max_beam_size=5,
)

# VAD threshold (line 470)
vad_threshold = 0.4  # More strict voice detection
```

### 6.3 Model Selection by Hardware

| Hardware | Model | Device | Compute | Expected Latency |
|----------|-------|--------|---------|-----------------|
| High-end GPU | large-v3 | cuda | float16 | 400-800ms |
| Mid GPU | medium | cuda | float16 | 200-400ms |
| Low GPU | base | cuda | int8 | 80-150ms |
| CPU only | tiny | cpu | int8 | 100-200ms |

### 6.4 Context Carryover Tuning (`streaming_engine.py:264-306`)

```python
# ContextCarryoverManager parameters
max_prefix_words: int = 5      # Words to carry between chunks
decay_factor: float = 0.8      # Reliability decay on low confidence
```

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| `max_prefix_words` | Less context, faster | More context, slower |
| `decay_factor` | Faster reset | Slower decay |

---

*Generated from codebase analysis. Last verified: 2026-03-04*
