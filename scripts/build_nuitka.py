#!/usr/bin/env python3
"""
Nuitka Build Script for SandiRaksa.

Builds standalone executables for Windows, macOS, and Linux.

Usage:
    python scripts/build_nuitka.py [--platform PLATFORM] [--output DIR]

Platforms: windows, macos, linux, auto (detect current)
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"


def get_platform() -> str:
    """Detect current platform."""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def get_nuitka_args(target_platform: str, output_dir: Path) -> list[str]:
    """Get Nuitka command-line arguments for the target platform."""
    args = [
        sys.executable,
        "-m", "nuitka",
        # Core options
        "--standalone",
        "--onefile",
        f"--output-dir={output_dir}",
        # Product info
        "--product-name=SandiRaksa",
        "--product-version=0.1.0",
        "--company-name=SandiRaksa",
        "--file-description=Local Privacy Gateway for AI",
        "--copyright=Copyright 2024 SandiRaksa Team",
        # Qt/PySide6 support
        "--enable-plugin=pyside6",
        "--include-qt-plugins=sensible,styles,platforms,imageformats",
        # Include packages
        "--include-package=sandiraksa",
        "--include-package=presidio_analyzer",
        "--include-package=presidio_anonymizer",
        "--include-package=spacy",
        "--include-package=openpyxl",
        "--include-package=docx",
        "--include-package=pptx",
        "--include-package=lxml",
        "--include-package=cryptography",
        "--include-package=keyring",
        "--include-package=pydantic",
        # Data files
        "--include-data-dir=src/sandiraksa/resources=sandiraksa/resources",
        "--include-data-dir=src/sandiraksa/config=sandiraksa/config",
        "--include-data-dir=src/sandiraksa/storage/migrations=sandiraksa/storage/migrations",
        # Optimizations
        "--assume-yes-for-downloads",
        "--remove-output",
        # Disable console for GUI app
        "--disable-console",
    ]

    # Platform-specific options
    if target_platform == "windows":
        # Check if icon exists
        icon_path = PROJECT_ROOT / "src/sandiraksa/resources/icons/sandiraksa.ico"
        if icon_path.exists():
            args.append(f"--windows-icon-from-ico={icon_path}")
        args.append("--output-filename=SandiRaksa.exe")
    elif target_platform == "macos":
        icon_path = PROJECT_ROOT / "src/sandiraksa/resources/icons/sandiraksa.icns"
        args.append("--macos-create-app-bundle")
        if icon_path.exists():
            args.append(f"--macos-app-icon={icon_path}")
        args.extend([
            "--macos-app-name=SandiRaksa",
            "--output-filename=SandiRaksa",
        ])
    else:  # linux
        icon_path = PROJECT_ROOT / "src/sandiraksa/resources/icons/sandiraksa.png"
        if icon_path.exists():
            args.append(f"--linux-icon={icon_path}")
        args.append("--output-filename=sandiraksa")

    # Entry point
    args.append("src/sandiraksa/__main__.py")

    return args


def build(target_platform: str, output_dir: Path) -> int:
    """Run Nuitka build."""
    print(f"[BUILD] Building SandiRaksa for {target_platform}...")
    print(f"        Output directory: {output_dir}")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get Nuitka arguments
    args = get_nuitka_args(target_platform, output_dir)

    print(f"\n        Running: {' '.join(args[:5])}...")

    # Run Nuitka
    try:
        result = subprocess.run(
            args,
            cwd=PROJECT_ROOT,
            check=True,
        )
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Build failed with exit code {e.returncode}")
        return e.returncode
    except FileNotFoundError:
        print("[ERROR] Nuitka not found. Install with: pip install nuitka")
        return 1


def clean_build() -> None:
    """Clean build artifacts."""
    print("[CLEAN] Cleaning build artifacts...")

    for directory in [BUILD_DIR, DIST_DIR]:
        if directory.exists():
            shutil.rmtree(directory)
            print(f"        Removed {directory}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build SandiRaksa with Nuitka"
    )
    parser.add_argument(
        "--platform",
        choices=["windows", "macos", "linux", "auto"],
        default="auto",
        help="Target platform (default: auto-detect)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DIST_DIR,
        help=f"Output directory (default: {DIST_DIR})",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean build artifacts before building",
    )

    args = parser.parse_args()

    # Determine target platform
    target_platform = args.platform
    if target_platform == "auto":
        target_platform = get_platform()

    # Clean if requested
    if args.clean:
        clean_build()

    # Run build
    return build(target_platform, args.output)


if __name__ == "__main__":
    sys.exit(main())
