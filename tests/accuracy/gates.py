"""
Release Gates for PII Detection Quality.

Defines minimum quality thresholds that must be met before release.
Each entity type has required F1 scores based on criticality.

Gate Levels:
- CRITICAL: Must pass for release (F1 >= threshold required)
- HIGH: Should pass, warning if not
- MEDIUM: Informational, tracks for improvement
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.accuracy.metrics import AccuracyReport

logger = logging.getLogger(__name__)


class GateLevel(str, Enum):
    """Importance level of a release gate."""

    CRITICAL = "critical"   # Must pass for release
    HIGH = "high"           # Should pass, warning if not
    MEDIUM = "medium"       # Informational


class GateStatus(str, Enum):
    """Status of a gate check."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class GateDefinition:
    """
    Definition of a release gate.

    Attributes:
        entity_type: Entity type to check
        min_f1: Minimum F1 score required
        min_precision: Minimum precision (optional)
        min_recall: Minimum recall (optional)
        level: Importance level
        description: Human-readable description
    """

    entity_type: str
    min_f1: float
    min_precision: float | None = None
    min_recall: float | None = None
    level: GateLevel = GateLevel.HIGH
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "min_f1": self.min_f1,
            "min_precision": self.min_precision,
            "min_recall": self.min_recall,
            "level": self.level.value,
            "description": self.description,
        }


@dataclass
class GateResult:
    """
    Result of checking a single gate.

    Attributes:
        gate: The gate definition
        status: Pass/fail status
        actual_f1: Actual F1 score achieved
        actual_precision: Actual precision achieved
        actual_recall: Actual recall achieved
        message: Result message
    """

    gate: GateDefinition
    status: GateStatus
    actual_f1: float = 0.0
    actual_precision: float = 0.0
    actual_recall: float = 0.0
    message: str = ""

    @property
    def passed(self) -> bool:
        return self.status == GateStatus.PASSED

    @property
    def failed(self) -> bool:
        return self.status == GateStatus.FAILED

    def to_dict(self) -> dict:
        return {
            "entity_type": self.gate.entity_type,
            "level": self.gate.level.value,
            "status": self.status.value,
            "required_f1": self.gate.min_f1,
            "actual_f1": round(self.actual_f1, 4),
            "actual_precision": round(self.actual_precision, 4),
            "actual_recall": round(self.actual_recall, 4),
            "message": self.message,
        }


