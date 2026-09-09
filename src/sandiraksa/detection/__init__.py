"""Detection engine for PII/sensitive data detection.

This module provides both the legacy detection engine and the new
unified detection pipeline (Sprint 3).

Unified Detection Pipeline (New):
    - UnifiedFinding: Detection result with evidence tracking
    - UnifiedDetectionEngine: Engine accepting LogicalSegments
    - UnifiedRecognizer: Protocol for recognizers
    - OverlapResolver: Resolves overlapping detections
    - PresidioUnifiedRecognizer: Presidio wrapper for unified pipeline
    - IndonesianIdRecognizer: NIK, NPWP, KK, Phone detection

Legacy Detection Engine:
    - DetectionEngine: Original engine interface
    - PresidioRecognizer: Original Presidio wrapper
"""

# Legacy context and engine
from sandiraksa.detection.context import (
    DetectionConfig as LegacyDetectionConfig,
    DetectionContext as LegacyDetectionContext,
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
    create_detection_engine as create_legacy_detection_engine,
    get_presidio_engine,
    PRESIDIO_ENTITY_MAP,
)

# Unified Detection Pipeline (Sprint 3)
from sandiraksa.detection.unified_finding import (
    ConfidenceBand,
    ConfidenceEvidence,
    EvidenceType,
    UnifiedFinding,
    classify_confidence,
)
from sandiraksa.detection.unified_engine import (
    BaseUnifiedRecognizer,
    DetectionConfig,
    DetectionContext,
    DetectionMode,
    EngineStatus,
    RecognizerInfo,
    UnifiedDetectionEngineProtocol,
    UnifiedRecognizer,
)
from sandiraksa.detection.detection_pipeline import (
    CONTEXT_MATCH_BOOST,
    CONTEXT_MISMATCH_PENALTY,
    CONTEXT_TO_ENTITY,
    UnifiedDetectionEngine,
    create_detection_engine,
    get_unified_engine,
)
from sandiraksa.detection.overlap import (
    ENTITY_PRIORITY,
    OverlapPair,
    OverlapResolver,
    OverlapStrategy,
    findings_overlap,
    get_entity_priority,
    get_overlap_pair,
    merge_adjacent_findings,
    resolve_overlaps,
)
from sandiraksa.detection.presidio_adapter import (
    CustomTermsRecognizer,
    IndonesianIdRecognizer,
    PresidioUnifiedRecognizer,
    create_default_recognizers,
)

__all__ = [
    # ==================== Unified Detection Pipeline (Sprint 3) ====================
    # Unified Finding Model
    "UnifiedFinding",
    "ConfidenceBand",
    "ConfidenceEvidence",
    "EvidenceType",
    "classify_confidence",
    # Unified Engine
    "UnifiedDetectionEngine",
    "UnifiedDetectionEngineProtocol",
    "UnifiedRecognizer",
    "BaseUnifiedRecognizer",
    "DetectionConfig",
    "DetectionContext",
    "DetectionMode",
    "EngineStatus",
    "RecognizerInfo",
    "get_unified_engine",
    "create_detection_engine",
    # Context Boosting
    "CONTEXT_TO_ENTITY",
    "CONTEXT_MATCH_BOOST",
    "CONTEXT_MISMATCH_PENALTY",
    # Overlap Resolution
    "OverlapResolver",
    "OverlapStrategy",
    "OverlapPair",
    "ENTITY_PRIORITY",
    "resolve_overlaps",
    "findings_overlap",
    "get_overlap_pair",
    "get_entity_priority",
    "merge_adjacent_findings",
    # Unified Recognizers
    "PresidioUnifiedRecognizer",
    "IndonesianIdRecognizer",
    "CustomTermsRecognizer",
    "create_default_recognizers",
    # ==================== Legacy Detection Engine ====================
    # Legacy Engine
    "DetectionEngine",
    "DetectionError",
    "RecognizerError",
    "Recognizer",
    "BaseRecognizer",
    "RecognizerRegistry",
    "get_detection_engine",
    "initialize_detection_engine",
    # Legacy Presidio
    "PresidioDetectionEngine",
    "PresidioRecognizer",
    "RegexRecognizer",
    "create_legacy_detection_engine",
    "get_presidio_engine",
    "PRESIDIO_ENTITY_MAP",
    # Legacy Context (aliased)
    "LegacyDetectionConfig",
    "LegacyDetectionContext",
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
