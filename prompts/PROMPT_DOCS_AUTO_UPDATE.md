# Docs Auto-Update Agent Prompt

Copy and paste this entire prompt to an AI assistant to automatically update all OpenWispr documentation.

---

## YOUR MISSION

You are the **Docs Auto-Update Agent**. Update ALL OpenWispr documentation to match the current codebase state. Do not stop until every doc is verified against code.

---

## STEP 1: INITIAL VERIFICATION

Run the docs verification script:
```bash
python tools/ci/verify-docs.py
```

If it passes, great. If not, note the errors - you'll fix them.

---

## STEP 2: DISCOVER CURRENT STATE

### 2.1 List All Existing Docs
```bash
find docs -name "*.md" -type f | sort
```

Read `docs/_inventory.yml` to understand the registry.

### 2.2 List Key Source Files
```bash
ls app/api/server.py
ls app/core/settings_manager.py
ls app/core/model_catalog.py
ls app/stt/streaming_engine.py
ls app/electron/main/preload.js
ls app/api/websocket_server.py
```

---

## STEP 3: UPDATE GENERATED SECTIONS

These sections are auto-generated from code. You MUST regenerate them.

### 3.1 API Endpoints

Check if API docs need updating:
```bash
python tools/ci/generate-api-docs.py --check
```

If exit code != 0, regenerate:
```bash
python tools/ci/generate-api-docs.py > /tmp/api-generated.md
```

Then update `docs/api/endpoints.md`:
- Find the markers: `<!-- GENERATED: api-routes -->` and `<!-- END GENERATED -->`
- Replace content between them with the generated output
- Update `last_verified: YYYY-MM-DD` in frontmatter to today's date

### 3.2 Settings Schema

Check if settings docs need updating:
```bash
python tools/ci/generate-settings-docs.py --check
```

If exit code != 0, regenerate:
```bash
python tools/ci/generate-settings-docs.py > /tmp/settings-generated.md
```

Then update `docs/reference/config.md`:
- Find the markers: `<!-- GENERATED: settings-schema -->` and `<!-- END GENERATED -->`
- Replace content between them with the generated output
- Update `last_verified` date in frontmatter

---

## STEP 4: VERIFY & UPDATE EACH DOC

For EACH doc file, read it and verify against source code:

### 4.1 docs/api/endpoints.md
**Source of truth:** `app/api/server.py`, `app/api/websocket_server.py`

Verify:
- [ ] All REST routes listed match @app decorators in server.py
- [ ] All WebSocket endpoints match @app.websocket decorators
- [ ] All SSE endpoints match StreamingResponse routes
- [ ] Request/response models match code

Update if mismatches found.

### 4.2 docs/reference/config.md
**Source of truth:** `app/core/settings_manager.py`, `app/config/settings.py`

Verify:
- [ ] All settings categories listed (general, transcription, audio, hotkey, coach, refiner, advanced)
- [ ] All fields match SettingsState dataclass
- [ ] Default values match code
- [ ] Types match code annotations

### 4.3 docs/engineering/dictation-pipeline.md
**Source of truth:** `app/stt/streaming_engine.py`, `app/stt/utterance_aggregator.py`, `app/stt/quality.py`

Verify:
- [ ] StreamingConfig values (window_ms, overlap_ms) match code
- [ ] Latency targets match (WISPR: 200ms, SYSTEM: 1000ms)
- [ ] Classes mentioned exist: DualModeTranscriptionEngine, StreamingInferenceEngine, AdaptiveBeamController
- [ ] Configuration options match actual code

### 4.4 docs/engineering/settings.md
**Source of truth:** `app/core/settings_manager.py`, `app/api/settings_sync.py`

Verify:
- [ ] Settings categories match code
- [ ] Sync protocol description matches settings_sync.py
- [ ] Migration flow matches settings_migrations.py
- [ ] All settings fields documented

### 4.5 docs/engineering/model-runtime.md
**Source of truth:** `app/core/model_catalog.py`, `app/api/model_service.py`, `app/stt/model_pool.py`

