"""
Findings Review Screen.

Shows detected PII findings for review and bulk actions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sandiraksa.app.i18n import tr
from sandiraksa.ui.theme import ColorPalette, FONT_SIZE, SPACING, get_entity_color
from sandiraksa.ui.widgets import Card, SectionHeader, StatusBadge

if TYPE_CHECKING:
    pass


class FindingSummaryCard(Card):
    """Summary card showing entity type counts."""

    filter_requested = Signal(str)  # entity_type or "" for all

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._counts: dict[str, int] = {}

        # Title
        title = QLabel(tr("findings.summary"))
        title.setStyleSheet(
            f"font-size: {FONT_SIZE.LG}px; "
            f"font-weight: 600; "
            f"color: {ColorPalette.GRAY_700.value};"
        )
        self.add_widget(title)

        # Total
        self._total_label = QLabel()
        self._total_label.setStyleSheet(
            f"font-size: {FONT_SIZE.XL}px; "
            f"font-weight: bold; "
            f"color: {ColorPalette.PRIMARY.value};"
        )
        self.add_widget(self._total_label)

        # Type breakdown container
        self._types_container = QWidget()
        self._types_layout = QVBoxLayout(self._types_container)
        self._types_layout.setContentsMargins(0, 0, 0, 0)
        self._types_layout.setSpacing(SPACING.XS)
        self.add_widget(self._types_container)

    def set_counts(self, counts: dict[str, int]) -> None:
        """Set entity type counts."""
        self._counts = counts
        total = sum(counts.values())

        self._total_label.setText(tr("findings.total_findings", count=total))

        # Clear existing items
        while self._types_layout.count() > 0:
            item = self._types_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add type rows
        for entity_type, count in sorted(counts.items(), key=lambda x: -x[1]):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            badge = StatusBadge(
                tr(f"entity_types.{entity_type}", default=entity_type),
                get_entity_color(entity_type),
            )
            row_layout.addWidget(badge)

            row_layout.addStretch()

            count_label = QLabel(str(count))
            count_label.setStyleSheet(f"color: {ColorPalette.GRAY_600.value};")
            row_layout.addWidget(count_label)

            row.setCursor(Qt.CursorShape.PointingHandCursor)
            row.mousePressEvent = lambda e, t=entity_type: self.filter_requested.emit(t)

            self._types_layout.addWidget(row)


class FindingsReviewScreen(QWidget):
    """
    Screen for reviewing and acting on findings.

    Allows bulk protection/ignore actions.
    """

    apply_treatments = Signal(list)  # list of finding_ids to protect
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._findings: list[dict] = []
        self._selected_findings: set[str] = set()
        self._current_filter: str = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.XL, SPACING.XL, SPACING.XL, SPACING.XL)
        layout.setSpacing(SPACING.LG)

        # Header
        header = SectionHeader(tr("findings.title"))
        layout.addWidget(header)

        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Summary
        self._summary = FindingSummaryCard()
        self._summary.filter_requested.connect(self._apply_filter)
        self._summary.setFixedWidth(250)
        splitter.addWidget(self._summary)

        # Right: Findings table
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(SPACING.MD)

        # Filter bar
        filter_bar = QHBoxLayout()

        self._filter_combo = QComboBox()
        self._filter_combo.addItem(tr("findings.by_type"), "")
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_bar.addWidget(self._filter_combo)

        filter_bar.addStretch()

        # Bulk actions
        self._select_all = QCheckBox(tr("buttons.select_all"))
        self._select_all.stateChanged.connect(self._on_select_all_changed)
        filter_bar.addWidget(self._select_all)

        self._protect_selected_btn = QPushButton(tr("findings.protect_selected"))
        self._protect_selected_btn.clicked.connect(self._protect_selected)
        self._protect_selected_btn.setEnabled(False)
        filter_bar.addWidget(self._protect_selected_btn)

        right_layout.addLayout(filter_bar)

        # Findings table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            "", tr("findings.entity_type"), tr("findings.original"),
            tr("findings.replacement"), tr("findings.context"), tr("findings.action"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self._table.setColumnWidth(0, 40)
        self._table.setColumnWidth(1, 120)
        self._table.setColumnWidth(3, 150)
        self._table.setColumnWidth(5, 100)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.itemChanged.connect(self._on_item_changed)

        right_layout.addWidget(self._table, stretch=1)

        splitter.addWidget(right_panel)
        splitter.setSizes([250, 750])

        layout.addWidget(splitter, stretch=1)

        # Bottom actions
        actions = QHBoxLayout()

        back_btn = QPushButton(tr("buttons.back"))
        back_btn.setProperty("secondary", True)
        back_btn.clicked.connect(self.back_requested.emit)
        actions.addWidget(back_btn)

        actions.addStretch()

        self._apply_btn = QPushButton(tr("findings.apply_treatments"))
        self._apply_btn.clicked.connect(self._apply_all_treatments)
        actions.addWidget(self._apply_btn)

        layout.addLayout(actions)

    def set_findings(self, findings: list[dict]) -> None:
        """
        Set findings to review.

        Args:
            findings: List of finding dicts with id, entity_type, original,
                     replacement, context, file_name
        """
        self._findings = findings
        self._selected_findings = set(f["id"] for f in findings)  # Select all by default
        self._update_summary()
        self._update_filter_options()
        self._refresh_table()

    def _update_summary(self) -> None:
        """Update the summary card."""
        counts: dict[str, int] = {}
        for f in self._findings:
            entity_type = f.get("entity_type", "UNKNOWN")
            counts[entity_type] = counts.get(entity_type, 0) + 1
        self._summary.set_counts(counts)

    def _update_filter_options(self) -> None:
        """Update filter dropdown options."""
        self._filter_combo.blockSignals(True)
        self._filter_combo.clear()
        self._filter_combo.addItem(f"All ({len(self._findings)})", "")

        types = set(f.get("entity_type", "UNKNOWN") for f in self._findings)
        for entity_type in sorted(types):
            count = sum(1 for f in self._findings if f.get("entity_type") == entity_type)
            display = tr(f"entity_types.{entity_type}", default=entity_type)
            self._filter_combo.addItem(f"{display} ({count})", entity_type)

        self._filter_combo.blockSignals(False)

    def _apply_filter(self, entity_type: str) -> None:
        """Apply filter by entity type."""
        self._current_filter = entity_type

        # Update combo to match
        for i in range(self._filter_combo.count()):
            if self._filter_combo.itemData(i) == entity_type:
                self._filter_combo.setCurrentIndex(i)
                break

        self._refresh_table()

    def _on_filter_changed(self, index: int) -> None:
        """Handle filter combo change."""
        entity_type = self._filter_combo.currentData() or ""
        self._current_filter = entity_type
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Refresh the findings table."""
        self._table.blockSignals(True)

        # Filter findings
        if self._current_filter:
            filtered = [f for f in self._findings if f.get("entity_type") == self._current_filter]
        else:
            filtered = self._findings

        self._table.setRowCount(len(filtered))

        for row, finding in enumerate(filtered):
            finding_id = finding["id"]

            # Checkbox
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checkbox.setCheckState(
                Qt.CheckState.Checked if finding_id in self._selected_findings
                else Qt.CheckState.Unchecked
            )
            checkbox.setData(Qt.ItemDataRole.UserRole, finding_id)
            self._table.setItem(row, 0, checkbox)

            # Entity type
            entity_type = finding.get("entity_type", "UNKNOWN")
            type_badge = StatusBadge(
                tr(f"entity_types.{entity_type}", default=entity_type),
                get_entity_color(entity_type),
            )
            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(4, 4, 4, 4)
            container_layout.addWidget(type_badge)
            self._table.setCellWidget(row, 1, container)

            # Original
            original = QTableWidgetItem(finding.get("original", ""))
            original.setFlags(original.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 2, original)

            # Replacement
            replacement = QTableWidgetItem(finding.get("replacement", ""))
            replacement.setFlags(replacement.flags() & ~Qt.ItemFlag.ItemIsEditable)
            replacement.setForeground(QColor(ColorPalette.PRIMARY.value))
            self._table.setItem(row, 3, replacement)

            # Context
            context = finding.get("context", "")
            context_item = QTableWidgetItem(context[:100] + "..." if len(context) > 100 else context)
            context_item.setFlags(context_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            context_item.setForeground(QColor(ColorPalette.GRAY_500.value))
            self._table.setItem(row, 4, context_item)

            # Action dropdown
            action_combo = QComboBox()
            action_combo.addItem(tr("findings.protect"), "protect")
            action_combo.addItem(tr("findings.ignore"), "ignore")
            if finding_id not in self._selected_findings:
                action_combo.setCurrentIndex(1)
            action_combo.currentIndexChanged.connect(
                lambda idx, fid=finding_id: self._on_action_changed(fid, idx)
            )
            self._table.setCellWidget(row, 5, action_combo)

        self._table.blockSignals(False)
        self._update_selection_state()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Handle item checkbox change."""
        if item.column() == 0:
            finding_id = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                self._selected_findings.add(finding_id)
            else:
                self._selected_findings.discard(finding_id)
            self._update_selection_state()

    def _on_action_changed(self, finding_id: str, index: int) -> None:
        """Handle action dropdown change."""
        if index == 0:  # Protect
            self._selected_findings.add(finding_id)
        else:  # Ignore
            self._selected_findings.discard(finding_id)
        self._update_selection_state()

    def _on_select_all_changed(self, state: int) -> None:
        """Handle select all checkbox."""
        if state == Qt.CheckState.Checked.value:
            self._selected_findings = set(f["id"] for f in self._findings)
        else:
            self._selected_findings.clear()
        self._refresh_table()

    def _update_selection_state(self) -> None:
        """Update UI based on selection."""
        count = len(self._selected_findings)
        self._protect_selected_btn.setEnabled(count > 0)
        self._protect_selected_btn.setText(
            f"{tr('findings.protect_selected')} ({count})"
        )

        # Update select all checkbox
        self._select_all.blockSignals(True)
        if count == len(self._findings):
            self._select_all.setCheckState(Qt.CheckState.Checked)
        elif count == 0:
            self._select_all.setCheckState(Qt.CheckState.Unchecked)
        else:
            self._select_all.setCheckState(Qt.CheckState.PartiallyChecked)
        self._select_all.blockSignals(False)

    def _protect_selected(self) -> None:
        """Emit protect signal for selected findings."""
        self.apply_treatments.emit(list(self._selected_findings))

    def _apply_all_treatments(self) -> None:
        """Apply treatments to all selected findings."""
        self.apply_treatments.emit(list(self._selected_findings))


__all__ = ["FindingsReviewScreen"]
