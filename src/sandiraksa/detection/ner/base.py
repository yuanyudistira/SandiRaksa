"""
NER Provider Protocol and Base Types.

Defines the protocol interface for NER providers and common data types
used across the NER module.

Entity Types Supported:
- PERSON: Indonesian names (Javanese, Sundanese, Batak, etc.)
- ORG: Organizations, companies (PT, CV, etc.)
- LOC: Locations, addresses
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class NEREntityType(str, Enum):
    """Entity types detected by NER models."""

    PERSON = "PERSON"       # Person names
    ORG = "ORG"             # Organizations
    LOC = "LOC"             # Locations
    MISC = "MISC"           # Miscellaneous entities

    # Additional types for compatibility
    PER = "PER"             # Alias for PERSON (some models)
    GPE = "GPE"             # Geo-Political Entity (alias for LOC)
    NORP = "NORP"           # Nationalities, religions, political groups

    @classmethod
    def normalize(cls, entity_type: str) -> str:
        """
        Normalize entity type to standard form.

        Args:
            entity_type: Raw entity type from model

        Returns:
            Normalized entity type string
        """
        # Map aliases to standard types
        aliases = {
            "PER": "PERSON",
            "GPE": "LOC",
            "LOCATION": "LOC",
            "ORGANIZATION": "ORG",
            "B-PER": "PERSON",
            "I-PER": "PERSON",
            "B-ORG": "ORG",
            "I-ORG": "ORG",
            "B-LOC": "LOC",
            "I-LOC": "LOC",
            "B-MISC": "MISC",
            "I-MISC": "MISC",
        }

        # Remove BIO prefix if present
        clean = entity_type.upper()
        if clean.startswith("B-") or clean.startswith("I-"):
            clean = clean[2:]

        return aliases.get(clean, clean)


@dataclass
class NERPrediction:
    """
    A single NER prediction.

    Attributes:
        start: Start character offset in text
        end: End character offset in text
        text: The extracted entity text
        entity_type: Type of entity (PERSON, ORG, LOC, etc.)
        score: Confidence score (0.0-1.0)
        source: Name of the model/provider
    """

    start: int
    end: int
    text: str
    entity_type: str
    score: float
    source: str = "ner"

    def __post_init__(self):
        """Normalize entity type after initialization."""
        self.entity_type = NEREntityType.normalize(self.entity_type)

    @property
    def length(self) -> int:
        """Length of the entity span."""
        return self.end - self.start

    def overlaps_with(self, other: "NERPrediction") -> bool:
        """Check if this prediction overlaps with another."""
        return not (self.end <= other.start or self.start >= other.end)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "entity_type": self.entity_type,
            "score": self.score,
            "source": self.source,
        }


@dataclass
class NERConfig:
    """
    Configuration for NER inference.

    Attributes:
        min_score: Minimum confidence threshold
        enabled_entities: Entity types to detect (None = all)
        max_length: Maximum text length to process
        use_context: Whether to use surrounding context
        batch_size: Batch size for inference
    """

    min_score: float = 0.5
    enabled_entities: set[str] | None = None
    max_length: int = 512
    use_context: bool = True
    batch_size: int = 32

    def should_detect(self, entity_type: str) -> bool:
        """Check if entity type should be detected."""
        if self.enabled_entities is None:
            return True
        return entity_type in self.enabled_entities


@dataclass
class NERResult:
    """
    Result from NER inference on a single text.

    Attributes:
        text: Original input text
        predictions: List of NER predictions
        processing_time_ms: Time taken for inference
        model_name: Name of the model used
    """

    text: str
    predictions: list[NERPrediction] = field(default_factory=list)
    processing_time_ms: float = 0.0
    model_name: str = ""

    @property
    def entity_count(self) -> int:
        """Total number of entities detected."""
        return len(self.predictions)

    def get_entities_by_type(self, entity_type: str) -> list[NERPrediction]:
        """Get predictions of a specific type."""
        return [p for p in self.predictions if p.entity_type == entity_type]

    def get_persons(self) -> list[NERPrediction]:
        """Get PERSON entities."""
        return self.get_entities_by_type("PERSON")

    def get_organizations(self) -> list[NERPrediction]:
        """Get ORG entities."""
        return self.get_entities_by_type("ORG")

    def get_locations(self) -> list[NERPrediction]:
        """Get LOC entities."""
        return self.get_entities_by_type("LOC")


@runtime_checkable
class NERProvider(Protocol):
    """
    Protocol for NER providers.

    All NER implementations (ONNX, Transformers, etc.) should
    implement this protocol for interoperability.
    """

    @property
    def name(self) -> str:
        """Name of the NER provider."""
        ...

    @property
    def supported_entities(self) -> list[str]:
        """List of entity types this provider can detect."""
        ...

    @property
    def is_loaded(self) -> bool:
        """Whether the model is currently loaded."""
        ...

    def load(self) -> None:
        """
        Load the model into memory.

        Should be called before predict() for better performance.
        Can be called multiple times safely (idempotent).
        """
        ...

    def unload(self) -> None:
        """
        Unload the model from memory.

        Frees resources. Model will be reloaded on next predict().
        """
        ...

    def predict(
        self,
        texts: list[str],
        config: NERConfig | None = None,
    ) -> list[NERResult]:
        """
        Perform NER on a list of texts.

        Args:
            texts: List of text strings to analyze
            config: Optional configuration

        Returns:
            List of NERResult, one per input text
        """
        ...

    def predict_single(
        self,
        text: str,
        config: NERConfig | None = None,
    ) -> NERResult:
        """
        Perform NER on a single text.

        Args:
            text: Text string to analyze
            config: Optional configuration

        Returns:
            NERResult for the input text
        """
        ...


class BaseNERProvider:
    """
    Base implementation for NER providers.

    Provides common functionality that can be inherited by
    specific provider implementations.
    """

    def __init__(
        self,
        name: str = "base_ner",
        supported_entities: list[str] | None = None,
    ):
        """
        Initialize base provider.

        Args:
            name: Provider name
            supported_entities: List of supported entity types
        """
        self._name = name
        self._supported_entities = supported_entities or [
            "PERSON", "ORG", "LOC", "MISC"
        ]
        self._loaded = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def supported_entities(self) -> list[str]:
        return self._supported_entities

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        """Override in subclass."""
        self._loaded = True

    def unload(self) -> None:
        """Override in subclass."""
        self._loaded = False

    def predict_single(
        self,
        text: str,
        config: NERConfig | None = None,
    ) -> NERResult:
        """Convenience method for single text prediction."""
        results = self.predict([text], config)
        return results[0] if results else NERResult(text=text)

    def predict(
        self,
        texts: list[str],
        config: NERConfig | None = None,
    ) -> list[NERResult]:
        """Override in subclass."""
        raise NotImplementedError("Subclass must implement predict()")

    def _filter_predictions(
        self,
        predictions: list[NERPrediction],
        config: NERConfig,
    ) -> list[NERPrediction]:
        """Filter predictions based on config."""
        filtered = []
        for pred in predictions:
            # Check minimum score
            if pred.score < config.min_score:
                continue

            # Check entity type
            if not config.should_detect(pred.entity_type):
                continue

            filtered.append(pred)

        return filtered

    def _resolve_overlaps(
        self,
        predictions: list[NERPrediction],
    ) -> list[NERPrediction]:
        """
        Resolve overlapping predictions.

        Strategy: Keep higher scoring prediction.
        """
        if len(predictions) < 2:
            return predictions

        # Sort by start position, then by score (descending)
        sorted_preds = sorted(
            predictions,
            key=lambda p: (p.start, -p.score),
        )

        resolved = []
        for pred in sorted_preds:
            # Check overlap with existing resolved predictions
            overlaps = False
            for existing in resolved:
                if pred.overlaps_with(existing):
                    # Keep existing (higher score or earlier)
                    overlaps = True
                    break

            if not overlaps:
                resolved.append(pred)

        return resolved


__all__ = [
    "NEREntityType",
    "NERPrediction",
    "NERConfig",
    "NERResult",
    "NERProvider",
    "BaseNERProvider",
]
