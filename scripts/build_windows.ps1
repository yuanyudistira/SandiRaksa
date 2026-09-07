# build_windows.ps1 - Build SandiRaksa for Windows
# Usage: .\scripts\build_windows.ps1

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SandiRaksa Windows Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to project root
Set-Location $ProjectRoot

# Check Python version
Write-Host "[1/5] Checking Python version..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
Write-Host "  Python: $pythonVersion"

if ($pythonVersion -notmatch "3\.(11|12|13)") {
    Write-Host "  WARNING: Python 3.11+ recommended" -ForegroundColor Yellow
}

# Install dependencies
Write-Host "[2/5] Installing dependencies..." -ForegroundColor Yellow
pip install -e . --quiet
pip install pyinstaller --quiet
Write-Host "  Dependencies installed"

# Clean previous builds
Write-Host "[3/5] Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "*.spec") { Remove-Item -Force "*.spec" }
Write-Host "  Cleaned"

# Build executable
Write-Host "[4/5] Building executable (this may take several minutes)..." -ForegroundColor Yellow
pyinstaller --name SandiRaksa `
    --windowed `
    --onefile `
    --add-data "src/sandiraksa/resources;sandiraksa/resources" `
    --hidden-import=PySide6.QtSvg `
    --hidden-import=PySide6.QtXml `
    --hidden-import=presidio_analyzer `
    --hidden-import=presidio_anonymizer `
    --hidden-import=spacy `
    --hidden-import=openpyxl `
    --hidden-import=docx `
    --hidden-import=pptx `
    --hidden-import=cryptography `
    --hidden-import=keyring `
    --hidden-import=charset_normalizer `
    --collect-all=presidio_analyzer `
    --collect-all=spacy `
    --noconfirm `
    src/sandiraksa/__main__.py

# Check result
Write-Host "[5/5] Checking build result..." -ForegroundColor Yellow
$exePath = "dist\SandiRaksa.exe"

if (Test-Path $exePath) {
    $fileInfo = Get-Item $exePath
    $sizeMB = [math]::Round($fileInfo.Length / 1MB, 2)
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  BUILD SUCCESSFUL!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Output: $exePath" -ForegroundColor White
    Write-Host "  Size: $sizeMB MB" -ForegroundColor White
    Write-Host ""
    Write-Host "  To run: .\dist\SandiRaksa.exe" -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  BUILD FAILED!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Check the error messages above." -ForegroundColor Yellow
    exit 1
}
