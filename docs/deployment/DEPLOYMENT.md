---
title: Deployment Guide
audience: operators
last_verified: 2026-03-04
source_of_truth:
  - tools/setup/
  - package.json
  - requirements.txt
---

# Transcripta Deployment Guide

Production-grade deployment instructions for the Transcripta Windows 11 desktop transcription application.

## Prerequisites

| Component | Minimum Version | Purpose |
|-----------|-----------------|---------|
| Windows 11 | 22H2 | Host operating system |
| Python | 3.11+ | Backend runtime |
| Node.js | 20.x+ | Frontend build tooling |
| Git | 2.40+ | Source control |
| NVIDIA Driver | 537+ | CUDA support (optional) |

### Verify Prerequisites

```powershell
# Windows version
winver

# Python version (must be 3.11 or higher)
python --version

# Node.js version (must be 20.x or higher)
node --version
npm --version

# Git version
git --version

# NVIDIA driver (if using GPU)
nvidia-smi
```

## Installation

### 1. Clone and Setup

```powershell
# Clone the repository
git clone <repository-url> transcripta
cd transcripta

# Create Python virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# If PowerShell execution policy blocks activation:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install build dependencies
python -m pip install --upgrade pip setuptools wheel

# Install the application in editable mode
pip install -e ".[dev]"
```

### 2. Install Node Dependencies

```powershell
# Install all dependencies (root + electron + frontend)
npm run install:all

# Or manually:
cd app/electron
npm install
```

## Dependencies

### Python Dependencies (from pyproject.toml)

Core runtime dependencies:
- `numpy==1.26.4` - Numerical operations
- `PySide6==6.8.1` - Qt bindings for UI
- `PyAudioWPatch==0.2.12.7` - Audio capture with loopback support
- `soundcard==0.4.3` - Audio device enumeration
- `sounddevice==0.5.1` - Audio I/O
- `soundfile==0.12.1` - Audio file handling
- `faster-whisper==1.1.1` - Speech-to-text engine
- `fastapi==0.115.0` - API framework
- `uvicorn==0.32.0` - ASGI server
- `python-multipart==0.0.17` - Form data parsing
- `httpx==0.27.2` - HTTP client
- `requests==2.32.3` - HTTP library
- `torch==2.5.1` / `torchaudio==2.5.1` - PyTorch for GPU inference
- `llama-cpp-python>=0.3.7` - Local LLM support

Development dependencies (`[dev]` extras):
- `pytest>=8.3` - Testing framework
- `pytest-asyncio>=0.24` - Async test support
- `pytest-cov>=6.0` - Coverage reporting
- `pytest-xdist>=3.6` - Parallel test execution
- `httpx>=0.27` - Test client
- `ruff>=0.8` - Python linting
- `mypy>=1.14` - Type checking
- `pyinstaller>=6.11` - Executable packaging
- `psutil>=6.0` - System utilities

### Node.js Dependencies (from package.json)

- `electron==37.2.0` - Desktop shell
- `electron-builder==26.0.12` - Packaging and distribution
- `electron-updater==6.1.8` - Auto-update support
- `concurrently==8.2.2` - Parallel process runner
- `cross-env==7.0.3` - Environment variable cross-platform support
- `rimraf==5.0.5` - Cross-platform file removal

## GPU vs CPU Setup

### GPU Setup (Recommended for NVIDIA)

Requirements:
- NVIDIA GPU with Compute Capability 6.0+ (GTX 1060, RTX 20-series, or newer)
- CUDA 11.8 or 12.1 runtime
- 2GB+ VRAM for `small` model, 5GB+ for `medium` model

**Verify GPU Detection:**

```powershell
.\.venv\Scripts\Activate.ps1

# Check PyTorch CUDA visibility
python -c "import torch; print(f'PyTorch CUDA available: {torch.cuda.is_available()}'); print(f'CUDA devices: {torch.cuda.device_count()}')"

# Check faster-whisper GPU initialization
python -c "from faster_whisper import WhisperModel; m = WhisperModel('small', device='cuda', compute_type='float16'); print('GPU ready')"
```

