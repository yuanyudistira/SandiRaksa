"""
CSV file protection service.

Replaces selected column values with tokens while preserving file structure.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from sandiraksa.protection.tokenizer import Tokenizer, TokenizerFactory

logger = logging.getLogger(__name__)


@dataclass
class CSVColumnConfig:
    """Configuration for a column to protect."""
    
    column_index: int  # 0-based
    column_name: str
    entity_type: str = "PII"


@dataclass
class CSVProtectionResult:
    """Result of protecting a CSV file."""
    
    success: bool
    output_path: str | None = None
    error_message: str | None = None
    cells_protected: int = 0
    rows_processed: int = 0
    duration_seconds: float = 0.0


@dataclass
class CSVProtectionProgress:
    """Progress information during protection."""
    
    current_row: int = 0
    total_rows: int = 0
    cells_protected: int = 0


class CSVProtector:
    """
    Protects CSV files by replacing selected column values with tokens.
    
    Features:
    - Preserves original file structure (delimiter, quoting)
    - Processes only selected columns
    - Uses consistent tokenization (same value = same token)
    - Auto-detects delimiter and encoding
    """
    
    def __init__(
        self,
        project_id: str,
        tokenizer: Tokenizer | None = None,
    ) -> None:
        """
        Initialize CSV protector.
        
        Args:
            project_id: Project ID for token scoping.
            tokenizer: Optional tokenizer instance.
        """
        self._project_id = project_id
        self._tokenizer = tokenizer or TokenizerFactory.get_tokenizer(project_id)
    
    def protect_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
        columns: list[CSVColumnConfig],
        progress_callback: Callable[[CSVProtectionProgress], None] | None = None,
    ) -> CSVProtectionResult:
        """
        Protect a CSV file by tokenizing selected columns.
        
        Args:
            input_path: Path to input CSV file.
            output_path: Path where protected file will be saved.
            columns: List of columns to protect.
            progress_callback: Optional callback for progress updates.
            
        Returns:
            CSVProtectionResult with status and statistics.
        """
        import gc
        gc_was_enabled = gc.isenabled()
        gc.disable()  # Disable GC during file I/O to prevent heap corruption with PySide6
        
        input_path = Path(input_path)
        output_path = Path(output_path)
        
        start_time = datetime.now()
        progress = CSVProtectionProgress()
        cells_protected = 0
        rows_processed = 0
        
        try:
            # Detect delimiter and read file
            delimiter = self._detect_delimiter(input_path)
            encoding = self._detect_encoding(input_path)
            
            logger.info(f"Loading CSV: {input_path} (delimiter='{delimiter}', encoding={encoding})")
            
            # Read all rows
            with open(input_path, 'r', encoding=encoding, newline='') as f:
                reader = csv.reader(f, delimiter=delimiter)
                rows = list(reader)
            
            if not rows:
                return CSVProtectionResult(
                    success=False,
                    error_message="File CSV kosong",
                )
            
            # Get header and data
            header = rows[0]
            data_rows = rows[1:]
            
            progress.total_rows = len(data_rows)
            
            # Build column index map
            col_indices = {col.column_index for col in columns}
            col_entity_map = {col.column_index: col.entity_type for col in columns}
            
            # Process data rows
            protected_rows = [header]  # Keep header unchanged
            
            for row_idx, row in enumerate(data_rows):
                protected_row = list(row)
                
                for col_idx in col_indices:
                    if col_idx < len(row):
                        value = row[col_idx]
                        
                        # Skip empty values
                        if value is None or not str(value).strip():
                            continue
                        
                        str_value = str(value).strip()
                        entity_type = col_entity_map.get(col_idx, "PII")
                        
                        # Get or create token
                        token = self._tokenizer.get_or_create_token(entity_type, str_value)
                        protected_row[col_idx] = token
                        cells_protected += 1
                
                protected_rows.append(protected_row)
                rows_processed += 1
                
                # Update progress
                progress.current_row = row_idx + 1
                progress.cells_protected = cells_protected
                
                if progress_callback and (row_idx % 100 == 0):
                    progress_callback(progress)
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write protected CSV
            logger.info(f"Saving protected file: {output_path}")
            with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f, delimiter=delimiter)
                writer.writerows(protected_rows)
            
            # Final progress
            if progress_callback:
                progress_callback(progress)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"CSV protection complete: {cells_protected} cells protected "
                f"in {duration:.2f}s"
            )
            
            return CSVProtectionResult(
                success=True,
                output_path=str(output_path),
                cells_protected=cells_protected,
                rows_processed=rows_processed,
                duration_seconds=duration,
            )
            
        except Exception as e:
            logger.error(f"CSV protection failed: {e}", exc_info=True)
            return CSVProtectionResult(
                success=False,
                error_message=str(e),
            )
        finally:
            if gc_was_enabled:
                gc.enable()
    
    def _detect_delimiter(self, path: Path) -> str:
        """Detect CSV delimiter by sampling first few lines."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                sample = f.read(4096)
            
            # Try to sniff delimiter
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
                return dialect.delimiter
            except csv.Error:
                pass
            
            # Fallback: count occurrences
            delimiters = [',', ';', '\t', '|']
            counts = {d: sample.count(d) for d in delimiters}
            return max(counts, key=counts.get)
            
        except Exception:
            return ','  # Default to comma
    
    def _detect_encoding(self, path: Path) -> str:
        """Detect file encoding."""
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    f.read(1024)
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        return 'utf-8'  # Default


