"""
Unit tests for Sprint 3: Unified Detection Engine & Presidio Integration.

Tests cover:
- UnifiedFinding model and evidence tracking
- DetectionConfig and DetectionContext
- OverlapResolver strategies
- IndonesianIdRecognizer (NIK, NPWP, Phone)
- CustomTermsRecognizer
- UnifiedDetectionEngine pipeline
- CSV/XLSX adapters
"""

import pytest

from sandiraksa.detection.unified_finding import (
    ConfidenceBand,
    ConfidenceEvidence,
    EvidenceType,
    UnifiedFinding,
    classify_confidence,
)
from sandiraksa.detection.unified_engine import (
    BaseUnifiedRecognizer,
    DetectionConfig,
    DetectionContext,
    DetectionMode,
)
from sandiraksa.detection.overlap import (
    ENTITY_PRIORITY,
    OverlapPair,
    OverlapResolver,
    OverlapStrategy,
    findings_overlap,
    get_entity_priority,
    get_overlap_pair,
    resolve_overlaps,
)
from sandiraksa.detection.presidio_adapter import (
    CustomTermsRecognizer,
    IndonesianIdRecognizer,
)
from sandiraksa.detection.detection_pipeline import (
    CONTEXT_TO_ENTITY,
    UnifiedDetectionEngine,
)
from sandiraksa.documents.logical_segment import LogicalSegment
from sandiraksa.documents.location import DocumentLocation, DocumentComponent


# =============================================================================
# UnifiedFinding Tests
# =============================================================================

class TestUnifiedFinding:
    """Tests for UnifiedFinding model."""

    def test_create_basic_finding(self):
        """Test creating a basic finding."""
        finding = UnifiedFinding(
            segment_id="seg-1",
            entity_type="PERSON",
            start=0,
            end=10,
            raw_score=0.85,
            confidence_band=ConfidenceBand.HIGH,  # Explicitly set
            detector="test",
            detected_text="John Smith",
        )
        assert finding.entity_type == "PERSON"
        assert finding.start == 0
        assert finding.end == 10
        assert finding.length == 10
        assert finding.raw_score == 0.85
        assert finding.is_high_confidence

    def test_confidence_band_assignment(self):
        """Test confidence band classification."""
        # HIGH confidence
        finding_high = UnifiedFinding(
            segment_id="seg-1",
            entity_type="PERSON",
            start=0,
            end=5,
            raw_score=0.9,
            confidence_band=ConfidenceBand.HIGH,
            detector="test",
        )
        assert finding_high.confidence_band == ConfidenceBand.HIGH
        assert finding_high.is_high_confidence

        # MEDIUM confidence
        finding_med = UnifiedFinding(
            segment_id="seg-1",
            entity_type="PERSON",
            start=0,
            end=5,
            raw_score=0.6,
            confidence_band=ConfidenceBand.MEDIUM,
            detector="test",
        )
        assert finding_med.confidence_band == ConfidenceBand.MEDIUM
        assert not finding_med.is_high_confidence

    def test_add_evidence(self):
        """Test adding evidence to finding."""
        finding = UnifiedFinding(
            segment_id="seg-1",
            entity_type="ID_NIK",
            start=0,
            end=16,
            raw_score=0.8,
            detector="test",
        )

        evidence = ConfidenceEvidence(
            evidence_type=EvidenceType.PATTERN_MATCH,
            source="indonesian_id",
            weight=0.7,
            reason_code="nik_pattern_match",
            description="Matched NIK pattern",
        )

        finding.add_evidence(evidence)

        assert len(finding.evidence) == 1
        assert "nik_pattern_match" in finding.reason_codes

    def test_from_custom_term(self):
        """Test creating finding from custom term."""
        finding = UnifiedFinding.from_custom_term(
            term="secret-project",
            start=10,
            end=24,
            segment_id="seg-1",
        )

        assert finding.entity_type == "CUSTOM"
        assert finding.confidence_band == ConfidenceBand.CRITICAL
        assert finding.raw_score == 1.0
        assert finding.is_from_custom_terms
        assert finding.detected_text == "secret-project"

    def test_from_regex_match(self):
        """Test creating finding from regex match."""
        finding = UnifiedFinding.from_regex_match(
            entity_type="EMAIL_ADDRESS",
            start=0,
            end=20,
            detected_text="test@example.com",
            segment_id="seg-1",
            recognizer_name="email_recognizer",
            score=0.9,
        )

        assert finding.entity_type == "EMAIL_ADDRESS"
        assert finding.raw_score == 0.9
        assert finding.confidence_band == ConfidenceBand.HIGH
        assert "pattern_matched" in finding.reason_codes


