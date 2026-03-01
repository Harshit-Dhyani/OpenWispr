# Transcripta Deployment Guide

Production-grade deployment instructions for the Transcripta Windows 11 desktop transcription application.

## Prerequisites

| Component | Minimum Version | Purpose |
|-----------|-----------------|---------|
| Windows 11 | 22H2 | Host operating system |
| Python | 3.11+ | Backend runtime |
| Node.js | 20.x LTS | Frontend build tooling |
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
pip install -e .[dev]
```

### 2. Install Node Dependencies

```powershell
# Install root-level scripts
npm run install:ui

# Or manually:
cd ui-electron
npm install
```

## GPU vs CPU Setup

### GPU Setup (Recommended for NVIDIA)

Requirements:
- NVIDIA GPU with Compute Capability 6.0+ (GTX 1060, RTX 20-series, or newer)
- CUDA 11.8 or 12.1 runtime
- 4GB+ VRAM for `small` model, 2GB+ for `base` model

**Verify GPU Detection:**

```powershell
.\.venv\Scripts\Activate.ps1

# Check CTranslate2 CUDA visibility
python -c "import ctranslate2; print('CUDA devices:', ctranslate2.get_cuda_device_count())"

# Expected output:
# CUDA devices: 1

# Verify faster-whisper GPU initialization
python -c "from faster_whisper import WhisperModel; m = WhisperModel('small', device='cuda', compute_type='float16'); print('GPU ready')"
```

**GPU Environment Configuration:**

```powershell
# Create .env file for GPU mode
@"
TRANSCRIPTA_DEVICE=cuda
TRANSCRIPTA_COMPUTE_TYPE=float16
TRANSCRIPTA_DEFAULT_MODEL=small
TRANSCRIPTA_LOG_LEVEL=INFO
"@ | Set-Content -Path .env -Encoding UTF8
```

### CPU Setup (Fallback)

Requirements:
- x86_64 processor with AVX2 support
- 8GB+ RAM for `small` model, 4GB+ for `base` model

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

### Model Size Selection

| Model | Size | VRAM Required | RAM Required | Use Case |
|-------|------|---------------|--------------|----------|
| `tiny` | 39 MB | 1 GB | 2 GB | Fastest, lowest accuracy |
| `base` | 74 MB | 2 GB | 4 GB | Balanced for CPU |
| `small` | 244 MB | 4 GB | 8 GB | Recommended for GPU |
| `medium` | 769 MB | 8 GB | 16 GB | High accuracy |
| `large-v3` | 2.9 GB | 12 GB | 32 GB | Maximum accuracy |

## Environment Configuration

Create a `.env` file in the project root:

```powershell
# Core settings
TRANSCRIPTA_DEVICE=auto                    # auto, cuda, cpu
TRANSCRIPTA_COMPUTE_TYPE=float16           # float16, int8, int8_float16
TRANSCRIPTA_DEFAULT_MODEL=small            # tiny, base, small, medium, large-v3
TRANSCRIPTA_DEFAULT_LANGUAGE=auto          # auto, en, de, fr, etc.

# Performance tuning
TRANSCRIPTA_CHUNK_SECONDS=3.2
TRANSCRIPTA_OVERLAP_SECONDS=0.6
TRANSCRIPTA_BEAM_SIZE=1
TRANSCRIPTA_BEST_OF=1
TRANSCRIPTA_TEMPERATURE=0.0

# VAD (Voice Activity Detection)
TRANSCRIPTA_VAD_FILTER=true
TRANSCRIPTA_VAD_THRESHOLD=0.5
TRANSCRIPTA_VAD_MIN_SILENCE_MS=200
TRANSCRIPTA_VAD_SPEECH_PAD_MS=200

# Paths
TRANSCRIPTA_EXPORT_ROOT=./sessions
TRANSCRIPTA_DOWNLOAD_ROOT=./models

# API settings
TRANSCRIPTA_API_HOST=127.0.0.1
TRANSCRIPTA_API_PORT=8765

# Logging
TRANSCRIPTA_LOG_LEVEL=INFO                 # DEBUG, INFO, WARNING, ERROR
```

### Per-Environment Presets

**Development:**
```powershell
@"
TRANSCRIPTA_DEVICE=cpu
TRANSCRIPTA_COMPUTE_TYPE=int8
TRANSCRIPTA_DEFAULT_MODEL=base
TRANSCRIPTA_LOG_LEVEL=DEBUG
TRANSCRIPTA_VAD_FILTER=true
"@ | Set-Content -Path .env -Encoding UTF8
```

**Production GPU:**
```powershell
@"
TRANSCRIPTA_DEVICE=cuda
TRANSCRIPTA_COMPUTE_TYPE=float16
TRANSCRIPTA_DEFAULT_MODEL=small
TRANSCRIPTA_LOG_LEVEL=INFO
TRANSCRIPTA_VAD_FILTER=true
"@ | Set-Content -Path .env -Encoding UTF8
```

**Production CPU:**
```powershell
@"
TRANSCRIPTA_DEVICE=cpu
TRANSCRIPTA_COMPUTE_TYPE=int8
TRANSCRIPTA_DEFAULT_MODEL=base
TRANSCRIPTA_LOG_LEVEL=INFO
TRANSCRIPTA_VAD_FILTER=true
"@ | Set-Content -Path .env -Encoding UTF8
```

## Building the Frontend

```powershell
# Navigate to Electron directory
cd ui-electron

# Build frontend assets (production)
npm run build:frontend

