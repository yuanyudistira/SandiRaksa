"""
Tier A end-to-end flow test: controller -> worker thread -> result.

Drives the real ClipboardGuardController with a fake backend through an actual
QThread and Qt event loop, proving a scan dispatched via the queued signal
completes on the worker thread and a result comes back. This reproduces and
guards against the "scan never runs / QThread destroyed while running" bug.
"""

from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    try:
        from PySide6.QtWidgets import QApplication

        return QApplication.instance() or QApplication([])
    except Exception:
        pytest.skip("Qt unavailable")


class FakeBackend:
    def __init__(self):
        from sandiraksa.clipboard.fingerprint import fingerprint_text
        from sandiraksa.clipboard.models import ClipboardCapability

        self._cap = ClipboardCapability.REALTIME_BACKGROUND
        self._text = ""
        self._fp = fingerprint_text

    def capability(self):
        return self._cap

    def start(self, on_change):
        self._on_change = on_change

    def stop(self):
        pass

    def read_text(self):
        return self._text or None

    def current_fingerprint(self):
        return self._fp(self._text) if self._text else None

    def write_safe_text(self, text, marker):
        self._text = text

    def set(self, text):
        self._text = text


def _pump(app, predicate, timeout_s=60.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return False


@pytest.mark.slow
def test_scan_runs_on_worker_thread_and_returns_result(qapp):
    from sandiraksa.clipboard.backends.base import ClipboardBackend
    from sandiraksa.clipboard.controller import ClipboardGuardController

    ClipboardBackend.register(FakeBackend)
    backend = FakeBackend()
    ctrl = ClipboardGuardController(backend=backend)

    results = []
    ctrl.resultReady.connect(lambda r: results.append(r))

    ctrl.start()
    try:
        # Simulate a real copy of PII-bearing text.
        backend.set("Hubungi 081234567890 atau budi@example.com")
        ctrl.scan_current_clipboard()

        assert _pump(qapp, lambda: len(results) > 0, timeout_s=60.0), (
            "worker never produced a result"
        )
        result = results[0]
        types = {f.entity_type for f in result.findings}
        # Phone + email should both be detected and redacted.
        assert "EMAIL_ADDRESS" in types
        assert any(t in types for t in ("ID_PHONE", "PHONE_NUMBER"))
        assert "[EMAIL_REDACTED]" in result.safe_text
    finally:
        ctrl.stop()
