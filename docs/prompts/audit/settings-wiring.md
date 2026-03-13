# Settings Wiring Audit

Use this prompt to audit settings flow across the entire application stack.

---

## MISSION

Trace settings from definition to consumption. Identify drift, duplication, and contract mismatches between:
- Backend settings registry (`app/config/settings.py`)
- Settings manager (`app/core/settings_manager.py`)
- API endpoints (`app/api/settings_sync.py`)
- Electron main process
- Frontend generated types and defaults

## SOURCE OF TRUTH

- **Definition**: `app/config/settings.py` - The authoritative settings registry
- **Runtime**: `app/core/settings_manager.py` - Settings loading, validation, migration
- **Transport**: `app/api/settings_sync.py` - Backend-to-Electron sync protocol

## AUDIT CHECKLIST

### 1. Settings Definition (`app/config/settings.py`)
- [ ] All settings have explicit types
- [ ] All settings have defaults
- [ ] No `is_fake: true` settings without implementation
- [ ] Settings grouped by category (general, transcription, audio, hotkey, coach, refiner, advanced)

### 2. Settings Manager (`app/core/settings_manager.py`)
- [ ] Loads all settings from `app/config/settings.py`
- [ ] Handles migrations correctly
- [ ] Validates incoming values
- [ ] Emits change events properly

### 3. Frontend Generation
- [ ] Generated types match backend exactly
- [ ] Generated defaults match backend defaults
- [ ] Run: Check if `app/electron/frontend/src/config/generated/` is up to date

### 4. Electron IPC
- [ ] All settings exposed via IPC are in registry
- [ ] No hardcoded defaults in renderer
- [ ] Frontend doesn't bypass IPC for settings

### 5. API Contract (`app/api/settings_sync.py`)
- [ ] All backend settings exposed to frontend
- [ ] No extra settings not in registry
- [ ] Type serialization matches

### 6. Usage in Code
- [ ] No `getattr(settings, ...)` with string keys
- [ ] No duplicate default definitions
- [ ] No settings imported directly from wrong module

## COMMON ISSUES TO FIND

1. **Frontend drift** - Frontend has hardcoded default that differs from backend
2. **Missing sync** - Setting exists in backend but not exposed to frontend
3. **Fake settings** - Setting marked `is_five: true` but appears in UI
4. **Type mismatch** - Backend sends number, frontend expects string
5. **Migration gaps** - Setting removed but migration not created

## VERIFICATION STEPS

1. Compare `app/config/settings.py` with `app/electron/frontend/src/config/generated/settings.ts`
2. Trace one setting end-to-end: definition → manager → API → frontend
3. Check for `is_fake` markers in settings and verify implementation status
4. Search for hardcoded defaults: `grep -r "default.*=" --include="*.ts" app/electron/frontend/src/`

## OUTPUT FORMAT

Create `reports/settings-wiring-audit-YYYY-MM-DD.md`:

```markdown
# Settings Wiring Audit - YYYY-MM-DD

## Summary

## Findings

### P0: Must Fix
- [Finding]: Evidence, impact, fix

### P1: Should Fix
- [Finding]: Evidence, impact, fix

### P2: Nice to Have
- [Finding]: Evidence, impact, fix

## Verification
- [ ] All settings traced end-to-end
- [ ] No hardcoded defaults found
- [ ] Generated files match source
```

## DONE CRITERIA

- [ ] Every setting in registry traced to frontend consumption
- [ ] No fake or unimplemented settings visible in UI
- [ ] Generated frontend config matches backend exactly
- [ ] Report created in `reports/`
