"""
Column Selection Dialog for Excel and CSV files.

Allows users to select which columns contain sensitive data.
Provides auto-suggestions based on column header names.
"""

from __future__ import annotations

import csv
import codecs  # Pre-import to avoid GC crash
import json
from dataclasses import dataclass, field
from enum import Enum
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
    QComboBox,
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

    "bpjs": "ID_BPJS",
    "jkn": "ID_BPJS",
    
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


class ProtectionMode(str, Enum):
    """How a selected column's cells are protected.

    - FULL_CELL: the entire cell value is replaced with one token (default for
      single-value columns like "Nama Pasien", "NIK", "Alamat").
    - PII_ONLY: run detection inside each cell and tokenize ONLY the detected
      PII substrings, leaving surrounding text/structure intact (default for
      free-text / narrative / JSON columns).
    """

    FULL_CELL = "full_cell"
    PII_ONLY = "pii_only"


# Sentinel suggested_type for free-text / structured-text columns.
NARRATIVE_TYPE = "TEKS_NARASI"

# Narrative heuristic thresholds (averaged over sampled non-empty cells).
_NARRATIVE_MIN_AVG_LEN = 50
_NARRATIVE_MIN_AVG_TOKENS = 8


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
    # How this column should be protected. Auto-set from the column's content
    # (narrative/JSON -> PII_ONLY, otherwise FULL_CELL) and user-overridable.
    protection_mode: str = ProtectionMode.FULL_CELL.value


@dataclass 
class WorksheetInfo:
    """Information about a worksheet."""
    
    name: str
    row_count: int
    columns: list[ColumnInfo] = field(default_factory=list)


# Header keywords that indicate a NON-sensitive column even if they contain a
# sensitive-looking substring (e.g. "Status Pasien" contains "pasien" but is
# not a name; "Patient ID" is an identifier, not a person name).
NON_SENSITIVE_HEADER_HINTS = (
    "status", "jenis", "tipe", "type", "kategori", "category",
    "golongan", "kode", "code", "klasifikasi", "persetujuan", "consent",
    "kota", "kabupaten", "provinsi", "fasilitas", "penjamin",
)

# When a header contains "id"/"nomor" together with a person keyword it is an
# identifier column, not a person-name column.
_ID_TOKENS = ("id", "no.", "no ", "nomor", "number")


def analyze_column_header(header: str) -> str | None:
    """
    Analyze column header to suggest entity type based on header name.
    
    Returns entity type string or None if not detected.
    """
    if not header:
        return None
    
    header_lower = header.lower().strip()

    # Skip clearly non-sensitive descriptor columns
    for hint in NON_SENSITIVE_HEADER_HINTS:
        if header_lower.startswith(hint) or f" {hint}" == header_lower[-len(hint) - 1:]:
            # e.g. "Status Pasien", "Jenis Kelamin", "Kategori BMI"
            if header_lower.split()[0] in NON_SENSITIVE_HEADER_HINTS:
                return None

    # Check keyword matches
    for keyword, entity_type in SENSITIVE_KEYWORDS.items():
        if keyword in header_lower:
            # Guard: a PERSON keyword combined with an ID token is an
            # identifier column ("Patient ID", "ID Pasien"), not a name.
            if entity_type == "PERSON" and any(
                tok in header_lower for tok in _ID_TOKENS
            ):
                return None
            return entity_type
    
    return None


