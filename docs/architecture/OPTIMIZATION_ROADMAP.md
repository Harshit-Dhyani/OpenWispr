# Transcripta Optimization Roadmap

**Status:** Active and code-aligned  
**Last Updated:** March 3, 2026  
**Scope:** Electron main + React renderer + FastAPI backend + faster-whisper + optional llama.cpp refiner

## Purpose

This roadmap tracks the real optimization work that matters for Transcripta today:

- hotkey dictation reliability
- live transcription latency
- transcript correctness
- model download robustness
- renderer responsiveness
- observability and debugging

This document is intentionally tied to the current codebase and should be updated when the implementation changes.

## Current Architecture

### Runtime paths

- Main transcript UI consumes backend events from `app/api/server.py`
- Hotkey dictation uses:
  - start/stop HTTP endpoints in `app/api/server.py`
  - WebSocket `GET /api/transcription/hotkey/ws`
  - Electron main handler in `app/electron/main/ipc/hotkeyHandlers.js`
- ASR runtime uses:
  - `app/stt/fast_engine.py`
  - `app/stt/fast_whisper_backend.py`
  - `app/stt/model_pool.py`
- Model downloads use:
  - `app/electron/main/model-download-manager.js`
- Optional refiner runtime uses:
  - `app/api/refiner_service.py`

### Current strengths

- Source-aware ASR settings exist:
  - `transcription.microphone_asr_model_id`
  - `transcription.system_asr_model_id`
- Hotkey stop acknowledgment exists via `hotkey_stop_ack`
- JSON-safe transport helpers exist:
  - `app/api/json_utils.py`
  - `app/api/websocket_server.py`
- Refiner status endpoint exists:
  - `GET /api/refiner/status`
- Runtime branding is centralized:
  - `app/config/constants.py`
  - `app/core/constants.py`

## What Is Already Implemented

### Reliability

- Hotkey stop no longer waits on final transcription to acknowledge stop.
- Late `hotkey_stopped` events are handled after `hotkey_stop_ack`.
- Duplicate hotkey partial event emission was reduced so draft and final paths are clearer.
- Download resume/retry support exists in the Electron model download manager.

### Settings and model routing

- Microphone and system audio can use different ASR model IDs.
- Default ASR model changes can propagate into source-specific defaults.
- Settings migration already maps older model fields into the canonical schema.

### Observability

- JSON-safe event encoding exists at the backend boundary.
- Refiner fallback now reports status via API.
- Download manager logs attempt, URL, status, and retry context.
- Model pool logs cache hits and load starts/completions.

## What Is Still Not Good Enough

### 1. Hotkey dictation quality

Current pain:

- short phrases can still truncate or repeat
- overlap/final-segment dedupe is still not strong enough
- first partial can still be slower than it should be on cold model loads

Files:

- `app/api/server.py`
- `app/stt/fast_engine.py`
- `app/stt/fast_whisper_backend.py`

### 2. Renderer responsiveness

Current pain:

- audio-level and live transcript UI can still feel heavy
- debug mode can expose too much noise
- some state transitions still trigger too many updates

Files:

- `app/electron/frontend/src/App.tsx`
- `app/electron/frontend/src/components/MainContent.tsx`
- `app/electron/frontend/src/lib/liveTranscript.ts`
- `app/electron/main/ipc/hotkeyHandlers.js`

### 3. Download UX

Current pain:

- progress behavior is better, but large-model UX is still rough
- finished-vs-partial validation is not strict enough
- missing optional artifacts need to stay non-fatal everywhere

Files:

- `app/electron/main/model-download-manager.js`
- `app/core/model_catalog.py`

### 4. Refiner UX

Current pain:

- runtime fallback is now explicit, but the UI still needs to surface it cleanly
- users need a simple post-processing explanation and a safe default prompt

Files:

- `app/api/refiner_service.py`
- `app/electron/frontend/src/components/settings/sections/ModelSection.tsx`
- `app/electron/frontend/src/components/settings/sections/TranscriptionSection.tsx`

## Priority Roadmap

## P0: Correctness and User Trust

These are the highest-value fixes and should stay ahead of new features.

### P0.1 Hotkey transcript correctness

Goal:

- no repeated phrase spam
- no duplicate partial/final rendering
- no stale-session transcript updates

Work:

- strengthen overlap and final-tail dedupe in `app/api/server.py`
- use timestamp/end-time-aware merge rules
- keep draft and committed text strictly separate in the renderer