# Or manually via frontend directory
cd frontend
npm run build
cd ..
```

Build output goes to `ui-electron/renderer/dist/`.

## Running in Development Mode

### Full Application (Recommended)

```powershell
# From project root with venv activated
.\.venv\Scripts\Activate.ps1
cd ui-electron
npm run dev
```

This command:
1. Builds the frontend assets
2. Starts the Python backend on port 8765
3. Launches Electron with dev tools

### Backend Only

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.api_main

# Verify API is running
curl http://127.0.0.1:8765/api/health
```

### Frontend Only (with external backend)

```powershell
cd ui-electron\frontend
npm run dev

# In another terminal, start backend separately
.\.venv\Scripts\Activate.ps1
python -m app.api_main
```

## Packaging for Distribution

### Portable Build

```powershell
# Ensure you're on a clean branch with latest changes
.\.venv\Scripts\Activate.ps1
cd ui-electron

# Install dependencies
npm install

# Build production frontend
npm run build:frontend

# Create portable executable
npm run pack
```

Output: `ui-electron/dist/win-unpacked/`

### Installer Build (NSIS)

```powershell
.\.venv\Scripts\Activate.ps1
cd ui-electron
npm install
npm run build:frontend

# Build both portable and installer
npm run dist
```

Outputs:
- `ui-electron/dist/Transcripta.exe` (portable)
- `ui-electron/dist/Transcripta Setup.exe` (installer)

### Build Configuration

The `ui-electron/package.json` controls packaging:

```json
{
  "build": {
    "appId": "local.transcripta.desktop",
    "productName": "Transcripta",
    "directories": {
      "output": "dist"
    },
    "files": [
      "main.js",
      "preload.js",
      "renderer/dist/**/*",
      "package.json"
    ],
    "win": {
      "target": ["portable", "nsis"]
    }
  }
}
```

### Pre-Packaging Checklist

- [ ] Virtual environment activated
- [ ] All tests passing (`pytest tests -q`)
- [ ] Frontend builds without errors
- [ ] `.env` configured for target environment
- [ ] Port 8765 is free
- [ ] Model files downloaded (first run will download)
- [ ] Windows Defender exclusion set (optional)

## Troubleshooting

### Backend fails to start

**Symptom:** Electron launches but shows connection error

```powershell
# Check if port is in use
netstat -ano | findstr :8765

# Kill process using port
Get-NetTCPConnection -LocalPort 8765 | ForEach-Object { Stop-Process -Id $_.OwningProcess }

# Test backend independently
.\.venv\Scripts\Activate.ps1
python -m app.api_main
```

### GPU not detected

**Symptom:** Logs show `CUDA devices: 0` or GPU initialization fails

```powershell
# Verify NVIDIA driver
nvidia-smi

# Check CUDA availability in Python
python -c "import torch; print(torch.cuda.is_available())"

# Force CPU fallback in .env
@"
TRANSCRIPTA_DEVICE=cpu
TRANSCRIPTA_COMPUTE_TYPE=int8
"@ | Set-Content -Path .env -Encoding UTF8
```

### Model download fails

**Symptom:** First run hangs at model download

```powershell
# Pre-download models manually
.\.venv\Scripts\Activate.ps1
python -c "from faster_whisper import WhisperModel; WhisperModel('small')"

# Or set custom download root
$env:TRANSCRIPTA_DOWNLOAD_ROOT="C:\Transcripta\Models"
```

### Audio capture not working

**Symptom:** No transcription output despite audio playing

1. Disable exclusive mode on playback device:
   - Settings > System > Sound > More sound settings
   - Playback tab > Select device > Properties > Advanced
   - Uncheck "Allow applications to take exclusive control"

2. Verify loopback device selection:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -c "import soundcard; print([d.name for d in soundcard.all_speakers()])"
   ```

3. Test with known audio source (YouTube, local media)

### Build fails

**Symptom:** `npm run dist` produces errors

```powershell
# Clear build artifacts
Remove-Item -Recurse -Force ui-electron/dist
Remove-Item -Recurse -Force ui-electron/renderer/dist
Remove-Item -Recurse -Force ui-electron/frontend/dist

# Rebuild from scratch
npm install
npm run build:frontend
npm run dist
```

### Slow transcription

**Symptom:** High latency between speech and text

| Cause | Solution |
|-------|----------|
| CPU bottleneck | Switch to GPU or reduce model size |
| Large model | Use `base` or `small` instead of `medium` |
| High VAD threshold | Lower `TRANSCRIPTA_VAD_THRESHOLD=0.3` |
| Chunk too large | Reduce `TRANSCRIPTA_CHUNK_SECONDS=2.0` |
| Background apps | Close GPU-intensive applications |

### Application crashes on startup

```powershell
# Check Windows Event Viewer
Get-EventLog -LogName Application -Source "Application Error" -Newest 10

# Run with debug logging
$env:TRANSCRIPTA_LOG_LEVEL="DEBUG"
cd ui-electron
npm run dev

# Check Electron process logs
# Located at: %APPDATA%\Transcripta\logs\
```

### Permission errors

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
python -c "import ctranslate2; print(f'CTranslate2 OK, CUDA: {ctranslate2.get_cuda_device_count()}')"

# Backend API
curl http://127.0.0.1:8765/api/health | ConvertFrom-Json

# Frontend build
cd ui-electron\frontend
npm run build
cd ..

# Electron shell
npm run pack
```

## Release Checklist

- [ ] Version bumped in `pyproject.toml` and `package.json`
- [ ] All tests passing (`pytest tests -q`)
- [ ] CHANGELOG.md updated
- [ ] README.md updated with new features
- [ ] Clean build tested on Windows 11
- [ ] GPU and CPU paths both tested
- [ ] Portable and installer builds produced
- [ ] Virus scan completed on artifacts
- [ ] Digital signature applied (if available)
