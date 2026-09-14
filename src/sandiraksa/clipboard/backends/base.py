"""
Clipboard backend abstraction (design 10, 11, 20, 21, 22).

Every platform clipboard interaction is funneled through this ABC so the rest
of the system never touches ``QGuiApplication.clipboard()`` directly. This
gives us a single place to enforce the MIME policy (design 21), safe
full-payload replacement (design 22), and the custom origin marker (design 20).
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Callable

from sandiraksa.clipboard.models import ClipboardCapability

#: Custom MIME type stamped onto SandiRaksa's own clipboard writes (design 20).
ORIGIN_MARKER_MIME = "application/x-sandiraksa-origin"

#: Supported plain-text MIME (design 21).
MIME_PLAIN = "text/plain"
#: HTML MIME - a plain-text representation is derived for analysis (design 21).
MIME_HTML = "text/html"


def make_origin_marker(operation_id: str | None = None) -> str:
    """
    Build an origin-marker value ``srk:v1:<random-operation-id>`` (design 20).

    This is supplementary: fingerprint matching remains authoritative because
    some clipboard managers strip custom MIME data (design 20).
    """
    op = operation_id or uuid.uuid4().hex
    return f"srk:v1:{op}"


#: Callback invoked (on the GUI thread) when the clipboard changes.
OnChangeCallback = Callable[[], None]


class ClipboardBackend(ABC):
    """
    Platform clipboard access contract (design 10).

    Implementations must be used only from the GUI thread for read/write, since
    they touch Qt clipboard objects (design 5.3). Detection never happens here.
    """

    @abstractmethod
    def capability(self) -> ClipboardCapability:
        """Report how reliably clipboard changes can be observed (design 7)."""

    @abstractmethod
    def start(self, on_change: OnChangeCallback) -> None:
        """Begin observing clipboard changes, invoking ``on_change`` per event."""

    @abstractmethod
    def stop(self) -> None:
        """Stop observing clipboard changes and release resources."""

    @abstractmethod
    def read_text(self) -> str | None:
        """
        Read the current clipboard as plain text per the MIME policy (design 21):
        return ``text/plain`` directly, or a derived plain-text representation
        of ``text/html``; return ``None`` for images/files/binary/unsupported.
        """

    @abstractmethod
    def current_fingerprint(self) -> str | None:
        """SHA-256 fingerprint of current clipboard text, or None if no text."""

    @abstractmethod
    def write_safe_text(self, text: str, origin_marker: str) -> None:
        """
        Replace the ENTIRE clipboard payload with protected plain text plus the
        origin marker (design 22). No original HTML/RTF/rich text is preserved,
        preventing hidden PII leakage through alternate MIME formats.
        """


__all__ = [
    "ClipboardBackend",
    "ORIGIN_MARKER_MIME",
    "MIME_PLAIN",
    "MIME_HTML",
    "make_origin_marker",
    "OnChangeCallback",
]
