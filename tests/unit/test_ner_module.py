"""
Unit tests for NER module.

Tests for:
- NER base types (NERPrediction, NERConfig, NEREntityType)
- Mock providers
- Batch processing
- Model loader (without actual model)
- Indonesian NER recognizer (with mock)
"""

import pytest
from unittest.mock import MagicMock, patch

from sandiraksa.detection.ner.base import (
    NERPrediction,
    NERConfig,
    NERResult,
    NEREntityType,
    BaseNERProvider,
)
from sandiraksa.detection.ner.onnx_provider import MockNERProvider
from sandiraksa.detection.ner.batch import (
    BatchConfig,
    BatchProgress,
    NERBatchProcessor,
)
from sandiraksa.detection.ner.loader import (
    NERModelLoader,
    is_ner_available,
)
from sandiraksa.detection.ner.recognizer import (
    IndonesianNERRecognizer,
    MockIndonesianNERRecognizer,
    NER_TO_PRESIDIO_ENTITY,
)


class TestNEREntityType:
    """Tests for NEREntityType enum and normalization."""

    def test_normalize_standard_types(self):
        """Test normalization of standard entity types."""
        assert NEREntityType.normalize("PERSON") == "PERSON"
        assert NEREntityType.normalize("ORG") == "ORG"
        assert NEREntityType.normalize("LOC") == "LOC"
        assert NEREntityType.normalize("MISC") == "MISC"

    def test_normalize_bio_tags(self):
        """Test normalization strips BIO prefixes."""
        assert NEREntityType.normalize("B-PER") == "PERSON"
        assert NEREntityType.normalize("I-PER") == "PERSON"
        assert NEREntityType.normalize("B-ORG") == "ORG"
        assert NEREntityType.normalize("I-ORG") == "ORG"
        assert NEREntityType.normalize("B-LOC") == "LOC"
        assert NEREntityType.normalize("I-LOC") == "LOC"

    def test_normalize_aliases(self):
        """Test normalization of alias types."""
        assert NEREntityType.normalize("PER") == "PERSON"
        assert NEREntityType.normalize("GPE") == "LOC"
        assert NEREntityType.normalize("LOCATION") == "LOC"
        assert NEREntityType.normalize("ORGANIZATION") == "ORG"

    def test_normalize_case_insensitive(self):
        """Test normalization handles case."""
        assert NEREntityType.normalize("person") == "PERSON"
        assert NEREntityType.normalize("org") == "ORG"
        assert NEREntityType.normalize("b-per") == "PERSON"


class TestNERPrediction:
    """Tests for NERPrediction dataclass."""

    def test_creation(self):
        """Test basic prediction creation."""
        pred = NERPrediction(
            start=0,
            end=4,
            text="Budi",
            entity_type="PERSON",
            score=0.95,
        )
        assert pred.start == 0
        assert pred.end == 4
        assert pred.text == "Budi"
        assert pred.entity_type == "PERSON"
        assert pred.score == 0.95
        assert pred.source == "ner"

    def test_entity_type_normalized(self):
        """Test entity type is normalized on creation."""
        pred = NERPrediction(
            start=0,
            end=4,
            text="Budi",
            entity_type="B-PER",
            score=0.95,
        )
        assert pred.entity_type == "PERSON"

    def test_length_property(self):
        """Test length property calculation."""
        pred = NERPrediction(start=5, end=15, text="PT Maju", entity_type="ORG", score=0.9)
        assert pred.length == 10

    def test_overlaps_with(self):
        """Test overlap detection."""
        pred1 = NERPrediction(start=0, end=10, text="Budi San", entity_type="PERSON", score=0.9)
        pred2 = NERPrediction(start=5, end=15, text="Santoso", entity_type="PERSON", score=0.8)
        pred3 = NERPrediction(start=20, end=30, text="Jakarta", entity_type="LOC", score=0.9)

        assert pred1.overlaps_with(pred2)
        assert pred2.overlaps_with(pred1)
        assert not pred1.overlaps_with(pred3)
        assert not pred3.overlaps_with(pred1)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        pred = NERPrediction(
            start=0,
            end=4,
            text="Budi",
            entity_type="PERSON",
            score=0.95,
            source="onnx_ner",
        )
        d = pred.to_dict()
        assert d["start"] == 0
        assert d["end"] == 4
        assert d["text"] == "Budi"
        assert d["entity_type"] == "PERSON"
        assert d["score"] == 0.95
        assert d["source"] == "onnx_ner"


