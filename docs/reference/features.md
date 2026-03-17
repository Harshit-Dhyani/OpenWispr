---
title: Features Documentation
audience: all
last_verified: 2026-03-15
source_of_truth:
  - app/audio/capture/capture.py
  - app/api/services/backend_service.py
  - app/core/mode_manager.py
  - app/core/modes.py
  - app/stt/fast_engine.py
---

# OpenWispr Features Documentation

Comprehensive documentation of OpenWispr's features, capabilities, and implementation details.

---

## Table of Contents

1. [Transcription Modes](#transcription-modes)
   - [Hotkey Mode (Wispr)](#1-hotkey-mode-wispr)
   - [System Mode](#2-system-mode)
   - [Transcription Output Modes](#transcription-output-modes)
2. [Audio Pipeline](#audio-pipeline)
3. [STT Engine](#stt-engine)
4. [Models](#models)
5. [Refiner](#refiner)
6. [Settings](#settings)
7. [Session Management](#session-management)
8. [Feature Comparison](#feature-comparison)
9. [Use Case Recommendations](#use-case-recommendations)
10. [Source Code References](#source-code-references)

---

## Transcription Modes

OpenWispr provides two distinct transcription modes optimized for different use cases.

### 1. Hotkey Mode (Wispr)

Hotkey Mode is designed for quick dictation and voice input tasks with minimal latency.

**Key Features:**

| Feature | Description |
|---------|-------------|
| **Global Hotkey** | Ctrl+Shift+T triggers transcription from anywhere |
| **Low Latency** | Optimized for sub-300ms end-to-end latency |
| **Auto-Paste** | Automatically inserts transcription at cursor position |
| **Floating Window** | Visual feedback with real-time audio visualization |
| **Partial Stabilization** | Shows draft text while speaking for immediate feedback |
| **Microphone Input** | Captures from default or selected microphone device |
| **Transient Sessions** | No disk persistence; purely in-memory operation |

**Technical Specifications:**

- **Default Model**: `tiny` (39M parameters)
- **Chunk Duration**: 0.5 seconds
- **Beam Size**: 1 (fastest decoding)
- **Compute Type**: `int8` (CPU-optimized)
- **VAD Threshold**: -40 dB
- **Sample Rate**: 16 kHz
- **Overlap Ratio**: 0.1 (10%)

**Configuration Class:** `WisprModeDefaults` (app/core/modes.py:199-249)

**Usage Flow:**
1. Press Ctrl+Shift+T to activate
2. Speak naturally
3. See real-time transcription in floating window
4. Release hotkey to finalize
5. Text is automatically pasted at cursor (or copied to clipboard)

---

### 2. System Mode

System Mode captures full system audio for transcribing videos, meetings, podcasts, and any PC audio output.

**Key Features:**

| Feature | Description |
|---------|-------------|
| **Loopback Capture** | Records any playback device without external cables |
| **Multi-Hour Sessions** | Optimized for long-form content (up to 8 hours) |
| **Audio Recording** | Saves original audio to WAV files with rotation |
| **Chapter Detection** | Auto-detects chapters based on silence (>2 seconds) |
| **Export Formats** | TXT, JSON, SRT, Markdown |
| **Session Notes** | Attach contextual notes with timestamps |
| **Formula Extraction** | STEM processing for mathematical expressions |
| **Document Context** | Attach PDFs for enhanced transcription context |
| **Auto-Save** | Persistent JSONL storage with recovery capability |

**Technical Specifications:**

- **Default Model**: `medium` (769M parameters)
- **Chunk Duration**: 2.0 seconds
- **Beam Size**: 5 (balanced accuracy/speed)
- **Compute Type**: `float16` (GPU-optimized)
- **VAD Threshold**: -35 dB
- **Sample Rate**: 16 kHz
- **Overlap Ratio**: 0.2 (20%)
- **Audio Rotation**: 100 MB per file

**Configuration Class:** `SystemModeDefaults` (app/core/modes.py:252-302)

**Session Components:**
- `AudioRecordingManager` - Continuous audio capture with rotation
- `ChapterDetector` - Silence-based chapter boundaries
- `ExportManager` - Background export tasks
- `SessionWriter` - JSONL persistence

---

### Transcription Output Modes

The API supports three transcription output modes that control how the final transcript is formatted. These are specified via the `transcription_mode` parameter in API requests.

| Mode | Description | Use Case |
|------|-------------|----------|
| **dictation** | Standard dictation output with punctuation | General voice input, emails, messages |
| **literal** | Word-for-word output with minimal processing | Technical content, verbatim transcripts |
| **session_paragraph** | Paragraph-structured output | Meeting notes, documentation |

**Default**: `dictation`

---

## Audio Pipeline

The audio pipeline handles capture, processing, and delivery to the STT engine.

### Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Audio Source   │───▶│  VAD Processing  │───▶│  Chunk Builder  │
│  (Device/API)   │    │  (Voice Detect)  │    │  (Overlap/Merge)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
┌─────────────────┐    ┌──────────────────┐            ▼
│  Visualizer     │◀───│  Level Meter     │    ┌─────────────────┐
│  (36 freq bars) │    │  (RMS/Peak)      │◀───│  STT Engine     │
└─────────────────┘    └──────────────────┘    │  (Whisper)      │
                                               └─────────────────┘
```

### Key Components

#### LoopbackAudioSource (app/audio/capture.py:20-291)

Primary audio capture interface supporting multiple backends:

| Property | Description |
|----------|-------------|
| **Device Selection** | Automatic or manual device ID |
| **Sample Rate** | 16 kHz (Whisper-optimized) |
| **Channels** | Mono (1) or Stereo (2) |
| **Block Size** | Configurable (default: 256-1024 samples) |
| **Queue Buffer** | Thread-safe bounded queue |
| **Error Handling** | Automatic fallback and recovery |

#### Backends

1. **SoundCard Backend** (app/audio/backends/soundcard_backend.py)
   - Cross-platform support
   - WASAPI on Windows
   - CoreAudio on macOS
   - ALSA/Pulse on Linux

2. **PyAudio WASAPI** (app/audio/backends/pyaudio_wasapi.py)
   - Windows-specific loopback
   - Low-latency capture
   - PyAudioWPatch for exclusive mode

#### Voice Activity Detection (app/audio/vad_optimized.py)

- **Algorithm**: Energy-based with adaptive threshold
- **Threshold Range**: -60 dB to -20 dB
- **Min Silence**: 200-500 ms (configurable)
- **Speech Padding**: 100-200 ms (configurable)
- **Optimization**: Prevents unnecessary transcription of silence

#### Real-Time Visualization

- **Frequency Bars**: 36 bars representing frequency distribution
- **Update Rate**: 50ms for smooth animation
- **Metrics**: RMS level, peak detection, frequency response
- **Implementation**: FFT-based spectrum analysis

---

## STT Engine

Speech-to-Text processing using optimized Whisper inference.

### faster-whisper Backend

OpenWispr uses `faster-whisper` (CTranslate2) for efficient inference.

**Key Features:**

| Feature | Description |
|---------|-------------|
| **Model Pool** | GPU memory management with model caching |
| **Adaptive Chunking** | Dynamic chunk sizing based on content |
| **Streaming Windows** | Configurable overlap for continuity |
| **Language Detection** | Auto-detection with caching |
| **Quality Filtering** | Filler word and hallucination removal |
| **Partial Stabilization** | Draft text with commit/revision semantics |
| **GPU Fallback** | Automatic CPU fallback on GPU errors |

### FastTranscriber (app/stt/fast_engine.py)

Primary transcription engine with the following capabilities:

**Performance Targets:**
- End-to-end latency: <300ms
- Throughput: Real-time factor >1.0x
- Memory: Efficient model pooling

**Configuration Options:**

```python
{
    "model_name": "tiny|base|small|medium|large-v3|turbo",
    "device": "auto|cuda|cpu",
    "compute_type": "float16|int8|int8_float16",
    "beam_size": 1-20,
    "best_of": 1-20,
    "temperature": 0.0-1.0,
    "vad_filter": true|false,
    "streaming_window_ms": 400-2000,
    "streaming_overlap_ms": 80-500
}
```

### Language Optimizer

Per-language tuning for Hindi and English:

| Language | Beam Size | Temperature | VAD Threshold |
|----------|-----------|-------------|---------------|
| Hindi (hi) | 3 | 0.3 | 0.35 |
| English (en) | 1 | 0.0 | 0.38 |
| Auto | 2 | 0.15 | 0.36 |

**Caching**: Language detection results cached by audio fingerprint (500 entry LRU).

### Quality Filtering (app/stt/quality.py)

Automatic quality assessment and filtering:

- **Filler Words**: "um", "uh", "er" removal
- **Hallucination Detection**: Repetitive or nonsensical content
- **Confidence Scoring**: Based on logprob, no_speech_prob, compression ratio
- **Suppression**: Low-quality segments marked for review

---

## Models

OpenWispr supports 6 Whisper model sizes with automatic optimization.

### Model Catalog (app/core/model_catalog.py)

| Model | Size | VRAM | Speed Tier | Best For |
|-------|------|------|------------|----------|
| **tiny** | 39 MB | 0 GB | Fast | Hotkey mode, CPU-only systems |
| **base** | 74 MB | 1 GB | Fast | Low-latency dictation |
| **small** | 244 MB | 2 GB | Fast | Balanced local dictation |
| **medium** | 769 MB | 5 GB | Balanced | Default for most systems |
| **large-v3** | 1.55 GB | 10 GB | Quality | Maximum accuracy |
| **turbo** | ~1.6 GB | 6 GB | Fast | Large-model quality, faster inference |

### Compute Types

| Type | Precision | Use Case |
|------|-----------|----------|
| **float16** | FP16 | GPU inference (2x faster) |
| **int8** | INT8 | CPU inference (4x smaller) |
| **int8_float16** | Mixed | Balanced GPU/CPU |

### Auto-Optimization

The system automatically selects optimal settings based on hardware:

```python
# GPU detected → float16, larger models
# CPU only → int8, smaller models
# Low VRAM → Model pooling, chunking
```

**Implementation**: `AutoOptimizer` (app/core/auto_optimizer.py)

---

## Refiner

Optional LLM-based post-processing for transcript cleanup.

### Architecture (app/api/refiner_service.py)

```
Raw Transcript ──▶ Refiner Service ──▶ LLM (llama.cpp) ──▶ Polished Text
                        │
                        ▼
               Quality Check (token preservation)
```

### Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **off** | No refinement | Fastest, raw output |
| **strict** | Punctuation/capitalization only | Technical content |
| **polished** | Readability improvements | General dictation |

### Supported Models

| Model | Size | VRAM | Speed Tier |
|-------|------|------|------------|
| **Phi-3 Mini 4K** | 2.4 GB | 4 GB | Fast |
| **Qwen2.5 3B** | 1.93 GB | 4 GB | Fast |
| **Qwen2.5 7B** | 4.7 GB | 8 GB | Balanced |
| **Mistral 7B** | 4.4 GB | 8 GB | Quality |

### Safety Features

- **Token Protection**: Preserves technical tokens (numbers, formulas, identifiers)
- **Delta Check**: Rejects changes >35% word delta
- **Fallback**: Returns original text if refinement fails

---

## Settings

Comprehensive configuration management with mode-specific defaults.

### Settings Architecture (app/core/settings_manager.py)

```
┌─────────────────────────────────────────────────────────────┐
│                    SettingsManager                          │
├─────────────────────────────────────────────────────────────┤
│  General Settings    │  Transcription Settings              │
│  - Theme             │  - Model selection                   │
│  - Language          │  - VAD parameters                    │
│  - Notifications     │  - Quality filters                   │
├─────────────────────────────────────────────────────────────┤
│  Audio Settings      │  Hotkey Settings                     │
│  - Capture source    │  - Key combination                   │
│  - Backend           │  - Auto-paste                        │
│  - Device ID         │  - Floating window                   │
├─────────────────────────────────────────────────────────────┤
│  Mode-Specific Settings                                     │
│  ┌───────────────┐    ┌───────────────┐                    │
│  │  Wispr Mode   │    │  System Mode  │                    │
│  │  - tiny model │    │  - medium     │                    │
│  │  - int8       │    │  - float16    │                    │
│  └───────────────┘    └───────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

### Key Features

| Feature | Implementation |
|---------|---------------|
| **Bidirectional Sync** | WebSocket-based real-time synchronization |
| **Validation** | Pydantic models with field validators |
| **Migrations** | Automatic upgrade from legacy settings formats |
| **Per-Mode Defaults** | Separate configurations for Hotkey/System |
| **Thread-Safe** | RLock protection for concurrent access |

### Settings Categories

1. **GeneralSettings** - UI, theme, notifications
2. **TranscriptionSettings** - Model, VAD, quality filters
3. **AudioSettings** - Capture source, backend, device
4. **HotkeySettings** - Key combo, auto-paste, floating window
5. **RefinerSettings** - LLM model, mode, runtime enable
6. **AdvancedSettings** - Debug mode, logging, metrics

---

## Session Management

Persistent storage and recovery for System Mode sessions.

### Storage Format (app/storage/session_store.py)

**JSONL Structure:**
```
session/
├── session.json          # Metadata
├── transcript.jsonl      # Append-only segments
├── transcript.txt        # Human-readable
├── notes.md              # Session notes
├── formulas.json         # Extracted formulas
├── highlights.txt        # Important segments
├── audio/                # Recorded audio (optional)
│   ├── audio_0001.wav
│   └── audio_0002.wav
└── logs/                 # Session logs
    └── session.log
```

### SessionWriter Features

| Feature | Description |
|---------|-------------|
| **Atomic Writes** | Temp file + rename for safety |
| **Append-Only** | Efficient segment logging |
| **Thread-Safe** | Lock-protected writes |
| **Auto-Recovery** | Resume interrupted sessions |
| **Export Formats** | TXT, JSON, SRT, Markdown |

### Export Formats

1. **TXT** - Plain text transcript
2. **JSON** - Structured data with metadata
3. **SRT** - Subtitle format with timestamps
4. **Markdown** - Rich document with chapters and notes

---

## Feature Comparison

| Feature | Hotkey Mode | System Mode |
|---------|-------------|-------------|
| **Trigger** | Global hotkey | Manual start/stop |
| **Input Source** | Microphone | System audio/loopback |
| **Default Model** | tiny | medium |
| **Latency** | <300ms | ~2s chunks |
| **Session Duration** | Seconds-minutes | Hours |
| **Persistence** | In-memory only | Full disk storage |
| **Auto-Paste** | Yes | No |
| **Floating Window** | Yes | No |
| **Audio Recording** | No | Yes |
| **Export Formats** | Clipboard only | TXT, JSON, SRT, MD |
| **Chapter Detection** | No | Yes |
| **Formula Extraction** | No | Yes |
| **Session Notes** | No | Yes |
| **Document Context** | No | Yes |
| **Best For** | Quick dictation | Meetings, videos, podcasts |

---

## Use Case Recommendations

### When to Use Hotkey Mode

1. **Quick Email Replies** - Dictate short responses
2. **Code Comments** - Voice-to-code documentation
3. **Chat Messages** - Fast messaging without typing
4. **Search Queries** - Voice-activated web search
5. **Form Filling** - Hands-free data entry

**Recommended Settings:**
- Model: `tiny` or `base`
- Compute: `int8` (CPU-friendly)
- VAD: Enabled
- Refiner: `off` or `strict`

### When to Use System Mode

1. **Video Transcription** - YouTube, lectures, tutorials
2. **Meeting Records** - Zoom, Teams, Meet sessions
3. **Podcast Archiving** - Long-form audio content
4. **Interview Documentation** - Record and transcribe
5. **Research Notes** - STEM content with formulas

**Recommended Settings:**
- Model: `medium` or `large-v3`
- Compute: `float16` (GPU recommended)
- VAD: Enabled
- Audio Recording: Enabled
- Refiner: `polished`

---

## Source Code References

### Core Modules

| Module | Path | Description |
|--------|------|-------------|
| **Modes** | `app/core/modes.py` | Mode definitions and defaults |
| **System Session** | `app/core/system_session.py` | Full session management |
| **Settings Manager** | `app/core/settings_manager.py` | Configuration persistence |
| **Model Catalog** | `app/core/model_catalog.py` | Available models metadata |
| **Hotkey Session** | `app/core/hotkey_session.py` | Hotkey-specific handling |

### Audio Pipeline

| Module | Path | Description |
|--------|------|-------------|
| **Capture** | `app/audio/capture.py` | Loopback audio source |
| **VAD** | `app/audio/vad_optimized.py` | Voice activity detection |
| **Backends** | `app/audio/backends/` | Platform-specific backends |
| **Devices** | `app/audio/devices.py` | Device enumeration |
| **Pipelines** | `app/audio/*_pipeline.py` | Mode-specific pipelines |

### STT Engine

| Module | Path | Description |
|--------|------|-------------|
| **Fast Engine** | `app/stt/fast_engine.py` | Main transcription engine |
| **Fast Whisper** | `app/stt/fast_whisper_backend.py` | faster-whisper wrapper |
| **Model Pool** | `app/stt/model_pool.py` | GPU memory management |
| **Quality** | `app/stt/quality.py` | Segment quality assessment |
| **Stability** | `app/stt/stability.py` | Partial text stabilization |
| **Chunker** | `app/stt/fast_chunker.py` | Audio chunking logic |

### API & Services

| Module | Path | Description |
|--------|------|-------------|
| **Server** | `app/api/server.py` | FastAPI endpoints |
| **Refiner** | `app/api/refiner_service.py` | LLM refinement service |
| **Settings Sync** | `app/api/settings_sync.py` | WebSocket sync |
| **WebSocket** | `app/api/websocket_server.py` | Real-time communication |

### Storage

| Module | Path | Description |
|--------|------|-------------|
| **Session Store** | `app/storage/session_store.py` | JSONL persistence |
| **Document Store** | `app/storage/document_store.py` | PDF context |
| **Session Writer** | `app/storage/session_writer.py` | Write operations |

---

## API Endpoints

### Hotkey Mode Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/transcription/hotkey/start` | POST | Begin hotkey session |
| `/api/transcription/hotkey/stop` | POST | End session and return text |
| `/api/transcription/hotkey/status` | GET | Current session status |
| `/api/transcription/hotkey/inject` | POST | Manually inject text |
| `/api/hotkey/config` | GET/POST | Get/update configuration |
| `/api/transcription/hotkey/ws` | WebSocket | Real-time transcription stream |

### System Mode Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/session/start` | POST | Begin system session |
| `/api/session/stop` | POST | End session |
| `/api/session` | GET | Get session info |
| `/api/session/attach-pdf` | POST | Attach PDF document for context |

### Settings Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/settings` | GET/POST | Get/update all settings |
| `/api/settings/reset` | POST | Reset settings to defaults |
| `/api/ws/settings` | WebSocket | Real-time bidirectional sync channel |

### Refiner Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/refiner/status` | GET | Get refiner runtime status |

### Coach Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/coach/prompt-preview` | POST | Preview coach prompt output |

---

*Documentation generated from OpenWispr source code. Last updated: March 2026.*
