"""
Clipboard detection pipeline (design 39, 40, 42, 43).

Pure, synchronous transformation from a :class:`ScanRequest` to a
:class:`ClipboardProtectionResult`. It is deliberately Qt-free and
thread-agnostic so it can run inside a Tier A QThread worker OR a Tier B
worker process unchanged.

Flow (design 39):
    input validation
      -> size policy (design 42)
      -> Stage 1 deterministic recognizers (design 40)
      -> Stage 2 contextual / NER recognizers (design 40)
      -> finding normalization (design 44)
      -> risk policy (design 46, 47)
      -> text treatment (design 48, 49)
      -> result DTO (design 50)

The engine is injected (built once by the worker, design 27); the pipeline
never constructs or reloads it.
"""

from __future__ import annotations

import time
import uuid

from sandiraksa.clipboard.models import (
    ClipboardProtectionResult,
    Finding,
    ScanRequest,
)
from sandiraksa.clipboard.normalize import normalize_findings
from sandiraksa.clipboard.risk_policy import compute_risk_level, severity_for
from sandiraksa.clipboard.treatment import protect_text
from sandiraksa.detection.shared_scan import detect

# Size limits in bytes of UTF-8 (design 42). Provisional; must be benchmarked.
SOFT_LIMIT = 100 * 1024   # 100 KiB - full automatic scan
HARD_LIMIT = 512 * 1024   # 512 KiB - above this, no automatic scan

#: Result TTL in seconds (design 50).
RESULT_TTL_SECONDS = 30.0


class OversizedError(Exception):
    """Raised when clipboard text exceeds the hard automatic-scan limit."""


def _byte_len(text: str) -> int:
    return len(text.encode("utf-8", errors="surrogatepass"))


def run_pipeline(
    request: ScanRequest,
    engine,
    context,
    *,
    now: float | None = None,
) -> ClipboardProtectionResult:
    """
    Execute the full clipboard detection pipeline.

    Args:
        request: Immutable scan request (design 30).
        engine: A ready DetectionEngine (built once by the worker, design 27).
        context: A DetectionContext whose config this pipeline tunes per stage.
        now: Monotonic time override for testing.

    Returns:
        A TTL-bounded protection result bound to the request generation +
        fingerprint (design 50, 51, 52).

    Raises:
        OversizedError: if the payload exceeds :data:`HARD_LIMIT` (design 42).
    """
    started = time.perf_counter()
    now = time.monotonic() if now is None else now

    text = request.text

    # -- input validation -------------------------------------------------
    if text is None or not text.strip():
        return _empty_result(request, now, started)

    size = _byte_len(text)

    # -- size policy (design 42) -----------------------------------------
    if size > HARD_LIMIT:
        # >512 KiB: no automatic scan; caller offers manual scan.
        raise OversizedError(f"payload {size} bytes exceeds hard limit")

    # -- detection (SHARED with file scanning) ---------------------------
    # Uses the exact same engine, entity set, confidence floor, custom
    # patterns, and deny-list as file scanning so any tweak applies to both.
    matches = detect(engine, context, text)

    # -- map to Findings (severity label is UI-only, not a detection gate) --
    findings: list[Finding] = [
        Finding(
            entity_type=m.entity_type,
            start=m.start,
            end=m.end,
            score=m.score,
            severity=severity_for(m.entity_type),
            text=m.text,
        )
        for m in matches
    ]

    # -- normalization (design 44, 45) -----------------------------------
    findings = normalize_findings(findings)

    # -- risk policy (design 47) -----------------------------------------
    risk = compute_risk_level(findings)

    # -- treatment (design 48, 49) ---------------------------------------
    safe_text = protect_text(text, findings)

    processing_ms = int((time.perf_counter() - started) * 1000)

    return ClipboardProtectionResult(
        result_id=uuid.uuid4().hex,
        generation=request.generation,
        source_fingerprint=request.fingerprint,
        created_monotonic=now,
        expires_monotonic=now + RESULT_TTL_SECONDS,
        risk_level=risk,
        findings=tuple(findings),
        safe_text=safe_text,
        processing_ms=processing_ms,
    )


def _empty_result(
    request: ScanRequest, now: float, started: float
) -> ClipboardProtectionResult:
    from sandiraksa.clipboard.models import ClipboardRiskLevel

    return ClipboardProtectionResult(
        result_id=uuid.uuid4().hex,
        generation=request.generation,
        source_fingerprint=request.fingerprint,
        created_monotonic=now,
        expires_monotonic=now + RESULT_TTL_SECONDS,
        risk_level=ClipboardRiskLevel.LOW,
        findings=(),
        safe_text=request.text or "",
        processing_ms=int((time.perf_counter() - started) * 1000),
    )


__all__ = [
    "run_pipeline",
    "OversizedError",
    "SOFT_LIMIT",
    "HARD_LIMIT",
    "RESULT_TTL_SECONDS",
]
