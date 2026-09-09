"""
XLSX Document Adapter for Unified Detection Pipeline.

Lightweight adapter that produces LogicalSegments from Excel files
for the unified detection engine.

Design:
- Each cell becomes a LogicalSegment
- Column headers provide context
- Sheet structure preserved
- Uses openpyxl for file access
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

from sandiraksa.documents.base import (
    BaseDocumentAdapter,
    DocumentFormat,
    ExtractionResult,
    ProtectionResult,
    Replacement,
)
from sandiraksa.documents.char_map import CharMap, CharMapEntry
from sandiraksa.documents.location import DocumentComponent, DocumentLocation
from sandiraksa.documents.logical_segment import LogicalSegment

if TYPE_CHECKING:
    from openpyxl import Workbook
    from openpyxl.cell.cell import Cell
    from openpyxl.worksheet.worksheet import Worksheet

logger = logging.getLogger(__name__)


def _get_cell_address(row: int, col: int) -> str:
    """Convert row/col (1-indexed) to cell address like A1, B2."""
    # Convert column number to letters
    result = []
    while col > 0:
        col, remainder = divmod(col - 1, 26)
        result.append(chr(65 + remainder))
    return "".join(reversed(result)) + str(row)


class XlsxDocumentAdapter(BaseDocumentAdapter):
    """
    Document adapter for XLSX (Excel) files.

    Extracts each cell as a LogicalSegment with column header context.
    """

    def __init__(self, file_path: str | Path) -> None:
        """
        Initialize XLSX adapter.

        Args:
            file_path: Path to the XLSX file
        """
        self._path = Path(file_path)
        self._workbook: "Workbook | None" = None
        self._loaded = False

    @property
    def format(self) -> DocumentFormat:
        """Document format."""
        return DocumentFormat.XLSX

    @property
    def file_path(self) -> Path:
        """Path to the document."""
        return self._path

    def _load_file(self) -> None:
        """Load the Excel workbook."""
        if self._loaded:
            return

        try:
            from openpyxl import load_workbook

            self._workbook = load_workbook(
                self._path,
                read_only=False,  # Need write access for modifications
                data_only=True,   # Get values instead of formulas
            )
            self._loaded = True
            logger.debug(
                f"Loaded XLSX: {len(self._workbook.sheetnames)} sheets"
            )
        except ImportError:
            raise ImportError(
                "openpyxl required for XLSX support. "
                "Install with: pip install openpyxl"
            )

    def _get_sheet_headers(self, sheet: "Worksheet") -> list[str]:
        """Get column headers from first row of sheet."""
        headers: list[str] = []
        for cell in sheet[1]:
            if cell.value is not None:
                headers.append(str(cell.value))
            else:
                headers.append("")
        return headers

    def extract(self) -> ExtractionResult:
        """
        Extract content as LogicalSegments.

        Returns:
            ExtractionResult with segments for each cell
        """
        self._load_file()

        if not self._workbook:
            return ExtractionResult(segments=[], metadata={})

        segments: list[LogicalSegment] = []
        file_id = str(self._path)
        total_cells = 0

        for sheet_name in self._workbook.sheetnames:
            sheet = self._workbook[sheet_name]
            headers = self._get_sheet_headers(sheet)

            # Get dimensions
            min_row = sheet.min_row or 1
            max_row = sheet.max_row or 1
            min_col = sheet.min_column or 1
            max_col = sheet.max_column or 1

            # Process data rows (skip header row)
            for row_idx in range(min_row + 1, max_row + 1):
                for col_idx in range(min_col, max_col + 1):
                    cell = sheet.cell(row=row_idx, column=col_idx)

                    # Skip empty cells
                    if cell.value is None:
                        continue

                    cell_value = str(cell.value)
                    if not cell_value.strip():
                        continue

                    # Get column header
                    header_idx = col_idx - min_col
                    header = headers[header_idx] if header_idx < len(headers) else None

                    # Cell address (e.g., "A1")
                    cell_address = _get_cell_address(row_idx, col_idx)

                    # Create segment
                    segment = LogicalSegment.for_xlsx_cell(
                        text=cell_value,
                        file_id=file_id,
                        sheet=sheet_name,
                        cell=cell_address,
                        row=row_idx - 1,  # 0-indexed
                        column=col_idx - 1,  # 0-indexed
                        table_headers=headers,
                    )

                    # Add key_label if header suggests PII field
                    if header:
                        segment.key_label = header
                        segment.is_value_of_key = True

                    segments.append(segment)
                    total_cells += 1

        return ExtractionResult(
            segments=segments,
            metadata={
                "sheet_count": len(self._workbook.sheetnames),
                "sheet_names": self._workbook.sheetnames,
                "total_cells": total_cells,
            },
        )

    def extract_sheet(self, sheet_name: str) -> list[LogicalSegment]:
        """
        Extract segments from a specific sheet.

        Args:
            sheet_name: Name of the sheet to extract

        Returns:
            List of LogicalSegments from that sheet
        """
        self._load_file()

        if not self._workbook or sheet_name not in self._workbook.sheetnames:
            return []

        segments: list[LogicalSegment] = []
        file_id = str(self._path)

        sheet = self._workbook[sheet_name]
        headers = self._get_sheet_headers(sheet)

        min_row = sheet.min_row or 1
        max_row = sheet.max_row or 1
        min_col = sheet.min_column or 1
        max_col = sheet.max_column or 1

        for row_idx in range(min_row + 1, max_row + 1):
            for col_idx in range(min_col, max_col + 1):
                cell = sheet.cell(row=row_idx, column=col_idx)

                if cell.value is None:
                    continue

                cell_value = str(cell.value)
                if not cell_value.strip():
                    continue

                header_idx = col_idx - min_col
                header = headers[header_idx] if header_idx < len(headers) else None
                cell_address = _get_cell_address(row_idx, col_idx)

                segment = LogicalSegment.for_xlsx_cell(
                    text=cell_value,
                    file_id=file_id,
                    sheet=sheet_name,
                    cell=cell_address,
                    row=row_idx - 1,
                    column=col_idx - 1,
                    table_headers=headers,
                )

                if header:
                    segment.key_label = header
                    segment.is_value_of_key = True

                segments.append(segment)

        return segments

    def extract_streaming(self) -> Iterator[LogicalSegment]:
        """
        Extract segments one at a time for memory efficiency.

        Yields:
            LogicalSegment for each non-empty cell
        """
        try:
            from openpyxl import load_workbook

            # Use read-only mode for streaming
            workbook = load_workbook(
                self._path,
                read_only=True,
                data_only=True,
            )

            file_id = str(self._path)

            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                headers: list[str] = []
                first_row = True

                for row_idx, row in enumerate(sheet.iter_rows(), start=1):
                    if first_row:
                        # Extract headers
                        headers = [
                            str(cell.value) if cell.value else ""
                            for cell in row
                        ]
                        first_row = False
                        continue

                    for col_idx, cell in enumerate(row, start=1):
                        if cell.value is None:
                            continue

                        cell_value = str(cell.value)
                        if not cell_value.strip():
                            continue

                        header = headers[col_idx - 1] if col_idx - 1 < len(headers) else None
                        cell_address = _get_cell_address(row_idx, col_idx)

                        segment = LogicalSegment.for_xlsx_cell(
                            text=cell_value,
                            file_id=file_id,
                            sheet=sheet_name,
                            cell=cell_address,
                            row=row_idx - 1,
                            column=col_idx - 1,
                            table_headers=headers,
                        )

                        if header:
                            segment.key_label = header
                            segment.is_value_of_key = True

                        yield segment

            workbook.close()

        except ImportError:
            raise ImportError(
                "openpyxl required for XLSX support. "
                "Install with: pip install openpyxl"
            )

    def apply_replacements(
        self, replacements: list[Replacement]
    ) -> ProtectionResult:
        """
        Apply replacements to the XLSX file.

        Args:
            replacements: List of replacements to apply

        Returns:
            ProtectionResult with modified workbook bytes
        """
        self._load_file()

        if not self._workbook:
            return ProtectionResult(
                content=b"",
                modified_count=0,
                format=DocumentFormat.XLSX,
            )

        # Group replacements by sheet and cell
        cell_replacements: dict[tuple[str, str], list[Replacement]] = {}
        for repl in replacements:
            loc = repl.location
            sheet = loc.sheet or self._workbook.sheetnames[0]
            cell = loc.cell or _get_cell_address(
                (loc.row or 0) + 1, (loc.column or 0) + 1
            )
            key = (sheet, cell)
            if key not in cell_replacements:
                cell_replacements[key] = []
            cell_replacements[key].append(repl)

        # Apply replacements
        modified_count = 0

        for (sheet_name, cell_address), repls in cell_replacements.items():
            if sheet_name not in self._workbook.sheetnames:
                continue

            sheet = self._workbook[sheet_name]
            cell = sheet[cell_address]

            if cell.value is None:
                continue

            cell_value = str(cell.value)

            # Sort by start position descending
            sorted_repls = sorted(repls, key=lambda r: r.start, reverse=True)

            for repl in sorted_repls:
                cell_value = (
                    cell_value[: repl.start]
                    + repl.new_text
                    + cell_value[repl.end:]
                )

            cell.value = cell_value
            modified_count += 1

        # Save to bytes
        from io import BytesIO
        output = BytesIO()
        self._workbook.save(output)

        return ProtectionResult(
            content=output.getvalue(),
            modified_count=modified_count,
            format=DocumentFormat.XLSX,
        )

    def validate(self) -> list[str]:
        """
        Validate the XLSX file.

        Returns:
            List of validation errors (empty if valid)
        """
        errors: list[str] = []

        if not self._path.exists():
            errors.append(f"File not found: {self._path}")
            return errors

        if self._path.suffix.lower() not in (".xlsx", ".xlsm"):
            errors.append(f"Unexpected file extension: {self._path.suffix}")

        try:
            self._load_file()
        except ImportError as e:
            errors.append(str(e))
        except Exception as e:
            errors.append(f"Failed to open workbook: {e}")

        return errors

    def close(self) -> None:
        """Close the workbook and release resources."""
        if self._workbook:
            self._workbook.close()
            self._workbook = None
            self._loaded = False


__all__ = [
    "XlsxDocumentAdapter",
]
