#!/bin/bash
# SandiRaksa Linux Build Script
# Builds standalone Linux executable using Nuitka

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${1:-dist/linux}"

echo "========================================"
echo "  SandiRaksa Linux Build"
echo "========================================"

cd "$PROJECT_ROOT"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found"
    exit 1
fi

echo "Python: $(which python3)"

# Check/install Nuitka
if ! python3 -c "import nuitka" 2>/dev/null; then
    echo "Installing Nuitka..."
    pip3 install nuitka
fi

# Check for required system packages (Ubuntu/Debian)
if command -v apt-get &> /dev/null; then
    echo "Checking system dependencies..."
    # patchelf is required for Linux builds
    if ! command -v patchelf &> /dev/null; then
        echo "Installing patchelf..."
        sudo apt-get install -y patchelf
    fi
fi

# Clean if --clean flag is passed
if [[ "$2" == "--clean" ]]; then
    echo "Cleaning build artifacts..."
    rm -rf build dist
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Run build
echo "Building..."
python3 scripts/build_nuitka.py --platform linux --output "$OUTPUT_DIR"

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "  Build Successful!"
    echo "  Output: $OUTPUT_DIR/sandiraksa"
    echo "========================================"
    
    # Create desktop entry
    cat > "$OUTPUT_DIR/sandiraksa.desktop" << EOF
[Desktop Entry]
Name=SandiRaksa
Comment=Local Privacy Gateway for AI
Exec=$OUTPUT_DIR/sandiraksa
Icon=$OUTPUT_DIR/sandiraksa.png
Terminal=false
Type=Application
Categories=Utility;Security;
EOF
    
    echo "  Desktop entry: $OUTPUT_DIR/sandiraksa.desktop"
else
    echo ""
    echo "Build failed"
    exit 1
fi
