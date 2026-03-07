---
name: openwispr-settings-wiring-check
description: Use when auditing or fixing OpenWispr settings wiring. Covers schema/defaults, migrations, validator, persistence, API sync, generated frontend metadata, settings UI sections, and detection of ignored or misleading settings.
---

# OpenWispr Settings Wiring Check

Use this skill whenever a change touches settings.

## Files To Inspect

- `app/config/settings.py`
- `app/core/settings_manager.py`
- `app/core/settings_migrations.py`
- `app/core/settings_validator.py`
- `app/api/routes/settings.py`
- `app/api/settings_sync.py`
- `app/electron/frontend/src/config/generated/settings.ts`
- `app/electron/frontend/src/lib/settingsSchema.ts`
- renderer settings components and sections
- `docs/engineering/settings.md`

## Audit Questions

- What is the authoritative schema/default source?
- Are defaults, validator rules, and migrations aligned?
- Does API shape match frontend expectations?
- Are generated settings outputs up to date?
- Does each visible control affect real behavior?
- Are any settings ignored, partially wired, misleading, or dev-only-but-visible?

## Output

Return:

- source of truth
- duplicated ownership points
- broken or weak wiring
- exact files that must change together
- smallest validation mix to confirm the wiring

## Rules

- Do not silently change settings precedence.
- Preserve migrations.
- Keep visible controls behavior-backed.
- If Python-side settings metadata changes, regenerate or update frontend generated outputs in the same change.
