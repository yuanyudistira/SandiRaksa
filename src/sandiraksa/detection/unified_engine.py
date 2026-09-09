"""
Unified Detection Engine Protocol and interfaces.

This module defines the Protocol interfaces for the unified detection
pipeline. The UnifiedDetectionEngine accepts LogicalSegments and returns
UnifiedFindings - bridging the document layer with the detection layer.

Architecture:
    DocumentAdapter → LogicalSegment → UnifiedDetectionEngine → UnifiedFinding

Key Interfaces:
    - UnifiedRecognizer: Protocol for all recognizers
    - UnifiedDetectionEngine: Protocol for the detection engine
    - DetectionConfig: Configuration for detection behavior
    - DetectionContext: Runtime context passed to recognizers
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sandiraksa.documents.logical_segment import LogicalSegment
    from sandiraksa.detection.unified_finding import UnifiedFinding


class DetectionMode(str, Enum):
    """Detection mode affecting sensitivity and performance."""

    STRICT = "strict"      # Highest sensitivity, may have false positives
    BALANCED = "balanced"  # Default, balanced precision/recall
    FAST = "fast"          # Lower sensitivity for large documents


@dataclass
class DetectionConfig:
    """
    Configuration for detection behavior.

    Attributes:
        entities: List of entity types to detect (None = all)
        mode: Detection mode (strict, balanced, fast)
        min_score: Minimum confidence score threshold
        use_context: Whether to use context for confidence boost
        max_findings_per_segment: Limit findings per segment
        custom_terms: Custom terms to always flag
        deny_list: Terms that should always be flagged as CRITICAL
        allow_list: Terms/patterns to ignore (reduce false positives)
        language: Primary language code
    """

    entities: list[str] | None = None  # None means all
    mode: DetectionMode = DetectionMode.BALANCED
    min_score: float = 0.4
    use_context: bool = True
    max_findings_per_segment: int = 100
    custom_terms: list[str] = field(default_factory=list)
    deny_list: list[str] = field(default_factory=list)
    allow_list: list[str] = field(default_factory=list)
    language: str = "id"

    def with_entities(self, entities: list[str]) -> "DetectionConfig":
        """Create a copy with specified entities."""
        return DetectionConfig(
            entities=entities,
            mode=self.mode,
            min_score=self.min_score,
            use_context=self.use_context,
            max_findings_per_segment=self.max_findings_per_segment,
            custom_terms=self.custom_terms.copy(),
            deny_list=self.deny_list.copy(),
            allow_list=self.allow_list.copy(),
            language=self.language,
        )

    def with_min_score(self, min_score: float) -> "DetectionConfig":
        """Create a copy with specified minimum score."""
        return DetectionConfig(
            entities=self.entities.copy() if self.entities else None,
            mode=self.mode,
            min_score=min_score,
            use_context=self.use_context,
            max_findings_per_segment=self.max_findings_per_segment,
            custom_terms=self.custom_terms.copy(),
            deny_list=self.deny_list.copy(),
            allow_list=self.allow_list.copy(),
            language=self.language,
        )


@dataclass
class DetectionContext:
    """
    Runtime context passed to recognizers.

    Contains information about the current detection run that
    recognizers may use to adjust their behavior.

    Attributes:
        segment: The LogicalSegment being analyzed
        config: Detection configuration
        file_type: File format being processed
        document_type: Detected document type if known
        hints: Additional hints from document analysis
    """

    segment: Any  # LogicalSegment (using Any to avoid circular import)
    config: DetectionConfig
    file_type: str = ""
    document_type: str | None = None
    hints: dict[str, Any] = field(default_factory=dict)

    @property
    def context_labels(self) -> list[str]:
        """Get all context labels from the segment."""
        return getattr(self.segment, "context_labels", [])

    @property
    def has_context(self) -> bool:
        """Check if segment has context information."""
        return getattr(self.segment, "has_context", False)

    def should_detect_entity(self, entity_type: str) -> bool:
        """Check if this entity type should be detected."""
        if self.config.entities is None:
            return True
        return entity_type in self.config.entities


@runtime_checkable
class UnifiedRecognizer(Protocol):
    """
    Protocol for unified recognizers.

    All recognizers in the unified pipeline implement this protocol.
    They receive LogicalSegments with context and return UnifiedFindings.
    """

    @property
    def name(self) -> str:
        """Unique name of the recognizer."""
        ...

    @property
    def supported_entities(self) -> list[str]:
        """List of entity types this recognizer can detect."""
        ...

    @property
    def priority(self) -> int:
        """
        Priority for overlap resolution.

        Higher priority recognizers' findings take precedence
        when overlapping with lower priority recognizers.
        Range: 0-100, default 50.
        """
        ...

    def analyze(
        self,
        segment: "LogicalSegment",
        context: DetectionContext,
    ) -> list["UnifiedFinding"]:
        """
        Analyze a LogicalSegment for entities.

        Args:
            segment: The LogicalSegment to analyze
            context: Runtime detection context

        Returns:
            List of UnifiedFinding objects
        """
        ...


class BaseUnifiedRecognizer(ABC):
    """
    Abstract base class for unified recognizers.

    Provides common functionality and enforces the Protocol.
    """

    def __init__(
        self,
        name: str,
        supported_entities: list[str],
        priority: int = 50,
    ) -> None:
        """
        Initialize the recognizer.

        Args:
            name: Unique name for this recognizer
            supported_entities: Entity types this recognizer handles
            priority: Priority for overlap resolution (0-100)
        """
        self._name = name
        self._supported_entities = supported_entities
        self._priority = max(0, min(100, priority))

    @property
    def name(self) -> str:
        """Unique name of the recognizer."""
        return self._name

    @property
    def supported_entities(self) -> list[str]:
        """List of entity types this recognizer can detect."""
        return self._supported_entities

    @property
    def priority(self) -> int:
        """Priority for overlap resolution."""
        return self._priority

    @abstractmethod
    def analyze(
        self,
        segment: "LogicalSegment",
        context: DetectionContext,
    ) -> list["UnifiedFinding"]:
        """Analyze a LogicalSegment for entities."""
        ...

    def _filter_entities(self, context: DetectionContext) -> list[str]:
        """Filter entities based on context configuration."""
        if context.config.entities is None:
            return self._supported_entities
        return [
            e for e in self._supported_entities
            if e in context.config.entities
        ]


@runtime_checkable
class UnifiedDetectionEngineProtocol(Protocol):
    """
    Protocol for the unified detection engine.

    The engine orchestrates multiple recognizers and produces
    findings from LogicalSegments.
    """

    def detect(
        self,
        segment: "LogicalSegment",
        config: DetectionConfig | None = None,
    ) -> list["UnifiedFinding"]:
        """
        Detect PII in a single segment.

        Args:
            segment: LogicalSegment to analyze
            config: Detection configuration (uses default if None)

        Returns:
            List of UnifiedFinding objects
        """
        ...

    def detect_batch(
        self,
        segments: list["LogicalSegment"],
        config: DetectionConfig | None = None,
    ) -> dict[str, list["UnifiedFinding"]]:
        """
        Detect PII in multiple segments.

        Args:
            segments: List of LogicalSegments to analyze
            config: Detection configuration

        Returns:
            Dict mapping segment IDs to their findings
        """
        ...

    def register_recognizer(self, recognizer: UnifiedRecognizer) -> None:
        """
        Register a recognizer with the engine.

        Args:
            recognizer: The recognizer to register
        """
        ...

    def get_supported_entities(self) -> set[str]:
        """
        Get all entity types supported by registered recognizers.

        Returns:
            Set of supported entity type names
        """
        ...


@dataclass
class RecognizerInfo:
    """Information about a registered recognizer."""

    name: str
    entities: list[str]
    priority: int
    enabled: bool = True


@dataclass
class EngineStatus:
    """Status information about the detection engine."""

    initialized: bool
    recognizer_count: int
    recognizers: list[RecognizerInfo]
    supported_entities: set[str]
    config: DetectionConfig


__all__ = [
    "BaseUnifiedRecognizer",
    "DetectionConfig",
    "DetectionContext",
    "DetectionMode",
    "EngineStatus",
    "RecognizerInfo",
    "UnifiedDetectionEngineProtocol",
    "UnifiedRecognizer",
]
