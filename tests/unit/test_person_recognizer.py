"""Tests for IndonesianPersonRecognizer and person false-positive filter."""

import pytest

from sandiraksa.detection.recognizers.id_person import IndonesianPersonRecognizer
from sandiraksa.detection.recognizers.person_filter import (
    is_false_positive_person,
    filter_person_detections,
)
from sandiraksa.detection.context import DetectionResult


@pytest.fixture
def recognizer():
    return IndonesianPersonRecognizer()


class TestLabeledNames:
    def test_detects_name_after_nama_label(self, recognizer):
        results = recognizer.analyze("Nama: Budi Santoso", ["PERSON"])
        assert len(results) == 1
        assert results[0].text == "Budi Santoso"

    def test_detects_name_after_nama_mock_label(self, recognizer):
        results = recognizer.analyze("Nama Mock: Aisyah Pratama", ["PERSON"])
        assert len(results) == 1
        assert results[0].text == "Aisyah Pratama"

    def test_name_does_not_cross_newline(self, recognizer):
        text = "Nama Mock: Aisyah Pratama\nJenis Kelamin: Perempuan"
        results = recognizer.analyze(text, ["PERSON"])
        names = [r.text for r in results]
        assert "Aisyah Pratama" in names
        # Must NOT capture across the line break
        assert all("\n" not in n for n in names)


class TestEmrPatternNames:
    def test_detects_name_in_emr_row(self, recognizer):
        text = "[EMR-MOCK-0001006] Fajar Nugraha | Laki-laki | Lahir: 17-Sep-1983"
        results = recognizer.analyze(text, ["PERSON"])
        names = [r.text for r in results]
        assert "Fajar Nugraha" in names


class TestFalsePositiveFilter:
    @pytest.mark.parametrize("word", [
        "Perempuan", "Laki-laki", "Penjamin", "Kunjungan", "Keluhan",
        "Terapi", "Diagnosis", "Demam", "Tanda", "NIK Mock",
    ])
    def test_common_terms_rejected(self, word):
        assert is_false_positive_person(word) is True

    @pytest.mark.parametrize("name", [
        "Budi Santoso", "Aisyah Pratama", "Fajar Nugraha", "Siti Aminah",
    ])
    def test_real_names_kept(self, name):
        assert is_false_positive_person(name) is False

    def test_multiline_rejected(self):
        assert is_false_positive_person("Asuransi Perusahaan\nKunjungan") is True

    def test_place_tokens_rejected(self):
        assert is_false_positive_person("Cemara No.") is True
        assert is_false_positive_person("Medan Baru") is True

    def test_long_phrase_rejected(self):
        assert is_false_positive_person("Ruam kulit dan gatal") is True


class TestAddressLabelContext:
    def test_person_after_address_label_rejected(self):
        # NLP-detected PERSON right after "Alamat Mock:" should be dropped
        full_text = "Alamat Mock: Kebon Jeruk"
        det = DetectionResult(
            entity_type="PERSON", start=13, end=24, text="Kebon Jeruk",
            score=0.85, recognizer_name="presidio",
        )
        filtered = filter_person_detections([det], full_text)
        assert filtered == []

    def test_context_recognizer_person_kept_after_address(self):
        # Context recognizer (id_person) results are trusted even near labels
        full_text = "Alamat Mock: Kebon Jeruk"
        det = DetectionResult(
            entity_type="PERSON", start=13, end=24, text="Kebon Jeruk",
            score=0.85, recognizer_name="id_person",
        )
        filtered = filter_person_detections([det], full_text)
        assert len(filtered) == 1
