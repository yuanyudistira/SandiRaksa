"""
Scan Progress Screen.

Shows scanning progress with file-by-file status.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from sandiraksa.app.i18n import tr
from sandiraksa.ui.theme import ColorPalette, FONT_SIZE, SPACING
from sandiraksa.ui.widgets import Card, StatusBadge

if TYPE_CHECKING:
    pass


class FileProgressItem(Card):
    """Progress item for a single file."""

    def __init__(
        self,
        file_id: str,
        file_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._file_id = file_id
        self._status = "pending"

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # File name
        self._name_label = QLabel(file_name)
        self._name_label.setStyleSheet(f"color: {ColorPalette.GRAY_700.value};")
        layout.addWidget(self._name_label, stretch=1)

        # Findings count
        self._findings_label = QLabel("")
        self._findings_label.setStyleSheet(f"color: {ColorPalette.GRAY_500.value};")
        layout.addWidget(self._findings_label)

        # Status
        self._status_badge = StatusBadge("Pending", ColorPalette.GRAY_400.value)
        layout.addWidget(self._status_badge)

        self.add_layout(layout)

    @property
    def file_id(self) -> str:
        """Get file ID."""
        return self._file_id

    def set_status(self, status: str, findings: int = 0) -> None:
        """Update status display."""
        self._status = status

        status_config = {
            "pending": ("⏳", ColorPalette.GRAY_400.value),
            "scanning": ("🔍", ColorPalette.INFO.value),
            "completed": ("✓", ColorPalette.SUCCESS.value),
            "error": ("✗", ColorPalette.ERROR.value),
        }

        icon, color = status_config.get(status, ("?", ColorPalette.GRAY_400.value))
        self._status_badge.setText(f"{icon} {status.title()}")
        self._status_badge.set_color(color)

        if findings > 0:
            self._findings_label.setText(
                tr("scan.findings_found", count=findings)
            )


class ScanProgressScreen(QWidget):
    """
    Screen showing scan progress.

    Shows overall progress and per-file status.
    """

    cancel_requested = Signal()
    scan_complete = Signal(int)  # total findings

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._file_items: dict[str, FileProgressItem] = {}
        self._total_files = 0
        self._completed_files = 0
        self._total_findings = 0
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.XL, SPACING.XL, SPACING.XL, SPACING.XL)
        layout.setSpacing(SPACING.LG)

        # Title
        self._title = QLabel(tr("scan.title"))
        self._title.setStyleSheet(
            f"font-size: {FONT_SIZE.XXL}px; "
            f"font-weight: bold; "
            f"color: {ColorPalette.GRAY_800.value};"
        )
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

        # Animated icon
        self._icon = QLabel("🔍")
        self._icon.setStyleSheet(f"font-size: {FONT_SIZE.HERO}px;")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon)

        # Status text
        self._status = QLabel(tr("scan.scanning"))
        self._status.setStyleSheet(
            f"font-size: {FONT_SIZE.LG}px; color: {ColorPalette.GRAY_600.value};"
        )
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setMinimumHeight(12)
        self._progress.setTextVisible(False)
        layout.addWidget(self._progress)

        # Progress text
        self._progress_text = QLabel("")
        self._progress_text.setStyleSheet(
            f"color: {ColorPalette.GRAY_500.value};"
        )
        self._progress_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._progress_text)

        # File list scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._files_container = QWidget()
        self._files_layout = QVBoxLayout(self._files_container)
        self._files_layout.setContentsMargins(0, 0, 0, 0)
        self._files_layout.setSpacing(SPACING.SM)
        self._files_layout.addStretch()

        scroll.setWidget(self._files_container)
        layout.addWidget(scroll, stretch=1)

        # Cancel button
        actions = QHBoxLayout()
        actions.addStretch()

        self._cancel_btn = QPushButton(tr("scan.cancel"))
        self._cancel_btn.setProperty("secondary", True)
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)
        actions.addWidget(self._cancel_btn)

        actions.addStretch()
        layout.addLayout(actions)

    def reset(self) -> None:
        """Reset the screen for a new scan."""
        # Clear file items
        while self._files_layout.count() > 1:
            item = self._files_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._file_items.clear()

        self._total_files = 0
        self._completed_files = 0
        self._total_findings = 0
        self._progress.setValue(0)
        self._progress_text.setText("")
        self._status.setText(tr("scan.scanning"))
        self._icon.setText("🔍")
        self._cancel_btn.setEnabled(True)

    def set_files(self, files: list[dict]) -> None:
        """
        Set the files to be scanned.

        Args:
            files: List of file dicts with id, name
        """
        self.reset()
        self._total_files = len(files)

        for file_info in files:
            item = FileProgressItem(
                file_id=file_info["id"],
                file_name=file_info.get("name", "Unknown"),
            )
            self._file_items[file_info["id"]] = item
            self._files_layout.insertWidget(
                self._files_layout.count() - 1, item
            )

        self._update_progress_text()

    def update_file_status(
        self,
        file_id: str,
        status: str,
        findings: int = 0,
    ) -> None:
        """
        Update status for a specific file.

        Args:
            file_id: File ID.
            status: Status (pending, scanning, completed, error).
            findings: Number of findings in this file.
        """
        item = self._file_items.get(file_id)
        if item:
            item.set_status(status, findings)

            if status == "completed":
                self._completed_files += 1
                self._total_findings += findings
                self._update_progress()

    def _update_progress(self) -> None:
        """Update overall progress display."""
        if self._total_files > 0:
            percent = int(100 * self._completed_files / self._total_files)
            self._progress.setValue(percent)
        self._update_progress_text()

        # Check if complete
        if self._completed_files >= self._total_files:
            self._on_scan_complete()

    def _update_progress_text(self) -> None:
        """Update progress text."""
        self._progress_text.setText(
            tr(
                "scan.progress",
                current=self._completed_files,
                total=self._total_files,
            )
        )

    def _on_scan_complete(self) -> None:
        """Handle scan completion."""
        self._status.setText(tr("scan.scan_complete"))
        self._icon.setText("✅")
        self._cancel_btn.setEnabled(False)
        self.scan_complete.emit(self._total_findings)


__all__ = ["ScanProgressScreen"]
