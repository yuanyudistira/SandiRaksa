"""
Run a blocking function off the GUI thread while keeping the UI responsive.

Some operations must produce a result before the flow can continue (e.g.
analyzing a workbook's columns before showing the column-selection dialog, or
restoring a file before reporting the outcome). Running them directly on the
GUI thread freezes the window ("Not Responding") and, on Windows, can end in a
forced close.

`run_with_busy_dialog` runs the work on a QThread and shows a small modal busy
dialog with an indeterminate progress bar. The Qt event loop keeps spinning
(the dialog's own local event loop), so the window paints and stays responsive,
but the user cannot interact with the rest of the app until the work finishes.
The function returns the worker's result synchronously to the caller, so
existing sequential code (analyze -> open dialog) needs only a minimal change.

This deliberately avoids QApplication.processEvents(): we never re-enter the
main event loop while a native read is in flight (that re-entrancy, combined
with heavy IO, was a source of instability). The heavy call runs on its own
thread; only the modal dialog's event loop runs on the GUI thread.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import QProgressDialog, QWidget


class _CallWorker(QObject):
    """Runs a no-arg callable on a worker thread and emits its result."""

    finished = Signal(object)

    def __init__(self, fn: Callable[[], object]) -> None:
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        result: object
        try:
            result = self._fn()
        except Exception as exc:  # pragma: no cover - defensive
            import traceback

            traceback.print_exc()
            result = exc
        self.finished.emit(result)


def run_with_busy_dialog(
    parent: QWidget | None,
    fn: Callable[[], object],
    message: str,
    title: str = "Mohon tunggu",
) -> object:
    """
    Run ``fn`` on a background thread, showing a modal busy dialog.

    Args:
        parent: Parent widget for the dialog.
        fn: Zero-argument callable performing the heavy work.
        message: Text shown in the busy dialog.
        title: Dialog window title.

    Returns:
        The value returned by ``fn``. If ``fn`` raised, the exception object is
        returned (callers may check ``isinstance(result, Exception)``).
    """
    thread = QThread()
    worker = _CallWorker(fn)
    worker.moveToThread(thread)

    dialog = QProgressDialog(message, "", 0, 0, parent)  # 0,0 = indeterminate
    dialog.setWindowTitle(title)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.setCancelButton(None)  # not cancellable; the work must complete
    dialog.setMinimumDuration(0)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)
    # Remove the close button so the user can't dismiss it mid-run.
    dialog.setWindowFlags(
        Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint
    )

    holder: dict[str, object] = {}

    def _on_finished(result: object) -> None:
        holder["result"] = result
        thread.quit()
        dialog.reset()
        dialog.close()

    thread.started.connect(worker.run)
    worker.finished.connect(_on_finished)
    thread.start()

    # Show the modal dialog; its event loop keeps the GUI responsive until the
    # worker finishes and closes the dialog above.
    dialog.exec()

    thread.wait()
    worker.deleteLater()

    return holder.get("result")


__all__ = ["run_with_busy_dialog"]
