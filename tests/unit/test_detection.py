"""Tests for detection engine module."""

import pytest

from sandiraksa.detection import (
    BaseRecognizer,
    DetectionConfig,
    DetectionContext,
    DetectionEngine,
    DetectionPhase,
    DetectionResult,
    EntityCategory,
    EntityType,
    RecognizerRegistry,
    TextSegment,
    get_entity_registry,
)
from sandiraksa.domain.finding import DocumentLocation


class MockRecognizer(BaseRecognizer):
    """Mock recognizer for testing."""

    def __init__(self, name: str, entities: list[str], mock_results: list[DetectionResult] = None):
        super().__init__(name, entities)
        self._mock_results = mock_results or []

    def analyze(self, text: str, entities: list[str]) -> list[DetectionResult]:
        # Filter results to requested entities
        return [r for r in self._mock_results if r.entity_type in entities]


class TestEntityTypeRegistry:
    """Tests for EntityTypeRegistry."""

    def test_get_builtin_type(self):
        """Should get built-in entity types."""
        registry = get_entity_registry()
        
        person = registry.get("PERSON")
        assert person is not None
        assert person.display_name == "Person Name"
        assert person.category == EntityCategory.PERSONAL

    def test_get_indonesian_types(self):
        """Should get Indonesian-specific types."""
        registry = get_entity_registry()
        
        nik = registry.get("ID_NIK")
        assert nik is not None
        assert nik.category == EntityCategory.GOVERNMENT
        
        id_types = registry.indonesian_types()
        assert len(id_types) >= 7  # NIK, NPWP, KK, PHONE, PASSPORT, SIM, BPJS

    def test_enabled_by_default(self):
        """Should return types enabled by default."""
        registry = get_entity_registry()
        
        enabled = registry.enabled_by_default()
        assert len(enabled) > 0
        
        # DATE_TIME should NOT be enabled by default
        assert not any(t.name == "DATE_TIME" for t in enabled)

    def test_register_custom_type(self):
        """Should allow registering custom types."""
        registry = get_entity_registry()
        
        custom = EntityType(
            name="TEST_CUSTOM",
            display_name="Test Custom",
            display_name_id="Tes Kustom",
            category=EntityCategory.CUSTOM,
        )
        
        registry.register(custom)
        
        retrieved = registry.get("TEST_CUSTOM")
        assert retrieved is not None
        assert retrieved.display_name == "Test Custom"
        
        # Cleanup
        registry.unregister("TEST_CUSTOM")


class TestRecognizerRegistry:
    """Tests for RecognizerRegistry."""

    def test_register_and_get(self):
        """Should register and retrieve recognizers."""
        registry = RecognizerRegistry()
        recognizer = MockRecognizer("test", ["PERSON", "EMAIL_ADDRESS"])
        
        registry.register(recognizer)
        
        retrieved = registry.get("test")
        assert retrieved is not None
        assert retrieved.name == "test"

    def test_get_for_entity(self):
        """Should find recognizers by entity type."""
        registry = RecognizerRegistry()
        recognizer1 = MockRecognizer("rec1", ["PERSON"])
        recognizer2 = MockRecognizer("rec2", ["PERSON", "EMAIL_ADDRESS"])
        
        registry.register(recognizer1)
        registry.register(recognizer2)
        
        person_recs = registry.get_for_entity("PERSON")
        assert len(person_recs) == 2
        
        email_recs = registry.get_for_entity("EMAIL_ADDRESS")
        assert len(email_recs) == 1

    def test_supported_entities(self):
        """Should track all supported entities."""
        registry = RecognizerRegistry()
        registry.register(MockRecognizer("rec1", ["PERSON"]))
        registry.register(MockRecognizer("rec2", ["EMAIL_ADDRESS", "PHONE_NUMBER"]))
        
        supported = registry.supported_entities
        assert "PERSON" in supported
        assert "EMAIL_ADDRESS" in supported
        assert "PHONE_NUMBER" in supported


class TestDetectionResult:
    """Tests for DetectionResult."""

    def test_overlap_detection(self):
        """Should detect overlapping results."""
        r1 = DetectionResult(
            entity_type="PERSON",
            start=0,
            end=10,
            text="John Smith",
            score=0.9,
        )
        r2 = DetectionResult(
            entity_type="PERSON",
            start=5,
            end=15,
            text="Smith Jane",
            score=0.8,
        )
        r3 = DetectionResult(
            entity_type="EMAIL_ADDRESS",
            start=20,
            end=35,
            text="test@example.com",
            score=0.95,
        )
        
        assert r1.overlaps_with(r2)
        assert r2.overlaps_with(r1)
        assert not r1.overlaps_with(r3)

    def test_confidence_band(self):
        """Should map score to confidence band."""
        high = DetectionResult("PERSON", 0, 5, "John", 0.95)
        medium = DetectionResult("PERSON", 0, 5, "John", 0.75)
        low = DetectionResult("PERSON", 0, 5, "John", 0.55)
        
        assert high.confidence_band.value == "high"
        assert medium.confidence_band.value == "medium"
        assert low.confidence_band.value == "low"


