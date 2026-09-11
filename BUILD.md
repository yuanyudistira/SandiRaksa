# Build Guide - SandiRaksa

Panduan untuk membuild SandiRaksa menjadi aplikasi standalone executable.

## 🚀 Quick Release (Recommended)

Cara termudah untuk release adalah menggunakan **GitHub Actions**:

```bash
# 1. Update version di version.py dan pyproject.toml
# 2. Update CHANGELOG.md
# 3. Commit dan push

git add .
git commit -m "Release v0.2.0"
git tag v0.2.0
git push origin main --tags
```

GitHub Actions akan otomatis:
- ✅ Build Windows executable (.exe)
- ✅ Build macOS Intel DMG
- ✅ Build macOS Apple Silicon DMG
- ✅ Create GitHub Release dengan semua artifacts

Download dari: https://github.com/yuanyudistira/sandiraksa/releases

---

## Manual Build

## Prerequisites

### Semua Platform
- Python 3.11 atau 3.12
- Git
- pip (Python package manager)

### Windows Specific
- Visual Studio Build Tools 2022 (untuk Nuitka)
- Windows 10/11

### macOS Specific
- Xcode Command Line Tools
- macOS 11 (Big Sur) atau lebih baru

---

## Method 1: PyInstaller (Recommended - Lebih Mudah)

### Install PyInstaller

```bash
pip install pyinstaller
```

### Build untuk Windows

```powershell
# Clone repository
git clone https://github.com/yuanyudistira/sandiraksa.git
cd sandiraksa

# Install dependencies
pip install -e .

# Build executable
pyinstaller --name SandiRaksa ^
    --windowed ^
    --onefile ^
    --icon=src/sandiraksa/resources/icons/app.ico ^
    --add-data "src/sandiraksa/resources;sandiraksa/resources" ^
    --hidden-import=PySide6.QtSvg ^
    --hidden-import=PySide6.QtXml ^
    --hidden-import=presidio_analyzer ^
    --hidden-import=presidio_anonymizer ^
    --hidden-import=spacy ^
    --hidden-import=openpyxl ^
    --hidden-import=docx ^
    --hidden-import=pptx ^
    src/sandiraksa/__main__.py

# Output: dist/SandiRaksa.exe
```

### Build untuk macOS

```bash
# Clone repository
git clone https://github.com/yuanyudistira/sandiraksa.git
cd sandiraksa

# Install dependencies
pip install -e .

# Build executable
pyinstaller --name SandiRaksa \
    --windowed \
    --onefile \
    --icon=src/sandiraksa/resources/icons/app.icns \
    --add-data "src/sandiraksa/resources:sandiraksa/resources" \
    --hidden-import=PySide6.QtSvg \
    --hidden-import=PySide6.QtXml \
    --hidden-import=presidio_analyzer \
    --hidden-import=presidio_anonymizer \
    --hidden-import=spacy \
    --hidden-import=openpyxl \
    --hidden-import=docx \
    --hidden-import=pptx \
    --osx-bundle-identifier=id.infosecguru.sandiraksa \
    src/sandiraksa/__main__.py

# Output: dist/SandiRaksa.app
```

---

## Method 2: Nuitka (Lebih Optimal - Lebih Kompleks)

Nuitka mengcompile Python ke C untuk performa lebih baik.

### Install Nuitka

```bash
pip install nuitka ordered-set zstandard
```

### Build untuk Windows

```powershell
# Pastikan Visual Studio Build Tools terinstall
# Download dari: https://visualstudio.microsoft.com/visual-cpp-build-tools/

python -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico=src/sandiraksa/resources/icons/app.ico ^
    --include-data-dir=src/sandiraksa/resources=sandiraksa/resources ^
    --enable-plugin=pyside6 ^
    --include-package=presidio_analyzer ^
    --include-package=presidio_anonymizer ^
    --include-package=spacy ^
    --include-package=openpyxl ^
    --include-package=docx ^
    --include-package=pptx ^
    --output-filename=SandiRaksa.exe ^
    src/sandiraksa/__main__.py

# Output: SandiRaksa.exe
```

