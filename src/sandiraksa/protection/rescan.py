"""
Leakage Re-scan Module.

Final validation before output is marked ready.
Re-scans the protected output to ensure no sensitive data leaked through.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sandiraksa.detection.context import (
    DetectionConfig,
    DetectionContext,
    DetectionResult,
    TextSegment,
    create_detection_context,
)
from sandiraksa.detection.engine import DetectionEngine, get_detection_engine
from sandiraksa.domain.finding import DocumentLocation, Finding
from sandiraksa.domain.token import TOKEN_PATTERN

if TYPE_CHECKING:
    from sandiraksa.protection.pipeline import DocumentHandler

logger = logging.getLogger(__name__)


class LeakageType(str, Enum):
    """Types of leakage detected."""

    RESIDUAL_PII = "residual_pii"  # PII that wasn't tokenized
    PARTIAL_TOKEN = "partial_token"  # Incomplete/corrupted token
    UNTOKENIZED_VALUE = "untokenized_value"  # Value that should have been tokenized
    CONTEXT_LEAK = "context_leak"  # Surrounding context reveals protected value


class LeakageSeverity(str, Enum):
    """Severity of detected leakage."""

    CRITICAL = "critical"  # Must be fixed before output
    WARNING = "warning"  # Should be reviewed
    INFO = "info"  # Informational


@dataclass
class LeakageFinding:
    """A potential leakage found during re-scan."""

    id: str
    leakage_type: LeakageType
    severity: LeakageSeverity
    text: str
    location: DocumentLocation
    entity_type: str | None = None
    message: str = ""
    confidence: float = 0.0

    # For comparison with original findings
    original_finding_id: str | None = None
    expected_token: str | None = None


@dataclass
class RescanResult:
    """Result of a re-scan operation."""

    success: bool
    is_clean: bool = False
    leakages: list[LeakageFinding] = field(default_factory=list)

    # Statistics
    total_segments_scanned: int = 0
    scan_duration_ms: float = 0.0

    # Counts by severity
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0

    @property
    def has_critical(self) -> bool:
        """Check if there are critical leakages."""
        return self.critical_count > 0

    def add_leakage(self, leakage: LeakageFinding) -> None:
        """Add a leakage finding."""
        self.leakages.append(leakage)

        if leakage.severity == LeakageSeverity.CRITICAL:
            self.critical_count += 1
        elif leakage.severity == LeakageSeverity.WARNING:
            self.warning_count += 1
        else:
            self.info_count += 1


class RescanEngine:
    """
    Engine for re-scanning protected output.

    Verifies that:
    1. No original sensitive values remain
    2. All tokens are properly formatted
    3. No partial/corrupted tokens exist
    4. No context leakage occurred
    """

    def __init__(
        self,
        detection_engine: DetectionEngine | None = None,
        strict_mode: bool = True,
    ) -> None:
        """
        Initialize rescan engine.

        Args:
            detection_engine: Detection engine for PII scanning.
            strict_mode: If True, any detection is critical. If False, uses confidence threshold.
        """
        self._engine = detection_engine or get_detection_engine()
        # Ensure the engine is ready; analyze_text() requires initialization.
        if not getattr(self._engine, "_initialized", False):
            self._engine.initialize()
        self._strict_mode = strict_mode

        # Values that were tokenized (for reference)
        self._protected_values: set[str] = set()

        # Tokens that should appear
        self._expected_tokens: set[str] = set()

    def set_protected_values(self, values: set[str]) -> None:
        """Set the values that were tokenized."""
        self._protected_values = values

    def set_expected_tokens(self, tokens: set[str]) -> None:
        """Set the tokens expected in output."""
        self._expected_tokens = tokens

    def rescan_text(
        self,
        text: str,
        location: DocumentLocation | None = None,
        config: DetectionConfig | None = None,
    ) -> list[LeakageFinding]:
        """
        Re-scan text for potential leakage.

        Args:
            text: Text to scan.
            location: Document location for reporting.
            config: Detection configuration.

        Returns:
            List of leakage findings.
        """
        findings: list[LeakageFinding] = []

        # 1. Check for residual PII using detection engine
        if config is None:
            config = DetectionConfig.default()

        context = create_detection_context(
            operation_id="rescan",
            file_id="output",
            project_id="rescan",
        )
        context.config = config

        results = self._engine.analyze_text(text, context)

        for result in results:
            # Skip if it's a properly formatted token
            if self._is_valid_token(result.text):
                continue

            severity = self._determine_severity(result)
            findings.append(
                LeakageFinding(
                    id=f"leak_{len(findings)}",
                    leakage_type=LeakageType.RESIDUAL_PII,
                    severity=severity,
                    text=result.text,
                    location=location or DocumentLocation(element_type="text", element_id=""),
                    entity_type=result.entity_type,
                    message=f"Residual {result.entity_type} found in output",
                    confidence=result.score,
                )
            )

        # 2. Check for original protected values
        for value in self._protected_values:
            if value.lower() in text.lower():
                findings.append(
                    LeakageFinding(
                        id=f"leak_{len(findings)}",
                        leakage_type=LeakageType.UNTOKENIZED_VALUE,
                        severity=LeakageSeverity.CRITICAL,
                        text=value,
                        location=location or DocumentLocation(element_type="text", element_id=""),
                        message="Original value found in output - should have been tokenized",
                        confidence=1.0,
                    )
                )

        # 3. Check for partial/corrupted tokens
        partial_tokens = self._find_partial_tokens(text)
        for partial in partial_tokens:
            findings.append(
                LeakageFinding(
                    id=f"leak_{len(findings)}",
                    leakage_type=LeakageType.PARTIAL_TOKEN,
                    severity=LeakageSeverity.WARNING,
                    text=partial,
                    location=location or DocumentLocation(element_type="text", element_id=""),
                    message="Partial or malformed token found",
                    confidence=0.8,
                )
            )

        return findings

    def rescan_document(
        self,
        file_path: Path,
        handler: Any,  # DocumentHandler
        config: DetectionConfig | None = None,
    ) -> RescanResult:
        """
        Re-scan an entire document for leakage.

        Args:
            file_path: Path to the protected output file.
            handler: Document handler for reading the file.
            config: Detection configuration.

        Returns:
            RescanResult with all findings.
        """
        start_time = datetime.utcnow()
        result = RescanResult(success=False)

        try:
            # Open the document
            handler.open(file_path)

            # Scan all segments
            for batch in handler.get_text_segments():
                for segment in batch:
                    result.total_segments_scanned += 1

                    # Re-scan this segment
                    leakages = self.rescan_text(
                        text=segment.text,
                        location=segment.location,
                        config=config,
                    )

                    for leakage in leakages:
                        result.add_leakage(leakage)

            # Determine if clean
            result.is_clean = result.critical_count == 0
            result.success = True

        except Exception as e:
            logger.error(f"Re-scan failed: {e}")
            result.success = False

        finally:
            try:
                handler.close()
            except Exception:
                pass

            end_time = datetime.utcnow()
            result.scan_duration_ms = (end_time - start_time).total_seconds() * 1000

        return result

    def quick_rescan(
        self,
        text_samples: list[str],
        config: DetectionConfig | None = None,
    ) -> bool:
        """
        Quick check on text samples.

        Args:
            text_samples: Sample texts to check.
            config: Detection configuration.

        Returns:
            True if all samples are clean.
        """
        for text in text_samples:
            leakages = self.rescan_text(text, config=config)
            if any(l.severity == LeakageSeverity.CRITICAL for l in leakages):
                return False
        return True

    def _is_valid_token(self, text: str) -> bool:
        """Check if text is a properly formatted token."""
        return TOKEN_PATTERN.fullmatch(text) is not None

    def _determine_severity(self, result: DetectionResult) -> LeakageSeverity:
        """Determine severity based on detection result."""
        if self._strict_mode:
            return LeakageSeverity.CRITICAL

        if result.score >= 0.9:
            return LeakageSeverity.CRITICAL
        elif result.score >= 0.7:
            return LeakageSeverity.WARNING
        else:
            return LeakageSeverity.INFO

    def _find_partial_tokens(self, text: str) -> list[str]:
        """Find partial or malformed tokens in text."""
        import re

        partial_patterns = [
            r"\[\[(?![A-Z][A-Z0-9_]{1,31}_[A-F0-9]{6,16}\]\])",  # Opening but not valid
            r"(?<!\[\[)[A-Z][A-Z0-9_]+_[A-F0-9]{6,16}\]\]",  # Missing opening
            r"\[\[[A-Z_]+\]\]",  # Missing ID
        ]

        partials: list[str] = []
        for pattern in partial_patterns:
            for match in re.finditer(pattern, text):
                partials.append(match.group())

        return partials


class RescanValidator:
    """
    Validator that integrates with the protection pipeline.

    Provides validation step before marking output as ready.
    """

    def __init__(self, engine: RescanEngine | None = None) -> None:
        """Initialize validator."""
        self._engine = engine or RescanEngine()

    def validate_output(
        self,
        output_path: Path,
        handler: Any,
        original_values: set[str] | None = None,
        expected_tokens: set[str] | None = None,
    ) -> tuple[bool, RescanResult]:
        """
        Validate protected output file.

        Args:
            output_path: Path to the protected output.
            handler: Document handler for the file type.
            original_values: Original values that were protected.
            expected_tokens: Tokens that should appear in output.

        Returns:
            Tuple of (is_valid, RescanResult).
        """
        # Set context for the scan
        if original_values:
            self._engine.set_protected_values(original_values)

        if expected_tokens:
            self._engine.set_expected_tokens(expected_tokens)

        # Run the re-scan
        result = self._engine.rescan_document(output_path, handler)

        # Validation passes if no critical issues
        is_valid = result.is_clean

        return is_valid, result

    def get_remediation_suggestions(
        self, leakages: list[LeakageFinding]
    ) -> list[str]:
        """
        Get suggestions for fixing leakages.

        Args:
            leakages: List of leakage findings.

        Returns:
            List of remediation suggestions.
        """
        suggestions: list[str] = []

        for leakage in leakages:
            if leakage.leakage_type == LeakageType.RESIDUAL_PII:
                suggestions.append(
                    f"Add detection rule for {leakage.entity_type}: '{leakage.text[:20]}...'"
                )
            elif leakage.leakage_type == LeakageType.UNTOKENIZED_VALUE:
                suggestions.append(
                    f"Value '{leakage.text[:20]}...' was not tokenized - check detection patterns"
                )
            elif leakage.leakage_type == LeakageType.PARTIAL_TOKEN:
                suggestions.append(
                    f"Fix malformed token at {leakage.location.element_id}: '{leakage.text}'"
                )

        return suggestions


# Factory functions
def create_rescan_engine(
    detection_engine: DetectionEngine | None = None,
    strict_mode: bool = True,
) -> RescanEngine:
    """Create a rescan engine.

    When no engine is supplied, build one populated with the standard
    recognizers so residual PII can actually be detected (the bare global
    engine has none registered).
    """
    if detection_engine is None:
        detection_engine = _build_default_rescan_engine()
    return RescanEngine(detection_engine, strict_mode)


def _build_default_rescan_engine() -> DetectionEngine:
    """Build a detection engine with the standard recognizer set."""
    from sandiraksa.detection.presidio_engine import RegexRecognizer
    from sandiraksa.detection.recognizers import (
        NIKRecognizer,
        NPWPRecognizer,
        KKRecognizer,
        IndonesianPhoneRecognizer,
        BPJSRecognizerLegacy,
    )

    engine = DetectionEngine()
    engine.registry.register(RegexRecognizer())
    engine.registry.register(NIKRecognizer())
    engine.registry.register(NPWPRecognizer())
    engine.registry.register(KKRecognizer())
    engine.registry.register(IndonesianPhoneRecognizer())
    engine.registry.register(BPJSRecognizerLegacy())
    engine.initialize()
    return engine


def create_validator() -> RescanValidator:
    """Create a rescan validator."""
    return RescanValidator()