def analyze_column_content(sample_values: list[str]) -> str | None:
    """
    Analyze column sample values to suggest an entity type using the detection
    engine (Indonesian recognizers, birth-date/name context, custom patterns).

    This complements header-based detection: when a header is ambiguous or in
    an unexpected language, the actual cell content often reveals the type
    (e.g. values that look like emails, NIK numbers, dates, or match a global
    custom pattern such as a Medical Record format).

    Args:
        sample_values: A few representative cell values from the column.

    Returns:
        The most likely entity type, or None if nothing sensitive is detected.
    """
    if not sample_values:
        return None

    # Count entity types detected across the sample values
    type_counts: dict[str, int] = {}
    non_empty = 0

    try:
        from sandiraksa.detection.custom_patterns import find_custom_matches
        from sandiraksa.detection.recognizers.id_nik import NIKRecognizer
        from sandiraksa.detection.recognizers.id_npwp import NPWPRecognizer
        from sandiraksa.detection.recognizers.id_phone import (
            IndonesianPhoneRecognizer,
        )

        nik = NIKRecognizer()
        npwp = NPWPRecognizer()
        phone = IndonesianPhoneRecognizer()

        _EMAIL = _re_email()
        _DATE = _re_date()

        for raw in sample_values:
            value = (raw or "").strip()
            if not value:
                continue
            non_empty += 1

            # 1. Global custom patterns take priority (user-defined, high signal)
            custom = find_custom_matches(value)
            if custom:
                _bump(type_counts, custom[0].label)
                continue

            # 2. Structured Indonesian IDs
            if nik.analyze(value, ["ID_NIK"]):
                _bump(type_counts, "ID_NIK")
                continue
            if npwp.analyze(value, ["ID_NPWP"]):
                _bump(type_counts, "ID_NPWP")
                continue
            if phone.analyze(value, ["ID_PHONE"]):
                _bump(type_counts, "ID_PHONE")
                continue

            # 3. Email
            if _EMAIL.search(value):
                _bump(type_counts, "EMAIL_ADDRESS")
                continue

            # 4. Date-looking values. Without a "birth" header we can't tell
            #    whether it's a birth date or another date, so use generic DATE.
            if _DATE.search(value):
                _bump(type_counts, "DATE")
                continue

    except Exception as e:
        print(f"Column content analysis failed: {e}")
        return None

    if not type_counts or non_empty == 0:
        return None

    # Pick the most frequent type, but require it to cover a strong majority of
    # the sampled values (>= 60%) to avoid false positives from a few outliers.
    best_type = max(type_counts, key=type_counts.get)
    if type_counts[best_type] / non_empty >= 0.6:
        return best_type

    return None


def suggest_column_type(header: str, sample_values: list[str]) -> str | None:
    """
    Suggest an entity type for a column using BOTH the header name and the
    actual cell content.

    Priority:
        1. Header-based match (fast, high precision for known labels).
        2. Content-based match (covers ambiguous / unlabeled columns).

    Args:
        header: Column header text.
        sample_values: Representative sample values from the column.

    Returns:
        Suggested entity type, or None.
    """
    # Header first (most reliable when it uses a known label)
    by_header = analyze_column_header(header)
    if by_header:
        return by_header

    # Content-based structured match (NIK, NPWP, email, etc.)
    by_content = analyze_column_content(sample_values)
    if by_content:
        return by_content

    # Free-text / structured-text (JSON) column -> narrative marker.
    if is_narrative_column(sample_values):
        return NARRATIVE_TYPE

    return None


def _looks_like_json(value: str) -> bool:
    """True if a cell value looks like a JSON object/array."""
    v = value.strip()
    if not (v.startswith("{") or v.startswith("[")):
        return False
    try:
        json.loads(v)
        return True
    except (ValueError, TypeError):
        return False


def is_narrative_column(sample_values: list[str]) -> bool:
    """
    Detect a free-text / structured-text ("narrative") column.

    A column is narrative when its sampled cells are, on average, long free text
    (many characters/words) OR most cells are JSON. Such columns must NOT be
    censored whole-cell; only the PII inside should be tokenized.
    """
    non_empty = [v.strip() for v in sample_values if v and v.strip()]
    if not non_empty:
        return False

    # JSON-heavy column (majority of cells parse as JSON).
    json_count = sum(1 for v in non_empty if _looks_like_json(v))
    if json_count / len(non_empty) >= 0.6:
        return True

    # Long free-text column.
    avg_len = sum(len(v) for v in non_empty) / len(non_empty)
    avg_tokens = sum(len(v.split()) for v in non_empty) / len(non_empty)
    return avg_len >= _NARRATIVE_MIN_AVG_LEN and avg_tokens >= _NARRATIVE_MIN_AVG_TOKENS


def default_protection_mode(suggested_type: str | None, sample_values: list[str]) -> str:
    """
    Choose a default protection mode for a column.

    Narrative/JSON/free-text columns default to PII_ONLY (protect only the PII
    inside each cell); everything else defaults to FULL_CELL.
    """
    if suggested_type == NARRATIVE_TYPE or is_narrative_column(sample_values):
        return ProtectionMode.PII_ONLY.value
    return ProtectionMode.FULL_CELL.value


