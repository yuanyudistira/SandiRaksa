"""
Tier B integration test: real out-of-process detector via the supervisor.

Spawns the actual worker process, drives a Qt event loop, and asserts a real
scan round-trips (request -> worker process -> result). Marked slow because it
launches a subprocess and loads the detection engine.
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


def _pump(app, predicate, timeout_s=60.0):
    """Spin the Qt event loop until predicate() or timeout."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return False


@pytest.mark.slow
def test_supervisor_real_scan_roundtrip(qapp):
    from sandiraksa.clipboard.fingerprint import fingerprint_text
    from sandiraksa.clipboard.models import ScanRequest
    from sandiraksa.clipboard.supervisor import DetectionWorkerSupervisor

    sup = DetectionWorkerSupervisor()
    ready = {"v": False}
    results = []
    sup.ready.connect(lambda: ready.__setitem__("v", True))
    sup.resultReady.connect(lambda p: results.append(p))

    assert sup.start() is True
    try:
        # Worker process must load the engine and report READY.
        assert _pump(qapp, lambda: ready["v"], timeout_s=90.0), "worker never ready"

        text = "NIK 3174010101800001 email budi@example.com"
        req = ScanRequest(
            request_id="q1",
            generation=1,
            fingerprint=fingerprint_text(text),
            text=text,
            created_monotonic=time.monotonic(),
        )
        assert sup.submit_scan(req) is True

        assert _pump(qapp, lambda: len(results) > 0, timeout_s=30.0), "no result"
        payload = results[0]
        assert payload["risk_level"] in ("high", "critical", "medium")
        assert "[NIK_REDACTED]" in payload["safe_text"]
        assert payload["generation"] == 1
    finally:
        sup.stop()