class TestDetectionConfig:
    """Tests for DetectionConfig."""

    def test_default_config(self):
        """Should create default config with enabled types."""
        config = DetectionConfig.default()
        
        assert len(config.enabled_entity_types) > 0
        assert "PERSON" in config.enabled_entity_types
        assert "EMAIL_ADDRESS" in config.enabled_entity_types

    def test_min_confidence_threshold(self):
        """Default min confidence should be set."""
        config = DetectionConfig.default()
        assert config.min_confidence == 0.7


class TestDetectionContext:
    """Tests for DetectionContext."""

    def test_add_result_filters_by_confidence(self):
        """Should filter results below confidence threshold."""
        context = DetectionContext(
            operation_id="op1",
            file_id="file1",
            project_id="proj1",
        )
        context.config.min_confidence = 0.8
        context.config.enabled_entity_types = {"PERSON"}
        
        high_conf = DetectionResult("PERSON", 0, 5, "John", 0.9)
        low_conf = DetectionResult("PERSON", 10, 15, "Jane", 0.6)
        
        context.add_result(high_conf)
        context.add_result(low_conf)
        
        assert len(context.results) == 1
        assert context.results[0].text == "John"

    def test_add_result_filters_by_entity_type(self):
        """Should filter results for disabled entity types."""
        context = DetectionContext(
            operation_id="op1",
            file_id="file1",
            project_id="proj1",
        )
        context.config.enabled_entity_types = {"PERSON"}  # Only PERSON enabled
        
        person = DetectionResult("PERSON", 0, 5, "John", 0.9)
        email = DetectionResult("EMAIL_ADDRESS", 10, 25, "test@test.com", 0.9)
        
        context.add_result(person)
        context.add_result(email)
        
        assert len(context.results) == 1
        assert context.results[0].entity_type == "PERSON"

    def test_resolve_overlapping(self):
        """Should resolve overlapping results."""
        context = DetectionContext(
            operation_id="op1",
            file_id="file1",
            project_id="proj1",
        )
        context.config.enabled_entity_types = {"PERSON"}
        context.config.resolve_overlaps = True
        
        # Add overlapping results with different confidence
        r1 = DetectionResult("PERSON", 0, 10, "John Smith", 0.8)
        r2 = DetectionResult("PERSON", 5, 15, "Smith Jane", 0.95)  # Higher confidence
        
        context.results = [r1, r2]
        context.resolve_overlapping_results()
        
        # Higher confidence should win
        assert len(context.results) == 1
        assert context.results[0].score == 0.95

    def test_lifecycle(self):
        """Should track phases correctly."""
        context = DetectionContext(
            operation_id="op1",
            file_id="file1",
            project_id="proj1",
        )
        
        assert context.phase == DetectionPhase.INITIALIZING
        
        context.start()
        assert context.phase == DetectionPhase.SCANNING
        assert context.stats.start_time is not None
        
        context.complete()
        assert context.phase == DetectionPhase.COMPLETED
        assert context.stats.end_time is not None


class TestDetectionEngine:
    """Tests for DetectionEngine."""

    def test_engine_initialization(self):
        """Should initialize and shutdown cleanly."""
        engine = DetectionEngine()
        
        engine.initialize()
        assert engine._initialized
        
        engine.shutdown()
        assert not engine._initialized

    def test_analyze_text(self):
        """Should analyze text with registered recognizers."""
        engine = DetectionEngine()
        engine.initialize()
        
        # Register mock recognizer
        mock_results = [
            DetectionResult("PERSON", 0, 10, "John Smith", 0.9),
        ]
        recognizer = MockRecognizer("mock", ["PERSON"], mock_results)
        engine.registry.register(recognizer)
        
        # Create context
        context = DetectionContext(
            operation_id="op1",
            file_id="file1",
            project_id="proj1",
        )
        context.config.enabled_entity_types = {"PERSON"}
        
        # Analyze
        results = engine.analyze_text("John Smith is a person", context)
        
        assert len(results) == 1
        assert results[0].entity_type == "PERSON"
        
        engine.shutdown()

    def test_analyze_segment_with_location(self):
        """Should attach location to results."""
        engine = DetectionEngine()
        engine.initialize()
        
        mock_results = [
            DetectionResult("EMAIL_ADDRESS", 0, 16, "test@example.com", 0.95),
        ]
        recognizer = MockRecognizer("mock", ["EMAIL_ADDRESS"], mock_results)
        engine.registry.register(recognizer)
        
        context = DetectionContext(
            operation_id="op1",
            file_id="file1",
            project_id="proj1",
        )
        context.config.enabled_entity_types = {"EMAIL_ADDRESS"}
        
        segment = TextSegment(
            text="test@example.com",
            location=DocumentLocation(
                element_type="cell",
                element_id="A1",
                worksheet_name="Sheet1",
            ),
            parent_offset=0,
        )
        
        results = engine.analyze_segment(segment, context)
        
        assert len(results) == 1
        assert results[0].document_location is not None
        assert results[0].document_location.element_type == "cell"
        
        engine.shutdown()
