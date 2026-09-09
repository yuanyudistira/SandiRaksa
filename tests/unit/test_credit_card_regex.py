"""
Regression tests for the CREDIT_CARD false-positive bug.

Bug: NIK-style IDs like "MOCK-3174-19880214-1001" were misdetected as credit
cards because the old regex allowed an optional/inconsistent separator, so a
run of 16 digits with mixed dashes matched.

Fix: require a CONSISTENT separator (all spaces, all dashes, or none) across
the four 4-digit groups.
"""

import pytest

from sandiraksa.protection.txt_protector import TxtProtector
from sandiraksa.protection.docx_protector import DocxProtector
from sandiraksa.protection.pptx_protector import PptxProtector
from sandiraksa.detection.presidio_engine import RegexRecognizer


NIK_STYLE = "MOCK-3174-19880214-1001"
REAL_CARDS = [
    "4111 1111 1111 1111",
    "4111-1111-1111-1111",
    "4111111111111111",
]


def _detect_types(protector, text, is_txt=False):
    if is_txt:
        ents = protector.detect_entities(text)
    else:
        ents = protector._detect_in_text(text, "loc")
    return {e.entity_type for e in ents}


class TestCreditCardFalsePositive:
    def test_txt_nik_style_not_credit_card(self):
        types = _detect_types(TxtProtector("test"), NIK_STYLE, is_txt=True)
        assert "CREDIT_CARD" not in types

    def test_docx_nik_style_not_credit_card(self):
        types = _detect_types(DocxProtector("test"), NIK_STYLE)
        assert "CREDIT_CARD" not in types

    def test_pptx_nik_style_not_credit_card(self):
        types = _detect_types(PptxProtector("test"), NIK_STYLE)
        assert "CREDIT_CARD" not in types

    def test_excel_csv_engine_nik_style_not_credit_card(self):
        # Excel/CSV column scanning uses RegexRecognizer via the detection engine
        r = RegexRecognizer()
        results = r.analyze(NIK_STYLE, ["CREDIT_CARD", "ID_NIK"])
        assert not any(x.entity_type == "CREDIT_CARD" for x in results)


class TestExcelCsvRealCard:
    @pytest.mark.parametrize("card", ["4111 1111 1111 1111", "4111-1111-1111-1111"])
    def test_regex_recognizer_detects_separated_card(self, card):
        r = RegexRecognizer()
        results = r.analyze(card, ["CREDIT_CARD"])
        assert any(x.entity_type == "CREDIT_CARD" for x in results)


# Cards with an explicit separator are unambiguously credit cards.
SEPARATED_CARDS = ["4111 1111 1111 1111", "4111-1111-1111-1111"]

# A protected type that means "this value is still protected" for a 16-digit
# run (which is ambiguous between NIK and credit card without a separator).
PROTECTED_16_DIGIT_TYPES = {"CREDIT_CARD", "ID_NIK", "ID_KK"}


class TestRealCreditCardStillDetected:
    @pytest.mark.parametrize("card", SEPARATED_CARDS)
    def test_txt_detects_separated_card(self, card):
        types = _detect_types(TxtProtector("test"), card, is_txt=True)
        assert "CREDIT_CARD" in types

    @pytest.mark.parametrize("card", SEPARATED_CARDS)
    def test_docx_detects_separated_card(self, card):
        types = _detect_types(DocxProtector("test"), card)
        assert "CREDIT_CARD" in types

    @pytest.mark.parametrize("card", SEPARATED_CARDS)
    def test_pptx_detects_separated_card(self, card):
        types = _detect_types(PptxProtector("test"), card)
        assert "CREDIT_CARD" in types

    def test_txt_16_digit_run_is_protected(self):
        # 16 consecutive digits is ambiguous (NIK vs card); either way it must
        # be detected/protected, not ignored.
        types = _detect_types(TxtProtector("test"), "4111111111111111", is_txt=True)
        assert types & PROTECTED_16_DIGIT_TYPES
