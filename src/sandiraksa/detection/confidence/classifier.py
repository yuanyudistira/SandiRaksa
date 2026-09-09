"""
Confidence Classifier.

Classifies raw detection scores into user-friendly confidence bands:
- HIGH: Strong confidence, likely true positive
- MEDIUM: Moderate confidence, may need review
- LOW: Weak confidence, higher false positive risk

Supports per-entity type threshold tuning for optimal accuracy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sandiraksa.domain.finding import Finding

logger = logging.getLogger(__name__)


class ConfidenceBand(str, Enum):
    """Confidence bands for PII findings."""

    HIGH = "HIGH"       # >= high threshold (e.g., 0.8)
    MEDIUM = "MEDIUM"   # >= medium threshold (e.g., 0.5)
    LOW = "LOW"         # < medium threshold

    @property
    def display_name(self) -> str:
        """User-friendly display name."""
        return {
            ConfidenceBand.HIGH: "High Confidence",
            ConfidenceBand.MEDIUM: "Medium Confidence",
            ConfidenceBand.LOW: "Low Confidence",
        }[self]

    @property
    def color_code(self) -> str:
        """Color code for UI display."""
        return {
            ConfidenceBand.HIGH: "#28a745",     # Green
            ConfidenceBand.MEDIUM: "#ffc107",   # Yellow/Amber
            ConfidenceBand.LOW: "#dc3545",      # Red
        }[self]

    @property
    def should_protect_by_default(self) -> bool:
        """Whether findings in this band should be protected by default."""
        return self in (ConfidenceBand.HIGH, ConfidenceBand.MEDIUM)


@dataclass
class ConfidenceThresholds:
    """
    Thresholds for confidence band classification.

    Attributes:
        high: Minimum score for HIGH confidence
        medium: Minimum score for MEDIUM confidence
        low: Minimum score to include (below this is filtered out)
    """

    high: float = 0.8
    medium: float = 0.5
    low: float = 0.3  # Minimum to include

    def __post_init__(self):
        """Validate thresholds."""
        if not (0 <= self.low <= self.medium <= self.high <= 1.0):
            raise ValueError(
                f"Thresholds must satisfy: 0 <= low ({self.low}) <= "
                f"medium ({self.medium}) <= high ({self.high}) <= 1.0"
            )

    def get_band(self, score: float) -> ConfidenceBand | None:
        """
        Get confidence band for a score.

        Args:
            score: Raw confidence score (0.0-1.0)

        Returns:
            ConfidenceBand or None if below minimum
        """
        if score < self.low:
            return None
        elif score >= self.high:
            return ConfidenceBand.HIGH
        elif score >= self.medium:
            return ConfidenceBand.MEDIUM
        else:
            return ConfidenceBand.LOW


@dataclass
class EntityThresholds:
    """
    Per-entity type threshold configuration.

    Different entity types may have different optimal thresholds
    based on recognizer characteristics and false positive rates.
    """

    # Indonesian structured identifiers (high precision)
    nik: ConfidenceThresholds = field(
        default_factory=lambda: ConfidenceThresholds(high=0.85, medium=0.6, low=0.4)
    )
    npwp: ConfidenceThresholds = field(
        default_factory=lambda: ConfidenceThresholds(high=0.85, medium=0.6, low=0.4)
    )
    kk: ConfidenceThresholds = field(
        default_factory=lambda: ConfidenceThresholds(high=0.85, medium=0.6, low=0.4)
    )

    # Contact information
    email: ConfidenceThresholds = field(
        default_factory=lambda: ConfidenceThresholds(high=0.9, medium=0.7, low=0.5)
    )
    phone: ConfidenceThresholds = field(
        default_factory=lambda: ConfidenceThresholds(high=0.8, medium=0.5, low=0.3)
    )

    # NER-detected entities (more noise)
    person: ConfidenceThresholds = field(
        default_factory=lambda: ConfidenceThresholds(high=0.75, medium=0.5, low=0.35)
    )
    organization: ConfidenceThresholds = field(
        default_factory=lambda: ConfidenceThresholds(high=0.75, medium=0.5, low=0.35)
    )
    location: ConfidenceThresholds = field(
        default_factory=lambda: ConfidenceThresholds(high=0.7, medium=0.45, low=0.3)
    )

    # Financial/medical
    credit_card: ConfidenceThresholds = field(
        default_factory=lambda: ConfidenceThresholds(high=0.9, medium=0.7, low=0.5)
    )
    iban: ConfidenceThresholds = field(
        default_factory=lambda: ConfidenceThresholds(high=0.9, medium=0.7, low=0.5)
    )
    medical_record: ConfidenceThresholds = field(
        default_factory=lambda: ConfidenceThresholds(high=0.8, medium=0.5, low=0.3)
    )

    # Default for unknown entity types
    default: ConfidenceThresholds = field(
        default_factory=lambda: ConfidenceThresholds(high=0.8, medium=0.5, low=0.3)
    )

    def get_thresholds(self, entity_type: str) -> ConfidenceThresholds:
        """
        Get thresholds for an entity type.

        Args:
            entity_type: Entity type string (case-insensitive)

        Returns:
            ConfidenceThresholds for the entity type
        """
        # Normalize entity type
        normalized = entity_type.lower().replace("_", "").replace("-", "")

        # Map common variations
        type_map = {
            "idnik": self.nik,
            "nik": self.nik,
            "idnpwp": self.npwp,
            "npwp": self.npwp,
            "idkk": self.kk,
            "kk": self.kk,
            "emailaddress": self.email,
            "email": self.email,
            "phonenumber": self.phone,
            "phone": self.phone,
            "idphone": self.phone,
            "person": self.person,
            "pername": self.person,
            "organization": self.organization,
            "org": self.organization,
            "location": self.location,
            "loc": self.location,
            "gpe": self.location,
            "creditcard": self.credit_card,
            "creditcardnumber": self.credit_card,
            "iban": self.iban,
            "ibancode": self.iban,
            "medicalrecord": self.medical_record,
            "medicalrecordnumber": self.medical_record,
        }

        return type_map.get(normalized, self.default)


class ConfidenceClassifier:
    """
    Classifies detection findings into confidence bands.

    Provides user-friendly confidence levels (High/Medium/Low) based
    on raw detection scores, with per-entity type threshold tuning.

    Usage:
        classifier = ConfidenceClassifier()
        classified = classifier.classify(findings)

        for finding in classified:
            print(f"{finding.text}: {finding.confidence_band}")
    """

    def __init__(
        self,
        thresholds: EntityThresholds | None = None,
        include_low: bool = True,
    ):
        """
        Initialize classifier.

        Args:
            thresholds: Per-entity type thresholds (uses defaults if None)
            include_low: Whether to include LOW confidence findings
        """
        self._thresholds = thresholds or EntityThresholds()
        self._include_low = include_low

    def classify(
        self,
        findings: list["Finding"],
    ) -> list["Finding"]:
        """
        Classify findings into confidence bands.

        Args:
            findings: List of findings with raw scores

        Returns:
            List of findings with confidence_band set
        """
        classified = []

        for finding in findings:
            entity_thresholds = self._thresholds.get_thresholds(
                finding.entity_type
            )
            band = entity_thresholds.get_band(finding.score)

            if band is None:
                # Below minimum threshold
                logger.debug(
                    f"Filtered out {finding.entity_type} "
                    f"(score={finding.score:.2f} below min)"
                )
                continue

            if band == ConfidenceBand.LOW and not self._include_low:
                logger.debug(
                    f"Filtered out LOW confidence {finding.entity_type}"
                )
                continue

            # Set confidence band on finding
            finding.confidence_band = band.value
            classified.append(finding)

        return classified

    def classify_single(
        self,
        finding: "Finding",
    ) -> "Finding | None":
        """
        Classify a single finding.

        Args:
            finding: Finding to classify

        Returns:
            Finding with confidence_band or None if filtered
        """
        result = self.classify([finding])
        return result[0] if result else None

    def get_band(
        self,
        entity_type: str,
        score: float,
    ) -> ConfidenceBand | None:
        """
        Get confidence band for entity type and score.

        Args:
            entity_type: Entity type string
            score: Raw confidence score

        Returns:
            ConfidenceBand or None if below threshold
        """
        thresholds = self._thresholds.get_thresholds(entity_type)
        return thresholds.get_band(score)

    def get_threshold_info(
        self,
        entity_type: str,
    ) -> dict:
        """
        Get threshold information for an entity type.

        Args:
            entity_type: Entity type string

        Returns:
            Dictionary with threshold values
        """
        thresholds = self._thresholds.get_thresholds(entity_type)
        return {
            "entity_type": entity_type,
            "high_threshold": thresholds.high,
            "medium_threshold": thresholds.medium,
            "low_threshold": thresholds.low,
        }

    @property
    def thresholds(self) -> EntityThresholds:
        """Get current thresholds."""
        return self._thresholds

    @thresholds.setter
    def thresholds(self, value: EntityThresholds) -> None:
        """Set thresholds."""
        self._thresholds = value


# Convenience functions

def classify_confidence(
    findings: list["Finding"],
    include_low: bool = True,
) -> list["Finding"]:
    """
    Classify findings into confidence bands.

    Convenience function using default thresholds.

    Args:
        findings: List of findings
        include_low: Whether to include LOW confidence

    Returns:
        Classified findings
    """
    classifier = ConfidenceClassifier(include_low=include_low)
    return classifier.classify(findings)


def get_confidence_band(
    entity_type: str,
    score: float,
) -> ConfidenceBand | None:
    """
    Get confidence band for a score.

    Convenience function using default thresholds.
    """
    classifier = ConfidenceClassifier()
    return classifier.get_band(entity_type, score)


__all__ = [
    "ConfidenceBand",
    "ConfidenceThresholds",
    "EntityThresholds",
    "ConfidenceClassifier",
    "classify_confidence",
    "get_confidence_band",
]