def _bump(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _re_email():
    import re
    return re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _re_date():
    import re
    return re.compile(
        r"\b\d{1,2}[-/][A-Za-z0-9]{1,9}[-/]\d{2,4}\b"
        r"|\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b"
    )


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
            
            # Get sample values from rows 2-21 (more rows -> better content
            # analysis for columns whose header is ambiguous)
            sample_rows = []
            for i, row in enumerate(sheet.iter_rows(min_row=2, max_row=21, values_only=True)):
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
                
                # Suggest type from header AND content (engine-based)
                suggested_type = suggest_column_type(header, samples)
                
                col_info = ColumnInfo(
                    sheet_name=sheet_name,
                    column_index=col_idx,
                    column_letter=get_column_letter(col_idx),
                    header=header,
                    sample_values=samples[:3],
                    suggested_type=suggested_type,
                    is_selected=suggested_type is not None,  # Auto-select if suggested
                    protection_mode=default_protection_mode(suggested_type, samples),
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
        # Use up to 20 data rows for content analysis (better type inference)
        data_rows = rows[1:21]
        row_count = len(rows)
        
        # Build column info
        columns = []
        for col_idx, header in enumerate(headers):
            # Get sample values for this column
            samples = []
            for row in data_rows:
                if col_idx < len(row) and row[col_idx]:
                    samples.append(str(row[col_idx]))
            
            # Suggest type from header AND content (engine-based)
            suggested_type = suggest_column_type(header, samples)
            
            col_info = ColumnInfo(
                sheet_name="CSV",  # CSV has no sheet name
                column_index=col_idx,  # 0-based for CSV
                column_letter=get_column_letter(col_idx + 1),  # Convert to letter
                header=header,
                sample_values=samples[:3],
                suggested_type=suggested_type,
                is_selected=suggested_type is not None,
                protection_mode=default_protection_mode(suggested_type, samples),
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
            is_narrative = self._column.suggested_type == NARRATIVE_TYPE
            badge_text = "TEKS NARASI" if is_narrative else self._column.suggested_type
            badge_color = (
                ColorPalette.WARNING.value if is_narrative
                else ColorPalette.PRIMARY.value
            )
            type_label = QLabel(badge_text)
            type_label.setToolTip(
                "Kolom teks bebas/JSON — hanya data pribadi di dalamnya yang "
                "diproteksi (bukan seluruh sel)."
                if is_narrative else ""
            )
            type_label.setStyleSheet(
                f"background-color: {badge_color}; "
                f"color: white; "
                f"padding: 2px 8px; "
                f"border-radius: 4px; "
                f"font-size: {FONT_SIZE.SM}px;"
            )
            layout.addWidget(type_label)
        
        layout.addStretch()

        # Protection-mode selector (how the cell is protected)
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet(f"color: {ColorPalette.GRAY_500.value};")
        layout.addWidget(mode_label)

        self._mode_combo = QComboBox()
        # (label, value) — order matters for index mapping below
        self._mode_combo.addItem("Sensor seluruh sel", ProtectionMode.FULL_CELL.value)
        self._mode_combo.addItem("Proteksi data pribadi", ProtectionMode.PII_ONLY.value)
        self._mode_combo.setToolTip(
            "Sensor seluruh sel: ganti seluruh isi sel dengan satu token.\n"
            "Proteksi data pribadi: hanya bagian PII di dalam sel yang diganti "
            "(cocok untuk teks bebas / JSON)."
        )
        current = getattr(self._column, "protection_mode", ProtectionMode.FULL_CELL.value)
        idx = self._mode_combo.findData(current)
        self._mode_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self._mode_combo)

        # Sample values
        if self._column.sample_values:
            samples = ", ".join(self._column.sample_values[:2])
            if len(samples) > 40:
                samples = samples[:40] + "..."
            sample_label = QLabel(f"e.g. {samples}")
            sample_label.setStyleSheet(f"color: {ColorPalette.GRAY_500.value}; font-style: italic;")
            layout.addWidget(sample_label)

    def _on_mode_changed(self, index: int) -> None:
        """Persist the chosen protection mode onto the ColumnInfo."""
        value = self._mode_combo.itemData(index)
        if value:
            self._column.protection_mode = value
    
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
    "ProtectionMode",
    "NARRATIVE_TYPE",
    "analyze_excel_file",
    "analyze_csv_file",
    "analyze_column_header",
    "analyze_column_content",
    "is_narrative_column",
    "default_protection_mode",
    "suggest_column_type",
]
