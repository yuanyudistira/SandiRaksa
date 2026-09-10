"""
Regression tests for BPJSRecognizerLegacy (Track A / A2).

BPJS is a 13-digit number with no public checksum, so detection is gated on
nearby context keywords. These tests confirm:
- Detection with context (plain and grouped formats).
- No detection without context (avoids flagging arbitrary 13-digit numbers).
- Rejection of repdigit / sequential runs.
- Entity gating.
"""

import pytest

from sandiraksa.detection.recognizers.id_bpjs_legacy import (
    BPJSRecognizerLegacy,
    format_bpjs,
)


@pytest.fixture
def recognizer():
    return BPJSRecognizerLegacy()


def _find(recognizer, text):
    return recognizer.analyze(text, ["ID_BPJS"])


class TestWithContext:
    def test_plain_13digit_with_context(self, recognizer):
        results = _find(recognizer, "No BPJS: 0001234567890")
        assert len(results) == 1
        assert results[0].entity_type == "ID_BPJS"
        assert results[0].score >= 0.6

    def test_grouped_format_with_context(self, recognizer):
        results = _find(recognizer, "BPJS Kesehatan 0005 5566 67778")
        assert len(results) == 1
        assert results[0].score >= 0.6

    def test_starts_with_zero_boost(self, recognizer):
        results = _find(recognizer, "Kartu BPJS 0009876543210")
        assert len(results) == 1
        assert results[0].analysis_explanation["starts_with_zero"] is True


class TestWithoutContext:
    def test_no_context_not_detected(self, recognizer):
        # A bare 13-digit number without BPJS context must NOT be detected.
        results = _find(recognizer, "Kode transaksi 1234567890123 selesai")
        assert results == []


class TestInvalidPatterns:
    def test_repdigit_rejected(self, recognizer):
        results = _find(recognizer, "BPJS: 1111111111111")
        assert results == []

    def test_sequential_rejected(self, recognizer):
        results = _find(recognizer, "BPJS 0123456789012")
        assert results == []


class TestEntityGating:
    def test_returns_empty_when_not_requested(self, recognizer):
        assert recognizer.analyze("No BPJS: 0001234567890", ["ID_NIK"]) == []


class TestFormatHelper:
    def test_format_groups(self):
        assert format_bpjs("0001234567890") == "0001-2345-67890"
