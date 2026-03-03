# Contributing to Transcripta

Thank you for your interest in contributing to Transcripta.

## Development Setup

### Prerequisites

- Windows 11 (primary development platform)
- Python 3.11+
- Node.js 20+
- Git

### Initial Setup

```powershell
# Clone the repository
git clone <repository-url>
cd Transcripta

# Set up Python environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -e .[dev]

# Set up Electron UI
cd app/desktop
npm install
cd ../..
```

### Running in Development Mode

```powershell
# Terminal 1: Start the backend
.\.venv\Scripts\Activate.ps1
python -m app.api_main

# Terminal 2: Start the Electron UI
cd app/desktop
npm run dev
```

Or use the combined dev command:

```powershell
cd app/desktop
npm run dev
```

## Code Style

### Python

- Follow PEP 8
- Use type hints
- Run `ruff check .` before committing
- Run `mypy app/` for type checking

### TypeScript/JavaScript

- Use strict TypeScript settings
- Follow the existing component patterns
- Run `npm run lint` in app/desktop/frontend before committing

## Testing

```powershell
# Run Python tests
pytest tests/

# Run specific test file
pytest tests/test_sse_events.py -v
```

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes
3. Add tests for new functionality
4. Ensure all tests pass
5. Update documentation if needed
6. Submit a pull request with a clear description

## Reporting Issues

When reporting issues, please include:

- Windows version
- Python version
- GPU/CPU configuration
- Steps to reproduce
- Expected vs actual behavior
- Relevant log excerpts

## Architecture Decisions

Key architectural constraints:

- **Privacy-first**: All processing stays local
- **Windows 11 primary**: Cross-platform is secondary
- **Local AI models**: No cloud dependencies for transcription
- **Session-based**: All data organized by session

See `docs/architecture/` for detailed design documentation.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
