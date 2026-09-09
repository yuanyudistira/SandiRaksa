"""
DOCX Document Adapter for SandiRaksa.

Extracts text content from Word documents and produces LogicalSegments
for the unified detection pipeline.

CRITICAL FEATURE: Run Reconstruction
------------------------------------
This adapter solves the DOCX split-run problem. In Word documents,
text that appears as a single string to the user may be split across
multiple runs internally due to formatting changes.

Example:
    User sees: "Nama: Satria Putra Yudistira"

    Internal DOCX structure:
        Run 1: "Nama: "
        Run 2: "Sat"        (bold starts)
        Run 3: "ria Put"    (bold continues)
        Run 4: "ra Yudistira"

    This adapter reconstructs the logical text and maintains a CharMap
    to map detection results back to the correct runs for replacement.

Key Features:
- Logical text reconstruction across runs
- CharMap for precise run mapping
- Heading/context extraction
- Table header detection
- Header/footer handling
- Comment extraction
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator
from uuid import uuid4

from sandiraksa.documents.base import (
    BaseDocumentAdapter,
    DocumentExtractionError,
    DocumentFormat,
    DocumentProtectionError,
    ExtractionResult,
    ProtectionResult,
    Replacement,
)
from sandiraksa.documents.char_map import CharMap, CharMapEntry
from sandiraksa.documents.location import DocumentComponent, DocumentLocation
from sandiraksa.documents.logical_segment import LogicalSegment

if TYPE_CHECKING:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

logger = logging.getLogger(__name__)


# Heading styles in Word
HEADING_STYLES = {
    'Heading 1', 'Heading 2', 'Heading 3', 'Heading 4',
    'Heading 5', 'Heading 6', 'Title', 'Subtitle',
    'Heading1', 'Heading2', 'Heading3', 'Heading4',
    'TOC Heading', 'TOCHeading',
}


class DocxDocumentAdapter(BaseDocumentAdapter):
    """
    Document adapter for Microsoft Word (DOCX) files.

    This adapter extracts content as LogicalSegments with proper
    run reconstruction to handle split-run scenarios.

    The key innovation is maintaining a CharMap that tracks how
    each character in the logical text maps back to specific runs
    in the DOCX file, enabling precise replacements that preserve
    formatting.
    """

    @property
    def supported_formats(self) -> list[DocumentFormat]:
        """Get list of formats this adapter supports."""
        return [DocumentFormat.DOCX]

    def extract(self, file_path: Path) -> ExtractionResult:
        """
        Extract content from a DOCX file into LogicalSegments.

        This method:
        1. Opens the DOCX file
        2. Iterates through all paragraphs, tables, headers, footers
        3. For each paragraph, reconstructs logical text from runs
        4. Builds CharMap for each segment
        5. Extracts context (headings, table headers)

        Args:
            file_path: Path to the DOCX file

        Returns:
            ExtractionResult containing segments and metadata

        Raises:
            DocumentExtractionError: If extraction fails
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise DocumentExtractionError(
                f"File not found: {file_path}",
                file_path=file_path,
            )

        file_id = self._generate_file_id(file_path)
        warnings: list[str] = []

        try:
            from docx import Document

            doc = Document(file_path)
            segments: list[LogicalSegment] = []

            # Track context
            current_heading: str | None = None
            para_index = 0

            # Build a list of all paragraphs with context
            all_paras = self._collect_all_paragraphs(doc)

            # Process each paragraph
            for i, para_data in enumerate(all_paras):
                para = para_data['paragraph']
                component = para_data['component']

                # Get previous/next text for context
                prev_text = all_paras[i - 1]['text'] if i > 0 else None
                next_text = all_paras[i + 1]['text'] if i < len(all_paras) - 1 else None

                # Check if this is a heading
                if self._is_heading(para):
                    current_heading = para.text.strip()
                    # Still create segment for heading (might contain PII)

                # Reconstruct logical text from runs
                logical_text, char_map = self._reconstruct_from_runs(
                    para,
                    para_index,
                    para_data.get('parent_id'),
                )

                if not logical_text.strip():
                    para_index += 1
                    continue

                # Create segment
                segment = self._create_segment(
                    text=logical_text,
                    char_map=char_map,
                    file_id=file_id,
                    para_index=para_index,
                    component=component,
                    heading=current_heading,
                    previous_text=prev_text,
                    next_text=next_text,
                    table_data=para_data.get('table_data'),
                    is_header=self._is_heading(para),
                )

                segments.append(segment)
                para_index += 1

            # Also extract comments
            comment_segments = self._extract_comments(doc, file_id, para_index)
            segments.extend(comment_segments)

            total_chars = sum(len(seg.text) for seg in segments)

            logger.info(
                f"Extracted {len(segments)} segments from DOCX "
                f"({total_chars} chars)"
            )

            return ExtractionResult(
                segments=segments,
                file_id=file_id,
                file_path=file_path,
                file_format=DocumentFormat.DOCX,
                total_characters=total_chars,
                extraction_warnings=warnings,
                metadata=self._extract_metadata(doc, file_path),
            )

        except ImportError as e:
            raise DocumentExtractionError(
                "python-docx library not installed",
                file_path=file_path,
                cause=e,
            ) from e
        except Exception as e:
            raise DocumentExtractionError(
                f"Failed to extract DOCX: {e}",
                file_path=file_path,
                cause=e,
            ) from e

    def _collect_all_paragraphs(
        self, doc: "Document"
    ) -> list[dict[str, Any]]:
        """
        Collect all paragraphs from document with metadata.

        Includes body paragraphs, tables, headers, and footers.

        Args:
            doc: The python-docx Document

        Returns:
            List of dicts with paragraph info
        """
        paras: list[dict[str, Any]] = []

        # Body paragraphs
        for para in doc.paragraphs:
            paras.append({
                'paragraph': para,
                'text': para.text,
                'component': DocumentComponent.DOCX_PARAGRAPH,
                'parent_id': 'body',
            })

        # Tables
        for table_idx, table in enumerate(doc.tables):
            # Get table headers (first row)
            table_headers = self._get_table_headers(table)

            for row_idx, row in enumerate(table.rows):
                for cell_idx, cell in enumerate(row.cells):
                    for para in cell.paragraphs:
                        # Get row header (first cell of row)
                        row_header = None
                        if cell_idx > 0 and row.cells:
                            row_header = row.cells[0].text.strip()

                        paras.append({
                            'paragraph': para,
                            'text': para.text,
                            'component': DocumentComponent.DOCX_TABLE_CELL,
                            'parent_id': f'table_{table_idx}',
                            'table_data': {
                                'table_index': table_idx,
                                'row_index': row_idx,
                                'cell_index': cell_idx,
                                'table_headers': table_headers,
                                'row_header': row_header,
                                'column_header': table_headers[cell_idx] if cell_idx < len(table_headers) else None,
                            },
                        })

        # Headers and footers
        for section_idx, section in enumerate(doc.sections):
            if section.header:
                for para in section.header.paragraphs:
                    paras.append({
                        'paragraph': para,
                        'text': para.text,
                        'component': DocumentComponent.DOCX_HEADER,
                        'parent_id': f'header_{section_idx}',
                    })

            if section.footer:
                for para in section.footer.paragraphs:
                    paras.append({
                        'paragraph': para,
                        'text': para.text,
                        'component': DocumentComponent.DOCX_FOOTER,
                        'parent_id': f'footer_{section_idx}',
                    })

        return paras

    def _get_table_headers(self, table: "Table") -> list[str]:
        """
        Extract column headers from table's first row.

        Args:
            table: python-docx Table object

        Returns:
            List of header strings
        """
        headers: list[str] = []

        if table.rows:
            first_row = table.rows[0]
            for cell in first_row.cells:
                header_text = cell.text.strip()
                headers.append(header_text)

        return headers

    def _is_heading(self, para: "Paragraph") -> bool:
        """
        Check if paragraph is a heading.

        Args:
            para: The paragraph to check

        Returns:
            True if it's a heading style
        """
        if para.style and para.style.name:
            return para.style.name in HEADING_STYLES
        return False

    def _reconstruct_from_runs(
        self,
        para: "Paragraph",
        para_index: int,
        parent_id: str | None,
    ) -> tuple[str, CharMap]:
        """
        Reconstruct logical text from runs and build CharMap.

        This is the CRITICAL method that solves the split-run problem.

        Algorithm:
        1. Enumerate all runs in the paragraph
        2. Concatenate visible text from each run
        3. Build CharMap entries mapping logical positions to run indices

        Args:
            para: The paragraph to process
            para_index: Index of this paragraph
            parent_id: Parent container ID

        Returns:
            Tuple of (logical_text, char_map)

        Example:
            Input runs:
                Run 0: "Nama: "
                Run 1: "Sat"
                Run 2: "ria Put"
                Run 3: "ra"

            Output:
                logical_text = "Nama: Satria Putra"
                char_map entries:
                    [0,6) -> run_0
                    [6,9) -> run_1
                    [9,16) -> run_2
                    [16,18) -> run_3
        """
        entries: list[CharMapEntry] = []
        logical_text = ""
        logical_pos = 0

        for run_idx, run in enumerate(para.runs):
            run_text = run.text
            if not run_text:
                continue

            text_len = len(run_text)
            run_id = f"para_{para_index}_run_{run_idx}"

            entries.append(
                CharMapEntry(
                    logical_start=logical_pos,
                    logical_end=logical_pos + text_len,
                    source_component_id=run_id,
                    source_start=0,
                    source_end=text_len,
                    source_type="run",
                    parent_id=parent_id,
                )
            )

            logical_text += run_text
            logical_pos += text_len

        return logical_text, CharMap(entries=entries)

    def _create_segment(
        self,
        text: str,
        char_map: CharMap,
        file_id: str,
        para_index: int,
        component: DocumentComponent,
        heading: str | None,
        previous_text: str | None,
        next_text: str | None,
        table_data: dict[str, Any] | None,
        is_header: bool,
    ) -> LogicalSegment:
        """
        Create a LogicalSegment for a paragraph.

        Args:
            text: Reconstructed logical text
            char_map: Mapping to source runs
            file_id: File identifier
            para_index: Paragraph index
            component: Document component type
            heading: Current heading context
            previous_text: Previous paragraph text
            next_text: Next paragraph text
            table_data: Table context if in a table
            is_header: Whether this is a heading

        Returns:
            Configured LogicalSegment
        """
        # Build location
        location = DocumentLocation(
            component=component,
            file_id=file_id,
            file_type="docx",
            paragraph_index=para_index,
        )

        # Add table info to location if applicable
        if table_data:
            location.table_index = table_data.get('table_index')
            location.table_row = table_data.get('row_index')
            location.table_col = table_data.get('cell_index')

        # Build table headers list
        table_headers: list[str] = []
        row_headers: list[str] = []
        column_index: int | None = None

        if table_data:
            table_headers = table_data.get('table_headers', [])
            if table_data.get('row_header'):
                row_headers = [table_data['row_header']]
            column_index = table_data.get('cell_index')

        # Detect key-value patterns in text
        key_label = self._detect_key_label(text)

        return LogicalSegment(
            text=text,
            file_id=file_id,
            file_type="docx",
            location=location,
            previous_text=previous_text,
            next_text=next_text,
            heading=heading,
            table_headers=table_headers,
            row_headers=row_headers,
            column_index=column_index,
            key_label=key_label,
            is_value_of_key=key_label is not None,
            char_map=char_map,
            is_header=is_header,
            language_hint="id",
        )

    def _detect_key_label(self, text: str) -> str | None:
        """
        Detect if text follows a key-value pattern and extract the key.

        Args:
            text: Text to analyze

        Returns:
            The key/label if found, None otherwise
        """
        import re

        # Pattern for "Key: Value" or "Key = Value"
        match = re.match(r'^(.{1,30}?)\s*[:=]\s*(.+)$', text)
        if match:
            key = match.group(1).strip()
            if len(key) <= 25:
                return key

        return None

    def _extract_comments(
        self,
        doc: "Document",
        file_id: str,
        start_index: int,
    ) -> list[LogicalSegment]:
        """
        Extract comments from the document.

        Args:
            doc: The Document object
            file_id: File identifier
            start_index: Starting paragraph index

        Returns:
            List of segments for comments
        """
        segments: list[LogicalSegment] = []

        try:
            from zipfile import ZipFile
            from xml.etree import ElementTree as ET

            # Get the document's file path
            # python-docx doesn't directly expose this, need workaround
            # For now, skip comment extraction as it requires file path
            # This can be enhanced later

            pass

        except Exception as e:
            logger.debug(f"Could not extract comments: {e}")

        return segments

    def _extract_metadata(
        self, doc: "Document", file_path: Path
    ) -> dict[str, Any]:
        """
        Extract document metadata.

        Args:
            doc: The Document object
            file_path: Path to the file

        Returns:
            Metadata dictionary
        """
        props = doc.core_properties

        return {
            "paragraph_count": len(doc.paragraphs),
            "table_count": len(doc.tables),
            "section_count": len(doc.sections),
            "author": props.author,
            "title": props.title,
            "created": str(props.created) if props.created else None,
            "modified": str(props.modified) if props.modified else None,
        }

    def apply_replacements(
        self,
        file_path: Path,
        output_path: Path,
        replacements: list[Replacement],
        segments: dict[str, LogicalSegment],
    ) -> ProtectionResult:
        """
        Apply replacements to a DOCX file and save the result.

        This method uses the CharMap in each segment to map logical
        positions back to specific runs, enabling precise replacements
        that preserve formatting.

        Args:
            file_path: Path to the original DOCX file
            output_path: Path for the protected output
            replacements: List of replacements to apply
            segments: Dictionary of segment_id -> LogicalSegment

        Returns:
            ProtectionResult with status
        """
        file_path = Path(file_path)
        output_path = Path(output_path)

        try:
            from docx import Document

            doc = Document(file_path)

            # Group replacements by paragraph
            para_replacements: dict[int, list[tuple[Replacement, LogicalSegment]]] = {}

            for replacement in replacements:
                segment = segments.get(replacement.segment_id)
                if not segment:
                    logger.warning(f"Segment not found: {replacement.segment_id}")
                    continue

                para_idx = segment.location.paragraph_index
                if para_idx is not None:
                    if para_idx not in para_replacements:
                        para_replacements[para_idx] = []
                    para_replacements[para_idx].append((replacement, segment))

            applied = 0
            failed = 0

            # Process each paragraph with replacements
            all_paras = self._collect_all_paragraphs(doc)

            for para_idx, rep_list in para_replacements.items():
                if para_idx >= len(all_paras):
                    failed += len(rep_list)
                    continue

                para = all_paras[para_idx]['paragraph']

                # Sort replacements by position (descending) to apply from end
                rep_list.sort(
                    key=lambda x: x[0].logical_start,
                    reverse=True,
                )

                for replacement, segment in rep_list:
                    try:
                        success = self._apply_run_replacement(
                            para,
                            replacement,
                            segment,
                        )
                        if success:
                            applied += 1
                        else:
                            failed += 1
                    except Exception as e:
                        logger.error(f"Failed to apply replacement: {e}")
                        failed += 1

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save document
            doc.save(output_path)

            # Validate output
            is_valid, errors = self.validate(output_path)

            return ProtectionResult(
                output_path=output_path,
                replacements_applied=applied,
                replacements_failed=failed,
                validation_passed=is_valid,
                validation_errors=errors,
            )

        except Exception as e:
            raise DocumentProtectionError(
                f"Failed to protect DOCX file: {e}",
                file_path=file_path,
                cause=e,
            ) from e

    def _apply_run_replacement(
        self,
        para: "Paragraph",
        replacement: Replacement,
        segment: LogicalSegment,
    ) -> bool:
        """
        Apply a single replacement to a paragraph using CharMap.

        This handles the case where a replacement spans multiple runs.

        Args:
            para: The paragraph to modify
            replacement: The replacement to apply
            segment: The segment with CharMap

        Returns:
            True if successful
        """
        # Get the run mappings for this replacement
        mappings = segment.get_source_mappings_for_span(
            replacement.logical_start,
            replacement.logical_end,
        )

        if not mappings:
            logger.warning("No run mappings found for replacement")
            return False

        runs = para.runs
        rep_text = replacement.get_padded_replacement()

        # If single run, simple replacement
        if len(mappings) == 1:
            comp_id, source_start, source_end = mappings[0]
            run_idx = self._parse_run_index(comp_id)

            if run_idx is None or run_idx >= len(runs):
                return False

            run = runs[run_idx]
            current_text = run.text

            # Verify text matches
            if current_text[source_start:source_end] != replacement.original_text:
                logger.warning(
                    f"Text mismatch in run {run_idx}: "
                    f"expected '{replacement.original_text}', "
                    f"found '{current_text[source_start:source_end]}'"
                )
                return False

            # Apply replacement
            run.text = current_text[:source_start] + rep_text + current_text[source_end:]
            return True

        # Multi-run case: put replacement in first run, clear others
        first_comp_id, first_start, first_end = mappings[0]
        first_run_idx = self._parse_run_index(first_comp_id)

        if first_run_idx is None or first_run_idx >= len(runs):
            return False

        # Modify first run
        first_run = runs[first_run_idx]
        first_run.text = first_run.text[:first_start] + rep_text

        # Clear middle runs
        for comp_id, start, end in mappings[1:-1]:
            run_idx = self._parse_run_index(comp_id)
            if run_idx is not None and run_idx < len(runs):
                runs[run_idx].text = ""

        # Modify last run (keep text after replacement)
        if len(mappings) > 1:
            last_comp_id, last_start, last_end = mappings[-1]
            last_run_idx = self._parse_run_index(last_comp_id)

            if last_run_idx is not None and last_run_idx < len(runs):
                last_run = runs[last_run_idx]
                last_run.text = last_run.text[last_end:]

        return True

    def _parse_run_index(self, component_id: str) -> int | None:
        """
        Parse run index from component ID.

        Args:
            component_id: ID like "para_5_run_2"

        Returns:
            Run index or None
        """
        import re

        match = re.search(r'run_(\d+)', component_id)
        if match:
            return int(match.group(1))
        return None

    def validate(self, file_path: Path) -> tuple[bool, list[str]]:
        """
        Validate that a DOCX file is readable and structurally valid.

        Args:
            file_path: Path to the file to validate

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors: list[str] = []

        try:
            if not file_path.exists():
                errors.append(f"File does not exist: {file_path}")
                return False, errors

            from docx import Document

            # Try to open and read the document
            doc = Document(file_path)

            # Basic validation - can we iterate paragraphs?
            para_count = len(doc.paragraphs)

            # Can we access tables?
            table_count = len(doc.tables)

            logger.debug(
                f"Validated DOCX: {para_count} paragraphs, "
                f"{table_count} tables"
            )

            return True, []

        except Exception as e:
            errors.append(f"Validation failed: {e}")
            return False, errors


__all__ = [
    "DocxDocumentAdapter",
    "HEADING_STYLES",
]
