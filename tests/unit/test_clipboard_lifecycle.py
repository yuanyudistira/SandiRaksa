"""Sprint 8 tests: controller lifecycle (lock/sleep/resume/watchdog) + backends."""

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
    def __init__(self, capability):
        from sandiraksa.clipboard.fingerprint import fingerprint_text

        self._cap = capability
        self._text = ""
        self._fp = fingerprint_text
        self.started = False
        self.stopped = False

    def capability(self):
        return self._cap

    def start(self, on_change):
        self.started = True

    def stop(self):
        self.stopped = True

    def read_text(self):
        return self._text or None

    def current_fingerprint(self):
        return self._fp(self._text) if self._text else None

    def write_safe_text(self, text, marker):
        self._text = text

    def set(self, text):
        self._text = text


def _controller(qapp, capability=None):
    from sandiraksa.clipboard.backends.base import ClipboardBackend
    from sandiraksa.clipboard.controller import ClipboardGuardController
    from sandiraksa.clipboard.models import ClipboardCapability

    ClipboardBackend.register(FakeBackend)
    backend = FakeBackend(capability or ClipboardCapability.REALTIME_BACKGROUND)
    return ClipboardGuardController(backend=backend), backend


class TestSessionLock:
    def test_lock_pauses_and_invalidates(self, qapp):
        from sandiraksa.clipboard.models import ClipboardMonitorState

        ctrl, backend = _controller(qapp)
        ctrl.start()
        assert ctrl.state == ClipboardMonitorState.ACTIVE
        gen_before = ctrl._generation
        ctrl.on_session_lock()
        assert ctrl.state == ClipboardMonitorState.PAUSED
        # Generation advanced -> any in-flight result becomes stale (design 62).
        assert ctrl._generation > gen_before
        ctrl.stop()

    def test_unlock_resumes(self, qapp):
        from sandiraksa.clipboard.models import ClipboardMonitorState

        ctrl, backend = _controller(qapp)
        ctrl.start()
        ctrl.on_session_lock()
        ctrl.on_session_unlock()
        assert ctrl.state == ClipboardMonitorState.ACTIVE
        ctrl.stop()


class TestSleepResume:
    def test_sleep_stops_backend_and_invalidates(self, qapp):
        from sandiraksa.clipboard.models import ClipboardMonitorState

        ctrl, backend = _controller(qapp)
        ctrl.start()
        gen_before = ctrl._generation
        ctrl.on_sleep()
        assert backend.stopped is True
        assert ctrl.state == ClipboardMonitorState.PAUSED
        assert ctrl._generation > gen_before
        ctrl.stop()

    def test_resume_clears_own_write_and_reactivates(self, qapp):
        from sandiraksa.clipboard.models import ClipboardMonitorState, PendingOwnWrite

        ctrl, backend = _controller(qapp)
        ctrl.start()
        ctrl.on_sleep()
        ctrl._pending_own_write = PendingOwnWrite("fp", time.monotonic() + 5, "op")
        ctrl.on_resume_from_sleep()
        # Own-write state cleared so genuine post-resume change isn't suppressed.
        assert ctrl._pending_own_write is None
        assert ctrl.state == ClipboardMonitorState.ACTIVE
        ctrl.stop()


class TestWatchdog:
    def test_late_result_discarded(self, qapp):
        from sandiraksa.clipboard.fingerprint import fingerprint_text
        from sandiraksa.clipboard.models import (
            ClipboardProtectionResult,
            ClipboardRiskLevel,
            Finding,
        )

        ctrl, backend = _controller(qapp)
        emitted = []
        ctrl.resultReady.connect(lambda r: emitted.append(r))
        fp = fingerprint_text("current")
        ctrl._generation = 5
        ctrl._current_fingerprint = fp
        now = time.monotonic()
        # created 10s ago -> beyond the 5s hard budget -> discarded (design 37/38).
        late = ClipboardProtectionResult(
            result_id="r",
            generation=5,
            source_fingerprint=fp,
            created_monotonic=now - 10.0,
            expires_monotonic=now + 20.0,  # not TTL-expired, but late
            risk_level=ClipboardRiskLevel.HIGH,
            findings=(Finding("ID_NIK", 0, 3, 0.9, "high", "abc"),),
            safe_text="[NIK_REDACTED]",
        )
        ctrl._on_result_ready(late)
        assert emitted == []
        ctrl.stop()


class TestUnsupportedStart:
    def test_unavailable_backend_goes_unsupported(self, qapp):
        from sandiraksa.clipboard.models import (
            ClipboardCapability,
            ClipboardMonitorState,
        )

        ctrl, backend = _controller(qapp, ClipboardCapability.UNAVAILABLE)
        ctrl.start()
        assert ctrl.state == ClipboardMonitorState.UNSUPPORTED

    def test_user_initiated_only_state(self, qapp):
        from sandiraksa.clipboard.models import (
            ClipboardCapability,
            ClipboardMonitorState,
        )

        ctrl, backend = _controller(qapp, ClipboardCapability.USER_INITIATED_ONLY)
        ctrl.start()
        assert ctrl.state == ClipboardMonitorState.USER_INITIATED_ONLY
        ctrl.stop()


class TestWaylandBackend:
    def test_default_user_initiated(self):
        from sandiraksa.clipboard.backends.linux_wayland import (
            LinuxWaylandClipboardBackend,
        )
        from sandiraksa.clipboard.models import ClipboardCapability

        b = LinuxWaylandClipboardBackend()
        assert b.capability() == ClipboardCapability.USER_INITIATED_ONLY
        b.confirm_background()
        assert b.capability() == ClipboardCapability.REALTIME_BACKGROUND

    def test_detect_environment(self, monkeypatch):
        from sandiraksa.clipboard.backends.linux_wayland import (
            LinuxWaylandClipboardBackend,
        )

        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        env = LinuxWaylandClipboardBackend.detect_environment()
        assert env["xdg_session_type"] == "wayland"
