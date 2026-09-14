"""
Linux X11 clipboard backend (design 14).

Uses Qt's ``QClipboard.Clipboard`` selection only. It deliberately does NOT
monitor the X11 PRIMARY selection in v1, because selecting text can change
PRIMARY without an explicit copy and would produce excessive alerts (design 14).
The shared :class:`QtClipboardBackend` already binds only to the Clipboard
selection, so this is a thin marker subclass.
"""

from __future__ import annotations

from sandiraksa.clipboard.backends.qt_common import QtClipboardBackend


class LinuxX11ClipboardBackend(QtClipboardBackend):
    """X11 backend: Clipboard selection only, never PRIMARY (design 14)."""


__all__ = ["LinuxX11ClipboardBackend"]