**GPU Environment Configuration:**

```powershell
# Create .env file for GPU mode
@"
TRANSCRIPTA_DEVICE=cuda
TRANSCRIPTA_COMPUTE_TYPE=float16
TRANSCRIPTA_DEFAULT_MODEL=medium
TRANSCRIPTA_LOG_LEVEL=INFO
"@ | Set-Content -Path .env -Encoding UTF8
```

### CPU Setup (Fallback)

Requirements:
- x86_64 processor with AVX2 support
- 4GB+ RAM for `small` model, 8GB+ for `medium` model

**Verify CPU Mode:**

```powershell
.\.venv\Scripts\Activate.ps1

# Test CPU initialization
python -c "from faster_whisper import WhisperModel; m = WhisperModel('small', device='cpu', compute_type='int8'); print('CPU ready')"
```

**CPU Environment Configuration:**

```powershell
# Create .env file for CPU mode
@"
TRANSCRIPTA_DEVICE=cpu
TRANSCRIPTA_COMPUTE_TYPE=int8
TRANSCRIPTA_DEFAULT_MODEL=small
TRANSCRIPTA_LOG_LEVEL=INFO
"@ | Set-Content -Path .env -Encoding UTF8
```

### Model Size Selection (from model_catalog.py)

Models download from HuggingFace (Systran/faster-whisper-* repositories):

| Model | Size | VRAM Required | Speed Tier | Use Case |
|-------|------|---------------|------------|----------|
| `tiny` | ~80 MB | 0 GB | fast | Fastest, lowest accuracy, CPU-first |
| `small` | ~460 MB | 2 GB | fast | Best fast option for local dictation |
| `medium` | ~1.5 GB | 5 GB | balanced | Default for most Windows systems with GPU |
| `large-v3` | ~3.1 GB | 10 GB | quality | Highest accuracy for stronger GPUs |
| `turbo` | ~1.6 GB | 6 GB | fast | Large-model style decoding (disabled) |

*Note: Model sizes are estimates including all artifacts (model.bin, config.json, tokenizer.json, vocabulary.txt)*

### Valid Model Names

From `ModelConstants.VALID_MODELS`: `tiny`, `base`, `small`, `medium`, `large-v3`, `turbo`

Default model: `medium`

## Environment Configuration

Create a `.env` file in the project root. All settings use `TRANSCRIPTA_` prefix:

### Available Environment Variables (from config.py)

```powershell
# Core application settings
TRANSCRIPTA_APP_NAME=Transcripta
TRANSCRIPTA_HOST=127.0.0.1
TRANSCRIPTA_PORT=8765
TRANSCRIPTA_LOG_LEVEL=INFO

# Audio settings
TRANSCRIPTA_SAMPLE_RATE=16000
TRANSCRIPTA_CHANNELS=1
TRANSCRIPTA_CHUNK_SECONDS=1.6
TRANSCRIPTA_OVERLAP_SECONDS=0.32
TRANSCRIPTA_CAPTURE_BLOCK_SECONDS=0.02
TRANSCRIPTA_METER_DECAY=0.85
TRANSCRIPTA_AUDIO_BACKEND=auto

# Model settings
TRANSCRIPTA_DEFAULT_MODEL=medium
TRANSCRIPTA_DEVICE=auto
TRANSCRIPTA_COMPUTE_TYPE=float16
TRANSCRIPTA_DEFAULT_LANGUAGE=auto
TRANSCRIPTA_BEAM_SIZE=5
TRANSCRIPTA_BEST_OF=5
TRANSCRIPTA_TEMPERATURE=0.0
TRANSCRIPTA_CONFIDENCE_THRESHOLD=0.6

# VAD (Voice Activity Detection)
TRANSCRIPTA_VAD_FILTER=true
TRANSCRIPTA_VAD_THRESHOLD_DB=-40.0
TRANSCRIPTA_VAD_MIN_SILENCE_MS=300
TRANSCRIPTA_VAD_SPEECH_PAD_MS=200

# Paths
TRANSCRIPTA_EXPORT_ROOT=./sessions
TRANSCRIPTA_DOWNLOAD_ROOT=./models

# Performance
TRANSCRIPTA_DEFAULT_LIVE_MODE=balanced
TRANSCRIPTA_DEFAULT_EXECUTION_MODE=auto
TRANSCRIPTA_AUTO_OPTIMIZE=true
TRANSCRIPTA_OPTIMIZATION_MODE=balanced

# Advanced quality
TRANSCRIPTA_ENABLE_FILLER_FILTER=true
TRANSCRIPTA_ENABLE_HALLUCINATION_FILTER=true
TRANSCRIPTA_MIN_SEGMENT_LENGTH=0.5
```

