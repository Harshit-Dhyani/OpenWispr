---
name: openwispr-release-validation
description: Use when validating OpenWispr changes before merge or release. Covers typecheck, targeted tests, renderer string validation, runtime smoke checks, and packaging/release command sanity.
---

# OpenWispr Release Validation

Use this skill before merge and before packaging-sensitive changes.

## Primary Commands

- `pnpm run typecheck`
- `pnpm run test:frontend`
- `pytest`
- `python tools/check_renderer_strings.py`
- `python scripts/validate.py --quick`

## Packaging And Release References

- `package.json`
- `scripts/build.py`
- `app/electron/package.json`
- `tools/runner.py`

## Validation Matrix

- Renderer/UI change:
  - typecheck
  - focused renderer tests
  - renderer strings check
- Backend/service change:
  - focused pytest targets
  - runtime or integration smoke validation
- Structural move:
  - import/reference verification
  - smallest relevant test set
- Build/release change:
  - package/build script sanity
  - artifact-related smoke checks

## Rules

- Run the smallest relevant checks, not a blind full suite by default.
- If a changed area is hotkey/session/model-download related, validate the specific flow in logs or smoke tests.
- Report what was not validated.
