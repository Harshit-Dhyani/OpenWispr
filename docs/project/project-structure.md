---
title: Project Structure
audience: developers
last_verified: 2026-03-08
source_of_truth:
  - app/
  - tests/
  - tools/
---

# Project Structure

This document outlines the organized project structure for OpenWispr.

## Directory Layout

```
OpenWispr/
├── app/                          # Python backend and Electron desktop app
│   ├── api/                      # FastAPI endpoints, WebSocket, SSE, services
│   │   ├── server.py             # Main API server entry
│   │   ├── service.py            # Core transcription service
│   │   ├── websocket_server.py   # WebSocket handler
│   │   ├── settings_sync.py      # Settings synchronization
│   │   ├── model_service.py      # Model management API
│   │   └── refinement_queue.py   # Async refinement pipeline
│   ├── audio/                    # Audio capture, VAD, chunking, pipelines
│   │   ├── capture.py            # Audio capture from devices
│   │   ├── devices.py            # Device enumeration and management
│   │   ├── vad_optimized.py      # Voice Activity Detection
│   │   ├── chunking.py           # Audio chunking logic
│   │   ├── pipeline_factory.py   # Pipeline creation
│   │   ├── system_pipeline.py    # System audio pipeline
│   │   └── wispr_pipeline.py     # Wispr audio pipeline
│   ├── config/                   # Shared constants and TypeScript generation
│   │   ├── constants.py          # Audio constants, model names
│   │   ├── text.py               # UI text strings
│   │   ├── settings.py           # Settings schema and defaults
│   │   ├── generate_ts.py        # TypeScript code generator
│   │   └── __init__.py           # Package exports
│   ├── core/                     # Settings, sessions, modes, logging, metrics
│   │   ├── settings_manager.py   # Settings persistence
│   │   ├── session_manager.py    # Session lifecycle
│   │   ├── mode_manager.py       # Transcription modes
│   │   ├── metrics.py            # Performance metrics
│   │   ├── error_handler.py      # Error handling
│   │   └── logging_utils.py      # Structured logging
│   ├── electron/                 # Electron desktop application
│   │   ├── main/                 # Main process (Node.js)
│   │   │   ├── index.js          # Entry point
│   │   │   ├── main.js           # Legacy entry (deprecated)
│   │   │   ├── preload.js        # Main window preload
│   │   │   ├── preload-floating.js
│   │   │   ├── preload-quick-settings.js
│   │   │   ├── model-download-manager.js
│   │   │   ├── config.js         # Main process config
│   │   │   ├── shared/           # Shared state
│   │   │   │   ├── state.js
│   │   │   │   └── generated/appMeta.js
│   │   │   ├── utils/            # API utilities
│   │   │   │   └── api.js
│   │   │   ├── windows/          # Window management
│   │   │   │   ├── mainWindow.js
│   │   │   │   ├── floatingWindow.js
│   │   │   │   ├── quickSettingsWindow.js
│   │   │   │   ├── tray.js
│   │   │   │   └── trayUtils.js
│   │   │   ├── ipc/              # IPC handlers
│   │   │   │   ├── handlers.js
│   │   │   │   └── hotkeyHandlers.js
│   │   │   └── services/         # Background services
│   │   │       ├── backendSpawn.js
│   │   │       └── textInjector.js
│   │   ├── frontend/             # React TypeScript UI
│   │   │   ├── src/
│   │   │   │   ├── components/   # React components
│   │   │   │   ├── hooks/        # Custom React hooks
│   │   │   │   ├── lib/          # Utility libraries
│   │   │   │   ├── config/       # Generated config imports
│   │   │   │   │   └── generated/# Auto-generated from Python
│   │   │   │   ├── context/      # React contexts
│   │   │   │   ├── services/     # API services
│   │   │   │   ├── types/        # TypeScript types
│   │   │   │   └── test/         # Test utilities
│   │   │   ├── package.json
│   │   │   ├── tsconfig.json
│   │   │   └── vite.config.ts
│   │   ├── renderer/dist/        # Built frontend (output)
│   │   ├── scripts/              # Build scripts
│   │   │   ├── dev.js
│   │   │   └── build-frontend.js
│   │   ├── package.json          # Electron package config
│   │   ├── floating-window.html
│   │   └── quick-settings.html
│   ├── stt/                      # Speech-to-text engines and chunkers
│   │   ├── engine.py             # Main STT engine
│   │   ├── fast_engine.py        # Optimized fast engine
│   │   ├── fast_whisper_backend.py
│   │   ├── chunker.py            # Standard chunker
│   │   ├── fast_chunker.py       # Optimized chunker
│   │   ├── model_pool.py         # Model caching
│   │   ├── quality.py            # Output quality filtering
│   │   └── stability.py          # Stability algorithms
│   ├── stem/                     # STEM formula extraction
│   │   ├── formula_extractor.py
│   │   ├── postprocess.py
│   │   └── unit_checker.py
│   ├── storage/                  # Session and document storage
│   │   ├── session_store.py      # Session metadata storage
│   │   └── document_store.py     # Document management
│   ├── ui/                       # Legacy Qt UI (PySide6)
│   │   ├── main_window.py
│   │   └── README.md
│   ├── main.py                   # Python entry point
│   └── api_main.py               # API-only entry point
├── docs/                         # Documentation
│   ├── api/                      # API documentation
│   ├── architecture/             # Design docs
│   ├── deployment/               # Deployment guides
│   ├── operations/               # Operations guides
│   ├── audits/                   # Security and performance audits
│   └── project/                  # Project documentation
├── tests/                        # Python test suite
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   ├── performance/              # Performance tests
│   ├── conftest.py               # Pytest configuration
│   └── README.md
├── e2e/                          # End-to-end tests (Playwright)
│   ├── test_system_mode.py
│   └── test_hotkey_mode.py
├── tools/                        # Development tools
│   ├── diagnostics/              # System diagnostics
│   ├── setup/                    # Setup scripts
│   ├── maintenance/              # Maintenance utilities
│   ├── ci/                       # CI verification
│   └── runner.py
├── scripts/                      # Build and release scripts
│   ├── build.py
│   ├── validate.py
│   ├── run-backend-dev.cjs
│   └── generate-tree.cjs
├── pyproject.toml                # Python project configuration
├── package.json                  # Root npm configuration
├── README.md                     # Main project README
└── LICENSE                       # License file
```

