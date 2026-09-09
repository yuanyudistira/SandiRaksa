"""
Structural Context for PII Detection.

This module extracts context from document structure:
- Table headers (column/row headers)
- Document headings (Word headings, slide titles)
- Key-value labels (TXT patterns like "Nama: John")
- Section context (form sections, document parts)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sandiraksa.documents.logical_segment import LogicalSegment


class StructuralContextType(str, Enum):
    """Types of structural context."""

    TABLE_HEADER = "table_header"       # Column header in table
    ROW_HEADER = "row_header"           # Row header (first column)
    KEY_LABEL = "key_label"             # Key in key:value pattern
    DOCUMENT_HEADING = "document_heading"  # Word heading, slide title
    SECTION_TITLE = "section_title"     # Form section title
    NEARBY_LABEL = "nearby_label"       # Adjacent label text
    CELL_POSITION = "cell_position"     # Excel cell reference


@dataclass
class StructuralContextItem:
    """A single structural context item."""

    context_type: StructuralContextType
    text: str
    weight: float = 0.3  # Default structural weight
    distance: int = 0    # Distance from detected value (0 = direct)


@dataclass
class StructuralContext:
    """
    Structural context extracted from a segment.

    Attributes:
        items: List of structural context items
        has_table_context: Whether table headers present
        has_label_context: Whether key/value label present
        has_heading_context: Whether document heading present
        primary_context: Most relevant context item
    """

    items: list[StructuralContextItem] = field(default_factory=list)

    @property
    def has_table_context(self) -> bool:
        """Check if table context exists."""
        return any(
            item.context_type in (
                StructuralContextType.TABLE_HEADER,
                StructuralContextType.ROW_HEADER,
            )
            for item in self.items
        )

    @property
    def has_label_context(self) -> bool:
        """Check if key/value label context exists."""
        return any(
            item.context_type == StructuralContextType.KEY_LABEL
            for item in self.items
        )

    @property
    def has_heading_context(self) -> bool:
        """Check if heading context exists."""
        return any(
            item.context_type in (
                StructuralContextType.DOCUMENT_HEADING,
                StructuralContextType.SECTION_TITLE,
            )
            for item in self.items
        )

    @property
    def primary_context(self) -> StructuralContextItem | None:
        """Get the most relevant structural context item."""
        if not self.items:
            return None

        # Priority: key_label > table_header > row_header > heading > nearby
        priority_order = [
            StructuralContextType.KEY_LABEL,
            StructuralContextType.TABLE_HEADER,
            StructuralContextType.ROW_HEADER,
            StructuralContextType.DOCUMENT_HEADING,
            StructuralContextType.SECTION_TITLE,
            StructuralContextType.NEARBY_LABEL,
            StructuralContextType.CELL_POSITION,
        ]

        for context_type in priority_order:
            for item in self.items:
                if item.context_type == context_type:
                    return item

        return self.items[0] if self.items else None

    def get_all_context_text(self) -> list[str]:
        """Get all context texts for analysis."""
        return [item.text for item in self.items if item.text]

    def get_total_weight(self) -> float:
        """Get combined weight of all structural context."""
        return sum(item.weight for item in self.items)


class StructuralContextExtractor:
    """
    Extracts structural context from LogicalSegments.

    Analyzes segment metadata to identify structural cues
    that indicate what type of data a value represents.
    """

    # Weight assignments for different context types
    WEIGHTS: dict[StructuralContextType, float] = {
        StructuralContextType.KEY_LABEL: 0.4,        # Direct label is strong
        StructuralContextType.TABLE_HEADER: 0.35,    # Column header
        StructuralContextType.ROW_HEADER: 0.3,       # Row header
        StructuralContextType.DOCUMENT_HEADING: 0.25,  # Section heading
        StructuralContextType.SECTION_TITLE: 0.25,
        StructuralContextType.NEARBY_LABEL: 0.2,     # Adjacent label
        StructuralContextType.CELL_POSITION: 0.1,    # Weakest signal
    }

    def extract(self, segment: "LogicalSegment") -> StructuralContext:
        """
        Extract structural context from a segment.

        Args:
            segment: LogicalSegment to analyze

        Returns:
            StructuralContext with extracted items
        """
        result = StructuralContext()

        # Extract key label context (key:value pattern)
        if segment.key_label:
            result.items.append(
                StructuralContextItem(
                    context_type=StructuralContextType.KEY_LABEL,
                    text=segment.key_label,
                    weight=self.WEIGHTS[StructuralContextType.KEY_LABEL],
                    distance=0,
                )
            )

        # Extract table headers
        if segment.table_headers:
            for i, header in enumerate(segment.table_headers):
                if header and header.strip():
                    result.items.append(
                        StructuralContextItem(
                            context_type=StructuralContextType.TABLE_HEADER,
                            text=header.strip(),
                            weight=self.WEIGHTS[StructuralContextType.TABLE_HEADER],
                            distance=i,  # Column index as distance
                        )
                    )

        # Extract row headers
        if segment.row_headers:
            for i, header in enumerate(segment.row_headers):
                if header and header.strip():
                    result.items.append(
                        StructuralContextItem(
                            context_type=StructuralContextType.ROW_HEADER,
                            text=header.strip(),
                            weight=self.WEIGHTS[StructuralContextType.ROW_HEADER],
                            distance=i,
                        )
                    )

        # Extract document heading (slide title, section heading)
        heading = getattr(segment, "heading", None)
        if heading and heading.strip():
            result.items.append(
                StructuralContextItem(
                    context_type=StructuralContextType.DOCUMENT_HEADING,
                    text=heading.strip(),
                    weight=self.WEIGHTS[StructuralContextType.DOCUMENT_HEADING],
                    distance=0,
                )
            )

        # Extract slide title (PowerPoint)
        slide_title = getattr(segment, "slide_title", None)
        if slide_title and slide_title.strip():
            result.items.append(
                StructuralContextItem(
                    context_type=StructuralContextType.SECTION_TITLE,
                    text=slide_title.strip(),
                    weight=self.WEIGHTS[StructuralContextType.SECTION_TITLE],
                    distance=0,
                )
            )

        # Extract nearby labels (from context_labels)
        for label in segment.context_labels:
            # Skip if already captured as key_label
            if label == segment.key_label:
                continue
            if label and label.strip():
                result.items.append(
                    StructuralContextItem(
                        context_type=StructuralContextType.NEARBY_LABEL,
                        text=label.strip(),
                        weight=self.WEIGHTS[StructuralContextType.NEARBY_LABEL],
                        distance=1,
                    )
                )

        # Extract cell position for Excel
        location = segment.location
        if location and location.cell:
            result.items.append(
                StructuralContextItem(
                    context_type=StructuralContextType.CELL_POSITION,
                    text=location.cell,
                    weight=self.WEIGHTS[StructuralContextType.CELL_POSITION],
                    distance=0,
                )
            )

        return result


# =============================================================================
# Key-Value Pattern Detection
# =============================================================================

# Common key-value separators
KEY_VALUE_PATTERNS = [
    r"^([^:]+):\s*(.+)$",           # Key: Value
    r"^([^=]+)=\s*(.+)$",           # Key = Value
    r"^([^\t]+)\t+(.+)$",           # Key<tab>Value
    r"^([^|]+)\|\s*(.+)$",          # Key | Value
]


def extract_key_value(text: str) -> tuple[str, str] | None:
    """
    Extract key and value from a key:value pattern.

    Args:
        text: Text to analyze

    Returns:
        Tuple of (key, value) or None if no pattern found
    """
    for pattern in KEY_VALUE_PATTERNS:
        match = re.match(pattern, text.strip())
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            # Validate key is reasonable (not too long, not numeric)
            if len(key) <= 50 and not key.isdigit():
                return (key, value)
    return None


def detect_table_structure(
    texts: list[str],
    delimiter: str | None = None,
) -> dict[str, list[str]]:
    """
    Detect table-like structure in a list of texts.

    Args:
        texts: List of text lines/cells
        delimiter: Optional delimiter (auto-detect if None)

    Returns:
        Dict with 'headers' and 'rows' if table detected
    """
    if not texts or len(texts) < 2:
        return {}

    # Try common delimiters
    delimiters = [delimiter] if delimiter else [",", "\t", "|", ";"]

    for delim in delimiters:
        # Count columns in each row
        column_counts = [len(line.split(delim)) for line in texts]

        # Check if consistent column count (likely table)
        if len(set(column_counts)) == 1 and column_counts[0] > 1:
            headers = texts[0].split(delim)
            rows = [line.split(delim) for line in texts[1:]]
            return {
                "headers": [h.strip() for h in headers],
                "rows": rows,
                "delimiter": delim,
            }

    return {}


# =============================================================================
# Module-level functions
# =============================================================================

_default_extractor: StructuralContextExtractor | None = None


def get_structural_extractor() -> StructuralContextExtractor:
    """Get the default structural context extractor."""
    global _default_extractor
    if _default_extractor is None:
        _default_extractor = StructuralContextExtractor()
    return _default_extractor


def extract_structural_context(segment: "LogicalSegment") -> StructuralContext:
    """
    Convenience function to extract structural context.

    Args:
        segment: LogicalSegment to analyze

    Returns:
        StructuralContext result
    """
    return get_structural_extractor().extract(segment)


__all__ = [
    "StructuralContextType",
    "StructuralContextItem",
    "StructuralContext",
    "StructuralContextExtractor",
    "extract_key_value",
    "detect_table_structure",
    "get_structural_extractor",
    "extract_structural_context",
]
