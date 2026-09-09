"""Tests for the context-aware DateOfBirthRecognizer."""

from datetime import date

import pytest

from sandiraksa.detection.recognizers.id_dob import DateOfBirthRecognizer


@pytest.fixture
def recognizer():
    # Fix "today" to 9-Sep-2026 for deterministic appointment-exclusion tests
    return DateOfBirthRecognizer(today=date(2026, 9, 9))


class TestBirthDateWithLabel:
    def test_detects_dob_with_label(self, recognizer):
        text = "Tanggal Lahir: 14-Feb-1988"
        results = recognizer.analyze(text, ["DATE_OF_BIRTH"])
        assert len(results) == 1
        assert results[0].text == "14-Feb-1988"
        assert results[0].score >= 0.9  # label precedes -> high confidence

    def test_detects_dob_lahir_label(self, recognizer):
        text = "Lahir: 03-Nov-1976"
        results = recognizer.analyze(text, ["DATE_OF_BIRTH"])
        assert len(results) == 1
        assert results[0].text == "03-Nov-1976"

    def test_detects_dob_ttl_label(self, recognizer):
        text = "TTL : 28-Jul-1995"
        results = recognizer.analyze(text, ["DATE_OF_BIRTH"])
        assert len(results) == 1


class TestBirthDateWithNameContext:
    def test_detects_dob_near_name(self, recognizer):
        # Person name present -> date may be a DOB (medium confidence)
        text = "Budi Santoso 17-Sep-1983 pasien lama"
        results = recognizer.analyze(text, ["DATE_OF_BIRTH"])
        assert len(results) == 1
        assert results[0].text == "17-Sep-1983"


class TestNonBirthDates:
    def test_ignores_date_without_context(self, recognizer):
        # No label, no name -> not a DOB
        text = "Rapat pada 15-Jan-2020 di kantor pusat wilayah"
        results = recognizer.analyze(text, ["DATE_OF_BIRTH"])
        assert results == []

    def test_excludes_current_month_appointment(self, recognizer):
        # Appointment this month (Sep 2026), only name context, no DOB label
        text = "Budi Santoso Kunjungan 02-Sep-2026 kontrol rutin"
        results = recognizer.analyze(text, ["DATE_OF_BIRTH"])
        dates = [r.text for r in results]
        assert "02-Sep-2026" not in dates

    def test_excludes_recent_visit_date(self, recognizer):
        # Recent date (within 2 years) with only name context -> excluded
        text = "Budi Santoso periksa 10-Mar-2025 poli umum"
        results = recognizer.analyze(text, ["DATE_OF_BIRTH"])
        assert "10-Mar-2025" not in [r.text for r in results]

    def test_excludes_future_date(self, recognizer):
        text = "Tanggal Lahir: 01-Jan-2030"
        results = recognizer.analyze(text, ["DATE_OF_BIRTH"])
        assert results == []

    def test_excludes_implausible_old_year(self, recognizer):
        text = "Lahir: 01-Jan-1900"
        results = recognizer.analyze(text, ["DATE_OF_BIRTH"])
        assert results == []


class TestLabelDoesNotLeakAcrossLines:
    def test_label_on_previous_line_does_not_apply(self, recognizer):
        # "Tanggal Lahir" on line 1, an appointment date on line 2 with its
        # own "Tanggal:" label -> the appointment date must NOT become a DOB.
        text = "Tanggal Lahir: 14-Feb-1988\nTanggal: 02-Sep-2026"
        results = recognizer.analyze(text, ["DATE_OF_BIRTH"])
        dates = [r.text for r in results]
        assert "14-Feb-1988" in dates
        assert "02-Sep-2026" not in dates


class TestEntityFilter:
    def test_returns_empty_when_not_requested(self, recognizer):
        text = "Tanggal Lahir: 14-Feb-1988"
        results = recognizer.analyze(text, ["PERSON"])
        assert results == []
