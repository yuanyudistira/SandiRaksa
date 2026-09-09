"""
Lexical Context for PII Detection.

This module provides keyword-based context analysis for improving
PII detection accuracy. Keywords are categorized as:
- Positive: Suggest PII presence (boost confidence)
- Negative: Suggest non-PII (reduce confidence)
- Entity-specific: Map to specific entity types
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sandiraksa.documents.logical_segment import LogicalSegment


class ContextPolarity(str, Enum):
    """Polarity of context evidence."""

    POSITIVE = "positive"  # Suggests PII
    NEGATIVE = "negative"  # Suggests non-PII
    NEUTRAL = "neutral"    # No strong signal


# =============================================================================
# Indonesian & English Positive Keywords
# =============================================================================

# Keywords that suggest PII presence
POSITIVE_KEYWORDS: dict[str, float] = {
    # Personal identifiers - Indonesian
    "nama": 0.3,
    "nama lengkap": 0.4,
    "nama pasien": 0.5,
    "nama karyawan": 0.5,
    "nama nasabah": 0.5,
    "nama pelanggan": 0.5,
    "nama pemilik": 0.4,
    "nama penumpang": 0.5,
    "nama tertanggung": 0.5,
    # Personal identifiers - English
    "name": 0.3,
    "full name": 0.4,
    "patient name": 0.5,
    "employee name": 0.5,
    "customer name": 0.5,
    "client name": 0.5,
    "passenger name": 0.5,
    # ID numbers - Indonesian
    "nik": 0.5,
    "no. nik": 0.5,
    "nomor nik": 0.5,
    "nomor induk kependudukan": 0.5,
    "ktp": 0.5,
    "no. ktp": 0.5,
    "kartu tanda penduduk": 0.5,
    "npwp": 0.5,
    "no. npwp": 0.5,
    "nomor pokok wajib pajak": 0.5,
    "kk": 0.4,
    "no. kk": 0.5,
    "kartu keluarga": 0.5,
    "bpjs": 0.5,
    "no. bpjs": 0.5,
    "sim": 0.4,
    "no. sim": 0.5,
    "surat izin mengemudi": 0.5,
    "paspor": 0.5,
    "no. paspor": 0.5,
    "passport": 0.5,
    # ID numbers - English
    "id number": 0.4,
    "national id": 0.5,
    "tax id": 0.5,
    "ssn": 0.5,
    "social security": 0.5,
    # Contact - Indonesian
    "telepon": 0.4,
    "no. telepon": 0.5,
    "nomor telepon": 0.5,
    "hp": 0.4,
    "no. hp": 0.5,
    "handphone": 0.4,
    "whatsapp": 0.4,
    "wa": 0.3,
    # Contact - English
    "phone": 0.4,
    "phone number": 0.5,
    "mobile": 0.4,
    "cell": 0.4,
    "contact": 0.3,
    "contact number": 0.4,
    # Email
    "email": 0.4,
    "e-mail": 0.4,
    "alamat email": 0.5,
    "email address": 0.5,
    # Address - Indonesian
    "alamat": 0.4,
    "alamat lengkap": 0.5,
    "alamat rumah": 0.5,
    "alamat kantor": 0.4,
    "alamat tinggal": 0.5,
    "domisili": 0.4,
    # Address - English
    "address": 0.4,
    "home address": 0.5,
    "mailing address": 0.5,
    "residential address": 0.5,
    # Financial - Indonesian
    "rekening": 0.5,
    "no. rekening": 0.5,
    "nomor rekening": 0.5,
    "kartu kredit": 0.5,
    "no. kartu kredit": 0.5,
    # Financial - English
    "account": 0.3,
    "account number": 0.5,
    "bank account": 0.5,
    "credit card": 0.5,
    "card number": 0.5,
    # Date of Birth
    "tanggal lahir": 0.4,
    "tgl lahir": 0.4,
    "ttl": 0.3,
    "tempat tanggal lahir": 0.4,
    "date of birth": 0.4,
    "dob": 0.4,
    "birth date": 0.4,
    # Medical
    "pasien": 0.4,
    "no. rm": 0.5,
    "nomor rekam medis": 0.5,
    "medical record": 0.5,
    "patient id": 0.5,
    "diagnosa": 0.3,
    "diagnosis": 0.3,
    # Employment
    "karyawan": 0.4,
    "nip": 0.5,
    "nik karyawan": 0.5,
    "employee id": 0.5,
    "staff id": 0.5,
    "gaji": 0.4,
    "salary": 0.4,
    # Context words
    "pribadi": 0.3,
    "rahasia": 0.3,
    "confidential": 0.3,
    "private": 0.3,
    "personal": 0.3,
    "data diri": 0.4,
}


# =============================================================================
# Negative Keywords (suggest non-PII)
# =============================================================================

NEGATIVE_KEYWORDS: dict[str, float] = {
    # Reference numbers
    "invoice": 0.4,
    "invoice number": 0.5,
    "no. invoice": 0.5,
    "faktur": 0.4,
    "no. faktur": 0.5,
    "order": 0.3,
    "order id": 0.5,
    "order number": 0.5,
    "no. order": 0.5,
    "po number": 0.5,
    "purchase order": 0.4,
    # Product identifiers
    "sku": 0.5,
    "kode barang": 0.4,
    "kode produk": 0.4,
    "product code": 0.5,
    "item code": 0.5,
    "serial number": 0.5,
    "serial no": 0.5,
    "no. seri": 0.5,
    "barcode": 0.5,
    # Document references
    "reference": 0.4,
    "reference number": 0.5,
    "ref": 0.3,
    "ref no": 0.4,
    "no. ref": 0.4,
    "document number": 0.4,
    "no. dokumen": 0.4,
    "file number": 0.4,
    "case number": 0.4,
    "ticket": 0.4,
    "ticket number": 0.5,
    # Transaction
    "transaction": 0.4,
    "transaction id": 0.5,
    "transaksi": 0.4,
    "no. transaksi": 0.5,
    "receipt": 0.4,
    "receipt number": 0.5,
    # Version/batch
    "version": 0.4,
    "versi": 0.4,
    "batch": 0.4,
    "batch number": 0.5,
    "lot": 0.4,
    "lot number": 0.5,
    # Business entities (not personal)
    "pt": 0.3,
    "cv": 0.3,
    "perusahaan": 0.3,
    "company": 0.3,
    "vendor": 0.3,
    "supplier": 0.3,
    # Technical
    "id": 0.2,  # Low weight - ambiguous
    "code": 0.2,
    "kode": 0.2,
    "nomor urut": 0.4,
    "sequence": 0.4,
    "index": 0.4,
}


# =============================================================================
# Entity-Specific Keywords
# =============================================================================

# Keywords that strongly suggest specific entity types
ENTITY_KEYWORDS: dict[str, dict[str, float]] = {
    "ID_NIK": {
        "nik": 0.5,
        "nomor induk kependudukan": 0.5,
        "ktp": 0.4,
        "kartu tanda penduduk": 0.5,
    },
    "ID_NPWP": {
        "npwp": 0.5,
        "nomor pokok wajib pajak": 0.5,
        "tax id": 0.4,
        "pajak": 0.3,
    },
    "ID_KK": {
        "kk": 0.4,
        "kartu keluarga": 0.5,
        "no. kk": 0.5,
    },
    "ID_BPJS": {
        "bpjs": 0.5,
        "bpjs kesehatan": 0.5,
        "bpjs ketenagakerjaan": 0.5,
        "jkn": 0.4,
    },
    "ID_SIM": {
        "sim": 0.4,
        "surat izin mengemudi": 0.5,
        "sim a": 0.5,
        "sim b": 0.5,
        "sim c": 0.5,
        "driving license": 0.4,
    },
    "ID_PASSPORT": {
        "passport": 0.5,
        "paspor": 0.5,
        "no. paspor": 0.5,
        "travel document": 0.4,
    },
    "ID_PHONE": {
        "telepon": 0.4,
        "no. telepon": 0.5,
        "hp": 0.4,
        "handphone": 0.4,
        "whatsapp": 0.4,
        "phone": 0.4,
        "mobile": 0.4,
    },
    "PERSON": {
        "nama": 0.3,
        "nama lengkap": 0.4,
        "name": 0.3,
        "full name": 0.4,
    },
    "EMAIL_ADDRESS": {
        "email": 0.5,
        "e-mail": 0.5,
        "alamat email": 0.5,
    },
    "LOCATION": {
        "alamat": 0.4,
        "address": 0.4,
        "domisili": 0.4,
    },
    "DATE_TIME": {
        "tanggal lahir": 0.4,
        "tgl lahir": 0.4,
        "date of birth": 0.4,
        "dob": 0.4,
    },
    "CREDIT_CARD": {
        "kartu kredit": 0.5,
        "credit card": 0.5,
        "card number": 0.4,
    },
    "IBAN_CODE": {
        "rekening": 0.4,
        "account number": 0.4,
        "bank account": 0.4,
    },
}


@dataclass
class LexicalMatch:
    """A matched keyword in text."""

    keyword: str
    weight: float
    polarity: ContextPolarity
    position: int  # Character position
    entity_hint: str | None = None  # Suggested entity type


@dataclass
class LexicalContext:
    """
    Lexical context analysis result for a segment.

    Attributes:
        positive_matches: Keywords suggesting PII
        negative_matches: Keywords suggesting non-PII
        entity_hints: Specific entity type hints
        net_score: Aggregated context score (positive - negative)
    """

    positive_matches: list[LexicalMatch] = field(default_factory=list)
    negative_matches: list[LexicalMatch] = field(default_factory=list)
    entity_hints: dict[str, float] = field(default_factory=dict)
    net_score: float = 0.0

    def has_positive_context(self) -> bool:
        """Check if positive context exists."""
        return len(self.positive_matches) > 0

    def has_negative_context(self) -> bool:
        """Check if negative context exists."""
        return len(self.negative_matches) > 0

    def get_strongest_entity_hint(self) -> tuple[str, float] | None:
        """Get the entity type with highest hint score."""
        if not self.entity_hints:
            return None
        entity = max(self.entity_hints, key=self.entity_hints.get)
        return (entity, self.entity_hints[entity])


class LexicalContextAnalyzer:
    """
    Analyzes text for lexical context clues.

    Scans text and labels for keywords that suggest or negate
    PII presence, providing evidence for confidence scoring.
    """

    def __init__(
        self,
        positive_keywords: dict[str, float] | None = None,
        negative_keywords: dict[str, float] | None = None,
        entity_keywords: dict[str, dict[str, float]] | None = None,
    ):
        """
        Initialize analyzer with keyword dictionaries.

        Args:
            positive_keywords: Override default positive keywords
            negative_keywords: Override default negative keywords
            entity_keywords: Override default entity-specific keywords
        """
        self.positive_keywords = positive_keywords or POSITIVE_KEYWORDS
        self.negative_keywords = negative_keywords or NEGATIVE_KEYWORDS
        self.entity_keywords = entity_keywords or ENTITY_KEYWORDS

        # Build regex patterns for efficient matching
        self._positive_pattern = self._build_pattern(self.positive_keywords)
        self._negative_pattern = self._build_pattern(self.negative_keywords)
        self._entity_patterns = {
            entity: self._build_pattern(keywords)
            for entity, keywords in self.entity_keywords.items()
        }

    def _build_pattern(self, keywords: dict[str, float]) -> re.Pattern[str]:
        """Build regex pattern from keyword dict."""
        # Sort by length (longest first) to match longer phrases first
        sorted_keywords = sorted(keywords.keys(), key=len, reverse=True)
        # Escape special regex characters and join with OR
        escaped = [re.escape(kw) for kw in sorted_keywords]
        pattern = r"\b(" + "|".join(escaped) + r")\b"
        return re.compile(pattern, re.IGNORECASE)

    def analyze(self, segment: "LogicalSegment") -> LexicalContext:
        """
        Analyze segment for lexical context.

        Args:
            segment: LogicalSegment to analyze

        Returns:
            LexicalContext with matches and scores
        """
        result = LexicalContext()

        # Combine text sources for analysis
        texts_to_analyze = [segment.text]

        # Add key label if present
        if segment.key_label:
            texts_to_analyze.append(segment.key_label)

        # Add context labels
        texts_to_analyze.extend(segment.context_labels)

        # Add table headers
        if segment.table_headers:
            texts_to_analyze.extend(segment.table_headers)

        combined_text = " ".join(texts_to_analyze)

        # Find positive matches
        for match in self._positive_pattern.finditer(combined_text):
            keyword = match.group(1).lower()
            weight = self.positive_keywords.get(keyword, 0.0)
            result.positive_matches.append(
                LexicalMatch(
                    keyword=keyword,
                    weight=weight,
                    polarity=ContextPolarity.POSITIVE,
                    position=match.start(),
                )
            )

        # Find negative matches
        for match in self._negative_pattern.finditer(combined_text):
            keyword = match.group(1).lower()
            weight = self.negative_keywords.get(keyword, 0.0)
            result.negative_matches.append(
                LexicalMatch(
                    keyword=keyword,
                    weight=weight,
                    polarity=ContextPolarity.NEGATIVE,
                    position=match.start(),
                )
            )

        # Find entity-specific hints
        for entity_type, pattern in self._entity_patterns.items():
            for match in pattern.finditer(combined_text):
                keyword = match.group(1).lower()
                weight = self.entity_keywords[entity_type].get(keyword, 0.0)
                if entity_type not in result.entity_hints:
                    result.entity_hints[entity_type] = 0.0
                result.entity_hints[entity_type] = max(
                    result.entity_hints[entity_type],
                    weight,
                )

        # Calculate net score
        positive_score = sum(m.weight for m in result.positive_matches)
        negative_score = sum(m.weight for m in result.negative_matches)
        result.net_score = positive_score - negative_score

        return result

    def analyze_text(self, text: str) -> LexicalContext:
        """
        Analyze plain text for lexical context.

        Args:
            text: Text string to analyze

        Returns:
            LexicalContext with matches and scores
        """
        # Create a minimal segment-like object
        from sandiraksa.documents.logical_segment import LogicalSegment

        segment = LogicalSegment.for_txt_paragraph(
            text=text,
            file_id="temp",
            paragraph_index=0,
        )
        return self.analyze(segment)


# Module-level analyzer instance for convenience
_default_analyzer: LexicalContextAnalyzer | None = None


def get_lexical_analyzer() -> LexicalContextAnalyzer:
    """Get the default lexical analyzer instance."""
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = LexicalContextAnalyzer()
    return _default_analyzer


def analyze_lexical_context(segment: "LogicalSegment") -> LexicalContext:
    """
    Convenience function to analyze segment lexical context.

    Args:
        segment: LogicalSegment to analyze

    Returns:
        LexicalContext result
    """
    return get_lexical_analyzer().analyze(segment)


__all__ = [
    "ContextPolarity",
    "POSITIVE_KEYWORDS",
    "NEGATIVE_KEYWORDS",
    "ENTITY_KEYWORDS",
    "LexicalMatch",
    "LexicalContext",
    "LexicalContextAnalyzer",
    "get_lexical_analyzer",
    "analyze_lexical_context",
]
