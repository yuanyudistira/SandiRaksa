"""
Context-based segment classifier.

For structured documents (DOCX tables, PPTX tables, XLSX, CSV), the strongest
signal for what a value represents is its column header or key label, not the
value text itself.

Example (DOCX table):
    table_headers = ['EMR ID', 'Nama Mock', 'Jenis Kelamin', 'Tanggal Lahir', ...]
    segment.text = 'Aisyah Pratama', column_index = 1
        -> header[1] = 'Nama Mock' -> PERSON

    segment.text = '14-Feb-1988', column_index = 3
        -> header[3] = 'Tanggal Lahir' -> DATE_OF_BIRTH

This classifier maps a label (column header or key label) to an entity type,
so that values in labeled columns/fields are detected even when the value text
alone carries no context.
"""

from __future__ import annotations

import re

from sandiraksa.detection.context import DetectionResult


# Map normalized label keywords -> entity type.
# Order matters: more specific labels should be checked first.
_LABEL_TO_ENTITY: list[tuple[tuple[str, ...], str]] = [
    # Birth date (check before generic name/date)
    (("tanggal lahir", "tgl lahir", "tgl. lahir", "date of birth", "dob",
      "birth date", "ttl", "lahir"), "DATE_OF_BIRTH"),
    # Person name
    (("nama lengkap", "nama pasien", "nama karyawan", "nama pelanggan",
      "nama mock", "nama", "full name", "patient name", "name"), "PERSON"),
    # NIK
    (("nik", "no ktp", "nomor ktp", "no. ktp"), "ID_NIK"),
    # NPWP
    (("npwp",), "ID_NPWP"),
    # KK
    (("no kk", "nomor kk", "kartu keluarga", "kk"), "ID_KK"),
    # BPJS
    (("bpjs", "no bpjs"), "ID_BPJS"),
    # Email
    (("email", "e-mail", "surel"), "EMAIL_ADDRESS"),
    # Phone
    (("telepon", "telp", "no telp", "no hp", "nomor hp", "handphone",
      "phone", "kontak"), "PHONE_NUMBER"),
    # Address
    (("alamat", "address", "domisili"), "LOCATION"),
]


# Labels that indicate the value is NOT sensitive (skip detection)
_NON_SENSITIVE_LABELS: frozenset[str] = frozenset({
    "jenis kelamin", "gender", "penjamin", "emr id", "encounter",
    "diagnosis", "diagnosa", "icd-10", "icd", "keluhan", "terapi",
    "tanda vital", "spo2", "td", "suhu", "penanggung",
})


def _normalize(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip().lower())


def classify_label(label: str) -> str | None:
    """
    Map a column header or key label to an entity type.

    Args:
        label: Column header or key label text.

    Returns:
        Entity type string, or None if not a sensitive/known label.
    """
    if not label:
        return None

    norm = _normalize(label)

    # Explicit non-sensitive labels
    if norm in _NON_SENSITIVE_LABELS:
        return None

    for keywords, entity_type in _LABEL_TO_ENTITY:
        for kw in keywords:
            # Match whole-word-ish: keyword appears as a token/prefix
            if norm == kw or norm.startswith(kw + " ") or (" " + kw) in (" " + norm):
                return entity_type

    return None


def get_segment_label(segment) -> str | None:
    """
    Determine the governing label for a segment.

    Priority:
        1. key_label (explicit key:value)
        2. table_headers[column_index] (table cell)
        3. nearby_labels (PPTX spatial labels) - pick the first that maps to
           a known entity type.

    Args:
        segment: A LogicalSegment-like object.

    Returns:
        The label string, or None.
    """
    key_label = getattr(segment, "key_label", None)
    if key_label:
        return key_label

    headers = getattr(segment, "table_headers", None)
    col_idx = getattr(segment, "column_index", None)
    if headers and col_idx is not None and 0 <= col_idx < len(headers):
        return headers[col_idx]

    # PPTX spatial labels: choose the nearby label that maps to an entity type
    nearby = getattr(segment, "nearby_labels", None)
    if nearby:
        for lbl in nearby:
            if classify_label(lbl) is not None:
                return lbl

    return None


def classify_segment_by_context(segment) -> DetectionResult | None:
    """
    Produce a DetectionResult for a structured segment based on its label.

    Only used when the segment's value is governed by a column header or key
    label (tables, spreadsheets, key:value pairs). The whole value is treated
    as the detected entity.

    Args:
        segment: A LogicalSegment-like object with .text and context fields.

    Returns:
        DetectionResult spanning the whole value, or None if the label is
        unknown / non-sensitive / value looks empty.
    """
    text = getattr(segment, "text", "") or ""
    if not text.strip():
        return None

    label = get_segment_label(segment)
    if not label:
        return None

    entity_type = classify_label(label)
    if entity_type is None:
        return None

    # For DATE_OF_BIRTH, ensure the value actually looks like a date
    if entity_type == "DATE_OF_BIRTH" and not _looks_like_date(text):
        return None

    return DetectionResult(
        entity_type=entity_type,
        start=0,
        end=len(text),
        text=text.strip(),
        score=0.9,
        recognizer_name="context_classifier",
        analysis_explanation={"label": label, "source": "column_header_or_key"},
    )


_DATE_HINT = re.compile(
    r"\d{1,2}[\s\-/][A-Za-z0-9]{1,9}[\s\-/]\d{2,4}"
    r"|\d{4}[\-/]\d{1,2}[\-/]\d{1,2}"
)


def _looks_like_date(text: str) -> bool:
    """Quick check that a value resembles a date."""
    return bool(_DATE_HINT.search(text.strip()))
