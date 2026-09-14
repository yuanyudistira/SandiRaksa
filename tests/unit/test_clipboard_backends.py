"""Sprint 2 tests: clipboard backends, MIME policy, origin marker, factory."""

from __future__ import annotations

import os

import pytest

from sandiraksa.clipboard.backends.base import (
    ORIGIN_MARKER_MIME,
    make_origin_marker,
)
from sandiraksa.clipboard.backends.factory import create_backend
from sandiraksa.clipboard.backends.html_text import html_to_plain_text
from sandiraksa.clipboard.backends.unsupported import UnsupportedClipboardBackend
from sandiraksa.clipboard.models import ClipboardCapability


class TestOriginMarker:
    def test_format(self):
        marker = make_origin_marker("abc123")
        assert marker == "srk:v1:abc123"

    def test_random_when_no_id(self):
        a = make_origin_marker()
        b = make_origin_marker()
        assert a.startswith("srk:v1:")
        assert a != b

    def test_mime_constant(self):
        assert ORIGIN_MARKER_MIME == "application/x-sandiraksa-origin"


class TestHtmlToPlainText:
    def test_strips_tags(self):
        assert html_to_plain_text("<b>hello</b>") == "hello"

    def test_unescapes_entities(self):
        assert html_to_plain_text("a &amp; b") == "a & b"

    def test_drops_script_style(self):
        html = "<style>.x{}</style><p>keep</p><script>bad()</script>"
        out = html_to_plain_text(html)
        assert "keep" in out
        assert "bad()" not in out
        assert ".x{}" not in out

    def test_block_boundaries_become_newlines(self):
        out = html_to_plain_text("<p>one</p><p>two</p>")
        assert "one" in out and "two" in out

    def test_empty(self):
        assert html_to_plain_text("") == ""

    def test_huge_input_bounded(self):
        # Must not hang or raise on very large input (design 43).
        big = "<p>" + ("a" * 5_000_000) + "</p>"
        out = html_to_plain_text(big)
        assert isinstance(out, str)


class TestFactory:
    def test_windows(self):
        b = create_backend(platform="win32")
        assert type(b).__name__ == "WindowsClipboardBackend"
        assert b.capability() == ClipboardCapability.REALTIME_BACKGROUND

    def test_linux_x11(self, monkeypatch):
        # Ensure no Wayland env signals leak in.
        for k in ("XDG_SESSION_TYPE", "WAYLAND_DISPLAY", "QT_QPA_PLATFORM"):
            monkeypatch.delenv(k, raising=False)
        b = create_backend(platform="linux")
        assert type(b).__name__ == "LinuxX11ClipboardBackend"
        assert b.capability() == ClipboardCapability.REALTIME_BACKGROUND

    def test_linux_wayland_degrades(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        b = create_backend(platform="linux")
        assert isinstance(b, UnsupportedClipboardBackend)
        assert b.capability() == ClipboardCapability.UNAVAILABLE

    def test_macos_degrades(self):
        b = create_backend(platform="darwin")
        assert isinstance(b, UnsupportedClipboardBackend)

    def test_unknown_platform(self):
        b = create_backend(platform="plan9")
        assert isinstance(b, UnsupportedClipboardBackend)


class TestUnsupportedBackend:
    def test_capability(self):
        assert UnsupportedClipboardBackend().capability() == ClipboardCapability.UNAVAILABLE

    def test_read_returns_none(self):
        assert UnsupportedClipboardBackend().read_text() is None
        assert UnsupportedClipboardBackend().current_fingerprint() is None

    def test_write_raises(self):
        with pytest.raises(RuntimeError):
            UnsupportedClipboardBackend().write_safe_text("x", "srk:v1:op")

    def test_start_stop_noop(self):
        b = UnsupportedClipboardBackend()
        b.start(lambda: None)
        b.stop()


# Qt-backed read/write test - only runs if we can create an offscreen app.
def _make_offscreen_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance() or QGuiApplication([])
        return app
    except Exception:
        return None


class TestQtBackendReadWrite:
    def test_write_then_read_roundtrip(self):
        app = _make_offscreen_app()
        if app is None:
            pytest.skip("Qt offscreen platform unavailable")
        from sandiraksa.clipboard.backends.qt_common import QtClipboardBackend

        backend = QtClipboardBackend()
        backend.write_safe_text("protected text", make_origin_marker("op1"))
        assert backend.read_text() == "protected text"
        fp = backend.current_fingerprint()
        assert fp is not None and len(fp) == 64

    def test_full_payload_replacement_drops_html(self):
        app = _make_offscreen_app()
        if app is None:
            pytest.skip("Qt offscreen platform unavailable")
        from PySide6.QtCore import QMimeData
        from PySide6.QtGui import QClipboard, QGuiApplication

        from sandiraksa.clipboard.backends.qt_common import QtClipboardBackend

        # Seed clipboard with rich content that contains PII in HTML.
        seed = QMimeData()
        seed.setText("plain")
        seed.setHtml("<p>secret NIK 3174000000000000</p>")
        QGuiApplication.clipboard().setMimeData(seed, QClipboard.Mode.Clipboard)

        backend = QtClipboardBackend()
        backend.write_safe_text("[NIK_REDACTED]", make_origin_marker("op2"))

        mime = QGuiApplication.clipboard().mimeData(QClipboard.Mode.Clipboard)
        # design 22: no HTML must survive the safe write.
        assert not mime.hasHtml()
        assert mime.text() == "[NIK_REDACTED]"
        assert mime.hasFormat(ORIGIN_MARKER_MIME)
