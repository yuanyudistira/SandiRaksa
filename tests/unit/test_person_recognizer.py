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


# =============================================================================
# Hybrid name detection: JSON key-aware + free-text cue (no colon)
# =============================================================================

def _names(recognizer, text):
    return [r.text for r in recognizer.analyze(text, ["PERSON"])]


@pytest.fixture(autouse=True)
def _empty_deny_list(monkeypatch):
    """Neutralize any on-disk deny-list so name tests are deterministic."""
    import sandiraksa.detection.deny_list as dl
    monkeypatch.setattr(dl, "_cached_terms", frozenset())


class TestJsonKeyNames:
    def test_json_name_key(self, recognizer):
        text = '{"emp_id": "EMP-001", "name": "Budi Sanjaya", "salary": 100}'
        assert "Budi Sanjaya" in _names(recognizer, text)

    def test_json_doctor_key_with_title(self, recognizer):
        text = '{"doctor": "dr. Andi Kurniawan", "room": "Melati 5"}'
        names = _names(recognizer, text)
        # Title may or may not be included; the core name must be present.
        assert any("Andi Kurniawan" in n for n in names)

    def test_json_lowercase_value_not_captured(self, recognizer):
        # Value that is not a capitalized name must not be captured.
        text = '{"name": "invalid_password"}'
        assert _names(recognizer, text) == []

    def test_json_key_not_name_ignored(self, recognizer):
        text = '{"status": "failed", "reason": "invalid_password"}'
        assert _names(recognizer, text) == []


class TestFreeTextCueNames:
    def test_pasien_cue(self, recognizer):
        assert "Budi Santoso" in _names(recognizer, "Pasien Budi Santoso mengeluh pusing.")

    def test_cek_lab_cue(self, recognizer):
        assert "Siti Aminah" in _names(recognizer, "Cek lab Siti Aminah hasil normal.")

    def test_cue_does_not_capture_lowercase(self, recognizer):
        # "kontak darurat istri" -> "istri" is lowercase, must NOT be captured.
        assert _names(recognizer, "kontak darurat istri.") == []


class TestStrongTermRejection:
    def test_medical_clause_rejected(self):
        # NLP-style over-capture with clinical terms must be rejected.
        assert is_false_positive_person("Demam Berdarah") is True
        assert is_false_positive_person("Rina M alergi penisilin") is True
        assert is_false_positive_person("Jangan berikan amoxicillin") is True

    def test_clean_name_still_accepted(self):
        assert is_false_positive_person("Budi Santoso") is False
        assert is_false_positive_person("Andi Kurniawan") is False
