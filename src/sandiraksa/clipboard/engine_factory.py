"""
Detection engine construction for the clipboard subsystem (design 27).

Delegates to :mod:`sandiraksa.detection.shared_scan`, the single source of
truth shared with file scanning, so clipboard and file detection use the exact
same engine, recognizers, entity set, and confidence floor (design 40: do not
fork a clipboard-only recognizer codebase). The engine is built ONCE per worker
and reused across every scan (design 27).
"""

from __future__ import annotations

from sandiraksa.detection.shared_scan import (
    FULL_CONTENT_ENTITIES,
    build_context as _shared_build_context,
    build_engine as _shared_build_engine,
)


def build_engine():
    """Build the canonical DetectionEngine (shared with file scanning)."""
    return _shared_build_engine()


def build_context(project_id: str | None = None):
    """Build a reusable full-content DetectionContext for clipboard scans."""
    return _shared_build_context(
        project_id=project_id, entities=set(FULL_CONTENT_ENTITIES)
    )


__all__ = ["build_engine", "build_context"]
