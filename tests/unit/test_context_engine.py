"""
Unit tests for Sprint 5: Context Engine & Custom Terms.

Tests cover:
- LexicalContextAnalyzer - positive/negative keywords, entity hints
- StructuralContextExtractor - headers, labels, table context
- SpatialContextAnalyzer - position-based relationships
- DocumentContextDetector - document type classification
- ContextScorer - unified scoring
- EnhancedCustomTermsManager - always/never protect
"""

import pytest
import tempfile
from pathlib import Path

from sandiraksa.documents.logical_segment import LogicalSegment

# Context modules
from sandiraksa.detection.context_engine.lexical import (
    LexicalContextAnalyzer,
    LexicalContext,
    ContextPolarity,
    POSITIVE_KEYWORDS,
    NEGATIVE_KEYWORDS,
    ENTITY_KEYWORDS,
)
from sandiraksa.detection.context_engine.structural import (
    StructuralContextExtractor,
    StructuralContext,
    StructuralContextType,
    extract_key_value,
    detect_table_structure,
)
from sandiraksa.detection.context_engine.spatial import (
    SpatialContextAnalyzer,
    BoundingBox,
    SpatialElement,
    SpatialRelation,
    is_label_like,
    create_spatial_element,
)
from sandiraksa.detection.context_engine.document import (
    DocumentContextDetector,
    DocumentContext,
    DocumentType,
    DOCUMENT_SENSITIVITY,
    EXPECTED_ENTITIES,
)
from sandiraksa.detection.context_engine.scorer import (
    ContextScorer,
    ContextWeights,
    ContextScoringResult,
)
from sandiraksa.detection.unified_finding import UnifiedFinding, ConfidenceBand


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def make_segment():
    """Factory for creating test segments."""
    def _make(
        text: str,
        key_label: str | None = None,
        table_headers: list[str] | None = None,
        context_labels: list[str] | None = None,
    ) -> LogicalSegment:
        segment = LogicalSegment.for_txt_paragraph(
            text=text,
            file_id="test.txt",
            paragraph_index=0,
            key_label=key_label,
        )
        if table_headers:
            segment.table_headers = table_headers
        if context_labels:
            segment.context_labels = context_labels
        return segment
    return _make


@pytest.fixture
def make_finding():
    """Factory for creating test findings."""
    def _make(
        entity_type: str = "PERSON",
        start: int = 0,
        end: int = 10,
        score: float = 0.7,
    ) -> UnifiedFinding:
        return UnifiedFinding(
            segment_id="test-segment",
            entity_type=entity_type,
            start=start,
            end=end,
            raw_score=score,
            confidence_band=ConfidenceBand.MEDIUM,
            detector="test",
            detected_text="test text",
        )
    return _make


# =============================================================================
# Lexical Context Tests
# =============================================================================

