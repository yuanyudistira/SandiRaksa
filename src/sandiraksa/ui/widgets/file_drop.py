"""
File drop zone widget.

Drag & drop area for adding files to a project.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from sandiraksa.app.i18n import tr
from sandiraksa.ui.theme import (
    BORDER_RADIUS,
    FONT_SIZE,
    SPACING,
    ColorPalette,
)

if TYPE_CHECKING:
    pass

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    ".csv", ".xlsx", ".xls",  # Tabular
    ".txt", ".log", ".md",     # Text
    ".json", ".xml", ".html",  # Structured text
    ".docx", ".doc",           # Word (coming soon)
    ".pptx", ".ppt",           # PowerPoint (coming soon)
}


class FileDropZone(QFrame):
    """
    Drop zone for file drag & drop.

    Emits files_dropped signal with list of valid file paths.
    """

    files_dropped = Signal(list)  # list[Path]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._setup_ui()
        self._is_dragging = False
        self._apply_style(dragging=False)

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(SPACING.SM)

        # Icon
        self._icon = QLabel("📄")
        self._icon.setStyleSheet(f"font-size: {FONT_SIZE.HERO}px;")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon)

        # Main text
        self._title = QLabel(tr("project_view.drop_files"))
        self._title.setStyleSheet(
            f"font-size: {FONT_SIZE.LG}px; "
            f"font-weight: 600; "
            f"color: {ColorPalette.GRAY_700.value};"
        )
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

        # Hint text
        self._hint = QLabel(tr("project_view.drop_hint"))
        self._hint.setStyleSheet(
            f"font-size: {FONT_SIZE.MD}px; color: {ColorPalette.GRAY_500.value};"
        )
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._hint)

        # Supported formats
        self._formats = QLabel(tr("project_view.supported_formats"))
        self._formats.setStyleSheet(
            f"font-size: {FONT_SIZE.SM}px; "
            f"color: {ColorPalette.GRAY_400.value}; "
            f"margin-top: {SPACING.SM}px;"
        )
        self._formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._formats)

        self.setMinimumHeight(200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _apply_style(self, dragging: bool = False) -> None:
        """Apply visual style based on drag state."""
        if dragging:
            border_color = ColorPalette.PRIMARY.value
            bg_color = "#eff6ff"  # Light blue
        else:
            border_color = ColorPalette.GRAY_300.value
            bg_color = ColorPalette.GRAY_50.value

        self.setStyleSheet(
            f"FileDropZone {{ "
            f"background-color: {bg_color}; "
            f"border: 2px dashed {border_color}; "
            f"border-radius: {BORDER_RADIUS.LG}px; "
            f"}}"
        )

    def mousePressEvent(self, event: object) -> None:
        """Handle click to open file dialog."""
        self._open_file_dialog()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter."""
        if event.mimeData().hasUrls():
            # Check if any files are supported
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                        event.acceptProposedAction()
                        self._is_dragging = True
                        self._apply_style(dragging=True)
                        return
        event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        """Handle drag leave."""
        self._is_dragging = False
        self._apply_style(dragging=False)

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle file drop."""
        self._is_dragging = False
        self._apply_style(dragging=False)

        valid_files: list[Path] = []

        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    valid_files.append(path)
                elif path.is_dir():
                    # Recursively find supported files in directory
                    for ext in SUPPORTED_EXTENSIONS:
                        valid_files.extend(path.rglob(f"*{ext}"))

        if valid_files:
            self.files_dropped.emit(valid_files)
            event.acceptProposedAction()
        else:
            event.ignore()

    def _open_file_dialog(self) -> None:
        """Open native file dialog."""
        extensions = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS))
        file_filter = f"Supported Documents ({extensions});;All Files (*.*)"

        files, _ = QFileDialog.getOpenFileNames(
            self,
            tr("project_view.add_files"),
            "",
            file_filter,
        )

        if files:
            valid_files = [
                Path(f) for f in files if Path(f).suffix.lower() in SUPPORTED_EXTENSIONS
            ]
            if valid_files:
                self.files_dropped.emit(valid_files)


__all__ = ["FileDropZone", "SUPPORTED_EXTENSIONS"]
