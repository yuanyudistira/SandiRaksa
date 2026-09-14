"""Sprint 5 tests: event coalescer (debounce, latest-wins, rate limit)."""

from __future__ import annotations

from sandiraksa.clipboard.coalescer import EventCoalescer
from sandiraksa.clipboard.models import ClipboardSnapshot


def _snap(gen, text, t):
    return ClipboardSnapshot.create(generation=gen, text=text, observed_at_monotonic=t)


class TestDebounce:
    def test_not_due_before_debounce(self):
        c = EventCoalescer(debounce_seconds=0.25, min_interval_seconds=0.25)
        c.submit(_snap(1, "a", 0.0), now=0.0)
        assert c.due(now=0.10) is None  # within debounce
        assert c.due(now=0.30) is not None  # after debounce

    def test_due_returns_snapshot_and_clears(self):
        c = EventCoalescer(0.25, 0.25)
        c.submit(_snap(1, "a", 0.0), now=0.0)
        got = c.due(now=0.30)
        assert got is not None and got.text == "a"
        # Pending cleared after dispatch.
        assert c.due(now=0.40) is None


class TestLatestWins:
    def test_only_latest_survives(self):
        c = EventCoalescer(0.25, 0.25)
        c.submit(_snap(1, "A", 0.0), now=0.0)
        c.submit(_snap(2, "B", 0.05), now=0.05)
        c.submit(_snap(3, "D", 0.10), now=0.10)
        # Debounce measured from the latest submit (0.10 + 0.25 = 0.35).
        assert c.due(now=0.30) is None
        got = c.due(now=0.36)
        assert got is not None and got.text == "D"


class TestRateLimit:
    def test_max_four_per_second(self):
        # min interval 0.25s => at most 4 starts per second.
        c = EventCoalescer(debounce_seconds=0.0, min_interval_seconds=0.25)
        c.submit(_snap(1, "a", 0.0), now=0.0)
        assert c.due(now=0.0) is not None  # first allowed

        c.submit(_snap(2, "b", 0.05), now=0.05)
        # Only 0.05s since last start; rate limit blocks.
        assert c.due(now=0.05) is None
        # After 0.25s it is allowed again.
        assert c.due(now=0.25) is not None


class TestNextWaitAndClear:
    def test_next_wait_none_when_empty(self):
        assert EventCoalescer().next_wait(now=1.0) is None

    def test_next_wait_reports_remaining(self):
        c = EventCoalescer(0.25, 0.25)
        c.submit(_snap(1, "a", 0.0), now=0.0)
        w = c.next_wait(now=0.10)
        assert w is not None and abs(w - 0.15) < 1e-6

    def test_clear(self):
        c = EventCoalescer(0.25, 0.25)
        c.submit(_snap(1, "a", 0.0), now=0.0)
        c.clear()
        assert c.has_pending() is False
        assert c.due(now=1.0) is None
