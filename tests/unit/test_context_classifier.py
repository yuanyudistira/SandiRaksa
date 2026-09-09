"""Tests for the context-based segment classifier (table/spatial labels)."""

import pytest

from sandiraksa.detection.recognizers.context_classifier import (
    classify_label,
    classify_segment_by_context,
    get_segment_label,
)


class _FakeSegment:
    """Minimal stand-in for a LogicalSegment."""

    def __init__(self, text="", key_label=None, table_headers=None,
                 column_index=None, nearby_labels=None):
        self.text = text
        self.key_label = key_label
        self.table_headers = table_headers or []
        self.column_index = column_index
        self.nearby_labels = nearby_labels or []


class TestClassifyLabel:
    @pytest.mark.parametrize("label,expected", [
        ("Nama", "PERSON"),
        ("Nama Mock", "PERSON"),
        ("Nama Pasien", "PERSON"),
        ("Tanggal Lahir", "DATE_OF_BIRTH"),
        ("TTL", "DATE_OF_BIRTH"),
        ("NIK", "ID_NIK"),
        ("NPWP", "ID_NPWP"),
        ("Email", "EMAIL_ADDRESS"),
        ("Alamat", "LOCATION"),
    ])
    def test_maps_known_labels(self, label, expected):
        assert classify_label(label) == expected

    @pytest.mark.parametrize("label", [
        "Jenis Kelamin", "Penjamin", "Diagnosis", "EMR ID", "SpO2",
    ])
    def test_non_sensitive_labels_return_none(self, label):
        assert classify_label(label) is None


class TestGetSegmentLabel:
    def test_key_label_priority(self):
        seg = _FakeSegment(key_label="Nama", table_headers=["X"], column_index=0)
        assert get_segment_label(seg) == "Nama"

    def test_table_header_by_column_index(self):
        seg = _FakeSegment(
            table_headers=["EMR ID", "Nama Mock", "Tanggal Lahir"],
            column_index=1,
        )
        assert get_segment_label(seg) == "Nama Mock"

    def test_pptx_nearby_labels(self):
        seg = _FakeSegment(nearby_labels=["EMR-MOCK-0001002", "NAMA"])
        assert get_segment_label(seg) == "NAMA"


class TestClassifySegmentByContext:
    def test_table_name_cell(self):
        seg = _FakeSegment(
            text="Aisyah Pratama",
            table_headers=["EMR ID", "Nama Mock", "Tanggal Lahir"],
            column_index=1,
        )
        result = classify_segment_by_context(seg)
        assert result is not None
        assert result.entity_type == "PERSON"
        assert result.text == "Aisyah Pratama"

    def test_table_dob_cell(self):
        seg = _FakeSegment(
            text="14-Feb-1988",
            table_headers=["EMR ID", "Nama Mock", "Tanggal Lahir"],
            column_index=2,
        )
        result = classify_segment_by_context(seg)
        assert result is not None
        assert result.entity_type == "DATE_OF_BIRTH"

    def test_dob_column_with_non_date_value_rejected(self):
        # Value under "Tanggal Lahir" that isn't a date -> no detection
        seg = _FakeSegment(
            text="tidak diketahui",
            table_headers=["Tanggal Lahir"],
            column_index=0,
        )
        assert classify_segment_by_context(seg) is None

    def test_non_sensitive_column_ignored(self):
        seg = _FakeSegment(
            text="Perempuan",
            table_headers=["Jenis Kelamin"],
            column_index=0,
        )
        assert classify_segment_by_context(seg) is None

    def test_pptx_spatial_dob(self):
        seg = _FakeSegment(
            text="03-Nov-1976",
            nearby_labels=["MOCK-3273-19761103-1002", "TANGGAL LAHIR"],
        )
        result = classify_segment_by_context(seg)
        assert result is not None
        assert result.entity_type == "DATE_OF_BIRTH"
