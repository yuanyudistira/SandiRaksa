"""
Presidio Adapter for Unified Detection Pipeline.

This module adapts Microsoft Presidio analyzer to work with the
unified detection pipeline using LogicalSegments.

The adapter:
1. Accepts LogicalSegments as input
2. Extracts text and passes to Presidio
3. Converts Presidio results to UnifiedFindings
4. Adds context from the segment to boost confidence
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sandiraksa.detection.unified_engine import (
    BaseUnifiedRecognizer,
    DetectionContext,
)
from sandiraksa.detection.unified_finding import (
    ConfidenceBand,
    ConfidenceEvidence,
    EvidenceType,
    UnifiedFinding,
    classify_confidence,
)

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult

    from sandiraksa.documents.logical_segment import LogicalSegment

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
}

# Reverse mapping
OUR_ENTITY_TO_PRESIDIO: dict[str, str] = {v: k for k, v in PRESIDIO_ENTITY_MAP.items()}

# Default entities to detect
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


class PresidioUnifiedRecognizer(BaseUnifiedRecognizer):
    """
    Unified recognizer that wraps Microsoft Presidio.

    This recognizer adapts Presidio to work with LogicalSegments,
    allowing it to be used in the unified detection pipeline.

    Features:
    - Lazy initialization of Presidio (only when first needed)
    - Automatic entity type mapping
    - Context extraction for evidence
    - Support for multiple languages
    """

    def __init__(
        self,
        entities: list[str] | None = None,
        language: str = "en",
        nlp_engine: str = "spacy",
        priority: int = 50,
    ) -> None:
        """
        Initialize the Presidio recognizer.

        Args:
            entities: Entity types to detect (None = defaults)
            language: Language code for NLP
            nlp_engine: NLP engine ("spacy" or "transformers")
            priority: Priority for overlap resolution
        """
        self._language = language
        self._nlp_engine = nlp_engine
        self._analyzer: "AnalyzerEngine | None" = None
        self._initialized = False

        # Determine supported entities
        if entities:
            self._presidio_entities = entities
        else:
            self._presidio_entities = DEFAULT_PRESIDIO_ENTITIES.copy()

        # Map to our entity types for the interface
        mapped_entities = [
            PRESIDIO_ENTITY_MAP.get(e, e) for e in self._presidio_entities
        ]

        super().__init__(
            name="presidio",
            supported_entities=mapped_entities,
            priority=priority,
        )

    def _ensure_initialized(self) -> bool:
        """
        Lazy initialization of Presidio analyzer.

        Returns:
            True if initialized successfully, False otherwise
        """
        if self._initialized:
            return True

        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider

            # Configure NLP engine
            nlp_config = {
                "nlp_engine_name": self._nlp_engine,
                "models": [
                    {"lang_code": self._language, "model_name": "en_core_web_sm"}
                ],
            }

            # Create analyzer
            provider = NlpEngineProvider(nlp_configuration=nlp_config)
            nlp_engine = provider.create_engine()

            self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
            self._initialized = True

            logger.info(
                f"Presidio analyzer initialized with {self._nlp_engine} engine"
            )
            return True

        except ImportError as e:
            logger.warning(f"Presidio not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Presidio: {e}")
            return False

    def analyze(
        self,
        segment: "LogicalSegment",
        context: DetectionContext,
    ) -> list[UnifiedFinding]:
        """
        Analyze a LogicalSegment using Presidio.

        Args:
            segment: The segment to analyze
            context: Detection context

        Returns:
            List of UnifiedFinding objects
        """
        if not self._ensure_initialized():
            return []

        if not segment.text or not self._analyzer:
            return []

        # Determine which entities to detect
        entities_to_detect = self._filter_entities(context)
        if not entities_to_detect:
            return []

        # Map to Presidio entity types
        presidio_entities = []
        for entity in entities_to_detect:
            if entity in OUR_ENTITY_TO_PRESIDIO:
                presidio_entities.append(OUR_ENTITY_TO_PRESIDIO[entity])
            elif entity in PRESIDIO_ENTITY_MAP:
                presidio_entities.append(entity)

        if not presidio_entities:
            return []

        try:
            # Run Presidio analysis
            results = self._analyzer.analyze(
                text=segment.text,
                entities=presidio_entities,
                language=self._language,
            )

            # Convert to UnifiedFindings
            return self._convert_results(results, segment)

        except Exception as e:
            logger.error(f"Presidio analysis failed: {e}")
            return []

    def _convert_results(
        self,
        results: list["RecognizerResult"],
        segment: "LogicalSegment",
    ) -> list[UnifiedFinding]:
        """
        Convert Presidio results to UnifiedFindings.

        Args:
            results: Presidio RecognizerResult list
            segment: Source segment

        Returns:
            List of UnifiedFinding objects
        """
        findings: list[UnifiedFinding] = []

        for result in results:
            # Map entity type
            entity_type = PRESIDIO_ENTITY_MAP.get(
                result.entity_type, result.entity_type
            )

            # Extract detected text
            detected_text = segment.text[result.start : result.end]

            # Get context window
            context_before, context_after = segment.get_context_window(
                result.start, result.end, window_size=30
            )

            # Get recognizer name from metadata
            recognizer_name = "presidio"
            if hasattr(result, "recognition_metadata") and result.recognition_metadata:
                recognizer_name = result.recognition_metadata.get(
                    "recognizer_name", "presidio"
                )

            # Create finding
            finding = UnifiedFinding(
                segment_id=segment.id,
                entity_type=entity_type,
                start=result.start,
                end=result.end,
                raw_score=result.score,
                confidence_band=classify_confidence(result.score),
                detector=f"presidio/{recognizer_name}",
                detected_text=detected_text,
                context_before=context_before,
                context_after=context_after,
            )

            # Add evidence
            finding.add_evidence(
                ConfidenceEvidence(
                    evidence_type=EvidenceType.PRESIDIO,
                    source=recognizer_name,
                    weight=result.score,
                    reason_code="presidio_detected",
                    description=f"Presidio {recognizer_name} detected {entity_type}",
                )
            )

            # Add NER evidence if applicable
            if recognizer_name in ("SpacyRecognizer", "TransformersRecognizer"):
                finding.add_evidence(
                    ConfidenceEvidence(
                        evidence_type=EvidenceType.NER_DETECTION,
                        source=recognizer_name,
                        weight=result.score * 0.8,
                        reason_code="ner_detected",
                        description=f"NER model detected {entity_type}",
                    )
                )

            findings.append(finding)

        return findings

    def get_supported_presidio_entities(self) -> list[str]:
        """Get entities supported by Presidio analyzer."""
        if self._ensure_initialized() and self._analyzer:
            return self._analyzer.get_supported_entities()
        return []


class IndonesianIdRecognizer(BaseUnifiedRecognizer):
    """
    Recognizer for Indonesian identity documents.

    Detects:
    - NIK (Nomor Induk Kependudukan) - 16 digits
    - NPWP (Nomor Pokok Wajib Pajak) - 15 digits with format XX.XXX.XXX.X-XXX.XXX
    - KK (Kartu Keluarga) - 16 digits
    - Indonesian phone numbers
    """

    def __init__(self, priority: int = 80) -> None:
        """Initialize Indonesian ID recognizer."""
        super().__init__(
            name="indonesian_id",
            supported_entities=["ID_NIK", "ID_NPWP", "ID_KK", "ID_PHONE"],
            priority=priority,
        )
        self._patterns_compiled = False
        self._nik_pattern = None
        self._npwp_pattern = None
        self._kk_pattern = None
        self._phone_pattern = None

    def _compile_patterns(self) -> None:
        """Compile regex patterns for Indonesian IDs."""
        if self._patterns_compiled:
            return

        import re

        # NIK: 16 digits, starts with province code (11-94)
        # Format: PPKKCC DDMMYY XXXX
        self._nik_pattern = re.compile(
            r"\b(?:[1-9][1-9])\d{14}\b"
        )

        # NPWP: 15 digits, can have separators
        # Format: XX.XXX.XXX.X-XXX.XXX or 15 consecutive digits
        self._npwp_pattern = re.compile(
            r"\b\d{2}\.?\d{3}\.?\d{3}\.?\d[-.]?\d{3}\.?\d{3}\b"
        )

        # KK: 16 digits (same structure as NIK but different purpose)
        self._kk_pattern = re.compile(
            r"\b(?:[1-9][1-9])\d{14}\b"
        )

        # Indonesian phone: +62 or 08XX
        self._phone_pattern = re.compile(
            r"(?:\+62|62|0)8[1-9][0-9]{7,10}\b"
        )

        self._patterns_compiled = True

    def analyze(
        self,
        segment: "LogicalSegment",
        context: DetectionContext,
    ) -> list[UnifiedFinding]:
        """Analyze segment for Indonesian IDs."""
        self._compile_patterns()

        if not segment.text:
            return []

        findings: list[UnifiedFinding] = []
        text = segment.text

        # Check which entities to detect
        entities = self._filter_entities(context)

        # Detect NIK
        if "ID_NIK" in entities and self._nik_pattern:
            for match in self._nik_pattern.finditer(text):
                # Validate NIK structure
                nik = match.group()
                if self._validate_nik(nik):
                    context_before, context_after = segment.get_context_window(
                        match.start(), match.end()
                    )
                    finding = UnifiedFinding(
                        segment_id=segment.id,
                        entity_type="ID_NIK",
                        start=match.start(),
                        end=match.end(),
                        raw_score=0.85,
                        confidence_band=ConfidenceBand.HIGH,
                        detector="indonesian_id/nik",
                        detected_text=nik,
                        context_before=context_before,
                        context_after=context_after,
                        is_validated=True,
                    )
                    finding.add_evidence(
                        ConfidenceEvidence(
                            evidence_type=EvidenceType.PATTERN_MATCH,
                            source="indonesian_id",
                            weight=0.7,
                            reason_code="nik_pattern_match",
                            description="Matched NIK 16-digit pattern",
                        )
                    )
                    finding.add_evidence(
                        ConfidenceEvidence(
                            evidence_type=EvidenceType.STRUCTURAL_VALID,
                            source="indonesian_id",
                            weight=0.15,
                            reason_code="nik_structure_valid",
                            description="NIK structure validated (province code, date)",
                        )
                    )
                    findings.append(finding)

        # Detect NPWP
        if "ID_NPWP" in entities and self._npwp_pattern:
            for match in self._npwp_pattern.finditer(text):
                npwp = match.group()
                # Remove separators for validation
                npwp_digits = "".join(c for c in npwp if c.isdigit())
                if len(npwp_digits) == 15:
                    context_before, context_after = segment.get_context_window(
                        match.start(), match.end()
                    )
                    finding = UnifiedFinding(
                        segment_id=segment.id,
                        entity_type="ID_NPWP",
                        start=match.start(),
                        end=match.end(),
                        raw_score=0.8,
                        confidence_band=ConfidenceBand.HIGH,
                        detector="indonesian_id/npwp",
                        detected_text=npwp,
                        context_before=context_before,
                        context_after=context_after,
                        is_validated=True,
                    )
                    finding.add_evidence(
                        ConfidenceEvidence(
                            evidence_type=EvidenceType.PATTERN_MATCH,
                            source="indonesian_id",
                            weight=0.8,
                            reason_code="npwp_pattern_match",
                            description="Matched NPWP 15-digit pattern",
                        )
                    )
                    findings.append(finding)

        # Detect phone
        if "ID_PHONE" in entities and self._phone_pattern:
            for match in self._phone_pattern.finditer(text):
                phone = match.group()
                context_before, context_after = segment.get_context_window(
                    match.start(), match.end()
                )
                finding = UnifiedFinding(
                    segment_id=segment.id,
                    entity_type="ID_PHONE",
                    start=match.start(),
                    end=match.end(),
                    raw_score=0.75,
                    confidence_band=ConfidenceBand.MEDIUM,
                    detector="indonesian_id/phone",
                    detected_text=phone,
                    context_before=context_before,
                    context_after=context_after,
                )
                finding.add_evidence(
                    ConfidenceEvidence(
                        evidence_type=EvidenceType.PATTERN_MATCH,
                        source="indonesian_id",
                        weight=0.75,
                        reason_code="id_phone_pattern_match",
                        description="Matched Indonesian phone pattern (+62/08XX)",
                    )
                )
                findings.append(finding)

        return findings

    def _validate_nik(self, nik: str) -> bool:
        """
        Validate NIK structure.

        NIK format: PPKKCC DDMMYY XXXX
        PP = Province code (11-94)
        KK = City/regency code
        CC = District code
        DDMMYY = Birth date (DD can be +40 for female)
        XXXX = Serial number
        """
        if len(nik) != 16 or not nik.isdigit():
            return False

        # Check province code (first 2 digits)
        province = int(nik[:2])
        if province < 11 or province > 94:
            return False

        # Check birth date (characters 7-12)
        day = int(nik[6:8])
        month = int(nik[8:10])
        year = int(nik[10:12])

        # Day can be 1-31 or 41-71 (female: day + 40)
        if not ((1 <= day <= 31) or (41 <= day <= 71)):
            return False

        # Month 1-12
        if not (1 <= month <= 12):
            return False

        return True


class CustomTermsRecognizer(BaseUnifiedRecognizer):
    """
    Recognizer for custom terms defined by user.

    Custom terms always match with CRITICAL confidence.
    """

    def __init__(
        self,
        terms: list[str] | None = None,
        case_sensitive: bool = False,
        priority: int = 100,
    ) -> None:
        """
        Initialize custom terms recognizer.

        Args:
            terms: List of terms to detect
            case_sensitive: Whether matching is case-sensitive
            priority: Priority (default highest)
        """
        super().__init__(
            name="custom_terms",
            supported_entities=["CUSTOM"],
            priority=priority,
        )
        self._terms = terms or []
        self._case_sensitive = case_sensitive

    def set_terms(self, terms: list[str]) -> None:
        """Update the list of custom terms."""
        self._terms = terms

    def add_term(self, term: str) -> None:
        """Add a custom term."""
        if term not in self._terms:
            self._terms.append(term)

    def analyze(
        self,
        segment: "LogicalSegment",
        context: DetectionContext,
    ) -> list[UnifiedFinding]:
        """Search for custom terms in segment."""
        if not segment.text or not self._terms:
            return []

        findings: list[UnifiedFinding] = []
        text = segment.text
        search_text = text if self._case_sensitive else text.lower()

        for term in self._terms:
            search_term = term if self._case_sensitive else term.lower()
            start = 0

            while True:
                pos = search_text.find(search_term, start)
                if pos == -1:
                    break

                end = pos + len(term)
                detected = text[pos:end]

                context_before, context_after = segment.get_context_window(pos, end)

                finding = UnifiedFinding.from_custom_term(
                    term=detected,
                    start=pos,
                    end=end,
                    segment_id=segment.id,
                )
                finding.context_before = context_before
                finding.context_after = context_after

                findings.append(finding)
                start = end

        return findings


def create_default_recognizers() -> list[BaseUnifiedRecognizer]:
    """
    Create the default set of recognizers for the unified engine.

    Returns:
        List of recognizers to register
    """
    recognizers: list[BaseUnifiedRecognizer] = []

    # Indonesian ID recognizer (high priority)
    recognizers.append(IndonesianIdRecognizer(priority=80))

    # Presidio recognizer (medium priority)
    recognizers.append(PresidioUnifiedRecognizer(priority=50))

    # Custom terms recognizer (highest priority, but empty by default)
    recognizers.append(CustomTermsRecognizer(priority=100))

    return recognizers


__all__ = [
    "CustomTermsRecognizer",
    "DEFAULT_PRESIDIO_ENTITIES",
    "IndonesianIdRecognizer",
    "OUR_ENTITY_TO_PRESIDIO",
    "PRESIDIO_ENTITY_MAP",
    "PresidioUnifiedRecognizer",
    "create_default_recognizers",
]
