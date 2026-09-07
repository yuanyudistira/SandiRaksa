"""
Entity type definitions for PII detection.

Defines all supported entity types with their metadata,
display information, and default configurations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar


class EntityCategory(str, Enum):
    """Categories of entity types."""

    PERSONAL = "personal"  # Names, IDs, etc.
    CONTACT = "contact"  # Email, phone, address
    FINANCIAL = "financial"  # Bank accounts, credit cards
    GOVERNMENT = "government"  # Government IDs (NIK, NPWP, etc.)
    HEALTH = "health"  # Medical information
    LOCATION = "location"  # Addresses, coordinates
    BUSINESS = "business"  # Company names, contracts
    CUSTOM = "custom"  # User-defined


@dataclass(frozen=True)
class EntityType:
    """Definition of an entity type."""

    name: str  # Unique identifier (e.g., "PERSON", "EMAIL")
    display_name: str  # Human-readable name
    display_name_id: str  # Indonesian display name
    category: EntityCategory
    description: str = ""
    description_id: str = ""

    # Detection settings
    default_enabled: bool = True
    min_confidence: float = 0.7  # Minimum confidence to report

    # Validation pattern (optional, for simple types)
    pattern: str | None = None

    # Whether this requires special recognizer
    requires_recognizer: bool = True

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, EntityType):
            return self.name == other.name
        return False


# =============================================================================
# Standard Entity Types (Presidio built-in)
# =============================================================================

PERSON = EntityType(
    name="PERSON",
    display_name="Person Name",
    display_name_id="Nama Orang",
    category=EntityCategory.PERSONAL,
    description="Full or partial person names",
    description_id="Nama lengkap atau sebagian dari nama orang",
)

EMAIL_ADDRESS = EntityType(
    name="EMAIL_ADDRESS",
    display_name="Email Address",
    display_name_id="Alamat Email",
    category=EntityCategory.CONTACT,
    description="Email addresses",
    description_id="Alamat email",
)

PHONE_NUMBER = EntityType(
    name="PHONE_NUMBER",
    display_name="Phone Number",
    display_name_id="Nomor Telepon",
    category=EntityCategory.CONTACT,
    description="Phone numbers in various formats",
    description_id="Nomor telepon dalam berbagai format",
)

CREDIT_CARD = EntityType(
    name="CREDIT_CARD",
    display_name="Credit Card",
    display_name_id="Kartu Kredit",
    category=EntityCategory.FINANCIAL,
    description="Credit card numbers",
    description_id="Nomor kartu kredit",
)

IBAN_CODE = EntityType(
    name="IBAN_CODE",
    display_name="IBAN",
    display_name_id="Kode IBAN",
    category=EntityCategory.FINANCIAL,
    description="International Bank Account Number",
    description_id="Nomor Rekening Bank Internasional",
)

IP_ADDRESS = EntityType(
    name="IP_ADDRESS",
    display_name="IP Address",
    display_name_id="Alamat IP",
    category=EntityCategory.CONTACT,
    description="IPv4 and IPv6 addresses",
    description_id="Alamat IPv4 dan IPv6",
)

DATE_TIME = EntityType(
    name="DATE_TIME",
    display_name="Date/Time",
    display_name_id="Tanggal/Waktu",
    category=EntityCategory.PERSONAL,
    description="Dates and times",
    description_id="Tanggal dan waktu",
    default_enabled=False,  # Often too noisy
)

LOCATION = EntityType(
    name="LOCATION",
    display_name="Location",
    display_name_id="Lokasi",
    category=EntityCategory.LOCATION,
    description="Geographic locations, addresses",
    description_id="Lokasi geografis, alamat",
)

NRP = EntityType(
    name="NRP",
    display_name="ID Number",
    display_name_id="Nomor ID",
    category=EntityCategory.PERSONAL,
    description="Generic ID numbers",
    description_id="Nomor ID umum",
)

MEDICAL_LICENSE = EntityType(
    name="MEDICAL_LICENSE",
    display_name="Medical License",
    display_name_id="Lisensi Medis",
    category=EntityCategory.HEALTH,
    description="Medical license numbers",
    description_id="Nomor lisensi medis",
)

URL = EntityType(
    name="URL",
    display_name="URL",
    display_name_id="URL",
    category=EntityCategory.CONTACT,
    description="Web URLs",
    description_id="URL web",
    default_enabled=False,  # Often not sensitive
)

# =============================================================================
# Indonesian-Specific Entity Types
# =============================================================================

ID_NIK = EntityType(
    name="ID_NIK",
    display_name="NIK (Indonesian ID)",
    display_name_id="NIK (Nomor Induk Kependudukan)",
    category=EntityCategory.GOVERNMENT,
    description="Indonesian National ID Number (16 digits)",
    description_id="Nomor Induk Kependudukan Indonesia (16 digit)",
    requires_recognizer=True,
)

ID_NPWP = EntityType(
    name="ID_NPWP",
    display_name="NPWP (Tax ID)",
    display_name_id="NPWP (Nomor Pokok Wajib Pajak)",
    category=EntityCategory.GOVERNMENT,
    description="Indonesian Tax ID Number",
    description_id="Nomor Pokok Wajib Pajak",
    requires_recognizer=True,
)

ID_KK = EntityType(
    name="ID_KK",
    display_name="KK (Family Card)",
    display_name_id="No. KK (Kartu Keluarga)",
    category=EntityCategory.GOVERNMENT,
    description="Indonesian Family Card Number",
    description_id="Nomor Kartu Keluarga",
    requires_recognizer=True,
)

ID_PHONE = EntityType(
    name="ID_PHONE",
    display_name="Indonesian Phone",
    display_name_id="Nomor HP Indonesia",
    category=EntityCategory.CONTACT,
    description="Indonesian phone numbers (08xx, +62)",
    description_id="Nomor telepon Indonesia (08xx, +62)",
    requires_recognizer=True,
)

ID_PASSPORT = EntityType(
    name="ID_PASSPORT",
    display_name="Indonesian Passport",
    display_name_id="Paspor Indonesia",
    category=EntityCategory.GOVERNMENT,
    description="Indonesian passport number",
    description_id="Nomor paspor Indonesia",
    requires_recognizer=True,
)

ID_SIM = EntityType(
    name="ID_SIM",
    display_name="SIM (Driver License)",
    display_name_id="SIM (Surat Izin Mengemudi)",
    category=EntityCategory.GOVERNMENT,
    description="Indonesian Driver License Number",
    description_id="Nomor Surat Izin Mengemudi",
    requires_recognizer=True,
)

ID_BPJS = EntityType(
    name="ID_BPJS",
    display_name="BPJS Number",
    display_name_id="Nomor BPJS",
    category=EntityCategory.HEALTH,
    description="Indonesian social security (BPJS) number",
    description_id="Nomor BPJS Kesehatan/Ketenagakerjaan",
    requires_recognizer=True,
)

# =============================================================================
# Business/Financial Entity Types
# =============================================================================

ORGANIZATION = EntityType(
    name="ORGANIZATION",
    display_name="Organization",
    display_name_id="Organisasi",
    category=EntityCategory.BUSINESS,
    description="Company and organization names",
    description_id="Nama perusahaan dan organisasi",
    min_confidence=0.75,  # Higher threshold due to false positives
)

BANK_ACCOUNT = EntityType(
    name="BANK_ACCOUNT",
    display_name="Bank Account",
    display_name_id="Rekening Bank",
    category=EntityCategory.FINANCIAL,
    description="Bank account numbers",
    description_id="Nomor rekening bank",
)

CONTRACT_VALUE = EntityType(
    name="CONTRACT_VALUE",
    display_name="Contract Value",
    display_name_id="Nilai Kontrak",
    category=EntityCategory.BUSINESS,
    description="Monetary values in contracts",
    description_id="Nilai uang dalam kontrak",
    default_enabled=False,  # Requires explicit enable
)

SALARY = EntityType(
    name="SALARY",
    display_name="Salary",
    display_name_id="Gaji",
    category=EntityCategory.FINANCIAL,
    description="Salary and compensation information",
    description_id="Informasi gaji dan kompensasi",
    default_enabled=False,  # HR-specific
)

# =============================================================================
# Custom/Project-Specific Types
# =============================================================================

CUSTOM_TERM = EntityType(
    name="CUSTOM_TERM",
    display_name="Custom Term",
    display_name_id="Istilah Kustom",
    category=EntityCategory.CUSTOM,
    description="User-defined sensitive terms",
    description_id="Istilah sensitif yang didefinisikan pengguna",
    requires_recognizer=True,
)


# =============================================================================
# Entity Type Registry
# =============================================================================

@dataclass
class EntityTypeRegistry:
    """Registry of all available entity types."""

    _types: dict[str, EntityType] = field(default_factory=dict)

    # Built-in types that are always available
    BUILTIN_TYPES: ClassVar[list[EntityType]] = [
        # Standard (Presidio)
        PERSON,
        EMAIL_ADDRESS,
        PHONE_NUMBER,
        CREDIT_CARD,
        IBAN_CODE,
        IP_ADDRESS,
        DATE_TIME,
        LOCATION,
        NRP,
        MEDICAL_LICENSE,
        URL,
        # Indonesian
        ID_NIK,
        ID_NPWP,
        ID_KK,
        ID_PHONE,
        ID_PASSPORT,
        ID_SIM,
        ID_BPJS,
        # Business
        ORGANIZATION,
        BANK_ACCOUNT,
        CONTRACT_VALUE,
        SALARY,
        # Custom
        CUSTOM_TERM,
    ]

    def __post_init__(self) -> None:
        """Initialize with built-in types."""
        for entity_type in self.BUILTIN_TYPES:
            self._types[entity_type.name] = entity_type

    def get(self, name: str) -> EntityType | None:
        """Get an entity type by name."""
        return self._types.get(name)

    def get_or_default(self, name: str) -> EntityType:
        """Get an entity type or create a default one."""
        if name in self._types:
            return self._types[name]

        # Create a default type for unknown names
        return EntityType(
            name=name,
            display_name=name.replace("_", " ").title(),
            display_name_id=name.replace("_", " ").title(),
            category=EntityCategory.CUSTOM,
            requires_recognizer=True,
        )

    def register(self, entity_type: EntityType) -> None:
        """Register a new entity type."""
        self._types[entity_type.name] = entity_type

    def unregister(self, name: str) -> None:
        """Unregister an entity type."""
        if name in self._types and self._types[name] not in self.BUILTIN_TYPES:
            del self._types[name]

    def all(self) -> list[EntityType]:
        """Get all registered entity types."""
        return list(self._types.values())

    def by_category(self, category: EntityCategory) -> list[EntityType]:
        """Get entity types by category."""
        return [t for t in self._types.values() if t.category == category]

    def enabled_by_default(self) -> list[EntityType]:
        """Get entity types enabled by default."""
        return [t for t in self._types.values() if t.default_enabled]

    def indonesian_types(self) -> list[EntityType]:
        """Get Indonesian-specific entity types."""
        return [t for t in self._types.values() if t.name.startswith("ID_")]


# Global registry instance
_registry: EntityTypeRegistry | None = None


def get_entity_registry() -> EntityTypeRegistry:
    """Get the global entity type registry."""
    global _registry
    if _registry is None:
        _registry = EntityTypeRegistry()
    return _registry
