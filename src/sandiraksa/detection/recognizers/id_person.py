"""
Indonesian Person Name Recognizer - Context-Aware.

The English spaCy model used by Presidio misses many Indonesian names
(e.g. "Fajar Nugraha", "Bima Hartono") and mislabels place names as persons.

This recognizer complements the NLP model by using structural context that is
reliable in Indonesian documents:

    1. Label-based: a name that follows a name label.
       "Nama: Budi Santoso"  /  "Nama Pasien : Siti Aminah"

    2. EMR/record pattern: a name right after a record ID token, before a
       delimiter. Example from real EMR exports:
       "[EMR-MOCK-0001006] Fajar Nugraha | Laki-laki | ..."

These matches get a high confidence because the structural context is strong.
The generic NLP PERSON detections still run in parallel; overlap resolution
merges duplicates downstream.
"""

from __future__ import annotations

import re
from typing import ClassVar

from sandiraksa.detection.context import DetectionResult
from sandiraksa.detection.engine import BaseRecognizer


# Name labels (lowercased, matched case-insensitively)
_NAME_LABELS: tuple[str, ...] = (
    "nama lengkap",
    "nama pasien",
    "nama karyawan",
    "nama pelanggan",
    "nama mock",
    "nama",
    "name",
    "full name",
    "patient name",
)


# JSON keys whose value is a person name (lowercased).
_JSON_NAME_KEYS: tuple[str, ...] = (
    "name",
    "nama",
    "full_name",
    "fullname",
    "patient",
    "patient_name",
    "pasien",
    "nama_pasien",
    "doctor",
    "dokter",
    "nama_dokter",
    "employee",
    "karyawan",
    "customer",
    "pelanggan",
)


# Cue words in free text that are commonly followed by a name WITHOUT a ':'.
# e.g. "Pasien Budi", "Cek lab Siti Aminah", "kontak darurat Joko".
_FREE_TEXT_CUES: tuple[str, ...] = (
    "pasien",
    "dokter",
    "perawat",
    "cek lab",
    "atas nama",
    "kontak darurat",
    "penanggung jawab",
    "pengirim",
    "penerima",
)


# A plausible Indonesian name: 1-4 capitalized words.
# Each word starts uppercase, followed by lowercase letters. Allows names like
# "Yudistira", "Siti Aminah", "Fajar Nugraha", "Rangga Adi Nugroho".
# Word separator is horizontal whitespace only ([^\S\n]) so a name never spans
# multiple lines / table rows.
_NAME_CORE = r"[A-Z][a-z]+(?:[^\S\n]+[A-Z][a-z]+){0,3}"

# Name core allowing an optional honorific/title prefix ("dr. Andi Kurniawan",
# "Ibu Siti"). Used for JSON values like "doctor": "dr. Andi Kurniawan".
_TITLE = r"(?:dr|drg|dra|ir|prof|h|hj|tn|ny|sdr|sdri|bpk|bapak|ibu)\.?\s*"
_NAME_CORE_TITLED = r"(?:" + _TITLE + r")?" + _NAME_CORE


class IndonesianPersonRecognizer(BaseRecognizer):
    """Context-aware recognizer for Indonesian person names."""

    # "Nama: Budi Santoso"  (label followed by separator then the name)
    # Sort labels longest-first so "nama mock" matches before "nama".
    _PAT_LABELED: ClassVar[re.Pattern] = re.compile(
        r"(?P<label>"
        + "|".join(re.escape(l) for l in sorted(_NAME_LABELS, key=len, reverse=True))
        + r")"
        r"\s*[:=]\s*"
        r"(?P<name>" + _NAME_CORE + r")",
        re.IGNORECASE,
    )

    # "[EMR-MOCK-0001006] Fajar Nugraha |"  (record id, name, delimiter)
    _PAT_EMR: ClassVar[re.Pattern] = re.compile(
        r"\]\s*(?P<name>" + _NAME_CORE + r")\s*[|\n]"
    )

    # JSON key/value:  "name": "Budi Sanjaya"  /  "doctor": "dr. Andi Kurniawan"
    # The KEY match is case-insensitive (inline (?i:...)), but the NAME core is
    # case-SENSITIVE so it only captures Capitalized words (not lowercase text).
    _PAT_JSON: ClassVar[re.Pattern] = re.compile(
        r"[\"'](?i:"
        + "|".join(re.escape(k) for k in sorted(_JSON_NAME_KEYS, key=len, reverse=True))
        + r")[\"']\s*:\s*[\"'](?P<name>" + _NAME_CORE_TITLED + r")[\"']"
    )

    # Free-text cue followed by a name, no ':' required.
    # "Pasien Budi S", "Cek lab Siti Aminah", "kontak darurat Joko Widodo"
    # Cue is case-insensitive; name core stays case-sensitive.
    _PAT_CUE: ClassVar[re.Pattern] = re.compile(
        r"\b(?i:"
        + "|".join(re.escape(c) for c in sorted(_FREE_TEXT_CUES, key=len, reverse=True))
        + r")\s+(?P<name>" + _NAME_CORE + r")"
    )

    def __init__(self) -> None:
        super().__init__("id_person", ["PERSON"])

    def analyze(
        self,
        text: str,
        entities: list[str],
    ) -> list[DetectionResult]:
        """Analyze text for Indonesian person names via context."""
        if "PERSON" not in entities:
            return []

        results: list[DetectionResult] = []
        seen: set[tuple[int, int]] = set()

        # 1. Label-based names (highest confidence)
        for m in self._PAT_LABELED.finditer(text):
            span = (m.start("name"), m.end("name"))
            if span in seen:
                continue
            seen.add(span)
            results.append(
                DetectionResult(
                    entity_type="PERSON",
                    start=span[0],
                    end=span[1],
                    text=m.group("name"),
                    score=0.9,
                    recognizer_name="id_person",
                    analysis_explanation={"context": "name_label"},
                )
            )

        # 2. EMR / record-pattern names
        for m in self._PAT_EMR.finditer(text):
            span = (m.start("name"), m.end("name"))
            if span in seen:
                continue
            seen.add(span)
            results.append(
                DetectionResult(
                    entity_type="PERSON",
                    start=span[0],
                    end=span[1],
                    text=m.group("name"),
                    score=0.85,
                    recognizer_name="id_person",
                    analysis_explanation={"context": "emr_record"},
                )
            )

        # 3. JSON key/value names (high confidence: explicit key)
        for m in self._PAT_JSON.finditer(text):
            span = (m.start("name"), m.end("name"))
            if span in seen:
                continue
            seen.add(span)
            results.append(
                DetectionResult(
                    entity_type="PERSON",
                    start=span[0],
                    end=span[1],
                    text=m.group("name"),
                    score=0.9,
                    recognizer_name="id_person",
                    analysis_explanation={"context": "json_key"},
                )
            )

        # 4. Free-text cue followed by a name (medium confidence)
        for m in self._PAT_CUE.finditer(text):
            span = (m.start("name"), m.end("name"))
            if span in seen:
                continue
            seen.add(span)
            results.append(
                DetectionResult(
                    entity_type="PERSON",
                    start=span[0],
                    end=span[1],
                    text=m.group("name"),
                    score=0.8,
                    recognizer_name="id_person",
                    analysis_explanation={"context": "free_text_cue"},
                )
            )

        return results
