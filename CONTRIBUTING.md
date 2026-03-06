# Contributing to Transcripta

Thank you for your interest in contributing to Transcripta. This document provides guidelines for setting up the development environment, coding standards, and the contribution process.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing](#testing)
- [Debugging](#debugging)
- [Pull Request Process](#pull-request-process)
- [Code Review Checklist](#code-review-checklist)
- [Architecture Constraints](#architecture-constraints)
- [Areas Needing Contribution](#areas-needing-contribution)
- [Documentation Contributions](#documentation-contributions)
- [Reporting Issues](#reporting-issues)

## Documentation Contributions

Contributing to documentation follows the same process as code contributions.

### Quick Start

1. Edit docs in the `docs/` directory
2. Add required YAML frontmatter to new files (see [docs/_style.md](./docs/_style.md))
3. Update `docs/_inventory.yml` for new files
4. Run `python tools/ci/verify-docs.py` to validate
5. Include doc changes in your PR

### Detailed Guide

See [docs/engineering/contributing-docs.md](./docs/engineering/contributing-docs.md) for:
- Required frontmatter format
- Code citation standards
- Cross-linking guidelines
- Terminology standards
- Review checklist

### Pull Request Template

When submitting PRs with documentation changes, please use this template:

```markdown
## Summary
Brief description of changes

## Documentation Changes
- [ ] Added/updated frontmatter
- [ ] Updated inventory (docs/_inventory.yml)
- [ ] Cross-links validated
- [ ] verify-docs.py passes

## Verification
<!-- Paste output from: python tools/ci/verify-docs.py -->
```

## Prerequisites

- **Windows 11** (primary development platform)
- **Python 3.11+**
- **Node.js 20+** (npm 10+)
- **Git**
- **Git LFS** (for model files)

## Development Setup

### 1. Clone the Repository

```powershell
git clone <repository-url>
cd Transcripta
```

### 2. Set Up Python Environment

```powershell
# Create virtual environment
python -m venv .venv

# Activate (PowerShell)
.\.venv\Scripts\Activate.ps1

# Install dependencies in editable mode with dev extras
pip install -e ".[dev]"
```

### 3. Set Up Electron Frontend

```powershell
cd app/electron
npm install
cd ../..
```

Or use the root-level convenience command:

```powershell
npm run install:all
```

### 4. Verify Installation

```powershell
# Run linting to verify Python setup
ruff check .
mypy app/

# Run frontend typecheck
cd app/electron/frontend && npm run typecheck
```

## Project Structure

```
Transcripta/
├── app/
│   ├── api/           # FastAPI endpoints, WebSocket, SSE
│   ├── audio/         # Audio capture, VAD, backends
│   ├── stt/           # Speech-to-text, chunking, quality
│   ├── core/          # Settings, modes, sessions, config
│   ├── stem/          # Formula extraction
│   ├── storage/       # Session storage, document store
│   ├── electron/      # Electron frontend
│   │   ├── main/      # Main process, IPC, windows
│   │   └── frontend/  # React TypeScript UI
│   ├── ui/            # Legacy Qt UI (fallback)
│   └── config/        # Shared constants
├── tests/             # Test suite
├── tools/             # Development tools
├── docs/              # Documentation
└── config/            # Shared Python/TypeScript config
```

## Development Workflow

### Start Development Server

```powershell
# Starts both backend and Electron concurrently
npm run dev
```

Or start individually:

```powershell
# Terminal 1: Backend
.\.venv\Scripts\Activate.ps1
python -m app.api_main

# Terminal 2: Electron frontend
cd app/electron
npm run dev
```

### Building

```powershell
# Development build
npm run build

# Production build
npm run build:production

# Clean build artifacts
npm run clean
```

## Code Style Guidelines

### Python

We use **ruff** for linting and **mypy** for type checking:

```powershell
# Check all Python files
ruff check .

# Auto-fix issues
ruff check . --fix

# Type checking
mypy app/
```

**Standards:**
- Line length: 100 characters (configured in `pyproject.toml`)
- Target Python version: 3.11
- Use type hints for all function signatures
- Follow PEP 8 style guidelines
- Import order: stdlib, third-party, local

### TypeScript/JavaScript

```powershell
# Run from app/electron/frontend directory
cd app/electron/frontend

# Linting
npm run lint

# Type checking
npm run typecheck
```

**Standards:**
- Strict TypeScript configuration enforced
- Functional components with hooks
- Explicit return types on exported functions
- Prefer `interface` over `type` for object shapes

## Testing

### Backend Tests (pytest)

```powershell
# Run all tests
pytest tests/ -q

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_sse_events.py -v

# Run only unit tests
pytest tests/ -m unit

# Run integration tests
pytest tests/ -m integration
```

### Frontend Tests (Vitest)

```powershell
cd app/electron/frontend

# Run tests
npm run test

# Run with coverage
npm run test:coverage

# Run in watch mode
npm run test:watch
```

### All Tests

```powershell
# Run both frontend and backend tests
npm run test
```

## Debugging

### Backend Debugging

```powershell
# Enable debug logging
$env:TRANSCRIPTA_DEBUG=1
python -m app.api_main

# Or use Python debugger
python -m pdb -m app.api_main
```

### Frontend Debugging

1. Open DevTools: `Ctrl+Shift+I` (or `Cmd+Option+I` on Mac)
2. Console logs from main process appear in terminal
3. Use `console.log()` in renderer process for UI debugging

### Electron Debugging

```powershell
# Run with Node inspector
cd app/electron
npm run dev -- --inspect=5858
```

## Pull Request Process

1. **Create a feature branch** from `main`:
   ```powershell
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following code style guidelines

3. **Add tests** for new functionality

4. **Run all checks** before committing:
   ```powershell
   # Python
   ruff check .
   mypy app/
   pytest tests/ -q

   # TypeScript
   cd app/electron/frontend
   npm run lint
   npm run typecheck
   npm run test
   ```

5. **Update documentation** if needed (README, docs/, inline comments)

6. **Commit** with clear messages following conventional commits:
   ```
   feat(stt): add support for new VAD algorithm
   fix(api): resolve WebSocket reconnection issue
   docs: update installation instructions
   ```

7. **Push and submit PR** with:
   - Clear title and description
   - Link to related issues
   - Screenshots for UI changes
   - Test results

## Code Review Checklist

Before submitting or reviewing a PR, verify:

- [ ] Code follows style guidelines (ruff, mypy, ESLint pass)
- [ ] All tests pass (`npm run test`)
- [ ] New functionality has test coverage
- [ ] Type hints/types are correct and complete
- [ ] No hardcoded secrets or credentials
- [ ] Error handling is robust
- [ ] Documentation is updated
- [ ] Changes respect architecture constraints (see below)

## Architecture Constraints

All contributions must respect these core principles:

### Privacy-First
- **All processing stays local** - no cloud transcription services
- User audio never leaves the machine
- No telemetry or analytics without explicit opt-in

### Local-Only AI
- Use local models (Whisper, Llama.cpp)
- No API keys for external AI services
- Models bundled or downloadable to local storage

### Windows 11 Primary
- Primary target platform is Windows 11
- Cross-platform support is secondary
- Use Windows-specific APIs where beneficial

### Session-Based Architecture
- All data organized by session
- Sessions are self-contained and portable
- Clear data lifecycle management

## Areas Needing Contribution

### High Priority
- **Audio Backend Optimization**: Improve WASAPI loopback capture performance
- **VAD Improvements**: Better voice activity detection for noisy environments
- **STEM Formula Recognition**: Enhanced LaTeX/formula extraction accuracy
- **Documentation**: API docs, architecture diagrams, user guides

### Medium Priority
- **Testing Coverage**: Expand test suite, especially integration tests
- **UI/UX**: Accessibility improvements, theme consistency
- **Performance**: Memory optimization, startup time reduction
- **Error Handling**: Better user-facing error messages

### Good First Issues
- Bug fixes labeled `good-first-issue`
- Documentation improvements
- Type annotation additions
- Code refactoring for clarity

## Reporting Issues

When reporting bugs, please include:

**Environment:**
- Windows version (e.g., Windows 11 23H2)
- Python version (`python --version`)
- Node.js version (`node --version`)
- GPU/CPU configuration

**Reproduction:**
- Steps to reproduce (numbered list)
- Expected behavior
- Actual behavior
- Error messages or stack traces

**Logs:**
- Relevant excerpts from logs (sanitize any personal info)
- Located in `%APPDATA%/Transcripta/logs/` (Windows)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

For questions or clarifications, open a discussion in the GitHub Discussions tab.
