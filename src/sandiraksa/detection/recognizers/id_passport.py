"""
Indonesian Passport Recognizer.

Indonesian Passport Number Format:
- 1 letter + 7 digits (e.g., A1234567)
- The letter indicates series/batch
- Common letters: A, B, C, M, N, P, R, S, T, X

Context: Passport, Paspor, No. Passport, Passport Number
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


# Context keywords for Passport
PASSPORT_CONTEXT_KEYWORDS: set[str] = {
    "passport",
    "paspor",
    "no. passport",
    "no passport",
    "nomor passport",
    "nomor paspor",
    "no. paspor",
    "no paspor",
    "passport number",
    "travel document",
    "dokumen perjalanan",
}

# Common passport series letters for Indonesia
VALID_PASSPORT_LETTERS: set[str] = {
    "A", "B", "C", "M", "N", "P", "R", "S", "T", "X",
}


@dataclass
class PassportMetadata:
    """Parsed metadata from a passport number."""

    raw_passport: str
    series_letter: str
    number_part: str
    is_valid: bool


class PassportRecognizer(BaseUnifiedRecognizer):
    """
    Recognizer for Indonesian Passport numbers.

    Indonesian passport numbers follow the format: 1 letter + 7 digits
    Example: A1234567, B9876543

    Features:
    - Pattern matching for letter + 7 digits
    - Valid series letter validation
    - Context-aware detection
    """

    # Pattern: 1 letter followed by 7 digits
    PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"\b([A-Z])[\s.\-]?(\d{7})\b",
        re.IGNORECASE,
    )

    # Also match without separator
    PATTERN_COMPACT: ClassVar[re.Pattern[str]] = re.compile(
        r"\b([A-Z]\d{7})\b",
        re.IGNORECASE,
    )

    def __init__(self, priority: int = 77) -> None:
        """Initialize Passport recognizer."""
        super().__init__(
            name="passport",
            supported_entities=["ID_PASSPORT"],
            priority=priority,
        )

    def analyze(
        self,
        segment: "LogicalSegment",
        context: DetectionContext,
    ) -> list[UnifiedFinding]:
        """
        Analyze segment for Indonesian passport numbers.

        Args:
            segment: LogicalSegment to analyze
            context: Detection context

        Returns:
            List of UnifiedFinding for detected passport numbers
        """
        if not context.should_detect_entity("ID_PASSPORT"):
            return []

        if not segment.text:
            return []

        findings: list[UnifiedFinding] = []
        text = segment.text
        found_positions: set[tuple[int, int]] = set()

        # Check for context
        has_context = self._has_passport_context(segment)

        # Try both patterns
        for match in self.PATTERN.finditer(text):
            pos = (match.start(), match.end())
            if pos in found_positions:
                continue

            letter = match.group(1).upper()
            digits = match.group(2)
            passport_number = letter + digits

            finding = self._create_finding(
                segment=segment,
                match_text=match.group(),
                start=match.start(),
                end=match.end(),
                letter=letter,
                digits=digits,
                has_context=has_context,
            )
            if finding:
                findings.append(finding)
                found_positions.add(pos)

        for match in self.PATTERN_COMPACT.finditer(text):
            pos = (match.start(), match.end())
            if pos in found_positions:
                continue

            passport_number = match.group(1).upper()
            letter = passport_number[0]
            digits = passport_number[1:]

            finding = self._create_finding(
                segment=segment,
                match_text=match.group(),
                start=match.start(),
                end=match.end(),
                letter=letter,
                digits=digits,
                has_context=has_context,
            )
            if finding:
                findings.append(finding)
                found_positions.add(pos)

        return findings

    def _has_passport_context(self, segment: "LogicalSegment") -> bool:
        """Check if segment has passport-related context."""
        # Check key_label
        if segment.key_label:
            label_lower = segment.key_label.lower()
            if any(kw in label_lower for kw in PASSPORT_CONTEXT_KEYWORDS):
                return True

        # Check context labels
        for label in segment.context_labels:
            label_lower = label.lower()
            if any(kw in label_lower for kw in PASSPORT_CONTEXT_KEYWORDS):
                return True

        # Check surrounding text
        text_lower = segment.text.lower()
        for kw in PASSPORT_CONTEXT_KEYWORDS:
            if kw in text_lower:
                return True

        return False

    def _create_finding(
        self,
        segment: "LogicalSegment",
        match_text: str,
        start: int,
        end: int,
        letter: str,
        digits: str,
        has_context: bool,
    ) -> UnifiedFinding | None:
        """Create finding for passport number."""
        validation = self._validate_passport(letter, digits, has_context)
        if validation.score <= 0:
            return None

        # Get context window
        context_before, context_after = segment.get_context_window(
            start, end, window_size=30
        )

        finding = UnifiedFinding(
            segment_id=segment.id,
            entity_type="ID_PASSPORT",
            start=start,
            end=end,
            raw_score=validation.score,
            confidence_band=classify_confidence(validation.score),
            detector="passport",
            detected_text=match_text,
            context_before=context_before,
            context_after=context_after,
            is_validated=validation.is_valid,
        )

        # Add evidence
        for evidence in validation.evidence:
            finding.add_evidence(evidence)

        return finding

    def _validate_passport(
        self,
        letter: str,
        digits: str,
        has_context: bool,
    ) -> "PassportValidationResult":
        """
        Validate passport number.

        Args:
            letter: The series letter
            digits: The 7-digit number
            has_context: Whether passport context was found

        Returns:
            PassportValidationResult with score and evidence
        """
        evidence: list[ConfidenceEvidence] = []

        # Basic validation
        if len(digits) != 7 or not digits.isdigit():
            return PassportValidationResult(score=0.0, is_valid=False, evidence=[])

        if not letter.isalpha():
            return PassportValidationResult(score=0.0, is_valid=False, evidence=[])

        letter = letter.upper()

        # Base score
        score = 0.4
        evidence.append(
            ConfidenceEvidence(
                evidence_type=EvidenceType.PATTERN_MATCH,
                source="passport",
                weight=0.4,
                reason_code="passport_pattern",
                description="Matches Indonesian passport pattern (letter + 7 digits)",
            )
        )

        # Valid series letter boost
        if letter in VALID_PASSPORT_LETTERS:
            score += 0.2
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.STRUCTURAL_VALID,
                    source="passport",
                    weight=0.2,
                    reason_code="passport_valid_series",
                    description=f"Valid passport series letter: {letter}",
                )
            )
        else:
            # Unknown series - still possible but lower confidence
            score += 0.05
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.PATTERN_MATCH,
                    source="passport",
                    weight=0.05,
                    reason_code="passport_unknown_series",
                    description=f"Unknown passport series: {letter}",
                )
            )

        # Context boost
        if has_context:
            score += 0.25
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.CONTEXT_POSITIVE,
                    source="passport",
                    weight=0.25,
                    reason_code="passport_context_keyword",
                    description="Passport context keyword found nearby",
                )
            )
        else:
            # Without context, lower confidence significantly
            # (too many letter+7digit patterns that aren't passports)
            score -= 0.1

        # Check for invalid digit patterns
        if len(set(digits)) == 1:
            return PassportValidationResult(score=0.0, is_valid=False, evidence=evidence)

        if digits == "0000000" or digits == "1234567":
            return PassportValidationResult(score=0.0, is_valid=False, evidence=evidence)

        metadata = PassportMetadata(
            raw_passport=letter + digits,
            series_letter=letter,
            number_part=digits,
            is_valid=score >= 0.6,
        )

        return PassportValidationResult(
            score=max(0.0, min(score, 1.0)),
            is_valid=score >= 0.6,
            evidence=evidence,
            metadata=metadata,
        )


@dataclass
class PassportValidationResult:
    """Result of passport validation."""

    score: float
    is_valid: bool
    evidence: list[ConfidenceEvidence]
    metadata: PassportMetadata | None = None


def format_passport(passport: str) -> str:
    """
    Format passport number.

    Args:
        passport: Raw passport string

    Returns:
        Formatted: A 1234567
    """
    # Remove non-alphanumeric
    cleaned = re.sub(r"[^A-Za-z0-9]", "", passport)
    if len(cleaned) == 8 and cleaned[0].isalpha():
        return f"{cleaned[0].upper()} {cleaned[1:]}"
    return passport


__all__ = [
    "PASSPORT_CONTEXT_KEYWORDS",
    "PassportMetadata",
    "PassportRecognizer",
    "PassportValidationResult",
    "VALID_PASSPORT_LETTERS",
    "format_passport",
]
