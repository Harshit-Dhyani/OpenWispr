# Transcripta Helper Scripts

This directory contains utility scripts for setting up and diagnosing the Transcripta application.

## Available Scripts

### `check_cuda.py`

Comprehensive CUDA diagnostic tool that verifies all transcription dependencies have working CUDA support.

**What it checks:**
- PyTorch CUDA availability and GPU memory
- CTranslate2 CUDA device count
- Faster-Whisper installation and compute types
- Environment variables (CUDA_PATH, etc.)
- NVIDIA driver status via `nvidia-smi`
- CUDA toolkit installation

**Usage:**
```powershell
# From project root
python scripts/check_cuda.py

# Or from scripts directory
python check_cuda.py
```

**Exit codes:**
- `0` - All CUDA components properly configured
- `1` - One or more CUDA issues detected (see recommendations in output)

---

### `install_pytorch_cuda.ps1`

PowerShell script to install PyTorch with CUDA 12.1 support for GPU-accelerated transcription.

**What it does:**
1. Activates the virtual environment (`.venv`)
2. Installs PyTorch, torchvision, and torchaudio with CUDA 12.1
3. Verifies the installation detects CUDA
4. Updates `requirements.txt` with the CUDA-specific index URL

**Prerequisites:**
- Virtual environment created at `.venv`
- NVIDIA GPU drivers installed
- PowerShell execution policy allows scripts (or run with bypass)

**Usage:**
```powershell
# From project root
.\scripts\install_pytorch_cuda.ps1

# If execution policy blocks scripts
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\install_pytorch_cuda.ps1
```

**Notes:**
- The script automatically detects the project root from its location
- If CUDA is not available after installation, the script will warn but complete
- You can still use Transcripta in CPU-only mode if CUDA setup fails

---

## Quick Setup Flow

For a fresh Windows 11 installation with NVIDIA GPU:

```powershell
# 1. Create virtual environment
python -m venv .venv

# 2. Activate it
.\.venv\Scripts\Activate.ps1

# 3. Install base dependencies
pip install -e .[dev]

# 4. Install PyTorch with CUDA
.\scripts\install_pytorch_cuda.ps1

# 5. Verify CUDA is working
python scripts\check_cuda.py

# 6. Start the application
cd app/desktop
npm install
npm run dev
```

## Troubleshooting

### Script won't run (execution policy)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Virtual environment not found

Ensure `.venv` exists at the project root:
```powershell
python -m venv .venv
```

### CUDA install fails

1. Verify NVIDIA drivers: `nvidia-smi`
2. Check GPU compatibility (RTX 20 series+ recommended)
3. Try CPU fallback: `pip install torch torchvision torchaudio`
4. Run `python scripts/check_cuda.py` for detailed diagnostics
