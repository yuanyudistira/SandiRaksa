"""
Person Name False-Positive Filter.

NLP-based PERSON detection (Presidio/spaCy with an English model) frequently
mislabels common Indonesian words as person names because they are capitalized
or unfamiliar to the model. Examples seen in real documents:

    "Perempuan", "Laki-laki", "Penjamin", "Kunjungan", "Keluhan",
    "Terapi", "Diagnosis", "Demam", "Tanda", "EMR", "NIK Mock"

This module provides a filter that removes such false positives from PERSON
detections while preserving genuine names.

Strategy:
    1. Reject if the detected text (normalized) is in a stop-word list of common
       Indonesian document terms (labels, medical terms, form fields).
    2. Reject if EVERY token in the detection is a stop word.
    3. Reject obvious non-name artifacts (contains digits, punctuation like '|',
       label fragments, or is a single very short token).
"""

from __future__ import annotations

import re


# Common Indonesian document terms that get misdetected as PERSON.
# Stored lowercase for case-insensitive matching.
COMMON_NON_NAME_TERMS: frozenset[str] = frozenset({
    # Gender / demographics
    "perempuan", "laki-laki", "laki laki", "pria", "wanita",
    "jenis kelamin", "gender", "usia", "umur",
    # Form / record labels
    "penjamin", "kunjungan", "keluhan", "terapi", "diagnosis", "diagnosa",
    "tanda", "tanda vital", "emr", "nik", "nik mock", "npwp", "kk",
    "no ktp", "nomor", "alamat", "alamat mock", "kontak", "email",
    "telepon", "telp", "hp", "penanggung", "pasien", "karyawan",
    "nama", "nama mock", "nama pasien", "nama lengkap",
    "tempat lahir", "tanggal lahir", "tgl lahir", "lahir",
    "encounter", "provinsi", "kota", "kabupaten", "kecamatan", "kelurahan",
    "pekerjaan", "jabatan", "departemen", "divisi", "unit",
    # Medical terms
    "demam", "batuk", "pilek", "nyeri", "sesak", "mual", "muntah",
    "hipertensi", "diabetes", "dispepsia", "asma", "dermatitis",
    "ispa", "kontrol", "gula darah", "tekanan darah", "suhu", "ruam",
    "rawat inap", "rawat jalan", "poli", "poliklinik", "igd", "ugd",
    "resep", "obat", "dosis", "rujukan", "anamnesis", "vital",
    "kulit", "gatal", "napas", "darah", "ulu", "hati", "punggung",
    "kepala", "perut", "dada", "kaki", "tangan", "mata", "telinga",
    # Insurance / admin
    "bpjs", "bpjs kesehatan", "asuransi", "asuransi swasta",
    "asuransi perusahaan", "corporate guarantee", "pribadi", "mandiri",
    # Document classification
    "sangat rahasia", "rahasia", "mockup", "klasifikasi", "peringatan",
    "confidential", "internal", "public",
    # Date/time words
    "januari", "februari", "maret", "april", "mei", "juni", "juli",
    "agustus", "september", "oktober", "november", "desember",
    "senin", "selasa", "rabu", "kamis", "jumat", "sabtu", "minggu",
    # Common status words
    "aktif", "nonaktif", "tidak", "spesifik", "esensial", "fungsional",
    "ringan", "sedang", "berat", "normal", "abnormal",
    # Conjunctions / stopwords
    "dan", "atau", "dengan", "yang", "untuk", "dari", "pada", "di", "ke",
    # Generic document words
    "catatan", "bukan", "data", "identitas", "medis", "file", "ini",
    "sintetis", "nyata", "semua", "contoh", "dokumen", "simulasi",
    "informasi", "keperluan", "demo", "pengujian",
})


# Tokens that, if present, strongly indicate this is NOT a person name.
_LABEL_FRAGMENTS: frozenset[str] = frozenset({
    "mock", "emr", "nik", "npwp", "id", "no", "nomor",
})


