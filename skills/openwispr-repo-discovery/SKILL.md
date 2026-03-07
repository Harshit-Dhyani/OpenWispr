---
name: openwispr-repo-discovery
description: Use when mapping the OpenWispr codebase before changes. Covers entrypoints, backend/Electron/frontend boundaries, settings ownership, model/runtime flow, audio/transcription flow, sessions/history flow, generated config outputs, and duplicate ownership hotspots.
---

# OpenWispr Repo Discovery

Use this skill before any non-trivial change.

## Goal

Build a factual map of the repo before editing so cleanup and fixes follow the actual wiring instead of guessed paths.

## Discovery Targets

- Entry points:
  - `app/main.py`
  - `app/api_main.py`
  - `app/electron/main/index.js`
  - `package.json`
- Backend transport:
  - `app/api/routes/`
  - `app/api/server.py`
  - `app/api/websocket_server.py`
- Settings:
  - `app/config/settings.py`
  - `app/core/settings_manager.py`
  - `app/core/settings_migrations.py`
  - `app/core/settings_validator.py`
  - `app/api/settings_sync.py`
  - `app/api/routes/settings.py`
- Config/text/codegen:
  - `app/config/constants.py`
  - `app/config/text.py`
  - `app/config/generate_ts.py`
  - `app/electron/frontend/src/config/generated/`
- Runtime/model/audio/transcription:
  - `app/core/model_catalog.py`
  - `app/api/model_service.py`
  - `app/audio/`
  - `app/stt/`
- Session/history/hotkey:
  - `app/core/session_manager.py`
  - `app/core/system_session.py`
  - `app/core/hotkey_session.py`
  - `app/storage/`
- Electron/renderer:
  - `app/electron/main/`
  - `app/electron/shared/`
  - `app/electron/frontend/src/`

## Output Shape

Return:

- current architecture map
- major ownership problems
- duplicate or overlapping modules
- risky modules that should not be moved casually
- likely source-of-truth files

## Existing References

- `docs/engineering/architecture-overview.md`
- `docs/engineering/architecture-electron-backend-contract.md`
- `docs/engineering/settings.md`
- `docs/engineering/model-runtime.md`
- `docs/engineering/audio-capture.md`
- `docs/engineering/dictation-pipeline.md`
- `docs/engineering/events-streaming.md`
- `docs/engineering/restructure-audit.md`
- `docs/engineering/folder-ownership.md`

## Rules

- Read `AGENTS.md` first.
- Prefer PowerShell-native inspection if `rg` is unavailable.
- Treat docs as references, not source of truth.
- Call out generated files separately from authoritative sources.
- Distinguish verified wiring from inferred ownership.
