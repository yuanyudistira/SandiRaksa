"""
NPWP (Nomor Pokok Wajib Pajak) Recognizer.

Indonesian Tax ID Number - 15 or 16 digits:
- Old format (15 digits): XX.XXX.XXX.X-XXX.XXX
- New format (16 digits): Based on NIK for individuals

Structure (old format):
- Digits 1-2: Tax subject type (01-03 personal, 21-24 corporate, etc.)
- Digits 3-8: Unique registration number
- Digits 9: Check digit
- Digits 10-12: Tax office code
- Digits 13-15: Branch code (000 = main)
"""

from __future__ import annotations

import re
from typing import ClassVar

from sandiraksa.detection.context import DetectionResult
from sandiraksa.detection.engine import BaseRecognizer


class NPWPRecognizer(BaseRecognizer):
    """Recognizer for Indonesian NPWP (Tax ID Number)."""

    # Old format: XX.XXX.XXX.X-XXX.XXX or without separators
    PATTERN_OLD: ClassVar[re.Pattern] = re.compile(
        r"\b(\d{2})\.?(\d{3})\.?(\d{3})\.?(\d)[-.]?(\d{3})\.?(\d{3})\b"
    )

    # New format (16 digits, same as NIK for individuals)
    PATTERN_NEW: ClassVar[re.Pattern] = re.compile(
        r"\b(\d{16})\b"
    )

    # Valid tax subject type codes (first 2 digits)
    VALID_SUBJECT_TYPES: ClassVar[dict[str, str]] = {
        "00": "Bendahara",
        "01": "Orang Pribadi",
        "02": "Orang Pribadi",
        "03": "Orang Pribadi",
        "04": "Orang Pribadi Pengusaha",
        "05": "Orang Pribadi Pengusaha",
        "06": "Orang Pribadi Pengusaha",
        "07": "Orang Pribadi Pengusaha",
        "08": "Orang Pribadi Pengusaha",
        "09": "Orang Pribadi Pengusaha",
        "21": "Badan Usaha",
        "22": "Badan Usaha",
        "31": "Badan Usaha",
        "32": "Badan Usaha",
    }

    def __init__(self) -> None:
        super().__init__("npwp", ["ID_NPWP"])

    def analyze(
        self,
        text: str,
        entities: list[str],
    ) -> list[DetectionResult]:
        """Analyze text for NPWP numbers."""
        if "ID_NPWP" not in entities:
            return []

        results: list[DetectionResult] = []

        # Check old format (15 digits)
        for match in self.PATTERN_OLD.finditer(text):
            npwp = "".join(match.groups())
            score = self._validate_npwp_old(npwp)
            if score > 0:
                results.append(
                    DetectionResult(
                        entity_type="ID_NPWP",
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        score=score,
                        recognizer_name="npwp",
                        analysis_explanation={
                            "format": "old",
                            "subject_type": npwp[:2],
                            "registration": npwp[2:9],
                            "tax_office": npwp[9:12],
                            "branch": npwp[12:15],
                        },
                    )
                )

        # Check new format (16 digits) - same as NIK
        # We mark these with lower confidence since they could be NIK
        for match in self.PATTERN_NEW.finditer(text):
            npwp = match.group(1)

            # Skip if already detected as old format or in results
            already_covered = any(
                r.start <= match.start() and r.end >= match.end()
                for r in results
            )
            if already_covered:
                continue

            # Lower confidence for 16-digit format (could be NIK)
            score = 0.6 if self._looks_like_npwp_context(text, match) else 0.4

            results.append(
                DetectionResult(
                    entity_type="ID_NPWP",
                    start=match.start(),
                    end=match.end(),
                    text=match.group(),
                    score=score,
                    recognizer_name="npwp",
                    analysis_explanation={
                        "format": "new_16digit",
                        "note": "Could also be NIK, context suggests NPWP",
                    },
                )
            )

        return results

    def _validate_npwp_old(self, npwp: str) -> float:
        """Validate old format NPWP (15 digits)."""
        if len(npwp) != 15 or not npwp.isdigit():
            return 0.0

        score = 0.5  # Base score

        # Check subject type
        subject_type = npwp[:2]
        if subject_type in self.VALID_SUBJECT_TYPES:
            score += 0.25
        else:
            return 0.0  # Invalid subject type

        # Check digit validation (Luhn-like algorithm)
        if self._validate_check_digit(npwp):
            score += 0.25

        return min(score, 1.0)

    def _validate_check_digit(self, npwp: str) -> bool:
        """
        Validate NPWP check digit.

        Uses a weighted sum algorithm similar to Luhn.
        """
        if len(npwp) < 9:
            return False

        weights = [4, 3, 2, 7, 6, 5, 4, 3, 2]
        total = sum(
            int(npwp[i]) * weights[i]
            for i in range(min(len(weights), len(npwp) - 1))
        )

        remainder = total % 11
        expected_check = 11 - remainder if remainder != 0 else 0

        # Check digit is at position 8 (0-indexed)
        try:
            actual_check = int(npwp[8])
            return actual_check == expected_check or expected_check >= 10
        except (IndexError, ValueError):
            return False

    def _looks_like_npwp_context(
        self, text: str, match: re.Match
    ) -> bool:
        """Check if surrounding context suggests NPWP."""
        # Look for keywords near the match
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 30)
        context = text[start:end].lower()

        npwp_keywords = [
            "npwp",
            "pajak",
            "tax",
            "wajib pajak",
            "nomor pokok",
            "dirjen pajak",
            "efin",
            "spt",
        ]

        return any(kw in context for kw in npwp_keywords)


def format_npwp(npwp: str) -> str:
    """Format NPWP to standard display format: XX.XXX.XXX.X-XXX.XXX"""
    digits = "".join(c for c in npwp if c.isdigit())

    if len(digits) == 15:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}.{digits[8]}-{digits[9:12]}.{digits[12:15]}"
    elif len(digits) == 16:
        return digits  # New format doesn't have standard formatting yet

    return npwp  # Return as-is if can't format