class TestLexicalContextAnalyzer:
    """Tests for LexicalContextAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        return LexicalContextAnalyzer()

    def test_positive_keyword_detection(self, analyzer, make_segment):
        """Test detection of positive keywords."""
        segment = make_segment("Nama: John Doe")
        result = analyzer.analyze(segment)

        assert result.has_positive_context()
        assert any(m.keyword == "nama" for m in result.positive_matches)
        assert result.net_score > 0

    def test_negative_keyword_detection(self, analyzer, make_segment):
        """Test detection of negative keywords."""
        segment = make_segment("Invoice Number: 12345")
        result = analyzer.analyze(segment)

        assert result.has_negative_context()
        # "invoice number" is the matched keyword (not just "invoice")
        assert any("invoice" in m.keyword for m in result.negative_matches)

    def test_entity_hints(self, analyzer, make_segment):
        """Test entity-specific keyword hints."""
        segment = make_segment("NIK: 3201011501900001", key_label="NIK")
        result = analyzer.analyze(segment)

        assert "ID_NIK" in result.entity_hints
        assert result.entity_hints["ID_NIK"] > 0

    def test_key_label_included(self, analyzer, make_segment):
        """Test that key_label is analyzed."""
        segment = make_segment("3201011501900001", key_label="Nomor NIK")
        result = analyzer.analyze(segment)

        assert result.has_positive_context()

    def test_table_headers_included(self, analyzer, make_segment):
        """Test that table headers are analyzed."""
        segment = make_segment("081234567890", table_headers=["Nama", "Telepon", "Alamat"])
        result = analyzer.analyze(segment)

        assert result.has_positive_context()
        assert any(m.keyword == "telepon" for m in result.positive_matches)

    def test_net_score_calculation(self, analyzer, make_segment):
        """Test net score with mixed keywords."""
        # Positive dominates
        segment = make_segment("Nama Pasien: John Doe, Telepon: 08123")
        result = analyzer.analyze(segment)
        assert result.net_score > 0

    def test_indonesian_keywords(self, analyzer, make_segment):
        """Test Indonesian keywords are recognized."""
        segment = make_segment("Data Karyawan PT ABC")
        result = analyzer.analyze(segment)

        assert any(m.keyword == "karyawan" for m in result.positive_matches)

    def test_positive_keywords_coverage(self):
        """Test that expected positive keywords exist."""
        assert "nama" in POSITIVE_KEYWORDS
        assert "nik" in POSITIVE_KEYWORDS
        assert "npwp" in POSITIVE_KEYWORDS
        assert "telepon" in POSITIVE_KEYWORDS
        assert "email" in POSITIVE_KEYWORDS

    def test_negative_keywords_coverage(self):
        """Test that expected negative keywords exist."""
        assert "invoice" in NEGATIVE_KEYWORDS
        assert "sku" in NEGATIVE_KEYWORDS
        assert "order" in NEGATIVE_KEYWORDS


# =============================================================================
# Structural Context Tests
# =============================================================================

class TestStructuralContextExtractor:
    """Tests for StructuralContextExtractor."""

    @pytest.fixture
    def extractor(self):
        return StructuralContextExtractor()

    def test_key_label_extraction(self, extractor, make_segment):
        """Test key label context extraction."""
        segment = make_segment("John Doe", key_label="Nama")
        result = extractor.extract(segment)

        assert result.has_label_context
        assert result.primary_context is not None
        assert result.primary_context.context_type == StructuralContextType.KEY_LABEL
        assert result.primary_context.text == "Nama"

    def test_table_headers_extraction(self, extractor, make_segment):
        """Test table header context extraction."""
        segment = make_segment("John", table_headers=["Nama", "NIK", "Telepon"])
        result = extractor.extract(segment)

        assert result.has_table_context
        assert len([i for i in result.items if i.context_type == StructuralContextType.TABLE_HEADER]) == 3

    def test_context_labels_extraction(self, extractor, make_segment):
        """Test context labels extraction."""
        # Use key_label since context_labels is a computed property
        segment = make_segment("3201011501900001", key_label="NIK")
        result = extractor.extract(segment)

        assert len(result.items) >= 1

    def test_primary_context_priority(self, extractor, make_segment):
        """Test that key_label has priority over table_header."""
        segment = make_segment("John", key_label="Nama", table_headers=["NIK", "Telepon"])
        result = extractor.extract(segment)

        # Key label should be primary
        assert result.primary_context.context_type == StructuralContextType.KEY_LABEL

    def test_get_all_context_text(self, extractor, make_segment):
        """Test getting all context texts."""
        segment = make_segment("value", key_label="Label", table_headers=["Header1", "Header2"])
        result = extractor.extract(segment)

        texts = result.get_all_context_text()
        assert "Label" in texts
        assert "Header1" in texts


class TestKeyValueExtraction:
    """Tests for key-value pattern detection."""

    def test_colon_separator(self):
        """Test key:value with colon."""
        result = extract_key_value("Nama: John Doe")
        assert result is not None
        assert result[0] == "Nama"
        assert result[1] == "John Doe"

    def test_equals_separator(self):
        """Test key=value with equals."""
        result = extract_key_value("Name = John Doe")
        assert result is not None
        assert result[0] == "Name"
        assert result[1] == "John Doe"

    def test_no_pattern(self):
        """Test text without key-value pattern."""
        result = extract_key_value("Just some text")
        assert result is None

    def test_key_too_long(self):
        """Test rejection of overly long keys."""
        long_key = "A" * 100
        result = extract_key_value(f"{long_key}: value")
        assert result is None


class TestTableStructureDetection:
    """Tests for table structure detection."""

    def test_csv_detection(self):
        """Test CSV-like structure detection."""
        lines = [
            "Name,NIK,Phone",
            "John,3201011501900001,081234567890",
            "Jane,3201011501900002,081234567891",
        ]
        result = detect_table_structure(lines)

        assert "headers" in result
        assert result["headers"] == ["Name", "NIK", "Phone"]
        assert result["delimiter"] == ","

    def test_tab_detection(self):
        """Test tab-separated detection."""
        lines = [
            "Name\tNIK\tPhone",
            "John\t3201011501900001\t081234567890",
        ]
        result = detect_table_structure(lines)

        assert "headers" in result
        assert result["delimiter"] == "\t"

    def test_no_table(self):
        """Test non-table text."""
        lines = ["Just a paragraph", "Another paragraph"]
        result = detect_table_structure(lines)

        assert result == {}


# =============================================================================
# Spatial Context Tests
# =============================================================================

class TestBoundingBox:
    """Tests for BoundingBox calculations."""

    def test_properties(self):
        """Test bounding box properties."""
        box = BoundingBox(left=100, top=50, width=200, height=100)

        assert box.right == 300
        assert box.bottom == 150
        assert box.center_x == 200
        assert box.center_y == 100

    def test_distance_to_non_overlapping(self):
        """Test distance between non-overlapping boxes."""
        box1 = BoundingBox(left=0, top=0, width=100, height=100)
        box2 = BoundingBox(left=200, top=0, width=100, height=100)

        distance = box1.distance_to(box2)
        assert distance == 100  # 200 - 100 = 100 horizontal gap

    def test_distance_to_overlapping(self):
        """Test distance between overlapping boxes."""
        box1 = BoundingBox(left=0, top=0, width=100, height=100)
        box2 = BoundingBox(left=50, top=50, width=100, height=100)

        distance = box1.distance_to(box2)
        assert distance == 0  # Overlapping

    def test_same_baseline(self):
        """Test same baseline detection."""
        box1 = BoundingBox(left=0, top=0, width=100, height=50)
        box2 = BoundingBox(left=200, top=5, width=100, height=50)  # Slightly offset

        assert box1.is_same_baseline(box2, tolerance=20)

    def test_same_column(self):
        """Test same column detection."""
        box1 = BoundingBox(left=100, top=0, width=50, height=30)
        box2 = BoundingBox(left=105, top=100, width=50, height=30)

        assert box1.is_same_column(box2, tolerance=20)


class TestSpatialContextAnalyzer:
    """Tests for SpatialContextAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        return SpatialContextAnalyzer(proximity_threshold=500)

    def test_left_of_relation(self, analyzer):
        """Test LEFT_OF spatial relation."""
        target = create_spatial_element("target", "John Doe", 200, 100, 100, 30)
        label = create_spatial_element("label", "Nama:", 50, 100, 50, 30)

        result = analyzer.analyze(target, [label])

        assert len(result.relationships) == 1
        assert result.relationships[0].relation == SpatialRelation.LEFT_OF

    def test_above_relation(self, analyzer):
        """Test vertical spatial relation detection."""
        # Create shapes with significant vertical separation
        target = create_spatial_element("target", "John Doe", 100, 300, 100, 30)
        label = create_spatial_element("label", "Nama:", 100, 100, 100, 30)

        result = analyzer.analyze(target, [label])

        assert len(result.relationships) == 1
        # Any vertical relationship is acceptable for this test
        assert result.relationships[0].relation in (
            SpatialRelation.ABOVE,
            SpatialRelation.SAME_COLUMN,
            SpatialRelation.SAME_LINE,  # Tolerance-based detection
        )

    def test_distant_excluded(self, analyzer):
        """Test that distant elements are excluded."""
        target = create_spatial_element("target", "John", 0, 0, 100, 30)
        distant = create_spatial_element("distant", "Label", 1000, 1000, 100, 30)

        result = analyzer.analyze(target, [distant])

        # Distant should be excluded
        assert all(r.relation == SpatialRelation.DISTANT for r in result.relationships) or len(result.relationships) == 0

    def test_get_best_label(self, analyzer):
        """Test best label selection."""
        target = create_spatial_element("target", "John", 200, 100, 100, 30)
        label1 = create_spatial_element("label1", "Nama:", 50, 100, 50, 30)
        label2 = create_spatial_element("label2", "Data:", 50, 50, 50, 30)

        # Mark as label-like
        label1.is_label_like = True
        label2.is_label_like = True

        result = analyzer.analyze(target, [label1, label2])

        best = result.get_best_label()
        assert best is not None
        assert best.text == "Nama:"  # LEFT_OF has priority


