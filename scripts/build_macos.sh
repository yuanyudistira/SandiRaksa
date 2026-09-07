#!/bin/bash
# build_macos.sh - Build SandiRaksa for macOS
# Usage: ./scripts/build_macos.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "  SandiRaksa macOS Build Script"
echo "========================================"
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Check Python version
echo "[1/5] Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1)
echo "  Python: $PYTHON_VERSION"

# Install dependencies
echo "[2/5] Installing dependencies..."
pip3 install -e . --quiet
pip3 install pyinstaller --quiet
echo "  Dependencies installed"

# Clean previous builds
echo "[3/5] Cleaning previous builds..."
rm -rf dist build *.spec
echo "  Cleaned"

# Build executable
echo "[4/5] Building executable (this may take several minutes)..."
pyinstaller --name SandiRaksa \
    --windowed \
    --onefile \
    --add-data "src/sandiraksa/resources:sandiraksa/resources" \
    --hidden-import=PySide6.QtSvg \
    --hidden-import=PySide6.QtXml \
    --hidden-import=presidio_analyzer \
    --hidden-import=presidio_anonymizer \
    --hidden-import=spacy \
    --hidden-import=openpyxl \
    --hidden-import=docx \
    --hidden-import=pptx \
    --hidden-import=cryptography \
    --hidden-import=keyring \
    --hidden-import=charset_normalizer \
    --collect-all=presidio_analyzer \
    --collect-all=spacy \
    --osx-bundle-identifier=id.infosecguru.sandiraksa \
    --noconfirm \
    src/sandiraksa/__main__.py

# Check result
echo "[5/5] Checking build result..."

if [ -f "dist/SandiRaksa" ] || [ -d "dist/SandiRaksa.app" ]; then
    if [ -d "dist/SandiRaksa.app" ]; then
        APP_PATH="dist/SandiRaksa.app"
        SIZE=$(du -sh "$APP_PATH" | cut -f1)
    else
        APP_PATH="dist/SandiRaksa"
        SIZE=$(ls -lh "$APP_PATH" | awk '{print $5}')
    fi
    
    echo ""
    echo "========================================"
    echo "  BUILD SUCCESSFUL!"
    echo "========================================"
    echo ""
    echo "  Output: $APP_PATH"
    echo "  Size: $SIZE"
    echo ""
    echo "  To run: open $APP_PATH"
    echo ""
    
    # Clear quarantine attribute
    echo "  Clearing quarantine attribute..."
    xattr -cr "$APP_PATH" 2>/dev/null || true
    echo "  Done"
    echo ""
else
    echo ""
    echo "========================================"
    echo "  BUILD FAILED!"
    echo "========================================"
    echo ""
    echo "  Check the error messages above."
    exit 1
fi