# Strong clinical / action / document terms. If ANY of these appears in a
# candidate PERSON phrase, it is not a name (NLP over-extends into clauses like
# "Demam Berdarah", "alergi penisilin", "Jangan berikan amoxicillin").
_STRONG_NON_NAME_TERMS: frozenset[str] = frozenset({
    # Diseases / symptoms / clinical
    "demam", "berdarah", "batuk", "pilek", "nyeri", "sesak", "mual", "muntah",
    "hipertensi", "diabetes", "dispepsia", "asma", "dermatitis", "ispa",
    "alergi", "penisilin", "amoxicillin", "amoksisilin", "paracetamol",
    "metformin", "amlodipine", "obat", "resep", "dosis", "diagnosis",
    "diagnosa", "gula", "darah", "ruam", "gatal", "endoskopi", "terapi",
    "penicillin", "antibiotik", "infeksi", "radang", "tumor", "kanker",
    # Action / imperative words NLP glues on
    "jangan", "berikan", "menunjukkan", "mengeluh", "kontrol", "isolasi",
    "rujukan", "rawat", "periksa", "cek",
    # Generic
    "penjamin", "asuransi", "mandiri", "inhealth",
})


# A detection containing any of these characters is not a clean person name.
_INVALID_CHARS: re.Pattern = re.compile(r"[0-9|:=/\\@#\[\](){}<>]")

