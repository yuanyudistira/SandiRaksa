"""Sprint 1 tests: clipboard core domain (models, fingerprint, state machines)."""

from __future__ import annotations

import pytest

from sandiraksa.clipboard.fingerprint import fingerprint_text, length_bucket
from sandiraksa.clipboard.models import (
    ClipboardCapability,
    ClipboardMonitorState,
    ClipboardProtectionResult,
    ClipboardRiskLevel,
    ClipboardSnapshot,
    DetectionSource,
    Finding,
    PendingOwnWrite,
    ScanFailure,
    ScanRequest,
    WorkerState,
)
from sandiraksa.clipboard.state_machine import (
    InvalidTransition,
    MonitorStateMachine,
    WorkerStateMachine,
)


class TestFingerprint:
    def test_stable_and_deterministic(self):
        assert fingerprint_text("hello") == fingerprint_text("hello")

    def test_differs_for_different_text(self):
        assert fingerprint_text("a") != fingerprint_text("b")

    def test_is_sha256_hex(self):
        fp = fingerprint_text("x")
        assert len(fp) == 64
        int(fp, 16)  # must be valid hex

    def test_handles_lone_surrogate(self):
        # Hostile/pathological Unicode must not raise (design 5.4, 18).
        weird = "abc\ud800def"
        fp = fingerprint_text(weird)
        assert len(fp) == 64

    def test_length_bucket(self):
        assert length_bucket(0) == "0"
        assert length_bucket(50) == "<100"
        assert length_bucket(500) == "<1k"
        assert length_bucket(600_000) == ">=512k"


class TestSnapshot:
    def test_create_computes_fingerprint(self):
        snap = ClipboardSnapshot.create(generation=1, text="hi", observed_at_monotonic=10.0)
        assert snap.fingerprint == fingerprint_text("hi")
        assert snap.generation == 1
        assert snap.observed_at_monotonic == 10.0

    def test_frozen(self):
        snap = ClipboardSnapshot.create(1, "hi", 10.0)
        with pytest.raises(Exception):
            snap.generation = 2  # type: ignore[misc]


class TestPendingOwnWrite:
    def test_matches_within_ttl(self):
        p = PendingOwnWrite(fingerprint="fp", expires_at_monotonic=100.0, operation_id="op")
        assert p.matches("fp", now_monotonic=99.0) is True

    def test_no_match_wrong_fingerprint(self):
        p = PendingOwnWrite(fingerprint="fp", expires_at_monotonic=100.0, operation_id="op")
        assert p.matches("other", now_monotonic=99.0) is False

    def test_no_match_after_ttl(self):
        p = PendingOwnWrite(fingerprint="fp", expires_at_monotonic=100.0, operation_id="op")
        assert p.matches("fp", now_monotonic=101.0) is False


class TestScanFailure:
    def test_from_exception_sanitizes(self):
        secret = "NIK 3174000000000000 leaked"
        try:
            raise ValueError(secret)
        except ValueError as exc:
            f = ScanFailure.from_exception(exc, generation=5, latency_ms=12)
        assert f.category == "ValueError"
        assert f.generation == 5
        assert f.latency_ms == 12
        # message is truncated but here short; ensure no object refs retained
        assert isinstance(f.message, str)

    def test_message_truncated(self):
        long = "x" * 1000
        try:
            raise RuntimeError(long)
        except RuntimeError as exc:
            f = ScanFailure.from_exception(exc, generation=1)
        assert len(f.message) <= 200


class TestRiskLevel:
    def test_rank_ordering(self):
        assert ClipboardRiskLevel.LOW.rank < ClipboardRiskLevel.MEDIUM.rank
        assert ClipboardRiskLevel.MEDIUM.rank < ClipboardRiskLevel.HIGH.rank
        assert ClipboardRiskLevel.HIGH.rank < ClipboardRiskLevel.CRITICAL.rank


