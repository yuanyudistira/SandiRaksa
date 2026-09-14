"""
Unsupported clipboard backend (design 7.3).

Used when clipboard access is unavailable. It reports UNAVAILABLE and performs
no monitoring, so the application can honestly show "Clipboard Protection
unavailable in this environment" instead of pretending protection is active.
"""

from __future__ import annotations

from sandiraksa.clipboard.backends.base import ClipboardBackend, OnChangeCallback
from sandiraksa.clipboard.models import ClipboardCapability


class UnsupportedClipboardBackend(ClipboardBackend):
    """A no-op backend that reports UNAVAILABLE."""

    def capability(self) -> ClipboardCapability:
        return ClipboardCapability.UNAVAILABLE

    def start(self, on_change: OnChangeCallback) -> None:  # noqa: D401
        # Intentionally does nothing; there is nothing to observe.
        return None

    def stop(self) -> None:
        return None

    def read_text(self) -> str | None:
        return None

    def current_fingerprint(self) -> str | None:
        return None

    def write_safe_text(self, text: str, origin_marker: str) -> None:
        # Cannot write; callers must check capability before offering actions.
        raise RuntimeError("Clipboard is unavailable in this environment.")


__all__ = ["UnsupportedClipboardBackend"]