### Per-Environment Presets

**Development:**
```powershell
@"
TRANSCRIPTA_DEVICE=cpu
TRANSCRIPTA_COMPUTE_TYPE=int8
TRANSCRIPTA_DEFAULT_MODEL=tiny
TRANSCRIPTA_LOG_LEVEL=DEBUG
TRANSCRIPTA_VAD_FILTER=true
TRANSCRIPTA_AUTO_OPTIMIZE=true
"@ | Set-Content -Path .env -Encoding UTF8
```

**Production GPU:**
```powershell
@"
TRANSCRIPTA_DEVICE=cuda
TRANSCRIPTA_COMPUTE_TYPE=float16
TRANSCRIPTA_DEFAULT_MODEL=medium
TRANSCRIPTA_LOG_LEVEL=INFO
TRANSCRIPTA_VAD_FILTER=true
TRANSCRIPTA_AUTO_OPTIMIZE=true
TRANSCRIPTA_OPTIMIZATION_MODE=balanced
"@ | Set-Content -Path .env -Encoding UTF8
```

**Production CPU:**
```powershell
@"
TRANSCRIPTA_DEVICE=cpu
TRANSCRIPTA_COMPUTE_TYPE=int8
TRANSCRIPTA_DEFAULT_MODEL=small
TRANSCRIPTA_LOG_LEVEL=INFO
TRANSCRIPTA_VAD_FILTER=true
TRANSCRIPTA_AUTO_OPTIMIZE=true
TRANSCRIPTA_OPTIMIZATION_MODE=low_memory
"@ | Set-Content -Path .env -Encoding UTF8
```

## Building the Frontend

```powershell
# Build frontend assets (production)
npm run build:frontend

# Or from root
cd app/electron
npm run build:frontend
```

Build output goes to `app/electron/renderer/dist/`.

## Running in Development Mode

### Full Application (Recommended)

```powershell
# From project root with venv activated
.\.venv\Scripts\Activate.ps1
npm run dev
```

This command (via `concurrently`):
1. Starts the Python backend on port 8765
2. Launches Electron with dev tools

### Backend Only

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.api_main

# Verify API is running
curl http://127.0.0.1:8765/api/health
```

### Frontend Only (with external backend)

```powershell
# Terminal 1: Start backend
.\.venv\Scripts\Activate.ps1
python -m app.api_main

# Terminal 2: Start frontend dev server
npm run dev:frontend
```

## Packaging for Distribution

Build targets (from root `package.json`):
- `nsis` - Windows installer
- `portable` - Standalone executable
- `msi` - Windows MSI package

### Portable Build

```powershell
# Ensure you're on a clean branch with latest changes
.\.venv\Scripts\Activate.ps1

# Clean and build
npm run build:clean
npm run build:frontend

# Create portable executable
cd app/electron
npm run pack
```

Output: `app/electron/dist/win-unpacked/`

### Full Distribution Build (NSIS + Portable)

```powershell
.\.venv\Scripts\Activate.ps1

# Build production assets
npm run build:production

