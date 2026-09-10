"""
Regression tests for the legacy NPWPRecognizer (Track A / A1).

Covers the DJP PER-06/PJ/2024 changes (effective 1 July 2024):
- 15-digit legacy format still recognized.
- 16-digit mandatory format scored high WITH tax context.
- "0" + 15-digit migrated numbers recognized with high confidence.
- Space/dot/dash separators supported.
- Invalid subject-type codes rejected (false-positive guard).
- Check digit is a bonus signal, never a hard reject.
"""

import pytest

from sandiraksa.detection.recognizers.id_npwp import NPWPRecognizer, format_npwp


@pytest.fixture
def recognizer():
    return NPWPRecognizer()


def _find(recognizer, text):
    return recognizer.analyze(text, ["ID_NPWP"])


class TestLegacy15Digit:
    def test_formatted_with_context(self, recognizer):
        results = _find(recognizer, "NPWP: 09.254.294.3-407.000")
        assert len(results) == 1
        assert results[0].entity_type == "ID_NPWP"
        assert results[0].score >= 0.75

    def test_space_separators(self, recognizer):
        # OCR-style spacing between groups (subject type 21 is valid corporate).
        results = _find(recognizer, "NPWP 21 315 628 1 424 000")
        assert len(results) == 1
        assert results[0].score >= 0.75

    def test_invalid_subject_type_rejected(self, recognizer):
        # Subject type "99" is not valid -> must NOT be detected.
        results = _find(recognizer, "NPWP: 99.999.999.9-999.999")
        assert results == []


class TestMigrated0Plus15:
    def test_migrated_number_with_context(self, recognizer):
        # "0" + valid 15-digit legacy body.
        results = _find(recognizer, "NPWP: 0092542943407000")
        assert len(results) == 1
        assert results[0].score >= 0.85


class Test16Digit:
    def test_16digit_with_context_high_score(self, recognizer):
        results = _find(recognizer, "NPWP: 1234567890123456")
        assert len(results) == 1
        assert results[0].score >= 0.85

    def test_16digit_without_context_low_score(self, recognizer):
        # No tax context -> ambiguous vs NIK -> deliberately low score.
        results = _find(recognizer, "Nomor referensi 1234567890123456 pada arsip")
        assert len(results) == 1
        assert results[0].score <= 0.5


class TestEntityGating:
    def test_returns_empty_when_not_requested(self, recognizer):
        assert recognizer.analyze("NPWP: 09.254.294.3-407.000", ["ID_NIK"]) == []


class TestFormatHelper:
    def test_format_15digit(self):
        assert format_npwp("092542943407000") == "09.254.294.3-407.000"
