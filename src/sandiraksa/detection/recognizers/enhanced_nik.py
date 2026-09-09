"""
Enhanced NIK (Nomor Induk Kependudukan) Recognizer.

Indonesian National ID Number - 16 digits with embedded information:
- Digits 1-2: Province code (11-96)
- Digits 3-4: City/Regency code
- Digits 5-6: District code
- Digits 7-12: Birth date (DDMMYY, female adds 40 to DD)
- Digits 13-16: Sequence number

Enhanced Features:
- Full province code validation (2024 updated codes)
- DOB plausibility check (not future, not >120 years old)
- Female day adjustment handling
- Context-aware confidence boost
- Integration with unified detection pipeline
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
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

if TYPE_CHECKING:
    from sandiraksa.documents.logical_segment import LogicalSegment


# Valid Indonesian province codes (updated 2024)
# Includes new provinces from Papua expansion
VALID_PROVINCE_CODES: dict[str, str] = {
    "11": "Aceh",
    "12": "Sumatera Utara",
    "13": "Sumatera Barat",
    "14": "Riau",
    "15": "Jambi",
    "16": "Sumatera Selatan",
    "17": "Bengkulu",
    "18": "Lampung",
    "19": "Kep. Bangka Belitung",
    "21": "Kepulauan Riau",
    "31": "DKI Jakarta",
    "32": "Jawa Barat",
    "33": "Jawa Tengah",
    "34": "DI Yogyakarta",
    "35": "Jawa Timur",
    "36": "Banten",
    "51": "Bali",
    "52": "Nusa Tenggara Barat",
    "53": "Nusa Tenggara Timur",
    "61": "Kalimantan Barat",
    "62": "Kalimantan Tengah",
    "63": "Kalimantan Selatan",
    "64": "Kalimantan Timur",
    "65": "Kalimantan Utara",
    "71": "Sulawesi Utara",
    "72": "Sulawesi Tengah",
    "73": "Sulawesi Selatan",
    "74": "Sulawesi Tenggara",
    "75": "Gorontalo",
    "76": "Sulawesi Barat",
    "81": "Maluku",
    "82": "Maluku Utara",
    "91": "Papua Barat",
    "92": "Papua",
    "93": "Papua Selatan",
    "94": "Papua Tengah",
    "95": "Papua Pegunungan",
    "96": "Papua Barat Daya",
}

# Context keywords that boost NIK confidence
NIK_CONTEXT_KEYWORDS: set[str] = {
    "nik",
    "nomor induk kependudukan",
    "no. ktp",
    "no ktp",
    "nomor ktp",
    "ktp",
    "kartu tanda penduduk",
    "identitas",
    "identity",
    "id number",
}


@dataclass
class NIKMetadata:
    """Parsed metadata from a NIK number."""

    province_code: str
    province_name: str
    city_code: str
    district_code: str
    birth_day: int
    birth_month: int
    birth_year: int
    is_female: bool
    sequence: str
    raw_nik: str

    @property
    def birth_date(self) -> date | None:
        """Get birth date as date object."""
        try:
            return date(self.birth_year, self.birth_month, self.birth_day)
        except ValueError:
            return None

    @property
    def age(self) -> int | None:
        """Calculate approximate age."""
        bd = self.birth_date
        if bd is None:
            return None
        today = date.today()
        age = today.year - bd.year
        if (today.month, today.day) < (bd.month, bd.day):
            age -= 1
        return age


class EnhancedNIKRecognizer(BaseUnifiedRecognizer):
    """
    Enhanced recognizer for Indonesian NIK with full validation.

    Features:
    - Province code validation (all 38 provinces)
    - Birth date plausibility checking
    - Female day encoding handling (+40)
    - Age reasonability check (0-120 years)
    - Context keyword detection
    - Multiple format support (with/without separators)
    """

    # Pattern matches: plain 16 digits or formatted with separators
    PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"\b"
        r"(?:"
        r"(\d{2})[\s.\-]?(\d{2})[\s.\-]?(\d{2})[\s.\-]?(\d{6})[\s.\-]?(\d{4})"  # Formatted
        r"|"
        r"(\d{16})"  # Plain 16 digits
        r")"
        r"\b"
    )

    def __init__(self, priority: int = 85) -> None:
        """Initialize enhanced NIK recognizer."""
        super().__init__(
            name="enhanced_nik",
            supported_entities=["ID_NIK"],
            priority=priority,
        )

    def analyze(
        self,
        segment: "LogicalSegment",
        context: DetectionContext,
    ) -> list[UnifiedFinding]:
        """
        Analyze segment for NIK numbers.

        Args:
            segment: LogicalSegment to analyze
            context: Detection context

        Returns:
            List of UnifiedFinding for detected NIKs
        """
        if not context.should_detect_entity("ID_NIK"):
            return []

        if not segment.text:
            return []

        findings: list[UnifiedFinding] = []
        text = segment.text

        # Check for context boost
        has_context_boost = self._has_nik_context(segment)

        for match in self.PATTERN.finditer(text):
            # Extract NIK digits
            if match.group(6):  # Plain 16-digit format
                nik = match.group(6)
            else:  # Formatted with separators
                groups = [g for g in match.groups()[:5] if g]
                nik = "".join(groups)

            # Validate and get metadata
            validation = self._validate_nik(nik)
            if validation.score <= 0:
                continue

            # Get context window
            context_before, context_after = segment.get_context_window(
                match.start(), match.end(), window_size=30
            )

            # Calculate final score with context boost
            final_score = validation.score
            if has_context_boost:
                final_score = min(1.0, final_score + 0.1)

            # Create finding
            finding = UnifiedFinding(
                segment_id=segment.id,
                entity_type="ID_NIK",
                start=match.start(),
                end=match.end(),
                raw_score=final_score,
                confidence_band=classify_confidence(final_score),
                detector="enhanced_nik",
                detected_text=match.group(),
                context_before=context_before,
                context_after=context_after,
                is_validated=validation.is_valid,
            )

            # Add evidence
            for evidence in validation.evidence:
                finding.add_evidence(evidence)

            if has_context_boost:
                finding.add_evidence(
                    ConfidenceEvidence(
                        evidence_type=EvidenceType.CONTEXT_POSITIVE,
                        source="enhanced_nik",
                        weight=0.1,
                        reason_code="nik_context_keyword",
                        description="NIK context keyword found nearby",
                    )
                )

            findings.append(finding)

        return findings

    def _has_nik_context(self, segment: "LogicalSegment") -> bool:
        """Check if segment has NIK-related context."""
        # Check key_label
        if segment.key_label:
            label_lower = segment.key_label.lower()
            if any(kw in label_lower for kw in NIK_CONTEXT_KEYWORDS):
                return True

        # Check context labels
        for label in segment.context_labels:
            label_lower = label.lower()
            if any(kw in label_lower for kw in NIK_CONTEXT_KEYWORDS):
                return True

        # Check surrounding text
        text_lower = segment.text.lower()
        for kw in NIK_CONTEXT_KEYWORDS:
            if kw in text_lower:
                return True

        return False

    def _validate_nik(self, nik: str) -> "NIKValidationResult":
        """
        Validate NIK and return detailed result.

        Args:
            nik: The 16-digit NIK string

        Returns:
            NIKValidationResult with score and evidence
        """
        evidence: list[ConfidenceEvidence] = []

        # Basic format check
        if len(nik) != 16 or not nik.isdigit():
            return NIKValidationResult(score=0.0, is_valid=False, evidence=[])

        # Base score for matching pattern
        score = 0.5
        evidence.append(
            ConfidenceEvidence(
                evidence_type=EvidenceType.PATTERN_MATCH,
                source="enhanced_nik",
                weight=0.5,
                reason_code="nik_16_digit_pattern",
                description="Matches 16-digit NIK pattern",
            )
        )

        # Province code validation
        province_code = nik[:2]
        if province_code in VALID_PROVINCE_CODES:
            score += 0.2
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.STRUCTURAL_VALID,
                    source="enhanced_nik",
                    weight=0.2,
                    reason_code="nik_valid_province",
                    description=f"Valid province: {VALID_PROVINCE_CODES[province_code]}",
                )
            )
        else:
            # Invalid province - likely not a NIK
            return NIKValidationResult(score=0.0, is_valid=False, evidence=evidence)

        # Birth date validation
        dob_result = self._validate_birthdate(nik[6:12])
        if dob_result.is_valid:
            score += 0.2
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.SEMANTIC_VALID,
                    source="enhanced_nik",
                    weight=0.2,
                    reason_code="nik_valid_dob",
                    description=f"Valid DOB: {dob_result.description}",
                )
            )

            # Age plausibility check
            if dob_result.age is not None:
                if 0 <= dob_result.age <= 120:
                    score += 0.1
                    evidence.append(
                        ConfidenceEvidence(
                            evidence_type=EvidenceType.SEMANTIC_VALID,
                            source="enhanced_nik",
                            weight=0.1,
                            reason_code="nik_plausible_age",
                            description=f"Plausible age: {dob_result.age} years",
                        )
                    )
        else:
            score -= 0.1
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.CONTEXT_NEGATIVE,
                    source="enhanced_nik",
                    weight=-0.1,
                    reason_code="nik_invalid_dob",
                    description=f"Invalid DOB encoding: {dob_result.description}",
                )
            )

        return NIKValidationResult(
            score=min(score, 1.0),
            is_valid=score >= 0.7,
            evidence=evidence,
            metadata=self._extract_metadata(nik) if score >= 0.5 else None,
        )

    def _validate_birthdate(self, encoded: str) -> "DOBValidationResult":
        """
        Validate the birthdate portion of NIK.

        Format: DDMMYY where DD for female is day + 40

        Args:
            encoded: 6-digit encoded birthdate

        Returns:
            DOBValidationResult with validation status
        """
        try:
            day = int(encoded[:2])
            month = int(encoded[2:4])
            year_2digit = int(encoded[4:6])

            # Detect female encoding
            is_female = False
            if day > 40:
                day -= 40
                is_female = True

            # Validate day and month ranges
            if day < 1 or day > 31:
                return DOBValidationResult(
                    is_valid=False,
                    description=f"Invalid day: {day}",
                )
            if month < 1 or month > 12:
                return DOBValidationResult(
                    is_valid=False,
                    description=f"Invalid month: {month}",
                )

            # Determine full year
            # Assume 1900s for year > current 2-digit, 2000s otherwise
            current_year = date.today().year
            current_2digit = current_year % 100

            if year_2digit > current_2digit:
                full_year = 1900 + year_2digit
            else:
                full_year = 2000 + year_2digit

            # Check if date is not in future
            try:
                birth_date = date(full_year, month, day)
                if birth_date > date.today():
                    return DOBValidationResult(
                        is_valid=False,
                        description="Birth date is in future",
                    )

                # Calculate age
                today = date.today()
                age = today.year - birth_date.year
                if (today.month, today.day) < (birth_date.month, birth_date.day):
                    age -= 1

                # Age plausibility (0-120 years)
                if age > 120:
                    return DOBValidationResult(
                        is_valid=False,
                        description=f"Implausible age: {age} years",
                    )

                gender = "female" if is_female else "male"
                return DOBValidationResult(
                    is_valid=True,
                    description=f"{birth_date.strftime('%d/%m/%Y')} ({gender})",
                    birth_date=birth_date,
                    age=age,
                    is_female=is_female,
                )

            except ValueError as e:
                return DOBValidationResult(
                    is_valid=False,
                    description=f"Invalid date: {e}",
                )

        except (ValueError, IndexError) as e:
            return DOBValidationResult(
                is_valid=False,
                description=f"Parse error: {e}",
            )

    def _extract_metadata(self, nik: str) -> NIKMetadata | None:
        """Extract metadata from validated NIK."""
        if len(nik) != 16:
            return None

        province_code = nik[:2]
        if province_code not in VALID_PROVINCE_CODES:
            return None

        day = int(nik[6:8])
        is_female = day > 40
        if is_female:
            day -= 40

        month = int(nik[8:10])
        year_2digit = int(nik[10:12])
        current_2digit = date.today().year % 100
        full_year = 1900 + year_2digit if year_2digit > current_2digit else 2000 + year_2digit

        return NIKMetadata(
            province_code=province_code,
            province_name=VALID_PROVINCE_CODES[province_code],
            city_code=nik[2:4],
            district_code=nik[4:6],
            birth_day=day,
            birth_month=month,
            birth_year=full_year,
            is_female=is_female,
            sequence=nik[12:16],
            raw_nik=nik,
        )


@dataclass
class DOBValidationResult:
    """Result of DOB validation."""

    is_valid: bool
    description: str
    birth_date: date | None = None
    age: int | None = None
    is_female: bool = False


@dataclass
class NIKValidationResult:
    """Result of NIK validation."""

    score: float
    is_valid: bool
    evidence: list[ConfidenceEvidence]
    metadata: NIKMetadata | None = None


def parse_nik(nik: str) -> NIKMetadata | None:
    """
    Parse a NIK string and extract metadata.

    Args:
        nik: The 16-digit NIK string

    Returns:
        NIKMetadata if valid, None otherwise
    """
    recognizer = EnhancedNIKRecognizer()
    result = recognizer._validate_nik(nik)
    return result.metadata


__all__ = [
    "DOBValidationResult",
    "EnhancedNIKRecognizer",
    "NIK_CONTEXT_KEYWORDS",
    "NIKMetadata",
    "NIKValidationResult",
    "VALID_PROVINCE_CODES",
    "parse_nik",
]
