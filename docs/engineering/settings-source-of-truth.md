# Settings Source Of Truth

This document records the current OpenWispr settings ownership so future cleanup can reduce drift safely.

## Authoritative Source Candidates

- Registry and defaults: `app/config/settings.py`
- Runtime persistence and normalization: `app/core/settings_manager.py`
- Migrations: `app/core/settings_migrations.py`
- Validation: `app/core/settings_validator.py`
- API exposure and sync: `app/api/routes/settings.py`, `app/api/settings_sync.py`
- TS codegen source: `app/config/generate_ts.py`
- Generated frontend metadata: `app/electron/frontend/src/config/generated/settings.ts`

## Drift Risks

- `app/electron/frontend/src/lib/settingsSchema.ts` also defines defaults and validation concepts.
- Renderer settings sections consume settings through multiple paths, including generated config, local schema, context, and top-level app orchestration.
- Changes to backend registry fields can drift if generated outputs and handwritten renderer consumers are not checked together.

## Current Rule

- Treat `app/config/settings.py` as the leading schema/default registry unless code proves a different source is authoritative.
- If Python-side settings metadata changes, regenerate or update frontend generated outputs in the same change.
- Any handwritten frontend settings schema that diverges from generated metadata must be explicitly justified and reviewed as a risk.