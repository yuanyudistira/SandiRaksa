"""
Indonesian NER Recognizer.

Presidio-compatible recognizer that uses local NER models for
detecting Indonesian PERSON, ORG, and LOC entities.

This bridges the NER module with the existing Presidio-based
detection engine.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sandiraksa.detection.context import DetectionResult
from sandiraksa.detection.engine import BaseRecognizer
from sandiraksa.detection.ner.base import NERConfig, NERPrediction
from sandiraksa.detection.ner.loader import is_ner_available, get_ner_model

if TYPE_CHECKING:
    from sandiraksa.detection.ner.base import NERProvider

logger = logging.getLogger(__name__)


# Map NER entity types to Presidio/SandiRaksa entity types
NER_TO_PRESIDIO_ENTITY = {
    "PERSON": "PERSON",
    "PER": "PERSON",
    "ORG": "ORGANIZATION",
    "ORGANIZATION": "ORGANIZATION",
    "LOC": "LOCATION",
    "LOCATION": "LOCATION",
    "GPE": "LOCATION",  # Geo-political entity
}

# Supported entities by this recognizer
SUPPORTED_ENTITIES = ["PERSON", "ORGANIZATION", "LOCATION"]


class IndonesianNERRecognizer(BaseRecognizer):
    """
    Recognizer for Indonesian named entities using local NER.

    Detects:
    - PERSON: Indonesian names (Javanese, Sundanese, Batak, etc.)
    - ORGANIZATION: Companies, institutions (PT, CV, etc.)
    - LOCATION: Places, addresses

    Uses ONNX-based NER model for privacy-preserving local inference.

    Usage:
        recognizer = IndonesianNERRecognizer()
        results = recognizer.analyze("Budi Santoso bekerja di PT Maju Jaya")
    """

    def __init__(
        self,
        min_score: float = 0.6,
        enabled_entities: set[str] | None = None,
        lazy_load: bool = True,
    ):
        """
        Initialize Indonesian NER recognizer.

        Args:
            min_score: Minimum confidence threshold (0.0-1.0)
            enabled_entities: Entity types to detect (default: all)
            lazy_load: If True, load model on first use
        """
        super().__init__(
            name="indonesian_ner",
            supported_entities=SUPPORTED_ENTITIES,
        )

        self._min_score = min_score
        self._enabled_entities = enabled_entities or set(SUPPORTED_ENTITIES)
        self._lazy_load = lazy_load

        # NER provider (loaded lazily)
        self._provider: "NERProvider | None" = None
        self._available: bool | None = None

        # Config for NER inference
        self._ner_config = NERConfig(
            min_score=min_score,
            enabled_entities=self._map_entities_to_ner(self._enabled_entities),
        )

        # Load immediately if not lazy
        if not lazy_load:
            self._ensure_loaded()

    def _map_entities_to_ner(self, entities: set[str]) -> set[str]:
        """Map Presidio entity types to NER entity types."""
        ner_entities = set()
        for entity in entities:
            if entity == "PERSON":
                ner_entities.add("PERSON")
            elif entity == "ORGANIZATION":
                ner_entities.add("ORG")
            elif entity == "LOCATION":
                ner_entities.update(["LOC", "GPE"])
        return ner_entities

    def is_available(self) -> bool:
        """Check if NER model is available."""
        if self._available is None:
            self._available = is_ner_available()
        return self._available

    def _ensure_loaded(self) -> bool:
        """Ensure NER model is loaded."""
        if self._provider is not None:
            return True

        if not self.is_available():
            logger.debug("Indonesian NER model not available")
            return False

        try:
            self._provider = get_ner_model()
            return True
        except Exception as e:
            logger.warning(f"Failed to load Indonesian NER model: {e}")
            self._available = False
            return False

    def analyze(
        self,
        text: str,
        entities: list[str],
    ) -> list[DetectionResult]:
        """
        Analyze text for Indonesian named entities.

        Args:
            text: Text to analyze
            entities: Entity types to look for

        Returns:
            List of DetectionResult for found entities
        """
        # Filter to supported entities
        target_entities = set(entities) & self._enabled_entities
        if not target_entities:
            return []

        # Ensure model is loaded
        if not self._ensure_loaded():
            return []

        # Run NER
        try:
            result = self._provider.predict_single(text, self._ner_config)
        except Exception as e:
            logger.error(f"NER prediction failed: {e}")
            return []

        # Convert NER predictions to DetectionResult
        detections = []
        for pred in result.predictions:
            presidio_type = NER_TO_PRESIDIO_ENTITY.get(pred.entity_type)

            if presidio_type is None:
                continue

            if presidio_type not in target_entities:
                continue

            detection = DetectionResult(
                entity_type=presidio_type,
                text=pred.text,
                start=pred.start,
                end=pred.end,
                score=pred.score,
                recognizer_name=self.name,
            )
            detections.append(detection)

        return detections

    def analyze_batch(
        self,
        texts: list[str],
        entities: list[str],
    ) -> list[list[DetectionResult]]:
        """
        Analyze multiple texts efficiently.

        Args:
            texts: List of texts to analyze
            entities: Entity types to look for

        Returns:
            List of detection results per text
        """
        # Filter to supported entities
        target_entities = set(entities) & self._enabled_entities
        if not target_entities:
            return [[] for _ in texts]

        # Ensure model is loaded
        if not self._ensure_loaded():
            return [[] for _ in texts]

        # Run batch NER
        try:
            results = self._provider.predict(texts, self._ner_config)
        except Exception as e:
            logger.error(f"NER batch prediction failed: {e}")
            return [[] for _ in texts]

        # Convert each result
        all_detections = []
        for result in results:
            detections = []
            for pred in result.predictions:
                presidio_type = NER_TO_PRESIDIO_ENTITY.get(pred.entity_type)

                if presidio_type is None:
                    continue

                if presidio_type not in target_entities:
                    continue

                detection = DetectionResult(
                    entity_type=presidio_type,
                    text=pred.text,
                    start=pred.start,
                    end=pred.end,
                    score=pred.score,
                    recognizer_name=self.name,
                )
                detections.append(detection)

            all_detections.append(detections)

        return all_detections


class MockIndonesianNERRecognizer(BaseRecognizer):
    """
    Mock Indonesian NER recognizer for testing.

    Returns predefined detections without actual NER inference.
    """

    def __init__(
        self,
        detections_map: dict[str, list[DetectionResult]] | None = None,
    ):
        """
        Initialize mock recognizer.

        Args:
            detections_map: Map of text -> detections for testing
        """
        super().__init__(
            name="mock_indonesian_ner",
            supported_entities=SUPPORTED_ENTITIES,
        )
        self._detections_map = detections_map or {}

    def is_available(self) -> bool:
        return True

    def analyze(
        self,
        text: str,
        entities: list[str],
    ) -> list[DetectionResult]:
        """Return mock detections."""
        all_detections = self._detections_map.get(text, [])
        return [d for d in all_detections if d.entity_type in entities]

    def add_detection(
        self,
        text: str,
        entity_type: str,
        entity_text: str,
        start: int,
        end: int,
        score: float = 0.9,
    ) -> None:
        """Add a mock detection for testing."""
        if text not in self._detections_map:
            self._detections_map[text] = []

        self._detections_map[text].append(
            DetectionResult(
                entity_type=entity_type,
                text=entity_text,
                start=start,
                end=end,
                score=score,
                recognizer_name=self.name,
            )
        )


def create_indonesian_ner_recognizer(
    min_score: float = 0.6,
    lazy_load: bool = True,
) -> IndonesianNERRecognizer | None:
    """
    Factory function to create Indonesian NER recognizer.

    Returns None if NER model is not available, allowing graceful
    degradation when model is not installed.

    Args:
        min_score: Minimum confidence threshold
        lazy_load: If True, defer model loading

    Returns:
        IndonesianNERRecognizer or None if unavailable
    """
    if not lazy_load and not is_ner_available():
        logger.info(
            "Indonesian NER model not available. "
            "PERSON/ORG/LOC detection will be limited to rule-based methods."
        )
        return None

    return IndonesianNERRecognizer(
        min_score=min_score,
        lazy_load=lazy_load,
    )


__all__ = [
    "IndonesianNERRecognizer",
    "MockIndonesianNERRecognizer",
    "create_indonesian_ner_recognizer",
    "NER_TO_PRESIDIO_ENTITY",
    "SUPPORTED_ENTITIES",
]