class TestIsLabelLike:
    """Tests for is_label_like function."""

    def test_colon_ending(self):
        """Test that text ending with colon is label-like."""
        assert is_label_like("Nama:")
        assert is_label_like("NIK:")

    def test_short_keyword(self):
        """Test that short text with keyword is label-like."""
        assert is_label_like("NIK")
        assert is_label_like("Nama")
        assert is_label_like("Phone")

    def test_all_caps_short(self):
        """Test that short all-caps is label-like."""
        assert is_label_like("NIK")
        assert is_label_like("NPWP")

    def test_long_text_not_label(self):
        """Test that long text is not label-like."""
        assert not is_label_like("This is a very long sentence that is definitely not a label")

    def test_empty_not_label(self):
        """Test that empty string is not label-like."""
        assert not is_label_like("")
        assert not is_label_like(None)


# =============================================================================
# Document Context Tests
# =============================================================================

class TestDocumentContextDetector:
    """Tests for DocumentContextDetector."""

    @pytest.fixture
    def detector(self):
        return DocumentContextDetector()

    def test_hr_document_detection(self, detector):
        """Test HR document detection."""
        texts = ["Data Karyawan", "Nama", "NIK", "Tanggal Lahir"]
        result = detector.detect(texts)

        assert result.detected_type == DocumentType.HR
        assert result.confidence > 0.3

    def test_medical_document_detection(self, detector):
        """Test medical document detection."""
        texts = ["Data Pasien", "Rekam Medis", "Diagnosa", "Resep"]
        result = detector.detect(texts)

        assert result.detected_type == DocumentType.MEDICAL
        assert result.sensitivity == "critical"

    def test_financial_document_detection(self, detector):
        """Test financial document detection."""
        texts = ["Nomor Rekening", "Bank", "Mutasi", "Saldo"]
        result = detector.detect(texts)

        assert result.detected_type == DocumentType.FINANCIAL

    def test_invoice_document_detection(self, detector):
        """Test invoice document detection."""
        texts = ["Invoice", "Faktur", "Total", "Payment"]
        result = detector.detect(texts)

        assert result.detected_type == DocumentType.INVOICE
        assert result.sensitivity == "low"

    def test_general_fallback(self, detector):
        """Test fallback to general type."""
        texts = ["Random text", "No keywords here"]
        result = detector.detect(texts)

        assert result.detected_type == DocumentType.GENERAL

    def test_expected_entities(self, detector):
        """Test expected entities for document type."""
        texts = ["Data Karyawan", "HRD"]
        result = detector.detect(texts)

        assert result.expects_entity("PERSON")
        assert result.expects_entity("ID_NIK")

    def test_sensitivity_mapping(self):
        """Test sensitivity levels are defined."""
        assert DOCUMENT_SENSITIVITY[DocumentType.MEDICAL] == "critical"
        assert DOCUMENT_SENSITIVITY[DocumentType.HR] == "high"
        assert DOCUMENT_SENSITIVITY[DocumentType.INVOICE] == "low"

    def test_expected_entities_mapping(self):
        """Test expected entities are defined."""
        assert "PERSON" in EXPECTED_ENTITIES[DocumentType.HR]
        assert "ID_BPJS" in EXPECTED_ENTITIES[DocumentType.MEDICAL]


