---
name: openwispr-safe-refactor
description: Use when moving, renaming, splitting, or consolidating OpenWispr code without changing behavior. Focuses on compatibility shims, boundary preservation, generated-file awareness, and targeted validation order.
---

# OpenWispr Safe Refactor

Use this skill for structural cleanup work.

## Goal

Improve ownership and navigability without breaking backend, Electron, renderer, settings migration, or runtime behavior.

## Workflow

1. Read `AGENTS.md`.
2. Map the current owner and destination owner for the code being moved.
3. Classify the change:
   - rename
   - move
   - split
   - merge
   - delete
4. Keep runtime behavior stable with compatibility imports or re-exports when needed.
5. Update imports and references in the same batch.
6. Run the smallest relevant validation set.

## High-Risk Areas

- settings schema/defaults/migrations/sync
- generated config outputs
- SSE/WebSocket payloads
- Electron preload/main/renderer contracts
- hotkey final transcript flow
- audio backend selection and capture source routing
- model preload/download semantics
- floating window lifecycle

## Validation Order

- import/reference verification
- targeted unit or integration tests
- `python tools/check_renderer_strings.py` if renderer strings or UI files changed
- `pnpm run typecheck` if renderer/frontend contracts changed
- targeted backend validation if Python service modules moved

## Rules

- One coherent structural improvement per batch.
- Do not combine folder cleanup with behavior changes.
- Keep generated files generated.
- When deleting, prove no imports, runtime refs, test refs, docs refs, or generated dependencies first.
