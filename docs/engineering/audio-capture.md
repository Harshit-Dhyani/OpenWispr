---
title: Audio Capture System
audience: developers
last_verified: 2026-03-08
source_of_truth:
  - app/audio/capture.py
  - app/audio/backends/
  - app/audio/devices.py
---

# Audio Capture System

The audio capture system provides a unified interface for recording audio from both microphone and system audio sources. It supports multiple backend implementations with automatic fallback and device probing capabilities.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LoopbackAudioSource                           │
│              (app/audio/capture.py:20)                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Threading: Daemon thread runs _run() loop               │  │
│  │  Queue: thread-safe audio buffer (max_queue_items)       │  │
│  │  Metrics: level_rms, dropped_frames tracking             │  │
│  └───────────────────────┬──────────────────────────────────┘  │
└──────────────────────────┼─────────────────────────────────────┘
                           │ open_audio_backend()
┌──────────────────────────┼─────────────────────────────────────┐
│              Backend Factory (app/audio/backends/factory.py)    │
│  ┌───────────────────────┴──────────────────────────────────┐  │
│  │  Preference: "auto" → pyaudio → soundcard (optional)      │  │
│  │  Fallback: Tracks failed backends with detailed errors    │  │
│  └───────────────────────┬──────────────────────────────────┘  │
└──────────────────────────┼─────────────────────────────────────┘
           ┌───────────────┴───────────────┐
           ▼                               ▼
┌──────────────────────┐      ┌──────────────────────┐
│ PyAudioWasapiBackend │      │  SoundcardBackend    │
│ (pyaudio_wasapi.py)  │      │ (soundcard_backend.py)│
│ - WASAPI loopback    │      │ - Direct WASAPI      │
│ - Format negotiation │      │ - Format negotiation │
│ - Device ranking     │      │ - Context manager    │
└──────────────────────┘      └──────────────────────┘
```

## LoopbackAudioSource

The main capture class at `app/audio/capture.py:20` that manages audio capture in a background thread.

### Initialization

```python
source = LoopbackAudioSource(
    device_id="CABLE Output (VB-Audio Virtual Cable)",
    sample_rate=16000,
    channels=1,
    block_size=1024,
    max_queue_items=10,
    audio_backend="auto"  # "auto", "pyaudio", "soundcard"
)
```

### Threading Model

- **Thread**: Daemon thread spawned on `start()` (line 62)
- **Queue**: `queue.Queue` with `maxsize=max_queue_items` (line 38)
- **Stop Event**: `threading.Event` for graceful shutdown (line 42)
- **Timeout**: 3-second join timeout on stop (line 79)

### Error Handling

The capture loop implements consecutive error tracking (lines 127-142):
- `max_consecutive_errors = 5`: Threshold before giving up
- Calls `on_error` callback when threshold exceeded
- Graceful degradation with fallback device suggestions

### Device Probing

Static method for testing devices before capture (lines 239-291):

```python
result = LoopbackAudioSource.probe_device(
    device_id="device_name",
    sample_rate=16000,
    channels=1,
    duration=3.0,
    output_dir=Path("./probes"),
    audio_backend="auto"
)
# Returns: DeviceProbeResult with rms_mean, rms_peak, has_signal, wav_path
```

## Backend Architecture

### Base Backend (app/audio/backends/base.py)

Abstract base class defining the backend interface:

```python
class AudioBackend(ABC):
    backend_name: str
    resolved_name: str | None
    runtime_sample_rate: int  # May differ from requested
    runtime_channels: int     # May differ from requested

    @abstractmethod
    def start(self) -> None: ...
    
    @abstractmethod
    def stop(self) -> None: ...
    
    @abstractmethod
    def read(self, timeout: float = 0.25) -> np.ndarray | None: ...
    
    @abstractmethod
    def probe(self, *, duration: float, output_dir: Path) -> DeviceProbeResult: ...
