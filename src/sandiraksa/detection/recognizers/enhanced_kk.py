"""
Enhanced KK (Kartu Keluarga) Recognizer.

Indonesian Family Card Number - 16 digits:
- Digits 1-2: Province code
- Digits 3-4: City/Regency code
- Digits 5-6: District code
- Digits 7-12: Registration date (DDMMYY)
- Digits 13-16: Sequence number

Key Differences from NIK:
- KK uses registration date, NOT birth date
- No female +40 adjustment
- Represents a family unit, not individual

Format: Same as NIK (16 digits)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, ClassVar

from sandiraksa.detection.unified_engine import (
    BaseUnifiedRecognizer,
    DetectionContext,
)
from sandiraksa.detection.unified_finding import (
    ConfidenceBand,
    ConfidenceEvidence,
    EvidenceType,
    UnifiedFinding,
    classify_confidence,
)

# Reuse province codes from NIK
from sandiraksa.detection.recognizers.enhanced_nik import VALID_PROVINCE_CODES

if TYPE_CHECKING:
    from sandiraksa.documents.logical_segment import LogicalSegment


# Context keywords for KK
KK_CONTEXT_KEYWORDS: set[str] = {
    "kk",
    "kartu keluarga",
    "no. kk",
    "no kk",
    "nomor kk",
    "nomor kartu keluarga",
    "family card",
    "family register",
}

# Keywords that suggest NIK instead of KK
NIK_INDICATORS: set[str] = {
    "nik",
    "ktp",
    "kartu tanda penduduk",
    "nomor induk kependudukan",
}


@dataclass
class KKMetadata:
    """Parsed metadata from a KK number."""

    province_code: str
    province_name: str
    city_code: str
    district_code: str
    reg_day: int
    reg_month: int
    reg_year: int
    sequence: str
    raw_kk: str

    @property
    def registration_date(self) -> date | None:
        """Get registration date as date object."""
        try:
            return date(self.reg_year, self.reg_month, self.reg_day)
        except ValueError:
            return None


class EnhancedKKRecognizer(BaseUnifiedRecognizer):
    """
    Enhanced recognizer for Indonesian KK (Family Card Number).

    Features:
    - Province code validation
    - Registration date validation (not birth date)
    - Context-aware detection (distinguishes from NIK)
    - Multiple format support
    """

    # Pattern: 16 digits with optional separators
    PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"\b"
        r"(?:"
        r"(\d{2})[\s.\-]?(\d{2})[\s.\-]?(\d{2})[\s.\-]?(\d{6})[\s.\-]?(\d{4})"
        r"|"
        r"(\d{16})"
        r")"
        r"\b"
    )

    def __init__(self, priority: int = 84) -> None:
        """Initialize enhanced KK recognizer."""
        super().__init__(
            name="enhanced_kk",
            supported_entities=["ID_KK"],
            priority=priority,
        )

    def analyze(
        self,
        segment: "LogicalSegment",
        context: DetectionContext,
    ) -> list[UnifiedFinding]:
        """
        Analyze segment for KK numbers.

        Args:
            segment: LogicalSegment to analyze
            context: Detection context

        Returns:
            List of UnifiedFinding for detected KKs
        """
        if not context.should_detect_entity("ID_KK"):
            return []

        if not segment.text:
            return []

        findings: list[UnifiedFinding] = []
        text = segment.text

        # Check context - KK requires explicit context to distinguish from NIK
        has_kk_context = self._has_kk_context(segment)
        has_nik_context = self._has_nik_context(segment)

        # If explicit NIK context, skip KK detection (let NIK recognizer handle)
        if has_nik_context and not has_kk_context:
            return []

        for match in self.PATTERN.finditer(text):
            # Extract KK digits
            if match.group(6):  # Plain 16-digit
                kk = match.group(6)
            else:  # Formatted
                groups = [g for g in match.groups()[:5] if g]
                kk = "".join(groups)

            # Validate
            validation = self._validate_kk(kk, has_kk_context)
            if validation.score <= 0:
                continue

            # Get context window
            context_before, context_after = segment.get_context_window(
                match.start(), match.end(), window_size=30
            )

            # Calculate final score
            final_score = validation.score
            if has_kk_context:
                final_score = min(1.0, final_score + 0.15)

            # Create finding
            finding = UnifiedFinding(
                segment_id=segment.id,
                entity_type="ID_KK",
                start=match.start(),
                end=match.end(),
                raw_score=final_score,
                confidence_band=classify_confidence(final_score),
                detector="enhanced_kk",
                detected_text=match.group(),
                context_before=context_before,
                context_after=context_after,
                is_validated=validation.is_valid,
            )

            # Add evidence
            for evidence in validation.evidence:
                finding.add_evidence(evidence)

            if has_kk_context:
                finding.add_evidence(
                    ConfidenceEvidence(
                        evidence_type=EvidenceType.CONTEXT_POSITIVE,
                        source="enhanced_kk",
                        weight=0.15,
                        reason_code="kk_context_keyword",
                        description="KK context keyword found nearby",
                    )
                )

            findings.append(finding)

        return findings

    def _has_kk_context(self, segment: "LogicalSegment") -> bool:
        """Check if segment has KK-related context."""
        # Check key_label
        if segment.key_label:
            label_lower = segment.key_label.lower()
            if any(kw in label_lower for kw in KK_CONTEXT_KEYWORDS):
                return True

        # Check context labels
        for label in segment.context_labels:
            label_lower = label.lower()
            if any(kw in label_lower for kw in KK_CONTEXT_KEYWORDS):
                return True

        # Check surrounding text
        text_lower = segment.text.lower()
        for kw in KK_CONTEXT_KEYWORDS:
            if kw in text_lower:
                return True

        return False

    def _has_nik_context(self, segment: "LogicalSegment") -> bool:
        """Check if segment has NIK-related context."""
        text_lower = segment.text.lower()
        label_lower = (segment.key_label or "").lower()

        for kw in NIK_INDICATORS:
            if kw in text_lower or kw in label_lower:
                return True

        for label in segment.context_labels:
            label_lower = label.lower()
            if any(kw in label_lower for kw in NIK_INDICATORS):
                return True

        return False

    def _validate_kk(self, kk: str, has_context: bool) -> "KKValidationResult":
        """
        Validate KK number.

        Args:
            kk: The 16-digit KK string
            has_context: Whether KK context was found

        Returns:
            KKValidationResult with score and evidence
        """
        evidence: list[ConfidenceEvidence] = []

        if len(kk) != 16 or not kk.isdigit():
            return KKValidationResult(score=0.0, is_valid=False, evidence=[])

        # Lower base score without context (could be NIK)
        score = 0.5 if has_context else 0.3
        evidence.append(
            ConfidenceEvidence(
                evidence_type=EvidenceType.PATTERN_MATCH,
                source="enhanced_kk",
                weight=score,
                reason_code="kk_16_digit_pattern",
                description="Matches 16-digit KK pattern",
            )
        )

        # Province code validation
        province_code = kk[:2]
        if province_code in VALID_PROVINCE_CODES:
            score += 0.2
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.STRUCTURAL_VALID,
                    source="enhanced_kk",
                    weight=0.2,
                    reason_code="kk_valid_province",
                    description=f"Valid province: {VALID_PROVINCE_CODES[province_code]}",
                )
            )
        else:
            return KKValidationResult(score=0.0, is_valid=False, evidence=evidence)

        # Registration date validation
        date_result = self._validate_registration_date(kk[6:12])
        if date_result.is_valid:
            score += 0.15
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.SEMANTIC_VALID,
                    source="enhanced_kk",
                    weight=0.15,
                    reason_code="kk_valid_reg_date",
                    description=f"Valid registration date: {date_result.description}",
                )
            )
        else:
            score -= 0.1
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.CONTEXT_NEGATIVE,
                    source="enhanced_kk",
                    weight=-0.1,
                    reason_code="kk_invalid_reg_date",
                    description=f"Invalid registration date: {date_result.description}",
                )
            )

        # Extract metadata
        metadata = self._extract_metadata(kk) if score >= 0.4 else None

        return KKValidationResult(
            score=min(score, 1.0),
            is_valid=score >= 0.6,
            evidence=evidence,
            metadata=metadata,
        )

    def _validate_registration_date(self, encoded: str) -> "DateValidationResult":
        """
        Validate the registration date portion of KK.

        Format: DDMMYY (no female adjustment like NIK)

        Args:
            encoded: 6-digit encoded date

        Returns:
            DateValidationResult with validation status
        """
        try:
            day = int(encoded[:2])
            month = int(encoded[2:4])
            year_2digit = int(encoded[4:6])

            # Basic validation
            if day < 1 or day > 31:
                return DateValidationResult(
                    is_valid=False,
                    description=f"Invalid day: {day}",
                )
            if month < 1 or month > 12:
                return DateValidationResult(
                    is_valid=False,
                    description=f"Invalid month: {month}",
                )

            # Determine full year
            current_year = date.today().year
            current_2digit = current_year % 100

            # KK registration dates are typically recent
            # Use 1900s only for year > current + 10
            if year_2digit > current_2digit + 10:
                full_year = 1900 + year_2digit
            else:
                full_year = 2000 + year_2digit

            # Validate date
            try:
                reg_date = date(full_year, month, day)

                # Check not in future
                if reg_date > date.today():
                    return DateValidationResult(
                        is_valid=False,
                        description="Registration date is in future",
                    )

                # Check not too old (KK system started ~2000)
                if full_year < 1990:
                    return DateValidationResult(
                        is_valid=False,
                        description=f"Registration year too old: {full_year}",
                    )

                return DateValidationResult(
                    is_valid=True,
                    description=reg_date.strftime("%d/%m/%Y"),
                    reg_date=reg_date,
                )

            except ValueError as e:
                return DateValidationResult(
                    is_valid=False,
                    description=f"Invalid date: {e}",
                )

        except (ValueError, IndexError) as e:
            return DateValidationResult(
                is_valid=False,
                description=f"Parse error: {e}",
            )

    def _extract_metadata(self, kk: str) -> KKMetadata | None:
        """Extract metadata from validated KK."""
        if len(kk) != 16:
            return None

        province_code = kk[:2]
        if province_code not in VALID_PROVINCE_CODES:
            return None

        day = int(kk[6:8])
        month = int(kk[8:10])
        year_2digit = int(kk[10:12])

        current_2digit = date.today().year % 100
        if year_2digit > current_2digit + 10:
            full_year = 1900 + year_2digit
        else:
            full_year = 2000 + year_2digit

        return KKMetadata(
            province_code=province_code,
            province_name=VALID_PROVINCE_CODES[province_code],
            city_code=kk[2:4],
            district_code=kk[4:6],
            reg_day=day,
            reg_month=month,
            reg_year=full_year,
            sequence=kk[12:16],
            raw_kk=kk,
        )


@dataclass
class DateValidationResult:
    """Result of date validation."""

    is_valid: bool
    description: str
    reg_date: date | None = None


@dataclass
class KKValidationResult:
    """Result of KK validation."""

    score: float
    is_valid: bool
    evidence: list[ConfidenceEvidence]
    metadata: KKMetadata | None = None


def parse_kk(kk: str) -> KKMetadata | None:
    """
    Parse a KK string and extract metadata.

    Args:
        kk: The 16-digit KK string

    Returns:
        KKMetadata if valid, None otherwise
    """
    # Remove non-digits
    digits = re.sub(r"[^\d]", "", kk)
    if len(digits) != 16:
        return None

    recognizer = EnhancedKKRecognizer()
    result = recognizer._validate_kk(digits, has_context=True)
    return result.metadata


__all__ = [
    "DateValidationResult",
    "EnhancedKKRecognizer",
    "KK_CONTEXT_KEYWORDS",
    "KKMetadata",
    "KKValidationResult",
    "parse_kk",
]