def get_csv_columns(path: str | Path) -> list[tuple[int, str]]:
    """
    Get column names from CSV file.
    
    Args:
        path: Path to CSV file.
        
    Returns:
        List of (index, column_name) tuples.
    """
    path = Path(path)
    
    # Detect delimiter and encoding
    protector = CSVProtector("temp")
    delimiter = protector._detect_delimiter(path)
    encoding = protector._detect_encoding(path)
    
    with open(path, 'r', encoding=encoding, newline='') as f:
        reader = csv.reader(f, delimiter=delimiter)
        header = next(reader, [])
    
    return [(i, name) for i, name in enumerate(header)]


def parse_csv_columns(
    selected_columns: list[tuple[int, str]],
    entity_type_map: dict[str, str] | None = None,
) -> list[CSVColumnConfig]:
    """
    Parse selected columns to CSVColumnConfig list.
    
    Args:
        selected_columns: List of (col_idx, col_name) tuples.
        entity_type_map: Optional mapping of column names to entity types.
        
    Returns:
        List of CSVColumnConfig objects.
    """
    configs = []
    entity_type_map = entity_type_map or {}
    
    # Default entity type mapping based on column name keywords
    default_entity_types = {
        "nama": "PERSON",
        "name": "PERSON",
        "email": "EMAIL",
        "e-mail": "EMAIL",
        "phone": "PHONE_NUMBER",
        "telepon": "PHONE_NUMBER",
        "telp": "PHONE_NUMBER",
        "hp": "PHONE_NUMBER",
        "handphone": "PHONE_NUMBER",
        "nik": "ID_NIK",
        "ktp": "ID_NIK",
        "npwp": "ID_NPWP",
        "kk": "ID_KK",
        "alamat": "ADDRESS",
        "address": "ADDRESS",
        "rekam medis": "MEDICAL_RECORD",
        "medical record": "MEDICAL_RECORD",
        "mrn": "MEDICAL_RECORD",
        "no rm": "MEDICAL_RECORD",
        "norm": "MEDICAL_RECORD",
        "tanggal lahir": "DATE_OF_BIRTH",
        "tgl lahir": "DATE_OF_BIRTH",
        "dob": "DATE_OF_BIRTH",
        "birth": "DATE_OF_BIRTH",
    }
    
    for col_idx, col_name in selected_columns:
        # Determine entity type
        entity_type = entity_type_map.get(col_name, "PII")
        
        # Try to infer from column name
        if entity_type == "PII":
            col_name_lower = col_name.lower()
            for keyword, etype in default_entity_types.items():
                if keyword in col_name_lower:
                    entity_type = etype
                    break
        
        configs.append(CSVColumnConfig(
            column_index=col_idx,
            column_name=col_name,
            entity_type=entity_type,
        ))
    
    return configs


__all__ = [
    "CSVColumnConfig",
    "CSVProtectionProgress",
    "CSVProtectionResult",
    "CSVProtector",
    "get_csv_columns",
    "parse_csv_columns",
]
