"""
Privacy-safe logging helpers for the clipboard subsystem (design 59, 60, 61).

Raw clipboard content must NEVER be written to logs. These helpers only ever
emit approved metadata: timestamp, backend, capability, risk level, entity
types/counts, a coarse text-length bucket, latency, generation, error category
(design 59).

Use :func:`log_scan_metadata` / :func:`log_failure` instead of ad-hoc logging
so no code path accidentally logs the payload.
"""

from __future__ import annotations

import logging

from sandiraksa.clipboard.fingerprint import length_bucket
from sandiraksa.clipboard.models import (
    ClipboardProtectionResult,
    ScanFailure,
)

logger = logging.getLogger("sandiraksa.clipboard")


def log_scan_metadata(
    result: ClipboardProtectionResult,
    *,
    backend: str,
    text_length: int,
) -> None:
    """Log approved, non-sensitive metadata about a completed scan."""
    logger.info(
        "clipboard scan: backend=%s risk=%s entities=%s len_bucket=%s "
        "latency_ms=%d generation=%d",
        backend,
        result.risk_level.value,
        _counts_str(result.entity_counts()),
        length_bucket(text_length),
        result.processing_ms,
        result.generation,
    )


def log_failure(failure: ScanFailure, *, backend: str) -> None:
    """Log a sanitized scan failure (never contains raw text; design 60)."""
    logger.warning(
        "clipboard scan failed: backend=%s category=%s generation=%d "
        "latency_ms=%s msg=%s",
        backend,
        failure.category,
        failure.generation,
        failure.latency_ms,
        failure.message,
    )


def _counts_str(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ",".join(f"{k}:{v}" for k, v in sorted(counts.items()))


__all__ = ["log_scan_metadata", "log_failure", "logger"]