# Address / place indicator tokens. A capitalized phrase containing these is
# almost certainly a place name, not a person.
_PLACE_TOKENS: frozenset[str] = frozenset({
    "no", "no.", "jl", "jl.", "jalan", "gang", "gg", "blok", "rt", "rw",
    "kecamatan", "kelurahan", "desa", "kota", "kabupaten", "kab",
    "baru", "lama", "timur", "barat", "utara", "selatan", "tengah",
    "raya", "dalam", "atas", "bawah",
})


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace."""
    return re.sub(r"\s+", " ", text.strip().lower())


def is_false_positive_person(text: str) -> bool:
    """
    Determine whether a PERSON detection is likely a false positive.

    Args:
        text: The detected text.

    Returns:
        True if the text should be rejected (not a real person name).
    """
    if not text or not text.strip():
        return True

    # A real name never spans multiple lines
    if "\n" in text or "\r" in text:
        return True

    normalized = _normalize(text)

    # 1. Exact match against common non-name terms OR the global deny-list.
    if normalized in COMMON_NON_NAME_TERMS:
        return True
    try:
        from sandiraksa.detection.deny_list import is_denied

        if is_denied(normalized):
            return True
    except Exception:
        pass

    # 2. Contains invalid characters (digits, separators, brackets)
    if _INVALID_CHARS.search(text):
        return True

    # 3. Tokenize and analyze
    tokens = [t for t in re.split(r"[\s\-]+", normalized) if t]
    if not tokens:
        return True

    # 3-place. Contains an address/place indicator token -> treat as place
    if any(tok in _PLACE_TOKENS for tok in tokens):
        return True

    # 3-long. Names rarely exceed 4 tokens; long phrases are usually clauses
    #         (e.g. "Ruam kulit dan gatal", "Kontrol tekanan darah")
    if len(tokens) > 4:
        return True

    # 3a. Single very short token (e.g. "id", "no") -> not a name
    if len(tokens) == 1 and len(tokens[0]) <= 2:
        return True

    # 3b. Every token is a common non-name term
    if all(tok in COMMON_NON_NAME_TERMS for tok in tokens):
        return True

    # 3b-strong. ANY token is a strong clinical/medical/action term -> reject.
    #            Real names never contain these; NLP glues them on
    #            (e.g. "Demam Berdarah", "Rina M alergi penisilin",
    #             "Jangan berikan amoxicillin").
    if any(tok in _STRONG_NON_NAME_TERMS for tok in tokens):
        return True

    # 3c. Contains a label fragment AND a non-name term
    #     (e.g. "NIK Mock" -> "nik" + "mock")
    has_label_fragment = any(tok in _LABEL_FRAGMENTS for tok in tokens)
    if has_label_fragment:
        # If the remaining tokens are also non-names, reject
        remaining = [t for t in tokens if t not in _LABEL_FRAGMENTS]
        if not remaining or all(
            t in COMMON_NON_NAME_TERMS or t in _LABEL_FRAGMENTS for t in tokens
        ):
            return True

    return False


# Labels that indicate the following text is an address/place, not a person.
_ADDRESS_LABELS: tuple[str, ...] = (
    "alamat", "address", "domisili", "jl.", "jalan", "kota", "kecamatan",
    "kelurahan",
)


def _preceded_by_address_label(full_text: str, start: int, window: int = 40) -> bool:
    """Check if the detection at `start` is shortly preceded by an address label."""
    if not full_text or start <= 0:
        return False
    preceding = full_text[max(0, start - window):start].lower()
    return any(label in preceding for label in _ADDRESS_LABELS)


# Leading words that NLP often glues onto a name (labels/verbs) but which are
# not part of the name itself.
_LEADING_NOISE_TOKENS: frozenset[str] = frozenset({
    "pasien", "dokter", "dr", "nama", "cek", "lab", "kontrol", "penjamin",
    "pengirim", "penerima", "kepada", "dari", "pic", "an", "atas", "kepada",
    "perawat", "bapak", "bpk", "ibu", "sdr", "sdri", "tn", "ny",
})


def trim_person_span(text: str, start: int, end: int) -> tuple[str, int, int] | None:
    """
    Trim label/noise tokens from the edges of an NLP-detected PERSON span.

    NLP (English spaCy) frequently over-extends a name to include a leading
    label ("Pasien Budi S") or a trailing common word ("Joko W kontak"). This
    strips such tokens from both ends using the known non-name term sets and
    returns (clean_text, new_start, new_end), or None if nothing name-like
    remains.

    Offsets are relative to the same base as the input start/end.
    """
    raw = text[start:end] if 0 <= start < end <= len(text) else text
    # Tokenize keeping track of offsets within `raw`.
    tokens: list[tuple[str, int, int]] = []
    for m in re.finditer(r"\S+", raw):
        tokens.append((m.group(), m.start(), m.end()))
    if not tokens:
        return None

    def _is_noise(tok: str) -> bool:
        t = tok.strip(".,;:|()[]").lower()
        if not t:
            return True
        return (
            t in _LEADING_NOISE_TOKENS
            or t in COMMON_NON_NAME_TERMS
            or t in _LABEL_FRAGMENTS
            or t in _PLACE_TOKENS
        )

    lo, hi = 0, len(tokens)
    # Strip leading noise tokens.
    while lo < hi and _is_noise(tokens[lo][0]):
        lo += 1
    # Strip trailing noise tokens.
    while hi > lo and _is_noise(tokens[hi - 1][0]):
        hi -= 1
    if lo >= hi:
        return None

    new_start = start + tokens[lo][1]
    new_end = start + tokens[hi - 1][2]
    clean = text[new_start:new_end]

    # Final sanity: must still look like a name (not a rejected phrase).
    if is_false_positive_person(clean):
        return None
    return clean, new_start, new_end


def filter_person_detections(detections: list, full_text: str = "") -> list:
    """
    Filter out false-positive PERSON detections from a list of DetectionResult.

    Non-PERSON detections are passed through unchanged.

    Args:
        detections: List of DetectionResult objects.
        full_text: The full segment text, used for context checks (address labels).

    Returns:
        Filtered list with false-positive PERSON detections removed.
    """
    filtered = []
    for d in detections:
        entity_type = getattr(d, "entity_type", None)
        if entity_type == "PERSON":
            text = getattr(d, "text", "")
            if is_false_positive_person(text):
                continue

            # Context check: a "PERSON" that immediately follows an address
            # label is almost certainly a place name (e.g. "Kebon Jeruk").
            # Only apply to NLP detections, not context recognizers which
            # already encode strong structural context.
            recognizer = getattr(d, "recognizer_name", "")
            if recognizer != "id_person" and full_text:
                start = getattr(d, "start", 0)
                if _preceded_by_address_label(full_text, start):
                    continue

        filtered.append(d)
    return filtered