Success criteria:

- saying a short phrase once should not repeat it multiple times
- `draft -> final` produces one stable final result

### P0.2 Deterministic source-aware ASR routing

Goal:

- the selected source model is always the one actually loaded

Work:

- preserve `microphone_asr_model_id` and `system_asr_model_id` as the routing source
- keep logs showing both:
  - `resolved_asr_model_id`
  - `runtime_model_name`

Success criteria:

- selecting `whisper-tiny` for microphone must log `resolved_asr_model_id=whisper-tiny`

### P0.3 Download integrity and resume safety

Goal:

- large model downloads do not restart unnecessarily
- optional/missing artifacts do not break installs

Work:

- keep `Range` resume behavior
- validate final artifacts more strictly before skipping them
- treat optional vocab-style files as skippable

Success criteria:

- interrupted large downloads resume
- `whisper-turbo` does not fail on missing vocabulary-style artifacts

## P1: Latency and Responsiveness

### P1.1 Faster hotkey first partial

Goal:

- reduce `start -> first_partial_ms`

Work:

- preload frequently used ASR models
- keep dictation-friendly decode defaults for hotkey
- reduce cold-start penalties

Targets:

- warm start first partial under `700ms`
- cold start clearly signaled in UI

### P1.2 Smoother waveform and lower renderer churn

Goal:

- reduce UI lag during recording

Work:

- cap waveform/audio-level update frequency
- keep live transcript updates lightweight
- avoid rerendering unrelated UI on every audio-level tick

### P1.3 Better SSE stability and quieter disconnect logs

Goal:

- `/api/events` disconnects are treated as normal client lifecycle, not suspicious failures

Work:

- maintain counters for connections, keepalives, and sent events
- keep disconnect logging informative but not noisy

## P2: Clarity and UX

### P2.1 Simplify settings

Goal:

- make the app understandable without reading implementation details

Work:

- one `System Profile` section only
- hide advanced decode knobs behind an advanced section
- clearly separate:
  - ASR engine
  - ASR model
  - refiner runtime
  - refiner model

### P2.2 Better post-processing experience

Goal:

- make the optional refiner understandable and safe

Work:

- expose runtime status from `/api/refiner/status`
- show whether llama.cpp is installed
- add small cleanup-instructions UX
- keep strict mode meaning-preserving

## Recommended Defaults

These should remain the practical defaults unless testing proves otherwise.

### Hotkey dictation

- ASR engine: faster-whisper
- default preset: `Dictation (Recommended)`
- microphone model:
  - `whisper-small` or `whisper-medium` on most systems
- system audio model:
  - `whisper-medium` or `large-v3-turbo` when quality matters more than speed

### Refiner

- runtime: optional
- mode default: `off` unless explicitly enabled
- recommended small local model: Qwen 2.5 3B instruct GGUF

## Observability Requirements

These logs and signals should exist and stay consistent.

### Hotkey

- session correlation id
- start time
- first partial latency
- stop ack latency
- stop total latency
- whether decode/refiner was cancelled

### Downloads

- download id
- attempt
- artifact filename
- resolved host
- bytes downloaded
- duration
- retry reason

### Model loading

- model id
- runtime model name
- device
- compute type
- cache hit vs new load
- load time

### Refiner

- runtime availability
- fallback reason
- used runtime or fallback
- latency

## What To Do Next

If you want the next highest-impact work, do it in this order:

1. Strengthen hotkey transcript dedupe in `app/api/server.py`
2. Tighten dictation defaults in `app/stt/fast_engine.py` and `app/stt/fast_whisper_backend.py`
3. Surface `/api/refiner/status` directly in the settings UI
4. Validate existing final model artifacts before skipping downloads
5. Reduce renderer churn from live audio-level updates

## What Not To Do

Do not spend time yet on:

- broad architecture rewrites
- switching away from faster-whisper
- heavy CSP changes in dev without a full Electron/Vite pass
- replacing the current downloader stack if the current one can be hardened incrementally

## Definition of Better

Transcripta is better when:

- short dictation does not repeat or truncate text
- the selected ASR model is the one actually used
- hotkey stop feels instant and reliable
- large model downloads survive flaky networks
- the renderer stays responsive while recording
- users can understand settings without knowing the internals

## Related Documents

- `docs/architecture/MODEL_SYSTEM.md`
- `docs/api/endpoints.md`
- `reports/tree.txt`
- `reports/changes-since-last-commit.md`
