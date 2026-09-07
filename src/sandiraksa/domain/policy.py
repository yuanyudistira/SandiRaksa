"""
Privacy policy and profile domain models.

Defines how sensitive data should be detected and treated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from sandiraksa.domain.token import TreatmentType

if TYPE_CHECKING:
    pass


class EntityCategory(str, Enum):
    """Categories of sensitive entities."""

    PERSONAL_DATA = "personal_data"
    INDONESIAN_ID = "indonesian_id"
    FINANCIAL = "financial"
    BUSINESS_CONFIDENTIAL = "business_confidential"
    CUSTOM = "custom"


# Standard entity types with their categories
ENTITY_CATEGORIES: dict[str, EntityCategory] = {
    # Personal data
    "PERSON": EntityCategory.PERSONAL_DATA,
    "EMAIL": EntityCategory.PERSONAL_DATA,
    "PHONE_NUMBER": EntityCategory.PERSONAL_DATA,
    "ADDRESS": EntityCategory.PERSONAL_DATA,
    "DATE_OF_BIRTH": EntityCategory.PERSONAL_DATA,
    "LOCATION": EntityCategory.PERSONAL_DATA,
    "URL": EntityCategory.PERSONAL_DATA,
    "IP_ADDRESS": EntityCategory.PERSONAL_DATA,
    # Indonesian identifiers
    "NIK": EntityCategory.INDONESIAN_ID,
    "NPWP": EntityCategory.INDONESIAN_ID,
    "KK": EntityCategory.INDONESIAN_ID,
    "BPJS": EntityCategory.INDONESIAN_ID,
    "PASSPORT_ID": EntityCategory.INDONESIAN_ID,
    "ID_PHONE": EntityCategory.INDONESIAN_ID,
    # Financial
    "CREDIT_CARD": EntityCategory.FINANCIAL,
    "BANK_ACCOUNT": EntityCategory.FINANCIAL,
    "IBAN": EntityCategory.FINANCIAL,
    "SALARY": EntityCategory.FINANCIAL,
    "TRANSACTION_VALUE": EntityCategory.FINANCIAL,
    # Business confidential
    "ORGANIZATION": EntityCategory.BUSINESS_CONFIDENTIAL,
    "CLIENT_NAME": EntityCategory.BUSINESS_CONFIDENTIAL,
    "SUPPLIER_NAME": EntityCategory.BUSINESS_CONFIDENTIAL,
    "PROJECT_CODENAME": EntityCategory.BUSINESS_CONFIDENTIAL,
    "PRODUCT_CODENAME": EntityCategory.BUSINESS_CONFIDENTIAL,
    "PRICING": EntityCategory.BUSINESS_CONFIDENTIAL,
    "MARGIN": EntityCategory.BUSINESS_CONFIDENTIAL,
    "REVENUE": EntityCategory.BUSINESS_CONFIDENTIAL,
    "VALUATION": EntityCategory.BUSINESS_CONFIDENTIAL,
    "EBITDA": EntityCategory.BUSINESS_CONFIDENTIAL,
    # Custom
    "CUSTOM_CONFIDENTIAL": EntityCategory.CUSTOM,
    "BUSINESS_CONFIDENTIAL": EntityCategory.BUSINESS_CONFIDENTIAL,
}


class EntityConfig(BaseModel):
    """Configuration for a specific entity type."""

    enabled: bool = True
    treatment: TreatmentType = TreatmentType.TOKEN
    min_confidence: float = 0.5  # 0.0 - 1.0

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class MetadataConfig(BaseModel):
    """Configuration for document metadata handling."""

    remove_author: bool = True
    remove_last_modified_by: bool = True
    sanitize_title: bool = True
    sanitize_subject: bool = True
    sanitize_keywords: bool = True
    sanitize_comments: bool = True
    sanitize_custom_properties: bool = True


class ReviewConfig(BaseModel):
    """Configuration for review behavior."""

    block_on_high_residual: bool = True
    require_review_for_low_confidence: bool = True
    auto_allow_numbers_only: bool = False


class PrivacyProfile(BaseModel):
    """
    Privacy profile defining detection and treatment rules.

    Built-in profiles:
    - standard_pii: Standard PII detection
    - hr: HR/Personnel data
    - customer: Customer data protection
    - legal: Legal documents
    - ma: M&A / Due Diligence
    - banking: Banking / Financial
    """

    id: str
    name: str
    description: str = ""
    version: int = 1

    # Entity configurations
    entities: dict[str, EntityConfig] = Field(default_factory=dict)

    # Category-level enable/disable
    enabled_categories: set[EntityCategory] = Field(
        default_factory=lambda: set(EntityCategory)
    )

    # Metadata handling
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)

    # Review settings
    review: ReviewConfig = Field(default_factory=ReviewConfig)

    class Config:
        """Pydantic configuration."""

        use_enum_values = True

    def is_entity_enabled(self, entity_type: str) -> bool:
        """Check if an entity type is enabled."""
        # Check explicit entity config
        if entity_type in self.entities:
            return self.entities[entity_type].enabled

        # Check category
        category = ENTITY_CATEGORIES.get(entity_type)
        if category:
            return category in self.enabled_categories

        # Default to enabled for unknown types
        return True

    def get_treatment(self, entity_type: str) -> TreatmentType:
        """Get the treatment type for an entity."""
        if entity_type in self.entities:
            return TreatmentType(self.entities[entity_type].treatment)
        return TreatmentType.TOKEN

    def get_min_confidence(self, entity_type: str) -> float:
        """Get the minimum confidence threshold for an entity."""
        if entity_type in self.entities:
            return self.entities[entity_type].min_confidence
        return 0.5


@dataclass
class CustomRule:
    """User-defined custom detection rule."""

    id: str
    project_id: str
    rule_type: str  # "exact", "phrase", "regex"
    entity_type: str
    pattern: str  # The pattern to match
    case_sensitive: bool = False
    treatment: TreatmentType = TreatmentType.TOKEN
    enabled: bool = True

    @property
    def is_regex(self) -> bool:
        """Check if this is a regex rule."""
        return self.rule_type == "regex"


@dataclass
class AllowRule:
    """Rule to allow (not protect) specific values."""

    id: str
    project_id: str
    value: str
    entity_type: str | None = None  # None = allow for all types
    case_sensitive: bool = False


class ProtectionPolicy(BaseModel):
    """
    Complete protection policy for a project.

    Combines profile settings with project-specific overrides.
    """

    profile: PrivacyProfile
    project_id: str
    reversible: bool = True

    # Project-level overrides
    entity_overrides: dict[str, EntityConfig] = Field(default_factory=dict)

    # Custom rules and allow rules are loaded separately

    def is_entity_enabled(self, entity_type: str) -> bool:
        """Check if an entity type is enabled (with overrides)."""
        if entity_type in self.entity_overrides:
            return self.entity_overrides[entity_type].enabled
        return self.profile.is_entity_enabled(entity_type)

    def get_treatment(self, entity_type: str) -> TreatmentType:
        """Get the treatment type (with overrides)."""
        if entity_type in self.entity_overrides:
            return TreatmentType(self.entity_overrides[entity_type].treatment)
        return self.profile.get_treatment(entity_type)


# Default profile definitions (to be loaded from YAML files)
DEFAULT_PROFILE_IDS = [
    "standard_pii",
    "hr",
    "customer",
    "legal",
    "ma",
    "banking",
]
