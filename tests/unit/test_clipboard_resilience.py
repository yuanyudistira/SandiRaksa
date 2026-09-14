"""Sprint 7 tests: worker resilience policy (heartbeat, backoff, circuit breaker)."""

from __future__ import annotations

from sandiraksa.clipboard.resilience import (
    CRASH_LIMIT,
    SCAN_FAILURE_LIMIT,
    CircuitBreaker,
    HeartbeatHealth,
    backoff_for_attempt,
    heartbeat_health,
)


class TestHeartbeatHealth:
    def test_never_acked_is_dead(self):
        assert heartbeat_health(None, now=100.0) == HeartbeatHealth.DEAD

    def test_recent_is_healthy(self):
        assert heartbeat_health(100.0, now=101.0) == HeartbeatHealth.HEALTHY

    def test_late(self):
        # interval 2s, unhealthy 6s -> age 4s is LATE.
        assert heartbeat_health(100.0, now=104.0) == HeartbeatHealth.LATE

    def test_unresponsive(self):
        assert heartbeat_health(100.0, now=107.0) == HeartbeatHealth.UNRESPONSIVE


class TestBackoff:
    def test_schedule(self):
        assert backoff_for_attempt(1) == 1.0
        assert backoff_for_attempt(2) == 2.0
        assert backoff_for_attempt(3) == 5.0
        assert backoff_for_attempt(4) == 15.0

    def test_exhausted_returns_none(self):
        # 5th attempt -> schedule exhausted -> open circuit.
        assert backoff_for_attempt(5) is None

    def test_invalid_attempt(self):
        assert backoff_for_attempt(0) is None


class TestCircuitBreaker:
    def test_opens_on_scan_failures(self):
        cb = CircuitBreaker()
        opened = False
        for i in range(SCAN_FAILURE_LIMIT):
            opened = cb.record_scan_failure(now=100.0 + i)
        assert opened is True
        assert cb.is_open is True

    def test_scan_failures_outside_window_do_not_open(self):
        cb = CircuitBreaker()
        # Spread failures beyond the 60s window so they prune.
        cb.record_scan_failure(now=0.0)
        cb.record_scan_failure(now=100.0)
        opened = cb.record_scan_failure(now=200.0)
        assert opened is False
        assert cb.is_open is False

    def test_opens_on_crashes(self):
        cb = CircuitBreaker()
        opened = False
        for i in range(CRASH_LIMIT):
            opened = cb.record_crash(now=100.0 + i)
        assert opened is True

    def test_crashes_outside_window_prune(self):
        cb = CircuitBreaker()
        # 10 min window; space crashes 200s apart so only recent ones count.
        for i in range(CRASH_LIMIT - 1):
            cb.record_crash(now=i * 200.0)
        # Latest crash far in the future prunes older ones.
        opened = cb.record_crash(now=10_000.0)
        assert opened is False

    def test_reset_closes(self):
        cb = CircuitBreaker()
        for i in range(SCAN_FAILURE_LIMIT):
            cb.record_scan_failure(now=100.0 + i)
        assert cb.is_open
        cb.reset()
        assert cb.is_open is False
