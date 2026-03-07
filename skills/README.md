# OpenWispr Repo Skills

These skills standardize repeat engineering tasks in this repo.

## Core Skills

- `openwispr-repo-discovery`: map entrypoints, ownership, boundaries, generated outputs, and duplication before edits.
- `openwispr-safe-refactor`: run behavior-safe move/rename/split workflow with compatibility shims and targeted validation.
- `openwispr-settings-wiring-check`: audit settings schema/defaults/migrations/validator/API/UI/generated metadata drift.
- `openwispr-ui-fix`: fix renderer/Electron UI wiring while preserving string ownership and floating-window behavior.
- `openwispr-runtime-debug`: debug model/audio/transcription/session runtime issues with focused diagnostics.
- `openwispr-release-validation`: run smallest relevant pre-merge and pre-release verification matrix.
- `openwispr-agents-memory`: append verified prevention rules to `AGENTS.md` using strict failure-entry format.

## Execution Rule

For non-trivial work, use skills in this order:

1. `openwispr-repo-discovery`
2. one or more task-specific skills (`safe-refactor`, `settings-wiring-check`, `ui-fix`, `runtime-debug`)
3. `openwispr-release-validation`
4. `openwispr-agents-memory` when a verified bug/regression/root cause is found

## Non-Goals

- Skills do not replace source-of-truth ownership in `app/config/*`.
- Skills do not authorize behavior changes without explicit validation.
- Skills do not permit hand-maintained duplicates of generated settings/config/text outputs.
