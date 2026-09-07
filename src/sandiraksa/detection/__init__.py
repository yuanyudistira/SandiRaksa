"""Detection engine for PII/sensitive data detection."""

from sandiraksa.detection.context import (
    DetectionConfig,
    DetectionContext,
    DetectionPhase,
    DetectionResult,
    DetectionStats,
    TextSegment,
    create_detection_context,
)
from sandiraksa.detection.engine import (
    BaseRecognizer,
    DetectionEngine,
    DetectionError,
    Recognizer,
    RecognizerError,
    RecognizerRegistry,
    get_detection_engine,
    initialize_detection_engine,
)
from sandiraksa.detection.entity_types import (
    EntityCategory,
    EntityType,
    EntityTypeRegistry,
    get_entity_registry,
    # Standard types
    PERSON,
    EMAIL_ADDRESS,
    PHONE_NUMBER,
    CREDIT_CARD,
    IBAN_CODE,
    IP_ADDRESS,
    DATE_TIME,
    LOCATION,
    URL,
    ORGANIZATION,
    # Indonesian types
    ID_NIK,
    ID_NPWP,
    ID_KK,
    ID_PHONE,
    ID_PASSPORT,
    ID_SIM,
    ID_BPJS,
    # Business types
    BANK_ACCOUNT,
    CONTRACT_VALUE,
    SALARY,
    CUSTOM_TERM,
)
from sandiraksa.detection.presidio_engine import (
    PresidioDetectionEngine,
    PresidioRecognizer,
    RegexRecognizer,
    create_detection_engine,
    get_presidio_engine,
    PRESIDIO_ENTITY_MAP,
)

__all__ = [
    # Engine
    "DetectionEngine",
    "DetectionError",
    "RecognizerError",
    "Recognizer",
    "BaseRecognizer",
    "RecognizerRegistry",
    "get_detection_engine",
    "initialize_detection_engine",
    # Presidio
    "PresidioDetectionEngine",
    "PresidioRecognizer",
    "RegexRecognizer",
    "create_detection_engine",
    "get_presidio_engine",
    "PRESIDIO_ENTITY_MAP",
    # Context
    "DetectionContext",
    "DetectionConfig",
    "DetectionResult",
    "DetectionStats",
    "DetectionPhase",
    "TextSegment",
    "create_detection_context",
    # Entity Types
    "EntityType",
    "EntityCategory",
    "EntityTypeRegistry",
    "get_entity_registry",
    # Standard entity type instances
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IBAN_CODE",
    "IP_ADDRESS",
    "DATE_TIME",
    "LOCATION",
    "URL",
    "ORGANIZATION",
    # Indonesian entity type instances
    "ID_NIK",
    "ID_NPWP",
    "ID_KK",
    "ID_PHONE",
    "ID_PASSPORT",
    "ID_SIM",
    "ID_BPJS",
    # Business entity type instances
    "BANK_ACCOUNT",
    "CONTRACT_VALUE",
    "SALARY",
    "CUSTOM_TERM",
]
