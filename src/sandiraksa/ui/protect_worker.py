"""
Background protection worker.

Runs file protection (tokenization) off the GUI thread so the Qt event loop is
never blocked. Protecting a large workbook loads the whole file, iterates every
cell, and saves it back to disk — synchronous, CPU- and IO-heavy work. Doing
that on the GUI thread makes the window go "Not Responding" and, on Windows,
can end in a forced close.

This mirrors the ScanWorker pattern: move an instance to a QThread, connect the
thread's ``started`` signal to :meth:`run`, and receive the result via a queued
signal so all GUI updates happen safely on the main thread.

The heavy work itself is delegated back to the caller-provided ``protect_fn``,
which returns a plain result dict (``success``/``output_path``/``cells_protected``
/``error``). Those functions already avoid touching any Qt widgets, so they are
safe to call from a worker thread.
"""

from __future__ import annotations

import gc
from typing import Callable

from PySide6.QtCore import QObject, Signal


class ProtectWorker(QObject):
    """Protects a single file on a background thread."""

    # result dict: {success, output_path, cells_protected, error}
    finished = Signal(dict)

    def __init__(
        self,
        protect_fn: Callable[[], dict],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._protect_fn = protect_fn

    def run(self) -> None:
        """Entry point executed on the worker thread."""
        result: dict
        try:
            result = self._protect_fn()
        except Exception as exc:  # pragma: no cover - defensive
            import traceback

            traceback.print_exc()
            result = {"success": False, "error": str(exc)}
        finally:
            # Reclaim the transient allocations from loading/saving the file.
            gc.collect()
        self.finished.emit(result or {"success": False, "error": "No result"})


__all__ = ["ProtectWorker"]
