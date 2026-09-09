"""
Benchmark Corpus Generator.

Generates annotated test data for accuracy measurement.
Each corpus entry contains text with marked PII positions.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal

from tests.accuracy.corpus.indonesian_data import (
    INDONESIAN_NAMES,
    INDONESIAN_ADDRESSES,
    COMPANY_NAMES,
    generate_nik,
    generate_npwp,
    generate_phone,
    generate_email,
    generate_bpjs,
    get_random_name,
    get_random_address,
    get_random_company,
)


class DocumentType(str, Enum):
    """Types of documents in the corpus."""

    HR = "hr"
    MEDICAL = "medical"
    BANKING = "banking"
    LEGAL = "legal"
    CUSTOMER = "customer"
    PAYROLL = "payroll"
    INVOICE = "invoice"
    CV = "cv"
    GENERAL = "general"


@dataclass
class Annotation:
    """
    A single PII annotation in the text.

    Attributes:
        start: Start character offset
        end: End character offset
        text: The PII text
        entity_type: Type of PII (NIK, PERSON, etc.)
        is_true_pii: True if this should be detected (False for negatives)
    """

    start: int
    end: int
    text: str
    entity_type: str
    is_true_pii: bool = True

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "entity_type": self.entity_type,
            "is_true_pii": self.is_true_pii,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Annotation":
        return cls(**d)


@dataclass
class CorpusEntry:
    """
    A single entry in the benchmark corpus.

    Attributes:
        id: Unique identifier
        text: The document text
        annotations: List of PII annotations
        document_type: Type of document
        format: File format (txt, csv, etc.)
        description: Human-readable description
        metadata: Additional metadata
    """

    id: str
    text: str
    annotations: list[Annotation] = field(default_factory=list)
    document_type: DocumentType = DocumentType.GENERAL
    format: str = "txt"
    description: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def pii_count(self) -> int:
        """Count of true PII annotations."""
        return sum(1 for a in self.annotations if a.is_true_pii)

    @property
    def negative_count(self) -> int:
        """Count of negative (should not detect) annotations."""
        return sum(1 for a in self.annotations if not a.is_true_pii)

    def get_annotations_by_type(self, entity_type: str) -> list[Annotation]:
        """Get annotations of a specific type."""
        return [a for a in self.annotations if a.entity_type == entity_type]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "annotations": [a.to_dict() for a in self.annotations],
            "document_type": self.document_type.value,
            "format": self.format,
            "description": self.description,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CorpusEntry":
        return cls(
            id=d["id"],
            text=d["text"],
            annotations=[Annotation.from_dict(a) for a in d.get("annotations", [])],
            document_type=DocumentType(d.get("document_type", "general")),
            format=d.get("format", "txt"),
            description=d.get("description", ""),
            metadata=d.get("metadata", {}),
        )


class CorpusGenerator:
    """
    Generator for benchmark corpus entries.

    Creates realistic documents with annotated PII for testing.
    """

    def __init__(self, seed: int | None = None):
        """Initialize generator with optional seed for reproducibility."""
        self._seed = seed
        if seed is not None:
            random.seed(seed)
        self._id_counter = 0

    def _next_id(self, prefix: str = "entry") -> str:
        """Generate next unique ID."""
        self._id_counter += 1
        return f"{prefix}_{self._id_counter:04d}"

    def generate_hr_document(self) -> CorpusEntry:
        """Generate an HR document (employee data)."""
        name = get_random_name()
        nik = generate_nik()
        phone = generate_phone()
        email = generate_email(name.full_name)
        address = get_random_address()

        text = f"""FORM DATA KARYAWAN

Nama Lengkap: {name.display_name}
NIK: {nik}
Alamat: {address}
No. Telepon: {phone}
Email: {email}

Tanggal Bergabung: 15 Januari 2024
Departemen: IT
Jabatan: Software Engineer
"""

        annotations = []

        # Name annotation
        name_start = text.find(name.display_name)
        if name_start >= 0:
            annotations.append(Annotation(
                start=name_start,
                end=name_start + len(name.display_name),
                text=name.display_name,
                entity_type="PERSON",
            ))

        # NIK annotation
        nik_start = text.find(nik)
        if nik_start >= 0:
            annotations.append(Annotation(
                start=nik_start,
                end=nik_start + len(nik),
                text=nik,
                entity_type="ID_NIK",
            ))

        # Phone annotation
        phone_start = text.find(phone)
        if phone_start >= 0:
            annotations.append(Annotation(
                start=phone_start,
                end=phone_start + len(phone),
                text=phone,
                entity_type="ID_PHONE",
            ))

        # Email annotation
        email_start = text.find(email)
        if email_start >= 0:
            annotations.append(Annotation(
                start=email_start,
                end=email_start + len(email),
                text=email,
                entity_type="EMAIL_ADDRESS",
            ))

        return CorpusEntry(
            id=self._next_id("hr"),
            text=text,
            annotations=annotations,
            document_type=DocumentType.HR,
            description="Employee data form",
        )

    def generate_medical_record(self) -> CorpusEntry:
        """Generate a medical record document."""
        patient = get_random_name()
        nik = generate_nik()
        bpjs = generate_bpjs()
        phone = generate_phone()
        doctor = get_random_name()

        text = f"""REKAM MEDIS PASIEN