## Configuration Centralization

The `app/config/` directory provides a single source of truth for constants shared between Python and TypeScript.

### Usage

**Python:**
```python
from app.config import AudioConstants, MODEL_NAMES
from app.config.text import UI_TEXT
```

**TypeScript:**
```typescript
// Generated files in app/electron/frontend/src/config/generated/
import { AudioConstants, ModelNames } from '@/config/generated/constants';
import { UIText } from '@/config/generated/text';
```

### Regenerating TypeScript

```powershell
python app/config/generate_ts.py
```

Generated files are written to `app/electron/frontend/src/config/generated/`.

## Electron Main Process

The main process is organized into modules:

```
app/electron/main/
├── index.js                    # Entry point (use this)
├── main.js                     # Legacy monolithic entry (deprecated)
├── preload.js                  # Main window preload
├── preload-floating.js         # Floating window preload
├── preload-quick-settings.js   # Quick settings preload
├── model-download-manager.js   # Model download logic
├── config.js                   # Main process configuration
├── shared/
│   ├── state.js                # Shared state between modules
│   └── generated/appMeta.js    # Build metadata
├── utils/
│   └── api.js                  # Backend API communication
├── windows/
│   ├── mainWindow.js           # Main application window
│   ├── floatingWindow.js       # Floating transcription window
│   ├── quickSettingsWindow.js  # Quick settings panel
│   ├── tray.js                 # System tray icon
│   └── trayUtils.js            # Tray utilities
├── ipc/
│   ├── handlers.js             # IPC event handlers
│   └── hotkeyHandlers.js       # Global hotkey management
└── services/
    ├── backendSpawn.js         # Python backend process manager
    └── textInjector.js         # Text injection service
```

## UI Organization

**Primary UI (Electron):** `app/electron/`
- Modern React-based desktop application
- TypeScript with Vite build system
- Full feature parity with backend

**Legacy UI (Qt):** `app/ui/`
- PySide6-based fallback UI
- Kept for development/debugging
- See `app/ui/README.md` for details

## Build Output Locations

- **Frontend build:** `app/electron/renderer/dist/`
- **Electron dist:** `app/electron/dist/`
- **Release artifacts:** `release/` (at root)
- **Session data:** `sessions/` (created at runtime)

## Key Configuration Files

- `pyproject.toml` - Python dependencies and project metadata
- `package.json` (root) - Root npm scripts and electron-builder config
- `app/electron/package.json` - Electron-specific dependencies
- `app/electron/frontend/package.json` - Frontend dependencies
- `app/electron/frontend/vite.config.ts` - Vite build configuration
- `app/electron/frontend/tsconfig.json` - TypeScript configuration

## Verification Commands

### Python Backend
```powershell
# Run Python tests
pytest

# Check Python imports
python -c "from app.config import AudioConstants; print(AudioConstants.DEFAULT_SAMPLE_RATE)"
```

### TypeScript Generation
```powershell
# Regenerate TypeScript from Python
python app/config/generate_ts.py
```

### Frontend
```powershell
# Install frontend dependencies
npm --prefix app/electron/frontend install

# Build frontend
npm --prefix app/electron/frontend run build

# Run frontend tests
npm --prefix app/electron/frontend run test

# Run frontend linter
npm --prefix app/electron/frontend run lint
```

### Electron
```powershell
# Development mode (backend + electron)
npm run dev

# Build for production
npm run build

# Create distribution
npm run dist
```

### Full Verification
```powershell
# Run all tests
npm run test

# Run linting
npm run lint

# Build everything
npm run build:production
```

## Maintenance

When adding new shared constants:

1. Add to `app/config/constants.py` or `app/config/text.py`
2. Run `python app/config/generate_ts.py`
3. Import from `@/config/generated/` in TypeScript code

## Architecture Notes

- **Backend:** FastAPI with WebSocket and SSE support
- **Audio:** Supports system audio and microphone capture
- **STT:** Faster-Whisper based with model pooling
- **Storage:** Local-first with session-based organization
- **UI:** React frontend served by Electron main process
- **Communication:** IPC between main/renderer, HTTP/WebSocket to backend

## Removed/Deprecated Locations

- ~~`app/desktop/`~~ → Use `app/electron/`
- ~~`ui-electron/`~~ → Use `app/electron/`
- ~~`config/` (at root)~~ → Use `app/config/`
- ~~`app/electron/main/config/`~~ → Config moved to `app/electron/main/config.js`
