"""
Confidence Filtering for PII Findings.

Provides flexible filtering of findings by:
- Confidence band (HIGH, MEDIUM, LOW)
- Entity type
- Score range
- Recognizer source
- Custom predicates

Useful for:
- UI filtering (show only high confidence)
- Export filtering (exclude low confidence)
- Review workflows (focus on medium confidence)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, TYPE_CHECKING

from sandiraksa.detection.confidence.classifier import ConfidenceBand

if TYPE_CHECKING:
    from sandiraksa.domain.finding import Finding

logger = logging.getLogger(__name__)


@dataclass
class FilterCriteria:
    """
    Criteria for filtering findings.

    All criteria are ANDed together. None/empty means no filter.

    Attributes:
        confidence_bands: Include only these bands (None = all)
        entity_types: Include only these types (None = all)
        exclude_entity_types: Exclude these types
        min_score: Minimum raw score (inclusive)
        max_score: Maximum raw score (inclusive)
        recognizers: Include only from these recognizers (None = all)
        exclude_recognizers: Exclude from these recognizers
        custom_predicate: Custom filter function
    """

    confidence_bands: set[ConfidenceBand | str] | None = None
    entity_types: set[str] | None = None
    exclude_entity_types: set[str] | None = None
    min_score: float | None = None
    max_score: float | None = None
    recognizers: set[str] | None = None
    exclude_recognizers: set[str] | None = None
    custom_predicate: Callable[["Finding"], bool] | None = None

    def __post_init__(self):
        """Normalize confidence bands to enum values."""
        if self.confidence_bands:
            normalized = set()
            for band in self.confidence_bands:
                if isinstance(band, str):
                    normalized.add(ConfidenceBand(band.upper()))
                else:
                    normalized.add(band)
            self.confidence_bands = normalized

    def matches(self, finding: "Finding") -> bool:
        """
        Check if finding matches all criteria.

        Args:
            finding: Finding to check

        Returns:
            True if finding matches all criteria
        """
        # Confidence band filter
        if self.confidence_bands:
            band = getattr(finding, "confidence_band", None)
            if band:
                if isinstance(band, str):
                    band = ConfidenceBand(band.upper())
                if band not in self.confidence_bands:
                    return False
            else:
                # No band assigned - exclude if filtering by band
                return False

        # Entity type filter
        if self.entity_types:
            if finding.entity_type.upper() not in {t.upper() for t in self.entity_types}:
                return False

        # Entity type exclusion
        if self.exclude_entity_types:
            if finding.entity_type.upper() in {t.upper() for t in self.exclude_entity_types}:
                return False

        # Score range filter
        if self.min_score is not None:
            if finding.score < self.min_score:
                return False

        if self.max_score is not None:
            if finding.score > self.max_score:
                return False

        # Recognizer filter
        recognizer = getattr(finding, "recognizer_name", None)
        if self.recognizers and recognizer:
            if recognizer not in self.recognizers:
                return False

        if self.exclude_recognizers and recognizer:
            if recognizer in self.exclude_recognizers:
                return False

        # Custom predicate
        if self.custom_predicate:
            if not self.custom_predicate(finding):
                return False

        return True

    @classmethod
    def high_confidence_only(cls) -> "FilterCriteria":
        """Create filter for HIGH confidence only."""
        return cls(confidence_bands={ConfidenceBand.HIGH})

    @classmethod
    def high_and_medium(cls) -> "FilterCriteria":
        """Create filter for HIGH and MEDIUM confidence."""
        return cls(confidence_bands={ConfidenceBand.HIGH, ConfidenceBand.MEDIUM})

    @classmethod
    def exclude_low(cls) -> "FilterCriteria":
        """Create filter that excludes LOW confidence."""
        return cls(confidence_bands={ConfidenceBand.HIGH, ConfidenceBand.MEDIUM})

    @classmethod
    def entity_type(cls, *types: str) -> "FilterCriteria":
        """Create filter for specific entity types."""
        return cls(entity_types=set(types))

    @classmethod
    def min_score_filter(cls, min_score: float) -> "FilterCriteria":
        """Create filter by minimum score."""
        return cls(min_score=min_score)


class ConfidenceFilter:
    """
    Filter findings by confidence and other criteria.

    Provides methods for filtering, grouping, and analyzing findings
    by confidence levels.

    Usage:
        filter = ConfidenceFilter()

        # Filter by confidence
        high_only = filter.filter(findings, FilterCriteria.high_confidence_only())

        # Group by confidence
        grouped = filter.group_by_confidence(findings)
        print(f"High: {len(grouped['HIGH'])}")

        # Get statistics
        stats = filter.get_statistics(findings)
    """

    def filter(
        self,
        findings: list["Finding"],
        criteria: FilterCriteria,
    ) -> list["Finding"]:
        """
        Filter findings by criteria.

        Args:
            findings: List of findings to filter
            criteria: Filter criteria

        Returns:
            Filtered list of findings
        """
        return [f for f in findings if criteria.matches(f)]

    def filter_by_confidence(
        self,
        findings: list["Finding"],
        bands: set[ConfidenceBand | str],
    ) -> list["Finding"]:
        """
        Filter findings by confidence bands.

        Args:
            findings: List of findings
            bands: Confidence bands to include

        Returns:
            Filtered findings
        """
        criteria = FilterCriteria(confidence_bands=bands)
        return self.filter(findings, criteria)

    def filter_by_entity_type(
        self,
        findings: list["Finding"],
        entity_types: set[str],
    ) -> list["Finding"]:
        """
        Filter findings by entity types.

        Args:
            findings: List of findings
            entity_types: Entity types to include

        Returns:
            Filtered findings
        """
        criteria = FilterCriteria(entity_types=entity_types)
        return self.filter(findings, criteria)

    def exclude_low_confidence(
        self,
        findings: list["Finding"],
    ) -> list["Finding"]:
        """
        Exclude LOW confidence findings.

        Args:
            findings: List of findings

        Returns:
            Findings without LOW confidence
        """
        return self.filter(findings, FilterCriteria.exclude_low())

    def group_by_confidence(
        self,
        findings: list["Finding"],
    ) -> dict[str, list["Finding"]]:
        """
        Group findings by confidence band.

        Args:
            findings: List of findings

        Returns:
            Dict mapping band name to findings
        """
        groups: dict[str, list["Finding"]] = {
            "HIGH": [],
            "MEDIUM": [],
            "LOW": [],
            "UNCLASSIFIED": [],
        }

        for finding in findings:
            band = getattr(finding, "confidence_band", None)
            if band:
                band_key = band.upper() if isinstance(band, str) else band.value
                if band_key in groups:
                    groups[band_key].append(finding)
                else:
                    groups["UNCLASSIFIED"].append(finding)
            else:
                groups["UNCLASSIFIED"].append(finding)

        return groups

    def group_by_entity_type(
        self,
        findings: list["Finding"],
    ) -> dict[str, list["Finding"]]:
        """
        Group findings by entity type.

        Args:
            findings: List of findings

        Returns:
            Dict mapping entity type to findings
        """
        groups: dict[str, list["Finding"]] = {}

        for finding in findings:
            entity_type = finding.entity_type.upper()
            if entity_type not in groups:
                groups[entity_type] = []
            groups[entity_type].append(finding)

        return groups

    def get_statistics(
        self,
        findings: list["Finding"],
    ) -> "FilterStatistics":
        """
        Get statistics about findings.

        Args:
            findings: List of findings

        Returns:
            FilterStatistics with counts and breakdowns
        """
        by_confidence = self.group_by_confidence(findings)
        by_entity = self.group_by_entity_type(findings)

        scores = [f.score for f in findings]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        return FilterStatistics(
            total=len(findings),
            high_count=len(by_confidence["HIGH"]),
            medium_count=len(by_confidence["MEDIUM"]),
            low_count=len(by_confidence["LOW"]),
            unclassified_count=len(by_confidence["UNCLASSIFIED"]),
            by_entity_type={k: len(v) for k, v in by_entity.items()},
            average_score=avg_score,
            min_score=min(scores) if scores else 0.0,
            max_score=max(scores) if scores else 0.0,
        )


@dataclass
class FilterStatistics:
    """Statistics about filtered findings."""

    total: int
    high_count: int
    medium_count: int
    low_count: int
    unclassified_count: int
    by_entity_type: dict[str, int]
    average_score: float
    min_score: float
    max_score: float

    @property
    def high_percentage(self) -> float:
        """Percentage of HIGH confidence."""
        return (self.high_count / self.total * 100) if self.total else 0.0

    @property
    def medium_percentage(self) -> float:
        """Percentage of MEDIUM confidence."""
        return (self.medium_count / self.total * 100) if self.total else 0.0

    @property
    def low_percentage(self) -> float:
        """Percentage of LOW confidence."""
        return (self.low_count / self.total * 100) if self.total else 0.0

    @property
    def protectable_count(self) -> int:
        """Count of findings that should be protected by default."""
        return self.high_count + self.medium_count

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total": self.total,
            "by_confidence": {
                "HIGH": self.high_count,
                "MEDIUM": self.medium_count,
                "LOW": self.low_count,
                "UNCLASSIFIED": self.unclassified_count,
            },
            "by_entity_type": self.by_entity_type,
            "scores": {
                "average": round(self.average_score, 3),
                "min": round(self.min_score, 3),
                "max": round(self.max_score, 3),
            },
            "protectable_count": self.protectable_count,
        }

    def summary(self) -> str:
        """Generate summary text."""
        lines = [
            f"Total findings: {self.total}",
            f"  HIGH: {self.high_count} ({self.high_percentage:.1f}%)",
            f"  MEDIUM: {self.medium_count} ({self.medium_percentage:.1f}%)",
            f"  LOW: {self.low_count} ({self.low_percentage:.1f}%)",
            f"Average score: {self.average_score:.1%}",
        ]
        return "\n".join(lines)


# Convenience functions

def filter_findings(
    findings: list["Finding"],
    criteria: FilterCriteria,
) -> list["Finding"]:
    """
    Filter findings by criteria.

    Convenience function wrapping ConfidenceFilter.
    """
    return ConfidenceFilter().filter(findings, criteria)


def get_high_confidence(findings: list["Finding"]) -> list["Finding"]:
    """Get only HIGH confidence findings."""
    return ConfidenceFilter().filter_by_confidence(findings, {ConfidenceBand.HIGH})


def get_protectable(findings: list["Finding"]) -> list["Finding"]:
    """Get findings that should be protected (HIGH and MEDIUM)."""
    return ConfidenceFilter().exclude_low_confidence(findings)


def get_for_review(findings: list["Finding"]) -> list["Finding"]:
    """Get MEDIUM confidence findings for human review."""
    return ConfidenceFilter().filter_by_confidence(findings, {ConfidenceBand.MEDIUM})


__all__ = [
    "FilterCriteria",
    "ConfidenceFilter",
    "FilterStatistics",
    "filter_findings",
    "get_high_confidence",
    "get_protectable",
    "get_for_review",
]