No. Rekam Medis: RM-2024-001234
Tanggal: 10 September 2026

DATA PASIEN:
Nama Pasien: {patient.display_name}
NIK: {nik}
No. BPJS: {bpjs}
No. HP: {phone}

DIAGNOSIS:
Keluhan: Demam dan batuk
Diagnosis: ISPA (Infeksi Saluran Pernapasan Akut)
Tindakan: Rawat jalan

Dokter Pemeriksa: {doctor.display_name}
"""

        annotations = []

        # Patient name
        patient_start = text.find(patient.display_name)
        if patient_start >= 0:
            annotations.append(Annotation(
                start=patient_start,
                end=patient_start + len(patient.display_name),
                text=patient.display_name,
                entity_type="PERSON",
            ))

        # NIK
        nik_start = text.find(nik)
        if nik_start >= 0:
            annotations.append(Annotation(
                start=nik_start,
                end=nik_start + len(nik),
                text=nik,
                entity_type="ID_NIK",
            ))

        # BPJS
        bpjs_start = text.find(bpjs)
        if bpjs_start >= 0:
            annotations.append(Annotation(
                start=bpjs_start,
                end=bpjs_start + len(bpjs),
                text=bpjs,
                entity_type="ID_BPJS",
            ))

        # Phone
        phone_start = text.find(phone)
        if phone_start >= 0:
            annotations.append(Annotation(
                start=phone_start,
                end=phone_start + len(phone),
                text=phone,
                entity_type="ID_PHONE",
            ))

        # Doctor name
        doctor_start = text.find(doctor.display_name, patient_start + 1)
        if doctor_start >= 0:
            annotations.append(Annotation(
                start=doctor_start,
                end=doctor_start + len(doctor.display_name),
                text=doctor.display_name,
                entity_type="PERSON",
            ))

        return CorpusEntry(
            id=self._next_id("medical"),
            text=text,
            annotations=annotations,
            document_type=DocumentType.MEDICAL,
            description="Patient medical record",
        )

    def generate_banking_document(self) -> CorpusEntry:
        """Generate a banking document."""
        customer = get_random_name()
        nik = generate_nik()
        npwp = generate_npwp(format_type="formatted")
        phone = generate_phone()
        email = generate_email(customer.full_name)

        text = f"""FORMULIR PEMBUKAAN REKENING

Data Nasabah:
Nama: {customer.display_name}
NIK: {nik}
NPWP: {npwp}
Telepon: {phone}
Email: {email}

Jenis Rekening: Tabungan
Mata Uang: IDR
Setoran Awal: Rp 1.000.000

Pernyataan:
Saya menyatakan bahwa data di atas adalah benar.

Tanda Tangan: _______________
"""

        annotations = []

        # Customer name
        name_start = text.find(customer.display_name)
        if name_start >= 0:
            annotations.append(Annotation(
                start=name_start,
                end=name_start + len(customer.display_name),
                text=customer.display_name,
                entity_type="PERSON",
            ))

        # NIK
        nik_start = text.find(nik)
        if nik_start >= 0:
            annotations.append(Annotation(
                start=nik_start,
                end=nik_start + len(nik),
                text=nik,
                entity_type="ID_NIK",
            ))

        # NPWP
        npwp_start = text.find(npwp)
        if npwp_start >= 0:
            annotations.append(Annotation(
                start=npwp_start,
                end=npwp_start + len(npwp),
                text=npwp,
                entity_type="ID_NPWP",
            ))

        # Phone
        phone_start = text.find(phone)
        if phone_start >= 0:
            annotations.append(Annotation(
                start=phone_start,
                end=phone_start + len(phone),
                text=phone,
                entity_type="ID_PHONE",
            ))

        # Email
        email_start = text.find(email)
        if email_start >= 0:
            annotations.append(Annotation(
                start=email_start,
                end=email_start + len(email),
                text=email,
                entity_type="EMAIL_ADDRESS",
            ))

        return CorpusEntry(
            id=self._next_id("banking"),
            text=text,
            annotations=annotations,
            document_type=DocumentType.BANKING,
            description="Bank account opening form",
        )

    def generate_negative_examples(self) -> CorpusEntry:
        """Generate document with negative examples (should NOT be detected as PII)."""
        company1 = get_random_company()
        company2 = get_random_company()
        address = get_random_address()

        text = f"""SURAT PERJANJIAN KERJASAMA

Pada hari ini, Senin tanggal 10 September 2026, telah ditandatangani
perjanjian kerjasama antara:

PIHAK PERTAMA: {company1}
Alamat: {address}

PIHAK KEDUA: {company2}

Nomor Perjanjian: PKS/2024/001234
Nomor Invoice: INV-2024-09-0001
Reference ID: REF123456789012345

