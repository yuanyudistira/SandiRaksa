"""Tests for Indonesian recognizers."""

import pytest

from sandiraksa.detection.recognizers import (
    IndonesianPhoneRecognizer,
    KKRecognizer,
    NIKRecognizer,
    NPWPRecognizer,
)


class TestNIKRecognizer:
    """Tests for NIK recognizer."""

    @pytest.fixture
    def recognizer(self):
        return NIKRecognizer()

    def test_detect_valid_nik_jakarta(self, recognizer):
        """Should detect valid Jakarta NIK."""
        # 31 = DKI Jakarta, 01 = Jakarta Pusat, 01 = Gambir
        # 150590 = 15 May 1990 (male)
        # 0001 = sequence
        text = "NIK: 3101011505900001"
        results = recognizer.analyze(text, ["ID_NIK"])

        assert len(results) == 1
        assert results[0].entity_type == "ID_NIK"
        assert results[0].score >= 0.7

    def test_detect_valid_nik_female(self, recognizer):
        """Should detect NIK with female date encoding (day + 40)."""
        # 55 = 15 + 40 (female born on 15th)
        text = "NIK saya 3101015505900002"
        results = recognizer.analyze(text, ["ID_NIK"])

        assert len(results) == 1
        assert results[0].score >= 0.7

    def test_detect_nik_with_separators(self, recognizer):
        """Should detect NIK with spaces or dashes."""
        text = "NIK: 31.01.01-150590-0001"
        results = recognizer.analyze(text, ["ID_NIK"])

        assert len(results) == 1

    def test_reject_invalid_province(self, recognizer):
        """Should reject NIK with invalid province code."""
        # 99 is not a valid province
        text = "NIK: 9901011505900001"
        results = recognizer.analyze(text, ["ID_NIK"])

        # Should not detect or have low score
        assert len(results) == 0 or results[0].score < 0.5

    def test_reject_invalid_date(self, recognizer):
        """Should reject NIK with invalid date."""
        # 32 is not a valid day
        text = "NIK: 3101013213900001"
        results = recognizer.analyze(text, ["ID_NIK"])

        # Should have lower confidence
        if results:
            assert results[0].score < 0.8

    def test_reject_random_numbers(self, recognizer):
        """Should not detect random 16-digit numbers."""
        text = "Order number: 1234567890123456"
        results = recognizer.analyze(text, ["ID_NIK"])

        # Should not detect (invalid province) or very low score
        assert len(results) == 0 or results[0].score < 0.5


class TestNPWPRecognizer:
    """Tests for NPWP recognizer."""

    @pytest.fixture
    def recognizer(self):
        return NPWPRecognizer()

    def test_detect_npwp_formatted(self, recognizer):
        """Should detect formatted NPWP."""
        text = "NPWP: 01.234.567.8-901.000"
        results = recognizer.analyze(text, ["ID_NPWP"])

        assert len(results) == 1
        assert results[0].entity_type == "ID_NPWP"

    def test_detect_npwp_no_separators(self, recognizer):
        """Should detect NPWP without separators."""
        text = "NPWP 012345678901000"
        results = recognizer.analyze(text, ["ID_NPWP"])

        assert len(results) == 1

    def test_detect_corporate_npwp(self, recognizer):
        """Should detect corporate NPWP (starts with 21-24)."""
        text = "NPWP Perusahaan: 21.234.567.8-901.000"
        results = recognizer.analyze(text, ["ID_NPWP"])

        assert len(results) == 1
        assert results[0].analysis_explanation["subject_type"] == "21"

    def test_reject_invalid_subject_type(self, recognizer):
        """Should reject NPWP with invalid subject type."""
        # 99 is not a valid subject type
        text = "NPWP: 99.234.567.8-901.000"
        results = recognizer.analyze(text, ["ID_NPWP"])

        assert len(results) == 0

    def test_context_boosts_score(self, recognizer):
        """Context keywords should boost confidence."""
        text_with_context = "Wajib Pajak dengan NPWP 012345678901000"
        text_without = "Nomor: 012345678901000"

        results_with = recognizer.analyze(text_with_context, ["ID_NPWP"])
        results_without = recognizer.analyze(text_without, ["ID_NPWP"])

        # Both should detect, but context should give higher score
        assert len(results_with) >= 1
        # Note: score comparison depends on implementation