class TestClassifyConfidence:
    """Tests for classify_confidence function."""

    def test_high_confidence(self):
        assert classify_confidence(0.85) == ConfidenceBand.HIGH
        assert classify_confidence(0.90) == ConfidenceBand.HIGH
        assert classify_confidence(1.0) == ConfidenceBand.HIGH

    def test_medium_confidence(self):
        assert classify_confidence(0.60) == ConfidenceBand.MEDIUM
        assert classify_confidence(0.70) == ConfidenceBand.MEDIUM
        assert classify_confidence(0.84) == ConfidenceBand.MEDIUM

    def test_low_confidence(self):
        assert classify_confidence(0.0) == ConfidenceBand.LOW
        assert classify_confidence(0.40) == ConfidenceBand.LOW
        assert classify_confidence(0.59) == ConfidenceBand.LOW


# =============================================================================
# DetectionConfig Tests
# =============================================================================

class TestDetectionConfig:
    """Tests for DetectionConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = DetectionConfig()
        assert config.entities is None  # All entities
        assert config.mode == DetectionMode.BALANCED
        assert config.min_score == 0.4
        assert config.use_context is True
        assert config.language == "id"

    def test_with_entities(self):
        """Test creating config with specific entities."""
        config = DetectionConfig()
        new_config = config.with_entities(["PERSON", "EMAIL_ADDRESS"])

        assert new_config.entities == ["PERSON", "EMAIL_ADDRESS"]
        assert config.entities is None  # Original unchanged

    def test_with_min_score(self):
        """Test creating config with different min score."""
        config = DetectionConfig()
        new_config = config.with_min_score(0.7)

        assert new_config.min_score == 0.7
        assert config.min_score == 0.4  # Original unchanged


# =============================================================================
# Overlap Resolver Tests
# =============================================================================

class TestOverlapResolver:
    """Tests for OverlapResolver."""

    def _make_finding(
        self,
        segment_id: str,
        entity_type: str,
        start: int,
        end: int,
        score: float = 0.8,
    ) -> UnifiedFinding:
        """Helper to create findings for tests."""
        return UnifiedFinding(
            segment_id=segment_id,
            entity_type=entity_type,
            start=start,
            end=end,
            raw_score=score,
            detector="test",
            detected_text="x" * (end - start),
        )

    def test_no_overlaps(self):
        """Test when there are no overlapping findings."""
        findings = [
            self._make_finding("s1", "PERSON", 0, 10),
            self._make_finding("s1", "EMAIL_ADDRESS", 20, 40),
        ]

        resolver = OverlapResolver()
        result = resolver.resolve(findings)

        assert len(result) == 2

    def test_overlap_priority_based(self):
        """Test overlap resolution by entity priority."""
        # ID_NIK has higher priority than generic number
        findings = [
            self._make_finding("s1", "NRP", 0, 16, score=0.7),
            self._make_finding("s1", "ID_NIK", 0, 16, score=0.85),
        ]

        resolver = OverlapResolver(strategy=OverlapStrategy.PRIORITY_FIRST)
        result = resolver.resolve(findings)

        assert len(result) == 1
        assert result[0].entity_type == "ID_NIK"

    def test_overlap_custom_always_wins(self):
        """Test that CUSTOM entity type always wins."""
        findings = [
            self._make_finding("s1", "ID_NIK", 0, 16, score=0.9),
            self._make_finding("s1", "CUSTOM", 0, 16, score=1.0),
        ]
        findings[1].is_from_custom_terms = True

        resolver = OverlapResolver()
        result = resolver.resolve(findings)

        assert len(result) == 1
        assert result[0].entity_type == "CUSTOM"

    def test_overlap_score_strategy(self):
        """Test overlap resolution by score."""
        findings = [
            self._make_finding("s1", "PERSON", 0, 10, score=0.6),
            self._make_finding("s1", "PERSON", 0, 10, score=0.9),
        ]

        resolver = OverlapResolver(strategy=OverlapStrategy.SCORE_FIRST)
        result = resolver.resolve(findings)

        assert len(result) == 1
        assert result[0].raw_score == 0.9

    def test_overlap_longer_span_strategy(self):
        """Test overlap resolution by span length."""
        findings = [
            self._make_finding("s1", "PERSON", 0, 5, score=0.8),
            self._make_finding("s1", "PERSON", 0, 15, score=0.8),
        ]

        resolver = OverlapResolver(strategy=OverlapStrategy.LONGER_SPAN)
        result = resolver.resolve(findings)

        assert len(result) == 1
        assert result[0].end == 15

    def test_different_segments_no_overlap(self):
        """Test that findings in different segments don't conflict."""
        findings = [
            self._make_finding("s1", "PERSON", 0, 10),
            self._make_finding("s2", "PERSON", 0, 10),  # Same position, different segment
        ]

        resolver = OverlapResolver()
        result = resolver.resolve(findings)

        assert len(result) == 2

    def test_keep_all_strategy(self):
        """Test KEEP_ALL strategy returns all findings."""
        findings = [
            self._make_finding("s1", "PERSON", 0, 10),
            self._make_finding("s1", "PERSON", 5, 15),  # Overlapping
        ]

        resolver = OverlapResolver(strategy=OverlapStrategy.KEEP_ALL)
        result = resolver.resolve(findings)

        assert len(result) == 2


