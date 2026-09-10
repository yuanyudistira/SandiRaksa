"""Tests for Excel/CSV column type suggestion (header + content based)."""

import pytest

from sandiraksa.ui.dialogs.column_selection import (
    analyze_column_header,
    analyze_column_content,
    suggest_column_type,
)


class TestHeaderBased:
    @pytest.mark.parametrize("header,expected", [
        ("Nama Pasien", "PERSON"),
        ("Email", "EMAIL_ADDRESS"),
        ("NIK", "ID_NIK"),
        ("Tanggal Lahir", "DATE_OF_BIRTH"),
        ("Alamat", "ADDRESS"),
    ])
    def test_known_headers(self, header, expected):
        assert analyze_column_header(header) == expected

    def test_patient_id_not_person(self):
        # "Patient ID" is an identifier column, not a person name
        assert analyze_column_header("Patient ID") is None
        assert analyze_column_header("ID Pasien") is None

    def test_status_columns_not_sensitive(self):
        assert analyze_column_header("Status Pasien") is None
        assert analyze_column_header("Status Pernikahan") is None
        assert analyze_column_header("Jenis Kelamin") is None
        assert analyze_column_header("Kategori BMI") is None

    def test_unknown_header_returns_none(self):
        assert analyze_column_header("Kolom1") is None
        assert analyze_column_header("XYZ") is None


class TestContentBased:
    def test_detects_email_content(self):
        samples = ["budi@test.com", "siti@mail.co.id", "andi@corp.com"]
        assert analyze_column_content(samples) == "EMAIL_ADDRESS"

    def test_detects_nik_content(self):
        samples = ["3201011234567890", "3175064512340001", "3273052309870002"]
        assert analyze_column_content(samples) == "ID_NIK"

    def test_detects_phone_content(self):
        samples = ["081234567890", "+62 813-5522-1002", "0857-1234-5678"]
        assert analyze_column_content(samples) == "ID_PHONE"

    def test_detects_generic_date_content(self):
        samples = ["14-Feb-1988", "03-Nov-1976", "28-Jul-1995"]
        # Content alone -> generic DATE (not DATE_OF_BIRTH without header)
        assert analyze_column_content(samples) == "DATE"

    def test_non_sensitive_content_returns_none(self):
        samples = ["nilai biasa", "teks umum", "bukan pii"]
        assert analyze_column_content(samples) is None

    def test_empty_samples_return_none(self):
        assert analyze_column_content([]) is None
        assert analyze_column_content(["", "  ", ""]) is None

    def test_requires_majority(self):
        # Only 1 of 5 is an email -> below 60% threshold -> None
        samples = ["a@b.com", "x", "y", "z", "w"]
        assert analyze_column_content(samples) is None


class TestSuggestColumnType:
    def test_header_takes_priority(self):
        # Known header wins even with unrelated samples
        assert suggest_column_type("Email", ["not-an-email"]) == "EMAIL_ADDRESS"

    def test_falls_back_to_content(self):
        # Ambiguous header, but content reveals emails
        assert suggest_column_type("Kolom1", ["a@b.com", "c@d.com"]) == "EMAIL_ADDRESS"

    def test_returns_none_when_nothing_detected(self):
        assert suggest_column_type("XYZ", ["foo", "bar", "baz"]) is None


class TestCustomPatternInColumn:
    def test_custom_pattern_detected_in_content(self, tmp_path, monkeypatch):
        # Register a global custom pattern, then verify column content uses it
        from sandiraksa.detection import custom_patterns as cp

        store = cp.CustomPatternStore(config_path=tmp_path / "custom.json")
        store.save(cp.parse_patterns_text("MEDICAL_RECORD: MR-\\d{6}"))

        # Point the cached global patterns at our temp store
        monkeypatch.setattr(cp, "_cached_patterns", store.load())

        samples = ["MR-004521", "MR-119283", "MR-556677"]
        assert analyze_column_content(samples) == "MEDICAL_RECORD"


# =============================================================================
# Narrative / free-text / JSON column detection + protection mode (A4)
# =============================================================================

from sandiraksa.ui.dialogs.column_selection import (  # noqa: E402
    ProtectionMode,
    NARRATIVE_TYPE,
    is_narrative_column,
    default_protection_mode,
)


class TestNarrativeColumnDetection:
    def test_free_text_is_narrative(self):
        samples = [
            "Pasien Budi S (NIK: 3171234567890001) mengeluh pusing. Resep BPJS 0001234567890.",
            "Cek lab Siti Aminah (0815123456789) menunjukkan gula darah 250 mg/dl.",
            "Andi P perlu endoskopi. Penjamin: Asuransi Mandiri Inhealth.",
        ]
        assert is_narrative_column(samples) is True

    def test_json_column_is_narrative(self):
        samples = [
            '{"patient_id": "MR-2026-888", "doctor": "dr. Andi Kurniawan", "room": "Melati 5"}',
            '{"emp_id": "EMP-001", "name": "Budi Sanjaya", "bank_acc": "BCA-1234567890"}',
        ]
        assert is_narrative_column(samples) is True

    def test_single_value_column_not_narrative(self):
        assert is_narrative_column(["Budi Santoso", "Siti Aminah", "Andi Permana"]) is False

    def test_short_codes_not_narrative(self):
        assert is_narrative_column(["A+", "O-", "B+", "AB+"]) is False

    def test_empty_samples_not_narrative(self):
        assert is_narrative_column([]) is False
        assert is_narrative_column(["", "  "]) is False


class TestSuggestNarrativeType:
    def test_narrative_header_content_returns_narrative_type(self):
        samples = [
            "Pasien Budi mengeluh nyeri dada sejak dua hari, tekanan darah tinggi.",
            "Kontrol rutin diabetes, gula darah stabil, lanjut terapi metformin.",
        ]
        assert suggest_column_type("Catatan_Dokter", samples) == NARRATIVE_TYPE


class TestDefaultProtectionMode:
    def test_narrative_defaults_to_pii_only(self):
        samples = [
            "Pasien Budi mengeluh nyeri dada sejak dua hari, tekanan darah tinggi.",
            "Kontrol rutin diabetes, gula darah stabil, lanjut terapi metformin.",
        ]
        assert default_protection_mode(NARRATIVE_TYPE, samples) == ProtectionMode.PII_ONLY.value

    def test_single_value_defaults_to_full_cell(self):
        samples = ["Budi Santoso", "Siti Aminah"]
        assert default_protection_mode("PERSON", samples) == ProtectionMode.FULL_CELL.value
