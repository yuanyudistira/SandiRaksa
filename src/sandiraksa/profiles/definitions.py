"""
Privacy Profile Definitions.

Predefined entity type configurations for common use cases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProfileId(str, Enum):
    """Profile identifiers."""

    STANDARD = "standard"
    HR = "hr"
    BANKING = "banking"
    HEALTHCARE = "healthcare"
    LEGAL = "legal"


@dataclass
class PrivacyProfile:
    """A privacy profile with entity type configuration."""

    id: str
    name: str
    name_id: str  # Indonesian name
    description: str
    description_id: str  # Indonesian description
    entity_types: list[str]
    high_confidence_types: list[str] = field(default_factory=list)
    custom_patterns: dict[str, str] = field(default_factory=dict)
    min_confidence: float = 0.7

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "name_id": self.name_id,
            "description": self.description,
            "description_id": self.description_id,
            "entity_types": self.entity_types,
            "high_confidence_types": self.high_confidence_types,
            "min_confidence": self.min_confidence,
        }


# Standard PII Profile
STANDARD_PROFILE = PrivacyProfile(
    id=ProfileId.STANDARD.value,
    name="Standard PII",
    name_id="PII Standar",
    description="Common personal information: names, emails, phones, addresses",
    description_id="Informasi pribadi umum: nama, email, telepon, alamat",
    entity_types=[
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "ID_PHONE",
        "LOCATION",
        "ADDRESS",
        "DATE_TIME",
        "ID_NIK",
        "ID_NPWP",
        "ID_KK",
        "URL",
        "IP_ADDRESS",
    ],
    high_confidence_types=[
        "EMAIL_ADDRESS",
        "ID_NIK",
        "ID_NPWP",
    ],
    min_confidence=0.7,
)

# HR & Recruitment Profile
HR_PROFILE = PrivacyProfile(
    id=ProfileId.HR.value,
    name="HR & Recruitment",
    name_id="HR & Rekrutmen",
    description="Employee data, CVs, salaries, performance reviews",
    description_id="Data karyawan, CV, gaji, penilaian kinerja",
    entity_types=[
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "ID_PHONE",
        "LOCATION",
        "ADDRESS",
        "DATE_TIME",
        "ID_NIK",
        "ID_NPWP",
        "ID_KK",
        "ORGANIZATION",
        "NRP",  # Nomor Registrasi Pegawai
        "DATE_OF_BIRTH",
        "AGE",
        "SALARY",
    ],
    high_confidence_types=[
        "ID_NIK",
        "ID_NPWP",
        "SALARY",
        "DATE_OF_BIRTH",
    ],
    min_confidence=0.6,
)

# Banking & Finance Profile
BANKING_PROFILE = PrivacyProfile(
    id=ProfileId.BANKING.value,
    name="Banking & Finance",
    name_id="Perbankan & Keuangan",
    description="Account numbers, credit cards, transactions",
    description_id="Nomor rekening, kartu kredit, transaksi",
    entity_types=[
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "ID_PHONE",
        "ADDRESS",
        "ID_NIK",
        "ID_NPWP",
        "CREDIT_CARD",
        "IBAN_CODE",
        "BANK_ACCOUNT",
        "SWIFT_CODE",
        "FINANCIAL_AMOUNT",
    ],
    high_confidence_types=[
        "CREDIT_CARD",
        "IBAN_CODE",
        "BANK_ACCOUNT",
        "ID_NIK",
    ],
    min_confidence=0.8,
)

# Healthcare Profile
HEALTHCARE_PROFILE = PrivacyProfile(
    id=ProfileId.HEALTHCARE.value,
    name="Healthcare",
    name_id="Kesehatan",
    description="Medical records, patient data, diagnoses",
    description_id="Rekam medis, data pasien, diagnosis",
    entity_types=[
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "ID_PHONE",
        "ADDRESS",
        "DATE_TIME",
        "ID_NIK",
        "ID_KK",
        "DATE_OF_BIRTH",
        "AGE",
        "MEDICAL_LICENSE",
        "MEDICAL_RECORD_NUMBER",
        "HEALTH_INSURANCE_ID",
        "BPJS_NUMBER",
    ],
    high_confidence_types=[
        "ID_NIK",
        "MEDICAL_RECORD_NUMBER",
        "BPJS_NUMBER",
    ],
    min_confidence=0.7,
)

# Legal & M&A Profile
LEGAL_PROFILE = PrivacyProfile(
    id=ProfileId.LEGAL.value,
    name="Legal & M&A",
    name_id="Hukum & M&A",
    description="Contracts, agreements, due diligence documents",
    description_id="Kontrak, perjanjian, dokumen due diligence",
    entity_types=[
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "ADDRESS",
        "ID_NIK",
        "ID_NPWP",
        "ORGANIZATION",
        "DATE_TIME",
        "FINANCIAL_AMOUNT",
        "BANK_ACCOUNT",
        "LEGAL_CASE_NUMBER",
        "CONTRACT_NUMBER",
    ],
    high_confidence_types=[
        "ID_NIK",
        "ID_NPWP",
        "LEGAL_CASE_NUMBER",
    ],
    min_confidence=0.7,
)

# Profile registry
_PROFILES: dict[str, PrivacyProfile] = {
    ProfileId.STANDARD.value: STANDARD_PROFILE,
    ProfileId.HR.value: HR_PROFILE,
    ProfileId.BANKING.value: BANKING_PROFILE,
    ProfileId.HEALTHCARE.value: HEALTHCARE_PROFILE,
    ProfileId.LEGAL.value: LEGAL_PROFILE,
}


def get_profile(profile_id: str) -> PrivacyProfile | None:
    """
    Get a profile by ID.

    Args:
        profile_id: Profile identifier.

    Returns:
        PrivacyProfile or None if not found.
    """
    return _PROFILES.get(profile_id)


def get_all_profiles() -> list[PrivacyProfile]:
    """Get all available profiles."""
    return list(_PROFILES.values())


def get_profile_names() -> dict[str, str]:
    """Get profile ID to name mapping."""
    return {p.id: p.name for p in _PROFILES.values()}