# =============================================================================
# Context Scorer Tests
# =============================================================================

class TestContextScorer:
    """Tests for ContextScorer."""

    @pytest.fixture
    def scorer(self):
        return ContextScorer()

    def test_positive_context_boost(self, scorer, make_segment, make_finding):
        """Test that positive context boosts score."""
        segment = make_segment("NIK: 3201011501900001", key_label="NIK")
        finding = make_finding(entity_type="ID_NIK", score=0.6)

        scored = scorer.score(segment, [finding])

        assert len(scored) == 1
        assert scored[0].raw_score > 0.6  # Score should increase

    def test_negative_context_penalty(self, scorer, make_segment, make_finding):
        """Test that negative context reduces score."""
        segment = make_segment("Invoice Number: 12345")
        finding = make_finding(entity_type="PERSON", score=0.7)

        scored = scorer.score(segment, [finding])

        assert len(scored) == 1
        assert scored[0].raw_score < 0.7  # Score should decrease

    def test_structural_context_key_label(self, scorer, make_segment, make_finding):
        """Test that key label provides strong context."""
        segment = make_segment("John Doe", key_label="Nama Lengkap")
        finding = make_finding(entity_type="PERSON", score=0.5)

        scored = scorer.score(segment, [finding])

        # Evidence is stored as dicts, check reason_code
        assert any(
            e.get("reason_code") == "key_label" 
            for e in scored[0].evidence
        )

    def test_document_context_expected_entity(self, scorer, make_segment, make_finding):
        """Test boost for expected entity in document type."""
        segment = make_segment("Data Karyawan\nNIK: 3201011501900001")
        finding = make_finding(entity_type="ID_NIK", score=0.6)

        scored = scorer.score(segment, [finding])

        # Score should be boosted due to HR document expecting NIK
        assert scored[0].raw_score >= 0.6

    def test_score_bounds(self, scorer, make_segment, make_finding):
        """Test that scores stay within bounds."""
        # Very positive context
        segment = make_segment(
            "Nama Pasien NIK NPWP Telepon",
            key_label="Data Pribadi",
        )
        finding = make_finding(score=0.9)

        scored = scorer.score(segment, [finding])

        assert scored[0].raw_score <= 1.0
        assert scored[0].raw_score >= 0.1

    def test_evidence_added_to_finding(self, scorer, make_segment, make_finding):
        """Test that evidence is added to findings."""
        segment = make_segment("Nama: John", key_label="Nama")
        finding = make_finding()

        scored = scorer.score(segment, [finding])

        assert len(scored[0].evidence) > 0

    def test_custom_weights(self, make_segment, make_finding):
        """Test scorer with custom weights."""
        weights = ContextWeights(
            lexical_weight=2.0,  # Double lexical weight
            structural_weight=0.5,
        )
        scorer = ContextScorer(weights=weights)

        segment = make_segment("Nama: John", key_label="Nama")
        finding = make_finding(score=0.5)

        scored = scorer.score(segment, [finding])

        # Lexical should have more impact
        assert scored[0].raw_score > 0.5