### Build untuk macOS

```bash
python -m nuitka \
    --standalone \
    --onefile \
    --macos-create-app-bundle \
    --macos-app-icon=src/sandiraksa/resources/icons/app.icns \
    --include-data-dir=src/sandiraksa/resources=sandiraksa/resources \
    --enable-plugin=pyside6 \
    --include-package=presidio_analyzer \
    --include-package=presidio_anonymizer \
    --include-package=spacy \
    --include-package=openpyxl \
    --include-package=docx \
    --include-package=pptx \
    --output-filename=SandiRaksa \
    src/sandiraksa/__main__.py

# Output: SandiRaksa.app
```

---

## Method 3: cx_Freeze (Alternative)

### Install cx_Freeze

```bash
pip install cx_Freeze
```

### Buat setup.py

```python
# setup_build.py
from cx_Freeze import setup, Executable
import sys

build_exe_options = {
    "packages": [
        "PySide6",
        "presidio_analyzer",
        "presidio_anonymizer", 
        "spacy",
        "openpyxl",
        "docx",
        "pptx",
        "sandiraksa",
    ],
    "include_files": [
        ("src/sandiraksa/resources", "sandiraksa/resources"),
    ],
    "excludes": ["tkinter", "unittest"],
}

base = "Win32GUI" if sys.platform == "win32" else None

setup(
    name="SandiRaksa",
    version="0.2.0",
    description="Local Privacy Gateway for AI",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "src/sandiraksa/__main__.py",
            base=base,
            target_name="SandiRaksa",
            icon="src/sandiraksa/resources/icons/app.ico",
        )
    ],
)
```

### Build

```bash
python setup_build.py build
```

---

## Troubleshooting

### Windows: "vcruntime140.dll not found"
Install Microsoft Visual C++ Redistributable:
https://aka.ms/vs/17/release/vc_redist.x64.exe

### Windows: Antivirus false positive
PyInstaller executables sering terdeteksi false positive. Sign executable dengan code signing certificate atau submit ke antivirus vendor untuk whitelist.

### macOS: "App is damaged"
```bash
# Clear quarantine attribute
xattr -cr /path/to/SandiRaksa.app
```

### macOS: Gatekeeper blocking
```bash
# Allow app from unidentified developer
sudo spctl --master-disable  # Temporary, not recommended
# Or right-click app > Open > Open anyway
```

### Missing spaCy model
Jika ada error tentang spaCy model:
```bash
python -m spacy download en_core_web_sm
```

### Large executable size
PySide6 dan spaCy membuat executable besar (200-500MB). Ini normal.
Untuk ukuran lebih kecil, pertimbangkan:
- Gunakan `--onedir` bukan `--onefile`
- Exclude unused Qt modules
- Gunakan spaCy model yang lebih kecil

---

## Creating Installer

### Windows - NSIS Installer

1. Download NSIS: https://nsis.sourceforge.io/
2. Buat script installer (lihat `installer/windows/installer.nsi`)
3. Compile dengan NSIS

### Windows - Inno Setup

1. Download Inno Setup: https://jrsoftware.org/isinfo.php
2. Buat script `.iss`
3. Compile

### macOS - DMG

```bash
# Install create-dmg
brew install create-dmg

# Create DMG
create-dmg \
    --volname "SandiRaksa" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --app-drop-link 450 185 \
    "SandiRaksa-0.2.0.dmg" \
    "dist/SandiRaksa.app"
```

---

## Quick Build Script

### Windows (build.ps1)