```

### Audio Processing Utilities

- `sanitize_audio()`: Clips to [-1.0, 1.0], removes NaN/Inf (line 39-45)
- `to_mono()`: Intelligent channel mixing with energy-based selection (line 48-72)
- `resample_audio()`: Linear interpolation resampling (line 75-90)

### Backend Factory (app/audio/backends/factory.py)

Entry point for backend selection (line 34-83):

```python
selection = open_audio_backend(
    device_id="device",
    sample_rate=16000,
    channels=1,
    block_size=1024,
    preferred_backend="auto"  # or "pyaudio", "soundcard"
)
# Returns: AudioBackendSelection(backend, failed_backends, failed_details)
```

**Backend Priority**:
1. If `preferred_backend="pyaudio"`: PyAudio only
2. If `preferred_backend="soundcard"`: Soundcard only (if available)
3. If `preferred_backend="auto"`: PyAudio first, then Soundcard

## Available Backends

### PyAudioWasapiBackend (app/audio/backends/pyaudio_wasapi.py)

Uses `pyaudiowpatch` for WASAPI loopback capture on Windows.

**Features**:
- Device enumeration with ranking by name hints (lines 54-88)
- Format negotiation: `paFloat32` preferred, `paInt16` fallback (lines 100-103)
- Sample rate fallback: requested → device default → 48000 → 44100 → 16000
- Channel fallback: requested → 2 → 1 → max available
- Buffer overflow detection and logging (lines 194-199)

**Device Ranking** (lines 63-88):
```python
priority = (
    0 if exact_hint else 1,      # Exact name match
    0 if partial_hint else 1,    # Partial name match
    0 if virtual_cable else 1,   # VB-Cable preferred
    0 if loopback else 1,        # Loopback preferred
    normalized_name              # Alphabetical
)
```

### SoundcardBackend (app/audio/backends/soundcard_backend.py)

Uses the `soundcard` library for direct WASAPI capture.

**Features**:
- Context manager-based recorder lifecycle (lines 44-101)
- Sample rate fallback chain (lines 45-48)
- Channel count negotiation via `candidate_channel_counts()` (lines 52-53)
- Resampling if runtime rate differs from target (lines 112-117)

**Optional Dependency**: Not all environments have `soundcard` installed. The factory gracefully handles this.

## Device Enumeration (app/audio/devices.py)

### Device Listing

```python
devices = list_audio_devices()  # Returns list[AudioDeviceInfo]
```

**Device Types**:
- **Speakers**: Exposed as WASAPI loopback devices (lines 82-93)
- **Microphones**: Including loopback microphones (lines 96-107)

**Deduplication** (lines 114-129):
- Normalizes names (removes "(WASAPI loopback)", "[REC]" markers)
- Prefers loopback over non-loopback
- Prefers VB-Cable/virtual devices
- Prefers microphones over speakers for same physical device

### Device Resolution

```python
device, name = resolve_capture_device("device_id")
# Returns: (soundcard device object, resolved name)
```

**Resolution Logic** (lines 252-256):
1. Exact match by ID
2. Speaker selection → find matching loopback microphone
3. Fallback to any available loopback microphone
4. Final fallback to default microphone

**Name Hints** (lines 156-194):
```python
hints = resolve_capture_name_hints("device_id")
# Returns: List of candidate device names for backend matching
```

## Configuration

### Backend Selection

Set in settings or per-source initialization:

```python
# Global default
settings.audio_backend = "auto"  # "auto", "pyaudio", "soundcard"

# Per-source override
source = LoopbackAudioSource(
    device_id="device",
    audio_backend="soundcard"  # Force specific backend
)
```

### Capture Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `sample_rate` | 16000 | Target sample rate (Hz) |
| `channels` | 1 | Target channels (1=mono, 2=stereo) |
| `block_size` | 1024 | Samples per read operation |
| `max_queue_items` | 10 | Maximum queued audio buffers |

### Runtime Properties

After `start()`, these reflect actual negotiated values:

```python
source.backend_name          # "pyaudio" or "soundcard"
source.backend_fallbacks     # List of backends that failed
backend.runtime_sample_rate  # Actual sample rate
backend.runtime_channels     # Actual channel count
```

## Error Handling

### AudioBackendError (app/audio/backends/base.py:22-36)

Detailed error information when backends fail:

```python
except AudioBackendError as e:
    print(e.backend)          # "pyaudio"
    print(e.attempts)         # List[BackendAttempt] with per-attempt details
    print(e.describe_attempts())  # Formatted error report
```

### Recovery Strategies

1. **Backend Fallback**: Automatic try-next-backend on failure
2. **Device Fallback**: Suggests alternate devices based on naming
3. **Format Fallback**: Automatic sample rate/channel negotiation
4. **Runtime Errors**: Consecutive error tracking with callback notification

## Integration with Transcription

The capture system feeds audio to `FastTranscriber` via:

```python
# Audio flow in hotkey service (app/api/server.py:1184-1277)
chunk = await asyncio.wait_for(
    asyncio.get_event_loop().run_in_executor(None, audio_source.read),
    timeout=0.1
)
if chunk is not None:
    session.transcriber.submit(AudioChunk(...))
```

The audio source runs in a separate thread, decoupling capture from processing to prevent dropouts.
