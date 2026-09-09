"""
Unified Finding model for SandiRaksa detection pipeline.

This module provides the core Finding model used by the unified detection
engine. It includes evidence tracking for explainability and confidence
scoring.

Key Design:
- Finding is the output of detection
- ConfidenceEvidence tracks why something was detected
- ConfidenceBand provides user-friendly confidence levels
- Detector source is tracked for debugging
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ConfidenceBand(str, Enum):
    """
    Confidence levels for detection results.

    These are user-facing labels, not raw scores.
    Internal scores (0.0-1.0) are mapped to these bands.
    """

    HIGH = "high"        # Strong evidence, high confidence
    MEDIUM = "medium"    # Moderate evidence
    LOW = "low"          # Weak evidence, may be false positive
    CRITICAL = "critical"  # Exact match from deny list


class EvidenceType(str, Enum):
    """Types of evidence that support a detection."""

    PATTERN_MATCH = "pattern_match"           # Regex/pattern matched
    STRUCTURAL_VALID = "structural_valid"     # Structure validated (e.g., NIK format)
    SEMANTIC_VALID = "semantic_valid"         # Semantic validation passed
    CONTEXT_POSITIVE = "context_positive"     # Positive context found
    CONTEXT_NEGATIVE = "context_negative"     # Negative context found
    NER_DETECTION = "ner_detection"           # NER model detected
    CUSTOM_TERM = "custom_term"               # Custom term list match
    PRESIDIO = "presidio"                     # Presidio detected
    CHECKSUM_VALID = "checksum_valid"         # Checksum validation passed


@dataclass
class ConfidenceEvidence:
    """
    Evidence supporting a detection result.

    Each evidence item contributes to the overall confidence score.
    Evidence is used for explainability in the UI.

    Attributes:
        evidence_type: Type of evidence
        source: Source recognizer/detector name
        weight: Weight contribution (positive or negative)
        reason_code: Machine-readable reason code
        description: Human-readable description
    """

    evidence_type: EvidenceType
    source: str
    weight: float  # Can be negative for negative evidence
    reason_code: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.evidence_type.value,
            "source": self.source,
            "weight": self.weight,
            "reason_code": self.reason_code,
            "description": self.description,
        }


class UnifiedFinding(BaseModel):
    """
    A detected PII entity from the unified detection pipeline.

    This is the primary output of the detection engine. Each Finding
    represents a potential PII item with:
    - Location in the document (via segment reference)
    - Entity type and detected value
    - Confidence score and band
    - Evidence explaining why it was detected

    Attributes:
        id: Unique identifier for this finding
        segment_id: ID of the LogicalSegment containing this finding
        entity_type: Type of entity (PERSON, EMAIL, NIK, etc.)

        start: Start position in the segment's logical text
        end: End position in the segment's logical text

        raw_score: Internal confidence score (0.0-1.0)
        confidence_band: User-facing confidence level
        detector: Name of the detector that found this

        evidence: List of evidence items explaining the detection
        reason_codes: Summary list of reason codes

        detected_text: The actual detected text (sensitive!)
        context_before: Text before the detection (truncated)
        context_after: Text after the detection (truncated)

        # Metadata
        is_from_custom_terms: Whether from custom terms list
        is_validated: Whether structural/semantic validation passed
    """

    # Identity
    id: str = Field(default_factory=lambda: str(uuid4()))
    segment_id: str = Field(description="ID of source LogicalSegment")
    entity_type: str = Field(description="Entity type (PERSON, EMAIL, NIK, etc.)")

    # Position in logical text
    start: int = Field(ge=0, description="Start position in segment text")
    end: int = Field(ge=0, description="End position in segment text")

    # Confidence
    raw_score: float = Field(
        ge=0.0, le=1.0, description="Internal confidence score"
    )
    confidence_band: ConfidenceBand = Field(
        default=ConfidenceBand.MEDIUM,
        description="User-facing confidence level",
    )
    detector: str = Field(description="Name of detector that found this")

    # Evidence for explainability
    evidence: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Evidence items explaining the detection",
    )
    reason_codes: list[str] = Field(
        default_factory=list,
        description="Summary of reason codes",
    )

    # Detected content (handle carefully!)
    detected_text: str = Field(
        default="",
        description="The detected text (sensitive, don't persist)",
    )
    context_before: str = Field(
        default="",
        description="Text before detection (truncated)",
    )
    context_after: str = Field(
        default="",
        description="Text after detection (truncated)",
    )

    # Metadata
    is_from_custom_terms: bool = Field(
        default=False,
        description="Whether from custom terms list",
    )
    is_validated: bool = Field(
        default=False,
        description="Whether structural/semantic validation passed",
    )

    model_config = {"extra": "forbid"}

    @property
    def length(self) -> int:
        """Get the length of the detected text."""
        return self.end - self.start

    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high confidence detection."""
        return self.confidence_band in (ConfidenceBand.HIGH, ConfidenceBand.CRITICAL)

    def add_evidence(self, evidence: ConfidenceEvidence) -> None:
        """Add evidence to this finding."""
        self.evidence.append(evidence.to_dict())
        if evidence.reason_code not in self.reason_codes:
            self.reason_codes.append(evidence.reason_code)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "segment_id": self.segment_id,
            "entity_type": self.entity_type,
            "start": self.start,
            "end": self.end,
            "raw_score": self.raw_score,
            "confidence_band": self.confidence_band.value,
            "detector": self.detector,
            "evidence": self.evidence,
            "reason_codes": self.reason_codes,
            "context_before": self.context_before,
            "context_after": self.context_after,
        }

    @classmethod
    def from_presidio_result(
        cls,
        result: Any,  # presidio RecognizerResult
        segment_id: str,
        detected_text: str,
        context_before: str = "",
        context_after: str = "",
    ) -> "UnifiedFinding":
        """
        Create a Finding from a Presidio RecognizerResult.

        Args:
            result: Presidio RecognizerResult
            segment_id: ID of the source segment
            detected_text: The detected text
            context_before: Text before detection
            context_after: Text after detection

        Returns:
            UnifiedFinding instance
        """
        # Map Presidio score to confidence band
        score = result.score
        if score >= 0.85:
            band = ConfidenceBand.HIGH
        elif score >= 0.6:
            band = ConfidenceBand.MEDIUM
        else:
            band = ConfidenceBand.LOW

        finding = cls(
            segment_id=segment_id,
            entity_type=result.entity_type,
            start=result.start,
            end=result.end,
            raw_score=score,
            confidence_band=band,
            detector=result.recognition_metadata.get("recognizer_name", "presidio")
            if hasattr(result, "recognition_metadata")
            else "presidio",
            detected_text=detected_text,
            context_before=context_before,
            context_after=context_after,
        )

        # Add evidence
        finding.add_evidence(
            ConfidenceEvidence(
                evidence_type=EvidenceType.PRESIDIO,
                source="presidio",
                weight=score,
                reason_code="presidio_detected",
                description=f"Presidio detected {result.entity_type}",
            )
        )

        return finding

    @classmethod
    def from_regex_match(
        cls,
        entity_type: str,
        start: int,
        end: int,
        detected_text: str,
        segment_id: str,
        recognizer_name: str,
        score: float = 0.7,
        context_before: str = "",
        context_after: str = "",
    ) -> "UnifiedFinding":
        """
        Create a Finding from a regex pattern match.

        Args:
            entity_type: Type of entity detected
            start: Start position
            end: End position
            detected_text: The matched text
            segment_id: Source segment ID
            recognizer_name: Name of the recognizer
            score: Confidence score
            context_before: Text before detection
            context_after: Text after detection

        Returns:
            UnifiedFinding instance
        """
        # Map score to band
        if score >= 0.85:
            band = ConfidenceBand.HIGH
        elif score >= 0.6:
            band = ConfidenceBand.MEDIUM
        else:
            band = ConfidenceBand.LOW

        finding = cls(
            segment_id=segment_id,
            entity_type=entity_type,
            start=start,
            end=end,
            raw_score=score,
            confidence_band=band,
            detector=recognizer_name,
            detected_text=detected_text,
            context_before=context_before,
            context_after=context_after,
        )

        finding.add_evidence(
            ConfidenceEvidence(
                evidence_type=EvidenceType.PATTERN_MATCH,
                source=recognizer_name,
                weight=score,
                reason_code="pattern_matched",
                description=f"Pattern matched for {entity_type}",
            )
        )

        return finding

    @classmethod
    def from_custom_term(
        cls,
        term: str,
        start: int,
        end: int,
        segment_id: str,
        entity_type: str = "CUSTOM",
    ) -> "UnifiedFinding":
        """
        Create a Finding from a custom term match.

        Custom terms always have CRITICAL confidence as they are
        explicitly defined by the user.

        Args:
            term: The matched term
            start: Start position
            end: End position
            segment_id: Source segment ID
            entity_type: Entity type (default CUSTOM)

        Returns:
            UnifiedFinding instance
        """
        return cls(
            segment_id=segment_id,
            entity_type=entity_type,
            start=start,
            end=end,
            raw_score=1.0,
            confidence_band=ConfidenceBand.CRITICAL,
            detector="custom_terms",
            detected_text=term,
            is_from_custom_terms=True,
            evidence=[
                {
                    "type": EvidenceType.CUSTOM_TERM.value,
                    "source": "custom_terms",
                    "weight": 1.0,
                    "reason_code": "custom_term_match",
                    "description": f"Matched custom term",
                }
            ],
            reason_codes=["custom_term_match"],
        )


def classify_confidence(score: float) -> ConfidenceBand:
    """
    Classify a raw score into a confidence band.

    Args:
        score: Raw confidence score (0.0-1.0)

    Returns:
        Appropriate ConfidenceBand
    """
    if score >= 0.85:
        return ConfidenceBand.HIGH
    elif score >= 0.6:
        return ConfidenceBand.MEDIUM
    else:
        return ConfidenceBand.LOW


__all__ = [
    "ConfidenceBand",
    "ConfidenceEvidence",
    "EvidenceType",
    "UnifiedFinding",
    "classify_confidence",
]
