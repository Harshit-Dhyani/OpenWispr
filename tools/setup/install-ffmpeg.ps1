#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Installs FFmpeg for OpenWispr audio processing.
.DESCRIPTION
    Downloads and installs FFmpeg for Windows if not already present.
    Adds FFmpeg to PATH if needed.
#>

[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# Colors
$Green = "`e[32m"
$Red = "`e[31m"
$Yellow = "`e[33m"
$Cyan = "`e[36m"
$Reset = "`e[0m"

function Write-Step { param([string]$Message) Write-Host "${Cyan}[STEP]${Reset} $Message" -ForegroundColor Cyan }
function Write-Success { param([string]$Message) Write-Host "${Green}[SUCCESS]${Reset} $Message" -ForegroundColor Green }
function Write-Error { param([string]$Message) Write-Host "${Red}[ERROR]${Reset} $Message" -ForegroundColor Red }
function Write-Warn { param([string]$Message) Write-Host "${Yellow}[WARN]${Reset} $Message" -ForegroundColor Yellow }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  FFmpeg Installer for OpenWispr" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if FFmpeg is already installed
Write-Step "Checking for existing FFmpeg installation..."
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue

if ($ffmpeg -and -not $Force) {
    Write-Success "FFmpeg already installed at: $($ffmpeg.Source)"
    & ffmpeg -version | Select-Object -First 1
    exit 0
}

# Download URL for FFmpeg (Windows 64-bit static build)
$FFmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$InstallDir = "$env:LOCALAPPDATA\FFmpeg"

Write-Step "Downloading FFmpeg..."
Write-Host "  URL: $FFmpegUrl"
Write-Host "  Destination: $InstallDir"

# Create install directory
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# Download
$ZipPath = "$env:TEMP\ffmpeg.zip"
try {
    Invoke-WebRequest -Uri $FFmpegUrl -OutFile $ZipPath -UseBasicParsing
    Write-Success "Download complete"
} catch {
    Write-Error "Failed to download FFmpeg: $_"
    exit 1
}

# Extract
Write-Step "Extracting..."
try {
    Expand-Archive -Path $ZipPath -DestinationPath $InstallDir -Force
    Remove-Item $ZipPath
    Write-Success "Extraction complete"
} catch {
    Write-Error "Failed to extract FFmpeg: $_"
    exit 1
}

# Find ffmpeg.exe
$ffmpegExe = Get-ChildItem -Path $InstallDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1

if (-not $ffmpegExe) {
    Write-Error "Could not find ffmpeg.exe after extraction"
    exit 1
}

$binDir = $ffmpegExe.DirectoryName

# Add to PATH
Write-Step "Adding to PATH..."
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($currentPath -notlike "*$binDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$binDir", "User")
    Write-Success "Added to PATH (restart terminal to use)"
} else {
    Write-Warn "Already in PATH"
}

# Verify
Write-Step "Verifying installation..."
& "$($ffmpegExe.FullName)" -version | Select-Object -First 1

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Success "FFmpeg installation complete!"
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Location: $binDir"
Write-Host ""
Write-Host "Note: Restart your terminal to use ffmpeg from PATH"
Write-Host ""
