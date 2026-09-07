"""
KK (Kartu Keluarga) Recognizer.

Indonesian Family Card Number - 16 digits with embedded information:
- Digits 1-2: Province code
- Digits 3-4: City/Regency code
- Digits 5-6: District code
- Digits 7-12: Registration date (DDMMYY)
- Digits 13-16: Sequence number

Note: Similar to NIK but without birth date encoding (uses registration date).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import ClassVar

from sandiraksa.detection.context import DetectionResult
from sandiraksa.detection.engine import BaseRecognizer
from sandiraksa.detection.recognizers.id_nik import NIKRecognizer


class KKRecognizer(BaseRecognizer):
    """Recognizer for Indonesian KK (Family Card Number)."""

    # Pattern: 16 consecutive digits, possibly with spaces/dashes
    PATTERN: ClassVar[re.Pattern] = re.compile(
        r"\b(\d{2})[\s.-]?(\d{2})[\s.-]?(\d{2})[\s.-]?(\d{6})[\s.-]?(\d{4})\b"
        r"|"
        r"\b(\d{16})\b"
    )

    def __init__(self) -> None:
        super().__init__("kk", ["ID_KK"])

    def analyze(
        self,
        text: str,
        entities: list[str],
    ) -> list[DetectionResult]:
        """Analyze text for KK numbers."""
        if "ID_KK" not in entities:
            return []

        results: list[DetectionResult] = []

        for match in self.PATTERN.finditer(text):
            # Extract the full KK number
            if match.group(6):  # 16-digit format
                kk = match.group(6)
            else:  # Formatted with separators
                kk = "".join(g for g in match.groups()[:5] if g)

            if len(kk) != 16:
                continue

            # Check context to determine if it's KK or NIK
            score = self._validate_kk(kk, text, match)

            if score > 0:
                results.append(
                    DetectionResult(
                        entity_type="ID_KK",
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        score=score,
                        recognizer_name="kk",
                        analysis_explanation={
                            "province": kk[:2],
                            "city": kk[2:4],
                            "district": kk[4:6],
                            "registration_date_encoded": kk[6:12],
                            "sequence": kk[12:16],
                        },
                    )
                )

        return results

    def _validate_kk(self, kk: str, text: str, match: re.Match) -> float:
        """
        Validate KK number and return confidence score.

        KK vs NIK differentiation:
        - KK has registration date in positions 7-12 (no female +40 encoding)
        - Context keywords help distinguish
        """
        if len(kk) != 16 or not kk.isdigit():
            return 0.0

        # Check province code (same as NIK)
        province = kk[:2]
        if province not in NIKRecognizer.VALID_PROVINCES:
            return 0.0

        score = 0.4  # Base score (lower than NIK due to ambiguity)

        # Check context for KK keywords
        if self._looks_like_kk_context(text, match):
            score += 0.3

        # Validate registration date
        date_score = self._validate_registration_date(kk[6:12])
        if date_score > 0:
            score += date_score * 0.2
        else:
            score -= 0.1

        # KK typically has day <= 31 (no +40 encoding like NIK)
        day = int(kk[6:8])
        if day > 31:
            score -= 0.2  # More likely NIK

        return max(0, min(score, 0.95))

    def _validate_registration_date(self, encoded: str) -> float:
        """Validate the registration date portion (DDMMYY)."""
        try:
            day = int(encoded[:2])
            month = int(encoded[2:4])
            year = int(encoded[4:6])

            if day < 1 or day > 31:
                return 0.0
            if month < 1 or month > 12:
                return 0.0

            # Registration dates are typically in the past
            full_year = 1900 + year if year > 50 else 2000 + year

            try:
                reg_date = datetime(full_year, month, day)
                # Should be in the past
                if reg_date <= datetime.now():
                    return 1.0
                return 0.5
            except ValueError:
                return 0.3

        except (ValueError, IndexError):
            return 0.0

    def _looks_like_kk_context(self, text: str, match: re.Match) -> bool:
        """Check if surrounding context suggests KK."""
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 30)
        context = text[start:end].lower()

        kk_keywords = [
            "kartu keluarga",
            "no. kk",
            "no kk",
            "nomor kk",
            "kk:",
            "family card",
            "kepala keluarga",
        ]

        return any(kw in context for kw in kk_keywords)
