"""
Presidio integration for PII detection.

Wraps Microsoft Presidio analyzer with our detection engine interface.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sandiraksa.detection.context import DetectionResult
from sandiraksa.detection.engine import BaseRecognizer, DetectionEngine, RecognizerRegistry
from sandiraksa.detection.entity_types import (
    CREDIT_CARD,
    DATE_TIME,
    EMAIL_ADDRESS,
    IBAN_CODE,
    IP_ADDRESS,
    LOCATION,
    MEDICAL_LICENSE,
    NRP,
    ORGANIZATION,
    PERSON,
    PHONE_NUMBER,
    URL,
    get_entity_registry,
)

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult

logger = logging.getLogger(__name__)

# Mapping from Presidio entity types to our entity types
PRESIDIO_ENTITY_MAP: dict[str, str] = {
    "PERSON": "PERSON",
    "EMAIL_ADDRESS": "EMAIL_ADDRESS",
    "PHONE_NUMBER": "PHONE_NUMBER",
    "CREDIT_CARD": "CREDIT_CARD",
    "IBAN_CODE": "IBAN_CODE",
    "IP_ADDRESS": "IP_ADDRESS",
    "DATE_TIME": "DATE_TIME",
    "LOCATION": "LOCATION",
    "NRP": "NRP",
    "MEDICAL_LICENSE": "MEDICAL_LICENSE",
    "URL": "URL",
    "CRYPTO": "CRYPTO",
    "UK_NHS": "UK_NHS",
    "US_SSN": "US_SSN",
    "US_DRIVER_LICENSE": "US_DRIVER_LICENSE",
    "US_PASSPORT": "US_PASSPORT",
    "US_BANK_NUMBER": "BANK_ACCOUNT",
    "US_ITIN": "US_ITIN",
    "SG_NRIC_FIN": "SG_NRIC_FIN",
    "AU_ABN": "AU_ABN",
    "AU_ACN": "AU_ACN",
    "AU_TFN": "AU_TFN",
    "AU_MEDICARE": "AU_MEDICARE",
    "IN_PAN": "IN_PAN",
    "IN_AADHAAR": "IN_AADHAAR",
    # Add more mappings as needed
}

# Entities we want to detect by default with Presidio
DEFAULT_PRESIDIO_ENTITIES: list[str] = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IBAN_CODE",
    "IP_ADDRESS",
    "LOCATION",
    "NRP",
    "URL",
]


class PresidioRecognizer(BaseRecognizer):
    """
    Recognizer that wraps Presidio analyzer.

    Uses Microsoft Presidio for NLP-based entity detection.
    """

    def __init__(
        self,
        entities: list[str] | None = None,
        language: str = "en",
        nlp_engine: str = "spacy",
    ) -> None:
        """
        Initialize Presidio recognizer.

        Args:
            entities: List of entity types to detect. If None, uses defaults.
            language: Language code for NLP (default: "en").
            nlp_engine: NLP engine to use ("spacy" or "transformers").
        """
        self._language = language
        self._nlp_engine = nlp_engine
        self._analyzer: AnalyzerEngine | None = None
        self._initialized = False

        # Determine supported entities
        if entities:
            self._presidio_entities = entities
        else:
            self._presidio_entities = DEFAULT_PRESIDIO_ENTITIES.copy()

        # Map to our entity types
        mapped_entities = [
            PRESIDIO_ENTITY_MAP.get(e, e) for e in self._presidio_entities
        ]

        super().__init__("presidio", mapped_entities)

    def _ensure_initialized(self) -> None:
        """Lazy initialization of Presidio analyzer."""
        if self._initialized:
            return

        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider

            # Configure NLP engine
            nlp_config = {
                "nlp_engine_name": self._nlp_engine,
                "models": [{"lang_code": self._language, "model_name": "en_core_web_sm"}],
            }

            # Create analyzer with configuration
            provider = NlpEngineProvider(nlp_configuration=nlp_config)
            nlp_engine = provider.create_engine()

            self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
            self._initialized = True

            logger.info(
                f"Presidio analyzer initialized with {self._nlp_engine} engine"
            )

        except ImportError as e:
            logger.error(f"Failed to import Presidio: {e}")
            raise RuntimeError(
                "Presidio not installed. Install with: pip install presidio-analyzer"
            ) from e
        except Exception as e:
            logger.error(f"Failed to initialize Presidio: {e}")
            raise

    def analyze(
        self,
        text: str,
        entities: list[str],
    ) -> list[DetectionResult]:
        """
        Analyze text using Presidio.

        Args:
            text: Text to analyze.
            entities: Entity types to look for.

        Returns:
            List of detection results.
        """
        self._ensure_initialized()

        if not text or not self._analyzer:
            return []

        # Map our entity types back to Presidio types
        presidio_entities = []
        reverse_map = {v: k for k, v in PRESIDIO_ENTITY_MAP.items()}

        for entity in entities:
            if entity in reverse_map:
                presidio_entities.append(reverse_map[entity])
            elif entity in PRESIDIO_ENTITY_MAP:
                presidio_entities.append(entity)

        if not presidio_entities:
            return []

        try:
            # Run Presidio analysis
            results = self._analyzer.analyze(
                text=text,
                entities=presidio_entities,
                language=self._language,
            )

            # Convert to our format
            return self._convert_results(results, text)

        except Exception as e:
            logger.error(f"Presidio analysis failed: {e}")
            return []

    def _convert_results(
        self,
        results: list[RecognizerResult],
        text: str,
    ) -> list[DetectionResult]:
        """Convert Presidio results to our format."""
        converted = []

        for result in results:
            # Map entity type
            entity_type = PRESIDIO_ENTITY_MAP.get(
                result.entity_type, result.entity_type
            )

            # Extract the detected text
            detected_text = text[result.start : result.end]

            converted.append(
                DetectionResult(
                    entity_type=entity_type,
                    start=result.start,
                    end=result.end,
                    text=detected_text,
                    score=result.score,
                    recognizer_name=result.recognition_metadata.get(
                        "recognizer_name", "presidio"
                    )
                    if result.recognition_metadata
                    else "presidio",
                    analysis_explanation={
                        "recognizer_identifier": result.recognition_metadata.get(
                            "recognizer_identifier"
                        )
                        if result.recognition_metadata
                        else None,
                    },
                )
            )

        return converted

    def get_supported_presidio_entities(self) -> list[str]:
        """Get list of entities supported by the analyzer."""
        self._ensure_initialized()
        if self._analyzer:
            return self._analyzer.get_supported_entities()
        return []


class PresidioDetectionEngine(DetectionEngine):
    """
    Detection engine using Presidio as the primary recognizer.

    Extends base DetectionEngine with Presidio-specific setup.
    """

    def __init__(
        self,
        language: str = "en",
        include_standard_recognizers: bool = True,
    ) -> None:
        """
        Initialize Presidio detection engine.

        Args:
            language: Language for NLP processing.
            include_standard_recognizers: Whether to include Presidio built-ins.
        """
        super().__init__()
        self._language = language
        self._include_standard = include_standard_recognizers
        self._presidio_recognizer: PresidioRecognizer | None = None

    def initialize(self) -> None:
        """Initialize the engine with Presidio recognizer + Indonesian recognizers."""
        if self._include_standard:
            # Create and register Presidio recognizer
            self._presidio_recognizer = PresidioRecognizer(
                language=self._language,
            )
            self._registry.register(self._presidio_recognizer)

        # Register Indonesian-specific recognizers
        self._register_indonesian_recognizers()

        self._initialized = True
        logger.info("Presidio detection engine initialized")

    def _register_indonesian_recognizers(self) -> None:
        """Register Indonesian ID and context-aware recognizers."""
        try:
            from sandiraksa.detection.recognizers.id_nik import NIKRecognizer
            from sandiraksa.detection.recognizers.id_dob import DateOfBirthRecognizer
            from sandiraksa.detection.recognizers.id_person import (
                IndonesianPersonRecognizer,
            )

            self._registry.register(NIKRecognizer())
            self._registry.register(DateOfBirthRecognizer())
            self._registry.register(IndonesianPersonRecognizer())
            logger.info(
                "Registered Indonesian recognizers (NIK, DateOfBirth, Person)"
            )
        except Exception as e:
            logger.warning(f"Failed to register some Indonesian recognizers: {e}")

    def add_custom_recognizer(self, recognizer: BaseRecognizer) -> None:
        """Add a custom recognizer to the engine."""
        self._registry.register(recognizer)

    @property
    def presidio_recognizer(self) -> PresidioRecognizer | None:
        """Get the Presidio recognizer if available."""
        return self._presidio_recognizer


# =============================================================================
# Lightweight Regex-based Recognizer (fallback when Presidio not available)
# =============================================================================

class RegexRecognizer(BaseRecognizer):
    """
    Simple regex-based recognizer for common patterns.

    Used as fallback when Presidio is not available or for
    patterns that don't need NLP.
    """

    # Regex patterns for common entities
    PATTERNS: dict[str, list[tuple[str, float]]] = {
        "EMAIL_ADDRESS": [
            (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", 0.9),
        ],
        "PHONE_NUMBER": [
            # International format
            (r"\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}", 0.8),
            # Generic format with separators
            (r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", 0.7),
        ],
        "CREDIT_CARD": [
            # Major card patterns (Visa, MC, Amex, etc.)
            (r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b", 0.85),
            # 4 groups of 4 digits with a CONSISTENT separator (backreference)
            # so NIK-style IDs like "3174-19880214-1001" do NOT match.
            (r"\b\d{4}([-\s]?)\d{4}\1\d{4}\1\d{4}\b", 0.7),
        ],
        "IP_ADDRESS": [
            # IPv4
            (r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b", 0.95),
            # IPv6 (simplified)
            (r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b", 0.9),
        ],
        "URL": [
            (r"https?://[^\s<>\"']+", 0.9),
            (r"www\.[^\s<>\"']+", 0.8),
        ],
        "IBAN_CODE": [
            (r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b", 0.8),
        ],
    }

    def __init__(self, entities: list[str] | None = None) -> None:
        """
        Initialize regex recognizer.

        Args:
            entities: Entity types to detect. If None, uses all available.
        """
        if entities:
            supported = [e for e in entities if e in self.PATTERNS]
        else:
            supported = list(self.PATTERNS.keys())

        super().__init__("regex", supported)
        self._compiled_patterns: dict[str, list[tuple[Any, float]]] = {}

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        import re

        for entity_type, patterns in self.PATTERNS.items():
            if entity_type in self._supported_entities:
                self._compiled_patterns[entity_type] = [
                    (re.compile(pattern, re.IGNORECASE), score)
                    for pattern, score in patterns
                ]

    def analyze(
        self,
        text: str,
        entities: list[str],
    ) -> list[DetectionResult]:
        """Analyze text using regex patterns."""
        if not self._compiled_patterns:
            self._compile_patterns()

        results: list[DetectionResult] = []

        for entity_type in entities:
            if entity_type not in self._compiled_patterns:
                continue

            for pattern, base_score in self._compiled_patterns[entity_type]:
                for match in pattern.finditer(text):
                    results.append(
                        DetectionResult(
                            entity_type=entity_type,
                            start=match.start(),
                            end=match.end(),
                            text=match.group(),
                            score=base_score,
                            recognizer_name="regex",
                        )
                    )

        return results


# =============================================================================
# Factory Functions
# =============================================================================

_presidio_engine: PresidioDetectionEngine | None = None


def get_presidio_engine() -> PresidioDetectionEngine:
    """Get the global Presidio detection engine."""
    global _presidio_engine
    if _presidio_engine is None:
        _presidio_engine = PresidioDetectionEngine()
    return _presidio_engine


def create_detection_engine(
    use_presidio: bool = True,
    language: str = "en",
) -> DetectionEngine:
    """
    Factory to create a detection engine.

    Args:
        use_presidio: Whether to use Presidio (requires installation).
        language: Language code for NLP.

    Returns:
        Configured DetectionEngine.
    """
    if use_presidio:
        try:
            engine = PresidioDetectionEngine(language=language)
            engine.initialize()
            return engine
        except Exception as e:
            logger.warning(f"Failed to create Presidio engine: {e}")
            logger.info("Falling back to regex-based detection")

    # Fallback to simple regex engine
    engine = DetectionEngine()
    engine.registry.register(RegexRecognizer())
    engine.initialize()
    return engine
