"""
Unit tests for Confidence & Explainability module.

Tests for:
- ConfidenceClassifier and bands
- ScanModes
- Evidence builder
- Confidence filtering
- Leakage re-scan
"""

import pytest
from dataclasses import dataclass
from unittest.mock import MagicMock

from sandiraksa.detection.confidence.classifier import (
    ConfidenceBand,
    ConfidenceThresholds,
    EntityThresholds,
    ConfidenceClassifier,
    classify_confidence,
    get_confidence_band,
)
from sandiraksa.detection.confidence.modes import (
    ScanMode,
    ScanModeConfig,
    get_mode_config,
    get_mode_thresholds,
    recommend_mode,
    compare_modes,
    STRICT_CONFIG,
    BALANCED_CONFIG,
    MINIMAL_CONFIG,
)
from sandiraksa.detection.confidence.evidence import (
    EvidenceType,
    Evidence,
    ExplanationResult,
    EvidenceBuilder,
    format_explanation_text,
)
from sandiraksa.detection.confidence.filtering import (
    FilterCriteria,
    ConfidenceFilter,
    FilterStatistics,
    filter_findings,
    get_high_confidence,
    get_protectable,
    get_for_review,
)
from sandiraksa.detection.confidence.rescan import (
    LeakageType,
    LeakageFinding,
    LeakageResult,
    LeakageScanner,
)


# Mock Finding class for testing
@dataclass
class MockFinding:
    """Mock Finding for tests."""
    entity_type: str
    text: str
    score: float
    start: int = 0
    end: int = 0
    confidence_band: str = ""
    recognizer_name: str = ""


# ============== ConfidenceBand Tests ==============

class TestConfidenceBand:
    """Tests for ConfidenceBand enum."""

    def test_band_values(self):
        """Test band enum values."""
        assert ConfidenceBand.HIGH.value == "HIGH"
        assert ConfidenceBand.MEDIUM.value == "MEDIUM"
        assert ConfidenceBand.LOW.value == "LOW"

    def test_display_name(self):
        """Test display names."""
        assert ConfidenceBand.HIGH.display_name == "High Confidence"
        assert ConfidenceBand.MEDIUM.display_name == "Medium Confidence"
        assert ConfidenceBand.LOW.display_name == "Low Confidence"

    def test_color_code(self):
        """Test color codes."""
        assert ConfidenceBand.HIGH.color_code == "#28a745"
        assert ConfidenceBand.MEDIUM.color_code == "#ffc107"
        assert ConfidenceBand.LOW.color_code == "#dc3545"

    def test_should_protect_by_default(self):
        """Test protection defaults."""
        assert ConfidenceBand.HIGH.should_protect_by_default is True
        assert ConfidenceBand.MEDIUM.should_protect_by_default is True
        assert ConfidenceBand.LOW.should_protect_by_default is False


# ============== ConfidenceThresholds Tests ==============

