"""
TXT Preview Dialog.

Shows detected PII entities in a text file before protection.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QWidget,
    QCheckBox,
    QGroupBox,
)

from sandiraksa.ui.theme import SPACING


class TxtPreviewDialog(QDialog):
    """
    Dialog to preview detected PII in a TXT file.
    
    Shows:
    - Original text with highlighted entities
    - Table of detected entities with checkboxes
    - Option to select which entities to protect
    """
    
    protection_requested = Signal(list)  # List of entity indices to protect
    
    def __init__(
        self,
        filename: str,
        text_content: str,
        detected_entities: list,  # list[DetectedEntity]
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._filename = filename
        self._text_content = text_content
        self._entities = detected_entities
        self._entity_checkboxes: list[QCheckBox] = []
        
        self._setup_ui()
        self._populate_data()
    
    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        self.setWindowTitle(f"Preview: {self._filename}")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING.MD)
        
        # Info label
        info_label = QLabel(
            f"Ditemukan <b>{len(self._entities)}</b> data sensitif dalam file. "
            "Pilih data yang ingin dilindungi."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Splitter for text preview and entity table
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Text preview with highlights
        preview_group = QGroupBox("Preview Teks")
        preview_layout = QVBoxLayout(preview_group)
        
        self._text_preview = QTextEdit()
        self._text_preview.setReadOnly(True)
        self._text_preview.setFont(QFont("Consolas", 10))
        preview_layout.addWidget(self._text_preview)
        
        splitter.addWidget(preview_group)
        
        # Entity table
        entities_group = QGroupBox("Data Sensitif Terdeteksi")
        entities_layout = QVBoxLayout(entities_group)
        
        # Select all checkbox
        select_row = QHBoxLayout()
        self._select_all = QCheckBox("Pilih Semua")
        self._select_all.setChecked(True)
        self._select_all.stateChanged.connect(self._on_select_all_changed)
        select_row.addWidget(self._select_all)
        select_row.addStretch()
        entities_layout.addLayout(select_row)
        
        # Table
        self._entity_table = QTableWidget()
        self._entity_table.setColumnCount(4)
        self._entity_table.setHorizontalHeaderLabels([
            "Lindungi", "Tipe", "Nilai", "Posisi"
        ])
        self._entity_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._entity_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._entity_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._entity_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self._entity_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._entity_table.itemSelectionChanged.connect(self._on_table_selection_changed)
        entities_layout.addWidget(self._entity_table)
        
        splitter.addWidget(entities_group)
        
        # Set splitter sizes
        splitter.setSizes([400, 300])
        
        layout.addWidget(splitter)
        
        # Buttons
        button_row = QHBoxLayout()
        button_row.addStretch()
        
        cancel_btn = QPushButton("Batal")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        
        self._protect_btn = QPushButton("Lindungi Data Terpilih")
        self._protect_btn.clicked.connect(self._on_protect_clicked)
        self._protect_btn.setDefault(True)
        button_row.addWidget(self._protect_btn)
        
        layout.addLayout(button_row)
    
    def _populate_data(self) -> None:
        """Populate the dialog with data."""
        # Show text with highlights
        self._highlight_entities()
        
        # Populate table
        self._entity_table.setRowCount(len(self._entities))
        self._entity_checkboxes.clear()
        
        for i, entity in enumerate(self._entities):
            # Checkbox
            cb = QCheckBox()
            cb.setChecked(True)
            cb.stateChanged.connect(self._update_protect_button)
            self._entity_checkboxes.append(cb)
            
            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self._entity_table.setCellWidget(i, 0, cb_widget)
            
            # Entity type
            type_item = QTableWidgetItem(self._format_entity_type(entity.entity_type))
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._entity_table.setItem(i, 1, type_item)
            
            # Value (masked for privacy in preview)
            value = entity.value
            if len(value) > 4:
                masked = value[:2] + '*' * (len(value) - 4) + value[-2:]
            else:
                masked = '*' * len(value)
            value_item = QTableWidgetItem(masked)
            value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            value_item.setToolTip(f"Nilai asli: {value}")
            self._entity_table.setItem(i, 2, value_item)
            
            # Position
            pos_item = QTableWidgetItem(f"Karakter {entity.start}-{entity.end}")
            pos_item.setFlags(pos_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._entity_table.setItem(i, 3, pos_item)
        
        self._update_protect_button()
    
    def _highlight_entities(self) -> None:
        """Highlight detected entities in text preview."""
        # Start with plain text
        self._text_preview.setPlainText(self._text_content)
        
        # Highlight each entity
        cursor = self._text_preview.textCursor()
        
        # Define highlight format
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor("#FFEB3B"))  # Yellow
        highlight_format.setForeground(QColor("#000000"))
        
        # Highlight from end to start to preserve positions
        for entity in reversed(self._entities):
            cursor.setPosition(entity.start)
            cursor.setPosition(entity.end, cursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(highlight_format)
        
        # Reset cursor position
        cursor.setPosition(0)
        self._text_preview.setTextCursor(cursor)
    
    def _format_entity_type(self, entity_type: str) -> str:
        """Format entity type for display."""
        type_names = {
            "EMAIL": "Email",
            "PHONE_NUMBER": "Nomor Telepon",
            "ID_NIK": "NIK",
            "ID_NPWP": "NPWP",
            "ID_KK": "No. KK",
            "CREDIT_CARD": "Kartu Kredit",
            "IP_ADDRESS": "Alamat IP",
            "DATE": "Tanggal",
            "URL": "URL",
            "PERSON": "Nama",
            "ADDRESS": "Alamat",
        }
        return type_names.get(entity_type, entity_type)
    
    def _on_select_all_changed(self, state: int) -> None:
        """Handle select all checkbox change."""
        checked = state == Qt.CheckState.Checked.value
        for cb in self._entity_checkboxes:
            cb.setChecked(checked)
    
    def _on_table_selection_changed(self) -> None:
        """Handle table row selection - highlight in preview."""
        selected_rows = set(item.row() for item in self._entity_table.selectedItems())
        
        if not selected_rows:
            return
        
        # Scroll to first selected entity in preview
        row = min(selected_rows)
        if row < len(self._entities):
            entity = self._entities[row]
            cursor = self._text_preview.textCursor()
            cursor.setPosition(entity.start)
            self._text_preview.setTextCursor(cursor)
            self._text_preview.ensureCursorVisible()
    
    def _update_protect_button(self) -> None:
        """Update protect button state based on selections."""
        selected_count = sum(1 for cb in self._entity_checkboxes if cb.isChecked())
        self._protect_btn.setEnabled(selected_count > 0)
        self._protect_btn.setText(f"Lindungi {selected_count} Data")
    
    def _on_protect_clicked(self) -> None:
        """Handle protect button click."""
        # Get selected entity indices
        selected_indices = [
            i for i, cb in enumerate(self._entity_checkboxes)
            if cb.isChecked()
        ]
        
        if selected_indices:
            self.protection_requested.emit(selected_indices)
            self.accept()
    
    def get_selected_entities(self) -> list:
        """Get the list of selected entities for protection."""
        return [
            self._entities[i]
            for i, cb in enumerate(self._entity_checkboxes)
            if cb.isChecked()
        ]


__all__ = ["TxtPreviewDialog"]
