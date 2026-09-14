"""
Shared Qt clipboard backend for platforms where ``QClipboard.dataChanged``
is a reliable background event source (Windows and Linux/X11 - design 12, 14).

This backend:
  * observes only the Clipboard selection, never the X11 PRIMARY selection
    (design 14), since PRIMARY changes on mere text selection;
  * enforces the MIME policy - plain text, or plain text derived from HTML,
    ignoring images/files/binary (design 21);
  * replaces the ENTIRE payload on write, attaching only protected plain text
    plus the origin marker (design 22, 20).

All methods must run on the GUI thread (design 5.3).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QGuiApplication, QClipboard

from sandiraksa.clipboard.backends.base import (
    MIME_HTML,
    MIME_PLAIN,
    ORIGIN_MARKER_MIME,
    ClipboardBackend,
    OnChangeCallback,
)
from sandiraksa.clipboard.backends.html_text import html_to_plain_text
from sandiraksa.clipboard.fingerprint import fingerprint_text
from sandiraksa.clipboard.models import ClipboardCapability

logger = logging.getLogger(__name__)


class QtClipboardBackend(ClipboardBackend):
    """Qt ``dataChanged``-based backend (shared by Windows and X11)."""

    def __init__(self) -> None:
        self._on_change: OnChangeCallback | None = None
        self._connected = False

    # -- capability ------------------------------------------------------
    def capability(self) -> ClipboardCapability:
        # Both Windows and X11 support reliable background observation.
        return ClipboardCapability.REALTIME_BACKGROUND

    def _clipboard(self) -> QClipboard | None:
        app = QGuiApplication.instance()
        if app is None:
            return None
        return QGuiApplication.clipboard()

    # -- lifecycle -------------------------------------------------------
    def start(self, on_change: OnChangeCallback) -> None:
        clipboard = self._clipboard()
        if clipboard is None:
            raise RuntimeError("No QGuiApplication; cannot observe clipboard.")
        self._on_change = on_change
        if not self._connected:
            clipboard.dataChanged.connect(self._handle_data_changed)
            self._connected = True
        logger.debug("Qt clipboard backend started")

    def stop(self) -> None:
        clipboard = self._clipboard()
        if clipboard is not None and self._connected:
            try:
                clipboard.dataChanged.disconnect(self._handle_data_changed)
            except (RuntimeError, TypeError):
                pass
        self._connected = False
        self._on_change = None
        logger.debug("Qt clipboard backend stopped")

    def _handle_data_changed(self) -> None:
        # Only fire for the actual Clipboard selection (design 14); Qt's
        # dataChanged is for QClipboard.Clipboard, so no PRIMARY handling here.
        cb = self._on_change
        if cb is not None:
            cb()

    # -- read ------------------------------------------------------------
    def read_text(self) -> str | None:
        clipboard = self._clipboard()
        if clipboard is None:
            return None
        mime = clipboard.mimeData(QClipboard.Mode.Clipboard)
        if mime is None:
            return None

        # MIME policy (design 21): prefer plain text; else derive from HTML;
        # ignore images/files/binary.
        if mime.hasText():
            text = mime.text()
            if text:
                return text
        if mime.hasHtml():
            derived = html_to_plain_text(mime.html())
            if derived:
                return derived
        return None

    def current_fingerprint(self) -> str | None:
        text = self.read_text()
        if text is None:
            return None
        return fingerprint_text(text)

    # -- write -----------------------------------------------------------
    def write_safe_text(self, text: str, origin_marker: str) -> None:
        clipboard = self._clipboard()
        if clipboard is None:
            raise RuntimeError("No QGuiApplication; cannot write clipboard.")

        # Full-payload replacement (design 22): a fresh QMimeData with ONLY
        # protected plain text + origin marker. No HTML/RTF is carried over.
        mime = QMimeData()
        mime.setText(text)
        mime.setData(ORIGIN_MARKER_MIME, origin_marker.encode("utf-8"))
        clipboard.setMimeData(mime, QClipboard.Mode.Clipboard)
        logger.debug("Wrote protected clipboard payload (%d chars)", len(text))


__all__ = ["QtClipboardBackend"]
