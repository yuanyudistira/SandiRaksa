"""
Column Selection Dialog for Excel and CSV files.

Allows users to select which columns contain sensitive data.
Provides auto-suggestions based on column header names.
"""

from __future__ import annotations

import csv
import codecs  # Pre-import to avoid GC crash
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

# Pre-import openpyxl at module level to avoid GC crash during Qt event loop
try:
    import openpyxl
except ImportError:
    openpyxl = None

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sandiraksa.app.i18n import tr
from sandiraksa.ui.theme import ColorPalette, FONT_SIZE, SPACING

if TYPE_CHECKING:
    pass


# Keywords that suggest sensitive data (case-insensitive)
SENSITIVE_KEYWORDS = {
    # Indonesian
    "nama": "PERSON",
    "name": "PERSON",
    "pasien": "PERSON",
    "patient": "PERSON",
    "karyawan": "PERSON",
    "employee": "PERSON",
    "pegawai": "PERSON",
    
    "nik": "ID_NIK",
    "ktp": "ID_NIK",
    "identitas": "ID_NIK",
    
    "npwp": "ID_NPWP",
    "pajak": "ID_NPWP",
    "tax": "ID_NPWP",
    
    "kk": "ID_KK",
    "kartu keluarga": "ID_KK",
    
    "hp": "ID_PHONE",
    "handphone": "ID_PHONE",
    "telepon": "PHONE_NUMBER",
    "telp": "PHONE_NUMBER",
    "phone": "PHONE_NUMBER",
    "mobile": "PHONE_NUMBER",
    "kontak": "PHONE_NUMBER",
    "contact": "PHONE_NUMBER",
    
    "email": "EMAIL_ADDRESS",
    "e-mail": "EMAIL_ADDRESS",
    "surel": "EMAIL_ADDRESS",
    
    "alamat": "ADDRESS",
    "address": "ADDRESS",
    "jalan": "ADDRESS",
    "jl.": "ADDRESS",
    
    "rekening": "BANK_ACCOUNT",
    "account": "BANK_ACCOUNT",
    "bank": "BANK_ACCOUNT",
    
    "kartu kredit": "CREDIT_CARD",
    "credit card": "CREDIT_CARD",
    "cc": "CREDIT_CARD",
    
    "tanggal lahir": "DATE_OF_BIRTH",
    "tgl lahir": "DATE_OF_BIRTH",
    "birth": "DATE_OF_BIRTH",
    "dob": "DATE_OF_BIRTH",
    
    "medical": "MEDICAL_RECORD",
    "medis": "MEDICAL_RECORD",
    "emr": "MEDICAL_RECORD",
    "rm": "MEDICAL_RECORD",
    "rekam medis": "MEDICAL_RECORD",
    "diagnosis": "MEDICAL_INFO",
    "diagnosa": "MEDICAL_INFO",
    "obat": "MEDICAL_INFO",
    "resep": "MEDICAL_INFO",
}


@dataclass
class ColumnInfo:
    """Information about a column."""
    
    sheet_name: str
    column_index: int
    column_letter: str
    header: str
    sample_values: list[str] = field(default_factory=list)
    suggested_type: str | None = None
    is_selected: bool = False


@dataclass 
class WorksheetInfo:
    """Information about a worksheet."""
    
    name: str
    row_count: int
    columns: list[ColumnInfo] = field(default_factory=list)


def analyze_column_header(header: str) -> str | None:
    """
    Analyze column header to suggest entity type.
    
    Returns entity type string or None if not detected.
    """
    if not header:
        return None
    
    header_lower = header.lower().strip()
    
    # Check exact matches first
    for keyword, entity_type in SENSITIVE_KEYWORDS.items():
        if keyword in header_lower:
            return entity_type
    
    return None


