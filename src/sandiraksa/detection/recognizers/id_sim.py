"""
SIM (Surat Izin Mengemudi) Recognizer.

Indonesian Driving License Number.

Format:
- 12-14 digits
- Structure varies by issuing region
- Some formats: XXXXXXXXXX (12 digits), XXXXXXXXXXXXXX (14 digits)

Context: SIM, Surat Izin Mengemudi, No. SIM, Driving License
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from sandiraksa.detection.unified_engine import (
    BaseUnifiedRecognizer,
    DetectionContext,
)
from sandiraksa.detection.unified_finding import (
    ConfidenceEvidence,
    EvidenceType,
    UnifiedFinding,
    classify_confidence,
)

if TYPE_CHECKING:
    from sandiraksa.documents.logical_segment import LogicalSegment


# Context keywords for SIM
SIM_CONTEXT_KEYWORDS: set[str] = {
    "sim",
    "surat izin mengemudi",
    "no. sim",
    "no sim",
    "nomor sim",
    "driving license",
    "driver license",
    "driver's license",
    "sim a",
    "sim b",
    "sim c",
    "sim d",
}

# SIM types
SIM_TYPES: set[str] = {"a", "b", "b1", "b2", "c", "d"}


@dataclass
class SIMMetadata:
    """Parsed metadata from a SIM number."""

    raw_sim: str
    digits_only: str
    sim_type: str | None  # A, B, B1, B2, C, D
    is_valid: bool


class SIMRecognizer(BaseUnifiedRecognizer):
    """
    Recognizer for Indonesian SIM (Driving License) numbers.

    SIM numbers are 12-14 digit identifiers.
    Detection relies on context keywords due to varying formats.

    Features:
    - 12-14 digit pattern matching
    - Context-aware detection
    - SIM type detection from context (A, B, C, D)
    """

    # Pattern: 12-14 digits
    PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(\d{12,14})\b"
    )

    # Pattern with possible formatting (groups of 4)
    PATTERN_FORMATTED: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(\d{4})[\s.\-]?(\d{4})[\s.\-]?(\d{4})(?:[\s.\-]?(\d{2}))?\b"
    )

    def __init__(self, priority: int = 76) -> None:
        """Initialize SIM recognizer."""
        super().__init__(
            name="sim",
            supported_entities=["ID_SIM"],
            priority=priority,
        )

    def analyze(
        self,
        segment: "LogicalSegment",
        context: DetectionContext,
    ) -> list[UnifiedFinding]:
        """
        Analyze segment for SIM numbers.

        Args:
            segment: LogicalSegment to analyze
            context: Detection context

        Returns:
            List of UnifiedFinding for detected SIM numbers
        """
        if not context.should_detect_entity("ID_SIM"):
            return []

        if not segment.text:
            return []

        findings: list[UnifiedFinding] = []
        text = segment.text
        found_positions: set[tuple[int, int]] = set()

        # Check for context - SIM requires explicit context
        has_context = self._has_sim_context(segment)

        # Only detect if SIM context is present
        if not has_context:
            return []

        # Detect SIM type from context
        sim_type = self._detect_sim_type(segment)

        # Try formatted pattern
        for match in self.PATTERN_FORMATTED.finditer(text):
            pos = (match.start(), match.end())
            if pos in found_positions:
                continue

            groups = [g for g in match.groups() if g]
            digits = "".join(groups)
            if 12 <= len(digits) <= 14:
                finding = self._create_finding(
                    segment=segment,
                    match_text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    digits=digits,
                    sim_type=sim_type,
                    has_context=has_context,
                )
                if finding:
                    findings.append(finding)
                    found_positions.add(pos)

        # Try plain digit pattern
        for match in self.PATTERN.finditer(text):
            pos = (match.start(), match.end())
            if pos in found_positions:
                continue

            digits = match.group(1)
            finding = self._create_finding(
                segment=segment,
                match_text=match.group(),
                start=match.start(),
                end=match.end(),
                digits=digits,
                sim_type=sim_type,
                has_context=has_context,
            )
            if finding:
                findings.append(finding)
                found_positions.add(pos)

        return findings

    def _has_sim_context(self, segment: "LogicalSegment") -> bool:
        """Check if segment has SIM-related context."""
        # Check key_label
        if segment.key_label:
            label_lower = segment.key_label.lower()
            if any(kw in label_lower for kw in SIM_CONTEXT_KEYWORDS):
                return True

        # Check context labels
        for label in segment.context_labels:
            label_lower = label.lower()
            if any(kw in label_lower for kw in SIM_CONTEXT_KEYWORDS):
                return True

        # Check surrounding text
        text_lower = segment.text.lower()
        for kw in SIM_CONTEXT_KEYWORDS:
            if kw in text_lower:
                return True

        return False

    def _detect_sim_type(self, segment: "LogicalSegment") -> str | None:
        """Detect SIM type (A, B, C, D) from context."""
        text_lower = segment.text.lower()
        label_lower = (segment.key_label or "").lower()
        combined = text_lower + " " + label_lower

        # Check for specific SIM types
        for sim_type in ["b1", "b2", "a", "b", "c", "d"]:
            pattern = rf"\bsim\s*{sim_type}\b"
            if re.search(pattern, combined):
                return sim_type.upper()

        return None

    def _create_finding(
        self,
        segment: "LogicalSegment",
        match_text: str,
        start: int,
        end: int,
        digits: str,
        sim_type: str | None,
        has_context: bool,
    ) -> UnifiedFinding | None:
        """Create finding for SIM number."""
        validation = self._validate_sim(digits, sim_type, has_context)
        if validation.score <= 0:
            return None

        # Get context window
        context_before, context_after = segment.get_context_window(
            start, end, window_size=30
        )

        finding = UnifiedFinding(
            segment_id=segment.id,
            entity_type="ID_SIM",
            start=start,
            end=end,
            raw_score=validation.score,
            confidence_band=classify_confidence(validation.score),
            detector="sim",
            detected_text=match_text,
            context_before=context_before,
            context_after=context_after,
            is_validated=validation.is_valid,
        )

        # Add evidence
        for evidence in validation.evidence:
            finding.add_evidence(evidence)

        return finding

    def _validate_sim(
        self,
        digits: str,
        sim_type: str | None,
        has_context: bool,
    ) -> "SIMValidationResult":
        """
        Validate SIM number.

        Args:
            digits: The 12-14 digit SIM string
            sim_type: Detected SIM type if any
            has_context: Whether SIM context was found

        Returns:
            SIMValidationResult with score and evidence
        """
        evidence: list[ConfidenceEvidence] = []

        if not (12 <= len(digits) <= 14) or not digits.isdigit():
            return SIMValidationResult(score=0.0, is_valid=False, evidence=[])

        # Base score
        score = 0.5 if has_context else 0.3
        evidence.append(
            ConfidenceEvidence(
                evidence_type=EvidenceType.PATTERN_MATCH,
                source="sim",
                weight=score,
                reason_code="sim_digit_pattern",
                description=f"Matches {len(digits)}-digit SIM pattern",
            )
        )

        # Context boost
        if has_context:
            score += 0.2
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.CONTEXT_POSITIVE,
                    source="sim",
                    weight=0.2,
                    reason_code="sim_context_keyword",
                    description="SIM context keyword found nearby",
                )
            )

        # SIM type boost
        if sim_type:
            score += 0.1
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.CONTEXT_POSITIVE,
                    source="sim",
                    weight=0.1,
                    reason_code="sim_type_detected",
                    description=f"SIM type detected: SIM {sim_type}",
                )
            )

        # Check for invalid patterns
        if len(set(digits)) == 1:
            return SIMValidationResult(score=0.0, is_valid=False, evidence=evidence)

        metadata = SIMMetadata(
            raw_sim=digits,
            digits_only=digits,
            sim_type=sim_type,
            is_valid=score >= 0.6,
        )

        return SIMValidationResult(
            score=min(score, 1.0),
            is_valid=score >= 0.6,
            evidence=evidence,
            metadata=metadata,
        )


@dataclass
class SIMValidationResult:
    """Result of SIM validation."""

    score: float
    is_valid: bool
    evidence: list[ConfidenceEvidence]
    metadata: SIMMetadata | None = None


__all__ = [
    "SIM_CONTEXT_KEYWORDS",
    "SIM_TYPES",
    "SIMMetadata",
    "SIMRecognizer",
    "SIMValidationResult",
]