Verify:
- [ ] All ASR models listed match MODEL_CATALOG
- [ ] All refiner models listed match MODEL_CATALOG
- [ ] VRAM requirements match catalog
- [ ] Hardware recommendations match SystemProfiler logic

### 4.6 docs/engineering/architecture-overview.md
**Source of truth:** `app/electron/main/index.js`, `app/electron/main/main.js`

Verify:
- [ ] Window dimensions match code
- [ ] Startup flow matches main/index.js
- [ ] IPC channel categories match actual handlers
- [ ] Global shortcuts match registered accelerators

### 4.7 docs/engineering/architecture-electron-backend-contract.md
**Source of truth:** `app/electron/main/preload.js`, `app/api/server.py`, `app/api/websocket_server.py`

Verify:
- [ ] Port (8765) matches code
- [ ] IPC channels match preload.js exposed APIs
- [ ] HTTP endpoints match server.py
- [ ] WebSocket endpoints match code
- [ ] MessageType enum matches websocket_server.py

### 4.8 docs/engineering/events-streaming.md
**Source of truth:** `app/api/websocket_server.py`, hooks in `app/electron/frontend/src/hooks/`

Verify:
- [ ] SSE endpoints match server.py
- [ ] WebSocket endpoints match server.py
- [ ] MessageType enum documented completely
- [ ] Reconnect strategy matches hook implementation
- [ ] useEventSource and useWebSocket APIs match code

### 4.9 docs/engineering/audio-capture.md
**Source of truth:** `app/audio/capture.py`, `app/audio/backends/`, `app/audio/devices.py`

Verify:
- [ ] Backend classes match code (PyAudioWasapiBackend, SoundcardBackend)
- [ ] LoopbackAudioSource configuration matches
- [ ] Device enumeration matches devices.py
- [ ] Error handling patterns match code

### 4.10 docs/engineering/english-coach.md
**Source of truth:** `app/api/coach_service.py`, `app/api/coach_cache.py`, `app/config/coach_prompts.py`

Verify:
- [ ] Coach endpoints match server.py routes
- [ ] Cache keying strategy matches coach_cache.py
- [ ] Prompt templates match coach_prompts.py
- [ ] Settings match SettingsManager coach section

### 4.11 docs/engineering/security.md
**Source of truth:** `app/electron/main/preload.js` (for IPC security)

Verify:
- [ ] Threat model still accurate
- [ ] IPC security section matches contextBridge usage
- [ ] Security audit findings status table up to date

### 4.12 docs/engineering/performance.md
**Source of truth:** `app/core/performance_monitor.py`, `app/stt/streaming_engine.py`

Verify:
- [ ] Tunable parameters match code
- [ ] AdaptiveBeamController logic matches
- [ ] VAD settings match
- [ ] Profiling hooks documented

### 4.13 docs/engineering/latency-playbook.md
**Source of truth:** AGENTS.md known issues, troubleshooting patterns

Verify:
- [ ] Diagnostic commands still work
- [ ] Quick fixes match current architecture
- [ ] Common scenarios cover actual user issues

### 4.14 docs/engineering/testing.md
**Source of truth:** `tests/`, `e2e/`, `app/electron/frontend/src/components/__tests__/`

Verify:
- [ ] Test commands match package.json and pyproject.toml
- [ ] Fixture list matches conftest.py
- [ ] Test patterns match actual test files

### 4.15 docs/engineering/contributing-docs.md
**Source of truth:** `docs/_style.md`

Verify:
- [ ] Frontmatter requirements match _style.md
- [ ] Code citation format matches spec
- [ ] Review checklist complete

### 4.16 docs/operations/OPERATIONS.md
**Source of truth:** `app/core/logging_utils.py`, `app/storage/session_store.py`, `app/api/streaming_metrics.py`

Verify:
- [ ] Log locations match code
- [ ] Session storage paths match session_store.py
- [ ] Health endpoint response matches server.py
- [ ] Metrics endpoints exist

