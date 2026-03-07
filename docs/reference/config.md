---
title: Configuration Reference
audience: developers
last_verified: 2026-03-04
source_of_truth:
  - app/core/settings_manager.py
  - app/config/settings.py
  - app/config/constants.py
  - app/core/modes.py
---

# OpenWispr Configuration Reference

Complete reference for all OpenWispr configuration options, including environment variables, settings file structure, mode-specific defaults, and validation bounds.

## Table of Contents

1. [Settings Schema](#settings-schema)
2. [Environment Variables](#environment-variables)
3. [Settings File Structure](#settings-file-structure)
4. [Mode-Specific Defaults](#mode-specific-defaults)
5. [Validation Bounds](#validation-bounds)
6. [Live Mode Profiles](#live-mode-profiles)
7. [Example Configurations](#example-configurations)
8. [Migration History](#migration-history)

---

## Settings Schema

<!-- GENERATED: settings-schema -->
## General Settings

General application settings.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `defaultSessionTitle` | string | 'New Session' | |
| `defaultLanguage` | string | 'auto' | |
| `exportDirectory` | string | '' | |
| `autoSaveInterval` | integer | 30 | |
| `showNotifications` | boolean | True | |
| `minimizeToTray` | boolean | True | |
| `startupWithSystem` | boolean | False | |
| `theme` | string | 'light' | |

## Transcription Settings

Transcription-related settings.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model_name` | string | 'medium' | |
| `default_asr_model_id` | string | 'whisper-medium' | |
| `microphone_asr_model_id` | string | 'whisper-medium' | |
| `system_asr_model_id` | string | 'whisper-medium' | |
| `refinement_mode` | string | 'off' | |
| `refinement_profile` | string | 'raw' | |
| `transcription_mode` | string | 'dictation' | |
| `compute_type` | string | 'float16' | |
| `chunk_duration` | float | 1.6 | |
| `overlap_ratio` | float | 0.2 | |
| `vad_enabled` | boolean | True | |
| `vad_threshold_db` | float | -40.0 | |
| `vad_min_silence_ms` | integer | 200 | |
| `vad_speech_pad_ms` | integer | 200 | |
| `confidence_threshold` | float | 0.6 | |
| `enable_filler_filter` | boolean | True | |
| `enable_hallucination_filter` | boolean | True | |
| `min_segment_length` | float | 0.5 | |
| `max_workers` | integer | 4 | |
| `use_parallel_processing` | boolean | True | |
| `preload_model` | boolean | True | |
| `hotkey_optimized` | boolean | False | |
| `beam_size` | integer | 5 | |
| `best_of` | integer | 5 | |
| `patience` | float | 1.0 | |
| `temperature` | float | 0.0 | |

## Audio Settings

Audio capture settings.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `captureMode` | string | 'microphone' | |
| `default_capture_source` | string | 'microphone' | |
| `defaultDeviceId` | string | 'default' | |
| `backend` | string | 'auto' | |
| `audio_backend` | string | 'auto' | |
| `sampleRate` | integer | 16000 | |
| `vadEnabled` | boolean | True | |
| `vadThresholdDb` | float | -40.0 | |
| `noiseFiltering` | boolean | True | |
| `echoCancellation` | boolean | True | |
| `autoGainControl` | boolean | True | |

## Refiner Settings

LLM refiner settings.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `selected_model_id` | string | 'qwen2.5-3b-instruct' | |
| `runtime_enabled` | boolean | False | |
| `cleanup_instructions` | string | '' | |
| `engine_preference` | string | 'llamacpp' | |

## Hotkey Settings

Global hotkey settings.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | False | |
| `key_combination` | string | 'Ctrl+Shift+T' | |
| `microphone_key_combination` | string | 'Ctrl+Shift+T' | |
| `system_key_combination` | string | 'CommandOrControl+Shift+Y' | |
| `hold_mode` | boolean | False | |
| `auto_inject` | boolean | True | |
| `language` | string | 'auto' | |
| `device_id` | string | 'default' | |
| `capture_source` | string | 'microphone' | |
| `finish_mode_default` | string | 'finish_and_paste' | |
| `enable_refiner_on_stop` | boolean | False | |
| `save_debug_wav` | boolean | False | |
| `show_floating_window` | boolean | True | |
| `floating_window_position` | string | 'bottom-right' | |
| `record_on_start` | boolean | False | |
| `stop_on_release` | boolean | False | |
| `copy_to_clipboard` | boolean | True | |

## Coach Settings

English Coach settings.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `coach_enabled` | boolean | True | |
| `coach_show_live_hints` | boolean | False | |
| `coach_detail_level` | string | 'compact' | |
| `copy_polished_by_default` | boolean | True | |
| `show_diff_view` | boolean | True | |
| `coach_template_id_mic` | string | 'default_english_coach' | |
| `coach_template_id_system` | string | 'default_english_coach' | |
| `coach_prompt_custom_enabled` | boolean | False | |
| `coach_prompt_custom_text` | string | '' | |
| `coach_overrides` | CoachPromptOverrides | '<computed>' | |
| `privacy_mode` | string | 'local_only' | |
| `show_floating_coach_result` | boolean | True | |
| `coach_prompt_templates` | array | '<computed>' | |

## Advanced Settings

Advanced settings.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `debugMode` | boolean | False | |
| `logLevel` | string | 'INFO' | |
| `enableMetrics` | boolean | True | |
| `maxLogFiles` | integer | 10 | |
| `experimentalStem` | boolean | False | |
| `experimentalGpuAccel` | boolean | True | |
<!-- END GENERATED -->

---

---

## Environment Variables

All environment variables use the `TRANSCRIPTA_` prefix. These can be set in a `.env` file or directly in your system environment.

### Core Application

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `TRANSCRIPTA_DEVICE` | string | `auto` | Execution device: `cuda`, `cpu`, or `auto` |
| `TRANSCRIPTA_COMPUTE_TYPE` | string | `float16` | Precision mode: `float16`, `int8`, or `int8_float16` |
| `TRANSCRIPTA_DEFAULT_MODEL` | string | `medium` | Whisper model size: `tiny`, `base`, `small`, `medium`, `large-v3`, `turbo` |
| `TRANSCRIPTA_DEFAULT_LANGUAGE` | string | `auto` | Default language code (e.g., `en`, `hi`, `auto`) |
| `TRANSCRIPTA_LOG_LEVEL` | string | `INFO` | Log level: `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `TRANSCRIPTA_API_HOST` | string | `127.0.0.1` | API server host address |
| `TRANSCRIPTA_API_PORT` | int | `8765` | API server port |
| `TRANSCRIPTA_EXPORT_ROOT` | path | `./sessions` | Root directory for session exports |
| `TRANSCRIPTA_DOWNLOAD_ROOT` | path | `./models` | Model download/cache directory |

### Audio Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `TRANSCRIPTA_SAMPLE_RATE` | int | `16000` | Audio sample rate in Hz |
| `TRANSCRIPTA_CHANNELS` | int | `1` | Audio channels (1=mono, 2=stereo) |
| `TRANSCRIPTA_CHUNK_SECONDS` | float | `1.6` | Audio chunk duration in seconds |
| `TRANSCRIPTA_OVERLAP_SECONDS` | float | `0.32` | Overlap between chunks in seconds |
| `TRANSCRIPTA_CAPTURE_BLOCK_SECONDS` | float | `0.02` | Capture block size in seconds |
| `TRANSCRIPTA_METER_DECAY` | float | `0.85` | VU meter decay factor (0.0-1.0) |
| `TRANSCRIPTA_CAPTURE_DEVICE_ID` | string | *(empty)* | Audio capture device ID |

### VAD (Voice Activity Detection)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `TRANSCRIPTA_VAD_FILTER` | bool | `true` | Enable VAD filtering |
| `TRANSCRIPTA_VAD_THRESHOLD` | float | `0.5` | VAD threshold (0.0-1.0) |
| `TRANSCRIPTA_VAD_MIN_SILENCE_MS` | int | `200` | Minimum silence duration in ms |
| `TRANSCRIPTA_VAD_SPEECH_PAD_MS` | int | `200` | Padding added to speech segments in ms |

### Transcription Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `TRANSCRIPTA_BEAM_SIZE` | int | `5` | Beam search width (1-20) |
| `TRANSCRIPTA_BEST_OF` | int | `5` | Number of candidates to consider (1-20) |
| `TRANSCRIPTA_TEMPERATURE` | float | `0.0` | Sampling temperature (0.0-1.0) |
| `TRANSCRIPTA_DEFAULT_LIVE_MODE` | string | `balanced` | Live mode profile |
| `TRANSCRIPTA_DEFAULT_EXECUTION_MODE` | string | `auto` | Execution mode: `auto`, `gpu_only`, `cpu_only` |

### Performance

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `TRANSCRIPTA_MAX_QUEUE_ITEMS` | int | `16` | Maximum STT queue items |
| `TRANSCRIPTA_OUTPUT_REFRESH_SECONDS` | float | `0.5` | Output refresh interval |
| `TRANSCRIPTA_AUTO_OPTIMIZE` | bool | `true` | Enable auto-optimization |
| `TRANSCRIPTA_OPTIMIZATION_MODE` | string | `balanced` | Optimization mode: `maximum`, `balanced`, `speed`, `low_memory` |

### Advanced

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `TRANSCRIPTA_CONDITION_ON_PREVIOUS_TEXT` | bool | `true` | Condition on previous text for context |
| `TRANSCRIPTA_COMPRESSION_RATIO_THRESHOLD` | float | *null* | Compression ratio threshold for quality control |
| `TRANSCRIPTA_NUM_CUDA_STREAMS` | int | `2` | Number of CUDA streams |

### Setting Environment Variables (PowerShell)

```powershell
# Set for current session
$env:TRANSCRIPTA_DEVICE = "cuda"
$env:TRANSCRIPTA_COMPUTE_TYPE = "float16"
$env:TRANSCRIPTA_DEFAULT_MODEL = "medium"
$env:TRANSCRIPTA_LOG_LEVEL = "DEBUG"

# Set permanently (requires restart)
[Environment]::SetEnvironmentVariable("TRANSCRIPTA_DEVICE", "cuda", "User")
[Environment]::SetEnvironmentVariable("TRANSCRIPTA_COMPUTE_TYPE", "float16", "User")
```

### Setting Environment Variables (Command Prompt)

```cmd
# Set for current session
set TRANSCRIPTA_DEVICE=cuda
set TRANSCRIPTA_COMPUTE_TYPE=float16

# Set permanently
setx TRANSCRIPTA_DEVICE cuda
setx TRANSCRIPTA_COMPUTE_TYPE float16
```

---

## Settings File Structure

The `user_settings.json` file stores all user-configurable settings. It is organized by category:

### File Location

```
<app_root>/user_settings.json
```

### Complete Structure

```json
{
  "version": 5,
  "general": {
    "defaultSessionTitle": "New Session",
    "defaultLanguage": "auto",
    "exportDirectory": "",
    "autoSaveInterval": 30,
    "showNotifications": true,
    "minimizeToTray": true,
    "startupWithSystem": false,
    "theme": "light"
  },
  "transcription": {
    "model_name": "medium",
    "default_asr_model_id": "whisper-medium",
    "microphone_asr_model_id": "whisper-medium",
    "system_asr_model_id": "whisper-medium",
    "refinement_mode": "off",
    "refinement_profile": "raw",
    "transcription_mode": "dictation",
    "compute_type": "float16",
    "chunk_duration": 1.6,
    "overlap_ratio": 0.2,
    "vad_enabled": true,
    "vad_threshold_db": -40.0,
    "vad_min_silence_ms": 200,
    "vad_speech_pad_ms": 200,
    "confidence_threshold": 0.6,
    "enable_filler_filter": true,
    "enable_hallucination_filter": true,
    "min_segment_length": 0.5,
    "max_workers": 4,
    "use_parallel_processing": true,
    "preload_model": true,
    "hotkey_optimized": false,
    "beam_size": 5,
    "best_of": 5,
    "patience": 1.0,
    "temperature": 0.0
  },
  "coach": {
    "coach_enabled": true,
    "coach_show_live_hints": false,
    "coach_detail_level": "compact",
    "copy_polished_by_default": true,
    "show_diff_view": true,
    "coach_template_id_mic": "default_english_coach",
    "coach_template_id_system": "default_english_coach",
    "coach_prompt_custom_enabled": false,
    "coach_prompt_custom_text": "",
    "coach_overrides": {
      "tone": "neutral",
      "aggressiveness": "light",
      "filler_removal": true,
      "keep_slang": true,
      "target_style": "simple"
    },
    "privacy_mode": "local_only",
    "show_floating_coach_result": true
  },
  "refiner": {
    "selected_model_id": "qwen2.5-3b-instruct",
    "runtime_enabled": false,
    "cleanup_instructions": "",
    "engine_preference": "llamacpp"
  },
  "audio": {
    "captureMode": "microphone",
    "default_capture_source": "microphone",
    "defaultDeviceId": "default",
    "backend": "auto",
    "audio_backend": "auto",
    "sampleRate": 16000,
    "vadEnabled": true,
    "vadThresholdDb": -40.0,
    "noiseFiltering": true,
    "echoCancellation": true,
    "autoGainControl": true
  },
  "hotkey": {
    "enabled": false,
    "key_combination": "Ctrl+Shift+T",
    "hold_mode": false,
    "auto_inject": true,
    "language": "auto",
    "device_id": "default",
    "finish_mode_default": "finish_and_paste",
    "show_floating_window": true,
    "floating_window_position": "bottom-right",
    "record_on_start": false,
    "stop_on_release": false,
    "copy_to_clipboard": true
  },
  "advanced": {
    "debugMode": false,
    "logLevel": "INFO",
    "enableMetrics": true,
    "maxLogFiles": 10,
    "experimentalStem": false,
    "experimentalGpuAccel": true
  },
  "modes": {
    "wispr": { ... },
    "system": { ... },
    "active_mode": "system"
  }
}
```

### Category Descriptions

| Category | Description |
|----------|-------------|
| `general` | Application-wide settings (theme, language, auto-save) |
| `transcription` | Core transcription parameters (model, VAD, quality) |
| `refiner` | LLM refinement settings |
| `coach` | English Coach settings (polished output, coaching notes) |
| `audio` | Audio capture and device settings |
| `hotkey` | Global hotkey configuration |
| `advanced` | Debug, logging, and experimental features |
| `modes` | Per-mode configuration overrides |

---

## Mode-Specific Defaults

OpenWispr supports two transcription modes with optimized defaults:

### Wispr Mode (Hotkey Dictation)

Optimized for low-latency microphone dictation triggered by hotkey.

**Source:** `app/core/modes.py:WisprModeDefaults`

| Setting | Default | Description |
|---------|---------|-------------|
| `model_name` | `tiny` | Smallest/fastest model |
| `beam_size` | `1` | Greedy decoding for speed |
| `best_of` | `1` | No candidate exploration |
| `vad_threshold` | `-40.0` | Moderate sensitivity |
| `chunk_duration` | `0.5` | 500ms chunks (fast) |
| `overlap_ratio` | `0.1` | Minimal overlap |
| `compute_type` | `int8` | Low precision for speed |
| `vad_enabled` | `true` | VAD active |
| `vad_min_silence_ms` | `300` | 300ms silence threshold |
| `vad_speech_pad_ms` | `100` | 100ms padding |
| `confidence_threshold` | `0.6` | 60% confidence threshold |
| `enable_filler_filter` | `true` | Filter filler words |
| `enable_hallucination_filter` | `true` | Filter hallucinations |
| `temperature` | `0.0` | Deterministic output |
| `hotkey_optimized` | `true` | Hotkey optimizations |

### System Mode (PC Audio Capture)

Optimized for high-accuracy system audio and video transcription.

**Source:** `app/core/modes.py:SystemModeDefaults`

| Setting | Default | Description |
|---------|---------|-------------|
| `model_name` | `medium` | Balanced accuracy/speed |
| `beam_size` | `5` | Standard beam search |
| `best_of` | `5` | Explore 5 candidates |
| `vad_threshold` | `-35.0` | Higher sensitivity |
| `chunk_duration` | `2.0` | 2-second chunks |
| `overlap_ratio` | `0.2` | 20% overlap |
| `compute_type` | `float16` | Full precision |
| `vad_enabled` | `true` | VAD active |
| `vad_min_silence_ms` | `500` | 500ms silence threshold |
| `vad_speech_pad_ms` | `200` | 200ms padding |
| `confidence_threshold` | `0.7` | 70% confidence threshold |
| `enable_filler_filter` | `true` | Filter filler words |
| `enable_hallucination_filter` | `true` | Filter hallucinations |
| `temperature` | `0.0` | Deterministic output |
| `hotkey_optimized` | `false` | No hotkey optimizations |

### Mode Configuration JSON Structure

```json
{
  "modes": {
    "wispr": {
      "model_name": "tiny",
      "beam_size": 1,
      "vad_threshold": -40.0,
      "chunk_duration": 0.5,
      "overlap_ratio": 0.1,
      "compute_type": "int8",
      "vad_enabled": true,
      "vad_min_silence_ms": 300,
      "vad_speech_pad_ms": 100,
      "confidence_threshold": 0.6,
      "enable_filler_filter": true,
      "enable_hallucination_filter": true,
      "best_of": 1,
      "temperature": 0.0,
      "hotkey_optimized": true
    },
    "system": {
      "model_name": "medium",
      "beam_size": 5,
      "vad_threshold": -35.0,
      "chunk_duration": 2.0,
      "overlap_ratio": 0.2,
      "compute_type": "float16",
      "vad_enabled": true,
      "vad_min_silence_ms": 500,
      "vad_speech_pad_ms": 200,
      "confidence_threshold": 0.7,
      "enable_filler_filter": true,
      "enable_hallucination_filter": true,
      "best_of": 5,
      "temperature": 0.0,
      "hotkey_optimized": false
    },
    "active_mode": "system"
  }
}
```

---

## Validation Bounds

All settings are validated against these bounds. Values outside these ranges will be rejected.

### Audio Bounds

| Setting | Min | Max | Default |
|---------|-----|-----|---------|
| `chunk_duration` | 0.5s | 5.0s | 1.6s |
| `overlap_ratio` | 0.0 | 0.5 | 0.2 |
| `sampleRate` | 8000 | 48000 | 16000 |

### VAD Bounds

| Setting | Min | Max | Default |
|---------|-----|-----|---------|
| `vad_threshold_db` | -60 dB | -20 dB | -40 dB |
| `vad_min_silence_ms` | 0 ms | 5000 ms | 300 ms |
| `vad_speech_pad_ms` | 0 ms | 1000 ms | 200 ms |

### Model Bounds

| Setting | Min | Max | Default |
|---------|-----|-----|---------|
| `beam_size` | 1 | 20 | 5 |
| `best_of` | 1 | 20 | 5 |
| `patience` | 0.1 | 5.0 | 1.0 |
| `temperature` | 0.0 | 1.0 | 0.0 |
| `confidence_threshold` | 0.0 | 1.0 | 0.6 |
| `min_segment_length` | 0.1s | 2.0s | 0.5s |

### Performance Bounds

| Setting | Min | Max | Default |
|---------|-----|-----|---------|
| `max_workers` | 1 | 16 | 4 |
| `autoSaveInterval` | 10s | 300s | 30s |
| `maxLogFiles` | 1 | 100 | 10 |

### Session Bounds

| Setting | Min | Max | Default |
|---------|-----|-----|---------|
| `SESSION_TITLE_LENGTH` | 1 | 100 chars | - |

### Valid Enumerations

| Setting | Valid Values | Default |
|---------|--------------|---------|
| `model_name` | `tiny`, `base`, `small`, `medium`, `large-v3`, `turbo` | `medium` |
| `compute_type` | `float16`, `int8`, `int8_float16` | `float16` |
| `theme` | `light`, `dark`, `cyber`, `dracula` | `light` |
| `live_mode` | `ultra`, `realtime`, `low_latency`, `balanced`, `high_accuracy` | `balanced` |
| `execution_mode` | `auto`, `cpu_only`, `gpu_only` | `auto` |
| `optimization_mode` | `maximum`, `balanced`, `speed`, `low_memory` | `balanced` |
| `refinement_mode` | `off`, `strict`, `polished` | `off` |
| `refinement_profile` | `raw`, `clean_dictation`, `professional`, `student_notes`, `code_logs` | `raw` |
| `transcription_mode` | `dictation`, `literal` | `dictation` |
| `engine_preference` | `llamacpp`, `ollama` | `llamacpp` |
| `captureMode` | `system`, `microphone` | `microphone` |
| `floating_window_position` | `top-left`, `top-right`, `bottom-left`, `bottom-right`, `center` | `bottom-right` |

---

## Live Mode Profiles

Live mode profiles adjust chunk sizing for different latency/accuracy trade-offs.

**Source:** `app/config/constants.py:LIVE_MODE_PROFILES`

| Profile | Chunk Size | Overlap | Use Case |
|---------|------------|---------|----------|
| `ultra` | 100ms | 20ms | Fastest response, lowest accuracy |
| `realtime` | 200ms | 40ms | Fast response for live interaction |
| `low_latency` | 500ms | 100ms | Balanced low latency |
| `balanced` | 1000ms | 200ms | Default balance (recommended) |
| `high_accuracy` | 2000ms | 400ms | Maximum accuracy, higher latency |

### Profile JSON

```json
{
  "live_mode_profiles": {
    "ultra": {
      "chunk_seconds": 0.1,
      "overlap_seconds": 0.02
    },
    "realtime": {
      "chunk_seconds": 0.2,
      "overlap_seconds": 0.04
    },
    "low_latency": {
      "chunk_seconds": 0.5,
      "overlap_seconds": 0.1
    },
    "balanced": {
      "chunk_seconds": 1.0,
      "overlap_seconds": 0.2
    },
    "high_accuracy": {
      "chunk_seconds": 2.0,
      "overlap_seconds": 0.4
    }
  }
}
```

### Selecting a Profile

Set via environment variable:

```powershell
$env:TRANSCRIPTA_DEFAULT_LIVE_MODE = "realtime"
```

Or in settings file:

```json
{
  "transcription": {
    "live_mode": "realtime"
  }
}
```

---

## Example Configurations

### Minimal Configuration (.env)

```env
# Essential settings only
TRANSCRIPTA_DEVICE=cuda
TRANSCRIPTA_DEFAULT_MODEL=small
TRANSCRIPTA_LOG_LEVEL=INFO
```

### High-Performance GPU Configuration

```env
# Maximum quality on high-end GPU
TRANSCRIPTA_DEVICE=cuda
TRANSCRIPTA_COMPUTE_TYPE=float16
TRANSCRIPTA_DEFAULT_MODEL=large-v3
TRANSCRIPTA_BEAM_SIZE=10
TRANSCRIPTA_BEST_OF=10
TRANSCRIPTA_DEFAULT_LIVE_MODE=high_accuracy
TRANSCRIPTA_NUM_CUDA_STREAMS=4
```

### CPU-Only Configuration

```env
# Optimized for CPU execution
TRANSCRIPTA_DEVICE=cpu
TRANSCRIPTA_COMPUTE_TYPE=int8
TRANSCRIPTA_DEFAULT_MODEL=small
TRANSCRIPTA_BEAM_SIZE=3
TRANSCRIPTA_DEFAULT_LIVE_MODE=balanced
TRANSCRIPTA_MAX_QUEUE_ITEMS=8
```

### Low-Latency Dictation

```env
# Fast response for dictation
TRANSCRIPTA_DEVICE=cuda
TRANSCRIPTA_COMPUTE_TYPE=int8
TRANSCRIPTA_DEFAULT_MODEL=tiny
TRANSCRIPTA_BEAM_SIZE=1
TRANSCRIPTA_DEFAULT_LIVE_MODE=realtime
TRANSCRIPTA_VAD_MIN_SILENCE_MS=200
```

### Development/Debug Configuration

```env
# Verbose logging for troubleshooting
TRANSCRIPTA_LOG_LEVEL=DEBUG
TRANSCRIPTA_DEBUG=true
TRANSCRIPTA_ENABLE_METRICS=true
```

### Complete User Settings (user_settings.json)

```json
{
  "version": 5,
  "general": {
    "defaultSessionTitle": "Meeting Notes",
    "defaultLanguage": "en",
    "exportDirectory": "C:/Transcripts",
    "autoSaveInterval": 60,
    "theme": "dark"
  },
  "transcription": {
    "model_name": "medium",
    "compute_type": "float16",
    "chunk_duration": 1.6,
    "overlap_ratio": 0.2,
    "vad_enabled": true,
    "vad_threshold_db": -40,
    "vad_min_silence_ms": 300,
    "confidence_threshold": 0.7,
    "enable_filler_filter": true,
    "enable_hallucination_filter": true,
    "beam_size": 5,
    "best_of": 5,
    "temperature": 0.0
  },
  "audio": {
    "captureMode": "system",
    "defaultDeviceId": "default",
    "backend": "auto",
    "sampleRate": 16000,
    "vadEnabled": true,
    "vadThresholdDb": -40
  },
  "hotkey": {
    "enabled": true,
    "key_combination": "Ctrl+Shift+T",
    "hold_mode": true,
    "auto_inject": true,
    "show_floating_window": true,
    "floating_window_position": "bottom-right",
    "copy_to_clipboard": true
  },
  "advanced": {
    "debugMode": false,
    "logLevel": "INFO",
    "enableMetrics": true,
    "maxLogFiles": 10
  },
  "modes": {
    "wispr": {
      "model_name": "tiny",
      "beam_size": 1,
      "chunk_duration": 0.5,
      "compute_type": "int8",
      "hotkey_optimized": true
    },
    "system": {
      "model_name": "medium",
      "beam_size": 5,
      "chunk_duration": 2.0,
      "compute_type": "float16",
      "hotkey_optimized": false
    },
    "active_mode": "system"
  }
}
```

### Per-Mode Configuration Examples

#### Wispr Mode (Quick Dictation)

```json
{
  "modes": {
    "wispr": {
      "model_name": "tiny",
      "beam_size": 1,
      "vad_threshold": -40,
      "chunk_duration": 0.5,
      "overlap_ratio": 0.1,
      "compute_type": "int8",
      "vad_enabled": true,
      "vad_min_silence_ms": 300,
      "vad_speech_pad_ms": 100,
      "confidence_threshold": 0.6,
      "enable_filler_filter": true,
      "enable_hallucination_filter": true,
      "best_of": 1,
      "temperature": 0,
      "hotkey_optimized": true
    }
  }
}
```

#### System Mode (Meeting Recording)

```json
{
  "modes": {
    "system": {
      "model_name": "medium",
      "beam_size": 5,
      "vad_threshold": -35,
      "chunk_duration": 2.0,
      "overlap_ratio": 0.2,
      "compute_type": "float16",
      "vad_enabled": true,
      "vad_min_silence_ms": 500,
      "vad_speech_pad_ms": 200,
      "confidence_threshold": 0.7,
      "enable_filler_filter": true,
      "enable_hallucination_filter": true,
      "best_of": 5,
      "temperature": 0,
      "hotkey_optimized": false
    }
  }
}
```

### Model Memory Requirements

| Model | Float16 VRAM | Int8 VRAM | Speed | Accuracy |
|-------|--------------|-----------|-------|----------|
| `tiny` | ~1 GB | ~0.6 GB | Fastest | Basic |
| `base` | ~1 GB | ~0.6 GB | Very Fast | Low |
| `small` | ~2 GB | ~1.2 GB | Fast | Good |
| `medium` | ~5 GB | ~3 GB | Moderate | Very Good |
| `large-v3` | ~10 GB | ~6 GB | Slow | Best |
| `turbo` | ~6 GB | ~3.6 GB | Fast | Excellent |

---

## Reference: Source Code Locations

| Component | File Path |
|-----------|-----------|
| Environment Config | `app/core/config.py` |
| App Settings | `app/core/config.py:AppSettings` |
| Mode Settings | `app/core/modes.py:ModeSettings` |
| Constants | `app/config/constants.py` |
| Settings Registry | `app/config/settings.py` |
| Frontend Constants | `app/electron/frontend/src/config/generated/constants.ts` |

---

## Migration History

Settings are automatically migrated when the app starts. Current version: **5**

| Version | Changes |
|---------|---------|
| 1 | Initial versioned settings with categories (general, transcription, refiner, audio, hotkey, advanced) |
| 2 | Added `default_asr_model_id`, `refinement_mode`, `refinement_profile`, and refiner settings |
| 3 | Added hotkey settings, moved VAD settings to transcription category |
| 4 | Renamed `backend` to `audio_backend`, removed duplicate VAD from audio |
| 5 | Added `coach` category with English Coach settings and prompt templates |

---

## Migration History

Settings are automatically migrated when the app starts. Current version: **5**

| Version | Changes |
|---------|---------|
| 1 | Initial versioned settings with categories (general, transcription, refiner, audio, hotkey, advanced) |
| 2 | Added `default_asr_model_id`, `refinement_mode`, `refinement_profile`, and refiner settings |
| 3 | Added hotkey settings, moved VAD settings to transcription category |
| 4 | Renamed `backend` to `audio_backend`, removed duplicate VAD from audio |
| 5 | Added `coach` category with English Coach settings and prompt templates |

---

## Notes

- Settings are validated on startup; invalid values fall back to defaults
- The `version` field in `user_settings.json` enables migration between app versions
- Mode-specific settings in `modes` override global transcription settings when that mode is active
- Fake/not-implemented settings are marked with `is_fake: true` in the registry
