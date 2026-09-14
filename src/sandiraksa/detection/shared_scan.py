"""
Shared PII detection core.

Single source of truth for how SandiRaksa detects PII in free text, used by
BOTH the file scanner (``sandiraksa.ui.scan_worker.ScanWorker``) and the
Clipboard Privacy Guard (``sandiraksa.clipboard.pipeline``).

Centralizing this here guarantees the two paths use the exact same:
  * detection engine + recognizer set,
  * enabled entity types,
  * confidence floor,
  * global custom patterns (``find_custom_matches``),
  * global deny-list (applied inside the engine).

So any tweak to detection automatically applies to files and clipboard alike.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

# Entity types detected in free-text content. This is THE canonical set used by
# both file scanning and clipboard scanning.
STRUCTURED_ENTITIES = {
    "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
    "IP_ADDRESS", "URL", "IBAN_CODE",
    "ID_NIK", "ID_NPWP", "ID_KK", "ID_PHONE", "ID_BPJS",
}

# Free-text / narrative content additionally looks for names and birth dates.
FULL_CONTENT_ENTITIES = STRUCTURED_ENTITIES | {"PERSON", "DATE_OF_BIRTH"}

# Confidence floor applied to the engine (matches the file scan path).
MIN_CONFIDENCE = 0.5


@dataclass
class DetectionMatch:
    """A single detection result in the shared, engine-neutral shape."""

    entity_type: str
    text: str
    start: int
    end: int
    score: float


def build_engine():
    """
    Build and initialize the canonical DetectionEngine with all recognizers.

    This is the ONE place recognizers are registered for free-text scanning;
    both file and clipboard paths call it.
    """
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


def build_context(
    project_id: str | None = None,
    entities: set[str] | None = None,
    min_confidence: float = MIN_CONFIDENCE,
):
    """Build a reusable DetectionContext for free-text scanning."""
    from sandiraksa.detection.context import DetectionConfig, DetectionContext

    return DetectionContext(
        operation_id=uuid4().hex,
        file_id=uuid4().hex,
        project_id=project_id or uuid4().hex,
        config=DetectionConfig(
            enabled_entity_types=set(entities or FULL_CONTENT_ENTITIES),
            min_confidence=min_confidence,
        ),
    )


def detect(engine, context, text: str) -> list[DetectionMatch]:
    """
    Run the canonical detection on ``text`` and return matches.

    This is the shared pipeline both callers use, so behavior is identical:
      1. engine.analyze_text (recognizers + deny-list applied inside), then
      2. global custom patterns chained on top (design: same as file path),
    returning a unified list of :class:`DetectionMatch`.

    The engine already applies the global deny-list via
    ``DetectionEngine._filter_false_positives`` (is_denied). Custom-pattern
    hits are also deny-list-filtered here so ALL surfaced matches respect it.
    """
    if not text or not text.strip():
        return []

    matches: list[DetectionMatch] = [
        DetectionMatch(r.entity_type, r.text, r.start, r.end, r.score)
        for r in engine.analyze_text(text, context)
    ]

    # Chain global custom patterns (the engine does not evaluate these).
    try:
        from sandiraksa.detection.custom_patterns import find_custom_matches

        is_denied = _load_is_denied()
        for cm in find_custom_matches(text):
            if is_denied is not None and is_denied(cm.value):
                continue
            matches.append(
                DetectionMatch(cm.label, cm.value, cm.start, cm.end, 0.95)
            )
    except Exception as exc:  # pragma: no cover - optional feature
        # Never fail detection because custom patterns errored.
        import logging

        logging.getLogger(__name__).debug(
            "custom pattern chain skipped: %s", type(exc).__name__
        )

    return matches


def _load_is_denied():
    try:
        from sandiraksa.detection.deny_list import is_denied

        return is_denied
    except Exception:  # pragma: no cover
        return None


__all__ = [
    "STRUCTURED_ENTITIES",
    "FULL_CONTENT_ENTITIES",
    "MIN_CONFIDENCE",
    "DetectionMatch",
    "build_engine",
    "build_context",
    "detect",
]
