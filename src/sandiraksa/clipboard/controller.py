"""
Clipboard Privacy Guard controller (Tier A) - design 5.1, 19, 23, 24, 51, 52.

Runs on the GUI thread. It owns and coordinates:
  * the platform backend (clipboard read/write/observe);
  * the generation tracker + fingerprint identity (design 16, 17);
  * the debounce/latest-wins coalescer (design 23, 24) via a QTimer;
  * the detection worker on a dedicated QThread (design 25);
  * feedback-loop protection for self-writes (design 19);
  * stale-result rejection (design 51) and safe-copy validation (design 52).

The GUI thread stays lightweight (design 5.1): it only reads clipboard text,
fingerprints it, enqueues immutable requests, and reacts to worker signals. It
never runs detection.

This controller is UI-agnostic: it exposes Qt signals that a panel/tray/window
connect to. It does not create widgets itself.
"""

from __future__ import annotations

import logging
import time
import uuid

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from sandiraksa.clipboard.backends import create_backend, make_origin_marker
from sandiraksa.clipboard.backends.base import ClipboardBackend
from sandiraksa.clipboard.coalescer import EventCoalescer
from sandiraksa.clipboard.models import (
    ClipboardCapability,
    ClipboardMonitorState,
    ClipboardProtectionResult,
    ClipboardSnapshot,
    PendingOwnWrite,
    ScanFailure,
    ScanRequest,
    WorkerState,
)
from sandiraksa.clipboard.safe_logging import log_failure, log_scan_metadata
from sandiraksa.clipboard.state_machine import (
    InvalidTransition,
    MonitorStateMachine,
)
from sandiraksa.clipboard.worker_thread import ClipboardScannerWorker

logger = logging.getLogger("sandiraksa.clipboard")

#: How long a self-write fingerprint is trusted to suppress its echo (design 19).
_OWN_WRITE_TTL = 2.0
#: Coalescer poll cadence (ms). The timer is short; actual dispatch is gated by
#: the coalescer's debounce + rate limit.
_POLL_INTERVAL_MS = 100


