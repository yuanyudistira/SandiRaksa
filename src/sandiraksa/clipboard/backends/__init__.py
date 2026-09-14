"""
Platform clipboard backends.

All OS clipboard access goes through :class:`ClipboardBackend` (design 10).
No other component may call ``QGuiApplication.clipboard()`` directly.

Use :func:`create_backend` to obtain the correct backend for the current
platform/session; it degrades honestly to an ``unsupported`` backend rather
than pretending protection is active (design 7.3).
"""

from sandiraksa.clipboard.backends.base import (
    ClipboardBackend,
    ORIGIN_MARKER_MIME,
    make_origin_marker,
)
from sandiraksa.clipboard.backends.factory import create_backend

__all__ = [
    "ClipboardBackend",
    "ORIGIN_MARKER_MIME",
    "make_origin_marker",
    "create_backend",
]
