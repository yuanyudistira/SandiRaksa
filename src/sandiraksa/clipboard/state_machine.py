"""
Validated state machines for the clipboard monitor and detection worker.

Design 8 (monitor) and design 9 (worker) define the allowed states and
transitions. This module enforces them: an illegal transition raises, so a
programming error cannot silently leave the guard in an inconsistent state.

Key safety rule (design 8): a watcher/health failure must never leave the
monitor in ACTIVE. The transition table encodes this - the only ways into
ACTIVE are from STARTING or from PAUSED (explicit resume) / DEGRADED
(explicit recovery), never as a fallthrough from an error path.
"""

from __future__ import annotations

import logging

from sandiraksa.clipboard.models import ClipboardMonitorState, WorkerState

logger = logging.getLogger(__name__)


class InvalidTransition(RuntimeError):
    """Raised when an illegal state transition is attempted."""


# Allowed monitor transitions (design 8).
_MONITOR_TRANSITIONS: dict[ClipboardMonitorState, set[ClipboardMonitorState]] = {
    ClipboardMonitorState.OFF: {
        ClipboardMonitorState.STARTING,
    },
    ClipboardMonitorState.STARTING: {
        ClipboardMonitorState.ACTIVE,
        ClipboardMonitorState.USER_INITIATED_ONLY,
        ClipboardMonitorState.PERMISSION_REQUIRED,
        ClipboardMonitorState.UNSUPPORTED,
        ClipboardMonitorState.DEGRADED,
        ClipboardMonitorState.ERROR,
        ClipboardMonitorState.STOPPING,
    },
    ClipboardMonitorState.ACTIVE: {
        ClipboardMonitorState.PAUSED,
        ClipboardMonitorState.DEGRADED,
        ClipboardMonitorState.ERROR,
        ClipboardMonitorState.STOPPING,
        # Capability can drop to manual-only at runtime (e.g. permission lost).
        ClipboardMonitorState.USER_INITIATED_ONLY,
    },
    ClipboardMonitorState.PAUSED: {
        ClipboardMonitorState.ACTIVE,
        ClipboardMonitorState.STOPPING,
        ClipboardMonitorState.ERROR,
    },
    ClipboardMonitorState.DEGRADED: {
        # Recovery only via explicit re-activation after health check.
        ClipboardMonitorState.ACTIVE,
        ClipboardMonitorState.USER_INITIATED_ONLY,
        ClipboardMonitorState.ERROR,
        ClipboardMonitorState.STOPPING,
    },
    ClipboardMonitorState.USER_INITIATED_ONLY: {
        ClipboardMonitorState.ACTIVE,
        ClipboardMonitorState.PAUSED,
        ClipboardMonitorState.DEGRADED,
        ClipboardMonitorState.ERROR,
        ClipboardMonitorState.STOPPING,
    },
    ClipboardMonitorState.PERMISSION_REQUIRED: {
        ClipboardMonitorState.STARTING,  # retry after permission granted
        ClipboardMonitorState.STOPPING,
        ClipboardMonitorState.ERROR,
    },
    ClipboardMonitorState.UNSUPPORTED: {
        ClipboardMonitorState.STOPPING,
    },
    ClipboardMonitorState.ERROR: {
        ClipboardMonitorState.STARTING,  # explicit retry
        ClipboardMonitorState.STOPPING,
    },
    ClipboardMonitorState.STOPPING: {
        ClipboardMonitorState.OFF,
    },
}


# Allowed worker transitions (design 9).
_WORKER_TRANSITIONS: dict[WorkerState, set[WorkerState]] = {
    WorkerState.STOPPED: {
        WorkerState.STARTING,
    },
    WorkerState.STARTING: {
        WorkerState.READY,
        WorkerState.DEGRADED,
        WorkerState.ERROR,
        WorkerState.STOPPING,
    },
    WorkerState.READY: {
        WorkerState.SCANNING,
        WorkerState.STOPPING,
        WorkerState.DEGRADED,
        WorkerState.ERROR,
    },
    WorkerState.SCANNING: {
        WorkerState.READY,
        WorkerState.DEGRADED,
        WorkerState.ERROR,
        WorkerState.STOPPING,
    },
    WorkerState.DEGRADED: {
        WorkerState.STARTING,  # restart
        WorkerState.ERROR,
        WorkerState.STOPPING,
    },
    WorkerState.ERROR: {
        WorkerState.STARTING,  # explicit restart / circuit reset
        WorkerState.STOPPING,
    },
    WorkerState.STOPPING: {
        WorkerState.STOPPED,
    },
}


class _StateMachine:
    """Generic guarded state machine over a transition table."""

    def __init__(self, initial, table: dict) -> None:
        self._state = initial
        self._table = table

    @property
    def state(self):
        return self._state

    def can_transition(self, target) -> bool:
        """True if moving to ``target`` from the current state is allowed."""
        if target == self._state:
            return True  # idempotent no-op is always allowed
        return target in self._table.get(self._state, set())

    def transition(self, target):
        """
        Move to ``target`` or raise :class:`InvalidTransition`.

        Returns the new state for convenient chaining.
        """
        if target == self._state:
            return self._state
        if target not in self._table.get(self._state, set()):
            raise InvalidTransition(
                f"illegal transition {self._state.value} -> {target.value}"
            )
        logger.debug("state %s -> %s", self._state.value, target.value)
        self._state = target
        return self._state


class MonitorStateMachine(_StateMachine):
    """Guarded monitor state machine (design 8)."""

    def __init__(
        self, initial: ClipboardMonitorState = ClipboardMonitorState.OFF
    ) -> None:
        super().__init__(initial, _MONITOR_TRANSITIONS)


class WorkerStateMachine(_StateMachine):
    """Guarded worker state machine (design 9)."""

    def __init__(self, initial: WorkerState = WorkerState.STOPPED) -> None:
        super().__init__(initial, _WORKER_TRANSITIONS)


__all__ = [
    "InvalidTransition",
    "MonitorStateMachine",
    "WorkerStateMachine",
]
