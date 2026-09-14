"""Sprint 5 tests: controller feedback-loop, stale rejection, safe-copy validation.

These test the controller's pure decision logic. A QApplication (offscreen) is
required because the controller is a QObject that owns QTimers.
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

        app = QApplication.instance() or QApplication([])
        return app
    except Exception:
        pytest.skip("Qt unavailable")


class FakeBackend:
    """In-memory backend implementing the ClipboardBackend contract."""

    def __init__(self, capability):
        from sandiraksa.clipboard.fingerprint import fingerprint_text

        self._cap = capability
        self._text = ""
        self._fp_fn = fingerprint_text
        self.writes: list[tuple[str, str]] = []

    def capability(self):
        return self._cap

    def start(self, on_change):
        self._on_change = on_change

    def stop(self):
        pass

    def read_text(self):
        return self._text or None

    def current_fingerprint(self):
        return self._fp_fn(self._text) if self._text else None

    def write_safe_text(self, text, origin_marker):
        self._text = text
        self.writes.append((text, origin_marker))

    def set(self, text):
        self._text = text


def _make_controller(qapp, capability):
    from sandiraksa.clipboard.backends.base import ClipboardBackend
    from sandiraksa.clipboard.controller import ClipboardGuardController
    from sandiraksa.clipboard.models import ClipboardCapability

    backend = FakeBackend(capability or ClipboardCapability.REALTIME_BACKGROUND)
    # Register FakeBackend as a virtual subclass so isinstance checks (if any) pass.
    ClipboardBackend.register(FakeBackend)
    ctrl = ClipboardGuardController(backend=backend)
    return ctrl, backend


def _mk_result(controller, safe_text, generation, source_fp, expires_in=30.0):
    from sandiraksa.clipboard.models import (
        ClipboardProtectionResult,
        ClipboardRiskLevel,
        Finding,
    )

    now = time.monotonic()
    return ClipboardProtectionResult(
        result_id="r1",
        generation=generation,
        source_fingerprint=source_fp,
        created_monotonic=now,
        expires_monotonic=now + expires_in,
        risk_level=ClipboardRiskLevel.HIGH,
        findings=(Finding("ID_NIK", 0, 3, 0.9, "high", "abc"),),
        safe_text=safe_text,
    )


class TestCapability:
    def test_reports_backend_capability(self, qapp):
        from sandiraksa.clipboard.models import ClipboardCapability

        ctrl, _ = _make_controller(qapp, ClipboardCapability.USER_INITIATED_ONLY)
        assert ctrl.capability() == ClipboardCapability.USER_INITIATED_ONLY


class TestSafeCopyValidation:
    def test_copy_rejected_when_generation_stale(self, qapp):
        from sandiraksa.clipboard.fingerprint import fingerprint_text

        ctrl, backend = _make_controller(qapp, None)
        backend.set("original NIK text")
        ctrl._generation = 5
        ctrl._current_fingerprint = fingerprint_text("original NIK text")
        # Result from an older generation must be rejected (design 52).
        result = _mk_result(ctrl, "[NIK_REDACTED]", generation=3,
                            source_fp=fingerprint_text("original NIK text"))
        assert ctrl.copy_protected(result) is False
        assert backend.writes == []

    def test_copy_rejected_when_clipboard_changed(self, qapp):
        from sandiraksa.clipboard.fingerprint import fingerprint_text

        ctrl, backend = _make_controller(qapp, None)
        backend.set("NEW clipboard content")  # changed since scan
        ctrl._generation = 3
        result = _mk_result(ctrl, "[NIK_REDACTED]", generation=3,
                            source_fp=fingerprint_text("OLD content"))
        assert ctrl.copy_protected(result) is False
        assert backend.writes == []

    def test_copy_rejected_when_expired(self, qapp):
        from sandiraksa.clipboard.fingerprint import fingerprint_text

        ctrl, backend = _make_controller(qapp, None)
        backend.set("original")
        ctrl._generation = 3
        result = _mk_result(ctrl, "[NIK_REDACTED]", generation=3,
                            source_fp=fingerprint_text("original"),
                            expires_in=-1.0)  # already expired
        assert ctrl.copy_protected(result) is False

    def test_copy_succeeds_and_writes(self, qapp):
        from sandiraksa.clipboard.fingerprint import fingerprint_text

        ctrl, backend = _make_controller(qapp, None)
        backend.set("original NIK 123")
        ctrl._generation = 3
        result = _mk_result(ctrl, "[NIK_REDACTED]", generation=3,
                            source_fp=fingerprint_text("original NIK 123"))
        assert ctrl.copy_protected(result) is True
        assert backend.writes[-1][0] == "[NIK_REDACTED]"
        # A pending own-write must be registered to suppress the echo (design 19).
        assert ctrl._pending_own_write is not None


class TestFeedbackLoop:
    def test_own_write_echo_is_ignored(self, qapp):
        from sandiraksa.clipboard.fingerprint import fingerprint_text
        from sandiraksa.clipboard.models import PendingOwnWrite

        ctrl, backend = _make_controller(qapp, None)
        safe = "[NIK_REDACTED]"
        backend.set(safe)
        ctrl._pending_own_write = PendingOwnWrite(
            fingerprint=fingerprint_text(safe),
            expires_at_monotonic=time.monotonic() + 2.0,
            operation_id="op",
        )
        # Simulate the echo event; it must NOT enqueue a scan.
        ctrl._on_clipboard_changed()
        assert ctrl._coalescer.has_pending() is False
        # And the pending own-write is consumed.
        assert ctrl._pending_own_write is None

    def test_real_change_is_enqueued(self, qapp):
        ctrl, backend = _make_controller(qapp, None)
        backend.set("genuinely new sensitive text")
        ctrl._on_clipboard_changed()
        assert ctrl._coalescer.has_pending() is True


class TestStaleResultRejection:
    def test_stale_generation_discarded(self, qapp):
        from sandiraksa.clipboard.fingerprint import fingerprint_text

        ctrl, backend = _make_controller(qapp, None)
        emitted = []
        ctrl.resultReady.connect(lambda r: emitted.append(r))
        ctrl._generation = 10
        ctrl._current_fingerprint = fingerprint_text("current")
        # Result from generation 4 must be dropped (design 51).
        stale = _mk_result(ctrl, "[NIK_REDACTED]", generation=4,
                          source_fp=fingerprint_text("current"))
        ctrl._on_result_ready(stale)
        assert emitted == []

    def test_current_result_emitted(self, qapp):
        from sandiraksa.clipboard.fingerprint import fingerprint_text

        ctrl, backend = _make_controller(qapp, None)
        emitted = []
        ctrl.resultReady.connect(lambda r: emitted.append(r))
        fp = fingerprint_text("current")
        ctrl._generation = 10
        ctrl._current_fingerprint = fp
        good = _mk_result(ctrl, "[NIK_REDACTED]", generation=10, source_fp=fp)
        ctrl._on_result_ready(good)
        assert len(emitted) == 1
