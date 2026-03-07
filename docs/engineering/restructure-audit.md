---
title: Restructure Audit
owner: docs/ux
audience: developers
last_verified: 2026-03-07
review_cadence: quarterly
source_of_truth:
  - app/
  - docs/
critical: false
---

# Restructure Audit

This document is the discovery baseline for the ongoing architecture cleanup. It records what currently exists, what appears duplicated or ambiguous, and which areas should not be moved casually.

## Current Map

- Python runtime root: `app/`
- Backend transport: `app/api/routes/`, `app/api/server.py`, `app/api/websocket_server.py`
- Backend feature/service mix: `app/api/services/`, `app/api/model_service.py`, `app/api/coach_service.py`, `app/api/refiner_service.py`
- Core orchestration and state: `app/core/mode_manager.py`, `app/core/settings_manager.py`, `app/core/session_manager.py`, `app/core/hotkey_session.py`, `app/core/system_session.py`
- Shared config candidates: `app/config/settings.py`, `app/config/constants.py`, `app/config/text.py`, `app/config/generate_ts.py`
- Audio runtime: `app/audio/`
- STT runtime: `app/stt/`
- Persistence: `app/storage/`
- Electron main: `app/electron/main/`
- Renderer: `app/electron/frontend/src/`
- Electron shell strings: `app/electron/strings/en.js`
- Renderer strings: `app/electron/frontend/src/strings/en.ts`

## Entry Points

- Python app: `app/main.py`
- Python API: `app/api_main.py`
- Electron main: `app/electron/main/index.js`
- Dev/build orchestration: `scripts/dev.cjs`, `scripts/run-backend-dev.cjs`, `scripts/validate.py`

## Ownership Problems

- `app/api/` mixes transport, orchestration helpers, and feature services.
- `app/core/` mixes runtime orchestration, settings logic, config-like helpers, and general utilities.
- Settings ownership is split across config, core, API sync, and renderer settings UI.
- Model/runtime ownership is split across catalog, API service, STT model pool, and Electron/frontend download flows.
- Session and history concepts overlap across route, orchestration, and storage layers.
- Audio and STT boundaries are partly clean but still have overlapping chunker/pipeline concerns.

## Duplicate Or Overlapping Areas

### Config / text / constants

- `app/config/constants.py`
- `app/config/text.py`
- `app/core/constants.py`
- `app/core/config.py`
- generated TS in `app/electron/frontend/src/config/generated/`
- runtime strings in:
  - `app/electron/strings/en.js`
  - `app/electron/frontend/src/strings/en.ts`

### Settings

- `app/config/settings.py`
- `app/core/settings_manager.py`
- `app/core/settings_migrations.py`
- `app/core/settings_validator.py`
- `app/api/routes/settings.py`
- `app/api/settings_sync.py`
- renderer settings schema/UI files

### Model / runtime

- `app/core/model_catalog.py`
- `app/api/model_service.py`
- `app/stt/model_pool.py`

### Session / history

- `app/core/session_manager.py`
- `app/core/system_session.py`
- `app/core/hotkey_session.py`
- `app/storage/session_store.py`
- `app/storage/session_writer.py`
- `app/api/routes/session.py`
- `app/api/routes/history.py`
- `app/api/services/transcript_history_service.py`

### Audio / transcription

- `app/audio/chunker.py`
- `app/audio/chunking.py`
- `app/stt/chunker.py`
- `app/stt/fast_chunker.py`
- `app/audio/*pipeline*`
- `app/stt/*engine*`

### Coach / refiner

- `app/api/coach_service.py`
- `app/api/refiner_service.py`
- `app/api/refinement_queue.py`
- `app/config/coach_prompts.py`
- `app/stt/prompts.py`
- `app/stt/refiner_prompts.py`

## High-Risk Areas

- Settings migration and persistence compatibility
- Generated config/text/constants flow from `app/config/generate_ts.py`
- Electron preload/main/renderer contracts
- SSE/WebSocket payload shapes
- Hotkey final transcript ownership
- Audio backend and device routing
- Model selection, preload, and download flow
- Floating window wiring
- Session/history persistence keys and replacement semantics

## Initial Audit Labels

These labels are the starting point for cleanup batches, not final decisions:

- `app/config/generate_ts.py`: `KEEP`
- `app/electron/frontend/src/config/generated/*`: `GENERATED`
- `app/api/routes/*`: `KEEP`
- `app/api/model_service.py`: `MOVE`
- `app/api/coach_service.py`: `MOVE`
- `app/api/refiner_service.py`: `MOVE`
- `app/api/refinement_queue.py`: `MOVE`
- `app/core/constants.py`: `LEGACY-CANDIDATE`
- `app/core/config.py`: `LEGACY-CANDIDATE`
- `app/audio/chunker.py`: `LEGACY-CANDIDATE`
- `app/audio/chunking.py`: `LEGACY-CANDIDATE`
- `app/stt/chunker.py`: `LEGACY-CANDIDATE`

## First Cleanup Principle

Do not move runtime code until the destination ownership is explicit and the imports can be preserved with compatibility shims. Start with discovery docs, repo-local skills, and low-risk naming/ownership clarifications.
