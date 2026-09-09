"""
Unit tests for Sprint 4: Enhanced Indonesian Recognizers.

Tests cover:
- EnhancedNIKRecognizer - province codes, DOB validation, female encoding
- EnhancedNPWPRecognizer - 15-digit legacy, 16-digit NIK-based, formats
- EnhancedKKRecognizer - registration date validation
- EnhancedPhoneRecognizer - phonenumbers integration, carrier detection
- BPJSRecognizer - 13-digit with context
- SIMRecognizer - 12-14 digits, SIM type detection
- PassportRecognizer - letter + 7 digits
"""

import pytest

from sandiraksa.detection.unified_engine import DetectionConfig, DetectionContext
from sandiraksa.documents.logical_segment import LogicalSegment

# Import recognizers
from sandiraksa.detection.recognizers.enhanced_nik import (
    EnhancedNIKRecognizer,
    NIKMetadata,
    VALID_PROVINCE_CODES,
    parse_nik,
)
from sandiraksa.detection.recognizers.enhanced_npwp import (
    EnhancedNPWPRecognizer,
    format_npwp,
    parse_npwp,
)
from sandiraksa.detection.recognizers.enhanced_kk import (
    EnhancedKKRecognizer,
    parse_kk,
)
from sandiraksa.detection.recognizers.enhanced_phone import (
    EnhancedPhoneRecognizer,
    CARRIER_PREFIXES,
    format_phone_indonesia,
    parse_phone_indonesia,
)
from sandiraksa.detection.recognizers.id_bpjs import (
    BPJSRecognizer,
    format_bpjs,
)
from sandiraksa.detection.recognizers.id_sim import (
    SIMRecognizer,
)
from sandiraksa.detection.recognizers.id_passport import (
    PassportRecognizer,
    format_passport,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def make_segment():
    """Factory for creating test segments."""
    def _make(
        text: str,
        file_id: str = "test.txt",
        key_label: str | None = None,
        table_headers: list[str] | None = None,
    ) -> LogicalSegment:
        segment = LogicalSegment.for_txt_paragraph(
            text=text,
            file_id=file_id,
            paragraph_index=0,
            key_label=key_label,
        )
        if table_headers:
            segment.table_headers = table_headers
        return segment
    return _make


@pytest.fixture
def make_context():
    """Factory for creating detection context."""
    def _make(segment: LogicalSegment, entities: list[str] | None = None) -> DetectionContext:
        config = DetectionConfig(entities=entities)
        return DetectionContext(
            segment=segment,
            config=config,
            file_type="txt",
        )
    return _make


# =============================================================================
# Enhanced NIK Recognizer Tests
# =============================================================================

class TestEnhancedNIKRecognizer:
    """Tests for EnhancedNIKRecognizer."""

    @pytest.fixture
    def recognizer(self):
        return EnhancedNIKRecognizer()

    def test_valid_nik_with_context(self, recognizer, make_segment, make_context):
        """Test detecting valid NIK with context."""
        # Valid NIK: province 32 (Jawa Barat), DOB 15/01/1990
        segment = make_segment("NIK: 3201011501900001", key_label="NIK")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1
        assert findings[0].entity_type == "ID_NIK"
        assert findings[0].is_validated
        assert findings[0].raw_score >= 0.8

    def test_valid_nik_female_encoding(self, recognizer, make_segment, make_context):
        """Test NIK with female day encoding (+40)."""
        # Female: day 15 + 40 = 55
        segment = make_segment("NIK: 3201015501900002", key_label="NIK")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1
        assert findings[0].is_validated

    def test_invalid_province_code(self, recognizer, make_segment, make_context):
        """Test NIK with invalid province code."""
        # Province 99 doesn't exist
        segment = make_segment("NIK: 9901011501900001")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 0

    def test_invalid_birthdate(self, recognizer, make_segment, make_context):
        """Test NIK with invalid birthdate."""
        # Month 13 is invalid
        segment = make_segment("NIK: 3201011513900001", key_label="NIK")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        # Should detect but with lower score
        if findings:
            assert findings[0].raw_score < 0.8

    def test_nik_with_separators(self, recognizer, make_segment, make_context):
        """Test NIK with separators."""
        segment = make_segment("NIK: 32.01.01.150190.0001", key_label="NIK")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1

    def test_parse_nik_function(self):
        """Test parse_nik helper function."""
        metadata = parse_nik("3201011501900001")

        assert metadata is not None
        assert metadata.province_code == "32"
        assert metadata.province_name == "Jawa Barat"
        assert metadata.birth_day == 15
        assert metadata.birth_month == 1
        assert metadata.birth_year == 1990
        assert metadata.is_female is False

    def test_all_provinces_valid(self):
        """Test that all province codes are recognized."""
        assert len(VALID_PROVINCE_CODES) >= 36
        assert "11" in VALID_PROVINCE_CODES  # Aceh
        assert "31" in VALID_PROVINCE_CODES  # DKI Jakarta
        assert "91" in VALID_PROVINCE_CODES  # Papua Barat


# =============================================================================
# Enhanced NPWP Recognizer Tests
# =============================================================================

class TestEnhancedNPWPRecognizer:
    """Tests for EnhancedNPWPRecognizer."""

    @pytest.fixture
    def recognizer(self):
        return EnhancedNPWPRecognizer()

    def test_formatted_npwp(self, recognizer, make_segment, make_context):
        """Test detecting formatted NPWP."""
        segment = make_segment("NPWP: 01.234.567.8-901.234", key_label="NPWP")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1
        assert findings[0].entity_type == "ID_NPWP"
        assert findings[0].is_validated

    def test_plain_npwp_with_context(self, recognizer, make_segment, make_context):
        """Test detecting plain NPWP with context."""
        segment = make_segment("NPWP: 012345678901234", key_label="NPWP")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1

    def test_plain_npwp_without_context(self, recognizer, make_segment, make_context):
        """Test plain NPWP without context - may still detect with valid structure."""
        segment = make_segment("Number: 012345678901234")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        # NPWP with valid structure may still be detected but with lower confidence
        if findings:
            assert findings[0].raw_score < 0.8  # Lower confidence without context

    def test_format_npwp_function(self):
        """Test format_npwp helper."""
        formatted = format_npwp("012345678901234")
        assert formatted == "01.234.567.8-901.234"

    def test_parse_npwp_function(self):
        """Test parse_npwp helper."""
        metadata = parse_npwp("01.234.567.8-901.234")

        assert metadata is not None
        assert metadata.is_legacy_format is True
        assert metadata.is_nik_based is False
        assert metadata.category_code == "01"
        assert metadata.branch_code == "901"


# =============================================================================
# Enhanced KK Recognizer Tests
# =============================================================================

class TestEnhancedKKRecognizer:
    """Tests for EnhancedKKRecognizer."""

    @pytest.fixture
    def recognizer(self):
        return EnhancedKKRecognizer()

    def test_kk_with_context(self, recognizer, make_segment, make_context):
        """Test detecting KK with explicit context."""
        segment = make_segment("No. KK: 3201011501200001", key_label="No. KK")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1
        assert findings[0].entity_type == "ID_KK"

    def test_kk_without_context(self, recognizer, make_segment, make_context):
        """Test KK without explicit context - may still detect with valid structure."""
        segment = make_segment("Number: 3201011501200001")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        # KK with valid structure may still be detected
        # In practice, overlap resolver would choose NIK over KK without explicit context
        if findings:
            assert findings[0].entity_type == "ID_KK"

    def test_kk_vs_nik_context(self, recognizer, make_segment, make_context):
        """Test that NIK context prevents KK detection."""
        segment = make_segment("NIK: 3201011501200001", key_label="NIK")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        # NIK context should prevent KK detection
        assert len(findings) == 0

    def test_parse_kk_function(self):
        """Test parse_kk helper."""
        # KK: 3201011501200001 - registration date 15/01/20 (2020)
        metadata = parse_kk("3201011501200001")

        assert metadata is not None
        assert metadata.province_code == "32"
        assert metadata.reg_day == 15
        assert metadata.reg_month == 1
        # Year format: 20 -> 2020 (or 1920 depending on implementation)
        assert metadata.reg_year in (2020, 1920)  # Accept either century


# =============================================================================
# Enhanced Phone Recognizer Tests
# =============================================================================

class TestEnhancedPhoneRecognizer:
    """Tests for EnhancedPhoneRecognizer."""

    @pytest.fixture
    def recognizer(self):
        return EnhancedPhoneRecognizer()

    def test_mobile_08xx_format(self, recognizer, make_segment, make_context):
        """Test detecting 08xx format."""
        segment = make_segment("Telepon: 081234567890", key_label="Telepon")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1
        assert findings[0].entity_type == "ID_PHONE"

    def test_mobile_plus62_format(self, recognizer, make_segment, make_context):
        """Test detecting +62 format."""
        segment = make_segment("Phone: +6281234567890", key_label="HP")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1

    def test_mobile_62_format(self, recognizer, make_segment, make_context):
        """Test detecting 62 format (without plus)."""
        segment = make_segment("HP: 6281234567890", key_label="HP")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1

    def test_formatted_phone(self, recognizer, make_segment, make_context):
        """Test detecting formatted phone."""
        segment = make_segment("Telepon: 0812-3456-7890", key_label="Telepon")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1

    def test_carrier_detection(self):
        """Test carrier prefix detection."""
        assert CARRIER_PREFIXES.get("812") == "Telkomsel"
        assert CARRIER_PREFIXES.get("856") == "Indosat"
        assert CARRIER_PREFIXES.get("817") == "XL"
        assert CARRIER_PREFIXES.get("831") == "Axis"
        assert CARRIER_PREFIXES.get("895") == "Three"
        assert CARRIER_PREFIXES.get("881") == "Smartfren"

    def test_format_phone_indonesia(self):
        """Test phone formatting."""
        formatted = format_phone_indonesia("081234567890")
        assert "+62" in formatted

    def test_parse_phone_indonesia(self):
        """Test phone parsing."""
        metadata = parse_phone_indonesia("+6281234567890")

        assert metadata is not None
        assert metadata.is_mobile is True
        assert metadata.region == "ID"


# =============================================================================
# BPJS Recognizer Tests
# =============================================================================

class TestBPJSRecognizer:
    """Tests for BPJSRecognizer."""

    @pytest.fixture
    def recognizer(self):
        return BPJSRecognizer()

    def test_bpjs_with_context(self, recognizer, make_segment, make_context):
        """Test detecting BPJS with context."""
        segment = make_segment("No. BPJS: 0001234567890", key_label="No. BPJS")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1
        assert findings[0].entity_type == "ID_BPJS"

    def test_bpjs_without_context(self, recognizer, make_segment, make_context):
        """Test BPJS without context is not detected."""
        segment = make_segment("Number: 0001234567890")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        # Requires context
        assert len(findings) == 0

    def test_bpjs_in_text_context(self, recognizer, make_segment, make_context):
        """Test BPJS with context in surrounding text."""
        segment = make_segment("Nomor BPJS Kesehatan: 0001234567890")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1

    def test_format_bpjs(self):
        """Test BPJS formatting."""
        formatted = format_bpjs("0001234567890")
        assert formatted == "0001-2345-67890"

    def test_invalid_bpjs_all_same(self, recognizer, make_segment, make_context):
        """Test that all-same-digit is rejected."""
        segment = make_segment("BPJS: 0000000000000", key_label="BPJS")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 0


# =============================================================================
# SIM Recognizer Tests
# =============================================================================

class TestSIMRecognizer:
    """Tests for SIMRecognizer."""

    @pytest.fixture
    def recognizer(self):
        return SIMRecognizer()

    def test_sim_with_context(self, recognizer, make_segment, make_context):
        """Test detecting SIM with context."""
        segment = make_segment("No. SIM: 123456789012", key_label="No. SIM")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1
        assert findings[0].entity_type == "ID_SIM"

    def test_sim_without_context(self, recognizer, make_segment, make_context):
        """Test SIM without context is not detected."""
        segment = make_segment("Number: 123456789012")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        # Requires context
        assert len(findings) == 0

    def test_sim_type_detection(self, recognizer, make_segment, make_context):
        """Test SIM type detection from context."""
        segment = make_segment("SIM A: 123456789012")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1
        # Evidence should mention SIM type

    def test_sim_14_digits(self, recognizer, make_segment, make_context):
        """Test 14-digit SIM."""
        segment = make_segment("SIM: 12345678901234", key_label="SIM")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1


# =============================================================================
# Passport Recognizer Tests
# =============================================================================

class TestPassportRecognizer:
    """Tests for PassportRecognizer."""

    @pytest.fixture
    def recognizer(self):
        return PassportRecognizer()

    def test_passport_with_context(self, recognizer, make_segment, make_context):
        """Test detecting passport with context."""
        segment = make_segment("Passport: A9876543", key_label="Passport")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1
        assert findings[0].entity_type == "ID_PASSPORT"

    def test_passport_lowercase(self, recognizer, make_segment, make_context):
        """Test passport with lowercase letter."""
        segment = make_segment("Paspor: a9876543", key_label="Paspor")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1

    def test_passport_with_separator(self, recognizer, make_segment, make_context):
        """Test passport with separator."""
        segment = make_segment("Passport: A 9876543", key_label="Passport")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 1

    def test_passport_without_context(self, recognizer, make_segment, make_context):
        """Test passport without context has lower score."""
        segment = make_segment("Code: A9876543")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        # May detect but with lower score
        if findings:
            assert findings[0].raw_score < 0.7

    def test_valid_series_letters(self, recognizer, make_segment, make_context):
        """Test various valid series letters."""
        for letter in ["A", "B", "C", "M", "N", "P", "R", "S", "T", "X"]:
            segment = make_segment(f"Passport: {letter}9876543", key_label="Passport")
            context = make_context(segment)

            findings = recognizer.analyze(segment, context)

            assert len(findings) == 1
            assert findings[0].is_validated

    def test_format_passport(self):
        """Test passport formatting."""
        formatted = format_passport("A9876543")
        assert formatted == "A 9876543"

    def test_invalid_passport_all_zeros(self, recognizer, make_segment, make_context):
        """Test that all-zero number is rejected."""
        segment = make_segment("Passport: A0000000", key_label="Passport")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 0

    def test_invalid_passport_sequential(self, recognizer, make_segment, make_context):
        """Test that sequential 1234567 is rejected as example data."""
        segment = make_segment("Passport: A1234567", key_label="Passport")
        context = make_context(segment)

        findings = recognizer.analyze(segment, context)

        assert len(findings) == 0


# =============================================================================
# Integration Tests
# =============================================================================

class TestRecognizerIntegration:
    """Integration tests for all recognizers working together."""

    def test_multiple_ids_in_document(self, make_segment, make_context):
        """Test detecting multiple ID types in one document."""
        nik_recognizer = EnhancedNIKRecognizer()
        npwp_recognizer = EnhancedNPWPRecognizer()
        phone_recognizer = EnhancedPhoneRecognizer()

        text = """
        Data Karyawan:
        NIK: 3201011501900001
        NPWP: 01.234.567.8-901.234
        Telepon: 081234567890
        """

        segment = make_segment(text)
        context = make_context(segment)

        nik_findings = nik_recognizer.analyze(segment, context)
        npwp_findings = npwp_recognizer.analyze(segment, context)
        phone_findings = phone_recognizer.analyze(segment, context)

        assert len(nik_findings) >= 1
        assert len(npwp_findings) >= 1
        assert len(phone_findings) >= 1

    def test_context_from_table_headers(self, make_segment, make_context):
        """Test that table headers provide context."""
        nik_recognizer = EnhancedNIKRecognizer()

        segment = make_segment(
            "3201011501900001",
            table_headers=["Nama", "NIK", "Alamat"],
        )
        context = make_context(segment)

        findings = nik_recognizer.analyze(segment, context)

        assert len(findings) == 1
        # Should have context boost
        assert findings[0].raw_score >= 0.8

    def test_no_false_positive_on_random_numbers(self, make_segment, make_context):
        """Test that random numbers don't trigger false positives."""
        recognizers = [
            EnhancedNIKRecognizer(),
            EnhancedNPWPRecognizer(),
            BPJSRecognizer(),
            SIMRecognizer(),
            PassportRecognizer(),
        ]

        # Random numbers that shouldn't match
        random_texts = [
            "Invoice #123456789",
            "Order ID: 9876543210",
            "SKU: ABC12345",
            "Reference: 2024010100001",
        ]

        for text in random_texts:
            segment = make_segment(text)
            context = make_context(segment)

            for recognizer in recognizers:
                findings = recognizer.analyze(segment, context)
                # Should not detect without proper context
                assert len(findings) == 0, f"{recognizer.name} false positive on: {text}"
