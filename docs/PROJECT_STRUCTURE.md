# Project Structure

This document outlines the organized project structure for Transcripta.

## Directory Layout

```
Transcripta/
├── app/                          # Python backend
│   ├── api/                      # API endpoints
│   ├── audio/                    # Audio capture
│   ├── config/                   # Backend-specific config (legacy)
│   ├── core/                     # Core functionality
│   ├── stt/                      # Speech-to-text
│   ├── stem/                     # STEM processing
│   └── storage/                  # Data persistence
├── config/                       # Shared configuration (NEW)
│   ├── generate_ts.py            # TypeScript generator
│   ├── python/                   # Python config source
│   │   ├── constants.py
│   │   └── text.py
│   ├── typescript/               # Auto-generated TypeScript
│   │   ├── constants.ts
│   │   └── text.ts
│   └── shared/                   # Shared exports
│       └── index.ts
├── docs/                         # Documentation
│   ├── api/                      # API documentation
│   ├── architecture/             # Design docs
│   ├── deployment/               # Deployment guides
│   └── operations/               # Operations guides
├── app/
│   ├── desktop/                  # Electron frontend (NEW LOCATION)
│   │   ├── frontend/             # React app
│   │   ├── main/                 # Main process
│   │   │   ├── main.js
│   │   │   ├── preload.js
│   │   │   ├── preload-floating.js
│   │   │   ├── preload-quick-settings.js
│   │   │   ├── model-download-manager.js
│   │   │   └── config.js
│   │   └── renderer/             # Renderer dist
├── tests/                        # Test suite
├── tools/                        # Development tools
├── scripts/                      # Build scripts
├── CHANGELOG.md                  # Version history
├── CONTRIBUTING.md               # Contribution guidelines
├── LICENSE                       # License file
├── pyproject.toml                # Python project config
├── README.md                     # Main entry
└── requirements.txt              # Python dependencies
```

## Key Changes

### 1. Configuration Centralization

The `config/` directory provides a single source of truth for constants shared between Python and TypeScript.

**Usage:**

```python
# Python
from config import AudioConstants, MODEL_NAMES
```

```typescript
// TypeScript
import { AudioConstants, ModelNames } from '@config/constants';
```

**Regenerating TypeScript:**

```powershell
python config/generate_ts.py
```

### 2. Documentation Organization

Documents are organized by purpose:

- `docs/architecture/` - Design decisions and planning
- `docs/deployment/` - Installation and deployment
- `docs/operations/` - Running and maintaining
- `docs/api/` - API documentation

### 3. Electron Main Process

Main process files in `app/desktop/main/`:

- `main.js` - Main entry point
- `preload.js` - Preload script for main window
- `preload-floating.js` - Preload for floating window
- `preload-quick-settings.js` - Preload for quick settings
- `model-download-manager.js` - Model management
- `config.js` - Configuration constants

## Import Path Updates

### Python

No changes needed - imports remain relative to `app/`.

### TypeScript

New path alias for configuration:

```typescript
// tsconfig.json paths
"@config/*": ["../../config/typescript/*"]
```

```typescript
// vite.config.ts alias
"@config": path.resolve(__dirname, '../../config/typescript')
```

## Build Scripts

Build scripts have been updated to reflect the new paths:

- `app/desktop/package.json` - Updated `main` entry to `main/main.js`
- `app/desktop/package.json` - Updated `files` array for electron-builder
- `app/desktop/main/main.js` - Updated all path references
- `app/desktop/main/config.js` - Updated path references

## Verification

To verify the reorganization:

1. Check Python imports work:
   ```powershell
   python -c "from config import AudioConstants; print(AudioConstants.DEFAULT_SAMPLE_RATE)"
   ```

2. Check TypeScript generation:
   ```powershell
   python config/generate_ts.py
   ```

3. Check Electron paths resolve:
   ```powershell
   cd app/desktop
   npm run build:frontend
   ```

## Maintenance

When adding new shared constants:

1. Add to `config/python/constants.py` or `config/python/text.py`
2. Run `python config/generate_ts.py`
3. Import from `@config/` in TypeScript code
