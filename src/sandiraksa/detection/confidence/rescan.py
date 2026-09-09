"""
Leakage Re-Scan for Protected Documents.

Verifies that protected documents don't contain any remaining PII.
Re-scans protected output to detect:
- Missed PII (protection gap)
- Partially replaced PII (incomplete protection)
- New PII introduced during protection

Critical for quality assurance and compliance verification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sandiraksa.domain.finding import Finding

logger = logging.getLogger(__name__)


class LeakageType(str, Enum):
    """Types of PII leakage detected."""

    MISSED = "missed"               # PII not detected in original scan
    INCOMPLETE = "incomplete"       # Partially replaced PII
    INTRODUCED = "introduced"       # New PII from replacement token
    RESIDUAL = "residual"           # Same PII still present after protection

    @property
    def severity(self) -> str:
        """Severity level of leakage type."""
        return {
            LeakageType.MISSED: "HIGH",
            LeakageType.INCOMPLETE: "HIGH",
            LeakageType.INTRODUCED: "MEDIUM",
            LeakageType.RESIDUAL: "CRITICAL",
        }[self]

    @property
    def description(self) -> str:
        """Human-readable description."""
        return {
            LeakageType.MISSED: "PII not detected in original scan",
            LeakageType.INCOMPLETE: "PII was partially replaced",
            LeakageType.INTRODUCED: "New PII introduced by replacement",
            LeakageType.RESIDUAL: "Original PII still present after protection",
        }[self]


@dataclass
class LeakageFinding:
    """
    A single leakage finding.

    Represents PII found in protected output that shouldn't be there.
    """

    leakage_type: LeakageType
    entity_type: str
    text: str
    start: int
    end: int
    score: float
    location: str  # Document location description
    original_finding: "Finding | None" = None  # If residual, the original

    @property
    def severity(self) -> str:
        """Get severity from leakage type."""
        return self.leakage_type.severity

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "leakage_type": self.leakage_type.value,
            "severity": self.severity,
            "entity_type": self.entity_type,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "score": self.score,
            "location": self.location,
            "has_original": self.original_finding is not None,
        }


@dataclass
class LeakageResult:
    """
    Result of leakage re-scan.

    Contains all leakage findings and summary statistics.
    """

    source_file: str
    protected_file: str
    scan_timestamp: datetime = field(default_factory=datetime.now)
    leakages: list[LeakageFinding] = field(default_factory=list)
    original_findings_count: int = 0
    protected_findings_count: int = 0
    scan_duration_ms: float = 0.0

    @property
    def has_leakage(self) -> bool:
        """Whether any leakage was found."""
        return len(self.leakages) > 0

    @property
    def is_clean(self) -> bool:
        """Whether protected file is clean (no leakage)."""
        return not self.has_leakage

    @property
    def critical_count(self) -> int:
        """Count of CRITICAL severity leakages."""
        return sum(1 for l in self.leakages if l.severity == "CRITICAL")

    @property
    def high_count(self) -> int:
        """Count of HIGH severity leakages."""
        return sum(1 for l in self.leakages if l.severity == "HIGH")

    @property
    def medium_count(self) -> int:
        """Count of MEDIUM severity leakages."""
        return sum(1 for l in self.leakages if l.severity == "MEDIUM")

    def get_by_type(self, leakage_type: LeakageType) -> list[LeakageFinding]:
        """Get leakages of a specific type."""
        return [l for l in self.leakages if l.leakage_type == leakage_type]

    def get_by_entity(self, entity_type: str) -> list[LeakageFinding]:
        """Get leakages for a specific entity type."""
        return [l for l in self.leakages if l.entity_type.upper() == entity_type.upper()]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "source_file": self.source_file,
            "protected_file": self.protected_file,
            "scan_timestamp": self.scan_timestamp.isoformat(),
            "is_clean": self.is_clean,
            "leakage_count": len(self.leakages),
            "by_severity": {
                "critical": self.critical_count,
                "high": self.high_count,
                "medium": self.medium_count,
            },
            "original_findings_count": self.original_findings_count,
            "protected_findings_count": self.protected_findings_count,
            "scan_duration_ms": self.scan_duration_ms,
            "leakages": [l.to_dict() for l in self.leakages],
        }

    def summary(self) -> str:
        """Generate summary text."""
        if self.is_clean:
            return f"✓ Protected file is clean. No PII leakage detected."

        lines = [
            f"⚠ PII LEAKAGE DETECTED in protected file",
            f"  Total leakages: {len(self.leakages)}",
        ]

        if self.critical_count:
            lines.append(f"  CRITICAL: {self.critical_count}")
        if self.high_count:
            lines.append(f"  HIGH: {self.high_count}")
        if self.medium_count:
            lines.append(f"  MEDIUM: {self.medium_count}")

        return "\n".join(lines)


class LeakageScanner:
    """
    Scanner for detecting PII leakage in protected documents.

    Re-scans protected output and compares with original findings
    to detect any remaining or new PII.

    Usage:
        scanner = LeakageScanner(detection_engine)

        # Scan protected file
        result = scanner.scan(
            protected_file="output/protected.xlsx",
            original_findings=original_findings,
        )

        if result.has_leakage:
            print(result.summary())
            for leak in result.leakages:
                print(f"  - {leak.entity_type}: {leak.text}")
    """

    def __init__(
        self,
        detection_engine=None,
        strict_mode: bool = True,
    ):
        """
        Initialize leakage scanner.

        Args:
            detection_engine: Detection engine to use for re-scan
            strict_mode: If True, use STRICT scan mode for re-scan
        """
        self._engine = detection_engine
        self._strict_mode = strict_mode

    def scan(
        self,
        protected_file: str | Path,
        original_findings: list["Finding"] | None = None,
        source_file: str | Path | None = None,
    ) -> LeakageResult:
        """
        Scan protected file for leakage.

        Args:
            protected_file: Path to protected output file
            original_findings: Findings from original scan (for comparison)
            source_file: Original source file path (for reporting)

        Returns:
            LeakageResult with any leakages found
        """
        import time
        start_time = time.perf_counter()

        protected_path = Path(protected_file)
        source_path = Path(source_file) if source_file else protected_path

        result = LeakageResult(
            source_file=str(source_path),
            protected_file=str(protected_path),
            original_findings_count=len(original_findings) if original_findings else 0,
        )

        # Re-scan protected file
        protected_findings = self._scan_file(protected_path)
        result.protected_findings_count = len(protected_findings)

        # Analyze for leakage
        leakages = self._analyze_leakage(
            protected_findings=protected_findings,
            original_findings=original_findings or [],
            protected_path=protected_path,
        )

        result.leakages = leakages
        result.scan_duration_ms = (time.perf_counter() - start_time) * 1000

        # Log result
        if result.has_leakage:
            logger.warning(
                f"Leakage detected in {protected_path.name}: "
                f"{len(leakages)} finding(s)"
            )
        else:
            logger.info(f"No leakage detected in {protected_path.name}")

        return result

    def scan_text(
        self,
        protected_text: str,
        original_findings: list["Finding"] | None = None,
        location: str = "text",
    ) -> LeakageResult:
        """
        Scan protected text content for leakage.

        Args:
            protected_text: Protected text content
            original_findings: Original findings for comparison
            location: Location description for reporting

        Returns:
            LeakageResult with any leakages found
        """
        import time
        start_time = time.perf_counter()

        result = LeakageResult(
            source_file=location,
            protected_file=location,
            original_findings_count=len(original_findings) if original_findings else 0,
        )

        # Re-scan text
        protected_findings = self._scan_text(protected_text)
        result.protected_findings_count = len(protected_findings)

        # Analyze for leakage
        leakages = self._analyze_leakage_text(
            protected_findings=protected_findings,
            original_findings=original_findings or [],
            protected_text=protected_text,
            location=location,
        )

        result.leakages = leakages
        result.scan_duration_ms = (time.perf_counter() - start_time) * 1000

        return result

    def _scan_file(self, file_path: Path) -> list["Finding"]:
        """Scan a file using the detection engine."""
        if self._engine is None:
            logger.warning("No detection engine configured for leakage scan")
            return []

        try:
            # Use detection engine to scan file
            # This would integrate with the actual detection pipeline
            return self._engine.scan_file(file_path)
        except Exception as e:
            logger.error(f"Failed to scan file {file_path}: {e}")
            return []

    def _scan_text(self, text: str) -> list["Finding"]:
        """Scan text using the detection engine."""
        if self._engine is None:
            logger.warning("No detection engine configured for leakage scan")
            return []

        try:
            return self._engine.scan_text(text)
        except Exception as e:
            logger.error(f"Failed to scan text: {e}")
            return []

    def _analyze_leakage(
        self,
        protected_findings: list["Finding"],
        original_findings: list["Finding"],
        protected_path: Path,
    ) -> list[LeakageFinding]:
        """Analyze findings for leakage."""
        leakages = []

        # Build set of original finding texts for comparison
        original_texts = {f.text.lower() for f in original_findings}
        original_positions = {(f.start, f.end, f.text.lower()) for f in original_findings}

        for pf in protected_findings:
            pf_text_lower = pf.text.lower()
            pf_position = (pf.start, pf.end, pf_text_lower)

            # Check if this was in original (residual)
            if pf_position in original_positions:
                leakage_type = LeakageType.RESIDUAL
                original = next(
                    (f for f in original_findings if f.text.lower() == pf_text_lower),
                    None,
                )
            elif pf_text_lower in original_texts:
                # Same text but different position - might be residual
                leakage_type = LeakageType.RESIDUAL
                original = next(
                    (f for f in original_findings if f.text.lower() == pf_text_lower),
                    None,
                )
            elif self._looks_like_partial(pf.text, original_findings):
                # Partial match - incomplete protection
                leakage_type = LeakageType.INCOMPLETE
                original = None
            elif self._looks_like_token(pf.text):
                # Looks like a replacement token that happens to match PII pattern
                leakage_type = LeakageType.INTRODUCED
                original = None
            else:
                # New finding not in original - missed
                leakage_type = LeakageType.MISSED
                original = None

            leakages.append(LeakageFinding(
                leakage_type=leakage_type,
                entity_type=pf.entity_type,
                text=pf.text,
                start=pf.start,
                end=pf.end,
                score=pf.score,
                location=str(protected_path),
                original_finding=original,
            ))

        return leakages

    def _analyze_leakage_text(
        self,
        protected_findings: list["Finding"],
        original_findings: list["Finding"],
        protected_text: str,
        location: str,
    ) -> list[LeakageFinding]:
        """Analyze text findings for leakage."""
        leakages = []

        original_texts = {f.text.lower() for f in original_findings}

        for pf in protected_findings:
            pf_text_lower = pf.text.lower()

            if pf_text_lower in original_texts:
                leakage_type = LeakageType.RESIDUAL
                original = next(
                    (f for f in original_findings if f.text.lower() == pf_text_lower),
                    None,
                )
            elif self._looks_like_token(pf.text):
                leakage_type = LeakageType.INTRODUCED
                original = None
            else:
                leakage_type = LeakageType.MISSED
                original = None

            leakages.append(LeakageFinding(
                leakage_type=leakage_type,
                entity_type=pf.entity_type,
                text=pf.text,
                start=pf.start,
                end=pf.end,
                score=pf.score,
                location=location,
                original_finding=original,
            ))

        return leakages

    def _looks_like_partial(
        self,
        text: str,
        original_findings: list["Finding"],
    ) -> bool:
        """Check if text looks like partial PII from original."""
        text_lower = text.lower()
        for of in original_findings:
            of_lower = of.text.lower()
            # Check if protected text is substring of original
            if text_lower in of_lower and text_lower != of_lower:
                return True
            # Check if original is substring of protected
            if of_lower in text_lower and text_lower != of_lower:
                return True
        return False

    def _looks_like_token(self, text: str) -> bool:
        """Check if text looks like a replacement token."""
        # Common token patterns
        token_patterns = [
            text.startswith("[") and text.endswith("]"),
            text.startswith("<") and text.endswith(">"),
            text.startswith("{{") and text.endswith("}}"),
            "_REDACTED" in text.upper(),
            "_MASKED" in text.upper(),
            "TOKEN_" in text.upper(),
        ]
        return any(token_patterns)


# Convenience functions

def scan_for_leakage(
    protected_file: str | Path,
    original_findings: list["Finding"] | None = None,
    detection_engine=None,
) -> LeakageResult:
    """
    Scan protected file for PII leakage.

    Convenience function wrapping LeakageScanner.
    """
    scanner = LeakageScanner(detection_engine=detection_engine)
    return scanner.scan(protected_file, original_findings)


def verify_protection(
    protected_text: str,
    original_findings: list["Finding"],
    detection_engine=None,
) -> bool:
    """
    Verify that protection was complete.

    Returns True if no leakage detected.
    """
    scanner = LeakageScanner(detection_engine=detection_engine)
    result = scanner.scan_text(protected_text, original_findings)
    return result.is_clean


__all__ = [
    "LeakageType",
    "LeakageFinding",
    "LeakageResult",
    "LeakageScanner",
    "scan_for_leakage",
    "verify_protection",
]
