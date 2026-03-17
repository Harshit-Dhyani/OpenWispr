# OpenWispr Settings Wiring Check

## Purpose
Verify that settings flow correctly from backend to frontend through the generated config pipeline.

## When to Use
- After modifying settings in `app/config/settings.py`
- When frontend settings appear out of sync
- When adding new settings
- When debugging settings-related bugs

## When NOT to Use
- For unrelated UI changes
- When only changing non-settings UI strings
- For backend logic changes that don't affect settings

## Discovery Steps
1. Verify settings exist in `app/config/settings.py`
2. Check generated TypeScript: `Get-ChildItem -Path app/electron/frontend/src/config/generated/`
3. Compare backend setting names with frontend generated config
4. Verify frontend component imports from generated config
5. Check settings validation in `app/config/`

## Verification Requirements
- Backend settings must have corresponding entries in generated frontend config
- Frontend components must import from generated config, not hardcode values
- Settings changes must regenerate TypeScript config
- All settings must have proper defaults and validation

## Common Failure Patterns
- Adding settings without regenerating TypeScript
- Hardcoding settings values in frontend components
- Mismatched setting names between backend and frontend (snake_case vs camelCase)
- Missing validation for new settings
- Settings marked `is_fake: true` that aren't hidden or implemented

## Safe Edit Rules
- Always regenerate TypeScript after Python settings changes
- Use snake_case in backend, expect camelCase in frontend
- Never hardcode settings values - import from generated config
- Run `python -m py_compile` on modified Python files
- Run TypeScript build after settings changes
