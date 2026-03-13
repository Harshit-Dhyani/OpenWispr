# Full Repository Audit

Use this prompt to perform a comprehensive audit of the OpenWispr codebase.

---

## MISSION

Perform a discovery-first, whole-project audit. Generate high-value Markdown audit files in `reports/` that improve quality, security, performance, and correctness.

## CRITICAL RULES

1. **Discovery first** - Inspect before writing. Never assume architecture.
2. **No shallow grep** - Read representative files across ALL major areas.
3. **Evidence-based** - Cite exact file paths and line numbers.
4. **Separate facts from hypotheses** - Label uncertain findings clearly.
5. **No fluff** - No marketing language, no generic advice.

## REPO CONTEXT TO INSPECT

```
app/api/           # FastAPI server, routes, WebSocket
app/audio/         # Audio capture, backends, devices
app/config/        # Settings definitions, defaults
app/core/          # Settings manager, model catalog, performance
app/electron/      # Main process, preload, IPC handlers
app/stt/           # Streaming engine, aggregation, quality
app/storage/       # Session store, history
tests/             # Python unit/integration tests
e2e/               # End-to-end tests
tools/             # CI scripts, verification tools
```

## AUDIT AREAS

### 1. Backend/API (`app/api/`)
- Request handling, validation, serialization
- Route consistency, error handling
- WebSocket/SSE contracts

### 2. Settings/Config (`app/config/`, `app/core/`)
- `app/config/settings.py` - Source of truth
- `app/core/settings_manager.py` - Runtime management
- Duplication, migration drift, frontend/backend mismatch

### 3. Electron (`app/electron/`)
- `app/electron/main/` - Main process
- `app/electron/main/preload.js` - IPC exposure
- Preload security, contextBridge usage
- IPC channel naming, event flow

### 4. Frontend (`app/electron/frontend/src/`)
- Duplicated logic, stale contracts
- Settings drift from backend
- Weak typing, dead components

### 5. Audio/STT/Runtime (`app/stt/`, `app/audio/`)
- Queueing, buffering, fallback behavior
- Model routing (microphone vs system audio)
- Performance assumptions, error recovery

### 6. Storage (`app/storage/`)
- Session persistence
- History management

### 7. Tests (`tests/`, `e2e/`)
- Missing coverage areas
- Contract drift, weak assertions

### 8. Documentation (`docs/`, existing reports)
- Source-of-truth drift
- Duplication, contradictions

## OUTPUT REQUIREMENTS

For each finding, include:
- **What** - Specific issue description
- **Where** - Exact file path and line numbers
- **Why** - Impact and risk
- **Fix** - Smallest safe remediation
- **Verify** - How to confirm the fix

## SEVERITY LEVELS

- **P0** - Must fix (security, data loss, crashes)
- **P1** - Should fix (correctness, performance)
- **P2** - Nice to have (maintainability, cleanup)

## REQUIRED OUTPUT

1. Create/update Markdown files in `reports/`
2. Each report must have:
   - Summary
   - Scope
   - Evidence-based findings
   - Separated by severity
   - Quick wins section
   - Done-when criteria

## MASTER ROADMAP

If creating multiple reports, also create `reports/master-roadmap-YYYY-MM-DD.md` that:
- Summarizes all findings
- Deduplicates recommendations
- Orders by impact vs risk
- Suggests execution sequence

## VERIFICATION

Before submitting:
- [ ] All major subsystems audited at least once
- [ ] Every claim has file path evidence
- [ ] Findings separated from hypotheses
- [ ] Reports are actionable, not generic
- [ ] No duplication with existing reports
