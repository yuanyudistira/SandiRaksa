"""
NPWP (Nomor Pokok Wajib Pajak) Recognizer.

Indonesian Tax ID Number. Per DJP rule PER-06/PJ/2024, effective 1 July 2024:
- 15-digit format is retired; 16 digits is mandatory.
- Resident individuals: NPWP = NIK (16 digits).
- Migrated legacy taxpayers: 16 digits = "0" + old 15 digits.
- NITKU (22 digits) replaces the branch code (out of scope here).

Structure (legacy 15-digit format): XX.XXX.XXX.X-XXX.XXX
- Digits 1-2:  Tax subject type (01-09 personal, 21-32 corporate, etc.)
- Digits 3-8:  Unique registration number
- Digit  9:    Check digit
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

    # Legacy 15-digit format: XX.XXX.XXX.X-XXX.XXX.
    # Separators are optional and may be dot, dash, or SPACE (e.g. an OCR-ed
    # document rendering "01 234 567 8 901 234").
    PATTERN_OLD: ClassVar[re.Pattern] = re.compile(
        r"\b(\d{2})[.\s]?(\d{3})[.\s]?(\d{3})[.\s]?(\d)[-.\s]?(\d{3})[.\s]?(\d{3})\b"
    )

    # New 16-digit format (mandatory since 1 July 2024). Same shape as NIK for
    # resident individuals, so this alone is ambiguous without context.
    # Matches with or without space/dot grouping.
    PATTERN_NEW: ClassVar[re.Pattern] = re.compile(
        r"\b(\d{2})[.\s]?(\d{3})[.\s]?(\d{3})[.\s]?(\d)[-.\s]?(\d{3})[.\s]?(\d{3})[.\s]?(\d)\b"
        r"|"
        r"\b(\d{16})\b"
    )

    # Valid tax subject type codes (first 2 digits of the legacy 15-digit form,
    # or of the trailing 15 digits of a migrated "0"+15 number).
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

    NPWP_KEYWORDS: ClassVar[list[str]] = [
        "npwp",
        "pajak",
        "tax",
        "wajib pajak",
        "nomor pokok",
        "dirjen pajak",
        "ditjen pajak",
        "efin",
        "spt",
    ]

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

        # Check legacy 15-digit format first (most specific span).
        for match in self.PATTERN_OLD.finditer(text):
            npwp = "".join(match.groups())
            if len(npwp) != 15:
                continue
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
                            "format": "legacy_15digit",
                            "subject_type": npwp[:2],
                            "registration": npwp[2:9],
                            "tax_office": npwp[9:12],
                            "branch": npwp[12:15],
                        },
                    )
                )

        # Check 16-digit format (current mandatory form).
        for match in self.PATTERN_NEW.finditer(text):
            # group(8) is the plain 16-digit alternative; groups 1-7 the grouped
            # form. Reconstruct the digit string either way.
            if match.group(8):
                npwp = match.group(8)
            else:
                npwp = "".join(g for g in match.groups()[:7] if g)
            if len(npwp) != 16 or not npwp.isdigit():
                continue

            # Skip spans already covered by a legacy-format result.
            already_covered = any(
                r.start <= match.start() and r.end >= match.end()
                for r in results
            )
            if already_covered:
                continue

            has_context = self._looks_like_npwp_context(text, match)
            score, fmt = self._score_npwp_16(npwp, has_context)
            if score <= 0:
                continue

            results.append(
                DetectionResult(
                    entity_type="ID_NPWP",
                    start=match.start(),
                    end=match.end(),
                    text=match.group(),
                    score=score,
                    recognizer_name="npwp",
                    analysis_explanation={
                        "format": fmt,
                        "note": (
                            "16-digit NPWP (mandatory since 1 Jul 2024); "
                            "may also be a NIK if no tax context"
                        ),
                    },
                )
            )

        return results

    def _score_npwp_16(self, npwp: str, has_context: bool) -> tuple[float, str]:
        """
        Score a 16-digit candidate.

        Two sub-cases:
        - Migrated legacy number: "0" + 15 digits whose subject type is valid.
          These are strong signals -> high score even without context.
        - Plain 16-digit (NIK-shaped): ambiguous vs NIK, so context drives the
          score; without context we keep it deliberately low so NIK detection
          is not masked.

        Returns (score, format_label).
        """
        # Migrated legacy: leading 0 + valid 15-digit legacy body.
        if npwp.startswith("0") and npwp[1:3] in self.VALID_SUBJECT_TYPES:
            base = 0.75
            if has_context:
                base += 0.15
            return min(base, 1.0), "migrated_0plus15"

        # Plain 16-digit NIK-shaped number.
        if has_context:
            return 0.85, "new_16digit_context"
        return 0.5, "new_16digit_no_context"

    def _validate_npwp_old(self, npwp: str) -> float:
        """
        Validate legacy 15-digit NPWP.

        Confidence model:
        - base 0.5
        - +0.25 if the subject-type code is valid (else reject: this is the
          primary guard against false positives)
        - +0.15 BONUS if the (unofficial) check digit matches. A failing check
          digit does NOT reduce the score, because DJP has not published the
          official algorithm and we must avoid false-rejecting valid numbers.
        """
        if len(npwp) != 15 or not npwp.isdigit():
            return 0.0

        subject_type = npwp[:2]
        if subject_type not in self.VALID_SUBJECT_TYPES:
            return 0.0  # Invalid subject type -> not an NPWP

        score = 0.5 + 0.25  # base + valid subject type

        # Check digit is a bonus signal only.
        if self._validate_check_digit(npwp):
            score += 0.15

        return min(score, 1.0)

    def _validate_check_digit(self, npwp: str) -> bool:
        """
        Validate the (unofficial) NPWP check digit using a weighted mod-11 sum.

        Treated as a soft/bonus signal only; the official algorithm is not
        published by DJP.
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
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 30)
        context = text[start:end].lower()
        return any(kw in context for kw in self.NPWP_KEYWORDS)


def format_npwp(npwp: str) -> str:
    """Format NPWP to standard display format: XX.XXX.XXX.X-XXX.XXX"""
    digits = "".join(c for c in npwp if c.isdigit())

    if len(digits) == 15:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}.{digits[8]}-{digits[9:12]}.{digits[12:15]}"
    elif len(digits) == 16:
        return digits  # New format doesn't have standard formatting yet

    return npwp  # Return as-is if can't format
