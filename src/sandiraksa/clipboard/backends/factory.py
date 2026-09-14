"""
Backend selection (design 7, 11, 15).

Chooses the correct clipboard backend for the current platform/session and
degrades honestly. macOS and Wayland backends arrive in a later sprint; until
then those environments fall back to the unsupported backend rather than
falsely claiming realtime protection (design 7.3, 15).
"""

from __future__ import annotations

import logging
import os
import sys

from sandiraksa.clipboard.backends.base import ClipboardBackend
from sandiraksa.clipboard.backends.unsupported import UnsupportedClipboardBackend

logger = logging.getLogger(__name__)


def _is_wayland() -> bool:
    """Detect a Wayland session (design 15) via environment signals."""
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        return True
    if os.environ.get("WAYLAND_DISPLAY"):
        return True
    if os.environ.get("QT_QPA_PLATFORM", "").lower().startswith("wayland"):
        return True
    return False


def create_backend(platform: str | None = None) -> ClipboardBackend:
    """
    Return the appropriate backend for the current environment.

    Args:
        platform: Override for ``sys.platform`` (testing). When None, detected.

    Returns:
        A concrete :class:`ClipboardBackend`. Never raises for an unknown
        platform - it returns the unsupported backend instead.
    """
    plat = platform or sys.platform

    if plat == "win32":
        from sandiraksa.clipboard.backends.windows_qt import (
            WindowsClipboardBackend,
        )

        return WindowsClipboardBackend()

    if plat.startswith("linux"):
        if _is_wayland():
            # Wayland background monitoring is capability-driven and handled by
            # a dedicated backend in a later sprint. Degrade honestly for now.
            logger.info(
                "Wayland session detected; realtime clipboard backend not yet "
                "available - degrading to unsupported."
            )
            return UnsupportedClipboardBackend()

        from sandiraksa.clipboard.backends.linux_x11_qt import (
            LinuxX11ClipboardBackend,
        )

        return LinuxX11ClipboardBackend()

    if plat == "darwin":
        # macOS NSPasteboard backend arrives in a later sprint (design 13).
        logger.info(
            "macOS detected; native pasteboard backend not yet available - "
            "degrading to unsupported."
        )
        return UnsupportedClipboardBackend()

    logger.info("Unknown platform %r; clipboard unsupported.", plat)
    return UnsupportedClipboardBackend()


__all__ = ["create_backend"]