# Build distribution
cd app/electron
npm run dist
```

Outputs:
- `app/electron/dist/Transcripta-<version>.exe` (portable)
- `app/electron/dist/Transcripta Setup-<version>.exe` (installer)

### Root-Level Build Commands

From project root (`package.json` scripts):

```powershell
# Install everything
npm run install:all

# Development
npm run dev              # Backend + Electron
npm run dev:backend      # Backend only
npm run dev:electron     # Electron only
npm run dev:frontend     # Frontend dev server

# Building
npm run build            # Full build (clean + frontend + electron)
npm run build:clean      # Remove dist directories
npm run build:frontend   # Build frontend assets
npm run build:production # Production build

# Packaging
npm run pack             # Create unpacked directory
npm run dist             # Create installers
npm run dist:portable    # Portable only
npm run dist:win         # Windows only

# Testing
npm run test             # All tests
npm run test:backend     # Python tests (pytest)
npm run test:frontend    # Frontend tests

# Linting
npm run lint             # All linting
npm run lint:python      # Ruff check
npm run lint:fix         # Auto-fix issues

# Other
npm run clean            # Remove all build artifacts
npm run clean:all        # Remove artifacts + cache
npm run tree:generate    # Generate project tree
```

### Build Configuration

The root `package.json` controls packaging:

```json
{
  "build": {
    "appId": "com.transcripta.desktop",
    "productName": "Transcripta",
    "directories": {
      "output": "release"
    },
    "win": {
      "target": [
        { "target": "nsis", "arch": ["x64", "ia32"] },
        { "target": "portable", "arch": ["x64"] },
        { "target": "msi", "arch": ["x64"] }
      ]
    }
  }
}
```

### Pre-Packaging Checklist

- [ ] Virtual environment activated
- [ ] All tests passing (`pytest` or `npm run test:backend`)
- [ ] Frontend builds without errors (`npm run build:frontend`)
- [ ] `.env` configured for target environment
- [ ] Port 8765 is free
- [ ] Model files downloaded (first run will download)
- [ ] Windows Defender exclusion set (optional)

## Troubleshooting

### Backend Port 8765 Conflicts

**Symptom:** `OSError: [WinError 10048]` or backend fails to start

```powershell
# Check if port is in use
netstat -ano | findstr :8765

# Kill process using port
Get-NetTCPConnection -LocalPort 8765 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

# Or use alternative port
$env:TRANSCRIPTA_PORT=8766
python -m app.api_main
```

### GPU Not Detected

**Symptom:** Logs show `CUDA devices: 0` or GPU initialization fails

```powershell
# Verify NVIDIA driver
nvidia-smi

# Check PyTorch CUDA availability
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# Check CUDA version
python -c "import torch; print(f'CUDA version: {torch.version.cuda}')"

# Force CPU fallback in .env
@"
TRANSCRIPTA_DEVICE=cpu
TRANSCRIPTA_COMPUTE_TYPE=int8
"@ | Set-Content -Path .env -Encoding UTF8

# Common GPU fallback triggers (from constants.py)
# - "cublas", "cuda", "cudnn", "out of memory", "cuda error"
```

### Model Download Failures

**Symptom:** First run hangs at model download or fails with network error

```powershell
# Pre-download models manually
.\.venv\Scripts\Activate.ps1
python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu')"

# Set custom download root
$env:TRANSCRIPTA_DOWNLOAD_ROOT="C:\Transcripta\Models"

# Check HuggingFace connectivity
python -c "import requests; r = requests.get('https://huggingface.co'); print(f'HuggingFace status: {r.status_code}')"

# Download models manually from:
# - https://huggingface.co/Systran/faster-whisper-tiny
# - https://huggingface.co/Systran/faster-whisper-small
# - https://huggingface.co/Systran/faster-whisper-medium
# - https://huggingface.co/Systran/faster-whisper-large-v3
```

### Audio Capture Not Working

**Symptom:** No transcription output despite audio playing

1. **Disable exclusive mode on playback device:**
   - Settings > System > Sound > More sound settings
   - Playback tab > Select device > Properties > Advanced
   - Uncheck "Allow applications to take exclusive control"

2. **Verify loopback device selection:**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -c "import soundcard; print([d.name for d in soundcard.all_speakers()])"
   ```

