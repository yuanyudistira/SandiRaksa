"""
CSV Document Handler.

Provides streaming CSV processing with:
- Encoding detection (UTF-8, Latin-1, Windows-1252, etc.)
- Delimiter auto-detection
- Memory-efficient row-by-row processing
- Header preservation
- BOM handling
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterator

from sandiraksa.detection.context import DetectionResult, TextSegment
from sandiraksa.domain.finding import DocumentLocation
from sandiraksa.domain.file_record import FileFormat

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class CSVHandlerError(Exception):
    """Base exception for CSV handler errors."""

    pass


class EncodingError(CSVHandlerError):
    """Failed to detect or decode file encoding."""

    pass


class DelimiterError(CSVHandlerError):
    """Failed to detect delimiter."""

    pass


@dataclass
class CSVMetadata:
    """Metadata about a CSV file."""

    encoding: str
    delimiter: str
    has_header: bool
    row_count: int
    column_count: int
    file_size: int
    headers: list[str] = field(default_factory=list)
    quotechar: str = '"'
    has_bom: bool = False


@dataclass
class CSVCell:
    """Represents a single cell in a CSV file."""

    row: int  # 0-indexed
    column: int  # 0-indexed
    column_name: str | None
    value: str
    raw_value: str  # Original value before any processing

    def to_location(self, file_id: str = "") -> DocumentLocation:
        """Convert to a DocumentLocation."""
        return DocumentLocation(
            file_id=file_id,
            component_type="cell",
            cell_address=f"R{self.row + 1}C{self.column + 1}",
        )


class EncodingDetector:
    """Detects file encoding using multiple strategies."""

    # Common encodings to try, in order of preference
    ENCODINGS: list[str] = [
        "utf-8-sig",  # UTF-8 with BOM
        "utf-8",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
        "cp1252",  # Windows Western European
        "iso-8859-1",  # Latin-1
        "iso-8859-15",  # Latin-9
        "cp1250",  # Windows Central European
    ]

    @classmethod
    def detect(cls, file_path: Path, sample_size: int = 65536) -> str:
        """
        Detect the encoding of a file.

        Args:
            file_path: Path to the file.
            sample_size: Number of bytes to read for detection.

        Returns:
            Detected encoding name.

        Raises:
            EncodingError: If encoding cannot be detected.
        """
        with open(file_path, "rb") as f:
            sample = f.read(sample_size)

        # Check for BOM first
        bom_encoding = cls._check_bom(sample)
        if bom_encoding:
            return bom_encoding

        # Try chardet if available
        try:
            import chardet

            result = chardet.detect(sample)
            if result["encoding"] and result["confidence"] > 0.7:
                encoding = result["encoding"].lower()
                # Map some common variations
                if encoding == "ascii":
                    encoding = "utf-8"
                return encoding
        except ImportError:
            pass

        # Fallback: try each encoding
        for encoding in cls.ENCODINGS:
            try:
                sample.decode(encoding)
                return encoding
            except (UnicodeDecodeError, LookupError):
                continue

        # Last resort
        logger.warning(f"Could not detect encoding for {file_path}, using utf-8")
        return "utf-8"

    @classmethod
    def _check_bom(cls, data: bytes) -> str | None:
        """Check for Byte Order Mark."""
        if data.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        if data.startswith(b"\xff\xfe\x00\x00"):
            return "utf-32-le"
        if data.startswith(b"\x00\x00\xfe\xff"):
            return "utf-32-be"
        if data.startswith(b"\xff\xfe"):
            return "utf-16-le"
        if data.startswith(b"\xfe\xff"):
            return "utf-16-be"
        return None


class DelimiterDetector:
    """Detects CSV delimiter."""

    DELIMITERS: list[str] = [",", ";", "\t", "|"]

    @classmethod
    def detect(cls, sample: str, max_lines: int = 10) -> str:
        """
        Detect the delimiter used in CSV content.

        Args:
            sample: Sample of CSV content.
            max_lines: Maximum lines to analyze.

        Returns:
            Detected delimiter character.
        """
        # Try Python's csv.Sniffer first
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, delimiters="".join(cls.DELIMITERS))
            return dialect.delimiter
        except csv.Error:
            pass

        # Fallback: count occurrences per line
        lines = sample.split("\n")[:max_lines]

        delimiter_scores: dict[str, float] = {}

        for delimiter in cls.DELIMITERS:
            counts = [line.count(delimiter) for line in lines if line.strip()]
            if not counts:
                delimiter_scores[delimiter] = 0
                continue

            # Score based on consistency (low variance) and frequency
            avg = sum(counts) / len(counts)
            variance = sum((c - avg) ** 2 for c in counts) / len(counts)

            # Higher score = more likely delimiter
            if avg > 0:
                delimiter_scores[delimiter] = avg / (1 + variance)
            else:
                delimiter_scores[delimiter] = 0

        # Return delimiter with highest score
        best = max(delimiter_scores, key=lambda d: delimiter_scores[d])
        return best if delimiter_scores[best] > 0 else ","


class CSVReader:
    """
    Memory-efficient CSV reader with streaming support.

    Reads CSV files row by row without loading entire file into memory.
    """

    # Maximum line length to prevent memory issues
    MAX_LINE_LENGTH = 10 * 1024 * 1024  # 10 MB

    def __init__(
        self,
        file_path: Path,
        encoding: str | None = None,
        delimiter: str | None = None,
        has_header: bool = True,
    ) -> None:
        """
        Initialize CSV reader.

        Args:
            file_path: Path to CSV file.
            encoding: File encoding. If None, auto-detected.
            delimiter: CSV delimiter. If None, auto-detected.
            has_header: Whether first row is header.
        """
        self.file_path = Path(file_path)
        self._encoding = encoding
        self._delimiter = delimiter
        self._has_header = has_header
        self._headers: list[str] = []
        self._metadata: CSVMetadata | None = None

    def detect_metadata(self) -> CSVMetadata:
        """
        Detect CSV file metadata.

        Returns:
            CSVMetadata with encoding, delimiter, etc.
        """
        if self._metadata:
            return self._metadata

        # Detect encoding
        encoding = self._encoding or EncodingDetector.detect(self.file_path)
        has_bom = encoding.endswith("-sig") or encoding.startswith("utf-16")

        # Read sample for delimiter detection
        with open(self.file_path, "r", encoding=encoding, errors="replace") as f:
            sample = f.read(8192)

        # Detect delimiter
        delimiter = self._delimiter or DelimiterDetector.detect(sample)

        # Count rows and detect header
        row_count = 0
        column_count = 0
        headers: list[str] = []

        with open(self.file_path, "r", encoding=encoding, errors="replace") as f:
            reader = csv.reader(f, delimiter=delimiter)

            for i, row in enumerate(reader):
                if i == 0:
                    column_count = len(row)
                    if self._has_header:
                        headers = row
                row_count += 1

        self._metadata = CSVMetadata(
            encoding=encoding,
            delimiter=delimiter,
            has_header=self._has_header and bool(headers),
            row_count=row_count,
            column_count=column_count,
            file_size=self.file_path.stat().st_size,
            headers=headers,
            has_bom=has_bom,
        )

        return self._metadata

    def iter_cells(
        self,
        skip_header: bool = True,
        columns: list[int] | None = None,
    ) -> Iterator[CSVCell]:
        """
        Iterate over cells in the CSV file.

        Args:
            skip_header: Whether to skip header row.
            columns: List of column indices to include. None = all.

        Yields:
            CSVCell objects.
        """
        metadata = self.detect_metadata()
        self._headers = metadata.headers

        with open(
            self.file_path, "r", encoding=metadata.encoding, errors="replace"
        ) as f:
            reader = csv.reader(f, delimiter=metadata.delimiter)

            for row_idx, row in enumerate(reader):
                # Skip header if requested
                if row_idx == 0 and skip_header and metadata.has_header:
                    continue

                # Adjust row index if we skipped header
                effective_row = row_idx if not (skip_header and metadata.has_header) else row_idx - 1

                for col_idx, value in enumerate(row):
                    # Filter columns if specified
                    if columns is not None and col_idx not in columns:
                        continue

                    # Get column name
                    col_name = None
                    if col_idx < len(self._headers):
                        col_name = self._headers[col_idx]

                    yield CSVCell(
                        row=effective_row,
                        column=col_idx,
                        column_name=col_name,
                        value=value,
                        raw_value=value,
                    )

    def iter_rows(
        self,
        skip_header: bool = True,
    ) -> Iterator[tuple[int, list[str]]]:
        """
        Iterate over rows in the CSV file.

        Args:
            skip_header: Whether to skip header row.

        Yields:
            Tuples of (row_index, row_values).
        """
        metadata = self.detect_metadata()

        with open(
            self.file_path, "r", encoding=metadata.encoding, errors="replace"
        ) as f:
            reader = csv.reader(f, delimiter=metadata.delimiter)

            for row_idx, row in enumerate(reader):
                if row_idx == 0 and skip_header and metadata.has_header:
                    continue

                effective_row = row_idx if not (skip_header and metadata.has_header) else row_idx - 1
                yield effective_row, row


class CSVWriter:
    """
    CSV writer that preserves original formatting where possible.
    """

    def __init__(
        self,
        output_path: Path,
        encoding: str = "utf-8",
        delimiter: str = ",",
        quotechar: str = '"',
        write_bom: bool = False,
    ) -> None:
        """
        Initialize CSV writer.

        Args:
            output_path: Path to output file.
            encoding: Output encoding.
            delimiter: CSV delimiter.
            quotechar: Quote character.
            write_bom: Whether to write UTF-8 BOM.
        """
        self.output_path = Path(output_path)
        self.encoding = encoding
        self.delimiter = delimiter
        self.quotechar = quotechar
        self.write_bom = write_bom

    def write_from_reader(
        self,
        reader: CSVReader,
        transform: Callable[[int, int, str], str] | None = None,
    ) -> int:
        """
        Write CSV with optional transformation.

        Args:
            reader: Source CSVReader.
            transform: Optional function(row, col, value) -> new_value.

        Returns:
            Number of rows written.
        """
        metadata = reader.detect_metadata()

        # Determine encoding
        encoding = self.encoding
        if self.write_bom and encoding == "utf-8":
            encoding = "utf-8-sig"

        rows_written = 0

        with open(self.output_path, "w", encoding=encoding, newline="") as f:
            writer = csv.writer(
                f,
                delimiter=self.delimiter,
                quotechar=self.quotechar,
                quoting=csv.QUOTE_MINIMAL,
            )

            # Write header if exists
            if metadata.has_header:
                writer.writerow(metadata.headers)
                rows_written += 1

            # Write data rows
            with open(
                reader.file_path, "r", encoding=metadata.encoding, errors="replace"
            ) as src:
                src_reader = csv.reader(src, delimiter=metadata.delimiter)

                for row_idx, row in enumerate(src_reader):
                    # Skip header in source
                    if row_idx == 0 and metadata.has_header:
                        continue

                    # Transform values if function provided
                    if transform:
                        row = [
                            transform(row_idx, col_idx, val)
                            for col_idx, val in enumerate(row)
                        ]

                    writer.writerow(row)
                    rows_written += 1

        return rows_written


class CSVHandler:
    """
    High-level CSV document handler.

    Provides scanning and treatment operations for CSV files.
    """

    def __init__(self) -> None:
        self._reader: CSVReader | None = None
        self._file_path: Path | None = None

    def open(
        self,
        file_path: Path | str,
        encoding: str | None = None,
        delimiter: str | None = None,
        has_header: bool = True,
    ) -> CSVMetadata:
        """
        Open a CSV file for processing.

        Args:
            file_path: Path to CSV file.
            encoding: File encoding. If None, auto-detected.
            delimiter: CSV delimiter. If None, auto-detected.
            has_header: Whether first row is header.

        Returns:
            CSVMetadata with file information.
        """
        self._file_path = Path(file_path)
        self._reader = CSVReader(
            self._file_path,
            encoding=encoding,
            delimiter=delimiter,
            has_header=has_header,
        )
        return self._reader.detect_metadata()

    def get_text_segments(
        self,
        skip_header: bool = True,
        batch_size: int = 1000,
    ) -> Iterator[list[TextSegment]]:
        """
        Get text segments for detection in batches.

        Yields batches of TextSegment objects for memory-efficient processing.

        Args:
            skip_header: Whether to skip header row.
            batch_size: Number of cells per batch.

        Yields:
            Lists of TextSegment objects.
        """
        if not self._reader:
            raise CSVHandlerError("No file opened. Call open() first.")

        batch: list[TextSegment] = []

        for cell in self._reader.iter_cells(skip_header=skip_header):
            # Skip empty cells
            if not cell.value or not cell.value.strip():
                continue

            segment = TextSegment(
                text=cell.value,
                location=cell.to_location(),
                parent_offset=0,
            )
            batch.append(segment)

            if len(batch) >= batch_size:
                yield batch
                batch = []

        # Yield remaining
        if batch:
            yield batch

    def create_treated_file(
        self,
        output_path: Path | str,
        treatments: dict[tuple[int, int], str],
        preserve_encoding: bool = True,
    ) -> Path:
        """
        Create a treated copy of the CSV file.

        Args:
            output_path: Path for the output file.
            treatments: Dict mapping (row, col) to replacement value.
            preserve_encoding: Whether to preserve original encoding.

        Returns:
            Path to the created file.
        """
        if not self._reader:
            raise CSVHandlerError("No file opened. Call open() first.")

        metadata = self._reader.detect_metadata()
        output = Path(output_path)

        # Determine encoding
        encoding = metadata.encoding if preserve_encoding else "utf-8"
        write_bom = metadata.has_bom

        writer = CSVWriter(
            output,
            encoding=encoding,
            delimiter=metadata.delimiter,
            write_bom=write_bom,
        )

        def transform(row: int, col: int, value: str) -> str:
            # Adjust row for header offset
            effective_row = row - 1 if metadata.has_header else row
            key = (effective_row, col)
            return treatments.get(key, value)

        writer.write_from_reader(self._reader, transform)
        return output

    def close(self) -> None:
        """Close the handler and release resources."""
        self._reader = None
        self._file_path = None

    @staticmethod
    def is_csv_file(file_path: Path | str) -> bool:
        """Check if a file is a CSV file."""
        path = Path(file_path)
        return path.suffix.lower() in {".csv", ".tsv", ".txt"}

    @staticmethod
    def get_format() -> FileFormat:
        """Get the file format this handler supports."""
        return FileFormat.CSV
