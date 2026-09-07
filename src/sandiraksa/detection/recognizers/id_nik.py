"""
NIK (Nomor Induk Kependudukan) Recognizer.

Indonesian National ID Number - 16 digits with embedded information:
- Digits 1-2: Province code
- Digits 3-4: City/Regency code  
- Digits 5-6: District code
- Digits 7-12: Birth date (DDMMYY, female adds 40 to DD)
- Digits 13-16: Sequence number
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import ClassVar

from sandiraksa.detection.context import DetectionResult
from sandiraksa.detection.engine import BaseRecognizer


class NIKRecognizer(BaseRecognizer):
    """Recognizer for Indonesian NIK (National ID Number)."""

    # Pattern: 16 consecutive digits, possibly with spaces/dashes
    PATTERN: ClassVar[re.Pattern] = re.compile(
        r"\b(\d{2})[\s.-]?(\d{2})[\s.-]?(\d{2})[\s.-]?(\d{6})[\s.-]?(\d{4})\b"
        r"|"
        r"\b(\d{16})\b"
    )

    # Valid province codes (Indonesia)
    VALID_PROVINCES: ClassVar[set[str]] = {
        "11",  # Aceh
        "12",  # Sumatera Utara
        "13",  # Sumatera Barat
        "14",  # Riau
        "15",  # Jambi
        "16",  # Sumatera Selatan
        "17",  # Bengkulu
        "18",  # Lampung
        "19",  # Kepulauan Bangka Belitung
        "21",  # Kepulauan Riau
        "31",  # DKI Jakarta
        "32",  # Jawa Barat
        "33",  # Jawa Tengah
        "34",  # DI Yogyakarta
        "35",  # Jawa Timur
        "36",  # Banten
        "51",  # Bali
        "52",  # Nusa Tenggara Barat
        "53",  # Nusa Tenggara Timur
        "61",  # Kalimantan Barat
        "62",  # Kalimantan Tengah
        "63",  # Kalimantan Selatan
        "64",  # Kalimantan Timur
        "65",  # Kalimantan Utara
        "71",  # Sulawesi Utara
        "72",  # Sulawesi Tengah
        "73",  # Sulawesi Selatan
        "74",  # Sulawesi Tenggara
        "75",  # Gorontalo
        "76",  # Sulawesi Barat
        "81",  # Maluku
        "82",  # Maluku Utara
        "91",  # Papua Barat
        "92",  # Papua (was 94)
        "93",  # Papua Selatan
        "94",  # Papua Tengah
        "95",  # Papua Pegunungan
        "96",  # Papua Barat Daya
    }

    def __init__(self) -> None:
        super().__init__("nik", ["ID_NIK"])

    def analyze(
        self,
        text: str,
        entities: list[str],
    ) -> list[DetectionResult]:
        """Analyze text for NIK numbers."""
        if "ID_NIK" not in entities:
            return []

        results: list[DetectionResult] = []

        for match in self.PATTERN.finditer(text):
            # Extract the full NIK (handle both formats)
            if match.group(6):  # 16-digit format
                nik = match.group(6)
            else:  # Formatted with separators
                nik = "".join(match.groups()[:5])

            # Validate the NIK
            score = self._validate_nik(nik)
            if score > 0:
                results.append(
                    DetectionResult(
                        entity_type="ID_NIK",
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        score=score,
                        recognizer_name="nik",
                        analysis_explanation={
                            "province": nik[:2],
                            "city": nik[2:4],
                            "district": nik[4:6],
                            "birthdate_encoded": nik[6:12],
                            "sequence": nik[12:16],
                        },
                    )
                )

        return results

    def _validate_nik(self, nik: str) -> float:
        """
        Validate NIK and return confidence score.

        Returns:
            Score between 0.0 and 1.0, or 0.0 if invalid.
        """
        if len(nik) != 16 or not nik.isdigit():
            return 0.0

        score = 0.5  # Base score for 16-digit number

        # Check province code
        province = nik[:2]
        if province in self.VALID_PROVINCES:
            score += 0.2
        else:
            # Invalid province, likely not a NIK
            return 0.0

        # Validate birth date encoding
        birth_score = self._validate_birthdate(nik[6:12])
        if birth_score > 0:
            score += birth_score * 0.3
        else:
            score -= 0.2  # Penalty for invalid date

        return min(score, 1.0)

    def _validate_birthdate(self, encoded: str) -> float:
        """
        Validate the birthdate portion of NIK.

        Format: DDMMYY where DD for female is day + 40
        """
        try:
            day = int(encoded[:2])
            month = int(encoded[2:4])
            year = int(encoded[4:6])

            # Adjust for female encoding
            if day > 40:
                day -= 40

            # Basic validation
            if day < 1 or day > 31:
                return 0.0
            if month < 1 or month > 12:
                return 0.0

            # Try to construct a valid date
            # Assume 1900s for year > 50, 2000s otherwise
            full_year = 1900 + year if year > 50 else 2000 + year

            try:
                datetime(full_year, month, day)
                return 1.0
            except ValueError:
                return 0.5  # Partial match (e.g., Feb 30)

        except (ValueError, IndexError):
            return 0.0


def get_nik_metadata(nik: str) -> dict | None:
    """
    Extract metadata from a NIK number.

    Returns dict with province, city, district, birthdate info,
    or None if invalid.
    """
    if len(nik) != 16 or not nik.isdigit():
        return None

    day = int(nik[6:8])
    is_female = day > 40
    if is_female:
        day -= 40

    month = int(nik[8:10])
    year = int(nik[10:12])
    full_year = 1900 + year if year > 50 else 2000 + year

    return {
        "province_code": nik[:2],
        "city_code": nik[2:4],
        "district_code": nik[4:6],
        "birth_day": day,
        "birth_month": month,
        "birth_year": full_year,
        "is_female": is_female,
        "sequence": nik[12:16],
    }