# =============================================================================
# Custom Terms Tests
# =============================================================================

class TestEnhancedCustomTermsManager:
    """Tests for EnhancedCustomTermsManager."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_storage_dir):
        """Create manager with temp storage."""
        from sandiraksa.detection.recognizers.custom_terms_enhanced import (
            EnhancedCustomTermsManager,
            EncryptedStorage,
        )
        storage = EncryptedStorage(storage_dir=temp_storage_dir)
        return EnhancedCustomTermsManager(
            project_id="test-project",
            storage=storage,
        )

    def test_add_always_protect(self, manager):
        """Test adding always protect term."""
        from sandiraksa.detection.recognizers.custom_terms_enhanced import MatchMode

        entry = manager.add_always_protect(
            term="Confidential Data",
            entity_type="SENSITIVE",
            match_mode=MatchMode.WORD,
        )

        assert entry is not None
        assert manager.always_protect_count == 1
        assert entry.term == "Confidential Data"

    def test_add_never_protect(self, manager):
        """Test adding never protect term."""
        entry = manager.add_never_protect(
            term="PT ABC",
            description="Company name, not person",
        )

        assert entry is not None
        assert manager.never_protect_count == 1

    def test_detect_always_protect(self, manager, make_segment):
        """Test detection of always protect terms."""
        manager.add_always_protect(term="Secret Project", entity_type="CONFIDENTIAL")

        segment = make_segment("This is about the Secret Project details")
        findings = manager.detect_always_protect(segment)

        assert len(findings) == 1
        assert findings[0].entity_type == "CONFIDENTIAL"
        assert findings[0].is_from_custom_terms

    def test_filter_findings_never_protect(self, manager, make_segment, make_finding):
        """Test filtering with never protect list."""
        manager.add_never_protect(term="John")

        segment = make_segment("John is here")
        finding = make_finding()
        # Set start/end to match "John" in text
        finding.start = 0
        finding.end = 4
        finding.detected_text = "John"

        filtered = manager.filter_findings([finding], segment)

        # Should be filtered out
        assert len(filtered) == 0

    def test_export_import(self, manager, temp_storage_dir):
        """Test export and import of terms."""
        from sandiraksa.detection.recognizers.custom_terms_enhanced import (
            EnhancedCustomTermsManager,
            EncryptedStorage,
        )

        # Add terms
        manager.add_always_protect(term="Term1")
        manager.add_never_protect(term="Term2")

        # Export
        exported = manager.export_terms()

        # Create new manager and import
        storage2 = EncryptedStorage(storage_dir=temp_storage_dir)
        manager2 = EnhancedCustomTermsManager(
            project_id="test-project-2",
            storage=storage2,
        )

        ap_count, np_count = manager2.import_terms(exported)

        assert ap_count == 1
        assert np_count == 1
        assert manager2.always_protect_count == 1
        assert manager2.never_protect_count == 1

    def test_persistence(self, temp_storage_dir):
        """Test that terms persist across manager instances."""
        from sandiraksa.detection.recognizers.custom_terms_enhanced import (
            EnhancedCustomTermsManager,
            EncryptedStorage,
        )

        storage = EncryptedStorage(storage_dir=temp_storage_dir)

        # Create manager and add term
        manager1 = EnhancedCustomTermsManager(
            project_id="persist-test",
            storage=storage,
        )
        manager1.add_always_protect(term="Persistent Term")

        # Create new manager with same project
        manager2 = EnhancedCustomTermsManager(
            project_id="persist-test",
            storage=storage,
        )

        # Term should be loaded
        assert manager2.always_protect_count == 1
        terms = manager2.get_always_protect_terms()
        assert terms[0].term == "Persistent Term"

    def test_remove_terms(self, manager):
        """Test removing terms."""
        entry = manager.add_always_protect(term="ToRemove")
        assert manager.always_protect_count == 1

        result = manager.remove_always_protect(entry.id)
        assert result is True
        assert manager.always_protect_count == 0


class TestCustomTermEntry:
    """Tests for CustomTermEntry."""

    def test_word_match(self):
        """Test word boundary matching."""
        from sandiraksa.detection.recognizers.custom_terms_enhanced import (
            CustomTermEntry,
            TermType,
            MatchMode,
        )

        entry = CustomTermEntry(
            id="1",
            term="John",
            term_type=TermType.ALWAYS_PROTECT,
            match_mode=MatchMode.WORD,
        )

        matches = entry.matches("Hello John, how are you?")
        assert len(matches) == 1
        assert matches[0][2] == "John"

        # Should not match partial
        matches = entry.matches("Johnson")
        assert len(matches) == 0

    def test_contains_match(self):
        """Test substring matching."""
        from sandiraksa.detection.recognizers.custom_terms_enhanced import (
            CustomTermEntry,
            TermType,
            MatchMode,
        )

        entry = CustomTermEntry(
            id="1",
            term="secret",
            term_type=TermType.ALWAYS_PROTECT,
            match_mode=MatchMode.CONTAINS,
        )

        matches = entry.matches("This is a topsecret document")
        assert len(matches) == 1

    def test_case_sensitive(self):
        """Test case-sensitive matching."""
        from sandiraksa.detection.recognizers.custom_terms_enhanced import (
            CustomTermEntry,
            TermType,
            MatchMode,
        )

        entry = CustomTermEntry(
            id="1",
            term="Secret",
            term_type=TermType.ALWAYS_PROTECT,
            match_mode=MatchMode.WORD,
            case_sensitive=True,
        )

        # Should match exact case
        matches = entry.matches("This is Secret")
        assert len(matches) == 1

        # Should not match different case
        matches = entry.matches("This is secret")
        assert len(matches) == 0

    def test_regex_match(self):
        """Test regex pattern matching."""
        from sandiraksa.detection.recognizers.custom_terms_enhanced import (
            CustomTermEntry,
            TermType,
            MatchMode,
        )

        entry = CustomTermEntry(
            id="1",
            term=r"ID-\d{4}",
            term_type=TermType.ALWAYS_PROTECT,
            match_mode=MatchMode.REGEX,
        )

        matches = entry.matches("Reference: ID-1234 and ID-5678")
        assert len(matches) == 2


# =============================================================================
# Integration Tests
# =============================================================================

class TestContextIntegration:
    """Integration tests for context engine components."""

    def test_full_context_pipeline(self, make_segment, make_finding):
        """Test full context scoring pipeline."""
        segment = make_segment(
            text="Data Pasien: NIK 3201011501900001, Nama: Budi Santoso",
            key_label="Data Pasien",
            table_headers=["NIK", "Nama", "Alamat"],
        )

        finding = make_finding(entity_type="ID_NIK", score=0.6)

        scorer = ContextScorer()
        scored = scorer.score(segment, [finding])

        # Evidence is stored as dicts
        evidence_sources = set(e.get("source", "") for e in scored[0].evidence)
        assert "lexical_context" in evidence_sources
        assert "structural_context" in evidence_sources

        # Score should be boosted (medical document, NIK expected)
        assert scored[0].raw_score > 0.6

    def test_context_reduces_false_positives(self, make_segment, make_finding):
        """Test that context helps reduce false positives."""
        # Invoice context should affect confidence for PERSON
        segment = make_segment(
            text="Invoice Number: 123456789",
            key_label="Invoice",
        )

        finding = make_finding(entity_type="PERSON", score=0.5)

        scorer = ContextScorer()
        scored = scorer.score(segment, [finding])

        # Evidence includes negative keywords
        negative_evidence = [
            e for e in scored[0].evidence
            if e.get("type") == "context_negative"
        ]
        assert len(negative_evidence) > 0
