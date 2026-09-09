"""
Enhanced Indonesian Phone Number Recognizer.

Uses the phonenumbers library for robust validation.

Indonesian Phone Format:
- Mobile: 08xx-xxxx-xxxx (starts with 08)
- International: +62 8xx-xxxx-xxxx
- Landline: (0xx) xxx-xxxx

Carrier Prefixes (mobile):
- Telkomsel: 0811, 0812, 0813, 0821, 0822, 0823, 0851, 0852, 0853
- Indosat: 0814, 0815, 0816, 0855, 0856, 0857, 0858
- XL: 0817, 0818, 0819, 0859, 0877, 0878
- Axis: 0831, 0832, 0833, 0838
- Three: 0895, 0896, 0897, 0898, 0899
- Smartfren: 0881, 0882, 0883, 0884, 0885, 0886, 0887, 0888, 0889

Features:
- phonenumbers validation (is_possible, is_valid)
- Carrier detection
- Multiple format support
- Context-aware confidence
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

# Try to import phonenumbers
try:
    import phonenumbers
    from phonenumbers import (
        PhoneNumberFormat,
        carrier,
        geocoder,
        is_possible_number,
        is_valid_number,
        number_type,
        parse as parse_phone,
    )
    from phonenumbers.phonenumberutil import PhoneNumberType

    PHONENUMBERS_AVAILABLE = True
except ImportError:
    PHONENUMBERS_AVAILABLE = False


# Context keywords for phone
PHONE_CONTEXT_KEYWORDS: set[str] = {
    "telepon",
    "telp",
    "telpon",
    "hp",
    "handphone",
    "no. hp",
    "no hp",
    "nomor hp",
    "phone",
    "mobile",
    "cell",
    "whatsapp",
    "wa",
    "contact",
    "kontak",
    "hubungi",
}

# Indonesian mobile carrier prefixes (after 0 or 62)
CARRIER_PREFIXES: dict[str, str] = {
    # Telkomsel
    "811": "Telkomsel", "812": "Telkomsel", "813": "Telkomsel",
    "821": "Telkomsel", "822": "Telkomsel", "823": "Telkomsel",
    "851": "Telkomsel", "852": "Telkomsel", "853": "Telkomsel",
    # Indosat Ooredoo
    "814": "Indosat", "815": "Indosat", "816": "Indosat",
    "855": "Indosat", "856": "Indosat", "857": "Indosat", "858": "Indosat",
    # XL Axiata
    "817": "XL", "818": "XL", "819": "XL",
    "859": "XL", "877": "XL", "878": "XL", "879": "XL",
    # Axis
    "831": "Axis", "832": "Axis", "833": "Axis", "838": "Axis",
    # Three (3)
    "895": "Three", "896": "Three", "897": "Three",
    "898": "Three", "899": "Three",
    # Smartfren
    "881": "Smartfren", "882": "Smartfren", "883": "Smartfren",
    "884": "Smartfren", "885": "Smartfren", "886": "Smartfren",
    "887": "Smartfren", "888": "Smartfren", "889": "Smartfren",
}


@dataclass
class PhoneMetadata:
    """Parsed metadata from a phone number."""

    raw_number: str
    national_number: str
    e164_format: str
    international_format: str
    is_mobile: bool
    is_valid: bool
    carrier_name: str | None
    region: str | None


class EnhancedPhoneRecognizer(BaseUnifiedRecognizer):
    """
    Enhanced recognizer for Indonesian phone numbers.

    Uses phonenumbers library for robust validation when available,
    falls back to regex-based detection otherwise.

    Features:
    - phonenumbers validation (is_possible, is_valid)
    - Carrier detection from prefix
    - Multiple format support (+62, 62, 08xx)
    - Context-aware confidence
    """

    # Pattern for Indonesian phone numbers
    # Matches: +62xxx, 62xxx, 08xxx with various separators
    PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"(?<![0-9])"  # Not preceded by digit
        r"(?:"
        r"(?:\+62|62)[\s.\-]?([1-9][0-9]{7,11})"  # +62 or 62 format
        r"|"
        r"(0[1-9][0-9]{6,11})"  # 0xxx format
        r")"
        r"(?![0-9])"  # Not followed by digit
    )

    # More lenient pattern to catch formatted numbers
    PATTERN_FORMATTED: ClassVar[re.Pattern[str]] = re.compile(
        r"(?<![0-9])"
        r"(?:"
        r"(?:\+62|62)[\s.\-]?[0-9][\s.\-]?(?:[0-9][\s.\-]?){6,11}"
        r"|"
        r"0[1-9][\s.\-]?(?:[0-9][\s.\-]?){6,11}"
        r")"
        r"(?![0-9])"
    )

    def __init__(self, priority: int = 75) -> None:
        """Initialize enhanced phone recognizer."""
        super().__init__(
            name="enhanced_phone",
            supported_entities=["ID_PHONE", "PHONE_NUMBER"],
            priority=priority,
        )

    def analyze(
        self,
        segment: "LogicalSegment",
        context: DetectionContext,
    ) -> list[UnifiedFinding]:
        """
        Analyze segment for Indonesian phone numbers.

        Args:
            segment: LogicalSegment to analyze
            context: Detection context

        Returns:
            List of UnifiedFinding for detected phones
        """
        should_detect = (
            context.should_detect_entity("ID_PHONE") or
            context.should_detect_entity("PHONE_NUMBER")
        )
        if not should_detect:
            return []

        if not segment.text:
            return []

        findings: list[UnifiedFinding] = []
        text = segment.text
        found_positions: set[tuple[int, int]] = set()

        # Check for context boost
        has_context_boost = self._has_phone_context(segment)

        # Try formatted pattern first (catches numbers with spaces/dashes)
        for match in self.PATTERN_FORMATTED.finditer(text):
            pos = (match.start(), match.end())
            if pos in found_positions:
                continue

            match_text = match.group()
            finding = self._create_finding(
                segment=segment,
                match_text=match_text,
                start=match.start(),
                end=match.end(),
                has_context_boost=has_context_boost,
            )
            if finding:
                findings.append(finding)
                found_positions.add(pos)

        # Try basic pattern for any missed ones
        for match in self.PATTERN.finditer(text):
            pos = (match.start(), match.end())
            if pos in found_positions:
                continue

            match_text = match.group()
            finding = self._create_finding(
                segment=segment,
                match_text=match_text,
                start=match.start(),
                end=match.end(),
                has_context_boost=has_context_boost,
            )
            if finding:
                findings.append(finding)
                found_positions.add(pos)

        return findings

    def _has_phone_context(self, segment: "LogicalSegment") -> bool:
        """Check if segment has phone-related context."""
        # Check key_label
        if segment.key_label:
            label_lower = segment.key_label.lower()
            if any(kw in label_lower for kw in PHONE_CONTEXT_KEYWORDS):
                return True

        # Check context labels
        for label in segment.context_labels:
            label_lower = label.lower()
            if any(kw in label_lower for kw in PHONE_CONTEXT_KEYWORDS):
                return True

        # Check surrounding text
        text_lower = segment.text.lower()
        for kw in PHONE_CONTEXT_KEYWORDS:
            if kw in text_lower:
                return True

        return False

    def _create_finding(
        self,
        segment: "LogicalSegment",
        match_text: str,
        start: int,
        end: int,
        has_context_boost: bool,
    ) -> UnifiedFinding | None:
        """Create finding for phone number."""
        validation = self._validate_phone(match_text)
        if validation.score <= 0:
            return None

        # Get context window
        context_before, context_after = segment.get_context_window(
            start, end, window_size=30
        )

        # Calculate final score
        final_score = validation.score
        if has_context_boost:
            final_score = min(1.0, final_score + 0.1)

        # Determine entity type
        entity_type = "ID_PHONE" if validation.metadata and validation.metadata.is_mobile else "PHONE_NUMBER"

        finding = UnifiedFinding(
            segment_id=segment.id,
            entity_type=entity_type,
            start=start,
            end=end,
            raw_score=final_score,
            confidence_band=classify_confidence(final_score),
            detector="enhanced_phone",
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
                    source="enhanced_phone",
                    weight=0.1,
                    reason_code="phone_context_keyword",
                    description="Phone context keyword found nearby",
                )
            )

        return finding

    def _validate_phone(self, phone_str: str) -> "PhoneValidationResult":
        """
        Validate phone number.

        Uses phonenumbers library if available, otherwise regex validation.

        Args:
            phone_str: The phone string to validate

        Returns:
            PhoneValidationResult with score and evidence
        """
        evidence: list[ConfidenceEvidence] = []

        # Clean the number (remove spaces, dashes, dots)
        cleaned = re.sub(r"[\s.\-()]", "", phone_str)

        # Normalize to +62 format
        if cleaned.startswith("0"):
            normalized = "+62" + cleaned[1:]
        elif cleaned.startswith("62"):
            normalized = "+" + cleaned
        elif cleaned.startswith("+62"):
            normalized = cleaned
        else:
            return PhoneValidationResult(score=0.0, is_valid=False, evidence=[])

        # Check length (Indonesian mobile: +62 + 9-12 digits)
        digits_after_62 = normalized[3:]
        if len(digits_after_62) < 8 or len(digits_after_62) > 12:
            return PhoneValidationResult(score=0.0, is_valid=False, evidence=[])

        # Base score for matching pattern
        score = 0.5
        evidence.append(
            ConfidenceEvidence(
                evidence_type=EvidenceType.PATTERN_MATCH,
                source="enhanced_phone",
                weight=0.5,
                reason_code="phone_pattern_match",
                description="Matches Indonesian phone pattern",
            )
        )

        # Use phonenumbers library if available
        if PHONENUMBERS_AVAILABLE:
            try:
                parsed = parse_phone(normalized, "ID")

                # Check if possible number
                if is_possible_number(parsed):
                    score += 0.15
                    evidence.append(
                        ConfidenceEvidence(
                            evidence_type=EvidenceType.STRUCTURAL_VALID,
                            source="phonenumbers",
                            weight=0.15,
                            reason_code="phone_possible",
                            description="phonenumbers: possible number",
                        )
                    )

                    # Check if valid number
                    if is_valid_number(parsed):
                        score += 0.2
                        evidence.append(
                            ConfidenceEvidence(
                                evidence_type=EvidenceType.SEMANTIC_VALID,
                                source="phonenumbers",
                                weight=0.2,
                                reason_code="phone_valid",
                                description="phonenumbers: valid Indonesian number",
                            )
                        )

                        # Get number type
                        num_type = number_type(parsed)
                        is_mobile = num_type == PhoneNumberType.MOBILE

                        # Get carrier if mobile
                        carrier_name = None
                        if is_mobile:
                            try:
                                carrier_name = carrier.name_for_number(parsed, "en")
                            except Exception:
                                pass

                        # Format the number
                        e164 = phonenumbers.format_number(
                            parsed, PhoneNumberFormat.E164
                        )
                        international = phonenumbers.format_number(
                            parsed, PhoneNumberFormat.INTERNATIONAL
                        )
                        national = phonenumbers.format_number(
                            parsed, PhoneNumberFormat.NATIONAL
                        )

                        metadata = PhoneMetadata(
                            raw_number=phone_str,
                            national_number=national,
                            e164_format=e164,
                            international_format=international,
                            is_mobile=is_mobile,
                            is_valid=True,
                            carrier_name=carrier_name,
                            region="ID",
                        )

                        return PhoneValidationResult(
                            score=min(score, 1.0),
                            is_valid=True,
                            evidence=evidence,
                            metadata=metadata,
                        )

            except Exception:
                # phonenumbers failed, fall back to regex validation
                pass

        # Fallback: regex-based validation
        # Check carrier prefix
        prefix_3 = digits_after_62[:3] if len(digits_after_62) >= 3 else ""
        carrier_name = CARRIER_PREFIXES.get(prefix_3)

        if carrier_name:
            score += 0.15
            evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.STRUCTURAL_VALID,
                    source="enhanced_phone",
                    weight=0.15,
                    reason_code="phone_carrier_prefix",
                    description=f"Valid carrier prefix: {carrier_name}",
                )
            )
            is_mobile = True
        else:
            is_mobile = digits_after_62.startswith("8")

        metadata = PhoneMetadata(
            raw_number=phone_str,
            national_number="0" + digits_after_62,
            e164_format=normalized,
            international_format=f"+62 {digits_after_62}",
            is_mobile=is_mobile,
            is_valid=score >= 0.6,
            carrier_name=carrier_name,
            region="ID",
        )

        return PhoneValidationResult(
            score=min(score, 1.0),
            is_valid=score >= 0.6,
            evidence=evidence,
            metadata=metadata,
        )


@dataclass
class PhoneValidationResult:
    """Result of phone validation."""

    score: float
    is_valid: bool
    evidence: list[ConfidenceEvidence]
    metadata: PhoneMetadata | None = None


def format_phone_indonesia(phone: str) -> str:
    """
    Format Indonesian phone number to standard format.

    Args:
        phone: Raw phone string

    Returns:
        Formatted phone: +62 XXX-XXXX-XXXX
    """
    # Clean the number
    cleaned = re.sub(r"[^\d+]", "", phone)

    # Normalize
    if cleaned.startswith("0"):
        cleaned = "+62" + cleaned[1:]
    elif cleaned.startswith("62"):
        cleaned = "+" + cleaned
    elif not cleaned.startswith("+62"):
        return phone  # Can't format

    if PHONENUMBERS_AVAILABLE:
        try:
            parsed = parse_phone(cleaned, "ID")
            return phonenumbers.format_number(
                parsed, PhoneNumberFormat.INTERNATIONAL
            )
        except Exception:
            pass

    # Manual formatting
    digits = cleaned[3:]  # After +62
    if len(digits) >= 10:
        return f"+62 {digits[:3]}-{digits[3:7]}-{digits[7:]}"
    return cleaned


def parse_phone_indonesia(phone: str) -> PhoneMetadata | None:
    """
    Parse an Indonesian phone number.

    Args:
        phone: The phone string

    Returns:
        PhoneMetadata if valid, None otherwise
    """
    recognizer = EnhancedPhoneRecognizer()
    result = recognizer._validate_phone(phone)
    return result.metadata


__all__ = [
    "CARRIER_PREFIXES",
    "EnhancedPhoneRecognizer",
    "PHONE_CONTEXT_KEYWORDS",
    "PHONENUMBERS_AVAILABLE",
    "PhoneMetadata",
    "PhoneValidationResult",
    "format_phone_indonesia",
    "parse_phone_indonesia",
]
