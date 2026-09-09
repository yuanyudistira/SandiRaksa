"""
Spatial Context for PII Detection.

This module provides position-based context analysis, primarily for
PowerPoint presentations where label-value relationships are often
based on spatial proximity rather than explicit structure.

Key concepts:
- Horizontal alignment: Label to the left of value
- Vertical alignment: Label above value
- Same baseline: Text on same horizontal line
- Proximity threshold: Maximum distance for context relationship
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sandiraksa.documents.logical_segment import LogicalSegment


class SpatialRelation(str, Enum):
    """Spatial relationship between elements."""

    LEFT_OF = "left_of"       # Label is to the left of value
    RIGHT_OF = "right_of"     # Label is to the right of value
    ABOVE = "above"           # Label is above value
    BELOW = "below"           # Label is below value
    SAME_LINE = "same_line"   # On same horizontal baseline
    SAME_COLUMN = "same_column"  # In same vertical alignment
    ADJACENT = "adjacent"     # Close but not aligned
    DISTANT = "distant"       # Too far for relationship


@dataclass
class BoundingBox:
    """
    Rectangular bounding box for a shape/element.

    Coordinates are in EMU (English Metric Units) or pixels,
    consistent within a document.
    """

    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        """Right edge x-coordinate."""
        return self.left + self.width

    @property
    def bottom(self) -> float:
        """Bottom edge y-coordinate."""
        return self.top + self.height

    @property
    def center_x(self) -> float:
        """Horizontal center."""
        return self.left + self.width / 2

    @property
    def center_y(self) -> float:
        """Vertical center."""
        return self.top + self.height / 2

    def distance_to(self, other: "BoundingBox") -> float:
        """Calculate minimum distance between two boxes."""
        # Horizontal distance
        if self.right < other.left:
            dx = other.left - self.right
        elif other.right < self.left:
            dx = self.left - other.right
        else:
            dx = 0  # Overlapping horizontally

        # Vertical distance
        if self.bottom < other.top:
            dy = other.top - self.bottom
        elif other.bottom < self.top:
            dy = self.top - other.bottom
        else:
            dy = 0  # Overlapping vertically

        return math.sqrt(dx * dx + dy * dy)

    def is_same_baseline(
        self,
        other: "BoundingBox",
        tolerance: float = 20.0,
    ) -> bool:
        """Check if two boxes share same horizontal baseline."""
        # Compare vertical centers
        return abs(self.center_y - other.center_y) <= tolerance

    def is_same_column(
        self,
        other: "BoundingBox",
        tolerance: float = 20.0,
    ) -> bool:
        """Check if two boxes are in same vertical column."""
        # Compare horizontal centers
        return abs(self.center_x - other.center_x) <= tolerance


@dataclass
class SpatialElement:
    """
    An element with spatial position and text content.

    Used to represent shapes in PowerPoint or positioned
    elements in other formats.
    """

    id: str
    text: str
    bounds: BoundingBox
    element_type: str = "shape"  # shape, textbox, placeholder, etc.
    is_label_like: bool = False  # Detected as label (short text, ends with :)


@dataclass
class SpatialRelationship:
    """A spatial relationship between two elements."""

    source: SpatialElement  # The value element
    target: SpatialElement  # The potential label element
    relation: SpatialRelation
    distance: float
    confidence: float = 0.0


@dataclass
class SpatialContext:
    """
    Spatial context analysis result.

    Attributes:
        nearby_labels: Labels spatially related to the segment
        relationships: All detected spatial relationships
        slide_context: Slide-level context (title, layout)
    """

    nearby_labels: list[SpatialElement] = field(default_factory=list)
    relationships: list[SpatialRelationship] = field(default_factory=list)
    slide_title: str | None = None
    slide_layout: str | None = None

    def get_best_label(self) -> SpatialElement | None:
        """Get the most likely label for this value."""
        if not self.relationships:
            return None

        # Priority: same_line left_of > above > adjacent
        priority = [
            SpatialRelation.LEFT_OF,
            SpatialRelation.ABOVE,
            SpatialRelation.SAME_LINE,
            SpatialRelation.ADJACENT,
        ]

        for relation_type in priority:
            for rel in self.relationships:
                if rel.relation == relation_type and rel.target.is_label_like:
                    return rel.target

        # Fall back to closest label-like element
        label_rels = [
            r for r in self.relationships if r.target.is_label_like
        ]
        if label_rels:
            return min(label_rels, key=lambda r: r.distance).target

        return None

    def get_context_texts(self) -> list[str]:
        """Get all nearby label texts."""
        return [label.text for label in self.nearby_labels if label.text]


class SpatialContextAnalyzer:
    """
    Analyzes spatial relationships for context extraction.

    Primarily designed for PowerPoint presentations where
    label-value relationships are position-based.
    """

    # Default proximity threshold (in EMU or consistent units)
    DEFAULT_PROXIMITY = 914400  # ~1 inch in EMU
    BASELINE_TOLERANCE = 50000  # ~0.05 inch

    def __init__(
        self,
        proximity_threshold: float | None = None,
        baseline_tolerance: float | None = None,
    ):
        """
        Initialize analyzer.

        Args:
            proximity_threshold: Max distance for relationship
            baseline_tolerance: Tolerance for same-line detection
        """
        self.proximity_threshold = proximity_threshold or self.DEFAULT_PROXIMITY
        self.baseline_tolerance = baseline_tolerance or self.BASELINE_TOLERANCE

    def analyze(
        self,
        target: SpatialElement,
        candidates: list[SpatialElement],
    ) -> SpatialContext:
        """
        Analyze spatial context for a target element.

        Args:
            target: The element containing potential PII
            candidates: Other elements on the same slide/page

        Returns:
            SpatialContext with relationships and labels
        """
        result = SpatialContext()

        for candidate in candidates:
            if candidate.id == target.id:
                continue

            relationship = self._analyze_relationship(target, candidate)
            if relationship.relation != SpatialRelation.DISTANT:
                result.relationships.append(relationship)
                if candidate.is_label_like:
                    result.nearby_labels.append(candidate)

        # Sort by distance
        result.relationships.sort(key=lambda r: r.distance)
        result.nearby_labels.sort(
            key=lambda e: target.bounds.distance_to(e.bounds)
        )

        return result

    def _analyze_relationship(
        self,
        source: SpatialElement,
        target: SpatialElement,
    ) -> SpatialRelationship:
        """Analyze spatial relationship between two elements."""
        distance = source.bounds.distance_to(target.bounds)

        # Check if too far
        if distance > self.proximity_threshold:
            return SpatialRelationship(
                source=source,
                target=target,
                relation=SpatialRelation.DISTANT,
                distance=distance,
                confidence=0.0,
            )

        # Determine relationship type
        relation = self._determine_relation(source, target)

        # Calculate confidence based on distance and relationship
        confidence = self._calculate_confidence(relation, distance)

        return SpatialRelationship(
            source=source,
            target=target,
            relation=relation,
            distance=distance,
            confidence=confidence,
        )

    def _determine_relation(
        self,
        source: SpatialElement,
        target: SpatialElement,
    ) -> SpatialRelation:
        """Determine the spatial relationship type."""
        src = source.bounds
        tgt = target.bounds

        # Check same baseline first
        same_baseline = src.is_same_baseline(tgt, self.baseline_tolerance)
        same_column = src.is_same_column(tgt, self.baseline_tolerance)

        if same_baseline:
            if tgt.right <= src.left:
                return SpatialRelation.LEFT_OF
            elif tgt.left >= src.right:
                return SpatialRelation.RIGHT_OF
            else:
                return SpatialRelation.SAME_LINE

        if same_column:
            if tgt.bottom <= src.top:
                return SpatialRelation.ABOVE
            elif tgt.top >= src.bottom:
                return SpatialRelation.BELOW
            else:
                return SpatialRelation.SAME_COLUMN

        return SpatialRelation.ADJACENT

    def _calculate_confidence(
        self,
        relation: SpatialRelation,
        distance: float,
    ) -> float:
        """Calculate confidence score for a relationship."""
        # Base confidence by relationship type
        base_confidence = {
            SpatialRelation.LEFT_OF: 0.9,
            SpatialRelation.ABOVE: 0.8,
            SpatialRelation.SAME_LINE: 0.7,
            SpatialRelation.SAME_COLUMN: 0.6,
            SpatialRelation.RIGHT_OF: 0.4,
            SpatialRelation.BELOW: 0.3,
            SpatialRelation.ADJACENT: 0.5,
            SpatialRelation.DISTANT: 0.0,
        }

        base = base_confidence.get(relation, 0.5)

        # Decay with distance
        if distance > 0:
            decay = 1.0 - (distance / self.proximity_threshold)
            decay = max(0.0, decay)
            return base * decay

        return base


def is_label_like(text: str) -> bool:
    """
    Determine if text looks like a label.

    Labels typically:
    - Are short (< 50 chars)
    - May end with : or similar
    - Don't contain long sentences
    - May be all caps or title case
    """
    if not text or len(text) > 50:
        return False

    text = text.strip()

    # Ends with colon or similar
    if text.endswith(":") or text.endswith("："):
        return True

    # Short text (likely label)
    if len(text) <= 20:
        # Contains keyword
        label_keywords = [
            "nama", "nik", "npwp", "telepon", "alamat", "email",
            "name", "phone", "address", "id", "no.", "nomor",
        ]
        text_lower = text.lower()
        if any(kw in text_lower for kw in label_keywords):
            return True

    # All caps short text
    if text.isupper() and len(text) <= 30:
        return True

    return False


def create_spatial_element(
    shape_id: str,
    text: str,
    left: float,
    top: float,
    width: float,
    height: float,
    element_type: str = "shape",
) -> SpatialElement:
    """
    Convenience function to create a SpatialElement.

    Args:
        shape_id: Unique identifier for the shape
        text: Text content
        left, top, width, height: Position and size
        element_type: Type of element

    Returns:
        SpatialElement instance
    """
    bounds = BoundingBox(
        left=left,
        top=top,
        width=width,
        height=height,
    )
    return SpatialElement(
        id=shape_id,
        text=text,
        bounds=bounds,
        element_type=element_type,
        is_label_like=is_label_like(text),
    )


def extract_spatial_context_from_segment(
    segment: "LogicalSegment",
) -> SpatialContext:
    """
    Extract spatial context from a segment's nearby_labels.

    This is a simplified extraction when full spatial analysis
    is not available (e.g., labels already extracted).

    Args:
        segment: LogicalSegment with nearby_labels

    Returns:
        SpatialContext with available information
    """
    result = SpatialContext()

    # Get nearby labels from segment
    nearby_labels = getattr(segment, "nearby_labels", [])
    for label_text in nearby_labels:
        if label_text and label_text.strip():
            result.nearby_labels.append(
                SpatialElement(
                    id=f"label_{hash(label_text)}",
                    text=label_text,
                    bounds=BoundingBox(0, 0, 0, 0),  # Unknown position
                    is_label_like=True,
                )
            )

    # Get slide title if available
    result.slide_title = getattr(segment, "slide_title", None)

    return result


__all__ = [
    "SpatialRelation",
    "BoundingBox",
    "SpatialElement",
    "SpatialRelationship",
    "SpatialContext",
    "SpatialContextAnalyzer",
    "is_label_like",
    "create_spatial_element",
    "extract_spatial_context_from_segment",
]
