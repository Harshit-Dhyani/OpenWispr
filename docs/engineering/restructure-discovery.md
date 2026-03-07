---
title: Restructure Discovery
owner: docs/ux
audience: developers
last_verified: 2026-03-07
review_cadence: quarterly
source_of_truth:
  - app/
critical: false
---

# Restructure Discovery

This document is the verified starting point for the OpenWispr cleanup program. It is intentionally limited to architecture mapping, ownership, risk boundaries, and safe first moves.

## Current Architecture Map

### Runtime entry points

- Python desktop entry: `app/main.py`
- Python API entry: `app/api_main.py`
- Backend app module: `app/api/server.py`
- Electron package entry: `app/electron/main/index.js`
- Electron bootstrap: `app/electron/main/index.js`
- Electron preloads:
  - `app/electron/main/preload/main.js`
  - `app/electron/main/preload/floating.js`
  - `app/electron/main/preload/quickSettings.js`

### Layer map

- `app/api/`
  - routes, some feature services, transport helpers, model/settings sync helpers
- `app/audio/`
  - capture, backends, pipelines, device selection, chunking helpers
- `app/config/`
  - product constants, text, settings registry, TS generation entrypoint
- `app/core/`
  - runtime orchestration, settings manager, mode/session state, model catalog, recovery/logging
- `app/storage/`
  - history/session/document persistence
- `app/stt/`
  - engines, model pool, prompts, cleanup, aggregation, chunkers
- `app/electron/main/`
  - windows, IPC, services, shared state/config, preloads
- `app/electron/shared/`
  - cross-shell helpers and theme tokens
- `app/electron/frontend/src/`
  - renderer UI, hooks, config, context, lib, strings, test

### Verified source-of-truth candidates

- Shared config/constants/text:
  - `app/config/constants.py`
  - `app/config/text.py`
  - `app/config/settings.py`
  - `app/config/generate_ts.py`
- Backend API copy:
  - `app/api/strings/en.py`
- Electron shell copy:
  - `app/electron/strings/en.js`
- Renderer copy:
  - `app/electron/frontend/src/strings/en.ts`
- Generated frontend config:
  - `app/electron/frontend/src/config/generated/constants.ts`
  - `app/electron/frontend/src/config/generated/settings.ts`
  - `app/electron/frontend/src/config/generated/text.ts`

### Verified structural facts

- Electron main is already partly organized by runtime role under `windows/`, `ipc/`, and `services/`.
- Floating window wiring is localized and should be treated as high-risk to move casually.
- Renderer structure is still technical-first, not feature-first.
- Settings are explicitly consumed from both Python and TS registries and require drift control.

## Biggest Structural Problems

- `app/core/` mixes runtime orchestration, shared logic, and feature-specific ownership.
- `app/api/` contains both transport-layer files and non-transport orchestration helpers.
- Settings ownership is distributed across config, manager, validator, migrations, sync, and UI schema.
- Config/constants/text ownership is partly centralized in `app/config/`, but overlapping files still exist in `app/core/` and the frontend.
- Model/runtime ownership is spread across `app/core/`, `app/api/`, and `app/stt/`.
- Session/history naming is conceptually overloaded across runtime state, routes, and persistence.
- Audio/transcription logic is separated physically but still has overlapping chunking/pipeline concepts.
- Electron shell boundaries are clearer than renderer ownership, which is still scattered by technical bucket.

## Duplicate Or Overlapping Modules

### Config, constants, and text

- KEEP as likely source-of-truth:
  - `app/config/constants.py`
  - `app/config/text.py`
  - `app/config/settings.py`
  - `app/config/generate_ts.py`
- AUDIT for overlap:
  - `app/core/constants.py`
  - `app/core/config.py`
  - `app/electron/strings/en.js`
  - `app/electron/frontend/src/strings/en.ts`
  - `app/electron/frontend/src/lib/settingsSchema.ts`

### Settings

- KEEP and audit together:
  - `app/config/settings.py`
  - `app/core/settings_manager.py`
  - `app/core/settings_migrations.py`
  - `app/core/settings_validator.py`
  - `app/api/routes/settings.py`
  - `app/api/settings_sync.py`
  - `app/electron/frontend/src/lib/settingsSchema.ts`
  - renderer settings components under `app/electron/frontend/src/components/settings/`

### Models and runtime

- KEEP and audit together:
  - `app/core/model_catalog.py`
  - `app/api/model_service.py`
  - `app/stt/model_pool.py`
  - preload/download UI wiring in frontend and Electron main

### Sessions and history

- KEEP and audit together:
  - `app/core/session_manager.py`
  - `app/core/system_session.py`
  - `app/core/hotkey_session.py`
  - `app/storage/session_store.py`
  - `app/storage/session_writer.py`
  - `app/api/routes/history.py`
  - `app/api/routes/session.py`
  - `app/api/services/transcript_history_service.py`

### Audio and transcription

- KEEP and audit together:
  - `app/audio/chunker.py`
  - `app/audio/chunking.py`
  - `app/stt/chunker.py`
  - `app/stt/fast_chunker.py`
  - `app/audio/*pipeline*`
  - `app/stt/*engine*`

