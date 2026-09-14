"""
Tier A clipboard scanner worker (design 25, 26, 27).

A ``QObject`` moved to a dedicated ``QThread``. It runs the detection pipeline
entirely off the GUI thread and returns results via queued signals. It never
touches widgets or the clipboard directly (design 5.2, 5.3).

The detection engine initializes once when the worker starts and is reused for
every scan (design 27); it is never reloaded per clipboard event.
"""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QObject, Signal, Slot

from sandiraksa.clipboard.models import ScanFailure, ScanRequest, WorkerState
from sandiraksa.clipboard.pipeline import OversizedError, run_pipeline

logger = logging.getLogger(__name__)


class ClipboardScannerWorker(QObject):
    """Runs the clipboard detection pipeline on a background thread."""

    #: Emitted with a ClipboardProtectionResult on success.
    resultReady = Signal(object)
    #: Emitted with a ScanFailure (sanitized) on error.
    scanFailed = Signal(object)
    #: Emitted with a WorkerState on lifecycle changes.
    stateChanged = Signal(object)
    #: Emitted with a ScanRequest whose payload exceeded the hard size limit.
    scanSkippedOversize = Signal(object)

    def __init__(self, project_id: str | None = None) -> None:
        super().__init__()
        self._project_id = project_id
        self._engine = None
        self._context = None

    @Slot()
    def initialize(self) -> None:
        """
        Build the engine once and warm up (design 27).

        Connect a thread's ``started`` signal to this so initialization runs on
        the worker thread, not the GUI thread.
        """
        self.stateChanged.emit(WorkerState.STARTING)
        try:
            from sandiraksa.clipboard.engine_factory import (
                build_context,
                build_engine,
            )

            self._engine = build_engine()
            self._context = build_context(self._project_id)
            # Warm-up: a tiny scan so first real scan isn't penalized.
            try:
                self._context.config.enabled_entity_types = {"EMAIL_ADDRESS"}
                self._engine.analyze_text("warmup a@b.com", self._context)
            except Exception:  # pragma: no cover - warm-up is best-effort
                pass
            self.stateChanged.emit(WorkerState.READY)
        except Exception as exc:
            logger.warning("Clipboard worker init failed: %s", type(exc).__name__)
            self.stateChanged.emit(WorkerState.ERROR)

    @Slot(object)
    def scan(self, request: ScanRequest) -> None:
        """Scan one request and emit the result/failure (design 26)."""
        if self._engine is None or self._context is None:
            # Lazy init if the caller didn't wire initialize().
            self.initialize()
            if self._engine is None:
                self.scanFailed.emit(
                    ScanFailure(
                        category="EngineUnavailable",
                        message="detection engine not initialized",
                        generation=request.generation,
                    )
                )
                return

        self.stateChanged.emit(WorkerState.SCANNING)
        started = time.perf_counter()
        try:
            result = run_pipeline(request, self._engine, self._context)
            self.resultReady.emit(result)
        except OversizedError:
            # Not an error: too large for automatic scan (design 42).
            self.scanSkippedOversize.emit(request)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            # Sanitized failure only; never include raw text (design 60).
            self.scanFailed.emit(
                ScanFailure.from_exception(
                    exc, generation=request.generation, latency_ms=latency_ms
                )
            )
        finally:
            self.stateChanged.emit(WorkerState.READY)


__all__ = ["ClipboardScannerWorker"]