### 4.17 docs/troubleshooting.md
**Source of truth:** `app/core/error_handler.py`, `app/core/recovery_strategies.py`

Verify:
- [ ] Error categories match error_handler.py
- [ ] Recovery strategies match recovery_strategies.py
- [ ] Known issues from AGENTS.md included
- [ ] Format follows Symptom→Cause→Fix→Verify

### 4.18 docs/deployment/DEPLOYMENT.md
**Source of truth:** `package.json`, `pyproject.toml`

Verify:
- [ ] Commands match package.json scripts
- [ ] Python version matches pyproject.toml
- [ ] Node version matches requirements
- [ ] Environment variables match config.py

### 4.19 docs/project/project-structure.md
Verify all paths still exist. Update if directory structure changed.

### 4.20 docs/README.md
Verify all links work and point to existing files.

---

## STEP 5: ADD FRONTMATTER TO MISSING DOCS

If verification reports files missing frontmatter, add the required frontmatter block to each:

```yaml
---
title: Title
owner: docs/ux
audience: developers|operators|all|security
last_verified: YYYY-MM-DD
review_cadence: monthly|quarterly
source_of_truth:
  - list/of/source/files.py
critical: true|false
---
```

Files that need frontmatter (verify with verify-docs.py):
- docs/branding/brand-assets.md
- docs/engineering/folder-ownership.md
- docs/engineering/restructure-audit.md
- docs/engineering/restructure-discovery.md
- docs/engineering/settings-source-of-truth.md
- docs/project/folder-ownership.md

Set appropriate values for each based on the doc's content and purpose.

---

## STEP 6: UPDATE DATES

For every doc you modified, update the frontmatter:
```yaml
last_verified: YYYY-MM-DD  # Today's date
```

---

## STEP 7: UPDATE INVENTORY

Update `docs/_inventory.yml`:
1. Update `last_updated: YYYY-MM-DD` at top
2. For each doc you changed, update its `last_verified` date
3. Add any new docs that are not yet in the inventory:

### New docs to add to inventory:
- docs/branding/brand-assets.md
- docs/engineering/folder-ownership.md
- docs/engineering/restructure-audit.md
- docs/engineering/restructure-discovery.md
- docs/engineering/settings-source-of-truth.md
- docs/project/folder-ownership.md

For each new file, determine appropriate ownership, audience, source_of_truth, and critical status based on content.

---

## STEP 8: FINAL VERIFICATION

Run verification again:
```bash
python tools/ci/verify-docs.py
```

MUST PASS before you're done.

---

## STEP 9: GENERATE REPORT

Create `reports/docs-update-YYYY-MM-DD.md` with:

```markdown
# Docs Update Report - YYYY-MM-DD

## Summary
- Docs checked: N
- Docs updated: N
- Generated sections refreshed: N

## Changes Made

| File | Change Type | Source Evidence |
|------|-------------|-----------------|
| docs/api/endpoints.md | Regenerated API routes | server.py lines X-Y |
| ... | ... | ... |

## Verification Result
```
{paste verify-docs.py output}
```
```

---

## RULES

1. **NEVER guess** - If you can't verify from code, ask or flag for manual review
2. **Cite evidence** - Every change must reference: `file.py::ClassName` or `file.py:line-range`
3. **Preserve manual content** - Only update between GENERATED markers for auto-generated sections
4. **Update dates** - Change `last_verified` for every file you touch
5. **Minimal diffs** - Don't reformat unchanged content
6. **Stop on failure** - If verify-docs.py fails after your changes, fix before finishing

---

## DONE CRITERIA

- [ ] `python tools/ci/verify-docs.py` passes
- [ ] All generated sections match current code
- [ ] Every modified doc has updated `last_verified` date
- [ ] Report generated at `reports/docs-update-YYYY-MM-DD.md`
- [ ] All internal links valid
- [ ] No placeholder content - every section cites code

---

Execute all steps. Do not stop until done criteria are met.
