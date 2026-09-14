"""
Clipboard Privacy Guard domain model.

Enums, immutable snapshots, and DTOs shared across the GUI thread, the
detection worker, and (in Tier B) the worker process/IPC boundary.

All request/result/failure DTOs are frozen so they can be passed across
threads and processes as immutable messages (design 30, 31, 50, 60).

Design references are cited inline (e.g. "design 16").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from sandiraksa.clipboard.fingerprint import fingerprint_text


# --------------------------------------------------------------------------
# Capability model (design 7)
# --------------------------------------------------------------------------
class ClipboardCapability(Enum):
    """How reliably clipboard changes can be observed on this platform."""

    #: Background clipboard changes are observed reliably (Windows, X11, ...).
    REALTIME_BACKGROUND = "realtime_background"
    #: Only user-initiated "Scan current clipboard" works (restricted Wayland,
    #: denied macOS permission, sandbox).
    USER_INITIATED_ONLY = "user_initiated_only"
    #: Clipboard access is unavailable; protection cannot run.
    UNAVAILABLE = "unavailable"


# --------------------------------------------------------------------------
# Monitor state machine (design 8)
# --------------------------------------------------------------------------
class ClipboardMonitorState(Enum):
    """Lifecycle state of the clipboard monitor."""

    OFF = "off"
    STARTING = "starting"
    ACTIVE = "active"
    PAUSED = "paused"
    DEGRADED = "degraded"
    USER_INITIATED_ONLY = "user_initiated_only"
    PERMISSION_REQUIRED = "permission_required"
    UNSUPPORTED = "unsupported"
    ERROR = "error"
    STOPPING = "stopping"


# --------------------------------------------------------------------------
# Worker state machine (design 9)
# --------------------------------------------------------------------------
class WorkerState(Enum):
    """Lifecycle state of the detection worker (thread or process)."""

    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    SCANNING = "scanning"
    DEGRADED = "degraded"
    ERROR = "error"
    STOPPING = "stopping"


# --------------------------------------------------------------------------
# Risk levels (design 47)
# --------------------------------------------------------------------------
class ClipboardRiskLevel(Enum):
    """Overall risk of a clipboard payload."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        """Numeric rank for comparison/aggregation (higher = riskier)."""
        return {
            ClipboardRiskLevel.LOW: 0,
            ClipboardRiskLevel.MEDIUM: 1,
            ClipboardRiskLevel.HIGH: 2,
            ClipboardRiskLevel.CRITICAL: 3,
        }[self]


# --------------------------------------------------------------------------
# Detection source (design 41)
# --------------------------------------------------------------------------
class DetectionSource(Enum):
    """Where a detection request originated, so config can tune behavior."""

    FILE = "file"
    CLIPBOARD = "clipboard"


# --------------------------------------------------------------------------
# Clipboard event identity (design 16)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ClipboardSnapshot:
    """
    An immutable observed clipboard version.

    Every observed version gets a monotonically increasing generation number,
    a content fingerprint, and a monotonic timestamp (design 16, 17).
    """

    generation: int
    fingerprint: str
    observed_at_monotonic: float
    text: str

    @classmethod
    def create(
        cls,
        generation: int,
        text: str,
        observed_at_monotonic: float,
    ) -> "ClipboardSnapshot":
        """Build a snapshot, computing the fingerprint from text."""
        return cls(
            generation=generation,
            fingerprint=fingerprint_text(text),
            observed_at_monotonic=observed_at_monotonic,
            text=text,
        )


# --------------------------------------------------------------------------
# Feedback-loop protection (design 19)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PendingOwnWrite:
    """
    Records a clipboard write SandiRaksa itself performed, so the resulting
    self-generated change event can be ignored (design 19).

    Uses an expected fingerprint + TTL rather than a single boolean skip flag,
    so a legitimate rapid user change is not swallowed.
    """

    fingerprint: str
    expires_at_monotonic: float
    operation_id: str

    def matches(self, fingerprint: str, now_monotonic: float) -> bool:
        """True if this pending self-write matches and has not expired."""
        return (
            self.fingerprint == fingerprint
            and now_monotonic <= self.expires_at_monotonic
        )


# --------------------------------------------------------------------------
# Scan request (design 30) - immutable message to the worker
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ScanRequest:
    """Immutable request enqueued for the detection worker (design 5.2, 30)."""

    request_id: str
    generation: int
    fingerprint: str
    text: str
    created_monotonic: float
    #: Protocol version, meaningful for the Tier B IPC boundary (design 30).
    protocol_version: int = 1
    source: DetectionSource = DetectionSource.CLIPBOARD


# --------------------------------------------------------------------------
# Finding (privacy-safe finding record surfaced to the GUI)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Finding:
    """
    A normalized detection finding.

    Carries the matched span so treatment can redact it, plus severity/score
    for risk aggregation. This crosses the worker->GUI boundary; the raw
    ``text`` slice is only present so the GUI can render a protected preview
    and is never logged (design 59-61).
    """

    entity_type: str
    start: int
    end: int
    score: float
    severity: str  # low | medium | high | critical
    text: str = ""

    @property
    def length(self) -> int:
        return self.end - self.start


# --------------------------------------------------------------------------
# Sanitized scan failure (design 60) - never carries raw text
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ScanFailure:
    """
    Sanitized failure record. Deliberately excludes raw clipboard text,
    locals, and tracebacks so nothing sensitive leaks through error paths
    (design 60, 61).
    """

    category: str
    message: str
    generation: int
    latency_ms: int | None = None

    @classmethod
    def from_exception(
        cls,
        exc: BaseException,
        *,
        generation: int,
        latency_ms: int | None = None,
    ) -> "ScanFailure":
        """
        Build a sanitized failure from an exception.

        Only the exception *type name* and a short, non-text message are kept.
        The original exception object (which may capture locals containing raw
        clipboard text) is intentionally not stored.
        """
        return cls(
            category=type(exc).__name__,
            message=str(exc)[:200],
            generation=generation,
            latency_ms=latency_ms,
        )


# --------------------------------------------------------------------------
# Protection result (design 50) - immutable, TTL-bounded
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ClipboardProtectionResult:
    """
    Result of scanning + treating one clipboard payload (design 50).

    Bound to the originating generation + fingerprint so the GUI can reject it
    if the clipboard has since changed (design 51, 52). TTL-bounded so a late
    result is discarded rather than shown (design 37, 50).
    """

    result_id: str
    generation: int
    source_fingerprint: str
    created_monotonic: float
    expires_monotonic: float
    risk_level: ClipboardRiskLevel
    findings: tuple[Finding, ...]
    safe_text: str
    processing_ms: int = 0

    def is_expired(self, now_monotonic: float) -> bool:
        """True if this result has passed its TTL (design 37, 50)."""
        return now_monotonic > self.expires_monotonic

    def entity_counts(self) -> dict[str, int]:
        """Count findings by entity type for privacy-safe UI/metadata."""
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.entity_type] = counts.get(f.entity_type, 0) + 1
        return counts


__all__ = [
    "ClipboardCapability",
    "ClipboardMonitorState",
    "WorkerState",
    "ClipboardRiskLevel",
    "DetectionSource",
    "ClipboardSnapshot",
    "PendingOwnWrite",
    "ScanRequest",
    "Finding",
    "ScanFailure",
    "ClipboardProtectionResult",
    "fingerprint_text",
]
