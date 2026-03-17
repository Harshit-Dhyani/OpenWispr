---
title: Dictation Pipeline
description: Speech-to-Text pipeline flow and streaming transcription architecture
audience: developers
last_verified: 2026-03-15
source_of_truth:
  - app/stt/streaming_engine.py
  - app/stt/utterance_aggregator.py
  - app/stt/quality.py
  - app/api/routes/hotkey.py
---

# Dictation Pipeline

This document describes the Speech-to-Text (STT) pipeline flow, from audio capture to final transcript output.

## Overview

The dictation pipeline consists of three main components:

1. **StreamingEngine** (`app/stt/streaming_engine.py`) - Dual-mode transcription engine with adaptive performance
2. **UtteranceAggregator** (`app/stt/utterance_aggregator.py`) - Segment aggregation and text composition
3. **QualityAssessor** (`app/stt/quality.py`) - Segment quality validation and filtering

## Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Audio Capture  │────▶│ StreamingEngine  │────▶│  Transcription  │
│   (AudioChunk)  │     │  (Dual Mode)     │     │   (Segments)    │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                           ┌──────────────────────────────┼──────────┐
                           │                              │          │
                           ▼                              ▼          │
              ┌─────────────────────┐          ┌──────────────────┐  │
              │  Quality Assessment │          │ Utterance        │  │
              │  (assess_segment    │          │ Aggregation      │  │
              │   _quality)         │          │ (Utterance       │  │
              └──────────┬──────────┘          │  Aggregator)     │  │
                         │                     └────────┬─────────┘  │
                         │ rejected                    │            │
                         ▼                             ▼            │
                ┌─────────────────┐           ┌─────────────────┐   │
                │   Suppressed    │           │  Aggregated     │◄──┘
                │   (dropped)     │           │  Utterance      │
                └─────────────────┘           └────────┬────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │  Final Output   │
                                              │  (Dictation UI) │
                                              └─────────────────┘
```

## Streaming Engine

The `DualModeTranscriptionEngine` (`app/stt/streaming_engine.py:637`) supports two transcription modes optimized for different use cases:

### Transcription Modes

| Mode | Latency Target | Model | Use Case |
|------|---------------|-------|----------|
| **WISPR** | <200ms first-word | tiny (int8) | Hotkey dictation, real-time |
| **SYSTEM** | <1s first-word | medium (fp16/int8) | System audio, accuracy-focused |

### StreamingInferenceEngine

Core streaming transcription logic at `app/stt/streaming_engine.py:312`:

```python
class StreamingInferenceEngine:
    def push_audio(self, samples: np.ndarray, timestamp: float | None) -> None
    def process_stream(self, language: str | None, yield_partial: bool) -> Generator[PartialResult, None, None]
    def flush(self, language: str | None) -> PartialResult | None
```

### Window Processing

Audio is processed in overlapping windows (`app/stt/streaming_engine.py:368`):

```
Window Configuration:
├── window_ms: 400ms (WISPR) / 1000ms (SYSTEM)
├── overlap_ms: 80ms (WISPR) / 200ms (SYSTEM)
├── min_chunk_ms: 200ms
└── step_samples = window_samples - overlap_samples
```

### Adaptive Beam Control

The `AdaptiveBeamController` (`app/stt/streaming_engine.py:205`) dynamically adjusts beam size:

```python
# Latency targets
WISPR:  target_latency_ms = 200.0
SYSTEM: target_latency_ms = 1000.0

# Adaptation logic
if p95 > target * 1.2:
    reduce_beam_size()
elif avg < target * 0.6:
    increase_beam_size()
```

### Context Carryover

Prefix context from previous chunks improves continuity (`app/stt/streaming_engine.py:267`):

```python
class ContextCarryoverManager:
    max_prefix_words: int = 5
    decay_factor: float = 0.8
    reliability_threshold: float = 0.3
```

## Quality Assessment

The `assess_segment_quality` function (`app/stt/quality.py:52`) validates transcription segments:

### Quality Checks

| Check | Threshold | Failure Action |
|-------|-----------|----------------|
| Empty text | N/A | suppressed, reason="empty" |
| Punctuation ratio | >0.45 | reason="punctuation-heavy" |
| Repeated char run | >=12 chars | reason="repeated-character-run" |
| Low entropy | unique_ratio <0.12 | reason="low-entropy" |
| Filler words | confidence <0.72 | reason="low-value-filler" |
| Hallucination phrases | confidence <0.7 | reason="likely-hallucination" |
| No-speech probability | >0.6 + low conf | reason="likely-no-speech" |
| Script mismatch | mode-dependent | reason="script-mismatch" |

### Quality Labels

```python
QUALITY_LABEL_JUNK   = "junk"     # Confidence < 0.45 → suppressed
QUALITY_LABEL_WEAK   = "weak"     # Confidence < 0.65
QUALITY_LABEL_OK     = "ok"       # Passed all checks
```

### Confidence Calculation

Segment confidence is calculated from Whisper outputs (`app/stt/streaming_engine.py:508`):

```python
seg_confidence = max(0.0, min(0.99, 0.65 + (avg_logprob + 1.2) / 1.2 * 0.25))
seg_confidence -= no_speech_prob * 0.25
```

## Utterance Aggregation

The `UtteranceAggregator` (`app/stt/utterance_aggregator.py:65`) combines segments into complete utterances:

### Aggregation Flow

```python
def add_segment(
    segment_id: str,
    text: str,
    display_text: str,
    start: float,
    end: float,
    confidence: float,
    suppressed: bool = False,
    suppression_reasons: list[str] | None = None,
) -> None
```

### Deduplication Logic

1. **Suppressed segments** → dropped (counted in `dropped_segments_count`)
2. **Empty text** → dropped
3. **Duplicate text** (via `compose_transcript_text`) → dropped
4. **New content** → appended, `merged_segments_count` incremented

### Finalization

```python
def finalize(self) -> AggregatedUtterance:
    return AggregatedUtterance(
        aggregated_raw_text=" ".join(segments),
        aggregated_clean_text=clean_final_text(merged),
        accepted_segments_count=len(self._segments),
        dropped_segments_count=self.dropped_segments_count,
        merged_segments_count=self.merged_segments_count,
        warnings=list(self.warnings),
    )
