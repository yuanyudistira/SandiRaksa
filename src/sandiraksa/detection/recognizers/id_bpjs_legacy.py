"""
BPJS Recognizer — legacy engine variant.

The existing ``id_bpjs.BPJSRecognizer`` targets the *unified* detection stack
(``BaseUnifiedRecognizer`` / ``LogicalSegment`` / ``UnifiedFinding``) which is
not wired into production. As a result BPJS numbers were never detected by the
UI or any protector.

This module provides a BPJS recognizer built on the *legacy* contract
(``BaseRecognizer`` + ``analyze(text, entities) -> list[DetectionResult]``) so
it can be registered in ``DetectionEngine`` and used everywhere the other
Indonesian recognizers (NIK, NPWP, KK, Phone) are.

BPJS numbers are 13-digit identifiers with no public checksum, so detection is
gated on nearby context keywords to avoid flagging arbitrary 13-digit numbers.
"""

from __future__ import annotations

import re
from typing import ClassVar

from sandiraksa.detection.context import DetectionResult
from sandiraksa.detection.engine import BaseRecognizer

# Ported from id_bpjs.BPJS_CONTEXT_KEYWORDS so both stacks stay consistent.
BPJS_CONTEXT_KEYWORDS: list[str] = [
    "bpjs",
    "bpjs kesehatan",
    "bpjs ketenagakerjaan",
    "no bpjs",
    "no. bpjs",
    "nomor bpjs",
    "kartu bpjs",
    "peserta bpjs",
    "jkn",  # Jaminan Kesehatan Nasional
    "jaminan kesehatan",
    "jaminan sosial",
]


class BPJSRecognizerLegacy(BaseRecognizer):
    """Legacy-contract recognizer for Indonesian BPJS numbers (13 digits)."""

    # Plain 13-digit run.
    PATTERN: ClassVar[re.Pattern] = re.compile(r"\b(\d{13})\b")

    # Grouped form: 4-4-5 with optional space/dot/dash separators, e.g.
    # "0001 2345 67890" or "000 555 666 777 8" style groupings.
    PATTERN_FORMATTED: ClassVar[re.Pattern] = re.compile(
        r"\b(\d{4})[\s.\-]?(\d{4})[\s.\-]?(\d{5})\b"
    )

    def __init__(self) -> None:
        super().__init__("bpjs", ["ID_BPJS"])

    def analyze(
        self,
        text: str,
        entities: list[str],
    ) -> list[DetectionResult]:
        """Analyze text for BPJS numbers."""
        if "ID_BPJS" not in entities:
            return []
        if not text:
            return []

        results: list[DetectionResult] = []
        found_positions: set[tuple[int, int]] = set()

        # Grouped form first (more specific span), then plain 13-digit.
        for pattern in (self.PATTERN_FORMATTED, self.PATTERN):
            for match in pattern.finditer(text):
                pos = (match.start(), match.end())
                if pos in found_positions:
                    continue

                digits = "".join(match.groups())
                if len(digits) != 13 or not digits.isdigit():
                    continue

                # BPJS has no public checksum -> require context to avoid
                # flagging arbitrary 13-digit numbers.
                if not self._has_context(text, match):
                    continue

                score = self._score_bpjs(digits)
                if score <= 0:
                    continue

                found_positions.add(pos)
                results.append(
                    DetectionResult(
                        entity_type="ID_BPJS",
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        score=score,
                        recognizer_name="bpjs",
                        analysis_explanation={
                            "digits": digits,
                            "starts_with_zero": digits.startswith("0"),
                        },
                    )
                )

        return results

    def _score_bpjs(self, digits: str) -> float:
        """
        Score a 13-digit BPJS candidate (context already confirmed).

        - base 0.5 (context present)
        - +0.25 strong context weight
        - +0.1 if it starts with 0 (common BPJS pattern)
        - reject repdigit (all same) or a pure 0..9 sequential run
        """
        if len(set(digits)) == 1:
            return 0.0
        if digits == "".join(str(i % 10) for i in range(13)):
            return 0.0

        score = 0.5 + 0.25
        if digits.startswith("0"):
            score += 0.1
        return min(score, 1.0)

    def _has_context(self, text: str, match: re.Match) -> bool:
        """Check for a BPJS keyword in the window around the match."""
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 30)
        context = text[start:end].lower()
        return any(kw in context for kw in BPJS_CONTEXT_KEYWORDS)


def format_bpjs(digits: str) -> str:
    """Format a 13-digit BPJS number as XXXX-XXXX-XXXXX."""
    digits = "".join(c for c in digits if c.isdigit())
    if len(digits) != 13:
        return digits
    return f"{digits[:4]}-{digits[4:8]}-{digits[8:]}"


__all__ = [
    "BPJS_CONTEXT_KEYWORDS",
    "BPJSRecognizerLegacy",
    "format_bpjs",
]
