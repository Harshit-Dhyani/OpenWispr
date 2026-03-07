---
name: openwispr-release-validation
description: Use when validating OpenWispr changes before merge or release. Covers typecheck, targeted tests, renderer string validation, runtime smoke checks, and packaging/release command sanity.
---

# OpenWispr Release Validation

Use this skill before merge and before packaging-sensitive changes.

## Validation Buckets

- Renderer/UI change:
  - `pnpm run typecheck`
  - focused renderer tests
  - `python tools/check_renderer_strings.py`
- Backend/service change:
  - focused `pytest` selection
  - runtime/integration smoke checks for touched routes/flows
- Structural move/rename/split:
  - import/reference verification
  - canonical + compatibility shim import checks
  - smallest relevant tests
- Build/release change:
  - package/build config sanity
  - packaging smoke checks

## Required References

- `package.json`
- `app/electron/package.json`
- `scripts/build.py`
- `scripts/validate.py`
- `tools/runner.py`

## Execution Rules

- Run the smallest relevant set, not a blind full suite.
- If you skip a check, state it explicitly in the result.
- For hotkey/session/model-download changes, include flow-specific runtime verification notes.
- For settings/config/text changes, include generated-output verification.