```

## Configuration Options

### StreamingConfig (`app/stt/streaming_engine.py:122`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `window_ms` | 400 | Processing window size in milliseconds |
| `overlap_ms` | 80 | Overlap between consecutive windows |
| `min_chunk_ms` | 200 | Minimum audio chunk to process |
| `target_latency_ms` | 200.0 | Target latency in milliseconds |
| `min_beam_size` | 1 | Minimum beam search width |
| `max_beam_size` | 5 | Maximum beam search width |
| `latency_history_size` | 10 | Samples for beam adaptation |
| `prefix_context_enabled` | True | Enable context carryover |
| `max_prefix_words` | 5 | Words to carry from previous chunk |
| `context_decay_factor` | 0.8 | Context reliability decay |
| `partial_threshold_ms` | 150.0 | Threshold for partial results |
| `stabilization_window` | 3 | Windows to wait for stabilization |

### Mode-Specific Configurations

WISPR mode (`streaming_engine.py:762-768`):
```python
window_ms=400, overlap_ms=80, target_latency_ms=200.0,
min_beam_size=1, max_beam_size=3
```

SYSTEM mode (`streaming_engine.py:770-776`):
```python
window_ms=1000, overlap_ms=200, target_latency_ms=1000.0,
min_beam_size=1, max_beam_size=5
```

### VAD Parameters (`app/stt/streaming_engine.py:474`)

```python
vad_parameters = {
    "threshold": 0.35 if WISPR else 0.4,
    "min_silence_duration_ms": 200,
    "speech_pad_ms": 200,
}
```

## Latency Targets

### First-Word Latency

| Mode | Target | Achieved | Notes |
|------|--------|----------|-------|
| WISPR | <200ms | ~150-200ms | Tiny model, int8 quantization |
| SYSTEM | <1000ms | ~500-800ms | Medium model, accuracy-focused |

### Processing Latency

```python
# Inference timing
inference_start = time.perf_counter()
segments, info = model.transcribe(audio, **kwargs)
inference_time_ms = (time.perf_counter() - inference_start) * 1000
```

### Metrics Collection

The engine collects detailed metrics (`app/stt/streaming_engine.py:53`):

```python
class PerformanceMetrics:
    first_word_latency_ms: float
    avg_chunk_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    chunks_processed: int
    words_per_second: float
    real_time_factor: float
    avg_confidence: float
    segments_produced: int
    segments_suppressed: int
```

## Segment to Transcript Flow

```
PartialResult (StreamingInferenceEngine)
    ↓
TranscriptSegment (DualModeTranscriptionEngine._create_segment)
    ↓
SegmentQuality (quality.assess_segment_quality)
    ↓
AcceptedSegment (UtteranceAggregator.add_segment)
    ↓
AggregatedUtterance (UtteranceAggregator.finalize)
    ↓
Dictation UI / Hotkey Output
```

## Error Handling

### Engine States (`app/stt/streaming_engine.py:40`)

```python
class EngineState(Enum):
    INITIALIZING
    WARMING        # Model warmup in progress
    READY          # Ready for transcription
    PROCESSING     # Active transcription
    PAUSED
    ERROR
    SHUTDOWN
```

### Backpressure

The async queue has maxsize=64 (`app/stt/streaming_engine.py:686`):

```python
async def submit(self, chunk: AudioChunk) -> bool:
    try:
        self._queue.put_nowait(chunk)
        return True
    except asyncio.QueueFull:
        logger.warning("Queue full, chunk dropped")
        return False
```

## Key Code Paths

| Function | File | Line | Purpose |
|----------|------|------|---------|
| `DualModeTranscriptionEngine.__init__` | streaming_engine.py | 640 | Initialize dual-mode engine |
| `StreamingInferenceEngine.process_stream` | streaming_engine.py | 368 | Main processing loop |
| `_transcribe_window` | streaming_engine.py | 454 | Single window transcription |
| `assess_segment_quality` | quality.py | 52 | Quality validation |
| `UtteranceAggregator.add_segment` | utterance_aggregator.py | 103 | Segment aggregation |
| `UtteranceAggregator.finalize` | utterance_aggregator.py | 196 | Final utterance build |

## Related Documentation

- [Model Runtime](./model-runtime.md) - Model loading and inference
- [Architecture Overview](./architecture-overview.md) - System architecture
- [Latency Playbook](./latency-playbook.md) - Performance optimization
