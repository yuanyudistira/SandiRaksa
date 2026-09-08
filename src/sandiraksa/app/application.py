"""
Main application class for SandiRaksa.

This module contains the Qt application setup and lifecycle management.
"""

from __future__ import annotations

import gc
import io
import os
import sys
from typing import TYPE_CHECKING

# Fix for PyInstaller --noconsole mode: sys.stdout/stderr may be None
# This must be done BEFORE importing any module that uses logging or faulthandler
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

import faulthandler

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from sandiraksa.version import __version__

if TYPE_CHECKING:
    from collections.abc import Sequence

# Enable faulthandler for better crash debugging (only if stderr is real)
if hasattr(sys.stderr, 'fileno'):
    try:
        faulthandler.enable()
    except (AttributeError, io.UnsupportedOperation):
        pass  # Skip if running in --noconsole mode

# Disable automatic garbage collection to prevent heap corruption with PySide6
# GC will be triggered manually during idle periods
gc.disable()


class SandiRaksaApp:
    """Main application class managing the Qt application lifecycle."""

    APP_NAME = "SandiRaksa"
    ORG_NAME = "SandiRaksa"
    ORG_DOMAIN = "sandiraksa.infosecguru.id"

    def __init__(self, argv: Sequence[str] | None = None) -> None:
        """
        Initialize the application.

        Args:
            argv: Command line arguments. If None, uses sys.argv.
        """
        self._argv = list(argv) if argv is not None else sys.argv
        self._app: QApplication | None = None
        self._main_window = None
        # Keep references to dialogs to prevent premature cleanup
        self._dialogs: list = []

    def _setup_application(self) -> QApplication:
        """Set up the Qt application with proper configuration."""
        # Enable high DPI scaling
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        app = QApplication(self._argv)
        app.setApplicationName(self.APP_NAME)
        app.setApplicationVersion(__version__)
        app.setOrganizationName(self.ORG_NAME)
        app.setOrganizationDomain(self.ORG_DOMAIN)

        return app

    def _initialize_services(self) -> None:
        """Initialize core application services."""
        # TODO: Initialize services in order:
        # 1. Config/settings
        # 2. Database
        # 3. Key store
        # 4. Localization
        pass

    def _create_main_window(self) -> None:
        """Create and configure the main window."""
        # Lazy import to avoid circular dependencies
        from sandiraksa.ui.main_window import MainWindow

        self._main_window = MainWindow()
        self._main_window.show()

    def run(self) -> int:
        """
        Run the application.

        Returns:
            Exit code from the application.
        """
        self._app = self._setup_application()
        self._initialize_services()
        self._create_main_window()

        result = self._app.exec()
        
        # Force exit to avoid PySide6 cleanup crash on Windows
        import sys
        sys.exit(result)

    def quit(self) -> None:
        """Quit the application gracefully."""
        if self._app is not None:
            self._app.quit()