class TestFindingsOverlap:
    """Tests for findings_overlap function."""

    def test_overlapping_findings(self):
        """Test detecting overlapping findings."""
        f1 = UnifiedFinding(
            segment_id="s1", entity_type="A", start=0, end=10,
            raw_score=0.8, detector="test"
        )
        f2 = UnifiedFinding(
            segment_id="s1", entity_type="B", start=5, end=15,
            raw_score=0.8, detector="test"
        )

        assert findings_overlap(f1, f2) is True

    def test_non_overlapping_findings(self):
        """Test detecting non-overlapping findings."""
        f1 = UnifiedFinding(
            segment_id="s1", entity_type="A", start=0, end=10,
            raw_score=0.8, detector="test"
        )
        f2 = UnifiedFinding(
            segment_id="s1", entity_type="B", start=10, end=20,
            raw_score=0.8, detector="test"
        )

        assert findings_overlap(f1, f2) is False

    def test_different_segments_not_overlap(self):
        """Test findings in different segments don't overlap."""
        f1 = UnifiedFinding(
            segment_id="s1", entity_type="A", start=0, end=10,
            raw_score=0.8, detector="test"
        )
        f2 = UnifiedFinding(
            segment_id="s2", entity_type="B", start=0, end=10,
            raw_score=0.8, detector="test"
        )

        assert findings_overlap(f1, f2) is False


class TestEntityPriority:
    """Tests for entity priority mapping."""

    def test_indonesian_ids_high_priority(self):
        """Test Indonesian IDs have high priority."""
        assert get_entity_priority("ID_NIK") == 90
        assert get_entity_priority("ID_KK") == 90
        assert get_entity_priority("ID_NPWP") == 85

    def test_custom_highest_priority(self):
        """Test CUSTOM has highest priority."""
        assert get_entity_priority("CUSTOM") == 100

    def test_unknown_default_priority(self):
        """Test unknown entity types get default priority."""
        assert get_entity_priority("UNKNOWN_TYPE") == 50


# =============================================================================
# Indonesian ID Recognizer Tests
# =============================================================================

class TestIndonesianIdRecognizer:
    """Tests for IndonesianIdRecognizer."""

    @pytest.fixture
    def recognizer(self):
        return IndonesianIdRecognizer()

    @pytest.fixture
    def make_segment(self):
        def _make(text: str, file_id: str = "test.txt") -> LogicalSegment:
            return LogicalSegment.for_txt_paragraph(
                text=text,
                file_id=file_id,
                paragraph_index=0,
            )
        return _make

    @pytest.fixture
    def make_context(self):
        def _make(segment: LogicalSegment) -> DetectionContext:
            return DetectionContext(
                segment=segment,
                config=DetectionConfig(),
                file_type="txt",
            )
        return _make

    def test_detect_valid_nik(self, recognizer, make_segment, make_context):
        """Test detecting valid NIK."""
        # Valid NIK format: province 32, date 150190, serial
        # Day 15, Month 01, Year 90
        segment = make_segment("NIK: 3201011501900001")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        nik_findings = [f for f in findings if f.entity_type == "ID_NIK"]
        assert len(nik_findings) == 1
        assert nik_findings[0].detected_text == "3201011501900001"
        assert nik_findings[0].is_validated

    def test_detect_invalid_nik_province(self, recognizer, make_segment, make_context):
        """Test that invalid province code is rejected."""
        # Province 99 is invalid
        segment = make_segment("NIK: 9901234567890123")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 0

    def test_detect_npwp(self, recognizer, make_segment, make_context):
        """Test detecting NPWP."""
        segment = make_segment("NPWP: 12.345.678.9-012.345")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        npwp_findings = [f for f in findings if f.entity_type == "ID_NPWP"]
        assert len(npwp_findings) == 1
        assert "12.345.678.9-012.345" in npwp_findings[0].detected_text

    def test_detect_phone(self, recognizer, make_segment, make_context):
        """Test detecting Indonesian phone number."""
        segment = make_segment("Telepon: 081234567890")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        phone_findings = [f for f in findings if f.entity_type == "ID_PHONE"]
        assert len(phone_findings) == 1
        assert phone_findings[0].detected_text == "081234567890"

    def test_detect_phone_with_country_code(self, recognizer, make_segment, make_context):
        """Test detecting phone with +62 country code."""
        segment = make_segment("Phone: +6281234567890")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        phone_findings = [f for f in findings if f.entity_type == "ID_PHONE"]
        assert len(phone_findings) == 1


