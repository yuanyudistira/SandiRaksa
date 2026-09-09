"""
Accuracy Metrics for PII Detection.

Provides precision, recall, and F1 score calculation for
evaluating detection quality against annotated corpus.

Metrics are calculated:
- Per entity type (NIK, PERSON, EMAIL, etc.)
- Per document type (HR, Medical, Banking, etc.)
- Overall aggregate

Matching strategies:
- Exact: Start and end must match exactly
- Overlap: Any overlap counts as match
- Partial: Configurable overlap threshold
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.accuracy.corpus.generator import Annotation, CorpusEntry

logger = logging.getLogger(__name__)


class MatchStrategy(str, Enum):
    """Strategy for matching predictions to annotations."""

    EXACT = "exact"           # Start and end must match exactly
    OVERLAP = "overlap"       # Any overlap counts as match
    PARTIAL = "partial"       # >= threshold overlap required
    CONTAINED = "contained"   # Prediction must be within annotation


@dataclass
class EntityMetrics:
    """
    Metrics for a single entity type.

    Attributes:
        entity_type: The entity type
        true_positives: Correctly detected
        false_positives: Incorrectly detected (not in annotations)
        false_negatives: Missed (in annotations but not detected)
        true_negatives: Correctly not detected (negative annotations)
    """

    entity_type: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0

    @property
    def precision(self) -> float:
        """Precision = TP / (TP + FP)"""
        total = self.true_positives + self.false_positives
        return self.true_positives / total if total > 0 else 0.0

    @property
    def recall(self) -> float:
        """Recall = TP / (TP + FN)"""
        total = self.true_positives + self.false_negatives
        return self.true_positives / total if total > 0 else 0.0

    @property
    def f1_score(self) -> float:
        """F1 = 2 * (precision * recall) / (precision + recall)"""
        p, r = self.precision, self.recall
        return 2 * (p * r) / (p + r) if (p + r) > 0 else 0.0

    @property
    def accuracy(self) -> float:
        """Accuracy = (TP + TN) / (TP + TN + FP + FN)"""
        total = (
            self.true_positives +
            self.true_negatives +
            self.false_positives +
            self.false_negatives
        )
        return (self.true_positives + self.true_negatives) / total if total > 0 else 0.0

    @property
    def total_predictions(self) -> int:
        """Total predictions made."""
        return self.true_positives + self.false_positives

    @property
    def total_annotations(self) -> int:
        """Total annotations (ground truth)."""
        return self.true_positives + self.false_negatives

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
        }

    def __add__(self, other: "EntityMetrics") -> "EntityMetrics":
        """Combine metrics."""
        return EntityMetrics(
            entity_type=self.entity_type,
            true_positives=self.true_positives + other.true_positives,
            false_positives=self.false_positives + other.false_positives,
            false_negatives=self.false_negatives + other.false_negatives,
            true_negatives=self.true_negatives + other.true_negatives,
        )


@dataclass
class AccuracyReport:
    """
    Complete accuracy report for a corpus evaluation.

    Contains metrics broken down by entity type and document type.
    """

    by_entity: dict[str, EntityMetrics] = field(default_factory=dict)
    by_document_type: dict[str, dict[str, EntityMetrics]] = field(default_factory=dict)
    overall: EntityMetrics = field(default_factory=lambda: EntityMetrics("OVERALL"))

    # Metadata
    corpus_size: int = 0
    total_annotations: int = 0
    total_predictions: int = 0

    def get_entity_metrics(self, entity_type: str) -> EntityMetrics:
        """Get metrics for an entity type."""
        return self.by_entity.get(entity_type, EntityMetrics(entity_type))

    def get_f1_score(self, entity_type: str) -> float:
        """Get F1 score for an entity type."""
        return self.get_entity_metrics(entity_type).f1_score

    def to_dict(self) -> dict:
        return {
            "overall": self.overall.to_dict(),
            "by_entity": {k: v.to_dict() for k, v in self.by_entity.items()},
            "by_document_type": {
                dt: {k: v.to_dict() for k, v in metrics.items()}
                for dt, metrics in self.by_document_type.items()
            },
            "corpus_size": self.corpus_size,
            "total_annotations": self.total_annotations,
            "total_predictions": self.total_predictions,
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=" * 60,
            "ACCURACY REPORT",
            "=" * 60,
            f"Corpus size: {self.corpus_size} documents",
            f"Total annotations: {self.total_annotations}",
            f"Total predictions: {self.total_predictions}",
            "",
            "OVERALL METRICS:",
            f"  Precision: {self.overall.precision:.2%}",
            f"  Recall: {self.overall.recall:.2%}",
            f"  F1 Score: {self.overall.f1_score:.2%}",
            "",
            "BY ENTITY TYPE:",
            "-" * 60,
            f"{'Entity':<20} {'Prec':>8} {'Recall':>8} {'F1':>8} {'TP':>6} {'FP':>6} {'FN':>6}",
            "-" * 60,
        ]

        for entity_type, metrics in sorted(self.by_entity.items()):
            lines.append(
                f"{entity_type:<20} "
                f"{metrics.precision:>7.2%} "
                f"{metrics.recall:>7.2%} "
                f"{metrics.f1_score:>7.2%} "
                f"{metrics.true_positives:>6} "
                f"{metrics.false_positives:>6} "
                f"{metrics.false_negatives:>6}"
            )

        lines.append("=" * 60)
        return "\n".join(lines)


@dataclass
class Prediction:
    """A detection prediction for comparison."""

    start: int
    end: int
    text: str
    entity_type: str
    score: float = 0.0

    @property
    def length(self) -> int:
        return self.end - self.start


class AccuracyCalculator:
    """
    Calculator for detection accuracy metrics.

    Compares predictions against annotated corpus entries
    and calculates precision, recall, and F1 scores.
    """

    def __init__(
        self,
        match_strategy: MatchStrategy = MatchStrategy.OVERLAP,
        overlap_threshold: float = 0.5,
        normalize_entity_types: bool = True,
    ):
        """
        Initialize calculator.

        Args:
            match_strategy: Strategy for matching predictions to annotations
            overlap_threshold: Minimum overlap ratio for PARTIAL strategy
            normalize_entity_types: Whether to normalize entity type names
        """
        self._match_strategy = match_strategy
        self._overlap_threshold = overlap_threshold
        self._normalize_types = normalize_entity_types

    def evaluate_corpus(
        self,
        corpus: list["CorpusEntry"],
        predictions_by_entry: dict[str, list[Prediction]],
    ) -> AccuracyReport:
        """
        Evaluate predictions against entire corpus.

        Args:
            corpus: List of annotated corpus entries
            predictions_by_entry: Dict mapping entry ID to predictions

        Returns:
            AccuracyReport with all metrics
        """
        report = AccuracyReport(corpus_size=len(corpus))

        for entry in corpus:
            predictions = predictions_by_entry.get(entry.id, [])
            entry_metrics = self._evaluate_entry(entry, predictions)

            # Aggregate by entity type
            for entity_type, metrics in entry_metrics.items():
                if entity_type not in report.by_entity:
                    report.by_entity[entity_type] = EntityMetrics(entity_type)
                report.by_entity[entity_type] = report.by_entity[entity_type] + metrics

            # Aggregate by document type
            doc_type = entry.document_type.value
            if doc_type not in report.by_document_type:
                report.by_document_type[doc_type] = {}

            for entity_type, metrics in entry_metrics.items():
                if entity_type not in report.by_document_type[doc_type]:
                    report.by_document_type[doc_type][entity_type] = EntityMetrics(entity_type)
                report.by_document_type[doc_type][entity_type] = (
                    report.by_document_type[doc_type][entity_type] + metrics
                )

            report.total_annotations += len([a for a in entry.annotations if a.is_true_pii])
            report.total_predictions += len(predictions)

        # Calculate overall metrics
        for metrics in report.by_entity.values():
            report.overall = report.overall + metrics

        return report

    def _evaluate_entry(
        self,
        entry: "CorpusEntry",
        predictions: list[Prediction],
    ) -> dict[str, EntityMetrics]:
        """Evaluate predictions for a single entry."""
        metrics_by_type: dict[str, EntityMetrics] = {}

        # Get true PII annotations
        true_annotations = [a for a in entry.annotations if a.is_true_pii]
        # Get negative annotations (should NOT be detected)
        negative_annotations = [a for a in entry.annotations if not a.is_true_pii]

        # Track matched annotations and predictions
        matched_annotations: set[int] = set()
        matched_predictions: set[int] = set()

        # Match predictions to annotations
        for pred_idx, pred in enumerate(predictions):
            pred_type = self._normalize_type(pred.entity_type)
            matched = False

            for ann_idx, ann in enumerate(true_annotations):
                if ann_idx in matched_annotations:
                    continue

                ann_type = self._normalize_type(ann.entity_type)
                if pred_type != ann_type:
                    continue

                if self._matches(pred, ann):
                    # True positive
                    matched_annotations.add(ann_idx)
                    matched_predictions.add(pred_idx)
                    matched = True

                    if pred_type not in metrics_by_type:
                        metrics_by_type[pred_type] = EntityMetrics(pred_type)
                    metrics_by_type[pred_type].true_positives += 1
                    break

            if not matched:
                # Check if it's a negative annotation match (false positive on negative)
                is_negative_match = False
                for neg_ann in negative_annotations:
                    if self._matches(pred, neg_ann):
                        is_negative_match = True
                        break

                # False positive
                if pred_type not in metrics_by_type:
                    metrics_by_type[pred_type] = EntityMetrics(pred_type)
                metrics_by_type[pred_type].false_positives += 1

        # Find false negatives (missed annotations)
        for ann_idx, ann in enumerate(true_annotations):
            if ann_idx not in matched_annotations:
                ann_type = self._normalize_type(ann.entity_type)
                if ann_type not in metrics_by_type:
                    metrics_by_type[ann_type] = EntityMetrics(ann_type)
                metrics_by_type[ann_type].false_negatives += 1

        # True negatives (correctly not detecting negative annotations)
        for neg_ann in negative_annotations:
            neg_type = self._normalize_type(neg_ann.entity_type)
            matched_negative = False
            for pred in predictions:
                if self._matches(pred, neg_ann):
                    matched_negative = True
                    break

            if not matched_negative:
                if neg_type not in metrics_by_type:
                    metrics_by_type[neg_type] = EntityMetrics(neg_type)
                metrics_by_type[neg_type].true_negatives += 1

        return metrics_by_type

    def _matches(
        self,
        pred: Prediction,
        ann: "Annotation",
    ) -> bool:
        """Check if prediction matches annotation based on strategy."""
        if self._match_strategy == MatchStrategy.EXACT:
            return pred.start == ann.start and pred.end == ann.end

        elif self._match_strategy == MatchStrategy.OVERLAP:
            return self._has_overlap(pred, ann)

        elif self._match_strategy == MatchStrategy.PARTIAL:
            overlap = self._calculate_overlap(pred, ann)
            min_len = min(pred.length, ann.end - ann.start)
            return (overlap / min_len) >= self._overlap_threshold if min_len > 0 else False

        elif self._match_strategy == MatchStrategy.CONTAINED:
            return pred.start >= ann.start and pred.end <= ann.end

        return False

    def _has_overlap(self, pred: Prediction, ann: "Annotation") -> bool:
        """Check if prediction overlaps with annotation."""
        return not (pred.end <= ann.start or pred.start >= ann.end)

    def _calculate_overlap(self, pred: Prediction, ann: "Annotation") -> int:
        """Calculate overlap length between prediction and annotation."""
        start = max(pred.start, ann.start)
        end = min(pred.end, ann.end)
        return max(0, end - start)

    def _normalize_type(self, entity_type: str) -> str:
        """Normalize entity type for comparison."""
        if not self._normalize_types:
            return entity_type

        # Map common variations
        type_map = {
            "PERSON_NAME": "PERSON",
            "PER": "PERSON",
            "PHONE_NUMBER": "ID_PHONE",
            "PHONE": "ID_PHONE",
            "EMAIL": "EMAIL_ADDRESS",
            "NIK": "ID_NIK",
            "NPWP": "ID_NPWP",
            "KK": "ID_KK",
            "BPJS": "ID_BPJS",
        }

        upper = entity_type.upper()
        return type_map.get(upper, upper)


def calculate_metrics(
    corpus: list["CorpusEntry"],
    predictions_by_entry: dict[str, list[Prediction]],
    match_strategy: MatchStrategy = MatchStrategy.OVERLAP,
) -> AccuracyReport:
    """
    Calculate accuracy metrics for predictions against corpus.

    Convenience function wrapping AccuracyCalculator.

    Args:
        corpus: Annotated corpus entries
        predictions_by_entry: Predictions per entry ID
        match_strategy: Matching strategy

    Returns:
        AccuracyReport with all metrics
    """
    calculator = AccuracyCalculator(match_strategy=match_strategy)
    return calculator.evaluate_corpus(corpus, predictions_by_entry)


def format_metrics_table(report: AccuracyReport) -> str:
    """Format metrics as ASCII table."""
    return report.summary()


__all__ = [
    "MatchStrategy",
    "EntityMetrics",
    "AccuracyReport",
    "Prediction",
    "AccuracyCalculator",
    "calculate_metrics",
    "format_metrics_table",
]
