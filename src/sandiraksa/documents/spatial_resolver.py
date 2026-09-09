"""
Spatial Context Resolver for PowerPoint documents.

In PowerPoint, meaning is often expressed spatially through positioning.
For example:

    [NIK]           [3271051708990001]
    [Nama]          [Satria Putra]
    [Alamat]        [Jl. Sudirman No. 123]

The label "NIK" is spatially associated with the value "3271051708990001"
because they share the same horizontal baseline.

This module provides algorithms to detect such spatial relationships
and attach context labels to detected values.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class ShapePosition:
    """
    Position and dimensions of a shape for spatial analysis.

    All measurements are in EMUs (English Metric Units).
    1 inch = 914400 EMUs
    """

    shape_id: str
    text: str
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        """Right edge position."""
        return self.left + self.width

    @property
    def bottom(self) -> int:
        """Bottom edge position."""
        return self.top + self.height

    @property
    def center_x(self) -> int:
        """Horizontal center."""
        return self.left + self.width // 2

    @property
    def center_y(self) -> int:
        """Vertical center."""
        return self.top + self.height // 2

    @property
    def vertical_center(self) -> int:
        """Alias for center_y (baseline approximation)."""
        return self.center_y


# Distance thresholds in EMUs
# 914400 EMU = 1 inch
HORIZONTAL_PROXIMITY_THRESHOLD = 2743200  # ~3 inches
VERTICAL_PROXIMITY_THRESHOLD = 457200     # ~0.5 inch
SAME_BASELINE_TOLERANCE = 228600          # ~0.25 inch


def is_potential_label(text: str) -> bool:
    """
    Check if text looks like a label.

    Labels are typically:
    - Short (< 30 chars)
    - May end with ':'
    - Single word or 2-3 words
    - Title case or uppercase

    Args:
        text: Text to check

    Returns:
        True if text looks like a label
    """
    text = text.strip()

    if not text:
        return False

    # Remove trailing colon for analysis
    clean = text.rstrip(':').strip()

    # Too long for a label
    if len(clean) > 30:
        return False

    # Too many words
    words = clean.split()
    if len(words) > 4:
        return False

    # Single short word is likely a label
    if len(words) == 1 and len(clean) <= 20:
        return True

    # Multiple words but short total length
    if len(clean) <= 25:
        return True

    return False


def distance_between(pos1: ShapePosition, pos2: ShapePosition) -> float:
    """
    Calculate Euclidean distance between shape centers.

    Args:
        pos1: First shape position
        pos2: Second shape position

    Returns:
        Distance in EMUs
    """
    dx = pos1.center_x - pos2.center_x
    dy = pos1.center_y - pos2.center_y
    return (dx * dx + dy * dy) ** 0.5


def are_on_same_baseline(
    pos1: ShapePosition,
    pos2: ShapePosition,
    tolerance: int = SAME_BASELINE_TOLERANCE,
) -> bool:
    """
    Check if two shapes are on approximately the same horizontal baseline.

    Args:
        pos1: First shape position
        pos2: Second shape position
        tolerance: Maximum vertical difference allowed

    Returns:
        True if shapes are on same baseline
    """
    return abs(pos1.vertical_center - pos2.vertical_center) <= tolerance


def is_left_adjacent(
    label_pos: ShapePosition,
    value_pos: ShapePosition,
    max_gap: int = HORIZONTAL_PROXIMITY_THRESHOLD,
) -> bool:
    """
    Check if label is immediately to the left of value.

    Args:
        label_pos: Position of potential label
        value_pos: Position of potential value
        max_gap: Maximum horizontal gap allowed

    Returns:
        True if label is left-adjacent to value
    """
    # Label must be to the left
    if label_pos.center_x >= value_pos.center_x:
        return False

    # Must be on same baseline
    if not are_on_same_baseline(label_pos, value_pos):
        return False

    # Check horizontal gap
    gap = value_pos.left - label_pos.right
    return 0 <= gap <= max_gap


def is_above(
    label_pos: ShapePosition,
    value_pos: ShapePosition,
    max_gap: int = VERTICAL_PROXIMITY_THRESHOLD,
) -> bool:
    """
    Check if label is directly above value.

    Args:
        label_pos: Position of potential label
        value_pos: Position of potential value
        max_gap: Maximum vertical gap allowed

    Returns:
        True if label is above value
    """
    # Label must be above
    if label_pos.center_y >= value_pos.center_y:
        return False

    # Should have similar horizontal position (overlapping or close)
    horizontal_overlap = (
        label_pos.left < value_pos.right and
        label_pos.right > value_pos.left
    )
    if not horizontal_overlap:
        # Check if centers are close horizontally
        if abs(label_pos.center_x - value_pos.center_x) > label_pos.width:
            return False

    # Check vertical gap
    gap = value_pos.top - label_pos.bottom
    return 0 <= gap <= max_gap


class SpatialContextResolver:
    """
    Resolves spatial relationships between shapes in PowerPoint.

    Given a target shape, finds nearby shapes that might be labels
    providing context for PII detection.
    """

    def __init__(
        self,
        horizontal_threshold: int = HORIZONTAL_PROXIMITY_THRESHOLD,
        vertical_threshold: int = VERTICAL_PROXIMITY_THRESHOLD,
        baseline_tolerance: int = SAME_BASELINE_TOLERANCE,
    ):
        """
        Initialize the resolver.

        Args:
            horizontal_threshold: Max horizontal distance for adjacency
            vertical_threshold: Max vertical distance for above/below
            baseline_tolerance: Tolerance for same-baseline detection
        """
        self.horizontal_threshold = horizontal_threshold
        self.vertical_threshold = vertical_threshold
        self.baseline_tolerance = baseline_tolerance

    def get_nearby_labels(
        self,
        target: ShapePosition,
        all_shapes: list[ShapePosition],
        max_labels: int = 3,
    ) -> list[str]:
        """
        Find labels that are spatially associated with the target shape.

        Priority order:
        1. Left-adjacent on same baseline (highest)
        2. Directly above
        3. Nearby on same baseline

        Args:
            target: The shape to find labels for
            all_shapes: All shapes on the same slide
            max_labels: Maximum number of labels to return

        Returns:
            List of label texts, ordered by relevance
        """
        candidates: list[tuple[str, float, str]] = []  # (text, score, reason)

        for shape in all_shapes:
            # Skip self
            if shape.shape_id == target.shape_id:
                continue

            # Skip if not a potential label
            if not is_potential_label(shape.text):
                continue

            # Check left-adjacent (highest priority)
            if is_left_adjacent(shape, target, self.horizontal_threshold):
                # Score based on horizontal distance
                dist = target.left - shape.right
                score = 100.0 - (dist / self.horizontal_threshold * 50)
                candidates.append((shape.text, score, "left_adjacent"))
                continue

            # Check directly above (second priority)
            if is_above(shape, target, self.vertical_threshold):
                dist = target.top - shape.bottom
                score = 80.0 - (dist / self.vertical_threshold * 30)
                candidates.append((shape.text, score, "above"))
                continue

            # Check same baseline but further away
            if are_on_same_baseline(shape, target, self.baseline_tolerance):
                dist = distance_between(shape, target)
                if dist <= self.horizontal_threshold * 2:
                    score = 50.0 - (dist / self.horizontal_threshold * 25)
                    candidates.append((shape.text, score, "same_baseline"))

        # Sort by score (descending) and take top N
        candidates.sort(key=lambda x: x[1], reverse=True)

        labels = []
        for text, score, reason in candidates[:max_labels]:
            # Clean up label text
            clean_text = text.strip().rstrip(':').strip()
            if clean_text and clean_text not in labels:
                labels.append(clean_text)
                logger.debug(
                    f"Found label '{clean_text}' for shape {target.shape_id} "
                    f"(reason={reason}, score={score:.1f})"
                )

        return labels

    def find_slide_title(
        self,
        all_shapes: list[ShapePosition],
    ) -> str | None:
        """
        Find the slide title from shape positions.

        The title is typically:
        - Near the top of the slide
        - Larger or more prominent
        - Short text

        Args:
            all_shapes: All shapes on the slide

        Returns:
            Title text or None
        """
        # Find shapes near the top (first 20% of vertical space)
        if not all_shapes:
            return None

        # Sort by vertical position
        sorted_shapes = sorted(all_shapes, key=lambda s: s.top)

        # Take shapes in the top portion
        top_shapes = [s for s in sorted_shapes[:5] if is_potential_label(s.text)]

        if top_shapes:
            # Return the first one (topmost)
            return top_shapes[0].text.strip()

        return None


def extract_shape_positions(
    shapes: list[dict],
) -> list[ShapePosition]:
    """
    Convert shape info dictionaries to ShapePosition objects.

    Args:
        shapes: List of shape info dicts with shape_id, text, left, top, width, height

    Returns:
        List of ShapePosition objects
    """
    positions = []

    for shape in shapes:
        try:
            pos = ShapePosition(
                shape_id=str(shape.get('shape_id', '')),
                text=shape.get('text', ''),
                left=shape.get('left', 0) or 0,
                top=shape.get('top', 0) or 0,
                width=shape.get('width', 0) or 0,
                height=shape.get('height', 0) or 0,
            )
            positions.append(pos)
        except Exception as e:
            logger.warning(f"Failed to create ShapePosition: {e}")

    return positions


__all__ = [
    "ShapePosition",
    "SpatialContextResolver",
    "is_potential_label",
    "is_left_adjacent",
    "is_above",
    "are_on_same_baseline",
    "distance_between",
    "extract_shape_positions",
    "HORIZONTAL_PROXIMITY_THRESHOLD",
    "VERTICAL_PROXIMITY_THRESHOLD",
    "SAME_BASELINE_TOLERANCE",
]
