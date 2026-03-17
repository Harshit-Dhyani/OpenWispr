---
name: openwispr-runtime-debug
description: Use when debugging OpenWispr model/runtime/audio/transcription failures. Covers model catalog and download ownership, audio backend/device selection, hotkey and session flows, and existing repo diagnostics.
---

# OpenWispr Runtime Debug

Use this skill for runtime investigation before patching.

## Primary Files

- `app/core/model_catalog.py`
- `app/api/model_service.py`
- `app/stt/model_pool.py`
- `app/audio/`
- `app/stt/`
- `app/core/hotkey_session.py`
- `app/core/system_session.py`
- `app/storage/history_db.py`
- `app/api/websocket_server.py`

## Existing Diagnostics

- `python tools/runner.py --system`
- `python tools/runner.py --audio`
- `python tools/runner.py --ci`
- `python tools/diagnostics/check-system.py`
- `python tools/diagnostics/check-audio.py`
- `python scripts/validate.py --quick`

## Debug Targets

- model catalog vs selected/preloaded/downloaded model ownership
- audio backend selection and device routing
- microphone vs system audio mode separation
- shared vs mode-specific transcription pipeline pieces
- hotkey transcript start/stop and final text flow
- session/history persistence and replay flow

## Rules

- Distinguish runtime bugs from doc drift.
- Preserve hotkey final transcript ownership semantics.
- Preserve source-specific model selection semantics.
- Treat clean disconnects as normal behavior, not application errors.