# =============================================================================
# Custom Terms Recognizer Tests
# =============================================================================

class TestCustomTermsRecognizer:
    """Tests for CustomTermsRecognizer."""

    @pytest.fixture
    def make_segment(self):
        def _make(text: str) -> LogicalSegment:
            return LogicalSegment.for_txt_paragraph(
                text=text,
                file_id="test.txt",
                paragraph_index=0,
            )
        return _make

    @pytest.fixture
    def make_context(self):
        def _make(segment: LogicalSegment) -> DetectionContext:
            return DetectionContext(
                segment=segment,
                config=DetectionConfig(),
                file_type="txt",
            )
        return _make

    def test_detect_custom_term(self, make_segment, make_context):
        """Test detecting custom terms."""
        recognizer = CustomTermsRecognizer(terms=["Project Alpha", "secret"])
        segment = make_segment("This is about Project Alpha development.")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1
        assert findings[0].entity_type == "CUSTOM"
        assert findings[0].detected_text == "Project Alpha"
        assert findings[0].confidence_band == ConfidenceBand.CRITICAL

    def test_case_insensitive_by_default(self, make_segment, make_context):
        """Test case-insensitive matching."""
        recognizer = CustomTermsRecognizer(terms=["SECRET"])
        segment = make_segment("This is a secret message.")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1
        assert findings[0].detected_text == "secret"

    def test_case_sensitive_mode(self, make_segment, make_context):
        """Test case-sensitive matching."""
        recognizer = CustomTermsRecognizer(terms=["SECRET"], case_sensitive=True)
        segment = make_segment("This is a secret message.")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 0  # "secret" doesn't match "SECRET"

    def test_multiple_occurrences(self, make_segment, make_context):
        """Test finding multiple occurrences of same term."""
        recognizer = CustomTermsRecognizer(terms=["test"])
        segment = make_segment("test one, test two, test three")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 3


# =============================================================================
# Unified Detection Engine Tests
# =============================================================================

