"""
Regression tests for the legacy IndonesianPhoneRecognizer landline tightening
(Track A / A5).

The "standard" landline pattern now REQUIRES an explicit separator between the
area code and subscriber part, so arbitrary long digit runs are no longer
grabbed as landlines. Separated/parenthesized landlines and mobiles are
unaffected.
"""

import pytest

from sandiraksa.detection.recognizers.id_phone import IndonesianPhoneRecognizer


@pytest.fixture
def recognizer():
    return IndonesianPhoneRecognizer()


def _texts(recognizer, text):
    return [r.text for r in recognizer.analyze(text, ["ID_PHONE"])]


class TestLandlineStillDetected:
    def test_dash_separated(self, recognizer):
        assert "021-7654321" in _texts(recognizer, "Telp: 021-7654321")

    def test_space_separated(self, recognizer):
        assert _texts(recognizer, "Telp 021 765 4321")

    def test_parenthesized(self, recognizer):
        assert _texts(recognizer, "(021) 7654321")


class TestMobileUnaffected:
    def test_mobile_local(self, recognizer):
        assert "081234567890" in _texts(recognizer, "HP: 081234567890")

    def test_mobile_international(self, recognizer):
        assert _texts(recognizer, "WA +62 812 3456 7890")


class TestArbitraryRunsNotGrabbed:
    def test_bare_digit_run_not_landline(self, recognizer):
        # No separator -> must NOT be detected as a landline.
        assert _texts(recognizer, "ID transaksi 021123456789") == []

    def test_long_bare_run_not_matched(self, recognizer):
        assert _texts(recognizer, "Kode 0891234567890123") == []


class TestEntityGating:
    def test_returns_empty_when_not_requested(self, recognizer):
        assert recognizer.analyze("Telp: 021-7654321", ["ID_NIK"]) == []
