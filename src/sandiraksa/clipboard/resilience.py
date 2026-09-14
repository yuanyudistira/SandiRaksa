"""
Worker resilience policy (design 34, 35, 36).

Pure, Qt-free decision logic for heartbeat health, restart backoff, and the
circuit breaker. Kept separate from the QProcess supervisor so the safety-
critical rules are deterministically unit-testable with an injected clock.
"""

from __future__ import annotations

from enum import Enum

# Heartbeat (design 34).
HEARTBEAT_INTERVAL_S = 2.0
HEARTBEAT_UNHEALTHY_S = 6.0

# Restart backoff schedule in seconds (design 35). After the last entry is
# exhausted, the breaker opens (ERROR).
RESTART_BACKOFF_S = [1.0, 2.0, 5.0, 15.0]
MAX_RESTARTS = len(RESTART_BACKOFF_S)  # 5th failure -> open circuit

# Circuit breaker thresholds (design 36).
SCAN_FAILURE_LIMIT = 3
SCAN_FAILURE_WINDOW_S = 60.0
CRASH_LIMIT = 5
CRASH_WINDOW_S = 600.0  # 10 minutes


class HeartbeatHealth(Enum):
    HEALTHY = "healthy"
    LATE = "late"
    UNRESPONSIVE = "unresponsive"
    DEAD = "dead"


def heartbeat_health(
    last_ack_monotonic: float | None,
    now: float,
    *,
    interval: float = HEARTBEAT_INTERVAL_S,
    unhealthy: float = HEARTBEAT_UNHEALTHY_S,
) -> HeartbeatHealth:
    """
    Classify heartbeat health from the last ack time (design 34).

    * within one interval -> HEALTHY
    * beyond interval but under the unhealthy threshold -> LATE
    * beyond the unhealthy threshold -> UNRESPONSIVE
    * never acked -> DEAD
    """
    if last_ack_monotonic is None:
        return HeartbeatHealth.DEAD
    age = now - last_ack_monotonic
    if age <= interval:
        return HeartbeatHealth.HEALTHY
    if age <= unhealthy:
        return HeartbeatHealth.LATE
    return HeartbeatHealth.UNRESPONSIVE


def backoff_for_attempt(attempt: int) -> float | None:
    """
    Backoff delay (seconds) before restart ``attempt`` (1-based), or None if the
    schedule is exhausted and the circuit should open (design 35).
    """
    if attempt < 1 or attempt > len(RESTART_BACKOFF_S):
        return None
    return RESTART_BACKOFF_S[attempt - 1]


class CircuitBreaker:
    """
    Trips to OPEN on repeated scan failures or worker crashes (design 36).

    * >= SCAN_FAILURE_LIMIT scan failures within SCAN_FAILURE_WINDOW_S, or
    * >= CRASH_LIMIT worker crashes within CRASH_WINDOW_S
    -> open (automatic scanning paused; main app keeps running).
    """

    def __init__(self) -> None:
        self._scan_failures: list[float] = []
        self._crashes: list[float] = []
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open

    def record_scan_failure(self, now: float) -> bool:
        """Record a scan failure; return True if the breaker is now open."""
        self._scan_failures.append(now)
        self._prune(now)
        if len(self._scan_failures) >= SCAN_FAILURE_LIMIT:
            self._open = True
        return self._open

    def record_crash(self, now: float) -> bool:
        """Record a worker crash; return True if the breaker is now open."""
        self._crashes.append(now)
        self._prune(now)
        if len(self._crashes) >= CRASH_LIMIT:
            self._open = True
        return self._open

    def reset(self) -> None:
        """Manual reset (Retry) - clears counters and closes the circuit."""
        self._scan_failures.clear()
        self._crashes.clear()
        self._open = False

    def _prune(self, now: float) -> None:
        self._scan_failures = [
            t for t in self._scan_failures if now - t <= SCAN_FAILURE_WINDOW_S
        ]
        self._crashes = [t for t in self._crashes if now - t <= CRASH_WINDOW_S]


__all__ = [
    "HeartbeatHealth",
    "heartbeat_health",
    "backoff_for_attempt",
    "CircuitBreaker",
    "HEARTBEAT_INTERVAL_S",
    "HEARTBEAT_UNHEALTHY_S",
    "RESTART_BACKOFF_S",
    "MAX_RESTARTS",
    "SCAN_FAILURE_LIMIT",
    "SCAN_FAILURE_WINDOW_S",
    "CRASH_LIMIT",
    "CRASH_WINDOW_S",
]