class TestNERConfig:
    """Tests for NERConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = NERConfig()
        assert config.min_score == 0.5
        assert config.enabled_entities is None
        assert config.max_length == 512
        assert config.batch_size == 32

    def test_should_detect_all(self):
        """Test should_detect with no filter."""
        config = NERConfig()
        assert config.should_detect("PERSON")
        assert config.should_detect("ORG")
        assert config.should_detect("LOC")
        assert config.should_detect("MISC")

    def test_should_detect_filtered(self):
        """Test should_detect with entity filter."""
        config = NERConfig(enabled_entities={"PERSON", "ORG"})
        assert config.should_detect("PERSON")
        assert config.should_detect("ORG")
        assert not config.should_detect("LOC")
        assert not config.should_detect("MISC")


class TestNERResult:
    """Tests for NERResult container."""

    def test_empty_result(self):
        """Test empty result."""
        result = NERResult(text="Hello")
        assert result.entity_count == 0
        assert result.get_persons() == []
        assert result.get_organizations() == []
        assert result.get_locations() == []

    def test_result_with_predictions(self):
        """Test result with predictions."""
        preds = [
            NERPrediction(start=0, end=4, text="Budi", entity_type="PERSON", score=0.9),
            NERPrediction(start=20, end=30, text="PT Maju", entity_type="ORG", score=0.85),
            NERPrediction(start=40, end=47, text="Jakarta", entity_type="LOC", score=0.95),
        ]
        result = NERResult(text="Budi bekerja di PT Maju, Jakarta", predictions=preds)

        assert result.entity_count == 3
        assert len(result.get_persons()) == 1
        assert len(result.get_organizations()) == 1
        assert len(result.get_locations()) == 1

    def test_get_entities_by_type(self):
        """Test filtering by entity type."""
        preds = [
            NERPrediction(start=0, end=4, text="Budi", entity_type="PERSON", score=0.9),
            NERPrediction(start=10, end=14, text="Siti", entity_type="PERSON", score=0.85),
        ]
        result = NERResult(text="Budi dan Siti", predictions=preds)

        persons = result.get_entities_by_type("PERSON")
        assert len(persons) == 2


class TestBaseNERProvider:
    """Tests for BaseNERProvider."""

    def test_init(self):
        """Test initialization."""
        provider = BaseNERProvider(name="test", supported_entities=["PERSON"])
        assert provider.name == "test"
        assert provider.supported_entities == ["PERSON"]
        assert not provider.is_loaded

    def test_load_unload(self):
        """Test load/unload state."""
        provider = BaseNERProvider()
        assert not provider.is_loaded
        provider.load()
        assert provider.is_loaded
        provider.unload()
        assert not provider.is_loaded

    def test_filter_predictions(self):
        """Test prediction filtering."""
        provider = BaseNERProvider()
        preds = [
            NERPrediction(start=0, end=4, text="Budi", entity_type="PERSON", score=0.9),
            NERPrediction(start=10, end=17, text="Jakarta", entity_type="LOC", score=0.3),  # Low score
            NERPrediction(start=20, end=27, text="PT Maju", entity_type="ORG", score=0.8),
        ]
        config = NERConfig(min_score=0.5, enabled_entities={"PERSON", "ORG"})

        filtered = provider._filter_predictions(preds, config)
        assert len(filtered) == 2
        assert filtered[0].text == "Budi"
        assert filtered[1].text == "PT Maju"

    def test_resolve_overlaps(self):
        """Test overlap resolution."""
        provider = BaseNERProvider()
        preds = [
            NERPrediction(start=0, end=10, text="Budi Santo", entity_type="PERSON", score=0.9),
            NERPrediction(start=5, end=12, text="Santoso", entity_type="PERSON", score=0.7),  # Overlap
        ]

        resolved = provider._resolve_overlaps(preds)
        assert len(resolved) == 1
        assert resolved[0].score == 0.9  # Higher score kept


class TestMockNERProvider:
    """Tests for MockNERProvider."""

    def test_empty_provider(self):
        """Test empty mock provider."""
        provider = MockNERProvider()
        results = provider.predict(["Hello world"])
        assert len(results) == 1
        assert results[0].entity_count == 0

    def test_with_predictions(self):
        """Test mock with predefined predictions."""
        text = "Budi tinggal di Jakarta"
        preds = [
            NERPrediction(start=0, end=4, text="Budi", entity_type="PERSON", score=0.9),
            NERPrediction(start=16, end=23, text="Jakarta", entity_type="LOC", score=0.95),
        ]
        provider = MockNERProvider(predictions_map={text: preds})

        results = provider.predict([text])
        assert len(results) == 1
        assert results[0].entity_count == 2

    def test_add_prediction(self):
        """Test adding predictions dynamically."""
        provider = MockNERProvider()
        text = "PT Maju Jaya"

        provider.add_prediction(text, 0, 12, "ORG", 0.9)
        results = provider.predict([text])

        assert results[0].entity_count == 1
        assert results[0].predictions[0].entity_type == "ORG"

    def test_predict_single(self):
        """Test single text prediction."""
        text = "Budi"
        provider = MockNERProvider()
        provider.add_prediction(text, 0, 4, "PERSON", 0.9)

        result = provider.predict_single(text)
        assert result.entity_count == 1


class TestBatchConfig:
    """Tests for BatchConfig."""

    def test_default_values(self):
        """Test default configuration."""
        config = BatchConfig()
        assert config.batch_size == 32
        assert config.max_text_length == 512
        assert config.chunk_overlap == 50

    def test_validation_batch_size(self):
        """Test batch_size validation."""
        with pytest.raises(ValueError):
            BatchConfig(batch_size=0)

    def test_validation_max_text_length(self):
        """Test max_text_length validation."""
        with pytest.raises(ValueError):
            BatchConfig(max_text_length=50)

    def test_validation_chunk_overlap(self):
        """Test chunk_overlap validation."""
        with pytest.raises(ValueError):
            BatchConfig(chunk_overlap=600, max_text_length=512)


class TestBatchProgress:
    """Tests for BatchProgress."""

    def test_progress_percent(self):
        """Test progress percentage calculation."""
        progress = BatchProgress(total_texts=100, processed_texts=25)
        assert progress.progress_percent == 25.0

    def test_progress_percent_zero_total(self):
        """Test progress with zero total."""
        progress = BatchProgress(total_texts=0)
        assert progress.progress_percent == 100.0


class TestNERBatchProcessor:
    """Tests for NERBatchProcessor."""

    def test_empty_input(self):
        """Test processing empty list."""
        provider = MockNERProvider()
        processor = NERBatchProcessor(provider)

        results = processor.process([])
        assert results == []

    def test_single_text(self):
        """Test processing single text."""
        text = "Budi tinggal di Jakarta"
        provider = MockNERProvider()
        provider.add_prediction(text, 0, 4, "PERSON", 0.9)

        processor = NERBatchProcessor(provider)
        results = processor.process([text])

        assert len(results) == 1
        assert results[0].entity_count == 1

    def test_multiple_texts(self):
        """Test processing multiple texts."""
        texts = [
            "Budi Santoso",
            "PT Maju Jaya",
            "Kota Jakarta",
        ]
        provider = MockNERProvider()
        provider.add_prediction(texts[0], 0, 12, "PERSON", 0.9)
        provider.add_prediction(texts[1], 0, 12, "ORG", 0.85)
        provider.add_prediction(texts[2], 5, 12, "LOC", 0.9)

        processor = NERBatchProcessor(provider)
        results = processor.process(texts)

        assert len(results) == 3
        assert results[0].predictions[0].entity_type == "PERSON"
        assert results[1].predictions[0].entity_type == "ORG"
        assert results[2].predictions[0].entity_type == "LOC"

    def test_progress_callback(self):
        """Test progress callback is called."""
        provider = MockNERProvider()
        processor = NERBatchProcessor(provider, BatchConfig(batch_size=2))

        progress_updates = []

        def on_progress(p):
            progress_updates.append(p.progress_percent)

        processor.process(["a", "b", "c", "d"], progress_callback=on_progress)

        assert len(progress_updates) > 0

    def test_chunking_long_text(self):
        """Test long text is chunked."""
        # Create a text longer than max_text_length
        long_text = "Budi " * 200  # ~1000 chars
        provider = MockNERProvider()

        config = BatchConfig(max_text_length=100, chunk_overlap=20)
        processor = NERBatchProcessor(provider, config)

        # Should not raise
        results = processor.process([long_text])
        assert len(results) == 1


class TestNERModelLoader:
    """Tests for NERModelLoader."""

    def test_singleton_instance(self):
        """Test singleton pattern."""
        loader1 = NERModelLoader.get_instance()
        loader2 = NERModelLoader.get_instance()
        assert loader1 is loader2

    def test_reset_instance(self):
        """Test singleton reset."""
        loader1 = NERModelLoader.get_instance()
        NERModelLoader.reset_instance()
        loader2 = NERModelLoader.get_instance()
        assert loader1 is not loader2

    def test_is_available_no_model(self):
        """Test is_available when no model exists."""
        NERModelLoader.reset_instance()
        loader = NERModelLoader.get_instance()
        # Without actual model files, should return False
        # (unless running in environment with model installed)
        result = loader.is_available()
        assert isinstance(result, bool)

    def test_module_function_is_ner_available(self):
        """Test module-level is_ner_available function."""
        NERModelLoader.reset_instance()
        result = is_ner_available()
        assert isinstance(result, bool)


class TestIndonesianNERRecognizer:
    """Tests for IndonesianNERRecognizer."""

    def test_entity_mapping(self):
        """Test NER to Presidio entity mapping."""
        assert NER_TO_PRESIDIO_ENTITY["PERSON"] == "PERSON"
        assert NER_TO_PRESIDIO_ENTITY["PER"] == "PERSON"
        assert NER_TO_PRESIDIO_ENTITY["ORG"] == "ORGANIZATION"
        assert NER_TO_PRESIDIO_ENTITY["LOC"] == "LOCATION"
        assert NER_TO_PRESIDIO_ENTITY["GPE"] == "LOCATION"

    @patch("sandiraksa.detection.ner.recognizer.is_ner_available")
    def test_is_available_checks_model(self, mock_is_available):
        """Test is_available delegates to loader."""
        mock_is_available.return_value = True
        recognizer = IndonesianNERRecognizer(lazy_load=True)
        assert recognizer.is_available() is True
        mock_is_available.assert_called()

    @patch("sandiraksa.detection.ner.recognizer.is_ner_available")
    def test_analyze_no_model(self, mock_is_available):
        """Test analyze returns empty when model unavailable."""
        mock_is_available.return_value = False
        recognizer = IndonesianNERRecognizer(lazy_load=True)

        results = recognizer.analyze("Budi tinggal di Jakarta", ["PERSON", "LOCATION"])
        assert results == []


class TestMockIndonesianNERRecognizer:
    """Tests for MockIndonesianNERRecognizer."""

    def test_always_available(self):
        """Test mock is always available."""
        recognizer = MockIndonesianNERRecognizer()
        assert recognizer.is_available() is True

    def test_add_and_retrieve_detection(self):
        """Test adding and retrieving mock detections."""
        recognizer = MockIndonesianNERRecognizer()
        text = "Budi tinggal di Jakarta"

        recognizer.add_detection(text, "PERSON", "Budi", 0, 4, 0.9)
        recognizer.add_detection(text, "LOCATION", "Jakarta", 16, 23, 0.95)

        results = recognizer.analyze(text, ["PERSON", "LOCATION"])
        assert len(results) == 2

    def test_filter_by_entity(self):
        """Test detection filtering by entity type."""
        recognizer = MockIndonesianNERRecognizer()
        text = "Budi di Jakarta"

        recognizer.add_detection(text, "PERSON", "Budi", 0, 4, 0.9)
        recognizer.add_detection(text, "LOCATION", "Jakarta", 8, 15, 0.95)

        # Only request PERSON
        results = recognizer.analyze(text, ["PERSON"])
        assert len(results) == 1
        assert results[0].entity_type == "PERSON"
