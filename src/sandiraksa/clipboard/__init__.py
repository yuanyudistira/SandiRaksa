"""
SandiRaksa Clipboard Privacy Guard.

Real-time clipboard PII protection subsystem.

Design reference:
    SandiRaksa-Clipboard-Privacy-Guard-Technical-Design-v2.1-Production-Hardened.md

Architecture principles (enforced across this package):
    * Detection never runs on the GUI thread (design 5.1, 5.2).
    * Clipboard content is untrusted input (design 5.4).
    * Raw clipboard text is never persisted or logged (design 32, 59-61).
    * Stale results must never overwrite newer clipboard content
      (design 17, 51, 52) - enforced via generation + fingerprint checks.
"""

from sandiraksa.clipboard.models import (
    ClipboardCapability,
    ClipboardMonitorState,
    ClipboardRiskLevel,
    ClipboardSnapshot,
    DetectionSource,
    Finding,
    PendingOwnWrite,
    ScanFailure,
    ScanRequest,
    ClipboardProtectionResult,
    WorkerState,
    fingerprint_text,
)
from sandiraksa.clipboard.coalescer import EventCoalescer

__all__ = [
    "ClipboardCapability",
    "ClipboardMonitorState",
    "WorkerState",
    "ClipboardRiskLevel",
    "DetectionSource",
    "ClipboardSnapshot",
    "ScanRequest",
    "ScanFailure",
    "PendingOwnWrite",
    "Finding",
    "ClipboardProtectionResult",
    "fingerprint_text",
    "EventCoalescer",
]