3. **Test PyAudio device enumeration:**
   ```powershell
   python -c "import pyaudiowpatch; pa = pyaudiowpatch.PyAudio(); print(f'Devices: {pa.get_device_count()}')"
   ```

4. **Test with known audio source (YouTube, local media)**

5. **Check audio backend:**
   ```powershell
   python -c "from app.audio.backends import get_backend; b = get_backend(); print(f'Backend: {b.name}')"
   ```

### Build Fails

**Symptom:** `npm run dist` produces errors

```powershell
# Clear build artifacts
npm run clean

# Reinstall dependencies
npm run install:all

# Rebuild from scratch
npm run build:production
npm run dist
```

### Slow Transcription

**Symptom:** High latency between speech and text

| Cause | Solution |
|-------|----------|
| CPU bottleneck | Switch to GPU or reduce model size |
| Large model | Use `small` instead of `medium` |
| High VAD threshold | Lower `TRANSCRIPTA_VAD_THRESHOLD_DB=-50.0` |
| Chunk too large | Reduce `TRANSCRIPTA_CHUNK_SECONDS=1.0` |
| Background apps | Close GPU-intensive applications |

### Application Crashes on Startup

```powershell
# Check Windows Event Viewer
Get-EventLog -LogName Application -Source "Application Error" -Newest 10

# Run with debug logging
$env:TRANSCRIPTA_LOG_LEVEL="DEBUG"
npm run dev

# Check backend logs
python -m app.api_main
```

### Permission Errors

**Symptom:** Access denied when writing sessions

```powershell
# Grant write permissions to sessions folder
$path = "$(Get-Location)\sessions"
New-Item -ItemType Directory -Force -Path $path
$acl = Get-Acl $path
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    $env:USERNAME, "Modify", "ContainerInherit,ObjectInherit", "None", "Allow"
)
$acl.SetAccessRule($rule)
Set-Acl $path $acl
```

## Verification Commands

```powershell
# Full system check
.\.venv\Scripts\Activate.ps1

# Python environment
python -c "import app; print('App module OK')"
python -c "from faster_whisper import WhisperModel; print('Whisper OK')"
python -c "import torch; print(f'PyTorch OK, CUDA: {torch.cuda.is_available()}')"
python -c "import soundcard; print('Soundcard OK')"
python -c "import pyaudiowpatch; print('PyAudio OK')"

# Backend API
curl http://127.0.0.1:8765/api/health

# Test transcription pipeline
python -c "
from app.stt import get_transcription_service
from app.core.config import AppSettings
settings = AppSettings()
print(f'Device: {settings.device}, Model: {settings.default_model}')
"

# Frontend build
cd app/electron
npm run build:frontend

# Electron pack
npm run pack
```

## Release Checklist

- [ ] Version bumped in `pyproject.toml` and `package.json`
- [ ] All tests passing (`pytest`)
- [ ] CHANGELOG.md updated
- [ ] README.md updated with new features
- [ ] Clean build tested on Windows 11
- [ ] GPU and CPU paths both tested
- [ ] Portable and installer builds produced (`npm run dist`)
- [ ] Artifacts in `release/` directory
- [ ] Virus scan completed on artifacts
- [ ] Digital signature applied (if available)

## Build Output Structure

```
release/
├── Transcripta-<version>-setup.exe     # NSIS installer
├── Transcripta-<version>-portable.exe  # Portable executable
└── win-unpacked/                       # Unpacked directory (npm run pack)
```

Or from `app/electron/dist/`:
```
app/electron/dist/
├── Transcripta-<version>.exe           # Portable
├── Transcripta Setup-<version>.exe     # Installer
└── win-unpacked/                       # Unpacked files
```
