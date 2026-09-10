"""
Main application class for SandiRaksa.

This module contains the Qt application setup and lifecycle management.
"""

from __future__ import annotations

import gc
import io
import logging
import os
import sys
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

# Fix for PyInstaller --noconsole mode: sys.stdout/stderr may be None
# This must be done BEFORE importing any module that uses logging or faulthandler
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

import faulthandler

from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QIcon, QPixmap
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
        self._splash: QSplashScreen | None = None
        # Keep references to dialogs to prevent premature cleanup
        self._dialogs: list = []

    def _set_app_user_model_id(self) -> None:
        """
        Set the Windows AppUserModelID so the taskbar uses our own icon.

        Without an explicit AUMID, Windows groups the process under the host
        (e.g. python.exe) and shows that host's icon in the taskbar instead of
        the application icon. No-op on non-Windows platforms.
        """
        if sys.platform != "win32":
            return
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "SandiRaksa.App"
            )
        except Exception as e:
            logger.warning(f"Could not set AppUserModelID: {e}")

    def _setup_application(self) -> QApplication:
        """Set up the Qt application with proper configuration."""
        # Must run before the QApplication/first window so Windows groups the
        # app under our own taskbar icon (not python.exe).
        self._set_app_user_model_id()

        # Enable high DPI scaling
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        app = QApplication(self._argv)
        app.setApplicationName(self.APP_NAME)
        app.setApplicationVersion(__version__)
        app.setOrganizationName(self.ORG_NAME)
        app.setOrganizationDomain(self.ORG_DOMAIN)

        # Application-wide window / taskbar icon.
        try:
            from sandiraksa.resources import app_icon_path

            icon = app_icon_path()
            if icon.exists():
                app.setWindowIcon(QIcon(str(icon)))
        except Exception as e:
            logger.warning(f"Could not set window icon: {e}")

        return app

    def _show_splash(self) -> None:
        """Show a splash screen while the main window initializes."""
        try:
            from sandiraksa.resources import splash_image_path

            path = splash_image_path()
            if not path.exists():
                return
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                return
            # Cap very large splash images to a sensible on-screen size.
            if pixmap.width() > 700:
                pixmap = pixmap.scaledToWidth(
                    700, Qt.TransformationMode.SmoothTransformation
                )
            self._splash = QSplashScreen(pixmap, Qt.WindowType.WindowStaysOnTopHint)
            self._splash.show()
            if self._app is not None:
                self._app.processEvents()
        except Exception as e:
            logger.warning(f"Could not show splash screen: {e}")

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
        self._show_splash()
        self._initialize_services()
        self._create_main_window()

        # Dismiss the splash once the main window is up.
        if self._splash is not None and self._main_window is not None:
            self._splash.finish(self._main_window)
            self._splash = None

        result = self._app.exec()
        
        # Force exit to avoid PySide6 cleanup crash on Windows
        import sys
        sys.exit(result)

    def quit(self) -> None:
        """Quit the application gracefully."""
        if self._app is not None:
            self._app.quit()
