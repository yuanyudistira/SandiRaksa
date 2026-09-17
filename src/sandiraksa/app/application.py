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

# Fix for PyInstaller --noconsole mode: sys.stdout/stderr may be None.
#
# This MUST run before importing any module that uses logging or faulthandler.
#
# We deliberately do NOT use io.StringIO() here. In a --noconsole build the
# whole app writes to these streams via scattered print("DEBUG: ...") calls,
# including from the background ScanWorker (a QThread) AND the GUI thread at the
# same time. io.StringIO() is (a) unbounded, so captured output grows forever
# (a slow memory leak), and (b) NOT thread-safe, so concurrent writes from the
# worker and GUI threads can corrupt its internal state and intermittently hang
# or crash the frozen app. A stateless sink that discards everything avoids
# both problems: nothing accumulates and there is no shared mutable state to
# corrupt across threads.
class _NullWriter:
    """Thread-safe no-op stream: discards all writes, keeps no state."""

    def write(self, _data):  # noqa: D401 - file-like API
        return 0

    def flush(self):
        pass

    def isatty(self):
        return False


if sys.stdout is None:
    sys.stdout = _NullWriter()
if sys.stderr is None:
    sys.stderr = _NullWriter()

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

# Root-cause fix for STATUS_HEAP_CORRUPTION (0xC0000374).
#
# This app mixes Python's non-deterministic cyclic GC with PySide6/Qt objects
# whose C++ lifetime is owned by Qt (parent/child, deleteLater). When the
# automatic collector runs at an arbitrary point inside the Qt event loop it
# can finalize a Python wrapper whose underlying C++ object Qt already
# destroyed (or is mid-teardown) -> use-after-free that Windows reports as heap
# corruption. It surfaced at many points (opening a TXT file, closing a preview
# dialog, creating a project) because it is timing-dependent, not per-handler.
#
# TEMPORARY MITIGATION (Path A): running the cyclic collector at all - whether
# automatically or via an explicit gc.collect() - has been observed to trip the
# 0xC0000374 heap corruption, which means some object graph holds a Python
# wrapper over an already-freed Qt C++ object. Until that root cause (introduced
# with the Clipboard Guard after v1.0.4) is fixed, we disable automatic
# collection here AND avoid manual gc.collect() elsewhere. This trades a small
# risk of cyclic-garbage retention for stability. See the scan/protect workers.
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
        """Initialize core application services on the main thread.

        Critically, we pre-load the shared spaCy/Presidio analyzer HERE, on the
        main thread, before any background worker can run. Loading the spaCy
        model on a worker QThread during file protection crashed the app with
        0xC0000374 (heap corruption in spaCy's from_disk). Loading it once on
        the main thread means workers only ever reuse the ready analyzer.
        """
        try:
            from sandiraksa.detection.presidio_engine import preload_shared_analyzer

            preload_shared_analyzer()
        except Exception as e:  # pragma: no cover - environment dependent
            logger.warning(f"Presidio preload skipped: {e}")

        # CRITICAL: spaCy/Presidio (and some other native libs) re-enable the
        # cyclic garbage collector during their initialization. We rely on GC
        # staying OFF (running it corrupts the heap - 0xC0000374 - while native
        # extensions like spaCy/lxml/openpyxl are mid-operation). Force it back
        # off after any such init so the mitigation actually holds.
        if gc.isenabled():
            gc.disable()
            logger.info("Re-disabled GC after NLP init (kept off for stability)")

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
        
        # Hard-exit to sidestep occasional PySide6/Qt teardown crashes on
        # Windows during interpreter shutdown (general safeguard, unrelated to
        # the scan-thread fix).
        import sys
        sys.exit(result)

    def quit(self) -> None:
        """Quit the application gracefully."""
        if self._app is not None:
            self._app.quit()