class TestUnifiedDetectionEngine:
    """Tests for UnifiedDetectionEngine."""

    @pytest.fixture
    def engine(self):
        engine = UnifiedDetectionEngine()
        # Register Indonesian ID recognizer for testing
        engine.register_recognizer(IndonesianIdRecognizer())
        engine.register_recognizer(CustomTermsRecognizer(terms=["secret"]))
        return engine

    @pytest.fixture
    def make_segment(self):
        def _make(
            text: str,
            file_id: str = "test.txt",
            key_label: str | None = None,
        ) -> LogicalSegment:
            return LogicalSegment.for_txt_paragraph(
                text=text,
                file_id=file_id,
                paragraph_index=0,
                key_label=key_label,
            )
        return _make

    def test_detect_basic(self, engine, make_segment):
        """Test basic detection."""
        # Valid NIK: province 32, district 01, subdistrict 01, date 150190, serial 0001
        segment = make_segment("NIK: 3201011501900001")
        findings = engine.detect(segment)

        assert len(findings) >= 1
        nik_findings = [f for f in findings if f.entity_type == "ID_NIK"]
        assert len(nik_findings) == 1

    def test_detect_with_custom_term(self, engine, make_segment):
        """Test detection with custom terms."""
        segment = make_segment("This is a secret project.")
        findings = engine.detect(segment)

        custom_findings = [f for f in findings if f.entity_type == "CUSTOM"]
        assert len(custom_findings) == 1
        assert custom_findings[0].confidence_band == ConfidenceBand.CRITICAL

    def test_detect_batch(self, engine, make_segment):
        """Test batch detection."""
        segments = [
            make_segment("NIK: 3201234567890123"),
            make_segment("Phone: 081234567890"),
            make_segment("No PII here"),
        ]

        results = engine.detect_batch(segments)

        assert len(results) == 3
        assert any(len(findings) > 0 for findings in results.values())

    def test_min_score_filtering(self, engine, make_segment):
        """Test findings below min_score are filtered."""
        segment = make_segment("081234567890")
        config = DetectionConfig(min_score=0.9)  # High threshold

        findings = engine.detect(segment, config)

        # Phone has score 0.75, should be filtered
        phone_findings = [f for f in findings if f.entity_type == "ID_PHONE"]
        assert len(phone_findings) == 0

    def test_allow_list_filtering(self, engine, make_segment):
        """Test allow list filters findings."""
        segment = make_segment("secret project")
        config = DetectionConfig(allow_list=["secret"])

        findings = engine.detect(segment, config)

        custom_findings = [f for f in findings if f.entity_type == "CUSTOM"]
        assert len(custom_findings) == 0

    def test_entity_filter(self, engine, make_segment):
        """Test filtering by entity type."""
        # Valid NIK for test
        segment = make_segment("NIK: 3201011501900001, secret code")
        config = DetectionConfig(entities=["ID_NIK"])  # Only NIK

        findings = engine.detect(segment, config)

        # Should only have NIK findings
        assert all(f.entity_type == "ID_NIK" for f in findings)

    def test_get_supported_entities(self, engine):
        """Test getting supported entities."""
        entities = engine.get_supported_entities()

        assert "ID_NIK" in entities
        assert "ID_NPWP" in entities
        assert "CUSTOM" in entities


# =============================================================================
# Context Boost Tests
# =============================================================================

class TestContextBoosting:
    """Tests for context-based confidence boosting."""

    def test_context_to_entity_mapping(self):
        """Test context label to entity mapping."""
        assert "ID_NIK" in CONTEXT_TO_ENTITY.get("nik", [])
        assert "PERSON" in CONTEXT_TO_ENTITY.get("nama", [])
        assert "EMAIL_ADDRESS" in CONTEXT_TO_ENTITY.get("email", [])
        assert "ID_PHONE" in CONTEXT_TO_ENTITY.get("telepon", [])


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the unified detection pipeline."""

    def test_full_pipeline(self):
        """Test full detection pipeline from segment to findings."""
        # Create engine with recognizers
        engine = UnifiedDetectionEngine()
        engine.register_recognizer(IndonesianIdRecognizer())

        # Create segment with context - valid NIK
        segment = LogicalSegment.for_txt_paragraph(
            text="3201011501900001",
            file_id="patient_data.txt",
            paragraph_index=0,
            key_label="NIK",  # Context hint
        )

        # Detect
        findings = engine.detect(segment)

        # Verify
        assert len(findings) >= 1
        nik_finding = next(
            (f for f in findings if f.entity_type == "ID_NIK"), None
        )
        assert nik_finding is not None
        assert nik_finding.segment_id == segment.id

    def test_overlap_resolution_in_pipeline(self):
        """Test that overlaps are resolved in the pipeline."""
        engine = UnifiedDetectionEngine()

        # Create a custom recognizer that produces overlapping findings
        class OverlappingRecognizer(BaseUnifiedRecognizer):
            def __init__(self):
                super().__init__("overlapper", ["TYPE_A", "TYPE_B"], priority=50)

            def analyze(self, segment, context):
                return [
                    UnifiedFinding(
                        segment_id=segment.id,
                        entity_type="TYPE_A",
                        start=0,
                        end=10,
                        raw_score=0.7,
                        detector="overlapper",
                        detected_text=segment.text[:10],
                    ),
                    UnifiedFinding(
                        segment_id=segment.id,
                        entity_type="TYPE_B",
                        start=0,
                        end=10,
                        raw_score=0.9,  # Higher score
                        detector="overlapper",
                        detected_text=segment.text[:10],
                    ),
                ]

        engine.register_recognizer(OverlappingRecognizer())

        segment = LogicalSegment.for_txt_paragraph(
            text="Some test text here",
            file_id="test.txt",
            paragraph_index=0,
        )

        findings = engine.detect(segment)

        # Should have resolved to single finding (higher score)
        assert len(findings) == 1
        assert findings[0].raw_score == 0.9
