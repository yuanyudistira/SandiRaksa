"""
Enhanced NPWP (Nomor Pokok Wajib Pajak) Recognizer.

Indonesian Tax ID Number with multiple formats:

Legacy Format (15 digits):
- Digits 1-2: Tax office category
- Digits 3-8: Registration sequence
- Digit 9: Check digit
- Digits 10-12: Branch code (000 = main)
- Digits 13-15: Tax office code

Current Format (16 digits - NIK-based):
- Since 2024, NPWP uses NIK for individuals
- Businesses use 16-digit format

Supported Format Variants:
- Plain: 012345678901234
- Formatted: 01.234.567.8-901.234
- With spaces: 01 234 567 8 901 234
- NIK as NPWP (16 digits)
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
    ConfidenceBand,
    ConfidenceEvidence,
    EvidenceType,
    UnifiedFinding,
    classify_confidence,
)

if TYPE_CHECKING:
    from sandiraksa.documents.logical_segment import LogicalSegment


# Context keywords for NPWP
NPWP_CONTEXT_KEYWORDS: set[str] = {
    "npwp",
    "nomor pokok wajib pajak",
    "tax id",
    "tax number",
    "nomor pajak",
    "wajib pajak",
    "pajak",
    "tax identification",
    "tin",  # Tax Identification Number
}

# Valid tax office category codes (first 2 digits)
# These indicate type of taxpayer
VALID_TAX_CATEGORIES: set[str] = {
    "01", "02", "03", "04", "05", "06", "07", "08", "09",
    "21", "31", "41", "51", "61", "71", "81",  # Corporate categories
}


@dataclass
class NPWPMetadata:
    """Parsed metadata from an NPWP number."""

    raw_npwp: str
    digits_only: str
    is_legacy_format: bool  # 15-digit legacy
    is_nik_based: bool      # 16-digit NIK format
    category_code: str | None
    registration_number: str | None
    check_digit: str | None
    branch_code: str | None
    tax_office_code: str | None
    is_main_branch: bool


class EnhancedNPWPRecognizer(BaseUnifiedRecognizer):
    """
    Enhanced recognizer for Indonesian NPWP with format variants.

    Supports:
    - Legacy 15-digit NPWP
    - Current 16-digit NPWP (NIK-based)
    - Multiple format variants (with/without separators)
    - Context-aware confidence boost
    """

    # Pattern for legacy 15-digit NPWP (formatted)
    # Format: XX.XXX.XXX.X-XXX.XXX
    PATTERN_FORMATTED_15: ClassVar[re.Pattern[str]] = re.compile(
        r"\b"
        r"(\d{2})[.\s]?"  # Category (2)
        r"(\d{3})[.\s]?"  # Registration part 1 (3)
        r"(\d{3})[.\s]?"  # Registration part 2 (3)
        r"(\d)[-.\s]?"    # Check digit (1)
        r"(\d{3})[.\s]?"  # Branch code (3)
        r"(\d{3})"        # Tax office (3)
        r"\b"
    )

    # Pattern for plain 15 digits
    PATTERN_PLAIN_15: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(\d{15})\b"
    )

    # Pattern for 16-digit (NIK-based NPWP)
    PATTERN_16: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(\d{16})\b"
    )

    # Combined pattern to catch formatted variants
    PATTERN_FORMATTED_VARIANTS: ClassVar[re.Pattern[str]] = re.compile(
        r"\b"
        r"\d{2}[.\s-]?\d{3}[.\s-]?\d{3}[.\s-]?\d[.\s-]?\d{3}[.\s-]?\d{3}"
        r"\b"
    )

    def __init__(self, priority: int = 82) -> None:
        """Initialize enhanced NPWP recognizer."""
        super().__init__(
            name="enhanced_npwp",
            supported_entities=["ID_NPWP"],
            priority=priority,
        )

    def analyze(
        self,
        segment: "LogicalSegment",
        context: DetectionContext,
    ) -> list[UnifiedFinding]:
        """
        Analyze segment for NPWP numbers.

        Args:
            segment: LogicalSegment to analyze
            context: Detection context

        Returns:
            List of UnifiedFinding for detected NPWPs
        """
        if not context.should_detect_entity("ID_NPWP"):
            return []

        if not segment.text:
            return []

        findings: list[UnifiedFinding] = []
        text = segment.text
        found_positions: set[tuple[int, int]] = set()

        # Check for context boost
        has_context_boost = self._has_npwp_context(segment)

        # Try formatted 15-digit pattern first
        for match in self.PATTERN_FORMATTED_15.finditer(text):
            pos = (match.start(), match.end())
            if pos in found_positions:
                continue

            digits = "".join(match.groups())
            if len(digits) == 15:
                finding = self._create_finding(
                    segment=segment,
                    match_text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    digits=digits,
                    is_formatted=True,
                    has_context_boost=has_context_boost,
                )
                if finding:
                    findings.append(finding)
                    found_positions.add(pos)

        # Try formatted variants pattern
        for match in self.PATTERN_FORMATTED_VARIANTS.finditer(text):
            pos = (match.start(), match.end())
            if pos in found_positions:
                continue

            # Extract digits only
            digits = re.sub(r"[^\d]", "", match.group())
            if len(digits) == 15:
                finding = self._create_finding(
                    segment=segment,
                    match_text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    digits=digits,
                    is_formatted=True,
                    has_context_boost=has_context_boost,
                )
                if finding:
                    findings.append(finding)
                    found_positions.add(pos)

        # Try plain 15-digit pattern
        for match in self.PATTERN_PLAIN_15.finditer(text):
            pos = (match.start(), match.end())
            if pos in found_positions:
                continue

            digits = match.group(1)
            # Only accept if has NPWP context (to avoid matching random 15-digit numbers)
            if has_context_boost:
                finding = self._create_finding(
                    segment=segment,
                    match_text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    digits=digits,
                    is_formatted=False,
                    has_context_boost=has_context_boost,
                )
                if finding:
                    findings.append(finding)
                    found_positions.add(pos)

        # Try 16-digit pattern (NIK-based NPWP)
        for match in self.PATTERN_16.finditer(text):
            pos = (match.start(), match.end())
            if pos in found_positions:
                continue

            digits = match.group(1)
            # For 16-digit, only if explicit NPWP context (not NIK context)
            if has_context_boost and self._is_npwp_not_nik_context(segment):
                finding = self._create_finding_16(
                    segment=segment,
                    match_text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    digits=digits,
                    has_context_boost=has_context_boost,
                )
                if finding:
                    findings.append(finding)
                    found_positions.add(pos)

        return findings

    def _has_npwp_context(self, segment: "LogicalSegment") -> bool:
        """Check if segment has NPWP-related context."""
        # Check key_label
        if segment.key_label:
            label_lower = segment.key_label.lower()
            if any(kw in label_lower for kw in NPWP_CONTEXT_KEYWORDS):
                return True

        # Check context labels
        for label in segment.context_labels:
            label_lower = label.lower()
            if any(kw in label_lower for kw in NPWP_CONTEXT_KEYWORDS):
                return True

        # Check surrounding text
        text_lower = segment.text.lower()
        for kw in NPWP_CONTEXT_KEYWORDS:
            if kw in text_lower:
                return True

        return False

    def _is_npwp_not_nik_context(self, segment: "LogicalSegment") -> bool:
        """Check if context explicitly mentions NPWP (not NIK)."""
        npwp_keywords = {"npwp", "pajak", "tax", "wajib pajak"}
        nik_keywords = {"nik", "ktp", "kartu tanda penduduk", "identitas"}

        text_lower = segment.text.lower()
        label_lower = (segment.key_label or "").lower()

        has_npwp = any(kw in text_lower or kw in label_lower for kw in npwp_keywords)
        has_nik = any(kw in text_lower or kw in label_lower for kw in nik_keywords)

        return has_npwp and not has_nik

    def _create_finding(
        self,
        segment: "LogicalSegment",
        match_text: str,
        start: int,
        end: int,
        digits: str,
        is_formatted: bool,
        has_context_boost: bool,
    ) -> UnifiedFinding | None:
        """Create finding for 15-digit NPWP."""
        validation = self._validate_npwp_15(digits, is_formatted)
        if validation.score <= 0:
            return None

        # Get context window
        context_before, context_after = segment.get_context_window(
            start, end, window_size=30
        )

        # Calculate final score
        final_score = validation.score
        if has_context_boost:
            final_score = min(1.0, final_score + 0.15)

        finding = UnifiedFinding(
            segment_id=segment.id,
            entity_type="ID_NPWP",
            start=start,
            end=end,
            raw_score=final_score,
            confidence_band=classify_confidence(final_score),
            detector="enhanced_npwp",
            detected_text=match_text,
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
                    source="enhanced_npwp",
                    weight=0.15,
                    reason_code="npwp_context_keyword",
                    description="NPWP context keyword found nearby",
                )
            )

        return finding

    def _create_finding_16(
        self,
        segment: "LogicalSegment",
        match_text: str,
        start: int,
        end: int,
        digits: str,
        has_context_boost: bool,
    ) -> UnifiedFinding | None:
        """Create finding for 16-digit NPWP (NIK-based)."""
        # Basic validation for 16-digit
        if len(digits) != 16 or not digits.isdigit():
            return None

        # Get context window
        context_before, context_after = segment.get_context_window(
            start, end, window_size=30
        )

        # Lower base score for 16-digit (could be NIK)
        score = 0.6 if has_context_boost else 0.4

        finding = UnifiedFinding(
            segment_id=segment.id,
            entity_type="ID_NPWP",
            start=start,
            end=end,
            raw_score=score,
            confidence_band=classify_confidence(score),
            detector="enhanced_npwp",
            detected_text=match_text,
            context_before=context_before,
            context_after=context_after,
            is_validated=False,  # Can't validate 16-digit structurally
        )

        finding.add_evidence(
            ConfidenceEvidence(
                evidence_type=EvidenceType.PATTERN_MATCH,
                source="enhanced_npwp",
                weight=0.4,
                reason_code="npwp_16_digit_nik_based",
                description="16-digit NIK-based NPWP format (since 2024)",
            )
        )

        if has_context_boost:
            finding.add_evidence(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.CONTEXT_POSITIVE,
                    source="enhanced_npwp",
                    weight=0.2,
                    reason_code="npwp_explicit_context",
                    description="Explicit NPWP context (not NIK)",
                )
            )

        return finding

    def _validate_npwp_15(self, digits: str, is_formatted: bool) -> "NPWPValidationResult":
        """
        Validate 15-digit NPWP.

        Args:
            digits: The 15-digit NPWP string
            is_formatted: Whether the original was formatted

        Returns:
            NPWPValidationResult with score and evidence
        """
        evidence: list[ConfidenceEvidence] = []

        if len(digits) != 15 or not digits.isdigit():
            return NPWPValidationResult(score=0.0, is_valid=False, evidence=[])

        # Base score
        score = 0.5 if is_formatted else 0.3
        evidence.append(
            ConfidenceEvidence(
                evidence_type=EvidenceType.PATTERN_MATCH,
                source="enhanced_npwp",
                weight=score,
                reason_code="npwp_15_digit_pattern",
                description=f"Matches 15-digit NPWP pattern ({'formatted' if is_formatted else 'plain'})",
            )
        )

        # Validate category code (first 2 digits)
        category = digits[:2]
        if category in VALID_TAX_CATEGORIES:
            score += 0.15
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.STRUCTURAL_VALID,
                    source="enhanced_npwp",
                    weight=0.15,
                    reason_code="npwp_valid_category",
                    description=f"Valid tax category code: {category}",
                )
            )
        else:
            # Non-standard category, might still be valid
            pass

        # Check branch code (digits 10-12)
        branch_code = digits[9:12]
        if branch_code == "000":
            # Main branch
            score += 0.1
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.STRUCTURAL_VALID,
                    source="enhanced_npwp",
                    weight=0.1,
                    reason_code="npwp_main_branch",
                    description="Main branch (000)",
                )
            )

        # Check for all zeros (invalid)
        if digits == "0" * 15:
            return NPWPValidationResult(score=0.0, is_valid=False, evidence=evidence)

        # Check for repeating patterns (likely invalid)
        if len(set(digits)) == 1:
            return NPWPValidationResult(score=0.0, is_valid=False, evidence=evidence)

        # Extract metadata
        metadata = NPWPMetadata(
            raw_npwp=digits,
            digits_only=digits,
            is_legacy_format=True,
            is_nik_based=False,
            category_code=category,
            registration_number=digits[2:8],
            check_digit=digits[8],
            branch_code=branch_code,
            tax_office_code=digits[12:15],
            is_main_branch=branch_code == "000",
        )

        return NPWPValidationResult(
            score=min(score, 1.0),
            is_valid=score >= 0.6,
            evidence=evidence,
            metadata=metadata,
        )


@dataclass
class NPWPValidationResult:
    """Result of NPWP validation."""

    score: float
    is_valid: bool
    evidence: list[ConfidenceEvidence]
    metadata: NPWPMetadata | None = None


def format_npwp(digits: str) -> str:
    """
    Format NPWP digits into standard format.

    Args:
        digits: 15-digit NPWP

    Returns:
        Formatted NPWP: XX.XXX.XXX.X-XXX.XXX
    """
    if len(digits) != 15 or not digits.isdigit():
        return digits

    return (
        f"{digits[0:2]}."
        f"{digits[2:5]}."
        f"{digits[5:8]}."
        f"{digits[8]}-"
        f"{digits[9:12]}."
        f"{digits[12:15]}"
    )


def parse_npwp(npwp: str) -> NPWPMetadata | None:
    """
    Parse an NPWP string and extract metadata.

    Args:
        npwp: The NPWP string (formatted or plain)

    Returns:
        NPWPMetadata if valid, None otherwise
    """
    # Remove non-digits
    digits = re.sub(r"[^\d]", "", npwp)

    if len(digits) == 15:
        recognizer = EnhancedNPWPRecognizer()
        result = recognizer._validate_npwp_15(digits, is_formatted=True)
        return result.metadata
    elif len(digits) == 16:
        return NPWPMetadata(
            raw_npwp=npwp,
            digits_only=digits,
            is_legacy_format=False,
            is_nik_based=True,
            category_code=None,
            registration_number=None,
            check_digit=None,
            branch_code=None,
            tax_office_code=None,
            is_main_branch=False,
        )

    return None


__all__ = [
    "EnhancedNPWPRecognizer",
    "NPWP_CONTEXT_KEYWORDS",
    "NPWPMetadata",
    "NPWPValidationResult",
    "VALID_TAX_CATEGORIES",
    "format_npwp",
    "parse_npwp",
]
