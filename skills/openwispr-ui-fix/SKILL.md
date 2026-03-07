---
name: openwispr-ui-fix
description: Use when fixing OpenWispr renderer or Electron UI behavior. Covers string ownership, floating window behavior, quick settings, page/feature ownership, and renderer contract-safe validation.
---

# OpenWispr UI Fix

Use this skill for renderer and Electron UI fixes.

## Ownership Rules

- Renderer copy belongs in `app/electron/frontend/src/strings/en.ts`
- Electron shell copy belongs in `app/electron/strings/en.js`
- Shared theme tokens should come from Electron shared theme/token sources

## Focus Areas

- `app/electron/frontend/src/`
- `app/electron/main/windows/`
- `app/electron/main/ipc/`
- `app/electron/shared/`
- floating window HTML/preload/main wiring
- quick settings window wiring

## Checks

- Is the control wired to real behavior?
- Is the copy externalized correctly?
- Is page/feature ownership obvious?
- Does the change cross preload/main/renderer boundaries?
- Does floating-window behavior still satisfy the AGENTS checklist?

## Validation

- `python tools/check_renderer_strings.py`
- `pnpm run typecheck`
- focused renderer tests for changed components
- Electron-side tests when preload or main-window code changes

## Rules

- Do not hardcode user-facing copy inline.
- Do not regress floating-window timer, waveform, scroll, or finish/cancel behavior.
- Do not add a parallel theme source.
