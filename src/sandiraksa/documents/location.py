"""
DocumentLocation model for SandiRaksa.

Provides a comprehensive location model that describes where content
exists within various document formats (TXT, DOCX, PPTX, CSV, XLSX).

This is part of the unified detection architecture that separates
document parsing from PII detection.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DocumentComponent(str, Enum):
    """Types of document components where text can be found."""

    # Generic
    BODY = "body"
    HEADER = "header"
    FOOTER = "footer"

    # Text file
    PARAGRAPH = "paragraph"
    LINE = "line"

    # Word document (DOCX)
    DOCX_PARAGRAPH = "docx_paragraph"
    DOCX_TABLE_CELL = "docx_table_cell"
    DOCX_HEADER = "docx_header"
    DOCX_FOOTER = "docx_footer"
    DOCX_FOOTNOTE = "docx_footnote"
    DOCX_ENDNOTE = "docx_endnote"
    DOCX_COMMENT = "docx_comment"
    DOCX_TEXTBOX = "docx_textbox"

    # PowerPoint (PPTX)
    PPTX_TITLE = "pptx_title"
    PPTX_BODY = "pptx_body"
    PPTX_TEXT_FRAME = "pptx_text_frame"
    PPTX_TABLE_CELL = "pptx_table_cell"
    PPTX_NOTE = "pptx_note"
    PPTX_SHAPE = "pptx_shape"

    # Excel (XLSX)
    XLSX_CELL = "xlsx_cell"
    XLSX_HEADER = "xlsx_header"
    XLSX_COMMENT = "xlsx_comment"

    # CSV
    CSV_CELL = "csv_cell"
    CSV_HEADER = "csv_header"


class DocumentLocation(BaseModel):
    """
    Describes the precise location of content within a document.

    This model provides a unified way to reference locations across
    all supported document formats. It's designed to be:
    - Format-agnostic at the consumer level
    - Precise enough to map back to source for modifications
    - Rich enough to provide context for detection

    Attributes:
        component: The type of document component (e.g., paragraph, cell, shape)
        file_id: Unique identifier for the source file
        file_type: File extension/type (txt, docx, pptx, xlsx, csv)

        # Page/sheet/slide location
        page: Page number for paginated documents (1-indexed)
        slide: Slide number for presentations (1-indexed)
        sheet: Sheet name for spreadsheets

        # Cell/position references
        cell: Cell address for spreadsheets (e.g., "A1", "B2")
        row: Row number (0-indexed)
        column: Column number (0-indexed)

        # Document structure references
        paragraph_index: Index of paragraph in document (0-indexed)
        table_index: Index of table in document (0-indexed)
        table_row: Row within table (0-indexed)
        table_col: Column within table (0-indexed)

        # OOXML-specific references
        shape_id: Unique identifier for PowerPoint shapes
        run_indices: Indices of text runs within a paragraph

        # Text position within component
        char_start: Starting character position within component
        char_end: Ending character position within component

        # Section/hierarchy
        section_index: Document section index
        heading_level: Level of heading (1-6) if applicable
    """

    # Required fields
    component: DocumentComponent
    file_id: str = Field(description="Unique identifier for the source file")
    file_type: str = Field(description="File extension/type (txt, docx, pptx, xlsx, csv)")

    # Page/sheet/slide location
    page: int | None = Field(default=None, ge=1, description="Page number (1-indexed)")
    slide: int | None = Field(default=None, ge=1, description="Slide number (1-indexed)")
    sheet: str | None = Field(default=None, description="Sheet name for spreadsheets")

    # Cell/position references
    cell: str | None = Field(default=None, description="Cell address (e.g., 'A1')")
    row: int | None = Field(default=None, ge=0, description="Row number (0-indexed)")
    column: int | None = Field(default=None, ge=0, description="Column number (0-indexed)")

    # Document structure references
    paragraph_index: int | None = Field(
        default=None, ge=0, description="Index of paragraph (0-indexed)"
    )
    table_index: int | None = Field(default=None, ge=0, description="Index of table (0-indexed)")
    table_row: int | None = Field(default=None, ge=0, description="Row within table (0-indexed)")
    table_col: int | None = Field(
        default=None, ge=0, description="Column within table (0-indexed)"
    )

    # OOXML-specific references
    shape_id: str | None = Field(default=None, description="PowerPoint shape identifier")
    run_indices: list[int] = Field(
        default_factory=list, description="Indices of text runs within paragraph"
    )

    # Text position within component
    char_start: int | None = Field(
        default=None, ge=0, description="Starting character position within component"
    )
    char_end: int | None = Field(
        default=None, ge=0, description="Ending character position within component"
    )

    # Section/hierarchy
    section_index: int | None = Field(default=None, ge=0, description="Document section index")
    heading_level: int | None = Field(
        default=None, ge=1, le=6, description="Heading level (1-6)"
    )

    model_config = {"frozen": False, "extra": "forbid"}

    @property
    def display_location(self) -> str:
        """
        Get a human-readable location string.

        Returns:
            A formatted string describing the location in the document.

        Examples:
            - "Sheet: Data | Cell: A1"
            - "Slide: 3 | Shape: Title"
            - "Paragraph: 5"
        """
        parts: list[str] = []

        if self.sheet:
            parts.append(f"Sheet: {self.sheet}")
        if self.cell:
            parts.append(f"Cell: {self.cell}")
        if self.slide:
            parts.append(f"Slide: {self.slide}")
        if self.page:
            parts.append(f"Page: {self.page}")
        if self.paragraph_index is not None:
            parts.append(f"Para: {self.paragraph_index + 1}")
        if self.table_index is not None:
            table_loc = f"Table: {self.table_index + 1}"
            if self.table_row is not None and self.table_col is not None:
                table_loc += f" [{self.table_row + 1}, {self.table_col + 1}]"
            parts.append(table_loc)

        parts.append(self.component.value)

        return " | ".join(parts)

    @property
    def sort_key(self) -> tuple[int, str, int, int, int, int]:
        """
        Get a sortable key for ordering locations.

        Returns:
            A tuple that can be used for consistent sorting of locations.
        """
        return (
            self.slide or self.page or 0,
            self.sheet or "",
            self.row or 0,
            self.column or 0,
            self.paragraph_index or 0,
            self.char_start or 0,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary, excluding None values.

        Returns:
            Dictionary with only non-None fields.
        """
        result: dict[str, Any] = {
            "component": self.component.value,
            "file_id": self.file_id,
            "file_type": self.file_type,
        }

        optional_fields = [
            "page",
            "slide",
            "sheet",
            "cell",
            "row",
            "column",
            "paragraph_index",
            "table_index",
            "table_row",
            "table_col",
            "shape_id",
            "char_start",
            "char_end",
            "section_index",
            "heading_level",
        ]

        for field in optional_fields:
            value = getattr(self, field)
            if value is not None:
                result[field] = value

        if self.run_indices:
            result["run_indices"] = self.run_indices

        return result

    @classmethod
    def for_txt(
        cls,
        file_id: str,
        paragraph_index: int,
        char_start: int | None = None,
        char_end: int | None = None,
    ) -> DocumentLocation:
        """
        Create a location for a TXT file.

        Args:
            file_id: Unique identifier for the file
            paragraph_index: Index of the paragraph (0-indexed)
            char_start: Starting character position
            char_end: Ending character position

        Returns:
            DocumentLocation configured for TXT format
        """
        return cls(
            component=DocumentComponent.PARAGRAPH,
            file_id=file_id,
            file_type="txt",
            paragraph_index=paragraph_index,
            char_start=char_start,
            char_end=char_end,
        )

    @classmethod
    def for_docx_paragraph(
        cls,
        file_id: str,
        paragraph_index: int,
        run_indices: list[int] | None = None,
        char_start: int | None = None,
        char_end: int | None = None,
    ) -> DocumentLocation:
        """
        Create a location for a DOCX paragraph.

        Args:
            file_id: Unique identifier for the file
            paragraph_index: Index of the paragraph (0-indexed)
            run_indices: Indices of text runs within the paragraph
            char_start: Starting character position
            char_end: Ending character position

        Returns:
            DocumentLocation configured for DOCX paragraph
        """
        return cls(
            component=DocumentComponent.DOCX_PARAGRAPH,
            file_id=file_id,
            file_type="docx",
            paragraph_index=paragraph_index,
            run_indices=run_indices or [],
            char_start=char_start,
            char_end=char_end,
        )

    @classmethod
    def for_docx_table_cell(
        cls,
        file_id: str,
        table_index: int,
        table_row: int,
        table_col: int,
        paragraph_index: int | None = None,
    ) -> DocumentLocation:
        """
        Create a location for a DOCX table cell.

        Args:
            file_id: Unique identifier for the file
            table_index: Index of the table (0-indexed)
            table_row: Row within the table (0-indexed)
            table_col: Column within the table (0-indexed)
            paragraph_index: Paragraph index within the cell

        Returns:
            DocumentLocation configured for DOCX table cell
        """
        return cls(
            component=DocumentComponent.DOCX_TABLE_CELL,
            file_id=file_id,
            file_type="docx",
            table_index=table_index,
            table_row=table_row,
            table_col=table_col,
            paragraph_index=paragraph_index,
        )

    @classmethod
    def for_pptx_shape(
        cls,
        file_id: str,
        slide: int,
        shape_id: str,
        char_start: int | None = None,
        char_end: int | None = None,
    ) -> DocumentLocation:
        """
        Create a location for a PPTX shape.

        Args:
            file_id: Unique identifier for the file
            slide: Slide number (1-indexed)
            shape_id: Unique identifier for the shape
            char_start: Starting character position
            char_end: Ending character position

        Returns:
            DocumentLocation configured for PPTX shape
        """
        return cls(
            component=DocumentComponent.PPTX_SHAPE,
            file_id=file_id,
            file_type="pptx",
            slide=slide,
            shape_id=shape_id,
            char_start=char_start,
            char_end=char_end,
        )

    @classmethod
    def for_pptx_title(
        cls,
        file_id: str,
        slide: int,
        shape_id: str | None = None,
    ) -> DocumentLocation:
        """
        Create a location for a PPTX slide title.

        Args:
            file_id: Unique identifier for the file
            slide: Slide number (1-indexed)
            shape_id: Optional shape identifier

        Returns:
            DocumentLocation configured for PPTX title
        """
        return cls(
            component=DocumentComponent.PPTX_TITLE,
            file_id=file_id,
            file_type="pptx",
            slide=slide,
            shape_id=shape_id,
        )

    @classmethod
    def for_pptx_note(
        cls,
        file_id: str,
        slide: int,
    ) -> DocumentLocation:
        """
        Create a location for PPTX slide notes.

        Args:
            file_id: Unique identifier for the file
            slide: Slide number (1-indexed)

        Returns:
            DocumentLocation configured for PPTX notes
        """
        return cls(
            component=DocumentComponent.PPTX_NOTE,
            file_id=file_id,
            file_type="pptx",
            slide=slide,
        )

    @classmethod
    def for_xlsx_cell(
        cls,
        file_id: str,
        sheet: str,
        cell: str,
        row: int | None = None,
        column: int | None = None,
    ) -> DocumentLocation:
        """
        Create a location for an XLSX cell.

        Args:
            file_id: Unique identifier for the file
            sheet: Sheet name
            cell: Cell address (e.g., "A1")
            row: Row number (0-indexed)
            column: Column number (0-indexed)

        Returns:
            DocumentLocation configured for XLSX cell
        """
        return cls(
            component=DocumentComponent.XLSX_CELL,
            file_id=file_id,
            file_type="xlsx",
            sheet=sheet,
            cell=cell,
            row=row,
            column=column,
        )

    @classmethod
    def for_csv_cell(
        cls,
        file_id: str,
        row: int,
        column: int,
        cell: str | None = None,
    ) -> DocumentLocation:
        """
        Create a location for a CSV cell.

        Args:
            file_id: Unique identifier for the file
            row: Row number (0-indexed)
            column: Column number (0-indexed)
            cell: Optional cell reference

        Returns:
            DocumentLocation configured for CSV cell
        """
        return cls(
            component=DocumentComponent.CSV_CELL,
            file_id=file_id,
            file_type="csv",
            row=row,
            column=column,
            cell=cell,
        )
