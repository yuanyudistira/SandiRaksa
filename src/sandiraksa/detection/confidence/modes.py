"""
Scan Modes for PII Detection.

Provides different detection modes optimized for different use cases:

- STRICT: Maximize recall, minimize missed PII
  - Best for: HR, medical, financial, legal documents
  - Tradeoff: More false positives

- BALANCED: Balance precision and recall
  - Best for: General documents, mixed content
  - Tradeoff: May miss some edge cases

- MINIMAL: Maximize precision, minimize false positives
  - Best for: Documents with lots of non-PII numbers/text
  - Tradeoff: May miss some true PII
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from sandiraksa.detection.confidence.classifier import (
    ConfidenceThresholds,
    EntityThresholds,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ScanMode(str, Enum):
    """
    Detection scan modes.

    Each mode optimizes for different goals:
    - STRICT: Catch as much PII as possible (high recall)
    - BALANCED: Balance between precision and recall
    - MINIMAL: Reduce false positives (high precision)
    """

    STRICT = "strict"
    BALANCED = "balanced"
    MINIMAL = "minimal"

    @property
    def display_name(self) -> str:
        """User-friendly display name."""
        return {
            ScanMode.STRICT: "Strict Mode",
            ScanMode.BALANCED: "Balanced Mode",
            ScanMode.MINIMAL: "Minimal Mode",
        }[self]

    @property
    def description(self) -> str:
        """Mode description for UI."""
        return {
            ScanMode.STRICT: (
                "Maximum protection - catches more PII but may have "
                "more false positives. Best for sensitive documents."
            ),
            ScanMode.BALANCED: (
                "Balanced detection - good tradeoff between catching PII "
                "and avoiding false positives. Recommended for most documents."
            ),
            ScanMode.MINIMAL: (
                "Minimal detection - only high-confidence PII. "
                "Best for documents with lots of numbers/codes."
            ),
        }[self]

    @property
    def recommended_for(self) -> list[str]:
        """Document types this mode is recommended for."""
        return {
            ScanMode.STRICT: [
                "HR documents",
                "Medical records",
                "Financial statements",
                "Legal documents",
                "Customer data exports",
                "Payroll files",
            ],
            ScanMode.BALANCED: [
                "General documents",
                "Reports",
                "Presentations",
                "Mixed content",
            ],
            ScanMode.MINIMAL: [
                "Technical documents",
                "Invoices with many reference numbers",
                "Logs and system outputs",
                "Documents with known false positive issues",
            ],
        }[self]


@dataclass
class ScanModeConfig:
    """
    Configuration for a scan mode.

    Defines thresholds, enabled detectors, and behavior for each mode.
    """

    mode: ScanMode
    thresholds: EntityThresholds
    include_low_confidence: bool
    enable_ner: bool
    enable_context_boost: bool
    min_score_override: float | None  # Override minimum score for all entities

    # Detector weights (multipliers for raw scores)
    ner_weight: float = 1.0
    regex_weight: float = 1.0
    structured_weight: float = 1.0
    custom_terms_weight: float = 1.0

    # Context scoring adjustments
    context_boost_max: float = 0.2
    context_penalty_max: float = 0.15


# Pre-defined mode configurations

def _create_strict_thresholds() -> EntityThresholds:
    """Create thresholds for STRICT mode (lower thresholds)."""
    return EntityThresholds(
        # Structured IDs - already high precision
        nik=ConfidenceThresholds(high=0.8, medium=0.5, low=0.3),
        npwp=ConfidenceThresholds(high=0.8, medium=0.5, low=0.3),
        kk=ConfidenceThresholds(high=0.8, medium=0.5, low=0.3),
        # Contact - lower thresholds
        email=ConfidenceThresholds(high=0.85, medium=0.6, low=0.4),
        phone=ConfidenceThresholds(high=0.7, medium=0.4, low=0.25),
        # NER - accept more candidates
        person=ConfidenceThresholds(high=0.65, medium=0.4, low=0.25),
        organization=ConfidenceThresholds(high=0.65, medium=0.4, low=0.25),
        location=ConfidenceThresholds(high=0.6, medium=0.35, low=0.2),
        # Financial/medical
        credit_card=ConfidenceThresholds(high=0.85, medium=0.6, low=0.4),
        iban=ConfidenceThresholds(high=0.85, medium=0.6, low=0.4),
        medical_record=ConfidenceThresholds(high=0.7, medium=0.4, low=0.25),
        # Default
        default=ConfidenceThresholds(high=0.7, medium=0.4, low=0.25),
    )


def _create_balanced_thresholds() -> EntityThresholds:
    """Create thresholds for BALANCED mode (default thresholds)."""
    return EntityThresholds()  # Use defaults


def _create_minimal_thresholds() -> EntityThresholds:
    """Create thresholds for MINIMAL mode (higher thresholds)."""
    return EntityThresholds(
        # Structured IDs - require more confidence
        nik=ConfidenceThresholds(high=0.9, medium=0.7, low=0.5),
        npwp=ConfidenceThresholds(high=0.9, medium=0.7, low=0.5),
        kk=ConfidenceThresholds(high=0.9, medium=0.7, low=0.5),
        # Contact - higher thresholds
        email=ConfidenceThresholds(high=0.95, medium=0.8, low=0.6),
        phone=ConfidenceThresholds(high=0.9, medium=0.7, low=0.5),
        # NER - only high confidence
        person=ConfidenceThresholds(high=0.85, medium=0.65, low=0.5),
        organization=ConfidenceThresholds(high=0.85, medium=0.65, low=0.5),
        location=ConfidenceThresholds(high=0.8, medium=0.6, low=0.45),
        # Financial/medical
        credit_card=ConfidenceThresholds(high=0.95, medium=0.8, low=0.6),
        iban=ConfidenceThresholds(high=0.95, medium=0.8, low=0.6),
        medical_record=ConfidenceThresholds(high=0.9, medium=0.7, low=0.5),
        # Default
        default=ConfidenceThresholds(high=0.9, medium=0.7, low=0.5),
    )


# Pre-built configurations
STRICT_CONFIG = ScanModeConfig(
    mode=ScanMode.STRICT,
    thresholds=_create_strict_thresholds(),
    include_low_confidence=True,
    enable_ner=True,
    enable_context_boost=True,
    min_score_override=None,
    ner_weight=1.1,  # Boost NER slightly
    regex_weight=1.0,
    structured_weight=1.0,
    custom_terms_weight=1.2,  # Boost custom terms
    context_boost_max=0.25,
    context_penalty_max=0.1,
)

BALANCED_CONFIG = ScanModeConfig(
    mode=ScanMode.BALANCED,
    thresholds=_create_balanced_thresholds(),
    include_low_confidence=True,
    enable_ner=True,
    enable_context_boost=True,
    min_score_override=None,
    ner_weight=1.0,
    regex_weight=1.0,
    structured_weight=1.0,
    custom_terms_weight=1.0,
    context_boost_max=0.2,
    context_penalty_max=0.15,
)

MINIMAL_CONFIG = ScanModeConfig(
    mode=ScanMode.MINIMAL,
    thresholds=_create_minimal_thresholds(),
    include_low_confidence=False,  # Exclude low confidence
    enable_ner=True,
    enable_context_boost=True,
    min_score_override=0.5,  # Higher minimum
    ner_weight=0.9,  # Slightly reduce NER weight
    regex_weight=1.0,
    structured_weight=1.1,  # Prefer structured detectors
    custom_terms_weight=1.0,
    context_boost_max=0.15,
    context_penalty_max=0.2,  # Allow more penalty
)


def get_mode_config(mode: ScanMode | str) -> ScanModeConfig:
    """
    Get configuration for a scan mode.

    Args:
        mode: ScanMode enum or string

    Returns:
        ScanModeConfig for the mode
    """
    if isinstance(mode, str):
        mode = ScanMode(mode.lower())

    configs = {
        ScanMode.STRICT: STRICT_CONFIG,
        ScanMode.BALANCED: BALANCED_CONFIG,
        ScanMode.MINIMAL: MINIMAL_CONFIG,
    }

    return configs[mode]


def get_mode_thresholds(mode: ScanMode | str) -> EntityThresholds:
    """
    Get thresholds for a scan mode.

    Args:
        mode: ScanMode enum or string

    Returns:
        EntityThresholds for the mode
    """
    return get_mode_config(mode).thresholds


def recommend_mode(document_type: str | None = None) -> ScanMode:
    """
    Recommend a scan mode based on document type.

    Args:
        document_type: Type of document (optional)

    Returns:
        Recommended ScanMode
    """
    if document_type is None:
        return ScanMode.BALANCED

    doc_lower = document_type.lower()

    # Check for strict mode indicators
    strict_indicators = [
        "hr", "human resource", "payroll", "salary",
        "medical", "patient", "health", "hospital",
        "financial", "bank", "account", "credit",
        "legal", "contract", "compliance",
        "customer", "client", "personal data",
    ]

    for indicator in strict_indicators:
        if indicator in doc_lower:
            return ScanMode.STRICT

    # Check for minimal mode indicators
    minimal_indicators = [
        "technical", "log", "system",
        "invoice", "reference", "order",
        "code", "programming", "config",
    ]

    for indicator in minimal_indicators:
        if indicator in doc_lower:
            return ScanMode.MINIMAL

    return ScanMode.BALANCED


@dataclass
class ModeComparison:
    """Comparison between scan modes for a set of findings."""

    strict_count: int
    balanced_count: int
    minimal_count: int
    strict_only: int  # Found only in strict
    minimal_excluded: int  # Found in balanced but not minimal


def compare_modes(
    findings_with_scores: list[tuple[str, float]],
) -> ModeComparison:
    """
    Compare how different modes would handle findings.

    Args:
        findings_with_scores: List of (entity_type, score) tuples

    Returns:
        ModeComparison showing differences
    """
    strict = get_mode_config(ScanMode.STRICT)
    balanced = get_mode_config(ScanMode.BALANCED)
    minimal = get_mode_config(ScanMode.MINIMAL)

    strict_count = 0
    balanced_count = 0
    minimal_count = 0

    for entity_type, score in findings_with_scores:
        strict_thresh = strict.thresholds.get_thresholds(entity_type)
        balanced_thresh = balanced.thresholds.get_thresholds(entity_type)
        minimal_thresh = minimal.thresholds.get_thresholds(entity_type)

        if strict_thresh.get_band(score) is not None:
            strict_count += 1
        if balanced_thresh.get_band(score) is not None:
            balanced_count += 1
        if minimal_thresh.get_band(score) is not None:
            if minimal.include_low_confidence or score >= minimal_thresh.medium:
                minimal_count += 1

    return ModeComparison(
        strict_count=strict_count,
        balanced_count=balanced_count,
        minimal_count=minimal_count,
        strict_only=strict_count - balanced_count,
        minimal_excluded=balanced_count - minimal_count,
    )


__all__ = [
    "ScanMode",
    "ScanModeConfig",
    "get_mode_config",
    "get_mode_thresholds",
    "recommend_mode",
    "compare_modes",
    "ModeComparison",
    "STRICT_CONFIG",
    "BALANCED_CONFIG",
    "MINIMAL_CONFIG",
]
