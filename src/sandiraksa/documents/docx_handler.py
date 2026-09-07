"""
DOCX Document Handler.

Provides Word document processing with:
- Paragraph and run-level text extraction
- Text across runs reconstruction
- Tables, headers/footers, comments handling
- Hyperlinks extraction
- Style-preserving modifications
- OOXML fallback for unsupported parts
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterator
from zipfile import ZipFile

from sandiraksa.detection.context import TextSegment
from sandiraksa.domain.finding import DocumentLocation
from sandiraksa.domain.file_record import FileFormat

if TYPE_CHECKING:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    from docx.text.run import Run

logger = logging.getLogger(__name__)


class DOCXHandlerError(Exception):
    """Base exception for DOCX handler errors."""

    pass


class DocumentOpenError(DOCXHandlerError):
    """Failed to open document."""

    pass


class DocumentModificationError(DOCXHandlerError):
    """Failed to modify document."""

    pass


@dataclass
class DOCXMetadata:
    """Metadata about a DOCX file."""

    file_path: Path
    file_size: int
    paragraph_count: int
    table_count: int
    has_headers: bool
    has_footers: bool
    has_comments: bool
    has_hyperlinks: bool
    has_footnotes: bool
    has_endnotes: bool
    created: str | None = None
    modified: str | None = None
    creator: str | None = None
    title: str | None = None
    subject: str | None = None


@dataclass
class TextRun:
    """Represents a run of text within a paragraph."""

    text: str
    run_index: int
    start_offset: int  # Offset within paragraph
    end_offset: int
    is_bold: bool = False
    is_italic: bool = False
    is_underline: bool = False
    font_name: str | None = None
    font_size: float | None = None
    hyperlink: str | None = None


@dataclass
class ParagraphInfo:
    """Information about a paragraph."""

    paragraph_index: int
    text: str
    runs: list[TextRun]
    style_name: str | None = None
    component_type: str = "paragraph"  # paragraph, header, footer, cell, comment

    # Context information
    section_index: int = 0
    table_index: int | None = None
    row_index: int | None = None
    cell_index: int | None = None

    def to_location(self, file_id: str = "") -> DocumentLocation:
        """Convert to DocumentLocation."""
        return DocumentLocation(
            file_id=file_id,
            component_type=self.component_type,
            paragraph_index=self.paragraph_index,
        )

    @property
    def run_indices(self) -> list[int]:
        """Get list of run indices."""
        return [r.run_index for r in self.runs]


@dataclass
class DocumentInventory:
    """Complete inventory of a DOCX document."""

    file_path: Path
    metadata: DOCXMetadata
    paragraph_count: int
    table_count: int
    header_count: int
    footer_count: int
    comment_count: int
    total_text_length: int


@dataclass
class TextSpan:
    """A span of text that may cross multiple runs."""

    text: str
    paragraph_index: int
    start_offset: int  # Offset within paragraph text
    end_offset: int
    run_spans: list[tuple[int, int, int]]  # (run_index, start_in_run, end_in_run)

    def to_location(self, file_id: str = "") -> DocumentLocation:
        """Convert to DocumentLocation."""
        return DocumentLocation(
            file_id=file_id,
            component_type="paragraph",
            paragraph_index=self.paragraph_index,
            start_offset=self.start_offset,
            end_offset=self.end_offset,
            run_indices=[rs[0] for rs in self.run_spans],
        )


class DOCXReader:
    """
    Reads DOCX files with comprehensive text extraction.

    Handles:
    - Body paragraphs
    - Tables
    - Headers and footers
    - Comments
    - Footnotes and endnotes
    - Hyperlinks
    """

    def __init__(self, file_path: Path | str) -> None:
        """
        Initialize DOCX reader.

        Args:
            file_path: Path to DOCX file.
        """
        self._file_path = Path(file_path)
        self._document: Document | None = None
        self._inventory: DocumentInventory | None = None

    def __enter__(self) -> DOCXReader:
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def open(self) -> None:
        """Open the document."""
        try:
            from docx import Document

            self._document = Document(self._file_path)
            logger.debug(f"Opened document: {self._file_path}")
        except Exception as e:
            raise DocumentOpenError(f"Failed to open {self._file_path}: {e}") from e

    def close(self) -> None:
        """Close the document (no-op for python-docx, but good practice)."""
        self._document = None

    @property
    def document(self) -> Document:
        """Get the document, opening if needed."""
        if self._document is None:
            self.open()
        assert self._document is not None
        return self._document

    def get_inventory(self) -> DocumentInventory:
        """
        Build inventory of the document.

        Returns:
            DocumentInventory with document details.
        """
        if self._inventory is not None:
            return self._inventory

        doc = self.document
        total_text = 0

        # Count paragraphs
        para_count = len(doc.paragraphs)
        for para in doc.paragraphs:
            total_text += len(para.text)

        # Count tables
        table_count = len(doc.tables)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        total_text += len(para.text)

        # Check headers/footers
        has_headers = False
        has_footers = False
        header_count = 0
        footer_count = 0

        for section in doc.sections:
            if section.header and section.header.paragraphs:
                has_headers = True
                header_count += len(section.header.paragraphs)
                for para in section.header.paragraphs:
                    total_text += len(para.text)
            if section.footer and section.footer.paragraphs:
                has_footers = True
                footer_count += len(section.footer.paragraphs)
                for para in section.footer.paragraphs:
                    total_text += len(para.text)

        # Check comments (requires OOXML access)
        has_comments = self._check_has_comments()
        comment_count = self._count_comments() if has_comments else 0

        # Build metadata
        core_props = doc.core_properties
        metadata = DOCXMetadata(
            file_path=self._file_path,
            file_size=self._file_path.stat().st_size,
            paragraph_count=para_count,
            table_count=table_count,
            has_headers=has_headers,
            has_footers=has_footers,
            has_comments=has_comments,
            has_hyperlinks=self._check_has_hyperlinks(),
            has_footnotes=self._check_has_footnotes(),
            has_endnotes=self._check_has_endnotes(),
            created=str(core_props.created) if core_props.created else None,
            modified=str(core_props.modified) if core_props.modified else None,
            creator=core_props.author,
            title=core_props.title,
            subject=core_props.subject,
        )

        self._inventory = DocumentInventory(
            file_path=self._file_path,
            metadata=metadata,
            paragraph_count=para_count,
            table_count=table_count,
            header_count=header_count,
            footer_count=footer_count,
            comment_count=comment_count,
            total_text_length=total_text,
        )

        return self._inventory

    def _check_has_comments(self) -> bool:
        """Check if document has comments."""
        try:
            with ZipFile(self._file_path, "r") as zf:
                return "word/comments.xml" in zf.namelist()
        except Exception:
            return False

    def _count_comments(self) -> int:
        """Count comments in document."""
        try:
            with ZipFile(self._file_path, "r") as zf:
                if "word/comments.xml" not in zf.namelist():
                    return 0
                content = zf.read("word/comments.xml").decode("utf-8")
                # Count <w:comment> elements
                return content.count("<w:comment ")
        except Exception:
            return 0

    def _check_has_hyperlinks(self) -> bool:
        """Check if document has hyperlinks."""
        for para in self.document.paragraphs:
            if para._element.xpath(".//w:hyperlink"):
                return True
        return False

    def _check_has_footnotes(self) -> bool:
        """Check if document has footnotes."""
        try:
            with ZipFile(self._file_path, "r") as zf:
                return "word/footnotes.xml" in zf.namelist()
        except Exception:
            return False

    def _check_has_endnotes(self) -> bool:
        """Check if document has endnotes."""
        try:
            with ZipFile(self._file_path, "r") as zf:
                return "word/endnotes.xml" in zf.namelist()
        except Exception:
            return False

    def iter_paragraphs(
        self,
        include_tables: bool = True,
        include_headers: bool = True,
        include_footers: bool = True,
    ) -> Iterator[ParagraphInfo]:
        """
        Iterate over all paragraphs in document.

        Args:
            include_tables: Include table cell paragraphs.
            include_headers: Include header paragraphs.
            include_footers: Include footer paragraphs.

        Yields:
            ParagraphInfo for each paragraph.
        """
        doc = self.document
        para_index = 0

        # Body paragraphs
        for para in doc.paragraphs:
            yield self._extract_paragraph_info(para, para_index, "paragraph")
            para_index += 1

        # Table cells
        if include_tables:
            for table_idx, table in enumerate(doc.tables):
                for row_idx, row in enumerate(table.rows):
                    for cell_idx, cell in enumerate(row.cells):
                        for para in cell.paragraphs:
                            info = self._extract_paragraph_info(para, para_index, "cell")
                            info.table_index = table_idx
                            info.row_index = row_idx
                            info.cell_index = cell_idx
                            yield info
                            para_index += 1

        # Headers and footers
        for section_idx, section in enumerate(doc.sections):
            if include_headers and section.header:
                for para in section.header.paragraphs:
                    info = self._extract_paragraph_info(para, para_index, "header")
                    info.section_index = section_idx
                    yield info
                    para_index += 1

            if include_footers and section.footer:
                for para in section.footer.paragraphs:
                    info = self._extract_paragraph_info(para, para_index, "footer")
                    info.section_index = section_idx
                    yield info
                    para_index += 1

    def _extract_paragraph_info(
        self,
        para: Paragraph,
        para_index: int,
        component_type: str,
    ) -> ParagraphInfo:
        """Extract information from a paragraph."""
        runs: list[TextRun] = []
        offset = 0

        for run_idx, run in enumerate(para.runs):
            text = run.text
            if text:
                runs.append(
                    TextRun(
                        text=text,
                        run_index=run_idx,
                        start_offset=offset,
                        end_offset=offset + len(text),
                        is_bold=run.bold or False,
                        is_italic=run.italic or False,
                        is_underline=run.underline or False,
                        font_name=run.font.name if run.font else None,
                        font_size=run.font.size.pt if run.font and run.font.size else None,
                    )
                )
                offset += len(text)

        return ParagraphInfo(
            paragraph_index=para_index,
            text=para.text,
            runs=runs,
            style_name=para.style.name if para.style else None,
            component_type=component_type,
        )

    def iter_text_segments(self) -> Iterator[TextSegment]:
        """
        Iterate all text as TextSegments for detection.

        Yields:
            TextSegment for each paragraph with text.
        """
        for para_info in self.iter_paragraphs():
            if para_info.text and para_info.text.strip():
                yield TextSegment(
                    text=para_info.text,
                    location=para_info.to_location(),
                )

        # Also extract comments
        for comment in self.iter_comments():
            if comment["text"] and comment["text"].strip():
                yield TextSegment(
                    text=comment["text"],
                    location=DocumentLocation(
                        file_id="",
                        component_type="comment",
                    ),
                )

    def iter_comments(self) -> Iterator[dict[str, Any]]:
        """
        Iterate over comments in the document.

        Yields:
            Dict with comment_id, author, text, date.
        """
        try:
            with ZipFile(self._file_path, "r") as zf:
                if "word/comments.xml" not in zf.namelist():
                    return

                from xml.etree import ElementTree as ET

                content = zf.read("word/comments.xml")
                root = ET.fromstring(content)

                # OOXML namespaces
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

                for comment in root.findall(".//w:comment", ns):
                    comment_id = comment.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id")
                    author = comment.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}author")
                    date = comment.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}date")

                    # Extract text from all <w:t> elements
                    text_parts = []
                    for t_elem in comment.findall(".//w:t", ns):
                        if t_elem.text:
                            text_parts.append(t_elem.text)

                    yield {
                        "comment_id": comment_id,
                        "author": author,
                        "date": date,
                        "text": "".join(text_parts),
                    }

        except Exception as e:
            logger.warning(f"Failed to read comments: {e}")

    def map_offset_to_runs(
        self,
        para_info: ParagraphInfo,
        start: int,
        end: int,
    ) -> list[tuple[int, int, int]]:
        """
        Map text offset to run indices and positions.

        Args:
            para_info: Paragraph information.
            start: Start offset in paragraph text.
            end: End offset in paragraph text.

        Returns:
            List of (run_index, start_in_run, end_in_run) tuples.
        """
        result = []

        for run in para_info.runs:
            # Check if this run overlaps with the span
            if run.end_offset <= start:
                continue  # Run is before span
            if run.start_offset >= end:
                break  # Run is after span

            # Calculate overlap
            overlap_start = max(start, run.start_offset)
            overlap_end = min(end, run.end_offset)

            # Convert to run-relative offsets
            run_start = overlap_start - run.start_offset
            run_end = overlap_end - run.start_offset

            result.append((run.run_index, run_start, run_end))

        return result


class DOCXWriter:
    """
    Modifies DOCX files with style preservation.

    Handles run-level modifications to preserve formatting.
    """

    def __init__(
        self,
        source_path: Path | str,
        output_path: Path | str | None = None,
    ) -> None:
        """
        Initialize DOCX writer.

        Args:
            source_path: Source DOCX file to modify.
            output_path: Output path. If None, modifies in place.
        """
        self._source_path = Path(source_path)
        self._output_path = Path(output_path) if output_path else self._source_path
        self._document: Document | None = None
        self._modifications: int = 0

    def __enter__(self) -> DOCXWriter:
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.save()

    def open(self) -> None:
        """Open document for modification."""
        try:
            from docx import Document

            self._document = Document(self._source_path)
            logger.debug(f"Opened document for writing: {self._source_path}")
        except Exception as e:
            raise DocumentOpenError(f"Failed to open {self._source_path}: {e}") from e

    def save(self) -> None:
        """Save changes to output file."""
        if self._document is not None:
            self._document.save(self._output_path)
            logger.info(
                f"Saved document: {self._output_path} "
                f"({self._modifications} modifications)"
            )

    @property
    def document(self) -> Document:
        """Get the document."""
        if self._document is None:
            self.open()
        assert self._document is not None
        return self._document

    def replace_in_paragraph(
        self,
        paragraph_index: int,
        old_text: str,
        new_text: str,
        component_type: str = "paragraph",
        table_index: int | None = None,
        row_index: int | None = None,
        cell_index: int | None = None,
    ) -> bool:
        """
        Replace text in a specific paragraph.

        Args:
            paragraph_index: Index of paragraph.
            old_text: Text to find and replace.
            new_text: Replacement text.
            component_type: Type of component (paragraph, cell, header, footer).
            table_index: Table index if in table.
            row_index: Row index if in table.
            cell_index: Cell index if in table.

        Returns:
            True if replacement was made.
        """
        para = self._get_paragraph(
            paragraph_index,
            component_type,
            table_index,
            row_index,
            cell_index,
        )

        if para is None:
            return False

        # Try simple replacement first
        if old_text in para.text:
            # Find which runs contain the text
            full_text = ""
            run_positions = []

            for run_idx, run in enumerate(para.runs):
                start = len(full_text)
                full_text += run.text
                run_positions.append((run_idx, start, len(full_text)))

            # Find the old text position
            start_pos = full_text.find(old_text)
            if start_pos == -1:
                return False

            end_pos = start_pos + len(old_text)

            # Perform the replacement across runs
            return self._replace_across_runs(
                para, run_positions, start_pos, end_pos, new_text
            )

        return False

    def _get_paragraph(
        self,
        paragraph_index: int,
        component_type: str,
        table_index: int | None,
        row_index: int | None,
        cell_index: int | None,
    ) -> Paragraph | None:
        """Get paragraph by location."""
        doc = self.document

        if component_type == "paragraph":
            if paragraph_index < len(doc.paragraphs):
                return doc.paragraphs[paragraph_index]

        elif component_type == "cell":
            if table_index is not None and row_index is not None and cell_index is not None:
                if table_index < len(doc.tables):
                    table = doc.tables[table_index]
                    if row_index < len(table.rows):
                        row = table.rows[row_index]
                        if cell_index < len(row.cells):
                            cell = row.cells[cell_index]
                            # Find the paragraph within cell
                            for para in cell.paragraphs:
                                if paragraph_index == 0:
                                    return para
                                paragraph_index -= 1

        elif component_type in ("header", "footer"):
            for section in doc.sections:
                container = section.header if component_type == "header" else section.footer
                if container:
                    for para in container.paragraphs:
                        if paragraph_index == 0:
                            return para
                        paragraph_index -= 1

        return None

    def _replace_across_runs(
        self,
        para: Paragraph,
        run_positions: list[tuple[int, int, int]],
        start_pos: int,
        end_pos: int,
        new_text: str,
    ) -> bool:
        """
        Replace text that may span multiple runs.

        Preserves formatting of the first run.
        """
        runs = para.runs

        # Find affected runs
        affected_runs = []
        for run_idx, run_start, run_end in run_positions:
            if run_end <= start_pos:
                continue
            if run_start >= end_pos:
                break
            affected_runs.append((run_idx, run_start, run_end))

        if not affected_runs:
            return False

        # Handle single run case
        if len(affected_runs) == 1:
            run_idx, run_start, run_end = affected_runs[0]
            run = runs[run_idx]
            local_start = start_pos - run_start
            local_end = end_pos - run_start
            run.text = run.text[:local_start] + new_text + run.text[local_end:]
            self._modifications += 1
            return True

        # Handle multi-run case
        first_run_idx, first_run_start, first_run_end = affected_runs[0]
        last_run_idx, last_run_start, last_run_end = affected_runs[-1]

        # Modify first run: keep text before match + new text
        first_run = runs[first_run_idx]
        local_start = start_pos - first_run_start
        first_run.text = first_run.text[:local_start] + new_text

        # Clear middle runs
        for run_idx, _, _ in affected_runs[1:-1]:
            runs[run_idx].text = ""

        # Modify last run: keep text after match
        last_run = runs[last_run_idx]
        local_end = end_pos - last_run_start
        last_run.text = last_run.text[local_end:]

        self._modifications += 1
        return True

    def apply_treatments(
        self,
        treatments: list[dict],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> int:
        """
        Apply multiple text treatments.

        Args:
            treatments: List of treatment dicts with:
                - paragraph_index
                - old_text
                - new_text
                - component_type (optional)
                - table_index, row_index, cell_index (optional)
            progress_callback: Called with (current, total).

        Returns:
            Number of successful modifications.
        """
        total = len(treatments)
        modified = 0

        for idx, treatment in enumerate(treatments):
            try:
                success = self.replace_in_paragraph(
                    paragraph_index=treatment.get("paragraph_index", 0),
                    old_text=treatment["old_text"],
                    new_text=treatment["new_text"],
                    component_type=treatment.get("component_type", "paragraph"),
                    table_index=treatment.get("table_index"),
                    row_index=treatment.get("row_index"),
                    cell_index=treatment.get("cell_index"),
                )
                if success:
                    modified += 1
            except Exception as e:
                logger.warning(f"Failed to apply treatment: {e}")

            if progress_callback:
                progress_callback(idx + 1, total)

        return modified


class DOCXHandler:
    """
    High-level DOCX handler combining reader and writer.

    Provides:
    - Document scanning for PII
    - Treatment application
    - Metadata handling
    """

    def __init__(self, file_path: Path | str) -> None:
        """
        Initialize handler.

        Args:
            file_path: Path to DOCX file.
        """
        self._file_path = Path(file_path)

    @property
    def file_format(self) -> FileFormat:
        """Get file format."""
        return FileFormat.DOCX

    def get_metadata(self) -> DOCXMetadata:
        """Get document metadata."""
        with DOCXReader(self._file_path) as reader:
            inventory = reader.get_inventory()
            return inventory.metadata

    def get_inventory(self) -> DocumentInventory:
        """Get full document inventory."""
        with DOCXReader(self._file_path) as reader:
            return reader.get_inventory()

    def iter_text_segments(self) -> Iterator[TextSegment]:
        """
        Iterate all text segments for detection.

        Yields:
            TextSegment for each paragraph/comment with text.
        """
        with DOCXReader(self._file_path) as reader:
            yield from reader.iter_text_segments()

    def iter_paragraphs(
        self,
        include_tables: bool = True,
        include_headers: bool = True,
        include_footers: bool = True,
    ) -> Iterator[ParagraphInfo]:
        """
        Iterate paragraphs in the document.

        Yields:
            ParagraphInfo for each paragraph.
        """
        with DOCXReader(self._file_path) as reader:
            yield from reader.iter_paragraphs(
                include_tables=include_tables,
                include_headers=include_headers,
                include_footers=include_footers,
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
            Tuple of (output_path, modifications_count).
        """
        output = Path(output_path) if output_path else self._get_default_output_path()

        with DOCXWriter(self._file_path, output) as writer:
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
        clear_author: bool = True,
        clear_title: bool = False,
        clear_comments: bool = True,
    ) -> Path:
        """
        Clear sensitive metadata from document.

        Args:
            output_path: Output file path.
            clear_author: Clear author information.
            clear_title: Clear title/subject.
            clear_comments: Remove all comments.

        Returns:
            Output file path.
        """
        output = Path(output_path) if output_path else self._get_default_output_path()

        from docx import Document

        doc = Document(self._file_path)

        if clear_author:
            doc.core_properties.author = None
            doc.core_properties.last_modified_by = None

        if clear_title:
            doc.core_properties.title = None
            doc.core_properties.subject = None
            doc.core_properties.keywords = None

        doc.save(output)

        # Remove comments if requested (requires OOXML manipulation)
        if clear_comments:
            self._remove_comments_from_file(output)

        logger.info(f"Cleared metadata and saved to: {output}")
        return output

    def _remove_comments_from_file(self, file_path: Path) -> None:
        """Remove comments by modifying the OOXML package."""
        import shutil
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Extract DOCX
            with ZipFile(file_path, "r") as zf:
                zf.extractall(tmpdir_path)

            # Remove comments.xml if exists
            comments_file = tmpdir_path / "word" / "comments.xml"
            if comments_file.exists():
                comments_file.unlink()

            # Update content types and relationships
            # (simplified - full implementation would update [Content_Types].xml)

            # Repack DOCX
            with ZipFile(file_path, "w") as zf:
                for file in tmpdir_path.rglob("*"):
                    if file.is_file():
                        arcname = file.relative_to(tmpdir_path)
                        zf.write(file, arcname)


__all__ = [
    # Errors
    "DOCXHandlerError",
    "DocumentOpenError",
    "DocumentModificationError",
    # Data classes
    "DOCXMetadata",
    "TextRun",
    "ParagraphInfo",
    "DocumentInventory",
    "TextSpan",
    # Classes
    "DOCXReader",
    "DOCXWriter",
    "DOCXHandler",
]
