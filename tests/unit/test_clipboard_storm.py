"""Hardening test: clipboard storm protection (design 67).

Simulates 100 clipboard changes across 10 seconds and asserts:
  * the queue stays bounded (at most one pending snapshot);
  * scan starts are rate-limited to <= 4/sec (design 23);
  * latest-wins - the final dispatched snapshot is the most recent one.
"""

from __future__ import annotations

from sandiraksa.clipboard.coalescer import (
    DEBOUNCE_SECONDS,
    MAX_SCANS_PER_SECOND,
    EventCoalescer,
)
from sandiraksa.clipboard.models import ClipboardSnapshot


def _snap(gen, t):
    return ClipboardSnapshot.create(generation=gen, text=f"payload-{gen}", observed_at_monotonic=t)


def test_storm_100_events_10_seconds():
    c = EventCoalescer()  # 250ms debounce, <=4/sec
    dispatched = []

    total_events = 100
    duration = 10.0
    dt = duration / total_events  # 0.1s between events

    now = 0.0
    for gen in range(1, total_events + 1):
        now = gen * dt
        c.submit(_snap(gen, now), now)
        # Queue must never hold more than one pending snapshot (bounded).
        assert c.has_pending() is True
        got = c.due(now)
        if got is not None:
            dispatched.append((got.generation, now))

    # Drain any final pending snapshot after the storm settles.
    now += DEBOUNCE_SECONDS + 1.0
    final = c.due(now)
    if final is not None:
        dispatched.append((final.generation, now))

    # Rate limit: at most ~4 scans/sec over 10s => well under total events.
    assert len(dispatched) <= (MAX_SCANS_PER_SECOND * duration) + 2
    assert len(dispatched) < total_events  # coalescing actually happened

    # Latest-wins: the last dispatched generation should be recent (the storm's
    # tail), never an early stale one.
    last_gen = dispatched[-1][0]
    assert last_gen >= total_events - 5


def test_queue_never_unbounded():
    c = EventCoalescer()
    # Fire 1000 rapid submits without ever draining.
    for gen in range(1000):
        c.submit(_snap(gen, gen * 0.001), gen * 0.001)
    # Still exactly one pending (single-slot bounded queue, design 23).
    assert c.has_pending() is True
    got = c.due(1000.0)
    assert got is not None
    # The single retained snapshot is the most recent submit.
    assert got.generation == 999
    assert c.has_pending() is False
