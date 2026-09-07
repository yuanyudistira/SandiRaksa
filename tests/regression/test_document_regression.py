"""
Document Regression Tests.

Tests to ensure document handlers maintain correct behavior across versions.
Uses predefined test cases with expected outputs.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


class TestCSVRegression:
    """Regression tests for CSV handling."""

    def test_csv_encoding_detection(self):
        """Test CSV encoding is correctly detected."""
        from sandiraksa.documents.csv_handler import CSVReader
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # UTF-8 with BOM
            utf8_bom = Path(tmpdir) / "utf8_bom.csv"
            utf8_bom.write_bytes(b"\xef\xbb\xbfname,value\ntest,123")
            
            reader = CSVReader(utf8_bom)
            metadata = reader.detect_metadata()
            
            assert metadata is not None
            assert metadata.encoding in ("utf-8-sig", "utf-8")

    def test_csv_quoted_fields(self):
        """Test CSV quoted fields with special characters."""
        from sandiraksa.documents.csv_handler import CSVReader
        
        with tempfile.TemporaryDirectory() as tmpdir:
            quoted_csv = Path(tmpdir) / "quoted.csv"
            quoted_csv.write_text(
                'name,description\n'
                '"John Doe","Has comma, here"\n',
                encoding="utf-8"
            )
            
            reader = CSVReader(quoted_csv)
            rows = list(reader.iter_rows())
            
            assert len(rows) >= 1

    def test_csv_unicode_content(self):
        """Test CSV handles Unicode content."""
        from sandiraksa.documents.csv_handler import CSVReader
        
        with tempfile.TemporaryDirectory() as tmpdir:
            unicode_csv = Path(tmpdir) / "unicode.csv"
            unicode_csv.write_text(
                "nama,keterangan\n"
                "Budi Santoso,Data test\n",
                encoding="utf-8"
            )
            
            reader = CSVReader(unicode_csv)
            rows = list(reader.iter_rows())
            
            assert len(rows) >= 1
            content = str(rows)
            assert "Budi" in content


class TestCryptoRegression:
    """Regression tests for cryptographic operations."""

    def test_hmac_deterministic(self):
        """Test HMAC produces consistent results."""
        from sandiraksa.security import compute_hmac
        
        key = b"test-key-32-bytes-for-hmac-test!"
        data = b"test data"
        
        result1 = compute_hmac(key, data)
        result2 = compute_hmac(key, data)
        
        assert result1 == result2

    def test_hmac_different_for_different_data(self):
        """Test HMAC is different for different data."""
        from sandiraksa.security import compute_hmac
        
        key = b"test-key-32-bytes-for-hmac-test!"
        
        result1 = compute_hmac(key, b"data1")
        result2 = compute_hmac(key, b"data2")
        
        assert result1 != result2

    def test_key_derivation_produces_key(self):
        """Test key derivation produces valid key."""
        from sandiraksa.security import KEY_SIZE, derive_key
        
        key, salt = derive_key("password")
        
        assert len(key) == KEY_SIZE
        assert len(salt) == 16


class TestProfilesRegression:
    """Regression tests for privacy profiles."""

    def test_all_profiles_available(self):
        """Test all expected profiles are available."""
        from sandiraksa.profiles import get_all_profiles, get_profile
        
        profiles = get_all_profiles()
        
        assert len(profiles) == 5
        
        assert get_profile("standard") is not None
        assert get_profile("hr") is not None
        assert get_profile("banking") is not None
        assert get_profile("healthcare") is not None
        assert get_profile("legal") is not None

    def test_profiles_have_indonesian_types(self):
        """Test profiles include Indonesian PII types."""
        from sandiraksa.profiles import get_all_profiles
        
        for profile in get_all_profiles():
            # All profiles should support NIK at minimum
            assert "ID_NIK" in profile.entity_types
