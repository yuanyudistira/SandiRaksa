"""
Windows clipboard backend (design 12).

Uses Qt's ``QClipboard.dataChanged`` as the default event mechanism. No native
``pywin32`` dependency is added unless a real compatibility defect requires it
(design 12).
"""

from __future__ import annotations

from sandiraksa.clipboard.backends.qt_common import QtClipboardBackend


class WindowsClipboardBackend(QtClipboardBackend):
    """Windows backend backed by Qt clipboard events."""


__all__ = ["WindowsClipboardBackend"]