class TestProtectionResult:
    def _mk(self, expires=100.0):
        return ClipboardProtectionResult(
            result_id="r1",
            generation=3,
            source_fingerprint="fp",
            created_monotonic=70.0,
            expires_monotonic=expires,
            risk_level=ClipboardRiskLevel.HIGH,
            findings=(
                Finding("ID_NIK", 0, 16, 0.9, "high", "3174000000000000"),
                Finding("EMAIL_ADDRESS", 20, 35, 0.8, "medium", "a@b.com"),
                Finding("ID_NIK", 40, 56, 0.9, "high", "3174000000000001"),
            ),
            safe_text="[NIK_REDACTED] ... [EMAIL_REDACTED] ... [NIK_REDACTED]",
        )

    def test_is_expired(self):
        r = self._mk(expires=100.0)
        assert r.is_expired(99.0) is False
        assert r.is_expired(101.0) is True

    def test_entity_counts(self):
        r = self._mk()
        counts = r.entity_counts()
        assert counts["ID_NIK"] == 2
        assert counts["EMAIL_ADDRESS"] == 1


class TestScanRequestDefaults:
    def test_defaults(self):
        req = ScanRequest(
            request_id="q1",
            generation=1,
            fingerprint="fp",
            text="hello",
            created_monotonic=1.0,
        )
        assert req.protocol_version == 1
        assert req.source == DetectionSource.CLIPBOARD


class TestMonitorStateMachine:
    def test_happy_path(self):
        m = MonitorStateMachine()
        assert m.state == ClipboardMonitorState.OFF
        m.transition(ClipboardMonitorState.STARTING)
        m.transition(ClipboardMonitorState.ACTIVE)
        m.transition(ClipboardMonitorState.PAUSED)
        m.transition(ClipboardMonitorState.ACTIVE)
        assert m.state == ClipboardMonitorState.ACTIVE

    def test_illegal_transition_raises(self):
        m = MonitorStateMachine()
        # OFF cannot jump straight to ACTIVE.
        with pytest.raises(InvalidTransition):
            m.transition(ClipboardMonitorState.ACTIVE)

    def test_error_path_cannot_reach_active_directly(self):
        # design 8: a failure must never leave state ACTIVE.
        m = MonitorStateMachine()
        m.transition(ClipboardMonitorState.STARTING)
        m.transition(ClipboardMonitorState.ERROR)
        assert not m.can_transition(ClipboardMonitorState.ACTIVE)
        with pytest.raises(InvalidTransition):
            m.transition(ClipboardMonitorState.ACTIVE)

    def test_degraded_recovers_via_active(self):
        m = MonitorStateMachine()
        m.transition(ClipboardMonitorState.STARTING)
        m.transition(ClipboardMonitorState.ACTIVE)
        m.transition(ClipboardMonitorState.DEGRADED)
        # Recovery requires explicit re-activation.
        assert m.can_transition(ClipboardMonitorState.ACTIVE)

    def test_idempotent_noop(self):
        m = MonitorStateMachine()
        assert m.transition(ClipboardMonitorState.OFF) == ClipboardMonitorState.OFF


class TestWorkerStateMachine:
    def test_lifecycle(self):
        w = WorkerStateMachine()
        assert w.state == WorkerState.STOPPED
        w.transition(WorkerState.STARTING)
        w.transition(WorkerState.READY)
        w.transition(WorkerState.SCANNING)
        w.transition(WorkerState.READY)
        assert w.state == WorkerState.READY

    def test_scan_failure_to_degraded_then_restart(self):
        w = WorkerStateMachine()
        w.transition(WorkerState.STARTING)
        w.transition(WorkerState.READY)
        w.transition(WorkerState.SCANNING)
        w.transition(WorkerState.DEGRADED)
        w.transition(WorkerState.STARTING)  # restart
        assert w.state == WorkerState.STARTING

    def test_illegal(self):
        w = WorkerStateMachine()
        with pytest.raises(InvalidTransition):
            w.transition(WorkerState.SCANNING)


class TestCapabilityEnum:
    def test_values(self):
        assert ClipboardCapability.REALTIME_BACKGROUND.value == "realtime_background"
        assert ClipboardCapability.USER_INITIATED_ONLY.value == "user_initiated_only"
        assert ClipboardCapability.UNAVAILABLE.value == "unavailable"