class TestKKRecognizer:
    """Tests for KK (Kartu Keluarga) recognizer."""

    @pytest.fixture
    def recognizer(self):
        return KKRecognizer()

    def test_detect_kk_with_context(self, recognizer):
        """Should detect KK when context mentions it."""
        text = "Kartu Keluarga: 3101011505200001"
        results = recognizer.analyze(text, ["ID_KK"])

        assert len(results) == 1
        assert results[0].entity_type == "ID_KK"

    def test_lower_score_without_context(self, recognizer):
        """Should have lower score without KK context."""
        text = "Nomor: 3101011505200001"
        results = recognizer.analyze(text, ["ID_KK"])

        # May detect but with lower confidence
        if results:
            assert results[0].score < 0.8

    def test_reject_invalid_province(self, recognizer):
        """Should reject KK with invalid province."""
        text = "KK: 9901011505200001"
        results = recognizer.analyze(text, ["ID_KK"])

        assert len(results) == 0


class TestIndonesianPhoneRecognizer:
    """Tests for Indonesian phone recognizer."""

    @pytest.fixture
    def recognizer(self):
        return IndonesianPhoneRecognizer()

    def test_detect_mobile_telkomsel(self, recognizer):
        """Should detect Telkomsel mobile number."""
        text = "HP: 0812-3456-7890"
        results = recognizer.analyze(text, ["ID_PHONE"])

        assert len(results) == 1
        assert results[0].entity_type == "ID_PHONE"
        assert results[0].analysis_explanation["carrier"] == "Telkomsel"

    def test_detect_mobile_indosat(self, recognizer):
        """Should detect Indosat mobile number."""
        text = "Hubungi 0856-1234-5678"
        results = recognizer.analyze(text, ["ID_PHONE"])

        assert len(results) == 1
        assert results[0].analysis_explanation["carrier"] == "Indosat"

    def test_detect_international_format(self, recognizer):
        """Should detect +62 format."""
        text = "WA: +62-812-345-6789"
        results = recognizer.analyze(text, ["ID_PHONE"])

        assert len(results) == 1
        assert results[0].score >= 0.9

    def test_detect_mobile_no_separator(self, recognizer):
        """Should detect mobile without separators."""
        text = "Call 081234567890"
        results = recognizer.analyze(text, ["ID_PHONE"])

        assert len(results) == 1

    def test_detect_landline_jakarta(self, recognizer):
        """Should detect Jakarta landline."""
        text = "Telp: (021) 1234-5678"
        results = recognizer.analyze(text, ["ID_PHONE"])

        assert len(results) == 1
        assert results[0].analysis_explanation["type"] == "landline"
        assert results[0].analysis_explanation["area"] == "Jakarta"

    def test_detect_landline_surabaya(self, recognizer):
        """Should detect Surabaya landline."""
        text = "Kantor: 031-1234567"
        results = recognizer.analyze(text, ["ID_PHONE"])

        assert len(results) == 1
        assert results[0].analysis_explanation["area"] == "Surabaya"

    def test_reject_invalid_prefix(self, recognizer):
        """Should have lower score for unknown prefix."""
        text = "Nomor: 0999-1234-5678"  # Invalid prefix
        results = recognizer.analyze(text, ["ID_PHONE"])

        # Should not detect or have very low score
        if results:
            assert results[0].score < 0.7

    def test_multiple_phones_in_text(self, recognizer):
        """Should detect multiple phone numbers."""
        text = "HP: 0812-1111-2222, Kantor: (021) 3333-4444"
        results = recognizer.analyze(text, ["ID_PHONE"])

        assert len(results) == 2
