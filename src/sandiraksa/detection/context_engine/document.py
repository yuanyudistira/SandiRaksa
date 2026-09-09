"""
Document-Level Context for PII Detection.

This module provides document type detection and classification
to inform detection strategy. Different document types have
different PII patterns and sensitivities:

- HR documents: Employee data, payroll, contracts
- Medical records: Patient info, diagnoses, prescriptions
- Banking/Financial: Account info, transactions
- Legal: Contracts, agreements, litigation
- Customer data: CRM exports, customer lists
- General: Unknown or mixed content
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sandiraksa.documents.logical_segment import LogicalSegment


class DocumentType(str, Enum):
    """Classification of document types."""

    # High sensitivity
    HR = "hr"                    # Human Resources documents
    MEDICAL = "medical"          # Medical/healthcare records
    FINANCIAL = "financial"      # Banking, financial records
    LEGAL = "legal"              # Legal documents, contracts

    # Medium sensitivity
    CUSTOMER = "customer"        # Customer data, CRM
    EMPLOYEE = "employee"        # Employee lists (non-HR)
    PAYROLL = "payroll"          # Salary, compensation
    INSURANCE = "insurance"      # Insurance documents

    # Lower sensitivity
    INVOICE = "invoice"          # Invoices, billing
    CORPORATE = "corporate"      # Corporate presentations
    MARKETING = "marketing"      # Marketing materials

    # Default
    GENERAL = "general"          # Unknown or general content


# =============================================================================
# Document Type Detection Keywords
# =============================================================================

# Keywords that suggest specific document types
DOCUMENT_TYPE_KEYWORDS: dict[DocumentType, dict[str, float]] = {
    DocumentType.HR: {
        # Indonesian
        "karyawan": 0.3,
        "pegawai": 0.3,
        "data karyawan": 0.5,
        "daftar karyawan": 0.5,
        "sdm": 0.4,
        "sumber daya manusia": 0.5,
        "hrd": 0.5,
        "human resources": 0.5,
        "rekrutmen": 0.4,
        "recruitment": 0.4,
        "cv": 0.3,
        "curriculum vitae": 0.4,
        "resume": 0.4,
        "lamaran": 0.4,
        "pelamar": 0.4,
        "kandidat": 0.4,
        # English
        "employee data": 0.5,
        "staff list": 0.5,
        "personnel": 0.4,
        "workforce": 0.3,
        "headcount": 0.4,
        "onboarding": 0.4,
        "offboarding": 0.4,
    },
    DocumentType.MEDICAL: {
        # Indonesian
        "pasien": 0.5,
        "data pasien": 0.6,
        "rekam medis": 0.6,
        "medical record": 0.6,
        "rm": 0.3,
        "no. rm": 0.5,
        "diagnosa": 0.5,
        "diagnosis": 0.5,
        "resep": 0.4,
        "prescription": 0.4,
        "rawat inap": 0.5,
        "rawat jalan": 0.5,
        "poliklinik": 0.5,
        "rumah sakit": 0.5,
        "rs": 0.3,
        "klinik": 0.4,
        "dokter": 0.3,
        "perawat": 0.3,
        "bpjs kesehatan": 0.5,
        # English
        "patient": 0.5,
        "patient data": 0.6,
        "medical": 0.4,
        "hospital": 0.4,
        "clinic": 0.4,
        "healthcare": 0.4,
        "treatment": 0.3,
        "medication": 0.4,
        "lab result": 0.5,
    },
    DocumentType.FINANCIAL: {
        # Indonesian
        "rekening": 0.4,
        "nomor rekening": 0.5,
        "bank": 0.3,
        "perbankan": 0.4,
        "mutasi": 0.4,
        "saldo": 0.4,
        "transfer": 0.3,
        "transaksi": 0.3,
        "kredit": 0.3,
        "debit": 0.3,
        "kartu kredit": 0.5,
        "pinjaman": 0.4,
        "loan": 0.4,
        "investasi": 0.3,
        "investment": 0.3,
        # English
        "account number": 0.5,
        "bank account": 0.5,
        "banking": 0.4,
        "financial": 0.3,
        "credit card": 0.5,
        "statement": 0.3,
        "balance": 0.3,
        "transaction": 0.3,
    },
    DocumentType.LEGAL: {
        # Indonesian
        "perjanjian": 0.5,
        "kontrak": 0.5,
        "contract": 0.5,
        "agreement": 0.5,
        "hukum": 0.4,
        "legal": 0.4,
        "pengadilan": 0.5,
        "court": 0.5,
        "gugatan": 0.5,
        "litigation": 0.5,
        "kuasa hukum": 0.5,
        "notaris": 0.5,
        "notary": 0.5,
        "akta": 0.4,
        "deed": 0.4,
        "surat kuasa": 0.5,
        "power of attorney": 0.5,
        # English
        "legal document": 0.5,
        "attorney": 0.4,
        "plaintiff": 0.5,
        "defendant": 0.5,
        "confidential": 0.3,
    },
    DocumentType.CUSTOMER: {
        # Indonesian
        "pelanggan": 0.4,
        "nasabah": 0.4,
        "customer": 0.4,
        "client": 0.4,
        "data pelanggan": 0.5,
        "daftar pelanggan": 0.5,
        "customer list": 0.5,
        "crm": 0.5,
        "member": 0.3,
        "membership": 0.4,
        "subscriber": 0.4,
        "pengguna": 0.3,
        "user": 0.3,
        # English
        "customer data": 0.5,
        "client list": 0.5,
        "contact list": 0.4,
        "mailing list": 0.4,
    },
    DocumentType.PAYROLL: {
        # Indonesian
        "gaji": 0.5,
        "salary": 0.5,
        "payroll": 0.6,
        "slip gaji": 0.6,
        "tunjangan": 0.5,
        "allowance": 0.4,
        "bonus": 0.4,
        "kompensasi": 0.5,
        "compensation": 0.5,
        "pph 21": 0.5,
        "pajak penghasilan": 0.5,
        "income tax": 0.4,
        "bpjs ketenagakerjaan": 0.5,
        "jamsostek": 0.5,
        # English
        "payslip": 0.6,
        "wage": 0.4,
        "remuneration": 0.5,
    },
    DocumentType.INSURANCE: {
        # Indonesian
        "asuransi": 0.5,
        "insurance": 0.5,
        "polis": 0.5,
        "policy": 0.4,
        "premi": 0.5,
        "premium": 0.4,
        "klaim": 0.4,
        "claim": 0.4,
        "tertanggung": 0.5,
        "insured": 0.5,
        "penerima manfaat": 0.5,
        "beneficiary": 0.5,
        "underwriting": 0.5,
        # English
        "insurance policy": 0.6,
        "coverage": 0.4,
    },
    DocumentType.INVOICE: {
        # Indonesian
        "invoice": 0.5,
        "faktur": 0.5,
        "tagihan": 0.4,
        "billing": 0.4,
        "pembayaran": 0.3,
        "payment": 0.3,
        "po": 0.3,
        "purchase order": 0.4,
        "quotation": 0.4,
        "penawaran": 0.4,
        "kwitansi": 0.4,
        "receipt": 0.4,
        # English
        "bill": 0.3,
        "order": 0.2,
    },
    DocumentType.CORPORATE: {
        # Indonesian
        "presentasi": 0.3,
        "presentation": 0.3,
        "perusahaan": 0.2,
        "company": 0.2,
        "corporate": 0.3,
        "pt": 0.2,
        "cv": 0.2,
        "manajemen": 0.3,
        "management": 0.3,
        "strategi": 0.3,
        "strategy": 0.3,
        "annual report": 0.4,
        "laporan tahunan": 0.4,
        # English
        "board": 0.3,
        "shareholders": 0.4,
        "stakeholder": 0.3,
    },
}


# =============================================================================
# Sensitivity Levels
# =============================================================================

DOCUMENT_SENSITIVITY: dict[DocumentType, str] = {
    DocumentType.HR: "high",
    DocumentType.MEDICAL: "critical",
    DocumentType.FINANCIAL: "high",
    DocumentType.LEGAL: "high",
    DocumentType.CUSTOMER: "high",
    DocumentType.EMPLOYEE: "medium",
    DocumentType.PAYROLL: "high",
    DocumentType.INSURANCE: "high",
    DocumentType.INVOICE: "low",
    DocumentType.CORPORATE: "medium",
    DocumentType.MARKETING: "low",
    DocumentType.GENERAL: "medium",
}


# Expected entity types by document type
EXPECTED_ENTITIES: dict[DocumentType, set[str]] = {
    DocumentType.HR: {
        "PERSON", "ID_NIK", "ID_NPWP", "ID_KK", "EMAIL_ADDRESS",
        "ID_PHONE", "LOCATION", "DATE_TIME",
    },
    DocumentType.MEDICAL: {
        "PERSON", "ID_NIK", "ID_BPJS", "ID_PHONE", "DATE_TIME",
        "LOCATION", "EMAIL_ADDRESS",
    },
    DocumentType.FINANCIAL: {
        "PERSON", "ID_NIK", "ID_NPWP", "CREDIT_CARD", "IBAN_CODE",
        "ID_PHONE", "EMAIL_ADDRESS",
    },
    DocumentType.LEGAL: {
        "PERSON", "ID_NIK", "ID_NPWP", "LOCATION", "DATE_TIME",
        "EMAIL_ADDRESS", "ID_PHONE",
    },
    DocumentType.CUSTOMER: {
        "PERSON", "EMAIL_ADDRESS", "ID_PHONE", "LOCATION",
        "ID_NIK", "DATE_TIME",
    },
    DocumentType.PAYROLL: {
        "PERSON", "ID_NIK", "ID_NPWP", "ID_BPJS", "IBAN_CODE",
        "EMAIL_ADDRESS",
    },
    DocumentType.INSURANCE: {
        "PERSON", "ID_NIK", "ID_KK", "ID_BPJS", "DATE_TIME",
        "ID_PHONE", "EMAIL_ADDRESS",
    },
    DocumentType.GENERAL: set(),  # No specific expectation
}


@dataclass
class DocumentTypeScore:
    """Score for a document type match."""

    document_type: DocumentType
    score: float
    matched_keywords: list[str] = field(default_factory=list)


@dataclass
class DocumentContext:
    """
    Document-level context analysis result.

    Attributes:
        detected_type: Most likely document type
        type_scores: Scores for all detected types
        sensitivity: Sensitivity level (critical/high/medium/low)
        expected_entities: Entity types expected in this document
        confidence: Confidence in type detection
        hints: Additional document hints
    """

    detected_type: DocumentType = DocumentType.GENERAL
    type_scores: list[DocumentTypeScore] = field(default_factory=list)
    sensitivity: str = "medium"
    expected_entities: set[str] = field(default_factory=set)
    confidence: float = 0.0
    hints: dict[str, str] = field(default_factory=dict)

    def is_high_sensitivity(self) -> bool:
        """Check if document is high or critical sensitivity."""
        return self.sensitivity in ("high", "critical")

    def expects_entity(self, entity_type: str) -> bool:
        """Check if an entity type is expected in this document."""
        if not self.expected_entities:
            return True  # No specific expectation = allow all
        return entity_type in self.expected_entities


class DocumentContextDetector:
    """
    Detects document type from content and metadata.

    Analyzes sheet names, headings, titles, and content
    to classify the document type.
    """

    def __init__(
        self,
        keywords: dict[DocumentType, dict[str, float]] | None = None,
    ):
        """
        Initialize detector.

        Args:
            keywords: Override default document type keywords
        """
        self.keywords = keywords or DOCUMENT_TYPE_KEYWORDS

        # Build regex patterns
        self._patterns = {}
        for doc_type, kw_dict in self.keywords.items():
            sorted_kw = sorted(kw_dict.keys(), key=len, reverse=True)
            escaped = [re.escape(kw) for kw in sorted_kw]
            pattern = r"\b(" + "|".join(escaped) + r")\b"
            self._patterns[doc_type] = re.compile(pattern, re.IGNORECASE)

    def detect(
        self,
        texts: list[str],
        file_name: str | None = None,
        sheet_names: list[str] | None = None,
    ) -> DocumentContext:
        """
        Detect document type from provided texts.

        Args:
            texts: Text samples from the document
            file_name: Optional file name for hints
            sheet_names: Optional Excel sheet names

        Returns:
            DocumentContext with detected type and scores
        """
        result = DocumentContext()

        # Combine all text sources
        combined_texts = list(texts)
        if file_name:
            combined_texts.append(file_name)
        if sheet_names:
            combined_texts.extend(sheet_names)

        combined = " ".join(combined_texts)

        # Score each document type
        for doc_type, pattern in self._patterns.items():
            matches = list(pattern.finditer(combined))
            if matches:
                matched_keywords = [m.group(1).lower() for m in matches]
                # Calculate score (sum of keyword weights, capped)
                score = sum(
                    self.keywords[doc_type].get(kw, 0.0)
                    for kw in matched_keywords
                )
                score = min(score, 1.0)

                result.type_scores.append(
                    DocumentTypeScore(
                        document_type=doc_type,
                        score=score,
                        matched_keywords=matched_keywords,
                    )
                )

        # Sort by score
        result.type_scores.sort(key=lambda x: x.score, reverse=True)

        # Set detected type
        if result.type_scores:
            best = result.type_scores[0]
            if best.score >= 0.3:  # Minimum threshold
                result.detected_type = best.document_type
                result.confidence = best.score
            else:
                result.detected_type = DocumentType.GENERAL
                result.confidence = 0.0
        else:
            result.detected_type = DocumentType.GENERAL
            result.confidence = 0.0

        # Set sensitivity and expected entities
        result.sensitivity = DOCUMENT_SENSITIVITY.get(
            result.detected_type, "medium"
        )
        result.expected_entities = EXPECTED_ENTITIES.get(
            result.detected_type, set()
        )

        # Add hints from file name
        if file_name:
            result.hints["file_name"] = file_name

        return result

    def detect_from_segment(
        self,
        segment: "LogicalSegment",
    ) -> DocumentContext:
        """
        Detect document type from a LogicalSegment.

        Args:
            segment: LogicalSegment with document metadata

        Returns:
            DocumentContext result
        """
        texts = [segment.text]

        # Add context labels
        texts.extend(segment.context_labels)

        # Add table headers
        if segment.table_headers:
            texts.extend(segment.table_headers)

        # Add heading
        heading = getattr(segment, "heading", None)
        if heading:
            texts.append(heading)

        # Get sheet name from location
        sheet_name = None
        if segment.location and segment.location.sheet:
            sheet_name = segment.location.sheet

        return self.detect(
            texts=texts,
            file_name=segment.file_id,
            sheet_names=[sheet_name] if sheet_name else None,
        )


# =============================================================================
# Module-level functions
# =============================================================================

_default_detector: DocumentContextDetector | None = None


def get_document_detector() -> DocumentContextDetector:
    """Get the default document context detector."""
    global _default_detector
    if _default_detector is None:
        _default_detector = DocumentContextDetector()
    return _default_detector


def detect_document_type(
    texts: list[str],
    file_name: str | None = None,
    sheet_names: list[str] | None = None,
) -> DocumentContext:
    """
    Convenience function to detect document type.

    Args:
        texts: Text samples from the document
        file_name: Optional file name
        sheet_names: Optional sheet names

    Returns:
        DocumentContext result
    """
    return get_document_detector().detect(texts, file_name, sheet_names)


def get_sensitivity(document_type: DocumentType) -> str:
    """Get sensitivity level for a document type."""
    return DOCUMENT_SENSITIVITY.get(document_type, "medium")


def get_expected_entities(document_type: DocumentType) -> set[str]:
    """Get expected entity types for a document type."""
    return EXPECTED_ENTITIES.get(document_type, set())


__all__ = [
    "DocumentType",
    "DOCUMENT_TYPE_KEYWORDS",
    "DOCUMENT_SENSITIVITY",
    "EXPECTED_ENTITIES",
    "DocumentTypeScore",
    "DocumentContext",
    "DocumentContextDetector",
    "get_document_detector",
    "detect_document_type",
    "get_sensitivity",
    "get_expected_entities",
]
