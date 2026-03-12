# Settings & Configuration Audit Report - 2026-03-08

## Verification Update - 2026-03-09
- Scope reviewed: `app/config/settings.py`, `app/config/constants.py`, `app/core/system_profiler.py`, `app/api/services/backend_service.py`, `app/electron/frontend/src/config/generated/settings.ts`, `app/electron/frontend/src/config/generated/constants.ts`
- Status counts for items verified in this pass: `completed=4`, `invalid=1`, `compatibility-retained=1`, `still-open=2`
- Validation: `pytest tests/test_report_verified_fixes_wave2.py -q`, `python -m py_compile app/config/constants.py app/core/system_profiler.py app/api/services/backend_service.py`

## Summary
22 settings/configuration issues found.

## P0 - Must Fix (8 issues)

### C0-1: Duplicate Settings - backend / audio_backend
- **Status**: completed (2026-03-09)
- **Evidence**: `backend` is now a hidden compatibility alias (`is_fake=True`); `audio_backend` remains the visible authoritative setting.
- **File**: app/config/settings.py
- **Lines**: 472-489
- **Code**:
```python
"backend": SettingDefinition(...),
"audio_backend": SettingDefinition(...),
```
- **Fix**: Remove one

### C0-2: Duplicate VAD Settings
- **File**: app/config/settings.py
- **Lines**: 243-250 vs 499-506
- **Code**:
```python
"vad_enabled": SettingDefinition(...)  # transcription
"vadEnabled": SettingDefinition(...)  # audio
```

### C0-3: Typo "transcripta"
- **Status**: invalid (2026-03-09)
- **Evidence**: the persisted key remains legacy for compatibility, but user-facing label/description already say `OpenWispr`; no public typo remained to fix in this pass.
- **File**: app/config/text.py
- **Lines**: 110,181
- **Code**: `"mute_transcripta_audio_during_dictation"`
- **Fix**: Change to "transcription"

### C0-4: Wrong Model Mapping
- **Status**: completed (2026-03-09)
- **Evidence**: `base` now maps to `whisper-base` in backend and generated frontend constants.
- **File**: app/config/constants.py
- **Line**: 85
- **Code**: `"base": "whisper-small"`
- **Fix**: Should be "whisper-base"

### C0-5: speed vs fast Inconsistency
- **File**: app/config/constants.py vs text.py
- **Code**: VALID_MODES uses "speed", text uses "fast"

### C0-6: recommended_quality_level Returns Invalid Values
- **Status**: completed (2026-03-09)
- **Evidence**: `app/core/system_profiler.py` now returns only `maximum|balanced|fast|low_memory`.
- **File**: app/core/system_profiler.py
- **Lines**: 91-100
- **Code**:
```python
return "high"  # Not in VALID_MODES!
return "low"   # Not in VALID_MODES!
```

### C0-7: Invalid execution_mode
- **File**: app/core/hotkey_session.py
- **Line**: 813
- **Code**: `execution_mode="fast"` (not valid)

### C0-8: Missing "ultra" in Live Modes
- **Status**: completed (2026-03-09)
- **Evidence**: `app/api/services/backend_service.py` snapshot now includes `ultra`.
- **File**: app/api/services/backend_service.py
- **Line**: 131
- **Code**: `available_live_modes=["realtime", ...]` missing "ultra"

## P1 - Should Fix (4 issues)

### C1-1: style_default_profile Default Mismatch
- **File**: app/config/settings.py:888 - empty string
- **File**: app/electron/frontend/src/config/settingsSchema.ts:281 - "casual"

### C1-2: vad_min_silence_ms Default Mismatch
- **File**: app/config/settings.py:267 - 200
- **File**: app/config/constants.py:54 - 300

### C1-3: Floating Point Precision
- **File**: app/electron/frontend/src/config/generated/settings.ts:670
- **Code**: `0.19999999999999998` (should be 0.2)

### C1-4: Fake Settings in UI
- **File**: app/config/settings.py
- **Settings**: showNotifications, minimizeToTray, startupWithSystem, noiseFiltering, echoCancellation, autoGainControl, max_workers, use_parallel_processing, preload_model, patience, experimentalStem, experimentalGpuAccel
- **Fix**: Hide or implement

## P2 - Nice to Have (4 issues)

### C2-1: Legacy .transcripta Directory
- **Files**: app/api/server.py:2155, app/core/recovery_strategies.py:489,760-761

### C2-2: FAKE_SETTINGS Duplication
- **File**: app/config/settings.py:47-66

### C2-3: Missing SETTING_LABELS Entry
- **File**: app/config/text.py:174 - default_capture_source

### C2-4: captureMode vs default_capture_source
- **File**: app/config/settings.py:446-463

## Quick Wins
1. Remove duplicate backend setting
2. Fix "transcripta" typo
3. Fix model mapping
4. Align defaults

## Done-When
- [ ] All P0 fixed
