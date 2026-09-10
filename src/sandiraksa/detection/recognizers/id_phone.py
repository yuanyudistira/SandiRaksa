"""
Indonesian Phone Number Recognizer.

Formats:
- Mobile: 08XX-XXXX-XXXX, +62-8XX-XXXX-XXXX
- Landline: (0XX) XXXX-XXXX, +62-XX-XXXX-XXXX

Mobile prefixes (2024):
- Telkomsel: 0811-0813, 0821-0823, 0852, 0853, 0851
- Indosat: 0814-0816, 0855-0858
- XL Axiata: 0817-0819, 0859, 0877, 0878
- Axis: 0831-0833, 0838
- Tri: 0895-0899
- Smartfren: 0881-0889
"""

from __future__ import annotations

import re
from typing import ClassVar

from sandiraksa.detection.context import DetectionResult
from sandiraksa.detection.engine import BaseRecognizer


class IndonesianPhoneRecognizer(BaseRecognizer):
    """Recognizer for Indonesian phone numbers."""

    # Mobile patterns
    MOBILE_PATTERNS: ClassVar[list[tuple[re.Pattern, float]]] = [
        # International format: +62-8XX-XXXX-XXXX
        (re.compile(r"\+62[-.\s]?8\d{2}[-.\s]?\d{3,4}[-.\s]?\d{3,4}"), 0.95),
        # Local format: 08XX-XXXX-XXXX
        (re.compile(r"\b08\d{2}[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b"), 0.9),
        # No separator: 08XXXXXXXXX (10-12 digits total)
        (re.compile(r"\b08\d{8,10}\b"), 0.85),
    ]

    # Landline patterns.
    #
    # The "standard" pattern is deliberately kept tight: it REQUIRES an explicit
    # separator (space/dash/dot) between the area code and the subscriber part.
    # Without this, a bare 9-12 digit run like "021123456789" would be grabbed
    # as a landline and over-match arbitrary numeric IDs. Numbers that are truly
    # separator-less are still commonly written for mobiles (handled above);
    # unseparated landlines are rare and better left to explicit-format cases.
    LANDLINE_PATTERNS: ClassVar[list[tuple[re.Pattern, float]]] = [
        # International: +62-XX-XXXX-XXXX (separators optional)
        (re.compile(r"\+62[-.\s]?\d{2,3}[-.\s]?\d{3,4}[-.\s]?\d{3,4}"), 0.85),
        # With area code in parentheses: (0XX) XXXX-XXXX
        (re.compile(r"\(0\d{2,3}\)[-.\s]?\d{3,4}[-.\s]?\d{3,4}"), 0.9),
        # Standard: 0XX-XXXX-XXXX — REQUIRE at least one real separator so we
        # don't swallow arbitrary long digit runs.
        (re.compile(r"\b0\d{1,3}[-.\s]\d{3,4}[-.\s]?\d{3,4}\b"), 0.75),
    ]

    # Valid mobile prefixes
    MOBILE_PREFIXES: ClassVar[dict[str, str]] = {
        # Telkomsel
        "0811": "Telkomsel", "0812": "Telkomsel", "0813": "Telkomsel",
        "0821": "Telkomsel", "0822": "Telkomsel", "0823": "Telkomsel",
        "0851": "Telkomsel", "0852": "Telkomsel", "0853": "Telkomsel",
        # Indosat Ooredoo
        "0814": "Indosat", "0815": "Indosat", "0816": "Indosat",
        "0855": "Indosat", "0856": "Indosat", "0857": "Indosat", "0858": "Indosat",
        # XL Axiata
        "0817": "XL", "0818": "XL", "0819": "XL",
        "0859": "XL", "0877": "XL", "0878": "XL", "0879": "XL",
        # Axis
        "0831": "Axis", "0832": "Axis", "0833": "Axis", "0838": "Axis",
        # Tri
        "0895": "Tri", "0896": "Tri", "0897": "Tri", "0898": "Tri", "0899": "Tri",
        # Smartfren
        "0881": "Smartfren", "0882": "Smartfren", "0883": "Smartfren",
        "0884": "Smartfren", "0885": "Smartfren", "0886": "Smartfren",
        "0887": "Smartfren", "0888": "Smartfren", "0889": "Smartfren",
    }

    # Major city area codes
    AREA_CODES: ClassVar[dict[str, str]] = {
        "021": "Jakarta",
        "022": "Bandung",
        "024": "Semarang",
        "031": "Surabaya",
        "061": "Medan",
        "0411": "Makassar",
        "0361": "Bali",
        "0274": "Yogyakarta",
        "0271": "Solo",
        "0341": "Malang",
    }

    def __init__(self) -> None:
        super().__init__("id_phone", ["ID_PHONE"])

    def analyze(
        self,
        text: str,
        entities: list[str],
    ) -> list[DetectionResult]:
        """Analyze text for Indonesian phone numbers."""
        if "ID_PHONE" not in entities:
            return []

        results: list[DetectionResult] = []
        found_ranges: list[tuple[int, int]] = []

        # Check mobile patterns first (higher priority)
        for pattern, base_score in self.MOBILE_PATTERNS:
            for match in pattern.finditer(text):
                # Skip if overlaps with existing result
                if self._overlaps(match.start(), match.end(), found_ranges):
                    continue

                phone = self._normalize_phone(match.group())
                score = self._validate_mobile(phone, base_score)

                if score > 0.5:
                    results.append(
                        DetectionResult(
                            entity_type="ID_PHONE",
                            start=match.start(),
                            end=match.end(),
                            text=match.group(),
                            score=score,
                            recognizer_name="id_phone",
                            analysis_explanation={
                                "type": "mobile",
                                "carrier": self._get_carrier(phone),
                                "normalized": phone,
                            },
                        )
                    )
                    found_ranges.append((match.start(), match.end()))

        # Check landline patterns
        for pattern, base_score in self.LANDLINE_PATTERNS:
            for match in pattern.finditer(text):
                if self._overlaps(match.start(), match.end(), found_ranges):
                    continue

                phone = self._normalize_phone(match.group())

                # Skip if it looks like a mobile number
                if phone.startswith("08") or phone.startswith("+628"):
                    continue

                score = self._validate_landline(phone, base_score)

                if score > 0.5:
                    results.append(
                        DetectionResult(
                            entity_type="ID_PHONE",
                            start=match.start(),
                            end=match.end(),
                            text=match.group(),
                            score=score,
                            recognizer_name="id_phone",
                            analysis_explanation={
                                "type": "landline",
                                "area": self._get_area(phone),
                                "normalized": phone,
                            },
                        )
                    )
                    found_ranges.append((match.start(), match.end()))

        return results

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to digits only."""
        digits = "".join(c for c in phone if c.isdigit() or c == "+")

        # Convert +62 to 0
        if digits.startswith("+62"):
            digits = "0" + digits[3:]
        elif digits.startswith("62"):
            digits = "0" + digits[2:]

        return digits

    def _validate_mobile(self, phone: str, base_score: float) -> float:
        """Validate mobile phone number."""
        score = base_score

        # Check prefix
        prefix = phone[:4]
        if prefix in self.MOBILE_PREFIXES:
            score += 0.05
        else:
            score -= 0.2

        # Check length (should be 10-12 digits for mobile)
        if 10 <= len(phone) <= 13:
            pass  # OK
        else:
            score -= 0.3

        return max(0, min(score, 1.0))

    def _validate_landline(self, phone: str, base_score: float) -> float:
        """Validate landline phone number."""
        score = base_score

        # Check if starts with known area code
        for code in self.AREA_CODES:
            if phone.startswith(code):
                score += 0.1
                break

        # Check length (should be 9-12 digits for landline)
        if 9 <= len(phone) <= 12:
            pass  # OK
        else:
            score -= 0.2

        return max(0, min(score, 1.0))

    def _get_carrier(self, phone: str) -> str | None:
        """Get carrier name from mobile prefix."""
        prefix = phone[:4]
        return self.MOBILE_PREFIXES.get(prefix)

    def _get_area(self, phone: str) -> str | None:
        """Get area name from landline code."""
        for code, area in self.AREA_CODES.items():
            if phone.startswith(code):
                return area
        return None

    def _overlaps(
        self,
        start: int,
        end: int,
        ranges: list[tuple[int, int]],
    ) -> bool:
        """Check if range overlaps with existing ranges."""
        for r_start, r_end in ranges:
            if start < r_end and end > r_start:
                return True
        return False


def format_phone_indonesian(phone: str) -> str:
    """Format Indonesian phone number for display."""
    digits = "".join(c for c in phone if c.isdigit())

    # Mobile format
    if digits.startswith("08") and len(digits) >= 10:
        # Format as 08XX-XXXX-XXXX
        return f"{digits[:4]}-{digits[4:8]}-{digits[8:]}"

    # International mobile
    if digits.startswith("628") and len(digits) >= 11:
        # Format as +62-8XX-XXXX-XXXX
        return f"+62-{digits[2:5]}-{digits[5:9]}-{digits[9:]}"

    return phone  # Return as-is if can't format
