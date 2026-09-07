"""
Document Preview Dialog.

Shows detected PII entities in Word/PowerPoint documents before protection.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QWidget,
    QCheckBox,
    QGroupBox,
)

from sandiraksa.ui.theme import ColorPalette, FONT_SIZE, SPACING


class DocumentPreviewDialog(QDialog):
    """
    Dialog to preview detected PII in a document file (DOCX/PPTX).
    
    Shows:
    - Summary of detected entities
    - Table of detected entities with checkboxes
    - Option to select which entities to protect
    """
    
    protection_requested = Signal(list)  # List of selected entities
    
    def __init__(
        self,
        filename: str,
        file_type: str,  # "docx" or "pptx"
        detected_entities: list,  # list[DetectedEntity]
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._filename = filename
        self._file_type = file_type
        self._entities = detected_entities
        self._entity_checkboxes: list[QCheckBox] = []
        
        self._setup_ui()
        self._populate_data()
    
    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        type_name = "Word" if self._file_type == "docx" else "PowerPoint"
        self.setWindowTitle(f"Preview {type_name}: {self._filename}")
        self.setMinimumSize(700, 500)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING.MD)
        
        # Header with file info
        header_layout = QHBoxLayout()
        
        icon = "📄" if self._file_type == "docx" else "📊"
        file_label = QLabel(f"{icon} <b>{self._filename}</b>")
        file_label.setStyleSheet(f"font-size: {FONT_SIZE.LG}px;")
        header_layout.addWidget(file_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Info label
        if self._entities:
            info_text = (
                f"Ditemukan <b>{len(self._entities)}</b> data sensitif dalam dokumen. "
                "Pilih data yang ingin dilindungi."
            )
        else:
            info_text = "Tidak ada data sensitif yang terdeteksi dalam dokumen ini."
        
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"color: {ColorPalette.GRAY_600.value};")
        layout.addWidget(info_label)
        
        # Entity table
        if self._entities:
            entities_group = QGroupBox("Data Sensitif Terdeteksi")
            entities_layout = QVBoxLayout(entities_group)
            
            # Select all checkbox
            select_row = QHBoxLayout()
            self._select_all = QCheckBox("Pilih Semua")
            self._select_all.setChecked(True)
            self._select_all.stateChanged.connect(self._on_select_all_changed)
            select_row.addWidget(self._select_all)
            select_row.addStretch()
            
            # Summary by type
            type_counts = {}
            for e in self._entities:
                t = e.entity_type
                type_counts[t] = type_counts.get(t, 0) + 1
            
            summary_parts = [f"{self._format_entity_type(t)}: {c}" for t, c in type_counts.items()]
            summary_label = QLabel(" | ".join(summary_parts))
            summary_label.setStyleSheet(f"color: {ColorPalette.GRAY_500.value}; font-size: {FONT_SIZE.SM}px;")
            select_row.addWidget(summary_label)
            
            entities_layout.addLayout(select_row)
            
            # Table
            self._entity_table = QTableWidget()
            self._entity_table.setColumnCount(4)
            self._entity_table.setHorizontalHeaderLabels([
                "Lindungi", "Tipe", "Nilai", "Lokasi"
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
            self._entity_table.setAlternatingRowColors(True)
            entities_layout.addWidget(self._entity_table)
            
            layout.addWidget(entities_group, 1)  # Give it stretch
        
        # Buttons
        button_row = QHBoxLayout()
        button_row.addStretch()
        
        cancel_btn = QPushButton("Batal")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        
        if self._entities:
            self._protect_btn = QPushButton("Lindungi Data Terpilih")
            self._protect_btn.clicked.connect(self._on_protect_clicked)
            self._protect_btn.setDefault(True)
            self._protect_btn.setStyleSheet(
                f"background-color: {ColorPalette.PRIMARY.value}; "
                f"color: white; padding: 8px 16px;"
            )
            button_row.addWidget(self._protect_btn)
        else:
            # No entities - just close button
            close_btn = QPushButton("Tutup")
            close_btn.clicked.connect(self.accept)
            close_btn.setDefault(True)
            button_row.addWidget(close_btn)
        
        layout.addLayout(button_row)
    
    def _populate_data(self) -> None:
        """Populate the dialog with data."""
        if not self._entities:
            return
        
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
            if len(value) > 6:
                masked = value[:3] + '*' * (len(value) - 6) + value[-3:]
            elif len(value) > 2:
                masked = value[:1] + '*' * (len(value) - 2) + value[-1:]
            else:
                masked = '*' * len(value)
            value_item = QTableWidgetItem(masked)
            value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            value_item.setToolTip(entity.context if hasattr(entity, 'context') else value)
            self._entity_table.setItem(i, 2, value_item)
            
            # Location
            location = getattr(entity, 'location', 'unknown')
            loc_item = QTableWidgetItem(location)
            loc_item.setFlags(loc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._entity_table.setItem(i, 3, loc_item)
        
        self._update_protect_button()
    
    def _format_entity_type(self, entity_type: str) -> str:
        """Format entity type for display."""
        type_names = {
            "EMAIL": "Email",
            "PHONE_NUMBER": "Telepon",
            "ID_NIK": "NIK",
            "ID_NPWP": "NPWP",
            "ID_KK": "No. KK",
            "CREDIT_CARD": "Kartu Kredit",
            "IP_ADDRESS": "IP Address",
            "DATE": "Tanggal",
            "URL": "URL",
            "PERSON": "Nama",
            "ADDRESS": "Alamat",
            "MEDICAL_RECORD": "No. RM",
        }
        return type_names.get(entity_type, entity_type)
    
    def _on_select_all_changed(self, state: int) -> None:
        """Handle select all checkbox change."""
        checked = state == Qt.CheckState.Checked.value
        for cb in self._entity_checkboxes:
            cb.setChecked(checked)
    
    def _update_protect_button(self) -> None:
        """Update protect button state based on selections."""
        if not hasattr(self, '_protect_btn'):
            return
        
        selected_count = sum(1 for cb in self._entity_checkboxes if cb.isChecked())
        self._protect_btn.setEnabled(selected_count > 0)
        self._protect_btn.setText(f"Lindungi {selected_count} Data")
    
    def _on_protect_clicked(self) -> None:
        """Handle protect button click."""
        self.accept()
    
    def get_selected_entities(self) -> list:
        """Get list of selected entities."""
        selected = []
        for i, cb in enumerate(self._entity_checkboxes):
            if cb.isChecked():
                selected.append(self._entities[i])
        return selected
