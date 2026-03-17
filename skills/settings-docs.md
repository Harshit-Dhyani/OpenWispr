# Settings Documentation Skill

## Purpose

Ensure settings documentation stays synchronized with code by documenting settings in the canonical locations, verifying wiring between backend and frontend, and catching drift before it causes issues.

Use this skill when:
- Adding new settings to `app/config/settings.py`
- Modifying existing setting definitions (labels, descriptions, defaults, bounds)
- Adding new setting text (labels, descriptions, tooltips) to `app/config/text.py`
- Regenerating frontend configuration with `python -m app.config.generate_ts`
- Documenting settings-related behavior in user-facing docs
- Performing settings wiring verification after code changes

## When NOT to Use

- Documenting general application features (use mkdocs/docs/ instead)
- Writing code behavior documentation (use docstrings in source files)
- Adding or modifying runtime Pydantic settings in `app/core/settings/config.py`
- Creating new API endpoint documentation (use docs/api/endpoints.md)

## Discovery Steps

1. **Find backend settings definitions**:
   - Primary: `app/config/settings.py` - contains `SettingDefinition` dataclass and `SETTINGS_REGISTRY`

2. **Find settings text definitions**:
   - `app/config/text.py` - contains all user-facing text

3. **Find generated frontend config**:
   - `app/electron/frontend/src/config/generated/settings.ts` - generated from settings.py
   - `app/electron/frontend/src/config/generated/text.ts` - generated from text.py

4. **Find settings wiring tests**:
   - `tests/test_settings_wiring.py`
   - `tests/test_settings_wiring_contract.py`

## Implementation Rules

1. **Settings must be defined in the registry first**: Add to `app/config/settings.py`
2. **Settings text must be in text.py**: Add labels to `SETTING_LABELS`, descriptions to `SETTING_DESCRIPTIONS`
3. **Generated files are output, never hand-edited**: Run `python -m app.config.generate_ts`
4. **Document what the setting actually does**: Description should describe current behavior
5. **Maintain fake settings list**: When a setting is fake, add to `FAKE_SETTINGS`

## Verification Steps

1. `python -m py_compile app/config/settings.py`
2. `python -m app.config.generate_ts`
3. `pytest tests/test_settings_wiring.py -v`
4. Check generated output for new settings
