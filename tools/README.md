# Transcripta Development Tools

This directory contains development, diagnostic, and maintenance tools for the Transcripta project.

## Quick Start

```bash
# Run all diagnostics
python tools/runner.py --all

# Check specific areas
python tools/runner.py --system    # CUDA, dependencies
python tools/runner.py --audio     # Audio devices
python tools/runner.py --ci         # Pre-commit checks
python tools/runner.py --cleanup    # Log cleanup

# Get JSON output for automation
python tools/runner.py --all --json
```

### PowerShell (Windows)

```powershell
# Run all diagnostics
python tools\runner.py --all

# Run with verbose output
python tools\runner.py --system --verbose

# JSON output for automation
python tools\runner.py --all --json | ConvertFrom-Json

# Setup scripts
.\tools\setup\install-pytorch-cuda.ps1
.\tools\setup\install-ffmpeg.ps1
```

## Directory Structure

```
tools/
├── runner.py              # Unified interface for all tools
├── README.md              # This file
├── diagnostics/           # Health checks and diagnostics
│   ├── check-system.py    # System-wide diagnostics (CUDA, deps)
│   └── check-audio.py     # Audio device diagnostics
├── ci/                    # CI/Pre-commit checks
│   └── verify-fixes.py    # Bug fix verification
├── maintenance/           # Cleanup and maintenance
│   └── cleanup-logs.py    # Log file management
└── setup/                 # Installation scripts
    ├── install-pytorch-cuda.ps1
    └── install-ffmpeg.ps1
```

## Tools Reference

### runner.py

Unified interface for all tools. Replaces running individual scripts.

```bash
python tools/runner.py [options]

Options:
  --all       Run all diagnostics (system, audio, ci)
  --system    System diagnostics (CUDA, Python deps)
  --audio     Audio device diagnostics
  --ci        CI verification checks
  --cleanup   Log cleanup
  --json      JSON output
  --verbose   Detailed output
  --list      List available tools
```

### diagnostics/check-system.py

Comprehensive system diagnostics covering:
- **PyTorch CUDA availability** - Checks if PyTorch can use GPU acceleration
- **CTRANSLATE2 CUDA support** - Verifies CTranslate2 library CUDA integration
- **Faster-Whisper installation** - Checks faster-whisper backend availability
- **NVIDIA driver status** - Runs nvidia-smi to check driver installation
- **Environment variables** - Checks CUDA_PATH, CUDA_HOME, PATH configuration

```bash
python tools/diagnostics/check-system.py [--json] [--verbose]
```

**Example Output:**
```
==================================================
  System Diagnostics for Transcripta
==================================================
  Platform: win32
  Python: 3.12.1
  Executable: C:\Python312\python.exe

──────────────────────────────────────────────────
  PyTorch
──────────────────────────────────────────────────
  [✓] CUDA available             Yes
  [✓] CUDA version               12.1
  [✓] GPU count                  1
  [✓] Primary GPU                NVIDIA GeForce RTX 4090
  [✓] GPU Memory                 24.00 GB

==================================================
SUMMARY
==================================================
  [✓] pytorch_cuda: PASS
  [✓] ctranslate2_cuda: PASS
  [✓] faster_whisper: PASS
  [✓] nvidia_driver: PASS
  [✓] environment: PASS

  Critical: 3/3 passed
```

### diagnostics/check-audio.py

Audio device diagnostics covering:
- **Soundcard module** - Checks if soundcard Python library is installed
- **Device enumeration** - Lists all microphones and speakers
- **Default microphone** - Identifies and validates default input device
- **Loopback device detection** - Finds WASAPI loopback devices for system audio capture
- **Audio capture test** - Records and analyzes audio levels from selected device

```bash
python tools/diagnostics/check-audio.py [--json] [--verbose] [--test DEVICE_ID]
```

