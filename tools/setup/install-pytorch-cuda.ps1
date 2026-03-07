#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Installs PyTorch with CUDA 12.1 support for OpenWispr.
.DESCRIPTION
    Activates the virtual environment, installs PyTorch with CUDA 12.1,
    verifies the installation, and updates requirements.txt with the
    CUDA-specific PyTorch index URL.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# Colors for output
$Green = "`e[32m"
$Red = "`e[31m"
$Yellow = "`e[33m"
$Cyan = "`e[36m"
$Reset = "`e[0m"

function Write-Step {
    param([string]$Message)
    Write-Host "${Cyan}[STEP]${Reset} $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "${Green}[SUCCESS]${Reset} $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "${Red}[ERROR]${Reset} $Message" -ForegroundColor Red
}

function Write-Warn {
    param([string]$Message)
    Write-Host "${Yellow}[WARN]${Reset} $Message" -ForegroundColor Yellow
}

# Get script directory and project root
# Script is at: tools/setup/install-pytorch-cuda.ps1
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ToolsDir = Split-Path -Parent $ScriptDir
$ProjectRoot = Split-Path -Parent $ToolsDir

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PyTorch CUDA 12.1 Installer" -ForegroundColor Cyan
Write-Host "  for OpenWispr" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
$VenvPath = Join-Path $ProjectRoot ".venv"
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"

if (-not (Test-Path $ActivateScript)) {
    Write-Error "Virtual environment not found at: $VenvPath"
    Write-Host ""
    Write-Host "Please create the virtual environment first:"
    Write-Host "  python -m venv .venv"
    Write-Host ""
    exit 1
}

# Step 1: Activate virtual environment
Write-Step "Activating virtual environment..."
try {
    & $ActivateScript
    Write-Success "Virtual environment activated"
} catch {
    Write-Error "Failed to activate virtual environment: $_"
    exit 1
}

# Step 2: Install PyTorch with CUDA 12.1
Write-Host ""
Write-Step "Installing PyTorch with CUDA 12.1 support..."
Write-Host "       This may take several minutes depending on your connection."
Write-Host ""

try {
    $InstallOutput = pip install torch==2.5.1 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed with exit code $LASTEXITCODE"
    }
    Write-Success "PyTorch CUDA packages installed successfully"
} catch {
    Write-Error "Failed to install PyTorch: $_"
    Write-Host ""
    Write-Host "Full output:"
    Write-Host $InstallOutput
    exit 1
}

# Step 3: Verify installation
Write-Host ""
Write-Step "Verifying PyTorch installation..."

try {
    $VerificationOutput = python -c "import torch; print(f'PyTorch version: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA version: {torch.version.cuda if torch.cuda.is_available() else \"N/A\"}')" 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        throw "Python verification failed with exit code $LASTEXITCODE"
    }
    
    Write-Host ""
    Write-Host $VerificationOutput
    Write-Host ""
    
    # Check if CUDA is available
    $CudaAvailable = python -c "import torch; print(torch.cuda.is_available())" 2>$null
    
    if ($CudaAvailable -eq "True") {
        Write-Success "CUDA is available! PyTorch can use your GPU."
    } else {
        Write-Warn "CUDA is NOT available. PyTorch will use CPU only."
        Write-Host ""
        Write-Host "Common causes:"
        Write-Host "  - NVIDIA GPU drivers not installed"
        Write-Host "  - CUDA toolkit not installed"
        Write-Host "  - No NVIDIA GPU detected"
        Write-Host ""
        Write-Host "You can still use OpenWispr, but transcription will be slower."
    }
} catch {
    Write-Error "Failed to verify PyTorch installation: $_"
    exit 1
}

# Step 4: Update requirements.txt
Write-Host ""
Write-Step "Updating requirements.txt with CUDA-specific PyTorch URL..."

$RequirementsPath = Join-Path $ProjectRoot "requirements.txt"

if (Test-Path $RequirementsPath) {
    $RequirementsContent = Get-Content $RequirementsPath -Raw
    
    # Check if already updated with CUDA index
    if ($RequirementsContent -match "download.pytorch.org/whl/cu121") {
        Write-Warn "requirements.txt already contains CUDA 12.1 index URL"
    } else {
        # Remove existing torch entries
        $Lines = $RequirementsContent -split "`r?`n"
        $FilteredLines = $Lines | Where-Object { $_ -notmatch "^torch==" -and $_ -notmatch "^torchaudio==" -and $_ -notmatch "^torchvision==" }
        
        # Create new content with CUDA index URL
        $NewContent = @()
        
        # Add the index URL before torch packages
        $NewContent += "# PyTorch with CUDA 12.1"
        $NewContent += "--index-url https://download.pytorch.org/whl/cu121"
        $NewContent += "torch==2.5.1"
        $NewContent += "torchvision"
        $NewContent += "torchaudio"
        $NewContent += ""
        $NewContent += $FilteredLines | Where-Object { $_.Trim() -ne "" }
        
        # Write back to file
        $NewContent -join "`n" | Set-Content $RequirementsPath -NoNewline
        
        Write-Success "requirements.txt updated with CUDA 12.1 index URL"
    }
} else {
    Write-Warn "requirements.txt not found at: $RequirementsPath"
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Success "PyTorch CUDA 12.1 installation complete!"
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Run 'npm run dev' to start OpenWispr"
Write-Host "  2. Check the Settings panel to confirm GPU is detected"
Write-Host ""

exit 0