```powershell
# build.ps1
$ErrorActionPreference = "Stop"

Write-Host "Installing dependencies..."
pip install -e . pyinstaller

Write-Host "Building executable..."
pyinstaller --name SandiRaksa `
    --windowed `
    --onefile `
    --add-data "src/sandiraksa/resources;sandiraksa/resources" `
    --hidden-import=PySide6.QtSvg `
    --hidden-import=presidio_analyzer `
    --hidden-import=openpyxl `
    --hidden-import=docx `
    --hidden-import=pptx `
    src/sandiraksa/__main__.py

Write-Host "Done! Output: dist/SandiRaksa.exe"
```

### macOS/Linux (build.sh)

```bash
#!/bin/bash
set -e

echo "Installing dependencies..."
pip install -e . pyinstaller

echo "Building executable..."
pyinstaller --name SandiRaksa \
    --windowed \
    --onefile \
    --add-data "src/sandiraksa/resources:sandiraksa/resources" \
    --hidden-import=PySide6.QtSvg \
    --hidden-import=presidio_analyzer \
    --hidden-import=openpyxl \
    --hidden-import=docx \
    --hidden-import=pptx \
    src/sandiraksa/__main__.py

echo "Done! Output: dist/SandiRaksa"
```

---

## Version Info

- SandiRaksa: 0.2.0
- Python: 3.11+
- PySide6: 6.6+
- Build Date: September 2026


---

## 🔏 Signed Release Setup (SignPath) — one-time manual steps

The signed Windows release runs via `.github/workflows/release-windows.yml`
(triggered by a `v*` tag). It builds the app, signs the EXE, builds the
installer, signs the installer, verifies signatures, generates a checksum, and
publishes the GitHub Release. Before the first signed release, complete these
**manual** steps (they cannot be automated in this repo):

### B2 — SignPath Foundation onboarding

1. Apply to SignPath Foundation (free OSS code signing). Approval is manual and
   can take several days — the repo must be public with an OSI license (MIT ✓).
2. Authorize the SignPath GitHub App for this repository.
3. Set **Trusted Build System = GitHub.com**.
4. Create a SignPath project **SandiRaksa** with:
   - Signing policy: `release-signing` (enable required approval).
   - Artifact config `windows-app-v1` — signs `SandiRaksa.exe` inside the
     GitHub artifact ZIP.
   - Artifact config `windows-installer-v1` — signs
     `SandiRaksa-Setup-<version>.exe` inside the artifact ZIP.
5. Obtain the CI **API token**.

### B3 — GitHub environment, secret, and variables

Create an Environment named **`production-signing`** (Settings → Environments)
with a **required reviewer**, then add:

| Kind | Name | Example value |
|------|------|---------------|
| Secret | `SIGNPATH_API_TOKEN` | *(from SignPath)* |
| Variable | `SIGNPATH_ORGANIZATION_ID` | *(from SignPath)* |
| Variable | `SIGNPATH_PROJECT_SLUG` | `SandiRaksa` |
| Variable | `SIGNPATH_SIGNING_POLICY_SLUG` | `release-signing` |
| Variable | `SIGNPATH_APP_ARTIFACT_CONFIG_SLUG` | `windows-app-v1` |
| Variable | `SIGNPATH_INSTALLER_ARTIFACT_CONFIG_SLUG` | `windows-installer-v1` |

Never commit a signing key (`*.pfx`, `*.p12`, private keys). The workflow only
holds the API token, and only inside the protected `production-signing`
environment.

### Cutting a signed release

```bash
# bump version in pyproject.toml and src/sandiraksa/version.py first
git tag v1.1.0
git push origin v1.1.0
```

The tag triggers `release-windows.yml`; approve the `production-signing`
deployment when prompted. The old `release.yml` is retired to manual-only
(`workflow_dispatch`) and no longer fires on tags, so only the signed pipeline
runs on a `v*` tag.

> **SmartScreen:** a valid signature fixes the "unknown publisher" warning but
> does not guarantee zero SmartScreen prompts on day one — reputation builds
> over time. Never instruct users to disable SmartScreen.
