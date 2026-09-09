"""
CSV Document Adapter for Unified Detection Pipeline.

Lightweight adapter that wraps the existing csv_handler to produce
LogicalSegments for the unified detection engine.

Design:
- Each cell becomes a LogicalSegment
- Column headers provide context
- Row-by-row processing for memory efficiency
"""

from __future__ import annotations

import csv
import io
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
    pass

logger = logging.getLogger(__name__)


# Common encoding fallbacks
ENCODING_ATTEMPTS = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]


class CsvDocumentAdapter(BaseDocumentAdapter):
    """
    Document adapter for CSV files.

    Extracts each cell as a LogicalSegment with column header context.
    Uses streaming for memory-efficient processing of large files.
    """

    def __init__(self, file_path: str | Path) -> None:
        """
        Initialize CSV adapter.

        Args:
            file_path: Path to the CSV file
        """
        self._path = Path(file_path)
        self._encoding: str | None = None
        self._delimiter: str | None = None
        self._headers: list[str] = []
        self._content: list[list[str]] = []
        self._loaded = False

    @property
    def format(self) -> DocumentFormat:
        """Document format."""
        return DocumentFormat.CSV

    @property
    def file_path(self) -> Path:
        """Path to the document."""
        return self._path

    def _detect_encoding(self, sample: bytes) -> str:
        """Detect file encoding from sample bytes."""
        # Check for BOM
        if sample.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        if sample.startswith(b"\xff\xfe"):
            return "utf-16-le"
        if sample.startswith(b"\xfe\xff"):
            return "utf-16-be"

        # Try encodings
        for encoding in ENCODING_ATTEMPTS:
            try:
                sample.decode(encoding)
                return encoding
            except (UnicodeDecodeError, LookupError):
                continue

        return "latin-1"  # Fallback

    def _detect_delimiter(self, sample: str) -> str:
        """Detect CSV delimiter from sample."""
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, delimiters=",;\t|")
            return dialect.delimiter
        except csv.Error:
            # Count occurrences
            counts = {
                ",": sample.count(","),
                ";": sample.count(";"),
                "\t": sample.count("\t"),
            }
            return max(counts, key=counts.get)  # type: ignore

    def _load_file(self) -> None:
        """Load and parse the CSV file."""
        if self._loaded:
            return

        # Read raw bytes for encoding detection
        with open(self._path, "rb") as f:
            sample = f.read(8192)

        self._encoding = self._detect_encoding(sample)

        # Read as text
        with open(self._path, "r", encoding=self._encoding, errors="replace") as f:
            content = f.read()

        # Detect delimiter
        self._delimiter = self._detect_delimiter(content[:4096])

        # Parse CSV
        reader = csv.reader(io.StringIO(content), delimiter=self._delimiter)
        rows = list(reader)

        if rows:
            # First row as headers
            self._headers = rows[0]
            self._content = rows
        else:
            self._headers = []
            self._content = []

        self._loaded = True
        logger.debug(
            f"Loaded CSV: {len(self._content)} rows, "
            f"{len(self._headers)} columns, encoding={self._encoding}"
        )

    def extract(self) -> ExtractionResult:
        """
        Extract content as LogicalSegments.

        Returns:
            ExtractionResult with segments for each cell
        """
        self._load_file()

        segments: list[LogicalSegment] = []
        file_id = str(self._path)

        # Skip header row (index 0), process data rows
        for row_idx, row in enumerate(self._content):
            if row_idx == 0:
                continue  # Skip header

            for col_idx, cell_value in enumerate(row):
                # Skip empty cells
                if not cell_value or not cell_value.strip():
                    continue

                # Get column header
                header = self._headers[col_idx] if col_idx < len(self._headers) else None

                # Create segment
                segment = LogicalSegment.for_csv_cell(
                    text=cell_value,
                    file_id=file_id,
                    row=row_idx,
                    column=col_idx,
                    table_headers=self._headers,
                )

                # Add key_label if header suggests PII field
                if header:
                    segment.key_label = header
                    segment.is_value_of_key = True

                segments.append(segment)

        return ExtractionResult(
            segments=segments,
            metadata={
                "encoding": self._encoding,
                "delimiter": self._delimiter,
                "row_count": len(self._content),
                "column_count": len(self._headers),
                "headers": self._headers,
            },
        )

    def extract_streaming(self) -> Iterator[LogicalSegment]:
        """
        Extract segments one at a time for memory efficiency.

        Yields:
            LogicalSegment for each non-empty cell
        """
        # Read raw bytes for encoding detection
        with open(self._path, "rb") as f:
            sample = f.read(8192)

        encoding = self._detect_encoding(sample)

        with open(self._path, "r", encoding=encoding, errors="replace") as f:
            # Detect delimiter from first chunk
            first_chunk = f.read(4096)
            delimiter = self._detect_delimiter(first_chunk)
            f.seek(0)

            reader = csv.reader(f, delimiter=delimiter)
            file_id = str(self._path)
            headers: list[str] = []

            for row_idx, row in enumerate(reader):
                if row_idx == 0:
                    headers = row
                    continue

                for col_idx, cell_value in enumerate(row):
                    if not cell_value or not cell_value.strip():
                        continue

                    header = headers[col_idx] if col_idx < len(headers) else None

                    segment = LogicalSegment.for_csv_cell(
                        text=cell_value,
                        file_id=file_id,
                        row=row_idx,
                        column=col_idx,
                        table_headers=headers,
                    )

                    if header:
                        segment.key_label = header
                        segment.is_value_of_key = True

                    yield segment

    def apply_replacements(
        self, replacements: list[Replacement]
    ) -> ProtectionResult:
        """
        Apply replacements to the CSV file.

        Args:
            replacements: List of replacements to apply

        Returns:
            ProtectionResult with modified content
        """
        self._load_file()

        # Group replacements by cell location
        cell_replacements: dict[tuple[int, int], list[Replacement]] = {}
        for repl in replacements:
            loc = repl.location
            key = (loc.row or 0, loc.column or 0)
            if key not in cell_replacements:
                cell_replacements[key] = []
            cell_replacements[key].append(repl)

        # Apply replacements
        modified_count = 0
        modified_content = [row.copy() for row in self._content]

        for (row_idx, col_idx), repls in cell_replacements.items():
            if row_idx >= len(modified_content):
                continue
            if col_idx >= len(modified_content[row_idx]):
                continue

            cell_value = modified_content[row_idx][col_idx]

            # Sort by start position descending to apply from end
            sorted_repls = sorted(repls, key=lambda r: r.start, reverse=True)

            for repl in sorted_repls:
                cell_value = (
                    cell_value[: repl.start]
                    + repl.new_text
                    + cell_value[repl.end:]
                )

            modified_content[row_idx][col_idx] = cell_value
            modified_count += 1

        # Generate output
        output = io.StringIO()
        writer = csv.writer(output, delimiter=self._delimiter or ",")
        writer.writerows(modified_content)

        return ProtectionResult(
            content=output.getvalue().encode(self._encoding or "utf-8"),
            modified_count=modified_count,
            format=DocumentFormat.CSV,
        )

    def validate(self) -> list[str]:
        """
        Validate the CSV file.

        Returns:
            List of validation errors (empty if valid)
        """
        errors: list[str] = []

        if not self._path.exists():
            errors.append(f"File not found: {self._path}")
            return errors

        if self._path.suffix.lower() not in (".csv", ".tsv", ".txt"):
            errors.append(f"Unexpected file extension: {self._path.suffix}")

        try:
            self._load_file()
        except Exception as e:
            errors.append(f"Failed to parse CSV: {e}")

        return errors


__all__ = [
    "CsvDocumentAdapter",
    "ENCODING_ATTEMPTS",
]
