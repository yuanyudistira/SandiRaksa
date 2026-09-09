"""
Finding domain model.

Represents a detected sensitive data item in a document.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass


class ConfidenceBand(str, Enum):
    """Confidence levels for detection."""

    CRITICAL = "critical"  # Exact match / deny-list
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewAction(str, Enum):
    """User review actions for a finding."""

    PENDING = "pending"
    PROTECT = "protect"
    ALLOW = "allow"
    CHANGE_TYPE = "change_type"
    CHANGE_TREATMENT = "change_treatment"


class ReviewScope(str, Enum):
    """Scope of a review decision."""

    OCCURRENCE = "occurrence"  # This occurrence only
    SAME_VALUE_FILE = "same_value_file"  # All same values in file
    SAME_VALUE_PROJECT = "same_value_project"  # All same values in project


@dataclass
class DocumentLocation:
    """Location of a finding within a document."""

    # Common fields
    file_id: str = ""
    component_type: str = ""  # e.g., "cell", "paragraph", "text_box", "note"

    # For text-based locations
    start_offset: int | None = None
    end_offset: int | None = None

    # For structured documents
    sheet_name: str | None = None  # XLSX
    cell_address: str | None = None  # XLSX: "A1", "B2"
    paragraph_index: int | None = None  # DOCX
    slide_number: int | None = None  # PPTX
    shape_id: str | None = None  # PPTX

    # Run information for OOXML
    run_indices: list[int] = field(default_factory=list)

    # Legacy aliases (deprecated - use component_type/cell_address)
    element_type: str | None = None  # Alias for component_type
    element_id: str | None = None  # Alias for cell_address
    row_number: int | None = None  # Legacy field
    column_number: int | None = None  # Legacy field
    column_name: str | None = None  # Legacy field

    def __post_init__(self):
        """Handle legacy field mapping."""
        # Map legacy element_type to component_type
        if self.element_type and not self.component_type:
            self.component_type = self.element_type
        elif self.component_type and not self.element_type:
            self.element_type = self.component_type

        # Map legacy element_id to cell_address
        if self.element_id and not self.cell_address:
            self.cell_address = self.element_id
        elif self.cell_address and not self.element_id:
            self.element_id = self.cell_address

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            k: v for k, v in {
                "file_id": self.file_id,
                "component_type": self.component_type,
                "start_offset": self.start_offset,
                "end_offset": self.end_offset,
                "sheet_name": self.sheet_name,
                "cell_address": self.cell_address,
                "paragraph_index": self.paragraph_index,
                "slide_number": self.slide_number,
                "shape_id": self.shape_id,
                "run_indices": self.run_indices if self.run_indices else None,
            }.items() if v is not None
        }

    @property
    def display_location(self) -> str:
        """Get human-readable location string."""
        parts = []
        if self.sheet_name:
            parts.append(f"Sheet: {self.sheet_name}")
        if self.cell_address:
            parts.append(f"Cell: {self.cell_address}")
        if self.slide_number:
            parts.append(f"Slide: {self.slide_number}")
        if self.paragraph_index is not None:
            parts.append(f"Para: {self.paragraph_index + 1}")
        parts.append(self.component_type)
        return " | ".join(parts)


class Finding(BaseModel):
    """
    Domain model for a detected sensitive data item.

    Findings are transient during processing and not stored
    in the database with raw values.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    entity_type: str  # e.g., "PERSON", "EMAIL", "NIK"
    score: float | None = None  # 0.0 - 1.0
    confidence_band: ConfidenceBand = ConfidenceBand.MEDIUM
    detector: str  # Which detector found this

    # Location within document
    file_id: str
    location: dict[str, Any]  # Serialized DocumentLocation

    # The detected text (only held in memory during review)
    # NEVER persist this to database
    detected_text: str = ""

    # Context for display (truncated, no full raw value)
    context_before: str = ""
    context_after: str = ""

    # Detection reasoning
    reason_codes: list[str] = Field(default_factory=list)

    # Review decision
    review_action: ReviewAction = ReviewAction.PENDING
    review_scope: ReviewScope = ReviewScope.OCCURRENCE

    # Treatment override
    treatment_override: str | None = None
    entity_type_override: str | None = None

    # Hash for deduplication (not the raw value)
    text_hash: str = ""

    class Config:
        """Pydantic configuration."""

        use_enum_values = True

    @property
    def effective_entity_type(self) -> str:
        """Get the effective entity type (considering override)."""
        return self.entity_type_override or self.entity_type

    @property
    def is_pending(self) -> bool:
        """Check if finding needs review."""
        return self.review_action == ReviewAction.PENDING

    @property
    def should_protect(self) -> bool:
        """Check if finding should be protected."""
        return self.review_action in {ReviewAction.PROTECT, ReviewAction.PENDING}

    def apply_decision(
        self,
        action: ReviewAction,
        scope: ReviewScope = ReviewScope.OCCURRENCE,
        *,
        entity_type_override: str | None = None,
        treatment_override: str | None = None,
    ) -> None:
        """Apply a review decision to this finding."""
        self.review_action = action
        self.review_scope = scope
        if entity_type_override:
            self.entity_type_override = entity_type_override
        if treatment_override:
            self.treatment_override = treatment_override


@dataclass
class FindingGroup:
    """Group of findings with the same value for bulk operations."""

    text_hash: str
    entity_type: str
    count: int
    findings: list[Finding]
    sample_context: str = ""  # Truncated sample for display

    @property
    def all_same_file(self) -> bool:
        """Check if all findings are in the same file."""
        file_ids = {f.file_id for f in self.findings}
        return len(file_ids) == 1


@dataclass
class DetectionExplanation:
    """Explanation for why something was detected."""

    finding_id: str
    entity_type: str
    confidence_band: ConfidenceBand
    detector: str
    reasons: list[str]

    def to_display_text(self) -> str:
        """Generate human-readable explanation."""
        lines = [
            f"Type: {self.entity_type}",
            f"Confidence: {self.confidence_band.value.title()}",
            "",
            "Why:",
        ]
        for reason in self.reasons:
            lines.append(f"• {reason}")
        return "\n".join(lines)
