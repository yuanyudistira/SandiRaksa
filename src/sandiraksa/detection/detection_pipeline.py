"""
Unified Detection Pipeline Implementation.

This module implements the UnifiedDetectionEngine that orchestrates
detection across all document types using LogicalSegments.

Architecture:
    DocumentAdapter.extract() → LogicalSegment[]
    UnifiedDetectionEngine.detect_batch(segments) → UnifiedFinding[]
    OverlapResolver.resolve(findings) → UnifiedFinding[]

Key Features:
    - Accepts LogicalSegments from any document adapter
    - Coordinates multiple recognizers
    - Applies context-based confidence boosting
    - Resolves overlapping detections
    - Returns UnifiedFindings with evidence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sandiraksa.detection.unified_engine import (
    BaseUnifiedRecognizer,
    DetectionConfig,
    DetectionContext,
    DetectionMode,
    RecognizerInfo,
    UnifiedDetectionEngineProtocol,
    UnifiedRecognizer,
)
from sandiraksa.detection.unified_finding import (
    ConfidenceBand,
    ConfidenceEvidence,
    EvidenceType,
    UnifiedFinding,
    classify_confidence,
)

if TYPE_CHECKING:
    from sandiraksa.documents.logical_segment import LogicalSegment

logger = logging.getLogger(__name__)


# Context labels that indicate specific PII types
CONTEXT_TO_ENTITY: dict[str, list[str]] = {
    # Indonesian labels
    "nik": ["ID_NIK"],
    "nomor induk kependudukan": ["ID_NIK"],
    "no. ktp": ["ID_NIK"],
    "no ktp": ["ID_NIK"],
    "ktp": ["ID_NIK"],
    "nama": ["PERSON"],
    "nama lengkap": ["PERSON"],
    "nama pasien": ["PERSON"],
    "nama karyawan": ["PERSON"],
    "alamat": ["ADDRESS", "LOCATION"],
    "alamat rumah": ["ADDRESS"],
    "alamat kantor": ["ADDRESS"],
    "telepon": ["ID_PHONE", "PHONE_NUMBER"],
    "telp": ["ID_PHONE", "PHONE_NUMBER"],
    "no. telp": ["ID_PHONE", "PHONE_NUMBER"],
    "no telp": ["ID_PHONE", "PHONE_NUMBER"],
    "hp": ["ID_PHONE", "PHONE_NUMBER"],
    "handphone": ["ID_PHONE", "PHONE_NUMBER"],
    "email": ["EMAIL_ADDRESS"],
    "e-mail": ["EMAIL_ADDRESS"],
    "npwp": ["ID_NPWP"],
    "no. npwp": ["ID_NPWP"],
    "kk": ["ID_KK"],
    "no. kk": ["ID_KK"],
    "nomor kartu keluarga": ["ID_KK"],
    "tanggal lahir": ["DATE_OF_BIRTH", "DATE"],
    "tgl lahir": ["DATE_OF_BIRTH", "DATE"],
    "tempat lahir": ["LOCATION"],
    "rekening": ["BANK_ACCOUNT"],
    "no. rekening": ["BANK_ACCOUNT"],
    "nomor rekening": ["BANK_ACCOUNT"],
    # English labels
    "name": ["PERSON"],
    "full name": ["PERSON"],
    "patient name": ["PERSON"],
    "employee name": ["PERSON"],
    "address": ["ADDRESS", "LOCATION"],
    "phone": ["PHONE_NUMBER"],
    "mobile": ["PHONE_NUMBER"],
    "dob": ["DATE_OF_BIRTH"],
    "date of birth": ["DATE_OF_BIRTH"],
    "ssn": ["US_SSN"],
    "social security": ["US_SSN"],
    "credit card": ["CREDIT_CARD"],
    "card number": ["CREDIT_CARD"],
}

# Confidence boost when context matches entity type
CONTEXT_MATCH_BOOST = 0.15

# Confidence penalty when context contradicts entity type
CONTEXT_MISMATCH_PENALTY = 0.1


@dataclass
class RecognizerRegistry:
    """Registry of recognizers with priority ordering."""

    _recognizers: dict[str, UnifiedRecognizer] = field(default_factory=dict)
    _entity_index: dict[str, list[str]] = field(default_factory=dict)

    def register(self, recognizer: UnifiedRecognizer) -> None:
        """Register a recognizer."""
        self._recognizers[recognizer.name] = recognizer

        for entity in recognizer.supported_entities:
            if entity not in self._entity_index:
                self._entity_index[entity] = []
            if recognizer.name not in self._entity_index[entity]:
                self._entity_index[entity].append(recognizer.name)

        logger.debug(
            f"Registered recognizer '{recognizer.name}' "
            f"for {recognizer.supported_entities}"
        )

    def unregister(self, name: str) -> None:
        """Unregister a recognizer."""
        if name in self._recognizers:
            recognizer = self._recognizers[name]
            for entity in recognizer.supported_entities:
                if entity in self._entity_index:
                    self._entity_index[entity] = [
                        r for r in self._entity_index[entity] if r != name
                    ]
            del self._recognizers[name]

    def get(self, name: str) -> UnifiedRecognizer | None:
        """Get a recognizer by name."""
        return self._recognizers.get(name)

    def get_for_entity(self, entity_type: str) -> list[UnifiedRecognizer]:
        """Get recognizers that handle an entity type."""
        names = self._entity_index.get(entity_type, [])
        return [self._recognizers[n] for n in names if n in self._recognizers]

    def get_for_entities(
        self, entity_types: list[str] | None
    ) -> list[UnifiedRecognizer]:
        """Get recognizers for specified entities (or all if None)."""
        if entity_types is None:
            return list(self._recognizers.values())

        seen: set[str] = set()
        result: list[UnifiedRecognizer] = []
        for entity in entity_types:
            for recognizer in self.get_for_entity(entity):
                if recognizer.name not in seen:
                    seen.add(recognizer.name)
                    result.append(recognizer)
        return result

    def all_recognizers(self) -> list[UnifiedRecognizer]:
        """Get all registered recognizers."""
        return list(self._recognizers.values())

    def supported_entities(self) -> set[str]:
        """Get all supported entity types."""
        return set(self._entity_index.keys())

    def get_info(self) -> list[RecognizerInfo]:
        """Get information about all recognizers."""
        return [
            RecognizerInfo(
                name=r.name,
                entities=r.supported_entities,
                priority=r.priority,
            )
            for r in self._recognizers.values()
        ]


class UnifiedDetectionEngine:
    """
    Unified detection engine that processes LogicalSegments.

    This is the main entry point for PII detection in SandiRaksa.
    It accepts LogicalSegments (produced by DocumentAdapters) and
    returns UnifiedFindings.

    Example:
        ```python
        engine = UnifiedDetectionEngine()
        engine.initialize()  # Registers default recognizers

        # Detect in a single segment
        findings = engine.detect(segment)

        # Detect in multiple segments
        all_findings = engine.detect_batch(segments)
        ```
    """

    def __init__(self, config: DetectionConfig | None = None) -> None:
        """
        Initialize the engine.

        Args:
            config: Default detection configuration
        """
        self._config = config or DetectionConfig()
        self._registry = RecognizerRegistry()
        self._initialized = False

    @property
    def config(self) -> DetectionConfig:
        """Get the default configuration."""
        return self._config

    @config.setter
    def config(self, value: DetectionConfig) -> None:
        """Set the default configuration."""
        self._config = value

    @property
    def initialized(self) -> bool:
        """Check if engine is initialized."""
        return self._initialized

    def initialize(self) -> None:
        """
        Initialize the engine with default recognizers.

        This registers the standard recognizers including:
        - Presidio-based recognizers
        - Indonesian ID recognizers (NIK, NPWP, KK, Phone)
        - Custom terms recognizer
        """
        if self._initialized:
            return

        # Register built-in recognizers
        # These will be added when we create the adapters
        self._initialized = True
        logger.info("UnifiedDetectionEngine initialized")

    def shutdown(self) -> None:
        """Shutdown the engine and release resources."""
        self._initialized = False
        logger.info("UnifiedDetectionEngine shutdown")

    def register_recognizer(self, recognizer: UnifiedRecognizer) -> None:
        """
        Register a recognizer with the engine.

        Args:
            recognizer: The recognizer to register
        """
        self._registry.register(recognizer)

    def unregister_recognizer(self, name: str) -> None:
        """
        Unregister a recognizer.

        Args:
            name: Name of the recognizer to remove
        """
        self._registry.unregister(name)

    def get_supported_entities(self) -> set[str]:
        """Get all entity types supported by registered recognizers."""
        return self._registry.supported_entities()

    def detect(
        self,
        segment: "LogicalSegment",
        config: DetectionConfig | None = None,
    ) -> list[UnifiedFinding]:
        """
        Detect PII in a single segment.

        Args:
            segment: LogicalSegment to analyze
            config: Detection configuration (uses default if None)

        Returns:
            List of UnifiedFinding objects
        """
        effective_config = config or self._config
        context = DetectionContext(
            segment=segment,
            config=effective_config,
            file_type=segment.file_type,
            document_type=segment.document_type,
        )

        # Get relevant recognizers
        recognizers = self._registry.get_for_entities(effective_config.entities)

        # Collect findings from all recognizers
        all_findings: list[UnifiedFinding] = []

        for recognizer in recognizers:
            try:
                findings = recognizer.analyze(segment, context)
                all_findings.extend(findings)
            except Exception as e:
                logger.warning(
                    f"Recognizer '{recognizer.name}' failed on segment "
                    f"'{segment.id}': {e}"
                )

        # Apply context-based confidence adjustment
        all_findings = self._apply_context_boost(all_findings, segment, context)

        # Filter by minimum score
        all_findings = [
            f for f in all_findings
            if f.raw_score >= effective_config.min_score
        ]

        # Apply allow list filtering
        if effective_config.allow_list:
            all_findings = self._apply_allow_list(
                all_findings, effective_config.allow_list
            )

        # Resolve overlaps
        all_findings = self._resolve_overlaps(all_findings)

        # Limit findings per segment
        if len(all_findings) > effective_config.max_findings_per_segment:
            # Sort by score descending, take top N
            all_findings.sort(key=lambda f: f.raw_score, reverse=True)
            all_findings = all_findings[:effective_config.max_findings_per_segment]

        return all_findings

    def detect_batch(
        self,
        segments: list["LogicalSegment"],
        config: DetectionConfig | None = None,
    ) -> dict[str, list[UnifiedFinding]]:
        """
        Detect PII in multiple segments.

        Args:
            segments: List of LogicalSegments to analyze
            config: Detection configuration

        Returns:
            Dict mapping segment IDs to their findings
        """
        results: dict[str, list[UnifiedFinding]] = {}

        for segment in segments:
            findings = self.detect(segment, config)
            results[segment.id] = findings

        return results

    def detect_all(
        self,
        segments: list["LogicalSegment"],
        config: DetectionConfig | None = None,
    ) -> list[UnifiedFinding]:
        """
        Detect PII in all segments and return flat list.

        Args:
            segments: List of LogicalSegments to analyze
            config: Detection configuration

        Returns:
            Flat list of all findings
        """
        all_findings: list[UnifiedFinding] = []

        for segment in segments:
            findings = self.detect(segment, config)
            all_findings.extend(findings)

        return all_findings

    def _apply_context_boost(
        self,
        findings: list[UnifiedFinding],
        segment: "LogicalSegment",
        context: DetectionContext,
    ) -> list[UnifiedFinding]:
        """
        Apply confidence adjustments based on context.

        If the segment has context labels that match the entity type,
        boost confidence. If they contradict, reduce confidence.
        """
        if not context.config.use_context or not segment.has_context:
            return findings

        labels = [label.lower() for label in segment.context_labels]

        for finding in findings:
            # Check if any context label suggests this entity type
            matched = False
            for label in labels:
                expected_entities = CONTEXT_TO_ENTITY.get(label, [])
                if finding.entity_type in expected_entities:
                    # Context supports this detection
                    matched = True
                    old_score = finding.raw_score
                    finding.raw_score = min(1.0, finding.raw_score + CONTEXT_MATCH_BOOST)
                    finding.confidence_band = classify_confidence(finding.raw_score)
                    finding.add_evidence(
                        ConfidenceEvidence(
                            evidence_type=EvidenceType.CONTEXT_POSITIVE,
                            source="context_analyzer",
                            weight=CONTEXT_MATCH_BOOST,
                            reason_code="context_match",
                            description=f"Context label '{label}' supports {finding.entity_type}",
                        )
                    )
                    break

            # If no match found but there were labels, might indicate mismatch
            # (only apply if we have specific labels, not generic ones)
            if not matched and labels and context.config.mode == DetectionMode.BALANCED:
                # Check if labels suggest a DIFFERENT entity type
                for label in labels:
                    expected = CONTEXT_TO_ENTITY.get(label, [])
                    if expected and finding.entity_type not in expected:
                        # Context suggests different type
                        finding.raw_score = max(
                            0.0, finding.raw_score - CONTEXT_MISMATCH_PENALTY
                        )
                        finding.confidence_band = classify_confidence(finding.raw_score)
                        finding.add_evidence(
                            ConfidenceEvidence(
                                evidence_type=EvidenceType.CONTEXT_NEGATIVE,
                                source="context_analyzer",
                                weight=-CONTEXT_MISMATCH_PENALTY,
                                reason_code="context_mismatch",
                                description=f"Context label '{label}' suggests different type",
                            )
                        )
                        break

        return findings

    def _apply_allow_list(
        self,
        findings: list[UnifiedFinding],
        allow_list: list[str],
    ) -> list[UnifiedFinding]:
        """Filter out findings that match the allow list."""
        allow_set = {term.lower() for term in allow_list}
        return [
            f for f in findings
            if f.detected_text.lower() not in allow_set
        ]

    def _resolve_overlaps(
        self,
        findings: list[UnifiedFinding],
    ) -> list[UnifiedFinding]:
        """
        Resolve overlapping findings.

        When findings overlap, keep the one with:
        1. Higher priority recognizer
        2. Higher confidence score
        3. Longer span
        """
        if not findings:
            return findings

        # Sort by start position, then by score descending
        sorted_findings = sorted(
            findings,
            key=lambda f: (f.start, -f.raw_score, -(f.end - f.start)),
        )

        result: list[UnifiedFinding] = []
        for finding in sorted_findings:
            # Check if this overlaps with any kept finding
            overlaps = False
            for kept in result:
                if self._findings_overlap(finding, kept):
                    overlaps = True
                    break

            if not overlaps:
                result.append(finding)

        return result

    def _findings_overlap(
        self, f1: UnifiedFinding, f2: UnifiedFinding
    ) -> bool:
        """Check if two findings overlap."""
        # Must be in same segment
        if f1.segment_id != f2.segment_id:
            return False

        # Check position overlap
        return f1.start < f2.end and f2.start < f1.end

    def get_status(self) -> dict[str, Any]:
        """Get engine status information."""
        return {
            "initialized": self._initialized,
            "recognizer_count": len(self._registry.all_recognizers()),
            "recognizers": [
                {
                    "name": r.name,
                    "entities": r.supported_entities,
                    "priority": r.priority,
                }
                for r in self._registry.all_recognizers()
            ],
            "supported_entities": list(self._registry.supported_entities()),
            "config": {
                "mode": self._config.mode.value,
                "min_score": self._config.min_score,
                "use_context": self._config.use_context,
                "language": self._config.language,
            },
        }


# Singleton instance
_engine_instance: UnifiedDetectionEngine | None = None


def get_unified_engine() -> UnifiedDetectionEngine:
    """
    Get the singleton UnifiedDetectionEngine instance.

    Returns:
        The global engine instance
    """
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = UnifiedDetectionEngine()
    return _engine_instance


def create_detection_engine(
    config: DetectionConfig | None = None,
) -> UnifiedDetectionEngine:
    """
    Create a new UnifiedDetectionEngine instance.

    Args:
        config: Detection configuration

    Returns:
        New engine instance (not singleton)
    """
    return UnifiedDetectionEngine(config)


__all__ = [
    "CONTEXT_MATCH_BOOST",
    "CONTEXT_MISMATCH_PENALTY",
    "CONTEXT_TO_ENTITY",
    "RecognizerRegistry",
    "UnifiedDetectionEngine",
    "create_detection_engine",
    "get_unified_engine",
]
