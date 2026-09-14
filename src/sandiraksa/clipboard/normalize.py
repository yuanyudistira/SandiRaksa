"""
Finding normalization and overlap resolution (design 44, 45).

Before treatment we must not apply every raw detection blindly (design 44):
offsets are validated, exact duplicates removed, overlaps resolved by a defined
precedence, and the result sorted by span so replacement is unambiguous.

Overlap precedence (design 45):
    1. higher severity
    2. higher confidence (score)
    3. longer span
"""

from __future__ import annotations

from sandiraksa.clipboard.models import Finding

# Severity rank for overlap comparison (design 45).
_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _sev_rank(f: Finding) -> int:
    return _SEVERITY_RANK.get(f.severity, 1)


def _better(a: Finding, b: Finding) -> Finding:
    """Return the finding that wins an overlap per precedence (design 45)."""
    if _sev_rank(a) != _sev_rank(b):
        return a if _sev_rank(a) > _sev_rank(b) else b
    if a.score != b.score:
        return a if a.score > b.score else b
    if a.length != b.length:
        return a if a.length > b.length else b
    # Stable: prefer the earlier-starting one.
    return a if a.start <= b.start else b


def _valid_offsets(f: Finding) -> bool:
    return 0 <= f.start < f.end


def normalize_findings(findings: list[Finding]) -> list[Finding]:
    """
    Validate, dedupe, resolve overlaps, and sort findings (design 44, 45).

    Returns a list sorted by ``start`` with no overlapping spans.
    """
    # 1. validate offsets.
    valid = [f for f in findings if _valid_offsets(f)]
    if not valid:
        return []

    # 2. deduplicate exact spans of the same entity type (keep highest score).
    dedup: dict[tuple, Finding] = {}
    for f in valid:
        key = (f.entity_type, f.start, f.end)
        existing = dedup.get(key)
        if existing is None or f.score > existing.score:
            dedup[key] = f
    candidates = list(dedup.values())

    # 3. resolve overlaps. Process by (start asc, longer span first) and keep a
    #    running list of accepted non-overlapping spans.
    candidates.sort(key=lambda f: (f.start, -(f.length)))
    accepted: list[Finding] = []
    for f in candidates:
        conflict_idx = None
        for i, kept in enumerate(accepted):
            if f.start < kept.end and kept.start < f.end:  # overlap
                conflict_idx = i
                break
        if conflict_idx is None:
            accepted.append(f)
        else:
            winner = _better(accepted[conflict_idx], f)
            accepted[conflict_idx] = winner

    # 4. sort by span for deterministic downstream replacement.
    accepted.sort(key=lambda f: (f.start, f.end))
    return accepted


__all__ = ["normalize_findings"]
