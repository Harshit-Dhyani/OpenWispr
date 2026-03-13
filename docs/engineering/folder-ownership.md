---
title: Folder Ownership
owner: docs/ux
audience: developers
last_verified: 2026-03-08
review_cadence: quarterly
source_of_truth:
  - app/
  - docs/
critical: false
---

**⚠️ DEPRECATED:** This document duplicates content from `docs/project/folder-ownership.md`. 
The authoritative version is now maintained there. This file will be removed in a future release.

**Please use:** [Folder Ownership](../project/folder-ownership.md)

# Folder Ownership

This is the target ownership model for the gradual cleanup. It is a guide for where new code should go and how existing code should be migrated in small batches.

## Runtime Boundaries

### `app/api/`

Owns transport only:

- HTTP route handlers
- WebSocket/SSE transport
- request validation
- response encoding

Do not put durable business logic here.

### `app/services/`

Owns orchestration and use-case flow:

- coordinate domain logic
- call storage/integrations
- enforce workflow-level behavior

### `app/domain/`

Owns domain logic by concern:

- settings
- models
- transcription
- audio
- sessions
- history
- coach
- dictionary
- snippets
- style

### `app/integrations/`

Owns external/runtime adapters:

- model runtimes
- OS/audio integration
- backend-specific helpers

### `app/storage/`

Owns persistence only:

- databases
- file stores
- writers
- migrations tied to storage shape

### `app/config/`

Owns authoritative metadata and generation inputs:

- product metadata
- settings schema/defaults
- shared constants
- shared text
- code generation entrypoints

Generated outputs should derive from here and be clearly marked as generated.

## Electron Ownership

### `app/electron/main/`

Target structure:

- `windows/`
- `ipc/`
- `services/`
- `state/` or `contracts/`

### `app/electron/shared/`

Owns Electron-side shared contracts and theme tokens only.

### `app/electron/strings/`

Owns Electron shell strings only.

## Renderer Ownership

Within `app/electron/frontend/src/`:

- `pages/` for route/page shells
- `features/` for product areas
- `components/ui/` for reusable primitives
- `hooks/` for shared renderer hooks
- `state/` for renderer state containers
- `api/` for backend adapters
- `config/` for renderer configuration
- `strings/` for renderer copy

## String Ownership

- Renderer copy: `app/electron/frontend/src/strings/en.ts`
- Electron shell copy: `app/electron/strings/en.js`
- Backend API copy: `app/api/strings/en.py`
- Prompt text: `app/stt/prompts.py`

## Generated Files

- Treat `app/electron/frontend/src/config/generated/*` as generated outputs.
- Regenerate from Python-side authoritative config instead of editing manually.

## Migration Rules

- Use compatibility shims when moving runtime modules.
- Prefer one concern per cleanup batch.
- Separate transport, orchestration, domain logic, persistence, and generated outputs.
- Do not merge dictation and system-audio flows unless the shared behavior is concrete and proven.