class TestConfidenceThresholds:
    """Tests for ConfidenceThresholds."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = ConfidenceThresholds()
        assert thresholds.high == 0.8
        assert thresholds.medium == 0.5
        assert thresholds.low == 0.3

    def test_custom_thresholds(self):
        """Test custom threshold values."""
        thresholds = ConfidenceThresholds(high=0.9, medium=0.6, low=0.4)
        assert thresholds.high == 0.9
        assert thresholds.medium == 0.6
        assert thresholds.low == 0.4

    def test_invalid_thresholds(self):
        """Test validation of invalid thresholds."""
        with pytest.raises(ValueError):
            ConfidenceThresholds(high=0.5, medium=0.8, low=0.3)

        with pytest.raises(ValueError):
            ConfidenceThresholds(high=0.8, medium=0.3, low=0.5)

    def test_get_band_high(self):
        """Test get_band returns HIGH for high scores."""
        thresholds = ConfidenceThresholds()
        assert thresholds.get_band(0.9) == ConfidenceBand.HIGH
        assert thresholds.get_band(0.8) == ConfidenceBand.HIGH

    def test_get_band_medium(self):
        """Test get_band returns MEDIUM for medium scores."""
        thresholds = ConfidenceThresholds()
        assert thresholds.get_band(0.7) == ConfidenceBand.MEDIUM
        assert thresholds.get_band(0.5) == ConfidenceBand.MEDIUM

    def test_get_band_low(self):
        """Test get_band returns LOW for low scores."""
        thresholds = ConfidenceThresholds()
        assert thresholds.get_band(0.4) == ConfidenceBand.LOW
        assert thresholds.get_band(0.3) == ConfidenceBand.LOW

    def test_get_band_below_minimum(self):
        """Test get_band returns None below minimum."""
        thresholds = ConfidenceThresholds()
        assert thresholds.get_band(0.2) is None
        assert thresholds.get_band(0.0) is None


# ============== EntityThresholds Tests ==============

class TestEntityThresholds:
    """Tests for EntityThresholds."""

    def test_get_thresholds_nik(self):
        """Test getting NIK thresholds."""
        entity_thresholds = EntityThresholds()
        nik_thresh = entity_thresholds.get_thresholds("ID_NIK")
        assert nik_thresh.high == 0.85

    def test_get_thresholds_normalized(self):
        """Test entity type normalization."""
        entity_thresholds = EntityThresholds()

        # Various formats should map to same thresholds
        assert entity_thresholds.get_thresholds("nik") == entity_thresholds.nik
        assert entity_thresholds.get_thresholds("NIK") == entity_thresholds.nik
        assert entity_thresholds.get_thresholds("id_nik") == entity_thresholds.nik

    def test_get_thresholds_person(self):
        """Test PERSON thresholds (NER entity)."""
        entity_thresholds = EntityThresholds()
        person_thresh = entity_thresholds.get_thresholds("PERSON")
        assert person_thresh.high == 0.75  # Lower for NER

    def test_get_thresholds_unknown(self):
        """Test unknown entity returns default."""
        entity_thresholds = EntityThresholds()
        unknown_thresh = entity_thresholds.get_thresholds("UNKNOWN_TYPE")
        assert unknown_thresh == entity_thresholds.default


# ============== ConfidenceClassifier Tests ==============

class TestConfidenceClassifier:
    """Tests for ConfidenceClassifier."""

    def test_classify_high_confidence(self):
        """Test classifying high confidence finding."""
        classifier = ConfidenceClassifier()
        finding = MockFinding(entity_type="EMAIL", text="test@example.com", score=0.95)

        classified = classifier.classify([finding])

        assert len(classified) == 1
        assert classified[0].confidence_band == "HIGH"

    def test_classify_medium_confidence(self):
        """Test classifying medium confidence finding."""
        classifier = ConfidenceClassifier()
        finding = MockFinding(entity_type="PERSON", text="Budi", score=0.6)

        classified = classifier.classify([finding])

        assert len(classified) == 1
        assert classified[0].confidence_band == "MEDIUM"

    def test_classify_low_confidence(self):
        """Test classifying low confidence finding."""
        classifier = ConfidenceClassifier()
        finding = MockFinding(entity_type="PERSON", text="Test", score=0.4)

        classified = classifier.classify([finding])

        assert len(classified) == 1
        assert classified[0].confidence_band == "LOW"

    def test_classify_exclude_low(self):
        """Test excluding low confidence findings."""
        classifier = ConfidenceClassifier(include_low=False)
        findings = [
            MockFinding(entity_type="PERSON", text="Budi", score=0.9),
            MockFinding(entity_type="PERSON", text="Test", score=0.4),
        ]

        classified = classifier.classify(findings)

        assert len(classified) == 1
        assert classified[0].text == "Budi"

    def test_classify_below_minimum(self):
        """Test filtering out below minimum score."""
        classifier = ConfidenceClassifier()
        finding = MockFinding(entity_type="PERSON", text="X", score=0.1)

        classified = classifier.classify([finding])

        assert len(classified) == 0

    def test_get_band(self):
        """Test get_band method."""
        classifier = ConfidenceClassifier()
        assert classifier.get_band("EMAIL", 0.95) == ConfidenceBand.HIGH
        assert classifier.get_band("PERSON", 0.6) == ConfidenceBand.MEDIUM


# ============== ScanMode Tests ==============

class TestScanMode:
    """Tests for ScanMode enum."""

    def test_mode_values(self):
        """Test mode values."""
        assert ScanMode.STRICT.value == "strict"
        assert ScanMode.BALANCED.value == "balanced"
        assert ScanMode.MINIMAL.value == "minimal"

    def test_display_name(self):
        """Test display names."""
        assert "Strict" in ScanMode.STRICT.display_name
        assert "Balanced" in ScanMode.BALANCED.display_name
        assert "Minimal" in ScanMode.MINIMAL.display_name

    def test_recommended_for(self):
        """Test recommended document types."""
        assert "HR" in ScanMode.STRICT.recommended_for[0]
        assert "General" in ScanMode.BALANCED.recommended_for[0]


class TestScanModeConfig:
    """Tests for ScanModeConfig."""

    def test_strict_config(self):
        """Test STRICT mode configuration."""
        assert STRICT_CONFIG.mode == ScanMode.STRICT
        assert STRICT_CONFIG.include_low_confidence is True
        assert STRICT_CONFIG.enable_ner is True

    def test_balanced_config(self):
        """Test BALANCED mode configuration."""
        assert BALANCED_CONFIG.mode == ScanMode.BALANCED
        assert BALANCED_CONFIG.include_low_confidence is True

    def test_minimal_config(self):
        """Test MINIMAL mode configuration."""
        assert MINIMAL_CONFIG.mode == ScanMode.MINIMAL
        assert MINIMAL_CONFIG.include_low_confidence is False
        assert MINIMAL_CONFIG.min_score_override == 0.5

    def test_get_mode_config(self):
        """Test get_mode_config function."""
        config = get_mode_config(ScanMode.STRICT)
        assert config.mode == ScanMode.STRICT

        # Test string input
        config = get_mode_config("balanced")
        assert config.mode == ScanMode.BALANCED

    def test_get_mode_thresholds(self):
        """Test get_mode_thresholds function."""
        strict_thresh = get_mode_thresholds(ScanMode.STRICT)
        balanced_thresh = get_mode_thresholds(ScanMode.BALANCED)

        # STRICT should have lower thresholds
        assert strict_thresh.default.low < balanced_thresh.default.low


class TestRecommendMode:
    """Tests for recommend_mode function."""

    def test_recommend_strict_for_hr(self):
        """Test STRICT recommended for HR documents."""
        assert recommend_mode("HR Document") == ScanMode.STRICT
        assert recommend_mode("medical records") == ScanMode.STRICT
        assert recommend_mode("Financial Report") == ScanMode.STRICT

    def test_recommend_minimal_for_technical(self):
        """Test MINIMAL recommended for technical documents."""
        assert recommend_mode("Technical Spec") == ScanMode.MINIMAL
        assert recommend_mode("Invoice #12345") == ScanMode.MINIMAL

    def test_recommend_balanced_default(self):
        """Test BALANCED is default."""
        assert recommend_mode(None) == ScanMode.BALANCED
        assert recommend_mode("Random Document") == ScanMode.BALANCED


# ============== Evidence Tests ==============

class TestEvidenceType:
    """Tests for EvidenceType enum."""

    def test_is_positive(self):
        """Test positive/negative classification."""
        assert EvidenceType.PATTERN_MATCH.is_positive is True
        assert EvidenceType.NER_DETECTION.is_positive is True
        assert EvidenceType.CONTEXT_NEGATIVE.is_positive is False
        assert EvidenceType.EXCLUDED_PATTERN.is_positive is False

    def test_display_name(self):
        """Test display names."""
        assert EvidenceType.PATTERN_MATCH.display_name == "Pattern Match"
        assert EvidenceType.NER_DETECTION.display_name == "Named Entity Recognition"


class TestEvidence:
    """Tests for Evidence dataclass."""

    def test_create_evidence(self):
        """Test creating evidence."""
        evidence = Evidence(
            evidence_type=EvidenceType.PATTERN_MATCH,
            description="Matched NIK pattern",
            weight=0.6,
            source="regex",
        )
        assert evidence.is_positive is True
        assert evidence.strength == "Moderate"

    def test_evidence_strength(self):
        """Test evidence strength calculation."""
        strong = Evidence(EvidenceType.PATTERN_MATCH, "test", 0.8)
        moderate = Evidence(EvidenceType.PATTERN_MATCH, "test", 0.5)
        weak = Evidence(EvidenceType.PATTERN_MATCH, "test", 0.2)

        assert strong.strength == "Strong"
        assert moderate.strength == "Moderate"
        assert weak.strength == "Weak"

    def test_to_dict(self):
        """Test to_dict conversion."""
        evidence = Evidence(
            evidence_type=EvidenceType.NER_DETECTION,
            description="Detected as PERSON",
            weight=0.7,
            source="ner_model",
        )
        d = evidence.to_dict()

        assert d["type"] == "ner_detection"
        assert d["is_positive"] is True
        assert d["strength"] == "Strong"


class TestEvidenceBuilder:
    """Tests for EvidenceBuilder."""

    def test_add_pattern_match(self):
        """Test adding pattern match evidence."""
        builder = EvidenceBuilder()
        builder.add_pattern_match("NIK", "Matched 16-digit pattern")

        assert len(builder._evidence) == 1
        assert builder._evidence[0].evidence_type == EvidenceType.PATTERN_MATCH

    def test_fluent_api(self):
        """Test fluent API chaining."""
        builder = EvidenceBuilder()
        builder.add_pattern_match("NIK").add_structural_validation("Valid province code")

        assert len(builder._evidence) == 2

    def test_add_context_positive(self):
        """Test adding positive context."""
        builder = EvidenceBuilder()
        builder.add_context_positive("Found near 'NIK:' label", keyword="NIK")

        assert builder._evidence[0].weight > 0

    def test_add_context_negative(self):
        """Test adding negative context."""
        builder = EvidenceBuilder()
        builder.add_context_negative("Found near 'Invoice Number'", keyword="Invoice")

        assert builder._evidence[0].weight < 0

    def test_build(self):
        """Test building explanation."""
        builder = EvidenceBuilder()
        builder.add_pattern_match("NIK")
        builder.add_structural_validation("Valid format")

        finding = MockFinding("ID_NIK", "3201051234567890", 0.9)
        finding.confidence_band = "HIGH"

        explanation = builder.build(finding)

        assert explanation.entity_type == "ID_NIK"
        assert len(explanation.evidence) == 2
        assert len(explanation.positive_evidence) == 2

    def test_clear(self):
        """Test clearing evidence."""
        builder = EvidenceBuilder()
        builder.add_pattern_match("test")
        builder.clear()

        assert len(builder._evidence) == 0


class TestExplanationResult:
    """Tests for ExplanationResult."""

    def test_primary_reason(self):
        """Test getting primary reason."""
        evidence = [
            Evidence(EvidenceType.PATTERN_MATCH, "Matched pattern", 0.5),
            Evidence(EvidenceType.STRUCTURAL_VALIDATION, "Valid structure", 0.8),
        ]
        result = ExplanationResult(
            entity_type="NIK",
            entity_text="123456",
            raw_score=0.9,
            confidence_band="HIGH",
            evidence=evidence,
        )

        # Primary reason should be highest weight positive evidence
        assert "Valid structure" in result.primary_reason

    def test_positive_negative_separation(self):
        """Test separating positive and negative evidence."""
        evidence = [
            Evidence(EvidenceType.PATTERN_MATCH, "Matched", 0.5),
            Evidence(EvidenceType.CONTEXT_NEGATIVE, "Negative context", -0.3),
        ]
        result = ExplanationResult(
            entity_type="TEST",
            entity_text="test",
            raw_score=0.7,
            confidence_band="MEDIUM",
            evidence=evidence,
        )

        assert len(result.positive_evidence) == 1
        assert len(result.negative_evidence) == 1


# ============== Filtering Tests ==============

class TestFilterCriteria:
    """Tests for FilterCriteria."""

    def test_high_confidence_only(self):
        """Test high confidence filter factory."""
        criteria = FilterCriteria.high_confidence_only()
        assert ConfidenceBand.HIGH in criteria.confidence_bands
        assert len(criteria.confidence_bands) == 1

    def test_exclude_low(self):
        """Test exclude low factory."""
        criteria = FilterCriteria.exclude_low()
        assert ConfidenceBand.LOW not in criteria.confidence_bands

    def test_entity_type_filter(self):
        """Test entity type filter factory."""
        criteria = FilterCriteria.entity_type("PERSON", "EMAIL")
        assert "PERSON" in criteria.entity_types
        assert "EMAIL" in criteria.entity_types

    def test_matches_confidence(self):
        """Test matching by confidence band."""
        criteria = FilterCriteria(confidence_bands={ConfidenceBand.HIGH})
        finding = MockFinding("TEST", "test", 0.9)
        finding.confidence_band = "HIGH"

        assert criteria.matches(finding) is True

        finding.confidence_band = "LOW"
        assert criteria.matches(finding) is False

    def test_matches_entity_type(self):
        """Test matching by entity type."""
        criteria = FilterCriteria(entity_types={"PERSON", "EMAIL"})
        finding = MockFinding("PERSON", "Budi", 0.9)

        assert criteria.matches(finding) is True

        finding.entity_type = "PHONE"
        assert criteria.matches(finding) is False

    def test_matches_score_range(self):
        """Test matching by score range."""
        criteria = FilterCriteria(min_score=0.5, max_score=0.9)
        finding = MockFinding("TEST", "test", 0.7)

        assert criteria.matches(finding) is True

        finding.score = 0.3
        assert criteria.matches(finding) is False

        finding.score = 0.95
        assert criteria.matches(finding) is False


class TestConfidenceFilter:
    """Tests for ConfidenceFilter."""

    def test_filter_by_confidence(self):
        """Test filtering by confidence bands."""
        filter = ConfidenceFilter()
        findings = [
            MockFinding("A", "a", 0.9),
            MockFinding("B", "b", 0.5),
        ]
        findings[0].confidence_band = "HIGH"
        findings[1].confidence_band = "LOW"

        result = filter.filter_by_confidence(findings, {ConfidenceBand.HIGH})

        assert len(result) == 1
        assert result[0].text == "a"

    def test_group_by_confidence(self):
        """Test grouping by confidence."""
        filter = ConfidenceFilter()
        findings = [
            MockFinding("A", "a", 0.9),
            MockFinding("B", "b", 0.6),
            MockFinding("C", "c", 0.4),
        ]
        findings[0].confidence_band = "HIGH"
        findings[1].confidence_band = "MEDIUM"
        findings[2].confidence_band = "LOW"

        groups = filter.group_by_confidence(findings)

        assert len(groups["HIGH"]) == 1
        assert len(groups["MEDIUM"]) == 1
        assert len(groups["LOW"]) == 1

    def test_group_by_entity_type(self):
        """Test grouping by entity type."""
        filter = ConfidenceFilter()
        findings = [
            MockFinding("PERSON", "Budi", 0.9),
            MockFinding("PERSON", "Siti", 0.8),
            MockFinding("EMAIL", "test@test.com", 0.9),
        ]

        groups = filter.group_by_entity_type(findings)

        assert len(groups["PERSON"]) == 2
        assert len(groups["EMAIL"]) == 1

    def test_get_statistics(self):
        """Test getting statistics."""
        filter = ConfidenceFilter()
        findings = [
            MockFinding("PERSON", "Budi", 0.9),
            MockFinding("EMAIL", "test@test.com", 0.6),
        ]
        findings[0].confidence_band = "HIGH"
        findings[1].confidence_band = "MEDIUM"

        stats = filter.get_statistics(findings)

        assert stats.total == 2
        assert stats.high_count == 1
        assert stats.medium_count == 1
        assert stats.average_score == 0.75


class TestFilterStatistics:
    """Tests for FilterStatistics."""

    def test_percentages(self):
        """Test percentage calculations."""
        stats = FilterStatistics(
            total=10,
            high_count=5,
            medium_count=3,
            low_count=2,
            unclassified_count=0,
            by_entity_type={},
            average_score=0.7,
            min_score=0.3,
            max_score=0.95,
        )

        assert stats.high_percentage == 50.0
        assert stats.medium_percentage == 30.0
        assert stats.low_percentage == 20.0

    def test_protectable_count(self):
        """Test protectable count."""
        stats = FilterStatistics(
            total=10,
            high_count=5,
            medium_count=3,
            low_count=2,
            unclassified_count=0,
            by_entity_type={},
            average_score=0.7,
            min_score=0.3,
            max_score=0.95,
        )

        assert stats.protectable_count == 8  # HIGH + MEDIUM


# ============== Leakage Re-Scan Tests ==============

class TestLeakageType:
    """Tests for LeakageType enum."""

    def test_severity_levels(self):
        """Test severity levels."""
        assert LeakageType.RESIDUAL.severity == "CRITICAL"
        assert LeakageType.MISSED.severity == "HIGH"
        assert LeakageType.INCOMPLETE.severity == "HIGH"
        assert LeakageType.INTRODUCED.severity == "MEDIUM"


class TestLeakageFinding:
    """Tests for LeakageFinding."""

    def test_create_finding(self):
        """Test creating leakage finding."""
        finding = LeakageFinding(
            leakage_type=LeakageType.RESIDUAL,
            entity_type="NIK",
            text="1234567890123456",
            start=0,
            end=16,
            score=0.9,
            location="test.xlsx",
        )

        assert finding.severity == "CRITICAL"

    def test_to_dict(self):
        """Test to_dict conversion."""
        finding = LeakageFinding(
            leakage_type=LeakageType.MISSED,
            entity_type="EMAIL",
            text="test@test.com",
            start=10,
            end=23,
            score=0.95,
            location="doc.docx",
        )
        d = finding.to_dict()

        assert d["leakage_type"] == "missed"
        assert d["severity"] == "HIGH"


class TestLeakageResult:
    """Tests for LeakageResult."""

    def test_empty_result_is_clean(self):
        """Test empty result is clean."""
        result = LeakageResult(
            source_file="source.xlsx",
            protected_file="protected.xlsx",
        )

        assert result.is_clean is True
        assert result.has_leakage is False

    def test_result_with_leakage(self):
        """Test result with leakage."""
        result = LeakageResult(
            source_file="source.xlsx",
            protected_file="protected.xlsx",
            leakages=[
                LeakageFinding(LeakageType.RESIDUAL, "NIK", "123", 0, 3, 0.9, "test"),
            ],
        )

        assert result.is_clean is False
        assert result.has_leakage is True
        assert result.critical_count == 1

    def test_summary_clean(self):
        """Test clean summary."""
        result = LeakageResult(
            source_file="source.xlsx",
            protected_file="protected.xlsx",
        )
        summary = result.summary()

        assert "clean" in summary.lower() or "✓" in summary

    def test_summary_with_leakage(self):
        """Test leakage summary."""
        result = LeakageResult(
            source_file="source.xlsx",
            protected_file="protected.xlsx",
            leakages=[
                LeakageFinding(LeakageType.MISSED, "EMAIL", "test@test.com", 0, 13, 0.9, "test"),
            ],
        )
        summary = result.summary()

        assert "LEAKAGE" in summary or "⚠" in summary


class TestLeakageScanner:
    """Tests for LeakageScanner."""

    def test_looks_like_token(self):
        """Test token pattern detection."""
        scanner = LeakageScanner()

        assert scanner._looks_like_token("[REDACTED]") is True
        assert scanner._looks_like_token("<EMAIL_TOKEN>") is True
        assert scanner._looks_like_token("{{MASKED}}") is True
        assert scanner._looks_like_token("TOKEN_12345") is True
        assert scanner._looks_like_token("Budi Santoso") is False

    def test_looks_like_partial(self):
        """Test partial match detection."""
        scanner = LeakageScanner()
        original_findings = [
            MockFinding("PERSON", "Budi Santoso", 0.9),
        ]

        assert scanner._looks_like_partial("Budi", original_findings) is True
        assert scanner._looks_like_partial("Santoso", original_findings) is True
        assert scanner._looks_like_partial("John Doe", original_findings) is False

    def test_scan_text_no_engine(self):
        """Test scan_text without engine returns empty."""
        scanner = LeakageScanner()
        result = scanner.scan_text("test text", [])

        # Without engine, should return clean result
        assert result.protected_findings_count == 0
