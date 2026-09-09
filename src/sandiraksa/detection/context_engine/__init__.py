"""
Context Engine for PII detection.

This module provides context-aware analysis to improve detection accuracy.
Context types:
- Lexical: Keywords that suggest or negate PII presence
- Structural: Headers, labels, table structures
- Spatial: Position-based context (PowerPoint)
- Document: Document-level hints (HR docs, medical records, etc.)
"""

from sandiraksa.detection.context_engine.lexical import (
    LexicalContext,
    POSITIVE_KEYWORDS,
    NEGATIVE_KEYWORDS,
    ENTITY_KEYWORDS,
)
from sandiraksa.detection.context_engine.structural import (
    StructuralContext,
    extract_structural_context,
)
from sandiraksa.detection.context_engine.spatial import (
    SpatialContext,
    SpatialRelation,
)
from sandiraksa.detection.context_engine.document import (
    DocumentContext,
    DocumentType,
    detect_document_type,
)
from sandiraksa.detection.context_engine.scorer import (
    ContextScorer,
    ContextScoringResult,
)

__all__ = [
    # Lexical
    "LexicalContext",
    "POSITIVE_KEYWORDS",
    "NEGATIVE_KEYWORDS",
    "ENTITY_KEYWORDS",
    # Structural
    "StructuralContext",
    "extract_structural_context",
    # Spatial
    "SpatialContext",
    "SpatialRelation",
    # Document
    "DocumentContext",
    "DocumentType",
    "detect_document_type",
    # Scorer
    "ContextScorer",
    "ContextScoringResult",
]
