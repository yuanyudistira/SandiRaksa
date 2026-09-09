"""
BPJS (Badan Penyelenggara Jaminan Sosial) Recognizer.

Indonesian Social Security Number - 13 digits.

BPJS Kesehatan (Health Insurance):
- 13-digit unique identifier
- Issued by BPJS Kesehatan

BPJS Ketenagakerjaan (Employment):
- Also uses numeric identifiers
- May differ in format

Format: 0001234567890 (13 digits)
Context: BPJS, No. BPJS, BPJS Kesehatan, Kartu BPJS
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


# Context keywords for BPJS
BPJS_CONTEXT_KEYWORDS: set[str] = {
    "bpjs",
    "bpjs kesehatan",
    "bpjs ketenagakerjaan",
    "no. bpjs",
    "no bpjs",
    "nomor bpjs",
    "kartu bpjs",
    "peserta bpjs",
    "jkn",  # Jaminan Kesehatan Nasional
    "jaminan kesehatan",
    "jaminan sosial",
}


@dataclass
class BPJSMetadata:
    """Parsed metadata from a BPJS number."""

    raw_bpjs: str
    digits_only: str
    is_valid: bool


class BPJSRecognizer(BaseUnifiedRecognizer):
    """
    Recognizer for Indonesian BPJS numbers.

    BPJS numbers are 13-digit identifiers used for social security.
    Due to lack of public checksum algorithm, detection relies heavily
    on context keywords.

    Features:
    - 13-digit pattern matching
    - Context-aware detection (requires BPJS context for high confidence)
    - Basic structural validation
    """

    # Pattern: 13 digits with optional separators
    PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(\d{13})\b"
    )

    # Pattern with possible formatting
    PATTERN_FORMATTED: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(\d{4})[\s.\-]?(\d{4})[\s.\-]?(\d{5})\b"
    )

    def __init__(self, priority: int = 78) -> None:
        """Initialize BPJS recognizer."""
        super().__init__(
            name="bpjs",
            supported_entities=["ID_BPJS"],
            priority=priority,
        )

    def analyze(
        self,
        segment: "LogicalSegment",
        context: DetectionContext,
    ) -> list[UnifiedFinding]:
        """
        Analyze segment for BPJS numbers.

        Args:
            segment: LogicalSegment to analyze
            context: Detection context

        Returns:
            List of UnifiedFinding for detected BPJS numbers
        """
        if not context.should_detect_entity("ID_BPJS"):
            return []

        if not segment.text:
            return []

        findings: list[UnifiedFinding] = []
        text = segment.text
        found_positions: set[tuple[int, int]] = set()

        # Check for context - BPJS requires explicit context
        has_context = self._has_bpjs_context(segment)

        # Only detect if BPJS context is present (too many false positives otherwise)
        if not has_context:
            return []

        # Try formatted pattern
        for match in self.PATTERN_FORMATTED.finditer(text):
            pos = (match.start(), match.end())
            if pos in found_positions:
                continue

            digits = "".join(match.groups())
            if len(digits) == 13:
                finding = self._create_finding(
                    segment=segment,
                    match_text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    digits=digits,
                    has_context=has_context,
                )
                if finding:
                    findings.append(finding)
                    found_positions.add(pos)

        # Try plain 13-digit pattern
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
                has_context=has_context,
            )
            if finding:
                findings.append(finding)
                found_positions.add(pos)

        return findings

    def _has_bpjs_context(self, segment: "LogicalSegment") -> bool:
        """Check if segment has BPJS-related context."""
        # Check key_label
        if segment.key_label:
            label_lower = segment.key_label.lower()
            if any(kw in label_lower for kw in BPJS_CONTEXT_KEYWORDS):
                return True

        # Check context labels
        for label in segment.context_labels:
            label_lower = label.lower()
            if any(kw in label_lower for kw in BPJS_CONTEXT_KEYWORDS):
                return True

        # Check surrounding text
        text_lower = segment.text.lower()
        for kw in BPJS_CONTEXT_KEYWORDS:
            if kw in text_lower:
                return True

        return False

    def _create_finding(
        self,
        segment: "LogicalSegment",
        match_text: str,
        start: int,
        end: int,
        digits: str,
        has_context: bool,
    ) -> UnifiedFinding | None:
        """Create finding for BPJS number."""
        validation = self._validate_bpjs(digits, has_context)
        if validation.score <= 0:
            return None

        # Get context window
        context_before, context_after = segment.get_context_window(
            start, end, window_size=30
        )

        finding = UnifiedFinding(
            segment_id=segment.id,
            entity_type="ID_BPJS",
            start=start,
            end=end,
            raw_score=validation.score,
            confidence_band=classify_confidence(validation.score),
            detector="bpjs",
            detected_text=match_text,
            context_before=context_before,
            context_after=context_after,
            is_validated=validation.is_valid,
        )

        # Add evidence
        for evidence in validation.evidence:
            finding.add_evidence(evidence)

        return finding

    def _validate_bpjs(self, digits: str, has_context: bool) -> "BPJSValidationResult":
        """
        Validate BPJS number.

        Args:
            digits: The 13-digit BPJS string
            has_context: Whether BPJS context was found

        Returns:
            BPJSValidationResult with score and evidence
        """
        evidence: list[ConfidenceEvidence] = []

        if len(digits) != 13 or not digits.isdigit():
            return BPJSValidationResult(score=0.0, is_valid=False, evidence=[])

        # Base score - lower without known checksum
        score = 0.5 if has_context else 0.3
        evidence.append(
            ConfidenceEvidence(
                evidence_type=EvidenceType.PATTERN_MATCH,
                source="bpjs",
                weight=score,
                reason_code="bpjs_13_digit_pattern",
                description="Matches 13-digit BPJS pattern",
            )
        )

        # Context boost
        if has_context:
            score += 0.25
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.CONTEXT_POSITIVE,
                    source="bpjs",
                    weight=0.25,
                    reason_code="bpjs_context_keyword",
                    description="BPJS context keyword found nearby",
                )
            )

        # Check for invalid patterns (all same digit, sequential)
        if len(set(digits)) == 1:
            return BPJSValidationResult(score=0.0, is_valid=False, evidence=evidence)

        # Check for sequential numbers (123456789...)
        if digits == "".join(str(i % 10) for i in range(13)):
            return BPJSValidationResult(score=0.0, is_valid=False, evidence=evidence)

        # BPJS numbers typically start with 0 (but not always)
        if digits.startswith("0"):
            score += 0.1
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.STRUCTURAL_VALID,
                    source="bpjs",
                    weight=0.1,
                    reason_code="bpjs_starts_with_zero",
                    description="BPJS number starts with 0 (common pattern)",
                )
            )

        metadata = BPJSMetadata(
            raw_bpjs=digits,
            digits_only=digits,
            is_valid=score >= 0.6,
        )

        return BPJSValidationResult(
            score=min(score, 1.0),
            is_valid=score >= 0.6,
            evidence=evidence,
            metadata=metadata,
        )


@dataclass
class BPJSValidationResult:
    """Result of BPJS validation."""

    score: float
    is_valid: bool
    evidence: list[ConfidenceEvidence]
    metadata: BPJSMetadata | None = None


def format_bpjs(digits: str) -> str:
    """
    Format BPJS number with standard grouping.

    Args:
        digits: 13-digit BPJS

    Returns:
        Formatted: XXXX-XXXX-XXXXX
    """
    if len(digits) != 13 or not digits.isdigit():
        return digits

    return f"{digits[:4]}-{digits[4:8]}-{digits[8:]}"


__all__ = [
    "BPJS_CONTEXT_KEYWORDS",
    "BPJSMetadata",
    "BPJSRecognizer",
    "BPJSValidationResult",
    "format_bpjs",
]
