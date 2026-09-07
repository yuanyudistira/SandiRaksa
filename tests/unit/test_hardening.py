"""Tests for security hardening utilities."""

import tempfile
import zipfile
from pathlib import Path

import pytest

from sandiraksa.security.hardening import (
    DEFAULT_CONFIG,
    FileSizeError,
    FileTypeError,
    SecurityConfig,
    SecurityError,
    XMLSecurityError,
    ZipBombError,
    check_zip_bomb,
    parse_xml_safely,
    sanitize_filename,
    validate_file_path,
    validate_input_text,
)


class TestSecurityConfig:
    """Tests for SecurityConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = DEFAULT_CONFIG
        
        assert config.max_file_size == 100 * 1024 * 1024
        assert config.max_xml_size == 10 * 1024 * 1024
        assert config.max_zip_ratio == 100.0
        assert config.forbid_dtd is True
        assert ".csv" in config.allowed_extensions

    def test_custom_config(self):
        """Test custom configuration."""
        config = SecurityConfig(
            max_file_size=50 * 1024 * 1024,
            max_zip_ratio=50.0,
        )
        
        assert config.max_file_size == 50 * 1024 * 1024
        assert config.max_zip_ratio == 50.0


class TestValidateFilePath:
    """Tests for file path validation."""

    def test_validate_nonexistent_file(self):
        """Test validation fails for nonexistent file."""
        is_valid, error = validate_file_path("/nonexistent/file.csv")
        
        assert is_valid is False
        assert "does not exist" in error

    def test_validate_valid_csv(self):
        """Test validation passes for valid CSV file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test.csv"
            csv_path.write_text("col1,col2\n1,2\n")
            
            is_valid, error = validate_file_path(csv_path)
            
            assert is_valid is True
            assert error == ""

    def test_validate_disallowed_extension(self):
        """Test validation fails for disallowed extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.write_bytes(b"fake exe content")
            
            is_valid, error = validate_file_path(exe_path)
            
            assert is_valid is False
            assert "not allowed" in error

    def test_validate_empty_file(self):
        """Test validation fails for empty file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_path = Path(tmpdir) / "empty.csv"
            empty_path.write_text("")
            
            is_valid, error = validate_file_path(empty_path)
            
            assert is_valid is False
            assert "empty" in error


class TestCheckZipBomb:
    """Tests for ZIP bomb detection."""

    def test_normal_zip(self):
        """Test normal ZIP file passes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "test.xlsx"
            
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("content.txt", "Normal content here")
            
            is_safe, warning = check_zip_bomb(zip_path)
            
            assert is_safe is True
            assert warning == ""

    def test_invalid_zip(self):
        """Test invalid ZIP file detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_zip = Path(tmpdir) / "fake.xlsx"
            fake_zip.write_text("not a zip file")
            
            is_safe, warning = check_zip_bomb(fake_zip)
            
            assert is_safe is False
            assert "Invalid" in warning or "corrupted" in warning

    def test_too_many_files(self):
        """Test detection of too many files."""
        config = SecurityConfig(max_zip_files=5)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "many_files.xlsx"
            
            with zipfile.ZipFile(zip_path, "w") as zf:
                for i in range(10):
                    zf.writestr(f"file{i}.txt", f"content {i}")
            
            is_safe, warning = check_zip_bomb(zip_path, config)
            
            assert is_safe is False
            assert "Too many files" in warning


class TestParseXMLSafely:
    """Tests for secure XML parsing."""

    def test_parse_valid_xml(self):
        """Test parsing valid XML."""
        xml = "<root><child>text</child></root>"
        
        element = parse_xml_safely(xml)
        
        assert element.tag == "root"
        assert element.find("child").text == "text"

    def test_parse_xml_bytes(self):
        """Test parsing XML bytes."""
        xml = b"<root><item>value</item></root>"
        
        element = parse_xml_safely(xml)
        
        assert element.tag == "root"

    def test_reject_doctype(self):
        """Test DOCTYPE is rejected."""
        xml = '<!DOCTYPE root><root></root>'
        
        with pytest.raises(XMLSecurityError) as exc_info:
            parse_xml_safely(xml)
        
        assert "DOCTYPE" in str(exc_info.value)

    def test_reject_entity(self):
        """Test ENTITY declarations are rejected."""
        xml = '<!ENTITY xxe SYSTEM "file:///etc/passwd"><root></root>'
        
        with pytest.raises(XMLSecurityError) as exc_info:
            parse_xml_safely(xml)
        
        assert "ENTITY" in str(exc_info.value)

    def test_reject_oversized_xml(self):
        """Test oversized XML is rejected."""
        config = SecurityConfig(max_xml_size=100)
        
        xml = "<root>" + "x" * 200 + "</root>"
        
        with pytest.raises(XMLSecurityError) as exc_info:
            parse_xml_safely(xml, config)
        
        assert "too large" in str(exc_info.value)


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_normal_filename(self):
        """Test normal filename unchanged."""
        result = sanitize_filename("document.csv")
        
        assert result == "document.csv"

    def test_remove_path_separators(self):
        """Test path separators replaced."""
        result = sanitize_filename(".._.._.._.._etc_passwd")
        
        assert "/" not in result
        assert "\\" not in result

    def test_remove_null_bytes(self):
        """Test null bytes removed."""
        result = sanitize_filename("file\x00.csv")
        
        assert "\x00" not in result

    def test_remove_dangerous_chars(self):
        """Test dangerous characters removed."""
        result = sanitize_filename('file<>:"|?*.csv')
        
        for char in '<>:"|?*':
            assert char not in result

    def test_strip_dots_spaces(self):
        """Test leading/trailing dots and spaces stripped."""
        result = sanitize_filename("  ..file.csv.  ")
        
        assert not result.startswith(".")
        assert not result.startswith(" ")
        assert not result.endswith(".")
        assert not result.endswith(" ")

    def test_empty_filename(self):
        """Test empty filename gets default."""
        result = sanitize_filename("...")
        
        assert result == "unnamed_file"

    def test_truncate_long_filename(self):
        """Test long filename is truncated."""
        long_name = "a" * 300 + ".csv"
        result = sanitize_filename(long_name)
        
        assert len(result) <= 255
        assert result.endswith(".csv")


class TestValidateInputText:
    """Tests for input text validation."""

    def test_valid_text(self):
        """Test valid text passes."""
        is_valid, error = validate_input_text("Hello, World!")
        
        assert is_valid is True
        assert error == ""

    def test_text_with_whitespace(self):
        """Test text with common whitespace."""
        is_valid, error = validate_input_text("Line 1\nLine 2\tTabbed")
        
        assert is_valid is True

    def test_text_too_long(self):
        """Test overly long text rejected."""
        is_valid, error = validate_input_text("x" * 20000, max_length=10000)
        
        assert is_valid is False
        assert "too long" in error

    def test_control_chars_rejected(self):
        """Test control characters rejected."""
        is_valid, error = validate_input_text("text\x00with\x01control")
        
        assert is_valid is False
        assert "control character" in error

    def test_control_chars_allowed(self):
        """Test control characters allowed when configured."""
        is_valid, error = validate_input_text(
            "text\x00with\x01control",
            allow_control_chars=True,
        )
        
        assert is_valid is True
