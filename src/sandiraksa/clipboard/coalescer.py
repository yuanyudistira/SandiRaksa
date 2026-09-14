"""
Clipboard event coalescer (design 23, 24).

Clipboard events arrive in bursts. This coalescer implements:
  * a 250 ms debounce window (design 23);
  * a single pending request - "latest wins" (design 24);
  * a hard cap of <= 4 automatic scan starts per second (design 23);
  * a bounded queue (exactly one slot) - never unbounded (design 23).

This is pure scheduling logic; it holds no clipboard text itself beyond the
single pending snapshot and performs no detection. It is Qt-free so it can be
unit-tested deterministically by injecting a clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sandiraksa.clipboard.models import ClipboardSnapshot

DEBOUNCE_SECONDS = 0.250
MAX_SCANS_PER_SECOND = 4
_MIN_INTERVAL = 1.0 / MAX_SCANS_PER_SECOND  # 250 ms between scan starts


@dataclass
class _Pending:
    snapshot: ClipboardSnapshot
    ready_at: float  # monotonic time when debounce elapses


class EventCoalescer:
    """
    Debounce + latest-wins coalescer.

    Usage pattern (driven by the controller, which owns a QTimer):
        coalescer.submit(snapshot, now)     # on each clipboard event
        ...
        due = coalescer.due(now)            # poll; returns a snapshot or None
        if due: start_scan(due)

    ``submit`` always replaces any pending snapshot (latest wins). ``due``
    returns the pending snapshot only when both the debounce window has elapsed
    AND the rate limit permits another scan start.
    """

    def __init__(
        self,
        debounce_seconds: float = DEBOUNCE_SECONDS,
        min_interval_seconds: float = _MIN_INTERVAL,
    ) -> None:
        self._debounce = debounce_seconds
        self._min_interval = min_interval_seconds
        self._pending: _Pending | None = None
        self._last_scan_started_at: float | None = None

    def submit(self, snapshot: ClipboardSnapshot, now: float) -> None:
        """Register the latest observed snapshot, replacing any pending one."""
        self._pending = _Pending(
            snapshot=snapshot,
            ready_at=now + self._debounce,
        )

    def has_pending(self) -> bool:
        return self._pending is not None

    def next_wait(self, now: float) -> float | None:
        """
        Seconds until the pending snapshot could next be dispatched, or None if
        nothing is pending. Useful for scheduling a timer precisely.
        """
        if self._pending is None:
            return None
        debounce_wait = max(0.0, self._pending.ready_at - now)
        rate_wait = 0.0
        if self._last_scan_started_at is not None:
            rate_wait = max(
                0.0, (self._last_scan_started_at + self._min_interval) - now
            )
        return max(debounce_wait, rate_wait)

    def due(self, now: float) -> ClipboardSnapshot | None:
        """
        Return the pending snapshot if it is ready to scan now, else None.

        "Ready" requires the debounce window elapsed and the per-second rate
        limit satisfied. On return, the pending slot is cleared and the scan
        start time recorded (design 23, 24).
        """
        if self._pending is None:
            return None
        if now < self._pending.ready_at:
            return None
        if (
            self._last_scan_started_at is not None
            and now < self._last_scan_started_at + self._min_interval
        ):
            return None

        snapshot = self._pending.snapshot
        self._pending = None
        self._last_scan_started_at = now
        return snapshot

    def clear(self) -> None:
        """Drop any pending snapshot (e.g. on pause/stop)."""
        self._pending = None


__all__ = [
    "EventCoalescer",
    "DEBOUNCE_SECONDS",
    "MAX_SCANS_PER_SECOND",
]
