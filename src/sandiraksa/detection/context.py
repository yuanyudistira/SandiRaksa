"""
Detection context management.

Provides context for detection operations including:
- Document metadata
- Detection configuration
- Results accumulation
- Progress tracking
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from sandiraksa.detection.entity_types import EntityType, get_entity_registry
from sandiraksa.domain.finding import (
    ConfidenceBand,
    DocumentLocation,
    Finding,
    ReviewAction,
)
from sandiraksa.domain.policy import ProtectionPolicy

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DetectionPhase(str, Enum):
    """Phases of detection processing."""

    INITIALIZING = "initializing"
    SCANNING = "scanning"
    POST_PROCESSING = "post_processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DetectionResult:
    """A single detection result from an analyzer."""

    entity_type: str
    start: int  # Start offset in text
    end: int  # End offset in text
    text: str  # The detected text
    score: float  # Confidence score (0.0-1.0)

    # Additional metadata
    recognizer_name: str = ""
    analysis_explanation: dict[str, Any] = field(default_factory=dict)

    # Location within document (set during processing)
    document_location: DocumentLocation | None = None

    @property
    def length(self) -> int:
        """Length of detected text."""
        return self.end - self.start

    @property
    def confidence_band(self) -> ConfidenceBand:
        """Map score to confidence band."""
        if self.score >= 0.9:
            return ConfidenceBand.HIGH
        elif self.score >= 0.7:
            return ConfidenceBand.MEDIUM
        else:
            return ConfidenceBand.LOW

    def overlaps_with(self, other: DetectionResult) -> bool:
        """Check if this result overlaps with another."""
        return not (self.end <= other.start or self.start >= other.end)

    def contains(self, other: DetectionResult) -> bool:
        """Check if this result fully contains another."""
        return self.start <= other.start and self.end >= other.end

    def to_finding(
        self,
        file_id: str,
        operation_id: str,
        location: DocumentLocation,
    ) -> Finding:
        """Convert to a Finding domain object."""
        return Finding(
            id=str(uuid4()),
            file_id=file_id,
            entity_type=self.entity_type,
            detector=self.recognizer_name or "unknown",
            detected_text=self.text,
            score=self.score,
            confidence_band=self.confidence_band.value,
            location=location.to_dict() if hasattr(location, "to_dict") else location,
            review_action=ReviewAction.PENDING,
        )


@dataclass
class TextSegment:
    """A segment of text to be analyzed."""

    text: str
    location: DocumentLocation
    segment_id: str = field(default_factory=lambda: str(uuid4()))

    # Offset mapping for nested segments
    parent_offset: int = 0

    def __len__(self) -> int:
        return len(self.text)


@dataclass
class DetectionConfig:
    """Configuration for a detection operation."""

    # Entity types to detect
    enabled_entity_types: set[str] = field(default_factory=set)

    # Minimum confidence threshold
    min_confidence: float = 0.5

    # Whether to use context enhancement
    use_context: bool = True

    # Maximum findings per segment (to prevent explosion)
    max_findings_per_segment: int = 1000

    # Whether to resolve overlapping findings
    resolve_overlaps: bool = True

    # Allow list patterns (skip these matches)
    allow_patterns: list[str] = field(default_factory=list)

    # Custom term patterns (exact match)
    custom_terms: list[str] = field(default_factory=list)

    @classmethod
    def from_policy(cls, policy: ProtectionPolicy) -> DetectionConfig:
        """Create config from a protection policy."""
        config = cls()

        # Enable entity types from policy
        for entity_config in policy.entity_configs:
            if entity_config.enabled:
                config.enabled_entity_types.add(entity_config.entity_type)
                # Use lowest min_confidence among enabled types
                if entity_config.min_confidence < config.min_confidence:
                    config.min_confidence = entity_config.min_confidence

        # Add allow patterns
        for rule in policy.allow_rules:
            if rule.pattern:
                config.allow_patterns.append(rule.pattern)

        # Add custom terms
        for rule in policy.custom_rules:
            if rule.enabled:
                config.custom_terms.append(rule.pattern)

        return config

    @classmethod
    def default(cls) -> DetectionConfig:
        """Create default configuration."""
        registry = get_entity_registry()
        enabled = {t.name for t in registry.enabled_by_default()}
        return cls(enabled_entity_types=enabled)


@dataclass
class DetectionStats:
    """Statistics for a detection operation."""

    segments_processed: int = 0
    total_characters: int = 0
    total_findings: int = 0
    findings_by_type: dict[str, int] = field(default_factory=dict)
    findings_by_confidence: dict[str, int] = field(default_factory=dict)

    processing_time_ms: float = 0.0
    start_time: datetime | None = None
    end_time: datetime | None = None

    # Error tracking
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def record_finding(self, result: DetectionResult) -> None:
        """Record a finding in statistics."""
        self.total_findings += 1

        # By type
        if result.entity_type not in self.findings_by_type:
            self.findings_by_type[result.entity_type] = 0
        self.findings_by_type[result.entity_type] += 1

        # By confidence
        band = result.confidence_band.value
        if band not in self.findings_by_confidence:
            self.findings_by_confidence[band] = 0
        self.findings_by_confidence[band] += 1

    def start(self) -> None:
        """Mark the start of processing."""
        self.start_time = datetime.utcnow()

    def finish(self) -> None:
        """Mark the end of processing."""
        self.end_time = datetime.utcnow()
        if self.start_time:
            delta = self.end_time - self.start_time
            self.processing_time_ms = delta.total_seconds() * 1000


ProgressCallback = Callable[[int, int, str], None]


@dataclass
class DetectionContext:
    """
    Context for a detection operation.

    Maintains state across multiple text segments and
    provides access to configuration, results, and progress.
    """

    # Identifiers
    operation_id: str
    file_id: str
    project_id: str

    # Configuration
    config: DetectionConfig = field(default_factory=DetectionConfig.default)

    # State
    phase: DetectionPhase = DetectionPhase.INITIALIZING
    results: list[DetectionResult] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    # Statistics
    stats: DetectionStats = field(default_factory=DetectionStats)

    # Progress callback
    _progress_callback: ProgressCallback | None = None
    _current_progress: int = 0
    _total_progress: int = 100

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        """Set a callback for progress updates."""
        self._progress_callback = callback

    def report_progress(self, current: int, total: int, message: str = "") -> None:
        """Report progress to callback."""
        self._current_progress = current
        self._total_progress = total
        if self._progress_callback:
            try:
                self._progress_callback(current, total, message)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    def add_result(self, result: DetectionResult) -> None:
        """Add a detection result."""
        # Check confidence threshold
        if result.score < self.config.min_confidence:
            return

        # Check if entity type is enabled
        if result.entity_type not in self.config.enabled_entity_types:
            return

        # Check allow patterns
        if self._matches_allow_pattern(result.text):
            logger.debug(f"Skipping allowed value: {result.text[:20]}...")
            return

        self.results.append(result)
        self.stats.record_finding(result)

    def _matches_allow_pattern(self, text: str) -> bool:
        """Check if text matches any allow pattern."""
        import re

        text_lower = text.lower()
        for pattern in self.config.allow_patterns:
            try:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    return True
            except re.error:
                # Invalid pattern, skip
                pass
        return False

    def resolve_overlapping_results(self) -> None:
        """
        Resolve overlapping detection results.

        Strategy:
        1. Higher confidence wins
        2. If same confidence, longer span wins
        3. If same length, first result wins
        """
        if not self.config.resolve_overlaps or len(self.results) < 2:
            return

        # Sort by start position
        sorted_results = sorted(self.results, key=lambda r: (r.start, -r.end))
        resolved: list[DetectionResult] = []

        for result in sorted_results:
            # Check if this result overlaps with any resolved result
            overlaps = False
            for existing in resolved:
                if result.overlaps_with(existing):
                    # Decide which to keep
                    if self._should_replace(existing, result):
                        resolved.remove(existing)
                        resolved.append(result)
                    overlaps = True
                    break

            if not overlaps:
                resolved.append(result)

        removed = len(self.results) - len(resolved)
        if removed > 0:
            logger.debug(f"Resolved {removed} overlapping results")

        self.results = resolved

    def _should_replace(
        self, existing: DetectionResult, new: DetectionResult
    ) -> bool:
        """Determine if new result should replace existing."""
        # Higher confidence wins
        if new.score > existing.score + 0.05:  # 5% margin
            return True
        if existing.score > new.score + 0.05:
            return False

        # Longer span wins
        if new.length > existing.length:
            return True
        if existing.length > new.length:
            return False

        # First result wins (existing stays)
        return False

    def convert_to_findings(self) -> list[Finding]:
        """Convert all results to Finding domain objects."""
        self.findings = []

        for result in self.results:
            if result.document_location is None:
                # Create a basic location if not set
                location = DocumentLocation(
                    element_type="text",
                    element_id="",
                    start_offset=result.start,
                    end_offset=result.end,
                )
            else:
                location = result.document_location

            finding = result.to_finding(
                file_id=self.file_id,
                operation_id=self.operation_id,
                location=location,
            )
            self.findings.append(finding)

        return self.findings

    def start(self) -> None:
        """Start the detection operation."""
        self.phase = DetectionPhase.SCANNING
        self.stats.start()

    def complete(self) -> None:
        """Mark detection as complete."""
        self.phase = DetectionPhase.COMPLETED
        self.stats.finish()

    def fail(self, error: str) -> None:
        """Mark detection as failed."""
        self.phase = DetectionPhase.FAILED
        self.stats.errors.append(error)
        self.stats.finish()


def create_detection_context(
    operation_id: str,
    file_id: str,
    project_id: str,
    policy: ProtectionPolicy | None = None,
) -> DetectionContext:
    """
    Factory function to create a detection context.

    Args:
        operation_id: The operation ID.
        file_id: The file being processed.
        project_id: The project ID.
        policy: Optional protection policy for configuration.

    Returns:
        Configured DetectionContext.
    """
    if policy:
        config = DetectionConfig.from_policy(policy)
    else:
        config = DetectionConfig.default()

    return DetectionContext(
        operation_id=operation_id,
        file_id=file_id,
        project_id=project_id,
        config=config,
    )
