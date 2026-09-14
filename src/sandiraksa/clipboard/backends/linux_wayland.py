"""
Linux Wayland clipboard backend (design 15).

Wayland support is capability-driven. Background clipboard observation is not
guaranteed across compositors, and the design explicitly forbids "proving"
background monitoring by writing dummy text and receiving our own event - that
only proves SandiRaksa can observe itself (design 15).

This backend therefore:
  * reads/writes via Qt (works when the app is focused);
  * reports capability based on environment signals; when passive background
    observation cannot be confirmed, it reports USER_INITIATED_ONLY, which is
    a valid supported mode (design 15);
  * relies on QClipboard.dataChanged for change events when available, but does
    not claim REALTIME_BACKGROUND unless a guided external-copy capability test
    has confirmed it.
"""

from __future__ import annotations

import logging
import os

from sandiraksa.clipboard.backends.qt_common import QtClipboardBackend
from sandiraksa.clipboard.models import ClipboardCapability

logger = logging.getLogger("sandiraksa.clipboard")


class LinuxWaylandClipboardBackend(QtClipboardBackend):
    """Capability-driven Wayland backend (design 15)."""

    def __init__(self, confirmed_background: bool = False) -> None:
        super().__init__()
        # Only REALTIME_BACKGROUND if a guided external-copy test confirmed it
        # (design 15). Default is the honest USER_INITIATED_ONLY.
        self._confirmed_background = confirmed_background

    def capability(self) -> ClipboardCapability:
        if self._confirmed_background:
            return ClipboardCapability.REALTIME_BACKGROUND
        return ClipboardCapability.USER_INITIATED_ONLY

    @staticmethod
    def detect_environment() -> dict:
        """
        Collect Wayland environment signals for a capability decision (design 15).

        Returns a dict of detected signals; the guided capability test (run in
        the UI) uses this plus an actual external-copy observation to decide
        whether to enable background mode.
        """
        return {
            "xdg_session_type": os.environ.get("XDG_SESSION_TYPE", ""),
            "wayland_display": os.environ.get("WAYLAND_DISPLAY", ""),
            "qt_qpa_platform": os.environ.get("QT_QPA_PLATFORM", ""),
            "xdg_current_desktop": os.environ.get("XDG_CURRENT_DESKTOP", ""),
        }

    def confirm_background(self) -> None:
        """Mark background observation as confirmed by a guided test."""
        self._confirmed_background = True


__all__ = ["LinuxWaylandClipboardBackend"]
