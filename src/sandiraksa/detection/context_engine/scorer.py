"""
Context Scorer for PII Detection.

This module provides unified context scoring by combining evidence
from all context types:
- Lexical: Keywords in text and labels
- Structural: Table headers, key-value labels
- Spatial: Position-based context (PowerPoint)
- Document: Document type hints

The scorer adjusts finding confidence based on context evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sandiraksa.detection.context_engine.lexical import (
    LexicalContext,
    LexicalContextAnalyzer,
    get_lexical_analyzer,
)
from sandiraksa.detection.context_engine.structural import (
    StructuralContext,
    StructuralContextExtractor,
    get_structural_extractor,
)
from sandiraksa.detection.context_engine.spatial import (
    SpatialContext,
    extract_spatial_context_from_segment,
)
from sandiraksa.detection.context_engine.document import (
    DocumentContext,
    DocumentContextDetector,
    get_document_detector,
)
from sandiraksa.detection.unified_finding import (
    ConfidenceEvidence,
    EvidenceType,
    UnifiedFinding,
    classify_confidence,
)

if TYPE_CHECKING:
    from sandiraksa.documents.logical_segment import LogicalSegment


@dataclass
class ContextScoringResult:
    """
    Result of context scoring for a finding.

    Attributes:
        original_score: Score before context adjustment
        adjusted_score: Score after context adjustment
        score_delta: Change in score
        lexical_evidence: Lexical context evidence
        structural_evidence: Structural context evidence
        spatial_evidence: Spatial context evidence
        document_evidence: Document-level evidence
        total_positive: Total positive evidence weight
        total_negative: Total negative evidence weight
    """

    original_score: float
    adjusted_score: float
    score_delta: float = 0.0
    lexical_evidence: list[ConfidenceEvidence] = field(default_factory=list)
    structural_evidence: list[ConfidenceEvidence] = field(default_factory=list)
    spatial_evidence: list[ConfidenceEvidence] = field(default_factory=list)
    document_evidence: list[ConfidenceEvidence] = field(default_factory=list)
    total_positive: float = 0.0
    total_negative: float = 0.0

    @property
    def all_evidence(self) -> list[ConfidenceEvidence]:
        """Get all evidence combined."""
        return (
            self.lexical_evidence +
            self.structural_evidence +
            self.spatial_evidence +
            self.document_evidence
        )


@dataclass
class ContextWeights:
    """
    Weight configuration for context scoring.

    Adjustable weights for each context type and evidence category.
    """

    # Context type weights
    lexical_weight: float = 1.0
    structural_weight: float = 1.2  # Structural is strong evidence
    spatial_weight: float = 0.8
    document_weight: float = 0.6

    # Evidence category weights
    positive_keyword_weight: float = 0.15
    negative_keyword_weight: float = 0.2  # Penalize more
    entity_hint_weight: float = 0.1
    key_label_weight: float = 0.2
    table_header_weight: float = 0.15
    document_type_weight: float = 0.1
    expected_entity_boost: float = 0.1
    unexpected_entity_penalty: float = 0.05

    # Score bounds
    min_score: float = 0.1
    max_score: float = 1.0
    max_boost: float = 0.3
    max_penalty: float = 0.4


class ContextScorer:
    """
    Unified context scorer for PII detection.

    Combines evidence from lexical, structural, spatial, and
    document context to adjust finding confidence scores.
    """

    def __init__(
        self,
        weights: ContextWeights | None = None,
        lexical_analyzer: LexicalContextAnalyzer | None = None,
        structural_extractor: StructuralContextExtractor | None = None,
        document_detector: DocumentContextDetector | None = None,
    ):
        """
        Initialize context scorer.

        Args:
            weights: Weight configuration
            lexical_analyzer: Lexical context analyzer
            structural_extractor: Structural context extractor
            document_detector: Document context detector
        """
        self.weights = weights or ContextWeights()
        self.lexical = lexical_analyzer or get_lexical_analyzer()
        self.structural = structural_extractor or get_structural_extractor()
        self.document = document_detector or get_document_detector()

    def score(
        self,
        segment: "LogicalSegment",
        findings: list[UnifiedFinding],
        document_context: DocumentContext | None = None,
    ) -> list[UnifiedFinding]:
        """
        Score findings with context evidence.

        Args:
            segment: LogicalSegment containing the findings
            findings: List of findings to score
            document_context: Optional pre-computed document context

        Returns:
            List of findings with adjusted scores and evidence
        """
        if not findings:
            return findings

        # Extract all context types
        lexical_ctx = self.lexical.analyze(segment)
        structural_ctx = self.structural.extract(segment)
        spatial_ctx = extract_spatial_context_from_segment(segment)
        doc_ctx = document_context or self._get_document_context(segment)

        # Score each finding
        scored_findings = []
        for finding in findings:
            result = self._score_finding(
                finding=finding,
                lexical_ctx=lexical_ctx,
                structural_ctx=structural_ctx,
                spatial_ctx=spatial_ctx,
                document_ctx=doc_ctx,
            )

            # Apply adjusted score
            finding.raw_score = result.adjusted_score
            finding.confidence_band = classify_confidence(result.adjusted_score)

            # Add evidence
            for evidence in result.all_evidence:
                finding.add_evidence(evidence)

            scored_findings.append(finding)

        return scored_findings

    def _get_document_context(
        self,
        segment: "LogicalSegment",
    ) -> DocumentContext:
        """Get document context from segment."""
        return self.document.detect_from_segment(segment)

    def _score_finding(
        self,
        finding: UnifiedFinding,
        lexical_ctx: LexicalContext,
        structural_ctx: StructuralContext,
        spatial_ctx: SpatialContext,
        document_ctx: DocumentContext,
    ) -> ContextScoringResult:
        """
        Score a single finding with all context types.

        Args:
            finding: The finding to score
            lexical_ctx: Lexical context
            structural_ctx: Structural context
            spatial_ctx: Spatial context
            document_ctx: Document context

        Returns:
            ContextScoringResult with adjusted score and evidence
        """
        result = ContextScoringResult(
            original_score=finding.raw_score,
            adjusted_score=finding.raw_score,
        )

        # Score lexical context
        self._score_lexical(finding, lexical_ctx, result)

        # Score structural context
        self._score_structural(finding, structural_ctx, result)

        # Score spatial context
        self._score_spatial(finding, spatial_ctx, result)

        # Score document context
        self._score_document(finding, document_ctx, result)

        # Calculate final adjusted score
        delta = result.total_positive - result.total_negative
        delta = max(-self.weights.max_penalty, min(self.weights.max_boost, delta))

        result.adjusted_score = finding.raw_score + delta
        result.adjusted_score = max(
            self.weights.min_score,
            min(self.weights.max_score, result.adjusted_score),
        )
        result.score_delta = result.adjusted_score - result.original_score

        return result

    def _score_lexical(
        self,
        finding: UnifiedFinding,
        ctx: LexicalContext,
        result: ContextScoringResult,
    ) -> None:
        """Score lexical context evidence."""
        w = self.weights

        # Positive keywords
        if ctx.positive_matches:
            for match in ctx.positive_matches:
                weight = match.weight * w.positive_keyword_weight * w.lexical_weight
                result.total_positive += weight
                result.lexical_evidence.append(
                    ConfidenceEvidence(
                        evidence_type=EvidenceType.CONTEXT_POSITIVE,
                        source="lexical_context",
                        weight=weight,
                        reason_code="positive_keyword",
                        description=f"Positive keyword: '{match.keyword}'",
                    )
                )

        # Negative keywords
        if ctx.negative_matches:
            for match in ctx.negative_matches:
                weight = match.weight * w.negative_keyword_weight * w.lexical_weight
                result.total_negative += weight
                result.lexical_evidence.append(
                    ConfidenceEvidence(
                        evidence_type=EvidenceType.CONTEXT_NEGATIVE,
                        source="lexical_context",
                        weight=-weight,
                        reason_code="negative_keyword",
                        description=f"Negative keyword: '{match.keyword}'",
                    )
                )

        # Entity-specific hints
        entity_hint_weight = ctx.entity_hints.get(finding.entity_type, 0.0)
        if entity_hint_weight > 0:
            weight = entity_hint_weight * w.entity_hint_weight * w.lexical_weight
            result.total_positive += weight
            result.lexical_evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.CONTEXT_POSITIVE,
                    source="lexical_context",
                    weight=weight,
                    reason_code="entity_hint",
                    description=f"Entity keyword hint for {finding.entity_type}",
                )
            )

    def _score_structural(
        self,
        finding: UnifiedFinding,
        ctx: StructuralContext,
        result: ContextScoringResult,
    ) -> None:
        """Score structural context evidence."""
        w = self.weights

        if not ctx.items:
            return

        # Get primary context
        primary = ctx.primary_context
        if primary:
            # Key label is strongest structural evidence
            if primary.context_type.value == "key_label":
                weight = w.key_label_weight * w.structural_weight
                result.total_positive += weight
                result.structural_evidence.append(
                    ConfidenceEvidence(
                        evidence_type=EvidenceType.CONTEXT_POSITIVE,
                        source="structural_context",
                        weight=weight,
                        reason_code="key_label",
                        description=f"Key label: '{primary.text}'",
                    )
                )
            # Table header
            elif primary.context_type.value in ("table_header", "row_header"):
                weight = w.table_header_weight * w.structural_weight
                result.total_positive += weight
                result.structural_evidence.append(
                    ConfidenceEvidence(
                        evidence_type=EvidenceType.CONTEXT_POSITIVE,
                        source="structural_context",
                        weight=weight,
                        reason_code="table_header",
                        description=f"Table header: '{primary.text}'",
                    )
                )
            # Other structural context
            else:
                weight = primary.weight * w.structural_weight * 0.5
                result.total_positive += weight
                result.structural_evidence.append(
                    ConfidenceEvidence(
                        evidence_type=EvidenceType.CONTEXT_POSITIVE,
                        source="structural_context",
                        weight=weight,
                        reason_code=primary.context_type.value,
                        description=f"Structural context: '{primary.text}'",
                    )
                )

    def _score_spatial(
        self,
        finding: UnifiedFinding,
        ctx: SpatialContext,
        result: ContextScoringResult,
    ) -> None:
        """Score spatial context evidence."""
        w = self.weights

        if not ctx.nearby_labels:
            return

        # Best label
        best_label = ctx.get_best_label()
        if best_label:
            weight = 0.15 * w.spatial_weight
            result.total_positive += weight
            result.spatial_evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.CONTEXT_POSITIVE,
                    source="spatial_context",
                    weight=weight,
                    reason_code="nearby_label",
                    description=f"Nearby label: '{best_label.text}'",
                )
            )

        # Slide title context
        if ctx.slide_title:
            weight = 0.1 * w.spatial_weight
            result.total_positive += weight
            result.spatial_evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.CONTEXT_POSITIVE,
                    source="spatial_context",
                    weight=weight,
                    reason_code="slide_title",
                    description=f"Slide title: '{ctx.slide_title}'",
                )
            )

    def _score_document(
        self,
        finding: UnifiedFinding,
        ctx: DocumentContext,
        result: ContextScoringResult,
    ) -> None:
        """Score document-level context evidence."""
        w = self.weights

        # Document type confidence
        if ctx.confidence > 0.3:
            weight = ctx.confidence * w.document_type_weight * w.document_weight
            result.total_positive += weight
            result.document_evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.CONTEXT_POSITIVE,
                    source="document_context",
                    weight=weight,
                    reason_code="document_type",
                    description=f"Document type: {ctx.detected_type.value}",
                )
            )

        # Expected entity boost
        if ctx.expects_entity(finding.entity_type):
            if ctx.expected_entities:  # Only if document has expectations
                weight = w.expected_entity_boost * w.document_weight
                result.total_positive += weight
                result.document_evidence.append(
                    ConfidenceEvidence(
                        evidence_type=EvidenceType.CONTEXT_POSITIVE,
                        source="document_context",
                        weight=weight,
                        reason_code="expected_entity",
                        description=f"{finding.entity_type} expected in {ctx.detected_type.value}",
                    )
                )
        elif ctx.expected_entities:  # Has expectations but entity not expected
            weight = w.unexpected_entity_penalty * w.document_weight
            result.total_negative += weight
            result.document_evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.CONTEXT_NEGATIVE,
                    source="document_context",
                    weight=-weight,
                    reason_code="unexpected_entity",
                    description=f"{finding.entity_type} not typical for {ctx.detected_type.value}",
                )
            )

        # High sensitivity document boost
        if ctx.is_high_sensitivity():
            weight = 0.05 * w.document_weight
            result.total_positive += weight
            result.document_evidence.append(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.CONTEXT_POSITIVE,
                    source="document_context",
                    weight=weight,
                    reason_code="high_sensitivity",
                    description=f"High sensitivity document ({ctx.sensitivity})",
                )
            )


# =============================================================================
# Module-level functions
# =============================================================================

_default_scorer: ContextScorer | None = None


def get_context_scorer() -> ContextScorer:
    """Get the default context scorer instance."""
    global _default_scorer
    if _default_scorer is None:
        _default_scorer = ContextScorer()
    return _default_scorer


def score_findings_with_context(
    segment: "LogicalSegment",
    findings: list[UnifiedFinding],
    document_context: DocumentContext | None = None,
) -> list[UnifiedFinding]:
    """
    Convenience function to score findings with context.

    Args:
        segment: LogicalSegment containing the findings
        findings: List of findings to score
        document_context: Optional pre-computed document context

    Returns:
        List of findings with adjusted scores and evidence
    """
    return get_context_scorer().score(segment, findings, document_context)


__all__ = [
    "ContextScoringResult",
    "ContextWeights",
    "ContextScorer",
    "get_context_scorer",
    "score_findings_with_context",
]
