"""Sprint 3/4 tests: detection pipeline, size limits, normalization, risk, treatment."""

from __future__ import annotations

import pytest

from sandiraksa.clipboard.models import (
    ClipboardRiskLevel,
    DetectionSource,
    Finding,
    ScanRequest,
)
from sandiraksa.clipboard.normalize import normalize_findings
from sandiraksa.clipboard.pipeline import (
    HARD_LIMIT,
    OversizedError,
    SOFT_LIMIT,
    run_pipeline,
)
from sandiraksa.clipboard.risk_policy import (
    compute_risk_level,
    passes_policy,
    severity_for,
)
from sandiraksa.clipboard.treatment import protect_text, replacement_for


# --- Fakes so pipeline tests don't need the heavy real engine ---------------
class _FakeResult:
    def __init__(self, entity_type, start, end, text, score):
        self.entity_type = entity_type
        self.start = start
        self.end = end
        self.text = text
        self.score = score


class _FakeConfig:
    def __init__(self):
        self.enabled_entity_types = set()
        self.min_confidence = 0.5


class _FakeContext:
    def __init__(self):
        self.config = _FakeConfig()


class _FakeEngine:
    """Returns canned detections filtered by enabled entity types."""

    def __init__(self, detections):
        self._detections = detections

    def analyze_text(self, text, context):
        enabled = context.config.enabled_entity_types
        return [d for d in self._detections if d.entity_type in enabled]


def _req(text, generation=1, fingerprint="fp"):
    return ScanRequest(
        request_id="q1",
        generation=generation,
        fingerprint=fingerprint,
        text=text,
        created_monotonic=0.0,
        source=DetectionSource.CLIPBOARD,
    )


class TestTreatment:
    def test_replacement_labels(self):
        assert replacement_for("ID_NIK") == "[NIK_REDACTED]"
        assert replacement_for("EMAIL_ADDRESS") == "[EMAIL_REDACTED]"
        assert replacement_for("UNKNOWN_X") == "[REDACTED]"

    def test_protect_reverse_order_preserves_offsets(self):
        text = "NIK 3174000000000000 email a@b.com"
        findings = [
            Finding("ID_NIK", 4, 20, 0.9, "high", "3174000000000000"),
            Finding("EMAIL_ADDRESS", 27, 34, 0.8, "medium", "a@b.com"),
        ]
        out = protect_text(text, findings)
        assert out == "NIK [NIK_REDACTED] email [EMAIL_REDACTED]"

    def test_protect_no_findings(self):
        assert protect_text("hello", []) == "hello"

    def test_protect_ignores_bad_offsets(self):
        out = protect_text("short", [Finding("ID_NIK", 0, 999, 0.9, "high")])
        assert out == "short"


class TestNormalize:
    def test_drops_invalid_offsets(self):
        assert normalize_findings([Finding("X", 5, 5, 0.9, "low")]) == []
        assert normalize_findings([Finding("X", -1, 3, 0.9, "low")]) == []

    def test_dedupe_exact_span_keeps_higher_score(self):
        out = normalize_findings([
            Finding("ID_NIK", 0, 5, 0.7, "high"),
            Finding("ID_NIK", 0, 5, 0.9, "high"),
        ])
        assert len(out) == 1
        assert out[0].score == 0.9

    def test_overlap_severity_wins(self):
        # PERSON (medium) vs MEDICAL_RECORD (critical) overlapping -> critical.
        out = normalize_findings([
            Finding("PERSON", 0, 10, 0.9, "medium"),
            Finding("MEDICAL_RECORD", 0, 6, 0.75, "critical"),
        ])
        assert len(out) == 1
        assert out[0].entity_type == "MEDICAL_RECORD"

    def test_non_overlapping_sorted(self):
        out = normalize_findings([
            Finding("EMAIL_ADDRESS", 20, 30, 0.8, "medium"),
            Finding("ID_NIK", 0, 16, 0.9, "high"),
        ])
        assert [f.start for f in out] == [0, 20]


class TestRiskPolicy:
    def test_passes_policy(self):
        assert passes_policy("EMAIL_ADDRESS", 0.80) is True
        assert passes_policy("EMAIL_ADDRESS", 0.70) is False  # min 0.75
        assert passes_policy("PERSON", 0.80) is False  # min 0.85

    def test_severity_lookup(self):
        assert severity_for("MEDICAL_RECORD") == "critical"
        assert severity_for("ID_NIK") == "high"

    def test_risk_empty_is_low(self):
        assert compute_risk_level([]) == ClipboardRiskLevel.LOW

    def test_risk_critical_dominates(self):
        r = compute_risk_level([Finding("MEDICAL_RECORD", 0, 5, 0.8, "critical")])
        assert r == ClipboardRiskLevel.CRITICAL

    def test_multiple_medium_escalates_to_high(self):
        r = compute_risk_level([
            Finding("EMAIL_ADDRESS", 0, 5, 0.8, "medium"),
            Finding("PERSON", 6, 10, 0.9, "medium"),
        ])
        assert r == ClipboardRiskLevel.HIGH

    def test_single_medium_stays_medium(self):
        r = compute_risk_level([Finding("EMAIL_ADDRESS", 0, 5, 0.8, "medium")])
        assert r == ClipboardRiskLevel.MEDIUM


class TestPipeline:
    def test_empty_text(self):
        result = run_pipeline(_req("   "), _FakeEngine([]), _FakeContext(), now=100.0)
        assert result.findings == ()
        assert result.risk_level == ClipboardRiskLevel.LOW
        assert result.generation == 1
        assert result.source_fingerprint == "fp"

    def test_detects_and_redacts(self):
        text = "email a@b.com"
        engine = _FakeEngine([_FakeResult("EMAIL_ADDRESS", 6, 13, "a@b.com", 0.9)])
        result = run_pipeline(_req(text), engine, _FakeContext(), now=100.0)
        assert len(result.findings) == 1
        assert result.findings[0].entity_type == "EMAIL_ADDRESS"
        assert "[EMAIL_REDACTED]" in result.safe_text
        assert result.risk_level == ClipboardRiskLevel.MEDIUM

    def test_policy_filters_low_score(self):
        # PERSON needs 0.85; a 0.80 detection is dropped.
        engine = _FakeEngine([_FakeResult("PERSON", 0, 4, "Budi", 0.80)])
        result = run_pipeline(_req("Budi"), engine, _FakeContext(), now=100.0)
        assert result.findings == ()

    def test_ttl_set(self):
        result = run_pipeline(_req("x"), _FakeEngine([]), _FakeContext(), now=100.0)
        assert result.expires_monotonic == pytest.approx(130.0)  # 30s TTL
        assert result.is_expired(131.0) is True
        assert result.is_expired(129.0) is False

    def test_oversized_raises(self):
        big = "a" * (HARD_LIMIT + 10)
        with pytest.raises(OversizedError):
            run_pipeline(_req(big), _FakeEngine([]), _FakeContext(), now=100.0)

    def test_over_soft_limit_runs_stage1_only(self):
        # Between soft and hard: Stage 2 (PERSON) must NOT run.
        size = SOFT_LIMIT + 1000
        text = "a" * size
        engine = _FakeEngine([
            _FakeResult("EMAIL_ADDRESS", 0, 5, "x", 0.9),  # stage 1
            _FakeResult("PERSON", 6, 10, "y", 0.95),        # stage 2
        ])
        result = run_pipeline(_req(text), engine, _FakeContext(), now=100.0)
        types = {f.entity_type for f in result.findings}
        assert "EMAIL_ADDRESS" in types
        assert "PERSON" not in types