**Example Output:**
```
============================================================
  Audio Diagnostics for Transcripta
============================================================
  ✓ soundcard module installed

────────────────────────────────────────────────────────────
  Audio Devices
────────────────────────────────────────────────────────────
  [0] Microphone (Realtek(R) Audio)
      ID: {0.0.1.00000001}, Channels: 2
  [1] Microphone (NVIDIA High Definition Audio) [LOOPBACK]
      ID: {0.0.1.00000002}, Channels: 2
  [S0] Speakers (Realtek(R) Audio)
      ID: {0.0.0.00000001}, Channels: 2

  ✓ Found 1 loopback device(s)
    - Microphone (NVIDIA High Definition Audio)

============================================================
SUMMARY
============================================================
  [✓] soundcard_module: soundcard module available
  [✓] device_list: Found 3 audio device(s)
  [✓] default_microphone: Default: Microphone (Realtek(R) Audio)
  [✓] loopback_support: Found 1 loopback device(s)

  Critical: 2/2 passed
```

### ci/verify-fixes.py

Pre-commit verification for bug fixes:
- **Duplicate definitions** - Finds duplicate function/class definitions
- **Iterator imports** - Ensures Iterator imported from collections.abc (not typing)
- **Empty exception blocks** - Flags empty or pass-only except blocks
- **Thread safety** - Warns on threading code without locks
- **Resource cleanup** - Checks for proper file handle cleanup
- **Magic numbers** - Identifies hardcoded values that should be constants
- **Critical fix verification** - Ensures specific bug fixes remain in place

```bash
python tools/ci/verify-fixes.py [--json] [--strict]
```

### maintenance/cleanup-logs.py

Cleans up old log files and temporary data.

**Removes files matching:**
- `*.log`, `*.log.*` - Log files
- `logs/**/*` - Log directories
- `tmp/**/*` - Temporary files
- `__pycache__/**/*`, `*.pyc` - Python cache
- `.pytest_cache/**/*`, `.mypy_cache/**/*` - Tool caches

```bash
python tools/maintenance/cleanup-logs.py [--days 30] [--dry-run]
```

### setup/install-pytorch-cuda.ps1

PowerShell script to install PyTorch with CUDA support.

```powershell
.\tools\setup\install-pytorch-cuda.ps1
```

### setup/install-ffmpeg.ps1

Installs FFmpeg for audio processing (Windows).

```powershell
.\tools\setup\install-ffmpeg.ps1
```

## Exit Codes

All tools use consistent exit codes:

| Exit Code | Meaning |
|-----------|---------|
| `0` | Success - All checks passed |
| `1` | Failure - One or more checks failed |
| `124` | Timeout - Operation exceeded time limit |

**Examples:**
```bash
# Check exit code on Windows PowerShell
python tools/runner.py --system
$LASTEXITCODE

# Check exit code on Linux/macOS
python tools/runner.py --system
echo $?
```

## CLI Standards

All tools support:
- `--json` - Machine-readable JSON output for automation
- `--verbose` - Detailed human-readable output
- Consistent exit codes: 0 (success), 1 (failure)
- Standard headers and formatting

## JSON Output Format

When using `--json`, output follows this structure:

```json
{
  "success": true,
  "results": [
    {
      "name": "system",
      "passed": true,
      "exit_code": 0,
      "duration_ms": 2345.6,
      "output": "...",
      "error": null
    }
  ]
}
```

## Automation Examples

**Pre-commit hook:**
```bash
#!/bin/bash
python tools/runner.py --ci || exit 1
```

**CI/CD pipeline:**
```yaml
- name: Run diagnostics
  run: |
    python tools/runner.py --all --json > diagnostics.json
    if [ $? -ne 0 ]; then
      cat diagnostics.json | jq '.results[] | select(.passed == false)'
      exit 1
    fi
```

**Windows batch script:**
```batch
@echo off
python tools\runner.py --all
if %ERRORLEVEL% neq 0 (
    echo Diagnostics failed!
    exit /b 1
)
```
