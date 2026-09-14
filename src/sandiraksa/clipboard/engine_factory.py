"""
Detection engine construction for the clipboard subsystem (design 27).

The expensive engine is built ONCE per worker and reused across every scan
(design 27); it is never reloaded per clipboard event. This mirrors the
recognizer registration used by the file scan worker so clipboard and file
detection share the exact same recognizers (design 40: do not fork a
clipboard-only recognizer codebase).
"""

from __future__ import annotations

import uuid


def build_engine():
    """Build and initialize a DetectionEngine with all recognizers."""
    from sandiraksa.detection.presidio_engine import RegexRecognizer
    from sandiraksa.detection.engine import DetectionEngine
    from sandiraksa.detection.recognizers import (
        NIKRecognizer,
        NPWPRecognizer,
        KKRecognizer,
        IndonesianPhoneRecognizer,
    )
    from sandiraksa.detection.recognizers.id_dob import DateOfBirthRecognizer
    from sandiraksa.detection.recognizers.id_person import (
        IndonesianPersonRecognizer,
    )
    from sandiraksa.detection.recognizers.id_bpjs_legacy import (
        BPJSRecognizerLegacy,
    )

    engine = DetectionEngine()
    engine.registry.register(RegexRecognizer())
    engine.registry.register(NIKRecognizer())
    engine.registry.register(NPWPRecognizer())
    engine.registry.register(KKRecognizer())
    engine.registry.register(IndonesianPhoneRecognizer())
    engine.registry.register(BPJSRecognizerLegacy())
    engine.registry.register(DateOfBirthRecognizer())
    engine.registry.register(IndonesianPersonRecognizer())
    engine.initialize()
    return engine


def build_context(project_id: str | None = None):
    """Build a reusable DetectionContext for clipboard scans (design 41)."""
    from sandiraksa.detection.context import DetectionConfig, DetectionContext

    return DetectionContext(
        operation_id=uuid.uuid4().hex,
        file_id=uuid.uuid4().hex,
        project_id=project_id or uuid.uuid4().hex,
        config=DetectionConfig(enabled_entity_types=set(), min_confidence=0.5),
    )


__all__ = ["build_engine", "build_context"]