Kedua belah pihak sepakat untuk bekerjasama dalam bidang teknologi informasi.
"""

        annotations = []

        # Company names - should NOT be detected as PERSON
        company1_start = text.find(company1)
        if company1_start >= 0:
            annotations.append(Annotation(
                start=company1_start,
                end=company1_start + len(company1),
                text=company1,
                entity_type="ORGANIZATION",
                is_true_pii=False,  # Not PII
            ))

        company2_start = text.find(company2)
        if company2_start >= 0:
            annotations.append(Annotation(
                start=company2_start,
                end=company2_start + len(company2),
                text=company2,
                entity_type="ORGANIZATION",
                is_true_pii=False,  # Not PII
            ))

        # Reference number - should NOT be detected as NIK
        ref_start = text.find("REF123456789012345")
        if ref_start >= 0:
            annotations.append(Annotation(
                start=ref_start,
                end=ref_start + len("REF123456789012345"),
                text="REF123456789012345",
                entity_type="REFERENCE",
                is_true_pii=False,  # Not PII
            ))

        return CorpusEntry(
            id=self._next_id("negative"),
            text=text,
            annotations=annotations,
            document_type=DocumentType.LEGAL,
            description="Legal document with negative examples",
        )

    def generate_payroll_document(self) -> CorpusEntry:
        """Generate a payroll document."""
        employees = [get_random_name() for _ in range(3)]
        niks = [generate_nik() for _ in range(3)]

        lines = ["SLIP GAJI KARYAWAN", "Periode: September 2026", ""]
        annotations = []
        current_pos = len("\n".join(lines[:3])) + 1

        for i, (emp, nik) in enumerate(zip(employees, niks)):
            line = f"Nama: {emp.display_name}, NIK: {nik}, Gaji Pokok: Rp 10.000.000"
            lines.append(line)

            # Calculate positions in full text
            text_so_far = "\n".join(lines)

            # Name annotation
            name_start = text_so_far.rfind(emp.display_name)
            if name_start >= 0:
                annotations.append(Annotation(
                    start=name_start,
                    end=name_start + len(emp.display_name),
                    text=emp.display_name,
                    entity_type="PERSON",
                ))

            # NIK annotation
            nik_start = text_so_far.rfind(nik)
            if nik_start >= 0:
                annotations.append(Annotation(
                    start=nik_start,
                    end=nik_start + len(nik),
                    text=nik,
                    entity_type="ID_NIK",
                ))

        text = "\n".join(lines)

        return CorpusEntry(
            id=self._next_id("payroll"),
            text=text,
            annotations=annotations,
            document_type=DocumentType.PAYROLL,
            description="Payroll slip with multiple employees",
        )

    def generate_customer_list(self) -> CorpusEntry:
        """Generate a customer list (CSV-like format)."""
        header = "No,Nama,NIK,Telepon,Email"
        rows = [header]
        annotations = []

        for i in range(5):
            customer = get_random_name()
            nik = generate_nik()
            phone = generate_phone()
            email = generate_email(customer.full_name)

            row = f"{i+1},{customer.display_name},{nik},{phone},{email}"
            rows.append(row)

        text = "\n".join(rows)

        # Add annotations for all PII in the text
        for i in range(5):
            customer = INDONESIAN_NAMES[i % len(INDONESIAN_NAMES)]
            # Recalculate positions based on text
            pass  # Simplified - in real implementation would track positions

        return CorpusEntry(
            id=self._next_id("customer"),
            text=text,
            annotations=annotations,  # Would be populated in full implementation
            document_type=DocumentType.CUSTOMER,
            format="csv",
            description="Customer list in CSV format",
        )

    def generate_corpus(self, count_per_type: int = 5) -> list[CorpusEntry]:
        """Generate a full corpus with multiple document types."""
        corpus = []

        for _ in range(count_per_type):
            corpus.append(self.generate_hr_document())
            corpus.append(self.generate_medical_record())
            corpus.append(self.generate_banking_document())
            corpus.append(self.generate_negative_examples())
            corpus.append(self.generate_payroll_document())

        return corpus


def save_corpus(corpus: list[CorpusEntry], path: Path) -> None:
    """Save corpus to JSON file."""
    data = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "entry_count": len(corpus),
        "entries": [e.to_dict() for e in corpus],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_corpus(path: Path) -> list[CorpusEntry]:
    """Load corpus from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [CorpusEntry.from_dict(e) for e in data["entries"]]


def generate_full_corpus(
    output_path: Path | None = None,
    seed: int = 42,
    count_per_type: int = 10,
) -> list[CorpusEntry]:
    """
    Generate the full benchmark corpus.

    Args:
        output_path: Optional path to save corpus
        seed: Random seed for reproducibility
        count_per_type: Number of documents per type

    Returns:
        List of CorpusEntry
    """
    generator = CorpusGenerator(seed=seed)
    corpus = generator.generate_corpus(count_per_type=count_per_type)

    if output_path:
        save_corpus(corpus, output_path)

    return corpus


__all__ = [
    "DocumentType",
    "Annotation",
    "CorpusEntry",
    "CorpusGenerator",
    "save_corpus",
    "load_corpus",
    "generate_full_corpus",
]
