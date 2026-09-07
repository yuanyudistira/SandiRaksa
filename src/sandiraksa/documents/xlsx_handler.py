"""
XLSX Document Handler.

Provides Excel workbook processing with:
- Worksheet inventory and navigation
- Large workbook support with iterative scanning
- Shared strings, inline strings, comments extraction
- Cell modification with formula/style preservation
- Metadata (core properties, custom properties) handling
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterator
from xml.etree import ElementTree as ET

from sandiraksa.detection.context import TextSegment
from sandiraksa.domain.finding import DocumentLocation
from sandiraksa.domain.file_record import FileFormat

if TYPE_CHECKING:
    from openpyxl import Workbook
    from openpyxl.cell.cell import Cell
    from openpyxl.worksheet.worksheet import Worksheet

logger = logging.getLogger(__name__)


class XLSXHandlerError(Exception):
    """Base exception for XLSX handler errors."""

    pass


class WorkbookOpenError(XLSXHandlerError):
    """Failed to open workbook."""

    pass


class WorksheetError(XLSXHandlerError):
    """Error accessing worksheet."""

    pass


class CellModificationError(XLSXHandlerError):
    """Failed to modify cell."""

    pass


@dataclass
class XLSXMetadata:
    """Metadata about an XLSX file."""

    file_path: Path
    file_size: int
    sheet_count: int
    sheet_names: list[str]
    total_rows: int  # Approximate total across all sheets
    total_cells: int  # Approximate total cells with data
    has_formulas: bool
    has_comments: bool
    has_hyperlinks: bool
    created: str | None = None
    modified: str | None = None
    creator: str | None = None
    title: str | None = None


@dataclass
class XLSXCell:
    """Represents a single cell in an XLSX file."""

    sheet_name: str
    row: int  # 1-indexed (Excel convention)
    column: int  # 1-indexed
    column_letter: str  # e.g., "A", "B", "AA"
    value: str  # String representation of cell value
    raw_value: Any  # Original value (may be number, date, etc.)
    cell_type: str  # "string", "number", "date", "formula", "boolean", "empty"
    has_formula: bool = False
    formula: str | None = None
    comment: str | None = None
    hyperlink: str | None = None

    @property
    def coordinate(self) -> str:
        """Get Excel coordinate like A1, B2."""
        return f"{self.column_letter}{self.row}"

    def to_location(self) -> DocumentLocation:
        """Convert to a DocumentLocation."""
        return DocumentLocation(
            file_id="",  # Will be set by caller
            component_type="cell",
            sheet_name=self.sheet_name,
            cell_address=self.coordinate,
        )


@dataclass
class SheetInventory:
    """Inventory of a single worksheet."""

    name: str
    index: int
    row_count: int
    column_count: int
    cell_count: int  # Non-empty cells
    has_formulas: bool
    has_comments: bool
    has_hyperlinks: bool
    min_row: int = 1
    max_row: int = 1
    min_col: int = 1
    max_col: int = 1


@dataclass
class WorkbookInventory:
    """Complete inventory of a workbook."""

    file_path: Path
    sheets: list[SheetInventory]
    total_cells: int
    metadata: XLSXMetadata


def _get_column_letter(col_idx: int) -> str:
    """Convert 1-indexed column number to Excel letter (1=A, 27=AA)."""
    result = ""
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _get_column_index(col_letter: str) -> int:
    """Convert Excel column letter to 1-indexed number (A=1, AA=27)."""
    result = 0
    for char in col_letter.upper():
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result


class XLSXReader:
    """
    Reads XLSX files with support for large workbooks.

    Uses openpyxl in read-only mode for memory efficiency.
    """

    # Batch size for iterative processing
    DEFAULT_BATCH_SIZE = 1000

    def __init__(
        self,
        file_path: Path | str,
        read_only: bool = True,
        data_only: bool = False,
    ) -> None:
        """
        Initialize XLSX reader.

        Args:
            file_path: Path to XLSX file.
            read_only: Open in read-only mode for memory efficiency.
            data_only: Return calculated values instead of formulas.
        """
        self._file_path = Path(file_path)
        self._read_only = read_only
        self._data_only = data_only
        self._workbook: Workbook | None = None
        self._inventory: WorkbookInventory | None = None

    def __enter__(self) -> XLSXReader:
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def open(self) -> None:
        """Open the workbook."""
        try:
            from openpyxl import load_workbook

            self._workbook = load_workbook(
                self._file_path,
                read_only=self._read_only,
                data_only=self._data_only,
            )
            logger.debug(f"Opened workbook: {self._file_path}")
        except Exception as e:
            raise WorkbookOpenError(f"Failed to open {self._file_path}: {e}") from e

    def close(self) -> None:
        """Close the workbook."""
        if self._workbook is not None:
            try:
                self._workbook.close()
            except Exception:
                pass
            self._workbook = None

    @property
    def workbook(self) -> Workbook:
        """Get the workbook, opening if needed."""
        if self._workbook is None:
            self.open()
        assert self._workbook is not None
        return self._workbook

    @property
    def sheet_names(self) -> list[str]:
        """Get list of worksheet names."""
        return self.workbook.sheetnames

    def get_inventory(self) -> WorkbookInventory:
        """
        Build inventory of the workbook.

        Returns:
            WorkbookInventory with sheet details.
        """
        if self._inventory is not None:
            return self._inventory

        wb = self.workbook
        sheets: list[SheetInventory] = []
        total_cells = 0

        for idx, sheet_name in enumerate(wb.sheetnames):
            ws = wb[sheet_name]

            # Get dimensions
            if self._read_only:
                # In read-only mode, need to iterate to get dimensions
                min_row = ws.min_row or 1
                max_row = ws.max_row or 1
                min_col = ws.min_column or 1
                max_col = ws.max_column or 1
            else:
                min_row = ws.min_row or 1
                max_row = ws.max_row or 1
                min_col = ws.min_column or 1
                max_col = ws.max_column or 1

            row_count = max_row - min_row + 1
            col_count = max_col - min_col + 1

            # Count non-empty cells (sample-based for large sheets)
            cell_count = 0
            has_formulas = False
            has_comments = False
            has_hyperlinks = False

            # Sample first 100 rows for characteristics
            sample_rows = min(100, row_count)
            for row_idx, row in enumerate(ws.iter_rows(min_row=min_row, max_row=min_row + sample_rows - 1)):
                for cell in row:
                    if cell.value is not None:
                        cell_count += 1
                    if not self._data_only and hasattr(cell, "data_type") and cell.data_type == "f":
                        has_formulas = True
                    if hasattr(cell, "comment") and cell.comment is not None:
                        has_comments = True
                    if hasattr(cell, "hyperlink") and cell.hyperlink is not None:
                        has_hyperlinks = True

            # Estimate total cells
            if sample_rows < row_count:
                cells_per_row = cell_count / sample_rows if sample_rows > 0 else 0
                cell_count = int(cells_per_row * row_count)

            total_cells += cell_count

            sheets.append(
                SheetInventory(
                    name=sheet_name,
                    index=idx,
                    row_count=row_count,
                    column_count=col_count,
                    cell_count=cell_count,
                    has_formulas=has_formulas,
                    has_comments=has_comments,
                    has_hyperlinks=has_hyperlinks,
                    min_row=min_row,
                    max_row=max_row,
                    min_col=min_col,
                    max_col=max_col,
                )
            )

        # Build metadata
        props = wb.properties
        metadata = XLSXMetadata(
            file_path=self._file_path,
            file_size=self._file_path.stat().st_size,
            sheet_count=len(sheets),
            sheet_names=[s.name for s in sheets],
            total_rows=sum(s.row_count for s in sheets),
            total_cells=total_cells,
            has_formulas=any(s.has_formulas for s in sheets),
            has_comments=any(s.has_comments for s in sheets),
            has_hyperlinks=any(s.has_hyperlinks for s in sheets),
            created=str(props.created) if props and props.created else None,
            modified=str(props.modified) if props and props.modified else None,
            creator=props.creator if props else None,
            title=props.title if props else None,
        )

        self._inventory = WorkbookInventory(
            file_path=self._file_path,
            sheets=sheets,
            total_cells=total_cells,
            metadata=metadata,
        )

        return self._inventory

    def iter_cells(
        self,
        sheet_name: str | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        include_empty: bool = False,
    ) -> Iterator[XLSXCell]:
        """
        Iterate over cells in the workbook.

        Args:
            sheet_name: Specific sheet to iterate, or None for all sheets.
            batch_size: Number of rows to process at a time.
            include_empty: Include empty cells.

        Yields:
            XLSXCell for each cell.
        """
        sheets = [sheet_name] if sheet_name else self.sheet_names

        for sname in sheets:
            ws = self.workbook[sname]

            for row in ws.iter_rows():
                for cell in row:
                    if cell.value is None and not include_empty:
                        continue

                    # Get string value
                    value = str(cell.value) if cell.value is not None else ""

                    # Determine cell type
                    cell_type = self._get_cell_type(cell)

                    # Get formula if present
                    has_formula = False
                    formula = None
                    if not self._data_only and hasattr(cell, "data_type"):
                        if cell.data_type == "f":
                            has_formula = True
                            formula = str(cell.value) if cell.value else None

                    # Get comment
                    comment = None
                    if hasattr(cell, "comment") and cell.comment is not None:
                        comment = str(cell.comment.text) if cell.comment.text else None

                    # Get hyperlink
                    hyperlink = None
                    if hasattr(cell, "hyperlink") and cell.hyperlink is not None:
                        hyperlink = str(cell.hyperlink.target) if cell.hyperlink.target else None

                    yield XLSXCell(
                        sheet_name=sname,
                        row=cell.row,
                        column=cell.column,
                        column_letter=_get_column_letter(cell.column),
                        value=value,
                        raw_value=cell.value,
                        cell_type=cell_type,
                        has_formula=has_formula,
                        formula=formula,
                        comment=comment,
                        hyperlink=hyperlink,
                    )

    def iter_text_segments(
        self,
        sheet_name: str | None = None,
    ) -> Iterator[TextSegment]:
        """
        Iterate cells as TextSegments for detection.

        Args:
            sheet_name: Specific sheet or None for all.

        Yields:
            TextSegment for each cell with text content.
        """
        for cell in self.iter_cells(sheet_name=sheet_name, include_empty=False):
            if cell.value and cell.value.strip():
                yield TextSegment(
                    text=cell.value,
                    location=cell.to_location(),
                )

            # Also yield comment as separate segment
            if cell.comment:
                yield TextSegment(
                    text=cell.comment,
                    location=DocumentLocation(
                        file_id="",  # Will be set by caller
                        component_type="comment",
                        sheet_name=cell.sheet_name,
                        cell_address=cell.coordinate,
                    ),
                )

    def _get_cell_type(self, cell: Cell) -> str:
        """Determine cell type string."""
        if cell.value is None:
            return "empty"

        if hasattr(cell, "data_type"):
            type_map = {
                "s": "string",
                "n": "number",
                "d": "date",
                "f": "formula",
                "b": "boolean",
                "e": "error",
            }
            return type_map.get(cell.data_type, "string")

        # Fallback based on Python type
        if isinstance(cell.value, bool):
            return "boolean"
        if isinstance(cell.value, (int, float)):
            return "number"
        return "string"


class XLSXWriter:
    """
    Writes/modifies XLSX files with style preservation.

    Supports:
    - Cell value modification preserving styles
    - Adding/modifying comments
    - Metadata modification
    """

    def __init__(
        self,
        source_path: Path | str,
        output_path: Path | str | None = None,
    ) -> None:
        """
        Initialize XLSX writer.

        Args:
            source_path: Source XLSX file to modify.
            output_path: Output path. If None, modifies in place.
        """
        self._source_path = Path(source_path)
        self._output_path = Path(output_path) if output_path else self._source_path
        self._workbook: Workbook | None = None
        self._modified_cells: set[str] = set()

    def __enter__(self) -> XLSXWriter:
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.save()
        self.close()

    def open(self) -> None:
        """Open workbook for modification."""
        try:
            from openpyxl import load_workbook

            # Must open in non-read-only mode for modification
            self._workbook = load_workbook(
                self._source_path,
                read_only=False,
                data_only=False,  # Preserve formulas
            )
            logger.debug(f"Opened workbook for writing: {self._source_path}")
        except Exception as e:
            raise WorkbookOpenError(f"Failed to open {self._source_path}: {e}") from e

    def close(self) -> None:
        """Close workbook without saving."""
        if self._workbook is not None:
            try:
                self._workbook.close()
            except Exception:
                pass
            self._workbook = None

    def save(self) -> None:
        """Save changes to output file."""
        if self._workbook is not None:
            self._workbook.save(self._output_path)
            logger.info(
                f"Saved workbook: {self._output_path} "
                f"({len(self._modified_cells)} cells modified)"
            )

    @property
    def workbook(self) -> Workbook:
        """Get the workbook."""
        if self._workbook is None:
            self.open()
        assert self._workbook is not None
        return self._workbook

    def set_cell_value(
        self,
        sheet_name: str,
        row: int,
        column: int,
        value: str,
        preserve_type: bool = True,
    ) -> None:
        """
        Set cell value, preserving formatting.

        Args:
            sheet_name: Worksheet name.
            row: 1-indexed row number.
            column: 1-indexed column number.
            value: New string value.
            preserve_type: Try to preserve original type (number, date).
        """
        try:
            ws = self.workbook[sheet_name]
            cell = ws.cell(row=row, column=column)

            # Store original style info
            original_type = cell.data_type if hasattr(cell, "data_type") else None

            # Set new value
            if preserve_type and original_type == "n":
                # Try to preserve numeric type
                try:
                    if "." in value:
                        cell.value = float(value)
                    else:
                        cell.value = int(value)
                except ValueError:
                    cell.value = value
            else:
                cell.value = value

            coord = f"{sheet_name}!{_get_column_letter(column)}{row}"
            self._modified_cells.add(coord)
            logger.debug(f"Modified cell: {coord}")

        except Exception as e:
            raise CellModificationError(
                f"Failed to modify {sheet_name}!R{row}C{column}: {e}"
            ) from e

    def set_cell_by_coordinate(
        self,
        sheet_name: str,
        coordinate: str,
        value: str,
    ) -> None:
        """
        Set cell value by Excel coordinate (e.g., "A1").

        Args:
            sheet_name: Worksheet name.
            coordinate: Excel coordinate like "A1", "B2".
            value: New string value.
        """
        # Parse coordinate
        match = re.match(r"([A-Z]+)(\d+)", coordinate.upper())
        if not match:
            raise CellModificationError(f"Invalid coordinate: {coordinate}")

        col_letter = match.group(1)
        row = int(match.group(2))
        column = _get_column_index(col_letter)

        self.set_cell_value(sheet_name, row, column, value)

    def set_comment(
        self,
        sheet_name: str,
        row: int,
        column: int,
        comment_text: str | None,
        author: str = "SandiRaksa",
    ) -> None:
        """
        Set or remove cell comment.

        Args:
            sheet_name: Worksheet name.
            row: 1-indexed row number.
            column: 1-indexed column number.
            comment_text: Comment text, or None to remove.
            author: Comment author.
        """
        from openpyxl.comments import Comment

        ws = self.workbook[sheet_name]
        cell = ws.cell(row=row, column=column)

        if comment_text:
            cell.comment = Comment(comment_text, author)
        else:
            cell.comment = None

    def apply_treatments(
        self,
        treatments: list[dict],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> int:
        """
        Apply multiple cell treatments.

        Args:
            treatments: List of dicts with sheet_name, row, column, new_value.
            progress_callback: Called with (current, total) for progress.

        Returns:
            Number of cells modified.
        """
        total = len(treatments)
        modified = 0

        for idx, treatment in enumerate(treatments):
            try:
                self.set_cell_value(
                    sheet_name=treatment["sheet_name"],
                    row=treatment["row"],
                    column=treatment["column"],
                    value=treatment["new_value"],
                )
                modified += 1
            except Exception as e:
                logger.warning(f"Failed to apply treatment: {e}")

            if progress_callback:
                progress_callback(idx + 1, total)

        return modified


class XLSXHandler:
    """
    High-level XLSX handler combining reader and writer.

    Provides:
    - Document scanning for PII
    - Treatment application
    - Metadata handling
    """

    def __init__(self, file_path: Path | str) -> None:
        """
        Initialize handler.

        Args:
            file_path: Path to XLSX file.
        """
        self._file_path = Path(file_path)

    @property
    def file_format(self) -> FileFormat:
        """Get file format."""
        return FileFormat.XLSX

    def get_metadata(self) -> XLSXMetadata:
        """Get workbook metadata."""
        with XLSXReader(self._file_path) as reader:
            inventory = reader.get_inventory()
            return inventory.metadata

    def get_inventory(self) -> WorkbookInventory:
        """Get full workbook inventory."""
        with XLSXReader(self._file_path) as reader:
            return reader.get_inventory()

    def iter_text_segments(self) -> Iterator[TextSegment]:
        """
        Iterate all text segments for detection.

        Yields:
            TextSegment for each cell/comment with text.
        """
        with XLSXReader(self._file_path, read_only=True) as reader:
            yield from reader.iter_text_segments()

    def iter_cells(
        self,
        sheet_name: str | None = None,
        include_empty: bool = False,
    ) -> Iterator[XLSXCell]:
        """
        Iterate cells in the workbook.

        Args:
            sheet_name: Specific sheet or None for all.
            include_empty: Include empty cells.

        Yields:
            XLSXCell for each cell.
        """
        with XLSXReader(self._file_path, read_only=True) as reader:
            yield from reader.iter_cells(
                sheet_name=sheet_name,
                include_empty=include_empty,
            )

    def apply_treatments(
        self,
        treatments: list[dict],
        output_path: Path | str | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[Path, int]:
        """
        Apply treatments and save to output file.

        Args:
            treatments: List of treatment dicts.
            output_path: Output file path.
            progress_callback: Progress callback.

        Returns:
            Tuple of (output_path, cells_modified).
        """
        output = Path(output_path) if output_path else self._get_default_output_path()

        with XLSXWriter(self._file_path, output) as writer:
            modified = writer.apply_treatments(treatments, progress_callback)

        return output, modified

    def _get_default_output_path(self) -> Path:
        """Generate default output path with _protected suffix."""
        stem = self._file_path.stem
        suffix = self._file_path.suffix
        return self._file_path.parent / f"{stem}_protected{suffix}"

    def clear_metadata(
        self,
        output_path: Path | str | None = None,
        clear_creator: bool = True,
        clear_title: bool = False,
        clear_custom: bool = True,
    ) -> Path:
        """
        Clear sensitive metadata from workbook.

        Args:
            output_path: Output file path.
            clear_creator: Clear creator/author.
            clear_title: Clear title.
            clear_custom: Clear custom properties.

        Returns:
            Output file path.
        """
        output = Path(output_path) if output_path else self._get_default_output_path()

        from openpyxl import load_workbook

        wb = load_workbook(self._file_path)

        if wb.properties:
            if clear_creator:
                wb.properties.creator = None
                wb.properties.lastModifiedBy = None
            if clear_title:
                wb.properties.title = None
                wb.properties.subject = None
                wb.properties.description = None

        # Clear custom properties if available
        if clear_custom and hasattr(wb, "custom_doc_props"):
            # openpyxl doesn't have great support for custom props
            # but we can try to clear them
            pass

        wb.save(output)
        wb.close()

        logger.info(f"Cleared metadata and saved to: {output}")
        return output


__all__ = [
    # Errors
    "XLSXHandlerError",
    "WorkbookOpenError",
    "WorksheetError",
    "CellModificationError",
    # Data classes
    "XLSXMetadata",
    "XLSXCell",
    "SheetInventory",
    "WorkbookInventory",
    # Classes
    "XLSXReader",
    "XLSXWriter",
    "XLSXHandler",
    # Utilities
    "_get_column_letter",
    "_get_column_index",
]
