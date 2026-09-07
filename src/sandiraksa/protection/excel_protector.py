"""
Excel file protection service.

Replaces selected column values with tokens while preserving file structure.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import openpyxl
from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from sandiraksa.protection.tokenizer import Tokenizer, TokenizerFactory

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class ColumnConfig:
    """Configuration for a column to protect."""
    
    sheet_name: str
    column_index: int  # 1-based
    column_name: str
    entity_type: str = "PII"  # Default entity type


@dataclass
class ProtectionResult:
    """Result of protecting a file."""
    
    success: bool
    output_path: str | None = None
    error_message: str | None = None
    cells_protected: int = 0
    rows_processed: int = 0
    tokens_created: int = 0
    duration_seconds: float = 0.0


@dataclass
class ProtectionProgress:
    """Progress information during protection."""
    
    current_sheet: str = ""
    current_row: int = 0
    total_rows: int = 0
    cells_protected: int = 0


class ExcelProtector:
    """
    Protects Excel files by replacing selected column values with tokens.
    
    Features:
    - Preserves original file structure and formatting
    - Processes only selected columns
    - Uses consistent tokenization (same value = same token)
    - Reports progress for UI feedback
    """
    
    def __init__(
        self,
        project_id: str,
        tokenizer: Tokenizer | None = None,
    ) -> None:
        """
        Initialize Excel protector.
        
        Args:
            project_id: Project ID for token scoping.
            tokenizer: Optional tokenizer instance. If None, creates one.
        """
        self._project_id = project_id
        self._tokenizer = tokenizer or TokenizerFactory.get_tokenizer(project_id)
    
    def protect_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
        columns: list[ColumnConfig],
        progress_callback: Callable[[ProtectionProgress], None] | None = None,
    ) -> ProtectionResult:
        """
        Protect an Excel file by tokenizing selected columns.
        
        Args:
            input_path: Path to input Excel file.
            output_path: Path where protected file will be saved.
            columns: List of columns to protect.
            progress_callback: Optional callback for progress updates.
            
        Returns:
            ProtectionResult with status and statistics.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        
        start_time = datetime.now()
        progress = ProtectionProgress()
        cells_protected = 0
        rows_processed = 0
        
        try:
            # Load workbook with data_only=False to preserve formulas
            logger.info(f"Loading workbook: {input_path}")
            wb = load_workbook(input_path, data_only=False)
            
            # Group columns by sheet
            columns_by_sheet: dict[str, list[ColumnConfig]] = {}
            for col in columns:
                if col.sheet_name not in columns_by_sheet:
                    columns_by_sheet[col.sheet_name] = []
                columns_by_sheet[col.sheet_name].append(col)
            
            # Process each sheet
            for sheet_name, sheet_columns in columns_by_sheet.items():
                if sheet_name not in wb.sheetnames:
                    logger.warning(f"Sheet not found: {sheet_name}")
                    continue
                
                ws = wb[sheet_name]
                progress.current_sheet = sheet_name
                progress.total_rows = ws.max_row - 1  # Exclude header
                
                # Process each column
                for col_config in sheet_columns:
                    protected = self._protect_column(
                        ws,
                        col_config,
                        progress,
                        progress_callback,
                    )
                    cells_protected += protected
                
                rows_processed += progress.total_rows
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save protected workbook
            logger.info(f"Saving protected file: {output_path}")
            wb.save(output_path)
            wb.close()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"Protection complete: {cells_protected} cells protected "
                f"in {duration:.2f}s"
            )
            
            return ProtectionResult(
                success=True,
                output_path=str(output_path),
                cells_protected=cells_protected,
                rows_processed=rows_processed,
                tokens_created=self._tokenizer.get_mapping_count(),
                duration_seconds=duration,
            )
            
        except Exception as e:
            logger.error(f"Protection failed: {e}", exc_info=True)
            return ProtectionResult(
                success=False,
                error_message=str(e),
            )
    
    def _protect_column(
        self,
        ws: Worksheet,
        col_config: ColumnConfig,
        progress: ProtectionProgress,
        progress_callback: Callable[[ProtectionProgress], None] | None,
    ) -> int:
        """
        Protect a single column in a worksheet.
        
        Returns number of cells protected.
        """
        cells_protected = 0
        col_idx = col_config.column_index
        entity_type = col_config.entity_type
        
        # Start from row 2 (skip header)
        for row in range(2, ws.max_row + 1):
            cell = ws.cell(row=row, column=col_idx)
            value = cell.value
            
            # Skip empty cells
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            
            # Convert to string for tokenization
            str_value = str(value).strip()
            
            # Get or create token
            token = self._tokenizer.get_or_create_token(entity_type, str_value)
            
            # Replace cell value with token
            cell.value = token
            cells_protected += 1
            
            # Update progress
            progress.current_row = row - 1
            progress.cells_protected = cells_protected
            
            # Report progress every 100 rows
            if progress_callback and (row % 100 == 0):
                progress_callback(progress)
        
        # Final progress update
        if progress_callback:
            progress_callback(progress)
        
        return cells_protected


def generate_output_path(
    input_path: str | Path,
    output_dir: str | Path | None = None,
    suffix: str = "_protected",
) -> Path:
    """
    Generate output path for protected file.
    
    Args:
        input_path: Original file path.
        output_dir: Output directory. If None, uses same dir as input.
        suffix: Suffix to add before extension.
        
    Returns:
        Path for output file.
    """
    input_path = Path(input_path)
    
    if output_dir is None:
        output_dir = input_path.parent
    else:
        output_dir = Path(output_dir)
    
    stem = input_path.stem
    ext = input_path.suffix
    
    # Generate unique name if file exists
    output_path = output_dir / f"{stem}{suffix}{ext}"
    counter = 1
    
    while output_path.exists():
        output_path = output_dir / f"{stem}{suffix}_{counter}{ext}"
        counter += 1
    
    return output_path


def parse_selected_columns(
    selected_columns: dict[str, list[tuple[int, str]]],
    entity_type_map: dict[str, str] | None = None,
) -> list[ColumnConfig]:
    """
    Parse selected columns dict to ColumnConfig list.
    
    Args:
        selected_columns: Dict of {sheet_name: [(col_idx, col_name), ...]}
        entity_type_map: Optional mapping of column names to entity types.
        
    Returns:
        List of ColumnConfig objects.
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
    }
    
    for sheet_name, columns in selected_columns.items():
        for col_idx, col_name in columns:
            # Determine entity type
            entity_type = entity_type_map.get(col_name, "PII")
            
            # Try to infer from column name
            if entity_type == "PII":
                col_name_lower = col_name.lower()
                for keyword, etype in default_entity_types.items():
                    if keyword in col_name_lower:
                        entity_type = etype
                        break
            
            configs.append(ColumnConfig(
                sheet_name=sheet_name,
                column_index=col_idx,
                column_name=col_name,
                entity_type=entity_type,
            ))
    
    return configs


__all__ = [
    "ColumnConfig",
    "ExcelProtector",
    "ProtectionProgress",
    "ProtectionResult",
    "generate_output_path",
    "parse_selected_columns",
]
