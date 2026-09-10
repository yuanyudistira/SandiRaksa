"""
Detection engine core.

Provides the main detection orchestration, coordinating
multiple recognizers and handling the detection pipeline.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from sandiraksa.detection.context import (
    DetectionConfig,
    DetectionContext,
    DetectionPhase,
    DetectionResult,
    TextSegment,
)
from sandiraksa.detection.entity_types import EntityType, get_entity_registry

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DetectionError(Exception):
    """Base exception for detection errors."""

    pass


class RecognizerError(DetectionError):
    """Error in a recognizer."""

    pass


@runtime_checkable
class Recognizer(Protocol):
    """Protocol for entity recognizers."""

    @property
    def name(self) -> str:
        """Unique name of the recognizer."""
        ...

    @property
    def supported_entities(self) -> list[str]:
        """List of entity types this recognizer can detect."""
        ...

    def analyze(
        self,
        text: str,
        entities: list[str],
    ) -> list[DetectionResult]:
        """
        Analyze text for entities.

        Args:
            text: The text to analyze.
            entities: List of entity types to look for.

        Returns:
            List of detection results.
        """
        ...


class BaseRecognizer(ABC):
    """Base class for recognizers."""

    def __init__(self, name: str, supported_entities: list[str]) -> None:
        self._name = name
        self._supported_entities = supported_entities

    @property
    def name(self) -> str:
        return self._name

    @property
    def supported_entities(self) -> list[str]:
        return self._supported_entities

    @abstractmethod
    def analyze(
        self,
        text: str,
        entities: list[str],
    ) -> list[DetectionResult]:
        """Analyze text for entities."""
        pass

    def _filter_entities(self, requested: list[str]) -> list[str]:
        """Filter requested entities to only those we support."""
        return [e for e in requested if e in self._supported_entities]


@dataclass
class RecognizerRegistry:
    """Registry of available recognizers."""

    _recognizers: dict[str, Recognizer] = field(default_factory=dict)
    _entity_to_recognizers: dict[str, list[str]] = field(default_factory=dict)

    def register(self, recognizer: Recognizer) -> None:
        """Register a recognizer."""
        self._recognizers[recognizer.name] = recognizer

        # Map entities to recognizers
        for entity in recognizer.supported_entities:
            if entity not in self._entity_to_recognizers:
                self._entity_to_recognizers[entity] = []
            if recognizer.name not in self._entity_to_recognizers[entity]:
                self._entity_to_recognizers[entity].append(recognizer.name)

        logger.debug(
            f"Registered recognizer '{recognizer.name}' "
            f"for entities: {recognizer.supported_entities}"
        )

    def unregister(self, name: str) -> None:
        """Unregister a recognizer."""
        if name in self._recognizers:
            recognizer = self._recognizers[name]

            # Remove from entity mapping
            for entity in recognizer.supported_entities:
                if entity in self._entity_to_recognizers:
                    self._entity_to_recognizers[entity] = [
                        r
                        for r in self._entity_to_recognizers[entity]
                        if r != name
                    ]

            del self._recognizers[name]

    def get(self, name: str) -> Recognizer | None:
        """Get a recognizer by name."""
        return self._recognizers.get(name)

    def get_for_entity(self, entity_type: str) -> list[Recognizer]:
        """Get all recognizers that support an entity type."""
        recognizer_names = self._entity_to_recognizers.get(entity_type, [])
        return [self._recognizers[name] for name in recognizer_names]

    def get_for_entities(self, entity_types: list[str]) -> list[Recognizer]:
        """Get all recognizers needed for a set of entity types."""
        needed: set[str] = set()
        for entity_type in entity_types:
            for name in self._entity_to_recognizers.get(entity_type, []):
                needed.add(name)
        return [self._recognizers[name] for name in needed]

    def all(self) -> list[Recognizer]:
        """Get all registered recognizers."""
        return list(self._recognizers.values())

    @property
    def supported_entities(self) -> set[str]:
        """Get all supported entity types."""
        return set(self._entity_to_recognizers.keys())


class DetectionEngine:
    """
    Main detection engine.

    Coordinates multiple recognizers to detect entities in text.
    """

    def __init__(self) -> None:
        self._registry = RecognizerRegistry()
        self._initialized = False

    @property
    def registry(self) -> RecognizerRegistry:
        """Get the recognizer registry."""
        return self._registry

    def initialize(self) -> None:
        """
        Initialize the engine.

        Subclasses should override to register recognizers.
        """
        self._initialized = True
        logger.info("Detection engine initialized")

    def shutdown(self) -> None:
        """Shutdown the engine and release resources."""
        self._initialized = False
        logger.info("Detection engine shutdown")

    def analyze_text(
        self,
        text: str,
        context: DetectionContext,
    ) -> list[DetectionResult]:
        """
        Analyze a text string for entities.

        Args:
            text: The text to analyze.
            context: Detection context with configuration.

        Returns:
            List of detection results.
        """
        if not self._initialized:
            raise DetectionError("Engine not initialized")

        if not text or not text.strip():
            return []

        # Get enabled entity types
        entities = list(context.config.enabled_entity_types)
        if not entities:
            logger.warning("No entity types enabled for detection")
            return []

        # Get recognizers for these entities
        recognizers = self._registry.get_for_entities(entities)
        if not recognizers:
            logger.warning(f"No recognizers found for entities: {entities}")
            return []

        # Run each recognizer
        all_results: list[DetectionResult] = []

        for recognizer in recognizers:
            try:
                # Filter to entities this recognizer supports
                recognizer_entities = [
                    e for e in entities if e in recognizer.supported_entities
                ]

                if not recognizer_entities:
                    continue

                results = recognizer.analyze(text, recognizer_entities)

                # Tag results with recognizer name
                for result in results:
                    result.recognizer_name = recognizer.name
                    all_results.append(result)

            except Exception as e:
                logger.error(f"Recognizer '{recognizer.name}' failed: {e}")
                context.stats.errors.append(
                    f"Recognizer '{recognizer.name}' failed: {str(e)}"
                )

        # Post-filter: remove false-positive PERSON detections
        all_results = self._filter_false_positives(all_results, text)

        return all_results

    def _filter_false_positives(
        self,
        results: list[DetectionResult],
        text: str = "",
    ) -> list[DetectionResult]:
        """Remove common false-positive PERSON detections and denied terms."""
        try:
            from sandiraksa.detection.recognizers.person_filter import (
                filter_person_detections,
            )

            results = filter_person_detections(results, text)
        except Exception as e:
            logger.warning(f"Person filter failed, returning unfiltered: {e}")

        # Global deny-list: drop ANY detection whose text is user-excluded.
        # Empty deny-list => no-op (nothing dropped).
        try:
            from sandiraksa.detection.deny_list import is_denied

            results = [r for r in results if not is_denied(r.text)]
        except Exception as e:
            logger.warning(f"Deny-list filter failed, skipping: {e}")

        return results

    def analyze_segment(
        self,
        segment: TextSegment,
        context: DetectionContext,
    ) -> list[DetectionResult]:
        """
        Analyze a text segment with location information.

        Args:
            segment: The text segment to analyze.
            context: Detection context.

        Returns:
            List of detection results with location info.
        """
        results = self.analyze_text(segment.text, context)

        # Update statistics
        context.stats.segments_processed += 1
        context.stats.total_characters += len(segment.text)

        # Attach location information
        import copy

        for result in results:
            # Create location from segment + result offsets
            location = copy.copy(segment.location)
            location.start_offset = segment.parent_offset + result.start
            location.end_offset = segment.parent_offset + result.end
            result.document_location = location

            # Add to context
            context.add_result(result)

        return results

    def process_document(
        self,
        segments: list[TextSegment],
        context: DetectionContext,
    ) -> DetectionContext:
        """
        Process a document's text segments.

        Args:
            segments: List of text segments from the document.
            context: Detection context.

        Returns:
            Updated context with results.
        """
        if not self._initialized:
            raise DetectionError("Engine not initialized")

        context.start()
        total = len(segments)

        try:
            for i, segment in enumerate(segments):
                # Check for max findings limit
                if len(context.results) >= context.config.max_findings_per_segment * total:
                    context.stats.warnings.append(
                        f"Maximum findings limit reached at segment {i}"
                    )
                    break

                # Analyze segment
                self.analyze_segment(segment, context)

                # Report progress
                context.report_progress(
                    i + 1,
                    total,
                    f"Scanning segment {i + 1}/{total}",
                )

            # Post-processing
            context.phase = DetectionPhase.POST_PROCESSING
            context.resolve_overlapping_results()
            context.convert_to_findings()

            context.complete()

        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            context.fail(str(e))
            raise DetectionError(f"Document processing failed: {e}") from e

        return context


# Global engine instance
_engine: DetectionEngine | None = None


def get_detection_engine() -> DetectionEngine:
    """Get the global detection engine instance."""
    global _engine
    if _engine is None:
        _engine = DetectionEngine()
    return _engine


def initialize_detection_engine() -> DetectionEngine:
    """Initialize and return the global detection engine."""
    engine = get_detection_engine()
    if not engine._initialized:
        engine.initialize()
    return engine