### Coach and refiner

- KEEP and audit together:
  - `app/api/coach_service.py`
  - `app/api/refiner_service.py`
  - `app/api/refinement_queue.py`
  - `app/config/coach_prompts.py`
  - `app/stt/prompts.py`
  - `app/stt/refiner_prompts.py`

## Risky Areas That Must Not Be Moved Blindly

- Settings defaults, migrations, validation, persistence, and sync
- Generated config/text pipeline driven by `app/config/generate_ts.py`
- Electron preload/main/renderer contracts
- SSE/WebSocket payload shapes and event naming
- Hotkey final text path and transcript replacement semantics
- Audio backend selection and device routing
- Model preload/download/runtime reporting
- Floating window state, event binding, timer, and content loading
- Session/history persistence schema and segment identity rules

## File Audit Classification

This is the initial audit set for the first cleanup wave.

| Path | Classification | Notes |
| --- | --- | --- |
| `app/config/constants.py` | KEEP | Likely source-of-truth for shared constants |
| `app/config/text.py` | KEEP | Likely source-of-truth for shared labels and descriptions |
| `app/config/settings.py` | KEEP | Authoritative settings registry candidate |
| `app/config/generate_ts.py` | KEEP | Codegen source, generated flow must remain explicit |
| `app/core/constants.py` | LEGACY-CANDIDATE | Overlap with `app/config/constants.py` must be reduced carefully |
| `app/core/config.py` | LEGACY-CANDIDATE | Name overlaps with `app/config/`; audit before move |
| `app/core/settings_manager.py` | KEEP | Runtime owner, but too central and should be split later |
| `app/core/settings_migrations.py` | KEEP | High-risk, keep stable |
| `app/core/settings_validator.py` | KEEP | High-risk, keep stable |
| `app/api/settings_sync.py` | MOVE | Should trend toward transport/integration boundary later |
| `app/api/model_service.py` | MOVE | Service/orchestration naming under API is misleading |
| `app/api/websocket_server.py` | MOVE | Better under API transport grouping later |
| `app/electron/main/windows/` | KEEP | Already aligned with target structure |
| `app/electron/main/ipc/` | KEEP | Already aligned with target structure |
| `app/electron/main/shared/` | MERGE | Ownership should be clarified against `app/electron/shared/` |
| `app/electron/shared/theme-tokens.css` | KEEP | Theme source-of-truth candidate |
| `app/electron/frontend/src/components/` | SPLIT | Too technical-first; should trend toward feature grouping |
| `app/electron/frontend/src/lib/settingsSchema.ts` | MOVE | Settings logic should live under clearer config/features ownership |
| `app/electron/frontend/src/config/generated/` | GENERATED | Keep generated and separate from hand-authored config |

## Proposed Target Structure

### Backend

- `app/api/`
  - `routes/`
  - `schemas/`
  - `transport/`
- `app/domain/`
  - `settings/`
  - `models/`
  - `transcription/`
  - `audio/`
  - `sessions/`
  - `history/`
  - `coach/`
  - `dictionary/`
  - `snippets/`
  - `style/`
- `app/services/`
  - orchestration and use cases only
- `app/integrations/`
  - runtime adapters and external integrations
- `app/storage/`
  - persistence only
- `app/config/`
  - shared source-of-truth config and codegen inputs

### Electron

- `app/electron/main/`
  - `windows/`
  - `ipc/`
  - `services/`
  - `state/`
  - `contracts/`
- `app/electron/shared/`
  - cross-shell contracts and theme tokens only
- `app/electron/strings/`
  - Electron-only strings

### Renderer

- `app/electron/frontend/src/`
  - `pages/`
  - `features/`
  - `components/ui/`
  - `hooks/`
  - `state/`
  - `api/`
  - `config/`
  - `strings/`

## Ordered Migration Plan

1. Create reusable repo skills and discovery docs first.
2. Tighten naming and ownership without changing behavior.
3. Audit and consolidate config/constants/text source-of-truth.
4. Clarify generated vs authored config outputs.
5. Centralize shared contracts at runtime boundaries.
6. Consolidate settings ownership end-to-end.
7. Re-home API non-transport modules gradually with compatibility shims.
8. Reorganize renderer by feature ownership.
9. Clarify Electron shared vs main-shared ownership.
10. Separate dictation and system-audio runtime ownership more explicitly.
11. Remove only proven dead or redundant files.
12. Update architecture and ownership docs after each structural wave.

## Purely Structural Vs Behavior-Changing

### Purely structural

- Adding docs and skills
- Renaming files with compatibility shims
- Moving modules without changing logic
- Grouping files by ownership
- Marking generated outputs clearly
- Tightening ownership docs

### Behavior-changing and high-risk

- Settings precedence changes
- Payload or IPC shape changes
- Model selection fallback changes
- Capture-source routing changes
- Hotkey final-text source changes
- Refiner/cleanup sequencing changes
- History/session persistence identity changes
- Floating-window runtime behavior changes