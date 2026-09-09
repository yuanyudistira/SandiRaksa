"""
LogicalSegment model for SandiRaksa.

The LogicalSegment is the core data structure passed to the detection engine.
It represents text as the user logically reads it (not as stored internally),
along with all available context that can improve detection accuracy.

Key Design Principle:
    The detector receives text as the user logically reads it,
    NOT merely as the Office document internally stores it.

Example:
    User sees: "Nama: Satria Putra Yudistira"

    DOCX internal storage:
        Run 1: "Nama: "
        Run 2: "Sat"
        Run 3: "ria Put"
        Run 4: "ra Yudistira"

    LogicalSegment.text = "Nama: Satria Putra Yudistira"
    LogicalSegment.char_map maps positions back to runs for replacement
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass

from sandiraksa.documents.char_map import CharMap, CharMapEntry
from sandiraksa.documents.location import DocumentComponent, DocumentLocation


class LogicalSegment(BaseModel):
    """
    Represents a unit of text for PII detection with full context.

    This is the primary input to the unified detection engine. Document
    adapters extract content and produce LogicalSegments that contain:
    1. The reconstructed logical text (across runs/shapes)
    2. Mapping back to source components (CharMap)
    3. Structural context (headings, labels, headers)
    4. Spatial context (for PowerPoint)
    5. Document-level hints

    Attributes:
        id: Unique identifier for this segment
        text: The reconstructed logical text to be analyzed

        file_id: Identifier of the source file
        file_type: File format (txt, docx, pptx, xlsx, csv)
        location: Precise location within the document

        # Surrounding text context
        previous_text: Text from the previous segment/paragraph
        next_text: Text from the next segment/paragraph
        heading: Nearest heading above this segment

        # Structural context (Excel/CSV)
        table_headers: Column headers if in a table/spreadsheet
        row_headers: Row headers/labels if available
        column_index: Column index for spreadsheet cells

        # PowerPoint spatial context
        slide_title: Title of the current slide
        nearby_labels: Labels found spatially near this text
        shape_type: Type of PowerPoint shape containing this text

        # Document-level hints
        document_hints: High-level document type indicators
        section_title: Current document section title
        document_type: Detected document type (HR, medical, etc.)

        # Key-value detection (for TXT)
        key_label: If this appears to be a key:value pair, the key part
        is_value_of_key: Whether this text is the value portion of a k:v pair

        # Mapping for replacement
        char_map: Mapping from logical positions to source components

        # Metadata
        language_hint: Detected or specified language
        is_header: Whether this segment is a header/title
        extraction_confidence: Confidence in text extraction quality
    """

    # Identity
    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str = Field(description="The reconstructed logical text to analyze")

    # Source information
    file_id: str = Field(description="Identifier of the source file")
    file_type: str = Field(description="File format: txt, docx, pptx, xlsx, csv")
    location: DocumentLocation = Field(description="Precise location in document")

    # Surrounding text context
    previous_text: str | None = Field(
        default=None,
        description="Text from the previous segment/paragraph (for context)",
    )
    next_text: str | None = Field(
        default=None,
        description="Text from the next segment/paragraph (for context)",
    )
    heading: str | None = Field(
        default=None,
        description="Nearest heading above this segment",
    )

    # Structural context (tables/spreadsheets)
    table_headers: list[str] = Field(
        default_factory=list,
        description="Column headers if in a table or spreadsheet",
    )
    row_headers: list[str] = Field(
        default_factory=list,
        description="Row headers or labels if available",
    )
    column_index: int | None = Field(
        default=None,
        ge=0,
        description="Column index for spreadsheet cells",
    )

    # PowerPoint spatial context
    slide_title: str | None = Field(
        default=None,
        description="Title of the current slide (PPTX)",
    )
    nearby_labels: list[str] = Field(
        default_factory=list,
        description="Labels found spatially near this text (PPTX)",
    )
    shape_type: str | None = Field(
        default=None,
        description="Type of PowerPoint shape (title, body, textbox, etc.)",
    )

    # Document-level hints
    document_hints: list[str] = Field(
        default_factory=list,
        description="High-level document type indicators",
    )
    section_title: str | None = Field(
        default=None,
        description="Current document section title",
    )
    document_type: str | None = Field(
        default=None,
        description="Detected document type (hr, medical, banking, legal, etc.)",
    )

    # Key-value detection (useful for TXT and some DOCX)
    key_label: str | None = Field(
        default=None,
        description="If key:value pattern detected, the key/label part",
    )
    is_value_of_key: bool = Field(
        default=False,
        description="Whether this segment is the value portion of a k:v pair",
    )

    # Character mapping for replacement
    char_map: CharMap = Field(
        default_factory=CharMap,
        description="Mapping from logical positions to source components",
    )

    # Metadata
    language_hint: str = Field(
        default="id",
        description="Language code (id=Indonesian, en=English)",
    )
    is_header: bool = Field(
        default=False,
        description="Whether this segment is a header or title",
    )
    extraction_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in text extraction quality (1.0 = perfect)",
    )

    model_config = {"frozen": False, "extra": "forbid"}

    @property
    def text_length(self) -> int:
        """Get the length of the logical text."""
        return len(self.text)

    @property
    def has_context(self) -> bool:
        """Check if this segment has any contextual information."""
        return bool(
            self.heading
            or self.table_headers
            or self.row_headers
            or self.slide_title
            or self.nearby_labels
            or self.key_label
            or self.document_hints
        )

    @property
    def context_labels(self) -> list[str]:
        """
        Get all context labels that could indicate PII type.

        This combines all sources of labels that might hint at the
        type of data (e.g., "NIK", "Nama", "Alamat").
        """
        labels: list[str] = []

        if self.heading:
            labels.append(self.heading)
        if self.key_label:
            labels.append(self.key_label)
        if self.slide_title:
            labels.append(self.slide_title)

        labels.extend(self.table_headers)
        labels.extend(self.row_headers)
        labels.extend(self.nearby_labels)

        return labels

    @property
    def is_spreadsheet(self) -> bool:
        """Check if this segment comes from a spreadsheet format."""
        return self.file_type in ("xlsx", "csv")

    @property
    def is_presentation(self) -> bool:
        """Check if this segment comes from a presentation."""
        return self.file_type == "pptx"

    @property
    def is_document(self) -> bool:
        """Check if this segment comes from a word document."""
        return self.file_type == "docx"

    @property
    def is_text_file(self) -> bool:
        """Check if this segment comes from a plain text file."""
        return self.file_type == "txt"

    def get_source_mappings_for_span(
        self, start: int, end: int
    ) -> list[tuple[str, int, int]]:
        """
        Get source component mappings for a detected span.

        This is the key method used when applying protection. Given
        the start/end of a detected entity in the logical text,
        it returns all source components that need modification.

        Args:
            start: Start position of the entity in logical text
            end: End position of the entity in logical text

        Returns:
            List of (source_component_id, source_start, source_end) tuples
        """
        return self.char_map.get_source_mappings_for_range(start, end)

    def get_text_slice(self, start: int, end: int) -> str:
        """
        Get a slice of the logical text.

        Args:
            start: Start position
            end: End position

        Returns:
            The text slice
        """
        return self.text[start:end]

    def get_context_window(
        self, start: int, end: int, window_size: int = 20
    ) -> tuple[str, str]:
        """
        Get context before and after a span.

        Args:
            start: Start of the span
            end: End of the span
            window_size: Characters of context to include

        Returns:
            Tuple of (context_before, context_after)
        """
        context_before = self.text[max(0, start - window_size) : start]
        context_after = self.text[end : end + window_size]
        return context_before, context_after

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: dict[str, Any] = {
            "id": self.id,
            "text": self.text,
            "file_id": self.file_id,
            "file_type": self.file_type,
            "location": self.location.to_dict(),
        }

        # Add optional fields if present
        if self.previous_text:
            result["previous_text"] = self.previous_text
        if self.next_text:
            result["next_text"] = self.next_text
        if self.heading:
            result["heading"] = self.heading
        if self.table_headers:
            result["table_headers"] = self.table_headers
        if self.row_headers:
            result["row_headers"] = self.row_headers
        if self.column_index is not None:
            result["column_index"] = self.column_index
        if self.slide_title:
            result["slide_title"] = self.slide_title
        if self.nearby_labels:
            result["nearby_labels"] = self.nearby_labels
        if self.shape_type:
            result["shape_type"] = self.shape_type
        if self.document_hints:
            result["document_hints"] = self.document_hints
        if self.section_title:
            result["section_title"] = self.section_title
        if self.document_type:
            result["document_type"] = self.document_type
        if self.key_label:
            result["key_label"] = self.key_label
        if self.is_value_of_key:
            result["is_value_of_key"] = True
        if self.char_map.entries:
            result["char_map"] = [e.to_dict() for e in self.char_map.entries]
        if self.language_hint != "id":
            result["language_hint"] = self.language_hint
        if self.is_header:
            result["is_header"] = True
        if self.extraction_confidence < 1.0:
            result["extraction_confidence"] = self.extraction_confidence

        return result

    @classmethod
    def for_txt_paragraph(
        cls,
        text: str,
        file_id: str,
        paragraph_index: int,
        *,
        previous_text: str | None = None,
        next_text: str | None = None,
        key_label: str | None = None,
    ) -> "LogicalSegment":
        """
        Create a LogicalSegment for a TXT file paragraph.

        Args:
            text: The paragraph text
            file_id: Identifier of the source file
            paragraph_index: Index of the paragraph (0-indexed)
            previous_text: Previous paragraph text for context
            next_text: Next paragraph text for context
            key_label: If this is a key:value, the key part

        Returns:
            Configured LogicalSegment
        """
        # For TXT, char_map is simple 1:1 mapping
        char_map = CharMap(
            entries=[
                CharMapEntry(
                    logical_start=0,
                    logical_end=len(text),
                    source_component_id=f"para_{paragraph_index}",
                    source_start=0,
                    source_end=len(text),
                    source_type="paragraph",
                )
            ]
        ) if text else CharMap()

        return cls(
            text=text,
            file_id=file_id,
            file_type="txt",
            location=DocumentLocation.for_txt(
                file_id=file_id,
                paragraph_index=paragraph_index,
            ),
            previous_text=previous_text,
            next_text=next_text,
            key_label=key_label,
            is_value_of_key=key_label is not None,
            char_map=char_map,
        )

    @classmethod
    def for_docx_paragraph(
        cls,
        text: str,
        file_id: str,
        paragraph_index: int,
        char_map: CharMap,
        *,
        heading: str | None = None,
        previous_text: str | None = None,
        next_text: str | None = None,
        run_indices: list[int] | None = None,
    ) -> "LogicalSegment":
        """
        Create a LogicalSegment for a DOCX paragraph.

        Args:
            text: The reconstructed paragraph text
            file_id: Identifier of the source file
            paragraph_index: Index of the paragraph (0-indexed)
            char_map: Mapping from logical positions to runs
            heading: Nearest heading above this paragraph
            previous_text: Previous paragraph text
            next_text: Next paragraph text
            run_indices: Indices of runs in this paragraph

        Returns:
            Configured LogicalSegment
        """
        return cls(
            text=text,
            file_id=file_id,
            file_type="docx",
            location=DocumentLocation.for_docx_paragraph(
                file_id=file_id,
                paragraph_index=paragraph_index,
                run_indices=run_indices,
            ),
            heading=heading,
            previous_text=previous_text,
            next_text=next_text,
            char_map=char_map,
        )

    @classmethod
    def for_pptx_shape(
        cls,
        text: str,
        file_id: str,
        slide: int,
        shape_id: str,
        char_map: CharMap,
        *,
        slide_title: str | None = None,
        nearby_labels: list[str] | None = None,
        shape_type: str | None = None,
    ) -> "LogicalSegment":
        """
        Create a LogicalSegment for a PPTX shape.

        Args:
            text: The reconstructed shape text
            file_id: Identifier of the source file
            slide: Slide number (1-indexed)
            shape_id: Unique identifier for the shape
            char_map: Mapping from logical positions to runs
            slide_title: Title of the slide
            nearby_labels: Labels found spatially near this shape
            shape_type: Type of shape (title, body, textbox, etc.)

        Returns:
            Configured LogicalSegment
        """
        return cls(
            text=text,
            file_id=file_id,
            file_type="pptx",
            location=DocumentLocation.for_pptx_shape(
                file_id=file_id,
                slide=slide,
                shape_id=shape_id,
            ),
            slide_title=slide_title,
            nearby_labels=nearby_labels or [],
            shape_type=shape_type,
            char_map=char_map,
        )

    @classmethod
    def for_xlsx_cell(
        cls,
        text: str,
        file_id: str,
        sheet: str,
        cell: str,
        *,
        row: int | None = None,
        column: int | None = None,
        table_headers: list[str] | None = None,
        row_headers: list[str] | None = None,
    ) -> "LogicalSegment":
        """
        Create a LogicalSegment for an XLSX cell.

        Args:
            text: The cell value as string
            file_id: Identifier of the source file
            sheet: Sheet name
            cell: Cell address (e.g., "A1")
            row: Row number (0-indexed)
            column: Column number (0-indexed)
            table_headers: Column headers from the sheet
            row_headers: Row headers if available

        Returns:
            Configured LogicalSegment
        """
        # For XLSX cells, char_map is simple 1:1
        char_map = CharMap(
            entries=[
                CharMapEntry(
                    logical_start=0,
                    logical_end=len(text),
                    source_component_id=f"{sheet}!{cell}",
                    source_start=0,
                    source_end=len(text),
                    source_type="cell",
                )
            ]
        ) if text else CharMap()

        return cls(
            text=text,
            file_id=file_id,
            file_type="xlsx",
            location=DocumentLocation.for_xlsx_cell(
                file_id=file_id,
                sheet=sheet,
                cell=cell,
                row=row,
                column=column,
            ),
            table_headers=table_headers or [],
            row_headers=row_headers or [],
            column_index=column,
            char_map=char_map,
        )

    @classmethod
    def for_csv_cell(
        cls,
        text: str,
        file_id: str,
        row: int,
        column: int,
        *,
        table_headers: list[str] | None = None,
    ) -> "LogicalSegment":
        """
        Create a LogicalSegment for a CSV cell.

        Args:
            text: The cell value
            file_id: Identifier of the source file
            row: Row number (0-indexed)
            column: Column number (0-indexed)
            table_headers: Column headers from the CSV

        Returns:
            Configured LogicalSegment
        """
        # For CSV cells, char_map is simple 1:1
        cell_ref = f"R{row + 1}C{column + 1}"
        char_map = CharMap(
            entries=[
                CharMapEntry(
                    logical_start=0,
                    logical_end=len(text),
                    source_component_id=cell_ref,
                    source_start=0,
                    source_end=len(text),
                    source_type="cell",
                )
            ]
        ) if text else CharMap()

        return cls(
            text=text,
            file_id=file_id,
            file_type="csv",
            location=DocumentLocation.for_csv_cell(
                file_id=file_id,
                row=row,
                column=column,
                cell=cell_ref,
            ),
            table_headers=table_headers or [],
            column_index=column,
            char_map=char_map,
        )