def get_column_letter(col_index: int) -> str:
    """Convert 1-based column index to Excel letter (A, B, ..., Z, AA, AB, ...)."""
    result = ""
    while col_index > 0:
        col_index, remainder = divmod(col_index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def analyze_excel_file(file_path: Path) -> list[WorksheetInfo]:
    """
    Analyze Excel file and return worksheet/column information.
    
    Args:
        file_path: Path to Excel file.
        
    Returns:
        List of WorksheetInfo with column details.
    """
    import gc
    gc_was_enabled = gc.isenabled()
    gc.disable()  # Disable GC during file I/O to prevent heap corruption with PySide6
    
    try:
        if openpyxl is None:
            raise ImportError("openpyxl not installed")
        
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        worksheets = []
        
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            
            # Get headers from first row
            headers = []
            first_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
            if first_row:
                headers = [str(h) if h else "" for h in first_row]
            
            # Get sample values from rows 2-6
            sample_rows = []
            for i, row in enumerate(sheet.iter_rows(min_row=2, max_row=6, values_only=True)):
                sample_rows.append(row)
            
            # Count total rows
            row_count = sum(1 for _ in sheet.iter_rows(values_only=True))
            
            # Build column info
            columns = []
            for col_idx, header in enumerate(headers, start=1):
                # Get sample values for this column
                samples = []
                for row in sample_rows:
                    if col_idx - 1 < len(row) and row[col_idx - 1] is not None:
                        samples.append(str(row[col_idx - 1]))
                
                # Analyze header for suggestion
                suggested_type = analyze_column_header(header)
                
                col_info = ColumnInfo(
                    sheet_name=sheet_name,
                    column_index=col_idx,
                    column_letter=get_column_letter(col_idx),
                    header=header,
                    sample_values=samples[:3],
                    suggested_type=suggested_type,
                    is_selected=suggested_type is not None,  # Auto-select if suggested
                )
                columns.append(col_info)
            
            worksheets.append(WorksheetInfo(
                name=sheet_name,
                row_count=row_count,
                columns=columns,
            ))
        
        wb.close()
        return worksheets
        
    except Exception as e:
        print(f"Error analyzing Excel file: {e}")
        return []
    finally:
        if gc_was_enabled:
            gc.enable()


def analyze_csv_file(file_path: Path) -> list[WorksheetInfo]:
    """
    Analyze CSV file and return column information.
    
    Args:
        file_path: Path to CSV file.
        
    Returns:
        List with single WorksheetInfo containing column details.
    """
    import gc
    gc_was_enabled = gc.isenabled()
    gc.disable()  # Disable GC during file I/O to prevent heap corruption
    
    try:
        # Detect delimiter and encoding
        delimiter = _detect_csv_delimiter(file_path)
        encoding = _detect_csv_encoding(file_path)
        
        with open(file_path, 'r', encoding=encoding, newline='') as f:
            reader = csv.reader(f, delimiter=delimiter)
            rows = list(reader)
        
        if not rows:
            return []
        
        # Get headers from first row
        headers = rows[0]
        data_rows = rows[1:6]  # Sample rows for preview
        row_count = len(rows)
        
        # Build column info
        columns = []
        for col_idx, header in enumerate(headers):
            # Get sample values for this column
            samples = []
            for row in data_rows:
                if col_idx < len(row) and row[col_idx]:
                    samples.append(str(row[col_idx]))
            
            # Analyze header for suggestion
            suggested_type = analyze_column_header(header)
            
            col_info = ColumnInfo(
                sheet_name="CSV",  # CSV has no sheet name
                column_index=col_idx,  # 0-based for CSV
                column_letter=get_column_letter(col_idx + 1),  # Convert to letter
                header=header,
                sample_values=samples[:3],
                suggested_type=suggested_type,
                is_selected=suggested_type is not None,
            )
            columns.append(col_info)
        
        return [WorksheetInfo(
            name="CSV",
            row_count=row_count,
            columns=columns,
        )]
        
    except Exception as e:
        print(f"Error analyzing CSV file: {e}")
        return []
    finally:
        if gc_was_enabled:
            gc.enable()


def _detect_csv_delimiter(path: Path) -> str:
    """Detect CSV delimiter."""
    import gc
    gc_was_enabled = gc.isenabled()
    gc.disable()
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            sample = f.read(4096)
        
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
            return dialect.delimiter
        except csv.Error:
            pass
        
        delimiters = [',', ';', '\t', '|']
        counts = {d: sample.count(d) for d in delimiters}
        return max(counts, key=counts.get)
        
    except Exception:
        return ','
    finally:
        if gc_was_enabled:
            gc.enable()


def _detect_csv_encoding(path: Path) -> str:
    """Detect file encoding."""
    import gc
    gc_was_enabled = gc.isenabled()
    gc.disable()  # Disable GC during file I/O to prevent heap corruption
    
    try:
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    f.read(1024)
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        return 'utf-8'
    finally:
        if gc_was_enabled:
            gc.enable()


class ColumnCheckbox(QWidget):
    """Checkbox widget for a single column with details."""
    
    toggled = Signal(str, int, bool)  # sheet_name, col_index, is_checked
    
    def __init__(
        self,
        column: ColumnInfo,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._column = column
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # Checkbox
        self._checkbox = QCheckBox()
        self._checkbox.setChecked(self._column.is_selected)
        self._checkbox.toggled.connect(self._on_toggled)
        layout.addWidget(self._checkbox)
        
        # Column letter
        letter_label = QLabel(f"[{self._column.column_letter}]")
        letter_label.setStyleSheet(f"color: {ColorPalette.GRAY_400.value}; min-width: 30px;")
        layout.addWidget(letter_label)
        
        # Header name
        header_label = QLabel(self._column.header or "(No header)")
        header_label.setStyleSheet(f"font-weight: bold; min-width: 150px;")
        layout.addWidget(header_label)
        
        # Suggested type badge
        if self._column.suggested_type:
            type_label = QLabel(self._column.suggested_type)
            type_label.setStyleSheet(
                f"background-color: {ColorPalette.PRIMARY.value}; "
                f"color: white; "
                f"padding: 2px 8px; "
                f"border-radius: 4px; "
                f"font-size: {FONT_SIZE.SM}px;"
            )
            layout.addWidget(type_label)
        
        layout.addStretch()
        
        # Sample values
        if self._column.sample_values:
            samples = ", ".join(self._column.sample_values[:2])
            if len(samples) > 40:
                samples = samples[:40] + "..."
            sample_label = QLabel(f"e.g. {samples}")
            sample_label.setStyleSheet(f"color: {ColorPalette.GRAY_500.value}; font-style: italic;")
            layout.addWidget(sample_label)
    
    def _on_toggled(self, checked: bool) -> None:
        self._column.is_selected = checked
        self.toggled.emit(self._column.sheet_name, self._column.column_index, checked)
    
    def is_checked(self) -> bool:
        return self._checkbox.isChecked()
    
    def set_checked(self, checked: bool) -> None:
        self._checkbox.setChecked(checked)


class ColumnSelectionDialog(QDialog):
    """
    Dialog for selecting columns to protect in Excel or CSV files.
    
    Shows worksheets as tabs (for Excel), columns with checkboxes,
    and auto-suggests sensitive columns based on headers.
    """
    
    columns_selected = Signal(list)  # List of ColumnInfo
    
    def __init__(
        self,
        file_path: Path,
        parent: QWidget | None = None,
        *,
        worksheets: list[WorksheetInfo] | None = None,
    ) -> None:
        super().__init__(parent)
        self._file_path = file_path
        self._worksheets: list[WorksheetInfo] = []
        self._column_widgets: dict[tuple[str, int], ColumnCheckbox] = {}
        self._is_csv = file_path.suffix.lower() == '.csv'
        
        # Use pre-analyzed worksheets if provided, otherwise analyze now
        if worksheets is not None:
            self._worksheets = worksheets
        else:
            self._analyze_file()
        
        self._setup_ui()
    
    def _analyze_file(self) -> None:
        """Analyze the file (Excel or CSV)."""
        if self._is_csv:
            self._worksheets = analyze_csv_file(self._file_path)
        else:
            self._worksheets = analyze_excel_file(self._file_path)
    
    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        self.setWindowTitle(tr("column_selection.title", default="Select Columns to Protect"))
        self.setMinimumSize(700, 500)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING.MD)
        
        # Header
        header = QLabel(tr("column_selection.description", 
            default="Select columns that contain sensitive data. Suggested columns are pre-selected."))
        header.setWordWrap(True)
        header.setStyleSheet(f"color: {ColorPalette.GRAY_600.value};")
        layout.addWidget(header)
        
        # File info
        file_label = QLabel(f"📄 {self._file_path.name}")
        file_label.setStyleSheet(f"font-weight: bold; font-size: {FONT_SIZE.LG}px;")
        layout.addWidget(file_label)
        
        # Tabs for worksheets
        self._tabs = QTabWidget()
        
        for ws in self._worksheets:
            tab = self._create_worksheet_tab(ws)
            self._tabs.addTab(tab, f"{ws.name} ({ws.row_count} rows)")
        
        layout.addWidget(self._tabs, stretch=1)
        
        # Summary
        self._summary_label = QLabel()
        self._update_summary()
        layout.addWidget(self._summary_label)
        
        # Buttons
        buttons = QHBoxLayout()
        
        select_all_btn = QPushButton(tr("buttons.select_all", default="Select All"))
        select_all_btn.clicked.connect(self._select_all)
        buttons.addWidget(select_all_btn)
        
        select_suggested_btn = QPushButton(tr("column_selection.select_suggested", default="Select Suggested Only"))
        select_suggested_btn.clicked.connect(self._select_suggested)
        buttons.addWidget(select_suggested_btn)
        
        deselect_all_btn = QPushButton(tr("buttons.deselect_all", default="Deselect All"))
        deselect_all_btn.clicked.connect(self._deselect_all)
        buttons.addWidget(deselect_all_btn)
        
        buttons.addStretch()
        
        cancel_btn = QPushButton(tr("buttons.cancel", default="Cancel"))
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        confirm_btn = QPushButton(tr("column_selection.confirm", default="Scan Selected Columns"))
        confirm_btn.setStyleSheet(
            f"background-color: {ColorPalette.PRIMARY.value}; "
            f"color: white; "
            f"font-weight: bold; "
            f"padding: 8px 16px;"
        )
        confirm_btn.clicked.connect(self._on_confirm)
        buttons.addWidget(confirm_btn)
        
        layout.addLayout(buttons)
    
    def _create_worksheet_tab(self, ws: WorksheetInfo) -> QWidget:
        """Create a tab for a worksheet."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area for columns
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(2)
        
        # Add column checkboxes
        for col in ws.columns:
            checkbox = ColumnCheckbox(col)
            checkbox.toggled.connect(self._on_column_toggled)
            self._column_widgets[(ws.name, col.column_index)] = checkbox
            content_layout.addWidget(checkbox)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        
        layout.addWidget(scroll)
        return widget
    
    def _on_column_toggled(self, sheet_name: str, col_index: int, is_checked: bool) -> None:
        """Handle column checkbox toggle."""
        self._update_summary()
    
    def _update_summary(self) -> None:
        """Update the summary label."""
        selected = sum(1 for w in self._column_widgets.values() if w.is_checked())
        total = len(self._column_widgets)
        
        # Count suggested
        suggested = sum(
            1 for ws in self._worksheets 
            for col in ws.columns 
            if col.suggested_type
        )
        
        self._summary_label.setText(
            f"Selected: {selected} of {total} columns | "
            f"Auto-suggested: {suggested} columns"
        )
    
    def _select_all(self) -> None:
        """Select all columns."""
        for widget in self._column_widgets.values():
            widget.set_checked(True)
        self._update_summary()
    
    def _deselect_all(self) -> None:
        """Deselect all columns."""
        for widget in self._column_widgets.values():
            widget.set_checked(False)
        self._update_summary()
    
    def _select_suggested(self) -> None:
        """Select only suggested columns."""
        for ws in self._worksheets:
            for col in ws.columns:
                key = (ws.name, col.column_index)
                if key in self._column_widgets:
                    self._column_widgets[key].set_checked(col.suggested_type is not None)
        self._update_summary()
    
    def _on_confirm(self) -> None:
        """Handle confirm button."""
        selected_columns = []
        for ws in self._worksheets:
            for col in ws.columns:
                key = (ws.name, col.column_index)
                if key in self._column_widgets and self._column_widgets[key].is_checked():
                    col.is_selected = True
                    selected_columns.append(col)
        
        self.columns_selected.emit(selected_columns)
        self.accept()
    
    def get_selected_columns(self) -> list[ColumnInfo]:
        """Get list of selected columns."""
        selected = []
        for ws in self._worksheets:
            for col in ws.columns:
                key = (ws.name, col.column_index)
                if key in self._column_widgets and self._column_widgets[key].is_checked():
                    selected.append(col)
        return selected


__all__ = [
    "ColumnInfo",
    "WorksheetInfo", 
    "ColumnSelectionDialog",
    "analyze_excel_file",
    "analyze_csv_file",
    "analyze_column_header",
]
