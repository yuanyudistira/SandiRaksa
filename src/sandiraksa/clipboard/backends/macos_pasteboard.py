"""
macOS clipboard backend (design 13).

``QClipboard.dataChanged`` is unreliable for true background detection on
macOS, so this backend polls ``NSPasteboard.general().changeCount()`` via
PyObjC and only reads the full pasteboard when the change count advances
(design 13). Reading the value continuously is avoided.

If PyObjC is unavailable or access is denied, the backend degrades to
USER_INITIATED_ONLY rather than crashing (design 13); the user can still
trigger manual scans.

Read/write of the actual pasteboard value reuses Qt for the plain-text/HTML
MIME policy and safe full-payload replacement; only *change observation* uses
NSPasteboard's changeCount.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer

from sandiraksa.clipboard.backends.base import OnChangeCallback
from sandiraksa.clipboard.backends.qt_common import QtClipboardBackend
from sandiraksa.clipboard.models import ClipboardCapability

logger = logging.getLogger("sandiraksa.clipboard")

# Poll interval for changeCount (design 13: 300-500 ms).
_POLL_MS = 400


def _load_nspasteboard():
    """Return NSPasteboard.general() or None if PyObjC is unavailable."""
    try:
        from AppKit import NSPasteboard  # type: ignore

        return NSPasteboard.generalPasteboard()
    except Exception:  # ImportError or runtime failure
        return None


class MacOSClipboardBackend(QtClipboardBackend):
    """NSPasteboard changeCount poller; Qt used for read/write value."""

    def __init__(self) -> None:
        super().__init__()
        self._pasteboard = _load_nspasteboard()
        self._last_change_count: int | None = None
        self._poll_timer: QTimer | None = None
        self._change_cb: OnChangeCallback | None = None

    def capability(self) -> ClipboardCapability:
        # Without PyObjC we cannot observe background changes reliably.
        if self._pasteboard is None:
            return ClipboardCapability.USER_INITIATED_ONLY
        return ClipboardCapability.REALTIME_BACKGROUND

    def start(self, on_change: OnChangeCallback) -> None:
        if self._pasteboard is None:
            # No background observation available; manual scans still work.
            self._change_cb = on_change
            return
        self._change_cb = on_change
        try:
            self._last_change_count = int(self._pasteboard.changeCount())
        except Exception:
            self._last_change_count = None
        self._poll_timer = QTimer()
        self._poll_timer.setInterval(_POLL_MS)
        self._poll_timer.timeout.connect(self._poll_change_count)
        self._poll_timer.start()
        logger.debug("macOS pasteboard poller started")

    def stop(self) -> None:
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None
        self._change_cb = None

    def _poll_change_count(self) -> None:
        if self._pasteboard is None:
            return
        try:
            count = int(self._pasteboard.changeCount())
        except Exception:
            return
        if self._last_change_count is None:
            self._last_change_count = count
            return
        if count != self._last_change_count:
            self._last_change_count = count
            cb = self._change_cb
            if cb is not None:
                cb()


__all__ = ["MacOSClipboardBackend"]
