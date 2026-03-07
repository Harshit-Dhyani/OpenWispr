# Folder Ownership

This is the working ownership guide for the restructure program. It is meant to reduce confusion when editing the repo during migration.

## Current Ownership

- `app/api/`
  - HTTP routes, some services, settings sync, model/runtime helpers, transport helpers
- `app/audio/`
  - audio capture and backend-specific runtime
- `app/config/`
  - shared product metadata, settings metadata, constants, text, TS generation
- `app/core/`
  - runtime orchestration, mode/session/settings managers, model catalog, recovery
- `app/storage/`
  - persistence and storage concerns
- `app/stt/`
  - speech-to-text engine, prompts, cleanup, chunking, aggregation
- `app/electron/main/`
  - Electron main process, IPC, windows, preloads, backend spawn
- `app/electron/shared/`
  - shared shell helpers and theme tokens
- `app/electron/frontend/src/`
  - renderer UI, config, hooks, API adapters, tests

## Target Ownership

- `app/config/`
  - authoritative source-of-truth for product metadata, settings registry, shared constants/text, and codegen inputs
- `app/api/`
  - transport only: routes, schemas, WebSocket/SSE/JSON helpers
- `app/services/`
  - orchestration and use-case coordination
- `app/domain/`
  - feature ownership and business logic by concern
- `app/integrations/`
  - OS/runtime/model/audio adapters
- `app/storage/`
  - persistence only
- `app/electron/main/`
  - windows, IPC, main-process services, state/contracts
- `app/electron/shared/`
  - shell-wide shared contracts and theme tokens
- `app/electron/frontend/src/features/`
  - renderer feature ownership

## Edit Rules During Migration

- Do not add new shared constants to `app/core/` if `app/config/` already owns them.
- Do not add user-facing renderer strings outside `app/electron/frontend/src/strings/en.ts`.
- Do not add Electron shell copy outside `app/electron/strings/en.js`.
- Do not hand-edit generated files under `app/electron/frontend/src/config/generated/`.
- Do not move settings migration, validator, or persistence code without a focused validation pass.
- Do not merge microphone dictation and system-audio session logic unless the shared abstraction is proven real.