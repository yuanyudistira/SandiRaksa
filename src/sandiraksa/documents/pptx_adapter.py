"""
PPTX Document Adapter for SandiRaksa.

Extracts text content from PowerPoint presentations and produces LogicalSegments
for the unified detection pipeline.

CRITICAL FEATURES:
1. Run Reconstruction - Like DOCX, PowerPoint text can be split across runs
2. Spatial Context - Labels are often positioned next to values spatially

Example:
    Slide Layout:
        [NIK]           [3271051708990001]
        [Nama]          [Satria Putra]

    The adapter detects that "NIK" is a spatial label for "3271051708990001"
    and attaches it as nearby_labels context.

Key Features:
- Logical text reconstruction across runs
- CharMap for precise run mapping
- Spatial context resolution (nearby labels)
- Slide title as context
- Table extraction with headers
- Notes extraction
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

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
from sandiraksa.documents.spatial_resolver import (
    ShapePosition,
    SpatialContextResolver,
)

if TYPE_CHECKING:
    from pptx import Presentation
    from pptx.shapes.base import BaseShape
    from pptx.slide import Slide

logger = logging.getLogger(__name__)


class PptxDocumentAdapter(BaseDocumentAdapter):
    """
    Document adapter for Microsoft PowerPoint (PPTX) files.

    This adapter extracts content as LogicalSegments with:
    - Run reconstruction for split text
    - Spatial context from nearby labels
    - Slide title context
    - Table headers
    """

    def __init__(self):
        """Initialize the adapter."""
        self._spatial_resolver = SpatialContextResolver()

    @property
    def supported_formats(self) -> list[DocumentFormat]:
        """Get list of formats this adapter supports."""
        return [DocumentFormat.PPTX]

    def extract(self, file_path: Path) -> ExtractionResult:
        """
        Extract content from a PPTX file into LogicalSegments.

        This method:
        1. Opens the PPTX file
        2. Iterates through all slides
        3. For each shape, reconstructs logical text from runs
        4. Resolves spatial context (nearby labels)
        5. Extracts slide titles, tables, and notes

        Args:
            file_path: Path to the PPTX file

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
            from pptx import Presentation

            prs = Presentation(file_path)
            segments: list[LogicalSegment] = []
            segment_index = 0

            for slide_num, slide in enumerate(prs.slides, 1):
                # Extract all shapes with positions for spatial analysis
                shape_positions = self._collect_shape_positions(slide)

                # Find slide title
                slide_title = self._get_slide_title(slide)

                # Process each shape
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        shape_segments = self._extract_text_frame_segments(
                            shape=shape,
                            slide_num=slide_num,
                            file_id=file_id,
                            slide_title=slide_title,
                            shape_positions=shape_positions,
                            start_index=segment_index,
                        )
                        segments.extend(shape_segments)
                        segment_index += len(shape_segments)

                    # Handle tables in shapes
                    if shape.has_table:
                        table_segments = self._extract_table_segments(
                            shape=shape,
                            slide_num=slide_num,
                            file_id=file_id,
                            slide_title=slide_title,
                            start_index=segment_index,
                        )
                        segments.extend(table_segments)
                        segment_index += len(table_segments)

                # Extract notes
                if slide.has_notes_slide:
                    notes_segments = self._extract_notes_segments(
                        slide=slide,
                        slide_num=slide_num,
                        file_id=file_id,
                        start_index=segment_index,
                    )
                    segments.extend(notes_segments)
                    segment_index += len(notes_segments)

            total_chars = sum(len(seg.text) for seg in segments)

            logger.info(
                f"Extracted {len(segments)} segments from PPTX "
                f"({total_chars} chars, {len(prs.slides)} slides)"
            )

            return ExtractionResult(
                segments=segments,
                file_id=file_id,
                file_path=file_path,
                file_format=DocumentFormat.PPTX,
                total_characters=total_chars,
                extraction_warnings=warnings,
                metadata=self._extract_metadata(prs, file_path),
            )

        except ImportError as e:
            raise DocumentExtractionError(
                "python-pptx library not installed",
                file_path=file_path,
                cause=e,
            ) from e
        except Exception as e:
            raise DocumentExtractionError(
                f"Failed to extract PPTX: {e}",
                file_path=file_path,
                cause=e,
            ) from e

    def _collect_shape_positions(self, slide: "Slide") -> list[ShapePosition]:
        """
        Collect all shapes with their positions for spatial analysis.

        Args:
            slide: The slide to analyze

        Returns:
            List of ShapePosition objects
        """
        positions: list[ShapePosition] = []

        for shape in slide.shapes:
            if shape.has_text_frame:
                text = shape.text_frame.text.strip()
                if text:
                    positions.append(
                        ShapePosition(
                            shape_id=str(shape.shape_id),
                            text=text,
                            left=shape.left or 0,
                            top=shape.top or 0,
                            width=shape.width or 0,
                            height=shape.height or 0,
                        )
                    )

        return positions

    def _get_slide_title(self, slide: "Slide") -> str | None:
        """
        Extract slide title.

        Args:
            slide: The slide to analyze

        Returns:
            Title text or None
        """
        for shape in slide.shapes:
            if shape.is_placeholder:
                try:
                    from pptx.enum.shapes import PP_PLACEHOLDER

                    if hasattr(shape, "placeholder_format"):
                        ph_type = shape.placeholder_format.type
                        if ph_type == PP_PLACEHOLDER.TITLE:
                            if shape.has_text_frame:
                                return shape.text_frame.text.strip()
                except Exception:
                    pass

        # Fallback: use spatial resolver
        positions = self._collect_shape_positions(slide)
        return self._spatial_resolver.find_slide_title(positions)

    def _extract_text_frame_segments(
        self,
        shape: "BaseShape",
        slide_num: int,
        file_id: str,
        slide_title: str | None,
        shape_positions: list[ShapePosition],
        start_index: int,
    ) -> list[LogicalSegment]:
        """
        Extract segments from a text frame with run reconstruction.

        Args:
            shape: The shape containing the text frame
            slide_num: Slide number (1-indexed)
            file_id: File identifier
            slide_title: Current slide title
            shape_positions: All shape positions for spatial analysis
            start_index: Starting segment index

        Returns:
            List of LogicalSegments
        """
        segments: list[LogicalSegment] = []

        if not shape.has_text_frame:
            return segments

        text_frame = shape.text_frame
        shape_id = str(shape.shape_id)

        # Get nearby labels via spatial analysis
        current_pos = ShapePosition(
            shape_id=shape_id,
            text=text_frame.text,
            left=shape.left or 0,
            top=shape.top or 0,
            width=shape.width or 0,
            height=shape.height or 0,
        )
        nearby_labels = self._spatial_resolver.get_nearby_labels(
            current_pos, shape_positions
        )

        # Determine shape type
        shape_type = "text_box"
        if shape.is_placeholder:
            try:
                from pptx.enum.shapes import PP_PLACEHOLDER

                if hasattr(shape, "placeholder_format"):
                    ph_type = shape.placeholder_format.type
                    if ph_type == PP_PLACEHOLDER.TITLE:
                        shape_type = "title"
                    elif ph_type == PP_PLACEHOLDER.BODY:
                        shape_type = "body"
                    elif ph_type == PP_PLACEHOLDER.SUBTITLE:
                        shape_type = "subtitle"
            except Exception:
                shape_type = "placeholder"

        # Process each paragraph
        para_index = 0
        for para in text_frame.paragraphs:
            # Reconstruct logical text from runs
            logical_text, char_map = self._reconstruct_from_runs(
                para,
                slide_num,
                shape_id,
                para_index,
            )

            if not logical_text.strip():
                para_index += 1
                continue

            # Create segment
            location = DocumentLocation(
                component=DocumentComponent.PPTX_SHAPE,
                file_id=file_id,
                file_type="pptx",
                slide=slide_num,
                shape_id=shape_id,
                paragraph_index=para_index,
            )

            segment = LogicalSegment(
                text=logical_text,
                file_id=file_id,
                file_type="pptx",
                location=location,
                slide_title=slide_title,
                nearby_labels=nearby_labels,
                shape_type=shape_type,
                char_map=char_map,
                is_header=shape_type in ("title", "subtitle"),
                language_hint="id",
            )

            segments.append(segment)
            para_index += 1

        return segments

    def _reconstruct_from_runs(
        self,
        para: Any,  # pptx paragraph
        slide_num: int,
        shape_id: str,
        para_index: int,
    ) -> tuple[str, CharMap]:
        """
        Reconstruct logical text from runs and build CharMap.

        Similar to DOCX, PowerPoint text can be split across runs.

        Args:
            para: The paragraph to process
            slide_num: Slide number
            shape_id: Shape identifier
            para_index: Paragraph index within shape

        Returns:
            Tuple of (logical_text, char_map)
        """
        entries: list[CharMapEntry] = []
        logical_text = ""
        logical_pos = 0

        for run_idx, run in enumerate(para.runs):
            run_text = run.text
            if not run_text:
                continue

            text_len = len(run_text)
            run_id = f"slide_{slide_num}_shape_{shape_id}_para_{para_index}_run_{run_idx}"

            entries.append(
                CharMapEntry(
                    logical_start=logical_pos,
                    logical_end=logical_pos + text_len,
                    source_component_id=run_id,
                    source_start=0,
                    source_end=text_len,
                    source_type="run",
                    parent_id=f"slide_{slide_num}_shape_{shape_id}",
                )
            )

            logical_text += run_text
            logical_pos += text_len

        return logical_text, CharMap(entries=entries)

    def _extract_table_segments(
        self,
        shape: "BaseShape",
        slide_num: int,
        file_id: str,
        slide_title: str | None,
        start_index: int,
    ) -> list[LogicalSegment]:
        """
        Extract segments from a table shape.

        Args:
            shape: The shape containing the table
            slide_num: Slide number
            file_id: File identifier
            slide_title: Current slide title
            start_index: Starting segment index

        Returns:
            List of LogicalSegments
        """
        segments: list[LogicalSegment] = []

        if not shape.has_table:
            return segments

        table = shape.table
        shape_id = str(shape.shape_id)

        # Get table headers from first row
        table_headers: list[str] = []
        if len(table.rows) > 0:
            for cell in table.rows[0].cells:
                table_headers.append(cell.text.strip())

        # Process each cell
        for row_idx, row in enumerate(table.rows):
            # Get row header (first cell)
            row_header = row.cells[0].text.strip() if row.cells else None

            for col_idx, cell in enumerate(row.cells):
                cell_text = cell.text.strip()
                if not cell_text:
                    continue

                # Simple char_map for cell (not split across runs typically)
                cell_id = f"slide_{slide_num}_shape_{shape_id}_row_{row_idx}_col_{col_idx}"
                char_map = CharMap(
                    entries=[
                        CharMapEntry(
                            logical_start=0,
                            logical_end=len(cell_text),
                            source_component_id=cell_id,
                            source_start=0,
                            source_end=len(cell_text),
                            source_type="table_cell",
                        )
                    ]
                ) if cell_text else CharMap()

                location = DocumentLocation(
                    component=DocumentComponent.PPTX_TABLE_CELL,
                    file_id=file_id,
                    file_type="pptx",
                    slide=slide_num,
                    shape_id=shape_id,
                    table_row=row_idx,
                    table_col=col_idx,
                )

                # Determine column header
                col_header = table_headers[col_idx] if col_idx < len(table_headers) else None

                segment = LogicalSegment(
                    text=cell_text,
                    file_id=file_id,
                    file_type="pptx",
                    location=location,
                    slide_title=slide_title,
                    table_headers=table_headers,
                    row_headers=[row_header] if row_header and col_idx > 0 else [],
                    column_index=col_idx,
                    char_map=char_map,
                    language_hint="id",
                )

                segments.append(segment)

        return segments

    def _extract_notes_segments(
        self,
        slide: "Slide",
        slide_num: int,
        file_id: str,
        start_index: int,
    ) -> list[LogicalSegment]:
        """
        Extract segments from slide notes.

        Args:
            slide: The slide with notes
            slide_num: Slide number
            file_id: File identifier
            start_index: Starting segment index

        Returns:
            List of LogicalSegments
        """
        segments: list[LogicalSegment] = []

        if not slide.has_notes_slide:
            return segments

        notes_slide = slide.notes_slide
        if not notes_slide.notes_text_frame:
            return segments

        notes_text = notes_slide.notes_text_frame.text.strip()
        if not notes_text:
            return segments

        # Create char_map
        char_map = CharMap(
            entries=[
                CharMapEntry(
                    logical_start=0,
                    logical_end=len(notes_text),
                    source_component_id=f"slide_{slide_num}_notes",
                    source_start=0,
                    source_end=len(notes_text),
                    source_type="notes",
                )
            ]
        )

        location = DocumentLocation(
            component=DocumentComponent.PPTX_NOTE,
            file_id=file_id,
            file_type="pptx",
            slide=slide_num,
        )

        segment = LogicalSegment(
            text=notes_text,
            file_id=file_id,
            file_type="pptx",
            location=location,
            char_map=char_map,
            language_hint="id",
        )

        segments.append(segment)
        return segments

    def _extract_metadata(
        self, prs: "Presentation", file_path: Path
    ) -> dict[str, Any]:
        """
        Extract presentation metadata.

        Args:
            prs: The Presentation object
            file_path: Path to the file

        Returns:
            Metadata dictionary
        """
        props = prs.core_properties

        return {
            "slide_count": len(prs.slides),
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
        Apply replacements to a PPTX file and save the result.

        Args:
            file_path: Path to the original PPTX file
            output_path: Path for the protected output
            replacements: List of replacements to apply
            segments: Dictionary of segment_id -> LogicalSegment

        Returns:
            ProtectionResult with status
        """
        file_path = Path(file_path)
        output_path = Path(output_path)

        try:
            from pptx import Presentation

            prs = Presentation(file_path)

            applied = 0
            failed = 0

            # Group replacements by slide and shape
            for replacement in replacements:
                segment = segments.get(replacement.segment_id)
                if not segment:
                    logger.warning(f"Segment not found: {replacement.segment_id}")
                    failed += 1
                    continue

                try:
                    success = self._apply_replacement(
                        prs, replacement, segment
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

            # Save presentation
            prs.save(output_path)

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
                f"Failed to protect PPTX file: {e}",
                file_path=file_path,
                cause=e,
            ) from e

    def _apply_replacement(
        self,
        prs: "Presentation",
        replacement: Replacement,
        segment: LogicalSegment,
    ) -> bool:
        """
        Apply a single replacement to the presentation.

        Args:
            prs: The Presentation object
            replacement: The replacement to apply
            segment: The segment with location info

        Returns:
            True if successful
        """
        loc = segment.location

        # Get slide (1-indexed to 0-indexed)
        slide_num = loc.slide
        if slide_num is None or slide_num < 1:
            return False

        slide_idx = slide_num - 1
        if slide_idx >= len(prs.slides):
            return False

        slide = prs.slides[slide_idx]

        # Handle notes
        if loc.component == DocumentComponent.PPTX_NOTE:
            return self._replace_in_notes(slide, replacement)

        # Find shape by ID
        shape_id = loc.shape_id
        if not shape_id:
            return False

        target_shape = None
        for shape in slide.shapes:
            if str(shape.shape_id) == shape_id:
                target_shape = shape
                break

        if not target_shape:
            return False

        # Handle table cell
        if loc.component == DocumentComponent.PPTX_TABLE_CELL:
            return self._replace_in_table_cell(
                target_shape, loc, replacement
            )

        # Handle text frame
        if target_shape.has_text_frame:
            return self._replace_in_text_frame(
                target_shape, loc, replacement, segment
            )

        return False

    def _replace_in_text_frame(
        self,
        shape: "BaseShape",
        loc: DocumentLocation,
        replacement: Replacement,
        segment: LogicalSegment,
    ) -> bool:
        """
        Replace text in a text frame using CharMap.

        Args:
            shape: The shape with text frame
            loc: Location info
            replacement: The replacement to apply
            segment: The segment with CharMap

        Returns:
            True if successful
        """
        if not shape.has_text_frame:
            return False

        para_idx = loc.paragraph_index
        if para_idx is None:
            para_idx = 0

        text_frame = shape.text_frame
        if para_idx >= len(text_frame.paragraphs):
            return False

        para = text_frame.paragraphs[para_idx]
        runs = list(para.runs)

        # Get run mappings from CharMap
        mappings = segment.get_source_mappings_for_span(
            replacement.logical_start,
            replacement.logical_end,
        )

        if not mappings:
            # Fallback: simple text replacement
            return self._simple_replace(para, replacement)

        rep_text = replacement.get_padded_replacement()

        # Parse run indices from component IDs
        run_indices = []
        for comp_id, start, end in mappings:
            run_idx = self._parse_run_index(comp_id)
            if run_idx is not None:
                run_indices.append((run_idx, start, end))

        if not run_indices:
            return self._simple_replace(para, replacement)

        # Single run case
        if len(run_indices) == 1:
            run_idx, start, end = run_indices[0]
            if run_idx < len(runs):
                run = runs[run_idx]
                current = run.text
                run.text = current[:start] + rep_text + current[end:]
                return True

        # Multi-run case
        first_idx, first_start, first_end = run_indices[0]
        if first_idx < len(runs):
            runs[first_idx].text = runs[first_idx].text[:first_start] + rep_text

        for run_idx, start, end in run_indices[1:-1]:
            if run_idx < len(runs):
                runs[run_idx].text = ""

        if len(run_indices) > 1:
            last_idx, last_start, last_end = run_indices[-1]
            if last_idx < len(runs):
                runs[last_idx].text = runs[last_idx].text[last_end:]

        return True

    def _simple_replace(self, para: Any, replacement: Replacement) -> bool:
        """Simple text replacement fallback."""
        for run in para.runs:
            if replacement.original_text in run.text:
                run.text = run.text.replace(
                    replacement.original_text,
                    replacement.get_padded_replacement(),
                    1,
                )
                return True
        return False

    def _replace_in_table_cell(
        self,
        shape: "BaseShape",
        loc: DocumentLocation,
        replacement: Replacement,
    ) -> bool:
        """Replace text in a table cell."""
        if not shape.has_table:
            return False

        table = shape.table
        row_idx = loc.table_row
        col_idx = loc.table_col

        if row_idx is None or col_idx is None:
            return False

        if row_idx >= len(table.rows):
            return False

        row = table.rows[row_idx]
        if col_idx >= len(row.cells):
            return False

        cell = row.cells[col_idx]

        # Replace in cell text
        for para in cell.text_frame.paragraphs:
            for run in para.runs:
                if replacement.original_text in run.text:
                    run.text = run.text.replace(
                        replacement.original_text,
                        replacement.get_padded_replacement(),
                        1,
                    )
                    return True

        return False

    def _replace_in_notes(
        self,
        slide: "Slide",
        replacement: Replacement,
    ) -> bool:
        """Replace text in slide notes."""
        if not slide.has_notes_slide:
            return False

        notes_frame = slide.notes_slide.notes_text_frame
        if not notes_frame:
            return False

        for para in notes_frame.paragraphs:
            for run in para.runs:
                if replacement.original_text in run.text:
                    run.text = run.text.replace(
                        replacement.original_text,
                        replacement.get_padded_replacement(),
                        1,
                    )
                    return True

        return False

    def _parse_run_index(self, component_id: str) -> int | None:
        """Parse run index from component ID."""
        import re

        match = re.search(r'run_(\d+)', component_id)
        if match:
            return int(match.group(1))
        return None

    def validate(self, file_path: Path) -> tuple[bool, list[str]]:
        """
        Validate that a PPTX file is readable.

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

            from pptx import Presentation

            # Try to open and read
            prs = Presentation(file_path)
            slide_count = len(prs.slides)

            logger.debug(f"Validated PPTX: {slide_count} slides")

            return True, []

        except Exception as e:
            errors.append(f"Validation failed: {e}")
            return False, errors


__all__ = [
    "PptxDocumentAdapter",
]
