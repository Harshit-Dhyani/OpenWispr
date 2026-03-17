---
title: Audio Capture System
audience: developers
last_verified: 2026-03-15
source_of_truth:
  - app/audio/capture/capture.py
  - app/audio/backends/
  - app/audio/devices/devices.py
---

# Audio Capture System

The audio capture system provides a unified interface for recording audio from both microphone and system audio sources. It supports multiple backend implementations with automatic fallback and device probing capabilities.

## Architecture

```
LoopbackAudioSource (app/audio/capture/capture.py:30)
- Threading: Daemon thread runs _run() loop
- Queue: thread-safe audio buffer (max_queue_items)
- Metrics: level_rms, dropped_frames tracking

Backend Factory (app/audio/backends/factory.py)
- Preference: "auto" -> pyaudio -> soundcard
- Fallback: Tracks failed backends with detailed errors

PyAudioWasapiBackend (pyaudio_wasapi.py)
- WASAPI loopback, Format negotiation, Device ranking

SoundcardBackend (soundcard_backend.py)
- Direct WASAPI, Format negotiation, Context manager
```

## Transitional Structure Note

The audio module has undergone structural reorganization. Legacy shims exist at the root level but are deprecated:

- `app/audio/capture.py` -> Use `app/audio/capture/capture.py` (canonical)
- `app/audio/devices.py` -> Use `app/audio/devices/devices.py` (canonical)
- `app/audio/vad_optimized.py` -> Use `app/audio/vad/vad_optimized.py` (canonical)

All new code should import from the canonical paths. The shims exist only for backward compatibility.

## LoopbackAudioSource

The main capture class at `app/audio/capture/capture.py:30` that manages audio capture in a background thread.

### Threading Model

- **Thread**: Daemon thread spawned on `start()` (line 89)
- **Queue**: `queue.Queue` with `maxsize=max_queue_items` (line 70)
- **Stop Event**: `threading.Event` for graceful shutdown (line 74)
- **Timeout**: 3-second join timeout on stop (line 111)

### Error Handling

The capture loop implements consecutive error tracking (lines 159-222):
- `max_consecutive_errors = 5`: Threshold before giving up
- Calls `on_error` callback when threshold exceeded
- Graceful degradation with fallback device suggestions

### Device Probing

Static method for testing devices before capture (lines 280-341).

## Backend Architecture

### Base Backend (app/audio/backends/base.py)

Abstract base class: `start()`, `stop()`, `read()`, `probe()`

### Audio Processing Utilities

- `sanitize_audio()`: Clips to [-1.0, 1.0], removes NaN/Inf (base.py:62)
- `to_mono()`: Intelligent channel mixing (base.py:71)
- `resample_audio()`: Linear interpolation resampling (base.py:98)

### Backend Factory (app/audio/backends/factory.py)

Entry point: `open_audio_backend()` (lines 43-92)
Backend Priority: auto -> pyaudio -> soundcard

## Available Backends

### PyAudioWasapiBackend (app/audio/backends/pyaudio_wasapi.py)

Uses pyaudiowpatch for WASAPI loopback capture on Windows.
Features: Device ranking (lines 83-109), format negotiation (lines 132-160), buffer overflow detection (lines 246-250)

### SoundcardBackend (app/audio/backends/soundcard_backend.py)

Uses soundcard library. Features: Context manager lifecycle (lines 66-122), sample rate fallback (lines 73-79), resampling (lines 134)

## Device Enumeration (app/audio/devices/devices.py)

### Device Listing

`list_audio_devices()` returns list[AudioDeviceInfo]

### Device Resolution

`resolve_capture_device(device_id)` returns (soundcard device, resolved name)
Resolution Logic (lines 264-268): exact match -> speaker loopback -> any loopback -> default mic

### Name Hints

`resolve_capture_name_hints(device_id)` returns candidate device names (lines 168-206)

## Configuration

### Backend Selection

`settings.audio_backend` or per-source: `audio_backend="soundcard"`

### Capture Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| sample_rate | 16000 | Target sample rate (Hz) |
| channels | 1 | Target channels (1=mono, 2=stereo) |
| block_size | 1024 | Samples per read |
| max_queue_items | 16 | Max queued buffers |

### Runtime Properties

source.backend_name, source.backend_fallbacks, backend.runtime_sample_rate, backend.runtime_channels

## Error Handling

### AudioBackendError (app/audio/backends/base.py:39-59)

Exception with .backend, .attempts, .describe_attempts()

### Recovery Strategies

1. Backend Fallback: try-next-backend
2. Device Fallback: suggest alternate devices
3. Format Fallback: sample rate/channel negotiation
4. Runtime Errors: consecutive error tracking with callback

## Integration with Transcription

The capture system feeds audio to FastTranscriber via executor-based read in the hotkey service.

## Voice Activity Detection (VAD)

The VAD implementation is at `app/audio/vad/vad_optimized.py` (canonical).

The root-level `app/audio/vad_optimized.py` is a backward-compatibility shim re-exporting from canonical path. All new code should import from `app.audio.vad`:

```python
from app.audio.vad import (
    OptimizedVAD,
    VADConfig,
    VADMode,
    VADState,
    create_vad,
)
```

VAD Features:
- Mode-specific configurations (HOTKEY vs SYSTEM)
- Adaptive thresholding based on ambient noise
- Hysteresis to prevent rapid switching
- Pre/post speech padding
- Numba-optimized processing
- Comprehensive metrics and profiling
