"""
Evidence Builder for PII Detection Explainability.

Builds human-readable explanations for why PII was detected,
including positive and negative evidence that influenced the score.

Evidence Types:
- PATTERN_MATCH: Matched a regex/pattern
- STRUCTURAL_VALIDATION: Passed structural checks (checksum, format)
- CONTEXT_POSITIVE: Found positive context keywords
- CONTEXT_NEGATIVE: Found negative context keywords
- NER_DETECTION: Detected by NER model
- CUSTOM_TERM: Matched custom always-protect term
- LOCATION_CONTEXT: Found in expected location (column header, label)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sandiraksa.domain.finding import Finding

logger = logging.getLogger(__name__)


class EvidenceType(str, Enum):
    """Types of evidence for PII detection."""

    # Detection source
    PATTERN_MATCH = "pattern_match"
    STRUCTURAL_VALIDATION = "structural_validation"
    NER_DETECTION = "ner_detection"
    CUSTOM_TERM = "custom_term"

    # Context evidence
    CONTEXT_POSITIVE = "context_positive"
    CONTEXT_NEGATIVE = "context_negative"
    LOCATION_CONTEXT = "location_context"
    DOCUMENT_TYPE = "document_type"

    # Validation evidence
    CHECKSUM_VALID = "checksum_valid"
    FORMAT_VALID = "format_valid"
    REGION_VALID = "region_valid"

    # Negative evidence
    EXCLUDED_PATTERN = "excluded_pattern"
    KNOWN_FALSE_POSITIVE = "known_false_positive"

    @property
    def is_positive(self) -> bool:
        """Whether this evidence type increases confidence."""
        negative_types = {
            EvidenceType.CONTEXT_NEGATIVE,
            EvidenceType.EXCLUDED_PATTERN,
            EvidenceType.KNOWN_FALSE_POSITIVE,
        }
        return self not in negative_types

    @property
    def display_name(self) -> str:
        """Human-readable name."""
        names = {
            EvidenceType.PATTERN_MATCH: "Pattern Match",
            EvidenceType.STRUCTURAL_VALIDATION: "Structure Validated",
            EvidenceType.NER_DETECTION: "Named Entity Recognition",
            EvidenceType.CUSTOM_TERM: "Custom Protected Term",
            EvidenceType.CONTEXT_POSITIVE: "Positive Context",
            EvidenceType.CONTEXT_NEGATIVE: "Negative Context",
            EvidenceType.LOCATION_CONTEXT: "Location Context",
            EvidenceType.DOCUMENT_TYPE: "Document Type",
            EvidenceType.CHECKSUM_VALID: "Checksum Valid",
            EvidenceType.FORMAT_VALID: "Format Valid",
            EvidenceType.REGION_VALID: "Region Code Valid",
            EvidenceType.EXCLUDED_PATTERN: "Excluded Pattern",
            EvidenceType.KNOWN_FALSE_POSITIVE: "Known False Positive",
        }
        return names.get(self, self.value)


@dataclass
class Evidence:
    """
    A single piece of evidence for a PII detection.

    Attributes:
        evidence_type: Type of evidence
        description: Human-readable description
        weight: Impact on confidence (-1.0 to 1.0)
        source: Detector/component that provided this evidence
        details: Additional details (optional)
    """

    evidence_type: EvidenceType
    description: str
    weight: float  # -1.0 (strong negative) to 1.0 (strong positive)
    source: str = ""
    details: dict = field(default_factory=dict)

    @property
    def is_positive(self) -> bool:
        """Whether this is positive evidence."""
        return self.weight > 0

    @property
    def strength(self) -> str:
        """Evidence strength description."""
        abs_weight = abs(self.weight)
        if abs_weight >= 0.7:
            return "Strong"
        elif abs_weight >= 0.4:
            return "Moderate"
        else:
            return "Weak"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "type": self.evidence_type.value,
            "description": self.description,
            "weight": self.weight,
            "source": self.source,
            "is_positive": self.is_positive,
            "strength": self.strength,
            "details": self.details,
        }


@dataclass
class ExplanationResult:
    """
    Complete explanation for a PII detection.

    Contains all evidence and a human-readable summary.
    """

    entity_type: str
    entity_text: str
    raw_score: float
    confidence_band: str
    evidence: list[Evidence] = field(default_factory=list)
    summary: str = ""
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def positive_evidence(self) -> list[Evidence]:
        """Get all positive evidence."""
        return [e for e in self.evidence if e.is_positive]

    @property
    def negative_evidence(self) -> list[Evidence]:
        """Get all negative evidence."""
        return [e for e in self.evidence if not e.is_positive]

    @property
    def primary_reason(self) -> str:
        """Get the primary reason for detection."""
        if not self.evidence:
            return "Unknown"

        # Find strongest positive evidence
        positive = sorted(
            self.positive_evidence,
            key=lambda e: e.weight,
            reverse=True,
        )
        if positive:
            return positive[0].description

        return "Pattern matched"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "entity_type": self.entity_type,
            "entity_text": self.entity_text,
            "raw_score": self.raw_score,
            "confidence_band": self.confidence_band,
            "summary": self.summary,
            "primary_reason": self.primary_reason,
            "evidence": [e.to_dict() for e in self.evidence],
            "positive_count": len(self.positive_evidence),
            "negative_count": len(self.negative_evidence),
            "generated_at": self.generated_at.isoformat(),
        }


class EvidenceBuilder:
    """
    Builds evidence explanations for PII findings.

    Collects evidence from various detection stages and generates
    human-readable explanations.

    Usage:
        builder = EvidenceBuilder()

        # Add evidence during detection
        builder.add_pattern_match("NIK", "Matched 16-digit pattern")
        builder.add_structural_validation("Valid province code: 32 (Jawa Barat)")
        builder.add_context_positive("Found near label 'NIK:'")

        # Build explanation
        explanation = builder.build(finding)
    """

    def __init__(self):
        """Initialize evidence builder."""
        self._evidence: list[Evidence] = []

    def clear(self) -> None:
        """Clear accumulated evidence."""
        self._evidence = []

    def add_evidence(self, evidence: Evidence) -> "EvidenceBuilder":
        """
        Add evidence.

        Args:
            evidence: Evidence to add

        Returns:
            Self for chaining
        """
        self._evidence.append(evidence)
        return self

    def add_pattern_match(
        self,
        pattern_name: str,
        description: str | None = None,
        weight: float = 0.5,
    ) -> "EvidenceBuilder":
        """Add pattern match evidence."""
        return self.add_evidence(Evidence(
            evidence_type=EvidenceType.PATTERN_MATCH,
            description=description or f"Matched {pattern_name} pattern",
            weight=weight,
            source="regex",
            details={"pattern": pattern_name},
        ))

    def add_structural_validation(
        self,
        description: str,
        validation_type: str = "structure",
        weight: float = 0.6,
    ) -> "EvidenceBuilder":
        """Add structural validation evidence."""
        evidence_type = {
            "checksum": EvidenceType.CHECKSUM_VALID,
            "format": EvidenceType.FORMAT_VALID,
            "region": EvidenceType.REGION_VALID,
        }.get(validation_type, EvidenceType.STRUCTURAL_VALIDATION)

        return self.add_evidence(Evidence(
            evidence_type=evidence_type,
            description=description,
            weight=weight,
            source="validator",
            details={"validation_type": validation_type},
        ))

    def add_ner_detection(
        self,
        entity_type: str,
        model_name: str,
        model_score: float,
        weight: float = 0.5,
    ) -> "EvidenceBuilder":
        """Add NER detection evidence."""
        return self.add_evidence(Evidence(
            evidence_type=EvidenceType.NER_DETECTION,
            description=f"Detected as {entity_type} by NER model",
            weight=weight,
            source=model_name,
            details={
                "entity_type": entity_type,
                "model_score": model_score,
            },
        ))

    def add_custom_term(
        self,
        term: str,
        weight: float = 0.9,
    ) -> "EvidenceBuilder":
        """Add custom term evidence."""
        return self.add_evidence(Evidence(
            evidence_type=EvidenceType.CUSTOM_TERM,
            description=f"Matched custom protected term",
            weight=weight,
            source="custom_terms",
            details={"term": term},
        ))

    def add_context_positive(
        self,
        description: str,
        keyword: str | None = None,
        weight: float = 0.3,
    ) -> "EvidenceBuilder":
        """Add positive context evidence."""
        return self.add_evidence(Evidence(
            evidence_type=EvidenceType.CONTEXT_POSITIVE,
            description=description,
            weight=weight,
            source="context",
            details={"keyword": keyword} if keyword else {},
        ))

    def add_context_negative(
        self,
        description: str,
        keyword: str | None = None,
        weight: float = -0.3,
    ) -> "EvidenceBuilder":
        """Add negative context evidence."""
        return self.add_evidence(Evidence(
            evidence_type=EvidenceType.CONTEXT_NEGATIVE,
            description=description,
            weight=weight,
            source="context",
            details={"keyword": keyword} if keyword else {},
        ))

    def add_location_context(
        self,
        location_type: str,
        location_value: str,
        weight: float = 0.4,
    ) -> "EvidenceBuilder":
        """Add location context evidence."""
        return self.add_evidence(Evidence(
            evidence_type=EvidenceType.LOCATION_CONTEXT,
            description=f"Found in {location_type}: {location_value}",
            weight=weight,
            source="location",
            details={
                "location_type": location_type,
                "location_value": location_value,
            },
        ))

    def add_document_type(
        self,
        document_type: str,
        expected_entity: bool,
        weight: float = 0.2,
    ) -> "EvidenceBuilder":
        """Add document type evidence."""
        if expected_entity:
            description = f"Expected in {document_type} document"
        else:
            description = f"Unusual for {document_type} document"
            weight = -abs(weight) * 0.5  # Mild negative

        return self.add_evidence(Evidence(
            evidence_type=EvidenceType.DOCUMENT_TYPE,
            description=description,
            weight=weight,
            source="document",
            details={
                "document_type": document_type,
                "expected": expected_entity,
            },
        ))

    def add_exclusion(
        self,
        reason: str,
        exclusion_type: str = "pattern",
        weight: float = -0.5,
    ) -> "EvidenceBuilder":
        """Add exclusion evidence."""
        evidence_type = {
            "pattern": EvidenceType.EXCLUDED_PATTERN,
            "false_positive": EvidenceType.KNOWN_FALSE_POSITIVE,
        }.get(exclusion_type, EvidenceType.EXCLUDED_PATTERN)

        return self.add_evidence(Evidence(
            evidence_type=evidence_type,
            description=reason,
            weight=weight,
            source="exclusion",
            details={"exclusion_type": exclusion_type},
        ))

    def build(
        self,
        finding: "Finding",
        include_summary: bool = True,
    ) -> ExplanationResult:
        """
        Build explanation from accumulated evidence.

        Args:
            finding: The finding to explain
            include_summary: Whether to generate summary text

        Returns:
            ExplanationResult with all evidence
        """
        confidence_band = getattr(finding, "confidence_band", "UNKNOWN")

        result = ExplanationResult(
            entity_type=finding.entity_type,
            entity_text=finding.text,
            raw_score=finding.score,
            confidence_band=confidence_band,
            evidence=list(self._evidence),
        )

        if include_summary:
            result.summary = self._generate_summary(result)

        return result

    def _generate_summary(self, result: ExplanationResult) -> str:
        """Generate human-readable summary."""
        parts = []

        # Primary detection reason
        if result.positive_evidence:
            primary = result.positive_evidence[0]
            parts.append(f"Detected as {result.entity_type}: {primary.description}.")

        # Additional positive evidence
        if len(result.positive_evidence) > 1:
            additional = len(result.positive_evidence) - 1
            parts.append(f"Supported by {additional} additional factor(s).")

        # Negative evidence warning
        if result.negative_evidence:
            neg_count = len(result.negative_evidence)
            parts.append(f"Note: {neg_count} factor(s) reduced confidence.")

        # Confidence band
        parts.append(f"Overall confidence: {result.confidence_band}.")

        return " ".join(parts)

    @classmethod
    def from_finding(
        cls,
        finding: "Finding",
    ) -> "EvidenceBuilder":
        """
        Create builder with evidence from finding's existing data.

        Args:
            finding: Finding with potential evidence attributes

        Returns:
            EvidenceBuilder with extracted evidence
        """
        builder = cls()

        # Extract evidence from finding if available
        recognizer = getattr(finding, "recognizer_name", None)
        if recognizer:
            if "ner" in recognizer.lower():
                builder.add_ner_detection(
                    finding.entity_type,
                    recognizer,
                    finding.score,
                )
            elif "custom" in recognizer.lower():
                builder.add_custom_term(finding.text)
            else:
                builder.add_pattern_match(recognizer)

        return builder


# Convenience functions

def explain_finding(finding: "Finding") -> ExplanationResult:
    """
    Generate explanation for a finding.

    Convenience function for simple explanation generation.
    """
    builder = EvidenceBuilder.from_finding(finding)
    return builder.build(finding)


def format_explanation_text(explanation: ExplanationResult) -> str:
    """
    Format explanation as readable text.

    Args:
        explanation: ExplanationResult to format

    Returns:
        Formatted text string
    """
    lines = [
        f"Entity: {explanation.entity_type}",
        f"Text: \"{explanation.entity_text}\"",
        f"Confidence: {explanation.confidence_band} ({explanation.raw_score:.0%})",
        "",
        "Why detected:",
    ]

    for ev in explanation.positive_evidence:
        lines.append(f"  ✓ {ev.description}")

    if explanation.negative_evidence:
        lines.append("")
        lines.append("Factors reducing confidence:")
        for ev in explanation.negative_evidence:
            lines.append(f"  ✗ {ev.description}")

    return "\n".join(lines)


__all__ = [
    "EvidenceType",
    "Evidence",
    "ExplanationResult",
    "EvidenceBuilder",
    "explain_finding",
    "format_explanation_text",
]
