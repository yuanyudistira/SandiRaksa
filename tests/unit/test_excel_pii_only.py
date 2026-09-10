"""
Tests for per-substring ("PII-only") Excel cell protection (Track A / A4).

Verifies that in PII_ONLY mode only the detected PII substrings inside a cell
are tokenized, while surrounding free text / structure is preserved, and cells
with no PII are left untouched.
"""

import pytest

from sandiraksa.protection.excel_protector import ExcelProtector


class _StubTokenizer:
    """Deterministic tokenizer that returns a readable placeholder per type."""

    def __init__(self):
        self._count = 0

    def get_or_create_token(self, entity_type: str, value: str) -> str:
        self._count += 1
        return f"[{entity_type}]"

    def get_mapping_count(self) -> int:
        return self._count


@pytest.fixture(autouse=True)
def _empty_deny_list(monkeypatch):
    """Neutralize any on-disk deny-list so tests are deterministic."""
    import sandiraksa.detection.deny_list as dl
    monkeypatch.setattr(dl, "_cached_terms", frozenset())


@pytest.fixture
def protector():
    return ExcelProtector("proj-test", tokenizer=_StubTokenizer())


@pytest.fixture
def engine(protector):
    return protector._build_engine()


class TestTokenizePiiInText:
    def test_only_pii_replaced_surrounding_kept(self, protector, engine):
        text = "Pasien kontrol, No BPJS: 0001234567890, hasil normal."
        new, hits = protector._tokenize_pii_in_text(engine, text)
        assert hits >= 1
        assert "0001234567890" not in new
        assert new.startswith("Pasien kontrol,")
        assert new.endswith("hasil normal.")

    def test_phone_in_free_text(self, protector, engine):
        text = "Hubungi pasien di 081512345678 untuk konfirmasi."
        new, hits = protector._tokenize_pii_in_text(engine, text)
        assert hits >= 1
        assert "081512345678" not in new
        assert "untuk konfirmasi." in new

    def test_no_pii_cell_untouched(self, protector, engine):
        text = "Tidak ada data sensitif di sini sama sekali."
        new, hits = protector._tokenize_pii_in_text(engine, text)
        assert hits == 0
        assert new == text

    def test_multiple_pii_all_replaced(self, protector, engine):
        text = "No BPJS 0001234567890 dan telepon 081512345678."
        new, hits = protector._tokenize_pii_in_text(engine, text)
        assert hits >= 2
        assert "0001234567890" not in new
        assert "081512345678" not in new


class TestCustomPatternChaining:
    def test_custom_pattern_matched_in_cell(self, protector, engine, monkeypatch):
        import sandiraksa.detection.custom_patterns as cp
        from sandiraksa.detection.custom_patterns import CustomPattern

        # Inject a custom Medical Record pattern matching the real data format.
        monkeypatch.setattr(cp, "_cached_patterns", [
            CustomPattern(label="REKAM_MEDIS", pattern=r"MR-\d{4}-\d{3,}",
                          match_type="regex"),
        ])

        text = '{"patient_id": "MR-2026-888", "room": "Melati 5"}'
        new, hits = protector._tokenize_pii_in_text(engine, text)
        assert hits >= 1
        assert "MR-2026-888" not in new
        assert "[REKAM_MEDIS]" in new
        # Non-PII structure preserved.
        assert "Melati 5" in new


class TestHybridNameDetection:
    def test_json_name_protected(self, protector, engine):
        text = '{"emp_id": "EMP-001", "name": "Budi Sanjaya", "salary": 100}'
        new, hits = protector._tokenize_pii_in_text(engine, text)
        assert "Budi Sanjaya" not in new
        assert '"emp_id": "EMP-001"' in new  # structure preserved

    def test_json_doctor_name_protected(self, protector, engine):
        text = '{"doctor": "dr. Andi Kurniawan", "room": "Melati 5"}'
        new, hits = protector._tokenize_pii_in_text(engine, text)
        assert "Andi Kurniawan" not in new
        assert "Melati 5" in new

    def test_free_text_cue_name_protected(self, protector, engine):
        text = "Pasien Budi Santoso mengeluh pusing."
        new, hits = protector._tokenize_pii_in_text(engine, text)
        assert "Budi Santoso" not in new
        assert "mengeluh pusing." in new

    def test_medical_clause_not_oversensored(self, protector, engine):
        # Clinical clause must not be mistaken for a name.
        text = "Diagnosis: Demam Berdarah, alergi penisilin."
        new, hits = protector._tokenize_pii_in_text(engine, text)
        assert "Demam Berdarah" in new
        assert "alergi penisilin" in new