@dataclass
class ReleaseGateReport:
    """
    Complete report of all gate checks.

    Attributes:
        results: List of gate check results
        overall_passed: Whether release can proceed
        critical_failed: Number of critical gates that failed
        high_failed: Number of high-level gates that failed
    """

    results: list[GateResult] = field(default_factory=list)
    checked_at: datetime = field(default_factory=datetime.now)

    @property
    def overall_passed(self) -> bool:
        """True if all critical gates passed."""
        return all(
            r.passed for r in self.results
            if r.gate.level == GateLevel.CRITICAL
        )

    @property
    def critical_failed(self) -> int:
        """Count of failed critical gates."""
        return sum(
            1 for r in self.results
            if r.gate.level == GateLevel.CRITICAL and r.failed
        )

    @property
    def high_failed(self) -> int:
        """Count of failed high-level gates."""
        return sum(
            1 for r in self.results
            if r.gate.level == GateLevel.HIGH and r.failed
        )

    @property
    def total_passed(self) -> int:
        """Count of passed gates."""
        return sum(1 for r in self.results if r.passed)

    @property
    def total_failed(self) -> int:
        """Count of failed gates."""
        return sum(1 for r in self.results if r.failed)

    def get_results_by_status(self, status: GateStatus) -> list[GateResult]:
        """Get results with a specific status."""
        return [r for r in self.results if r.status == status]

    def to_dict(self) -> dict:
        return {
            "overall_passed": self.overall_passed,
            "critical_failed": self.critical_failed,
            "high_failed": self.high_failed,
            "total_passed": self.total_passed,
            "total_failed": self.total_failed,
            "checked_at": self.checked_at.isoformat(),
            "results": [r.to_dict() for r in self.results],
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=" * 70,
            "RELEASE GATE CHECK REPORT",
            "=" * 70,
            f"Checked at: {self.checked_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        if self.overall_passed:
            lines.append("✅ RELEASE GATES PASSED - Ready for release")
        else:
            lines.append("❌ RELEASE GATES FAILED - Not ready for release")
            lines.append(f"   Critical failures: {self.critical_failed}")

        lines.extend([
            "",
            f"Summary: {self.total_passed} passed, {self.total_failed} failed",
            "",
            "-" * 70,
            f"{'Entity':<20} {'Level':<10} {'Status':<10} {'Req F1':>8} {'Act F1':>8} {'Gap':>8}",
            "-" * 70,
        ])

        for r in sorted(self.results, key=lambda x: (x.gate.level.value, x.gate.entity_type)):
            gap = r.actual_f1 - r.gate.min_f1
            gap_str = f"{gap:+.2%}" if gap != 0 else "0.00%"

            status_icon = "✅" if r.passed else ("⚠️" if r.status == GateStatus.WARNING else "❌")

            lines.append(
                f"{r.gate.entity_type:<20} "
                f"{r.gate.level.value:<10} "
                f"{status_icon} {r.status.value:<7} "
                f"{r.gate.min_f1:>7.0%} "
                f"{r.actual_f1:>7.2%} "
                f"{gap_str:>8}"
            )

        lines.append("=" * 70)
        return "\n".join(lines)


# ============== Default Gate Definitions ==============

# Critical Indonesian PII - must have high accuracy
CRITICAL_GATES = [
    GateDefinition(
        entity_type="ID_NIK",
        min_f1=0.95,
        min_precision=0.95,
        level=GateLevel.CRITICAL,
        description="Indonesian National ID (NIK) - 16 digits",
    ),
    GateDefinition(
        entity_type="ID_NPWP",
        min_f1=0.90,
        min_precision=0.90,
        level=GateLevel.CRITICAL,
        description="Indonesian Tax ID (NPWP)",
    ),
    GateDefinition(
        entity_type="EMAIL_ADDRESS",
        min_f1=0.95,
        min_precision=0.95,
        level=GateLevel.CRITICAL,
        description="Email addresses",
    ),
]

# High importance - should pass
HIGH_GATES = [
    GateDefinition(
        entity_type="ID_PHONE",
        min_f1=0.90,
        min_precision=0.85,
        level=GateLevel.HIGH,
        description="Indonesian phone numbers",
    ),
    GateDefinition(
        entity_type="ID_KK",
        min_f1=0.90,
        level=GateLevel.HIGH,
        description="Family Card (KK) number",
    ),
    GateDefinition(
        entity_type="PERSON",
        min_f1=0.80,
        min_recall=0.85,
        level=GateLevel.HIGH,
        description="Person names (Indonesian)",
    ),
    GateDefinition(
        entity_type="ID_BPJS",
        min_f1=0.85,
        level=GateLevel.HIGH,
        description="BPJS health insurance number",
    ),
]

# Medium importance - informational
MEDIUM_GATES = [
    GateDefinition(
        entity_type="LOCATION",
        min_f1=0.70,
        level=GateLevel.MEDIUM,
        description="Locations/addresses",
    ),
    GateDefinition(
        entity_type="ORGANIZATION",
        min_f1=0.70,
        level=GateLevel.MEDIUM,
        description="Organization names",
    ),
    GateDefinition(
        entity_type="CREDIT_CARD",
        min_f1=0.90,
        level=GateLevel.MEDIUM,
        description="Credit card numbers",
    ),
]

# All default gates
DEFAULT_GATES = CRITICAL_GATES + HIGH_GATES + MEDIUM_GATES


class ReleaseGateChecker:
    """
    Checker for release quality gates.

    Validates detection accuracy against defined thresholds.
    """

    def __init__(
        self,
        gates: list[GateDefinition] | None = None,
        strict_mode: bool = False,
    ):
        """
        Initialize checker.

        Args:
            gates: Gate definitions (uses defaults if None)
            strict_mode: If True, HIGH gates also block release
        """
        self._gates = gates or DEFAULT_GATES
        self._strict_mode = strict_mode

    def check(self, report: "AccuracyReport") -> ReleaseGateReport:
        """
        Check accuracy report against all gates.

        Args:
            report: AccuracyReport from accuracy evaluation

        Returns:
            ReleaseGateReport with all results
        """
        gate_report = ReleaseGateReport()

        for gate in self._gates:
            result = self._check_gate(gate, report)
            gate_report.results.append(result)

        # Log summary
        if gate_report.overall_passed:
            logger.info("All critical release gates passed")
        else:
            logger.warning(
                f"Release gates failed: {gate_report.critical_failed} critical, "
                f"{gate_report.high_failed} high"
            )

        return gate_report

    def _check_gate(
        self,
        gate: GateDefinition,
        report: "AccuracyReport",
    ) -> GateResult:
        """Check a single gate against the report."""
        metrics = report.get_entity_metrics(gate.entity_type)

        # Skip if no data for this entity type
        if metrics.total_annotations == 0 and metrics.total_predictions == 0:
            return GateResult(
                gate=gate,
                status=GateStatus.SKIPPED,
                message=f"No data for {gate.entity_type}",
            )

        actual_f1 = metrics.f1_score
        actual_precision = metrics.precision
        actual_recall = metrics.recall

        # Check F1 threshold
        f1_passed = actual_f1 >= gate.min_f1

        # Check precision threshold if specified
        precision_passed = True
        if gate.min_precision is not None:
            precision_passed = actual_precision >= gate.min_precision

        # Check recall threshold if specified
        recall_passed = True
        if gate.min_recall is not None:
            recall_passed = actual_recall >= gate.min_recall

        # Determine status
        all_passed = f1_passed and precision_passed and recall_passed

        if all_passed:
            status = GateStatus.PASSED
            message = f"{gate.entity_type}: F1={actual_f1:.2%} >= {gate.min_f1:.0%}"
        elif gate.level == GateLevel.MEDIUM:
            status = GateStatus.WARNING
            message = f"{gate.entity_type}: F1={actual_f1:.2%} < {gate.min_f1:.0%} (warning)"
        else:
            status = GateStatus.FAILED
            failures = []
            if not f1_passed:
                failures.append(f"F1={actual_f1:.2%} < {gate.min_f1:.0%}")
            if not precision_passed:
                failures.append(f"Precision={actual_precision:.2%} < {gate.min_precision:.0%}")
            if not recall_passed:
                failures.append(f"Recall={actual_recall:.2%} < {gate.min_recall:.0%}")
            message = f"{gate.entity_type}: " + ", ".join(failures)

        return GateResult(
            gate=gate,
            status=status,
            actual_f1=actual_f1,
            actual_precision=actual_precision,
            actual_recall=actual_recall,
            message=message,
        )

    def add_gate(self, gate: GateDefinition) -> None:
        """Add a custom gate."""
        self._gates.append(gate)

    def get_gate(self, entity_type: str) -> GateDefinition | None:
        """Get gate definition for an entity type."""
        for gate in self._gates:
            if gate.entity_type == entity_type:
                return gate
        return None


# ============== Convenience Functions ==============

def check_release_gates(
    report: "AccuracyReport",
    gates: list[GateDefinition] | None = None,
) -> ReleaseGateReport:
    """
    Check accuracy report against release gates.

    Convenience function wrapping ReleaseGateChecker.

    Args:
        report: AccuracyReport from evaluation
        gates: Optional custom gates

    Returns:
        ReleaseGateReport
    """
    checker = ReleaseGateChecker(gates=gates)
    return checker.check(report)


def is_release_ready(report: "AccuracyReport") -> bool:
    """
    Quick check if accuracy meets release requirements.

    Args:
        report: AccuracyReport from evaluation

    Returns:
        True if ready for release
    """
    gate_report = check_release_gates(report)
    return gate_report.overall_passed


def get_blocking_gates(report: "AccuracyReport") -> list[GateResult]:
    """
    Get list of gates blocking release.

    Args:
        report: AccuracyReport from evaluation

    Returns:
        List of failed critical gates
    """
    gate_report = check_release_gates(report)
    return [
        r for r in gate_report.results
        if r.failed and r.gate.level == GateLevel.CRITICAL
    ]


__all__ = [
    "GateLevel",
    "GateStatus",
    "GateDefinition",
    "GateResult",
    "ReleaseGateReport",
    "ReleaseGateChecker",
    "check_release_gates",
    "is_release_ready",
    "get_blocking_gates",
    "CRITICAL_GATES",
    "HIGH_GATES",
    "MEDIUM_GATES",
    "DEFAULT_GATES",
]