class ClipboardGuardController(QObject):
    """GUI-thread coordinator for the Clipboard Privacy Guard (Tier A)."""

    #: Monitor state changed -> new ClipboardMonitorState.
    stateChanged = Signal(object)
    #: A protection result is ready and current -> ClipboardProtectionResult.
    resultReady = Signal(object)
    #: A scan failed (sanitized) -> ScanFailure.
    scanFailed = Signal(object)
    #: Clipboard payload too large for automatic scan (design 42).
    oversizeSkipped = Signal()

    def __init__(
        self,
        backend: ClipboardBackend | None = None,
        project_id: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._backend = backend or create_backend()
        self._project_id = project_id
        self._sm = MonitorStateMachine()
        self._coalescer = EventCoalescer()

        self._generation = 0
        self._current_fingerprint: str | None = None
        self._pending_own_write: PendingOwnWrite | None = None
        self._latest_result: ClipboardProtectionResult | None = None

        self._thread: QThread | None = None
        self._worker: ClipboardScannerWorker | None = None

        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._drain_coalescer)

        # Single-shot timer for timed pauses (design 58); auto-resumes.
        self._resume_timer = QTimer(self)
        self._resume_timer.setSingleShot(True)
        self._resume_timer.timeout.connect(self.resume)

    # -- public API ------------------------------------------------------
    @property
    def state(self) -> ClipboardMonitorState:
        return self._sm.state

    def capability(self) -> ClipboardCapability:
        return self._backend.capability()

    def start(self) -> None:
        """Enable monitoring (design 8 STARTING -> ACTIVE / fallback)."""
        if self._sm.state not in (
            ClipboardMonitorState.OFF,
            ClipboardMonitorState.ERROR,
            ClipboardMonitorState.PERMISSION_REQUIRED,
        ):
            return
        self._set_state(ClipboardMonitorState.STARTING)

        cap = self._backend.capability()
        if cap == ClipboardCapability.UNAVAILABLE:
            self._set_state(ClipboardMonitorState.UNSUPPORTED)
            return

        self._start_worker()

        if cap == ClipboardCapability.USER_INITIATED_ONLY:
            # No background observation; user must trigger scans manually.
            self._set_state(ClipboardMonitorState.USER_INITIATED_ONLY)
            return

        try:
            self._backend.start(self._on_clipboard_changed)
        except Exception as exc:
            logger.warning("backend start failed: %s", type(exc).__name__)
            self._set_state(ClipboardMonitorState.ERROR)
            return

        self._timer.start()
        self._set_state(ClipboardMonitorState.ACTIVE)

    def stop(self) -> None:
        """Disable monitoring and tear down worker (design 64)."""
        if self._sm.state in (ClipboardMonitorState.OFF,):
            return
        self._set_state(ClipboardMonitorState.STOPPING)
        self._timer.stop()
        self._coalescer.clear()
        try:
            self._backend.stop()
        except Exception:
            pass
        self._teardown_worker()
        self._set_state(ClipboardMonitorState.OFF)

    def pause(self, minutes: float | None = None) -> None:
        """
        Pause automatic scanning (design 58, 62).

        If ``minutes`` is given, scanning auto-resumes after that duration; a
        timed pause must resume automatically (design 58). ``None`` pauses until
        the user explicitly resumes.
        """
        if self._sm.state == ClipboardMonitorState.ACTIVE:
            self._timer.stop()
            self._coalescer.clear()
            self._set_state(ClipboardMonitorState.PAUSED)
            if minutes is not None:
                # Auto-resume timer (single-shot).
                self._resume_timer.start(int(minutes * 60_000))

    def resume(self) -> None:
        """Resume automatic scanning after a pause."""
        self._resume_timer.stop()
        if self._sm.state == ClipboardMonitorState.PAUSED:
            self._set_state(ClipboardMonitorState.ACTIVE)
            self._timer.start()

    def scan_current_clipboard(self) -> None:
        """
        Manually scan the current clipboard (design 7.2).

        Works in ACTIVE and USER_INITIATED_ONLY modes; the entry point for the
        tray/menu "Scan current clipboard" action.
        """
        text = self._backend.read_text()
        if not text:
            return
        snapshot = self._new_snapshot(text)
        self._dispatch_scan(snapshot)

    def copy_protected(self, result: ClipboardProtectionResult) -> bool:
        """
        Write the protected text to the clipboard, if still valid (design 52).

        Returns True if written, False if rejected because the clipboard has
        changed since the scan or the result expired.
        """
        now = time.monotonic()
        if result.is_expired(now):
            return False
        if result.generation != self._generation:
            return False
        current_fp = self._backend.current_fingerprint()
        if current_fp != result.source_fingerprint:
            return False

        op_id = uuid.uuid4().hex
        marker = make_origin_marker(op_id)
        # Register the expected self-write so its echo event is ignored (design 19).
        self._pending_own_write = PendingOwnWrite(
            fingerprint=self._fingerprint(result.safe_text),
            expires_at_monotonic=now + _OWN_WRITE_TTL,
            operation_id=op_id,
        )
        self._backend.write_safe_text(result.safe_text, marker)
        return True

    # -- clipboard event handling (GUI thread) ---------------------------
    def _on_clipboard_changed(self) -> None:
        """Handle a backend change event. Lightweight only (design 5.1)."""
        text = self._backend.read_text()
        if text is None:
            return
        fingerprint = self._fingerprint(text)
        now = time.monotonic()

        # Feedback-loop protection: ignore our own write's echo (design 19).
        own = self._pending_own_write
        if own is not None and own.matches(fingerprint, now):
            self._pending_own_write = None
            return

        snapshot = self._new_snapshot(text, fingerprint=fingerprint, now=now)
        # Debounce/latest-wins: enqueue, the timer will dispatch (design 23, 24).
        self._coalescer.submit(snapshot, now)

    def _drain_coalescer(self) -> None:
        now = time.monotonic()
        snapshot = self._coalescer.due(now)
        if snapshot is not None:
            self._dispatch_scan(snapshot)

    def _dispatch_scan(self, snapshot: ClipboardSnapshot) -> None:
        if self._worker is None:
            return
        request = ScanRequest(
            request_id=uuid.uuid4().hex,
            generation=snapshot.generation,
            fingerprint=snapshot.fingerprint,
            text=snapshot.text,
            created_monotonic=snapshot.observed_at_monotonic,
        )
        # Queued connection hands the request to the worker thread.
        self._worker.scan(request)

    # -- worker signal handlers (GUI thread) -----------------------------
    def _on_result_ready(self, result: ClipboardProtectionResult) -> None:
        # Stale-result rejection (design 51): generation + fingerprint must
        # still be current, else discard silently.
        if result.generation != self._generation:
            return
        if result.source_fingerprint != self._current_fingerprint:
            return
        if result.is_expired(time.monotonic()):
            return

        self._latest_result = result
        log_scan_metadata(
            result,
            backend=type(self._backend).__name__,
            text_length=len(result.safe_text),
        )
        # Only surface a result that actually found something to protect.
        if result.findings:
            self.resultReady.emit(result)

    def _on_scan_failed(self, failure: ScanFailure) -> None:
        log_failure(failure, backend=type(self._backend).__name__)
        self.scanFailed.emit(failure)

    def _on_oversize(self, _request) -> None:
        self.oversizeSkipped.emit()

    # -- worker lifecycle ------------------------------------------------
    def _start_worker(self) -> None:
        if self._thread is not None:
            return
        self._thread = QThread(self)
        self._worker = ClipboardScannerWorker(self._project_id)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.initialize)
        self._worker.resultReady.connect(self._on_result_ready)
        self._worker.scanFailed.connect(self._on_scan_failed)
        self._worker.scanSkippedOversize.connect(self._on_oversize)
        self._thread.start()

    def _teardown_worker(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread.deleteLater()
        if self._worker is not None:
            self._worker.deleteLater()
        self._thread = None
        self._worker = None

    # -- helpers ---------------------------------------------------------
    def _new_snapshot(
        self,
        text: str,
        fingerprint: str | None = None,
        now: float | None = None,
    ) -> ClipboardSnapshot:
        now = time.monotonic() if now is None else now
        self._generation += 1
        fp = fingerprint if fingerprint is not None else self._fingerprint(text)
        self._current_fingerprint = fp
        return ClipboardSnapshot(
            generation=self._generation,
            fingerprint=fp,
            observed_at_monotonic=now,
            text=text,
        )

    @staticmethod
    def _fingerprint(text: str) -> str:
        from sandiraksa.clipboard.fingerprint import fingerprint_text

        return fingerprint_text(text)

    def _set_state(self, target: ClipboardMonitorState) -> None:
        try:
            self._sm.transition(target)
        except InvalidTransition:
            logger.debug("ignored invalid monitor transition to %s", target.value)
            return
        self.stateChanged.emit(target)


__all__ = ["ClipboardGuardController"]
