---
name: openwispr-audit
description: Guide agents through systematic repo audits to assess codebase health, find bugs, and identify architectural issues.
---

# OpenWispr Audit Skill

## Purpose

Provide systematic guidance for performing comprehensive repo audits to assess codebase health, discover bugs, identify architectural drift, and verify implementation against documented contracts.

## When to Use

- Assessing overall codebase health
- Finding bugs or regressions
- Identifying architectural issues
- Verifying settings/model/runtime wiring
- Checking cross-layer contract consistency
- Before major refactors
- After significant feature additions

## When NOT to Use

- Small targeted fixes (use specific skills like openwispr-test-for-bug-fix)
- Documentation-only changes
- Single-file changes with known impact
- Quick hotfixes in well-understood areas

## Discovery Steps

### 1. Inspect Actual Entry Points

- Backend: `app/main.py`, `app/api_main.py`, `app/api/server.py`
- Electron: `app/electron/main/index.js`
- Frontend: `app/electron/frontend/src/`
- Package: `package.json`

### 2. Identify Actual Settings Source-of-Truth

- Settings registry: `app/config/settings.py`
- Runtime settings: `app/core/settings/config.py`
- Settings migrations: `app/core/settings_migrations.py`
- Settings validator: `app/core/settings_validator.py`
- Frontend generated config: `app/electron/frontend/src/config/generated/`

### 3. Check Actual Model Routing Flow

- Model catalog: `app/core/model_catalog.py`
- Model service: `app/api/model_service.py`
- STT modules: `app/stt/`
- Audio pipeline: `app/audio/`
- Verify source-specific routing (microphone vs system audio)

### 4. Verify Actual Test Commands

- Check `pytest.ini`, `pyproject.toml`, or `setup.cfg` for test config
- Check `package.json` for frontend tests
- Look for `tests/` directory structure
- Verify lint/typecheck commands in `AGENTS.md` or `package.json`

### 5. Inspect Cross-Layer Contracts

- API routes: `app/api/routes/`
- WebSocket server: `app/api/websocket_server.py`
- Electron IPC: `app/electron/shared/`
- Event streaming: SSE and WebSocket payloads
- Settings sync: `app/api/settings_sync.py`

### 6. Check Audio/Transcription Pipeline

- Audio sources: `app/audio/`
- STT engines: `app/stt/`
- Session management: `app/core/session_manager.py`, `app/core/hotkey_session.py`
- History storage: `app/storage/`

## Verification Requirements

### Python Changes

- Run `python -m py_compile` on modified Python files
- Run settings generation if applicable: `python -m app.config.generate_ts`
- Run relevant tests: `pytest tests/ -v` or specific test files
- Check for import errors in modified modules

### Settings/Config Changes

- Verify backend registry in `app/config/settings.py`
- Verify generated frontend config in `app/electron/frontend/src/config/generated/`
- Check renderer consumers are updated
- Run settings wiring tests if available

### Frontend/Electron Changes

- Run frontend build if applicable
- Verify IPC contract consistency
- Check for TypeScript errors

### Cross-Layer Changes

- Verify producer and consumer contracts together
- Test runtime behavior end-to-end when possible
- Check event payload consistency

## Common Failure Patterns

### Trusting Docs Over Code

- Documentation may be stale or inaccurate
- Always verify against actual implementation
- Check `AGENTS.md` for authoritative sources
- Generated docs are outputs, not source of truth

### Not Verifying Runtime Behavior

- Code may compile but not work at runtime
- Run relevant tests before marking complete
- Check actual execution paths, not just static analysis
- Verify error handling and edge cases

### Missing Cross-Layer Verification

- Settings changes require backend + frontend + runtime verification
- API changes require route + service + client verification
- Model changes require catalog + routing + execution verification
- Don't assume changes work without testing actual flows

### Hardcoded Values

- Language values (e.g., "hi", "en") should come from settings
- Model names should come from catalog/settings
- Paths should be configurable, not hardcoded
- Check for magic strings/numbers in transcription code

### Incomplete Migration

- Settings name changes require migration logic
- Database schema changes require migration
- API breaking changes require version handling
- Check `app/core/settings_manager.py` for migration patterns

## Audit Output Shape

Return:

- Summary of findings (bugs, architectural issues, wiring problems)
- Specific files affected with line numbers
- Recommended fixes with priority
- Verification steps taken
- Areas that need further investigation

## Reference Files

- `AGENTS.md` - Primary guidance for all changes
- `docs/engineering/architecture-overview.md`
- `docs/engineering/settings.md`
- `docs/engineering/model-runtime.md`
- `.codex/AUDIT_REPORT.md` - Previous audit findings
