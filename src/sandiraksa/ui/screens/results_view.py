"""
Results View Screen.

Shows protection results with download options.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sandiraksa.app.i18n import tr
from sandiraksa.ui.theme import ColorPalette, FONT_SIZE, SPACING
from sandiraksa.ui.widgets import Card, SectionHeader, StatusBadge

if TYPE_CHECKING:
    pass


class ResultsSummaryCard(Card):
    """Summary card showing protection results."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Success icon
        icon = QLabel("✅")
        icon.setStyleSheet(f"font-size: {FONT_SIZE.HERO}px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.add_widget(icon)

        # Title
        title = QLabel(tr("results.title"))
        title.setStyleSheet(
            f"font-size: {FONT_SIZE.XL}px; "
            f"font-weight: bold; "
            f"color: {ColorPalette.GRAY_800.value};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.add_widget(title)

        # Stats
        self._protected_label = QLabel()
        self._protected_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.add_widget(self._protected_label)

        self._tokens_label = QLabel()
        self._tokens_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.add_widget(self._tokens_label)

    def set_stats(self, protected_count: int, tokens_count: int) -> None:
        """Set summary statistics."""
        self._protected_label.setText(
            tr("results.protected_count", count=protected_count)
        )
        self._protected_label.setStyleSheet(
            f"font-size: {FONT_SIZE.LG}px; color: {ColorPalette.SUCCESS.value};"
        )

        self._tokens_label.setText(
            tr("results.tokens_generated", count=tokens_count)
        )
        self._tokens_label.setStyleSheet(
            f"font-size: {FONT_SIZE.MD}px; color: {ColorPalette.GRAY_600.value};"
        )


class ResultsViewScreen(QWidget):
    """
    Screen showing protection results.

    Allows previewing and downloading protected files.
    """

    download_file = Signal(str)  # file_id
    download_all = Signal()
    open_folder = Signal()
    back_requested = Signal()
    done_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._results: list[dict] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.XL, SPACING.XL, SPACING.XL, SPACING.XL)
        layout.setSpacing(SPACING.LG)

        # Splitter for layout
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Summary
        self._summary = ResultsSummaryCard()
        self._summary.setFixedWidth(300)
        splitter.addWidget(self._summary)

        # Right: File list and preview
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(SPACING.MD)

        # Output files section
        files_header = SectionHeader(tr("results.output_files"))
        right_layout.addWidget(files_header)

        # File table
        self._file_table = QTableWidget()
        self._file_table.setColumnCount(3)
        self._file_table.setHorizontalHeaderLabels(["File", "Status", ""])
        self._file_table.horizontalHeader().setStretchLastSection(False)
        self._file_table.setColumnWidth(0, 300)
        self._file_table.setColumnWidth(1, 100)
        self._file_table.setColumnWidth(2, 150)
        self._file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._file_table.verticalHeader().setVisible(False)
        self._file_table.itemSelectionChanged.connect(self._on_file_selected)
        right_layout.addWidget(self._file_table)

        # Preview section
        preview_header = SectionHeader(tr("results.preview"))
        right_layout.addWidget(preview_header)

        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMaximumHeight(200)
        self._preview.setStyleSheet(
            f"font-family: 'Consolas', 'Monaco', monospace; "
            f"font-size: {FONT_SIZE.SM}px; "
            f"background-color: {ColorPalette.GRAY_50.value};"
        )
        right_layout.addWidget(self._preview)

        splitter.addWidget(right_panel)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter, stretch=1)

        # Bottom actions
        actions = QHBoxLayout()

        back_btn = QPushButton(tr("buttons.back"))
        back_btn.setProperty("secondary", True)
        back_btn.clicked.connect(self.back_requested.emit)
        actions.addWidget(back_btn)

        actions.addStretch()

        open_folder_btn = QPushButton(tr("results.open_folder"))
        open_folder_btn.setProperty("secondary", True)
        open_folder_btn.clicked.connect(self.open_folder.emit)
        actions.addWidget(open_folder_btn)

        download_all_btn = QPushButton(tr("results.download_all"))
        download_all_btn.clicked.connect(self.download_all.emit)
        actions.addWidget(download_all_btn)

        done_btn = QPushButton(tr("buttons.finish"))
        done_btn.clicked.connect(self.done_requested.emit)
        actions.addWidget(done_btn)

        layout.addLayout(actions)

    def set_results(
        self,
        results: list[dict],
        protected_count: int,
        tokens_count: int,
    ) -> None:
        """
        Set protection results.

        Args:
            results: List of result dicts with id, name, status, preview, path
            protected_count: Total protected items.
            tokens_count: Total tokens generated.
        """
        self._results = results
        self._summary.set_stats(protected_count, tokens_count)
        self._refresh_file_list()

    def _refresh_file_list(self) -> None:
        """Refresh the file list."""
        self._file_table.setRowCount(len(self._results))

        for row, result in enumerate(self._results):
            # File name
            name_item = QTableWidgetItem(result.get("name", "Unknown"))
            name_item.setData(Qt.ItemDataRole.UserRole, result.get("id"))
            self._file_table.setItem(row, 0, name_item)

            # Status
            status = result.get("status", "ready")
            status_colors = {
                "ready": ColorPalette.SUCCESS.value,
                "error": ColorPalette.ERROR.value,
            }
            badge = StatusBadge(status.title(), status_colors.get(status, ColorPalette.GRAY_500.value))
            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(4, 4, 4, 4)
            container_layout.addWidget(badge)
            self._file_table.setCellWidget(row, 1, container)

            # Download button
            download_btn = QPushButton(tr("results.download"))
            download_btn.setProperty("secondary", True)
            download_btn.clicked.connect(
                lambda checked, fid=result.get("id"): self._on_download(fid)
            )
            self._file_table.setCellWidget(row, 2, download_btn)

    def _on_file_selected(self) -> None:
        """Handle file selection for preview."""
        selected = self._file_table.selectedItems()
        if selected:
            row = selected[0].row()
            if row < len(self._results):
                preview = self._results[row].get("preview", "")
                self._preview.setPlainText(preview)
        else:
            self._preview.clear()

    def _on_download(self, file_id: str) -> None:
        """Handle download button click."""
        self.download_file.emit(file_id)


__all__ = ["ResultsViewScreen"]
