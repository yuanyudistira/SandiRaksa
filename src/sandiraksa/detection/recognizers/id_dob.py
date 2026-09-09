"""
Date of Birth (Tanggal Lahir) Recognizer - Context-Aware.

Detects birth dates using context signals rather than tagging every date.

Key principles:
    - A raw date is NOT automatically a birth date.
    - Requires supporting context to be considered a birth date:
        1. A nearby birth-date label ("Lahir", "TTL", "Tgl Lahir", "DOB", etc.), OR
        2. A person name detected in the same segment.
    - Excludes dates that fall in the CURRENT month/year (more likely an
      appointment/visit date than a birth date).
    - Validates the year is plausible for a birth date (1920..today, not future).

Supported date formats (Indonesian + common):
    - 14-Feb-1988, 03-Nov-1976   (DD-Mon-YYYY)
    - 14/02/1988, 14-02-1988     (DD/MM/YYYY, DD-MM-YYYY)
    - 14 Februari 1988           (DD Bulan YYYY)
    - 1988-02-14                 (ISO YYYY-MM-DD)
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import ClassVar

from sandiraksa.detection.context import DetectionResult
from sandiraksa.detection.engine import BaseRecognizer


# Minimum plausible birth year (people older than ~105 are extremely rare)
MIN_BIRTH_YEAR = 1920


# Month name lookups (English + Indonesian, abbreviated + full)
_MONTHS: dict[str, int] = {
    # English abbreviated
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    # English full
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
    # Indonesian full
    "januari": 1, "februari": 2, "maret": 3, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "oktober": 10, "desember": 12,
    # Indonesian abbreviated (that differ)
    "agu": 8, "okt": 10, "des": 12, "peb": 2,
}


# Labels that strongly indicate a birth date is nearby
_DOB_LABELS: tuple[str, ...] = (
    "tanggal lahir",
    "tgl lahir",
    "tgl. lahir",
    "tanggal. lahir",
    "tempat/tanggal lahir",
    "ttl",
    "lahir",
    "date of birth",
    "d.o.b",
    "dob",
    "born",
    "birth date",
    "birthdate",
)


class DateOfBirthRecognizer(BaseRecognizer):
    """
    Context-aware recognizer for birth dates (DATE_OF_BIRTH).

    Rather than tagging every date, this recognizer only reports dates that
    have supporting context indicating they are birth dates.
    """

    # DD-Mon-YYYY / DD Mon YYYY (e.g. 14-Feb-1988, 14 Februari 1988)
    _PAT_DMY_NAME: ClassVar[re.Pattern] = re.compile(
        r"\b(\d{1,2})[\s\-/]+"
        r"([A-Za-z]{3,9})[\s\-/]+"
        r"(\d{4})\b"
    )

    # DD/MM/YYYY or DD-MM-YYYY (numeric)
    _PAT_DMY_NUM: ClassVar[re.Pattern] = re.compile(
        r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b"
    )

    # ISO YYYY-MM-DD
    _PAT_ISO: ClassVar[re.Pattern] = re.compile(
        r"\b(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})\b"
    )

    # Simple person-name heuristic: two capitalized words in a row
    _PERSON_HINT: ClassVar[re.Pattern] = re.compile(
        r"\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b"
    )

    def __init__(self, today: date | None = None) -> None:
        """
        Args:
            today: Reference "current date" (defaults to real today).
                   Injectable for deterministic testing.
        """
        super().__init__("date_of_birth", ["DATE_OF_BIRTH"])
        self._today = today or date.today()

    def analyze(
        self,
        text: str,
        entities: list[str],
    ) -> list[DetectionResult]:
        """Analyze text for birth dates using context."""
        if "DATE_OF_BIRTH" not in entities:
            return []

        # Determine whether the segment has supporting context at all
        text_lower = text.lower()
        has_dob_label = any(label in text_lower for label in _DOB_LABELS)
        has_person = bool(self._PERSON_HINT.search(text))

        # No supporting context at all -> do not treat any date as DOB
        if not has_dob_label and not has_person:
            return []

        results: list[DetectionResult] = []
        seen_spans: set[tuple[int, int]] = set()

        for match, parsed in self._iter_dates(text):
            span = (match.start(), match.end())
            if span in seen_spans:
                continue

            parsed_date = parsed
            if parsed_date is None:
                continue

            # Plausibility: year must be a valid birth year, not in the future
            if not self._is_plausible_birth_year(parsed_date):
                continue

            label_precedes = self._label_precedes(text_lower, match.start())

            # If NO explicit DOB label precedes the date, apply appointment
            # heuristics to avoid tagging visit/appointment dates as DOB:
            if not label_precedes:
                # Recent dates (within ~2 years of today) are much more likely
                # to be appointment/visit dates than birth dates.
                if self._is_recent(parsed_date):
                    continue
                # Current month/year is almost certainly not a birth date.
                if self._is_current_month(parsed_date):
                    continue

            # Compute confidence from context strength
            score = self._score(text_lower, match.start(), has_dob_label, has_person)
            if score <= 0:
                continue

            seen_spans.add(span)
            results.append(
                DetectionResult(
                    entity_type="DATE_OF_BIRTH",
                    start=match.start(),
                    end=match.end(),
                    text=match.group(),
                    score=score,
                    recognizer_name="date_of_birth",
                    analysis_explanation={
                        "parsed_date": parsed_date.isoformat(),
                        "has_dob_label": has_dob_label,
                        "has_person_context": has_person,
                    },
                )
            )

        return results

    # ------------------------------------------------------------------ #
    # Date parsing
    # ------------------------------------------------------------------ #

    def _iter_dates(self, text: str):
        """Yield (match, parsed_date) for all date-like substrings."""
        for m in self._PAT_DMY_NAME.finditer(text):
            yield m, self._parse_dmy_name(m)
        for m in self._PAT_DMY_NUM.finditer(text):
            yield m, self._parse_dmy_num(m)
        for m in self._PAT_ISO.finditer(text):
            yield m, self._parse_iso(m)

    def _parse_dmy_name(self, m: re.Match) -> date | None:
        try:
            day = int(m.group(1))
            month = _MONTHS.get(m.group(2).lower())
            year = int(m.group(3))
            if month is None:
                return None
            return date(year, month, day)
        except (ValueError, TypeError):
            return None

    def _parse_dmy_num(self, m: re.Match) -> date | None:
        try:
            day = int(m.group(1))
            month = int(m.group(2))
            year = int(m.group(3))
            if month < 1 or month > 12 or day < 1 or day > 31:
                return None
            return date(year, month, day)
        except (ValueError, TypeError):
            return None

    def _parse_iso(self, m: re.Match) -> date | None:
        try:
            year = int(m.group(1))
            month = int(m.group(2))
            day = int(m.group(3))
            if month < 1 or month > 12 or day < 1 or day > 31:
                return None
            return date(year, month, day)
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------ #
    # Context / plausibility checks
    # ------------------------------------------------------------------ #

    def _is_plausible_birth_year(self, d: date) -> bool:
        """Year must be between MIN_BIRTH_YEAR and today (no future dates)."""
        if d.year < MIN_BIRTH_YEAR:
            return False
        if d > self._today:
            return False
        return True

    def _is_current_month(self, d: date) -> bool:
        """True if date is in the same month & year as 'today'."""
        return d.year == self._today.year and d.month == self._today.month

    def _is_recent(self, d: date, years: int = 2) -> bool:
        """
        True if the date is within `years` of today.

        Recent dates are far more likely to be appointment/visit dates than
        birth dates, so without an explicit DOB label we treat them as non-DOB.
        """
        try:
            cutoff = date(self._today.year - years, self._today.month, self._today.day)
        except ValueError:
            # Handle Feb 29 edge case
            cutoff = date(self._today.year - years, self._today.month, 28)
        return d >= cutoff

    def _label_precedes(self, text_lower: str, pos: int, window: int = 30) -> bool:
        """
        Check if a DOB label appears shortly before the date position.

        The look-back is confined to the current line (does not cross a
        newline) so labels from adjacent rows/paragraphs don't leak in.
        """
        start = max(0, pos - window)
        preceding = text_lower[start:pos]

        # Confine to current line: only consider text after the last newline
        newline_idx = preceding.rfind("\n")
        if newline_idx != -1:
            preceding = preceding[newline_idx + 1:]

        return any(label in preceding for label in _DOB_LABELS)

    def _score(
        self,
        text_lower: str,
        pos: int,
        has_dob_label: bool,
        has_person: bool,
    ) -> float:
        """
        Compute confidence based on context strength.

        - Explicit DOB label right before the date -> high confidence.
        - DOB label somewhere in segment -> medium-high.
        - Only a person name present -> medium.
        """
        if self._label_precedes(text_lower, pos):
            return 0.95
        if has_dob_label:
            return 0.85
        if has_person:
            return 0.65
        return 0.0
