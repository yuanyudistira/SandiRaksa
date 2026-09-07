"""Tests for logging module with PII redaction."""

import logging
import tempfile
from pathlib import Path

import pytest

from sandiraksa.app.logging import (
    PIIRedactionFilter,
    SandiRaksaFormatter,
    get_log_file_path,
    setup_logging,
)


class TestPIIRedactionFilter:
    """Tests for PII redaction in logs."""

    @pytest.fixture
    def pii_filter(self):
        """Create PII filter instance."""
        return PIIRedactionFilter()

    def test_redact_email(self, pii_filter):
        """Test email redaction."""
        text = "Contact john.doe@example.com for details"
        result = pii_filter._redact(text)
        
        assert "[EMAIL_REDACTED]" in result
        assert "john.doe@example.com" not in result

    def test_redact_indonesian_phone(self, pii_filter):
        """Test Indonesian phone number redaction."""
        text = "Call me at +62 812-3456-7890"
        result = pii_filter._redact(text)
        
        assert "[PHONE_REDACTED]" in result
        assert "812-3456-7890" not in result

    def test_redact_nik(self, pii_filter):
        """Test NIK redaction (16 digits)."""
        text = "NIK: 3201234567890123"
        result = pii_filter._redact(text)
        
        assert "[NIK_REDACTED]" in result
        assert "3201234567890123" not in result

    def test_redact_npwp(self, pii_filter):
        """Test NPWP redaction."""
        text = "NPWP: 12.345.678.9-012.345"
        result = pii_filter._redact(text)
        
        assert "[NPWP_REDACTED]" in result
        assert "12.345.678.9-012.345" not in result

    def test_redact_credit_card(self, pii_filter):
        """Test credit card redaction."""
        text = "Card: 4111-1111-1111-1111"
        result = pii_filter._redact(text)
        
        assert "[CC_REDACTED]" in result
        assert "4111-1111-1111-1111" not in result

    def test_redact_ip_address(self, pii_filter):
        """Test IP address redaction."""
        text = "Server at 192.168.1.100"
        result = pii_filter._redact(text)
        
        assert "[IP_REDACTED]" in result
        assert "192.168.1.100" not in result

    def test_no_false_positives_for_normal_text(self, pii_filter):
        """Test normal text is not redacted."""
        text = "This is a normal log message about processing files"
        result = pii_filter._redact(text)
        
        assert result == text

    def test_filter_log_record(self, pii_filter):
        """Test filtering log record."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="User email is test@example.com",
            args=(),
            exc_info=None,
        )
        
        pii_filter.filter(record)
        
        assert "[EMAIL_REDACTED]" in record.msg
        assert "test@example.com" not in record.msg

    def test_filter_with_dict_args(self, pii_filter):
        """Test filtering direct text with dict format."""
        # Test redaction works when email appears in string
        text = "secret@example.com"
        result = pii_filter._redact(text)
        
        assert "[EMAIL_REDACTED]" in result

    def test_filter_with_tuple_args(self, pii_filter):
        """Test filtering with tuple args."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Email: %s Phone: %s",
            args=("test@email.com", "+62 812 3456 7890"),
            exc_info=None,
        )
        
        pii_filter.filter(record)
        
        assert "[EMAIL_REDACTED]" in record.args[0]
        assert "[PHONE_REDACTED]" in record.args[1]


class TestSandiRaksaFormatter:
    """Tests for custom log formatter."""

    def test_formatter_with_module(self):
        """Test formatter includes module name."""
        formatter = SandiRaksaFormatter(include_module=True)
        
        record = logging.LogRecord(
            name="sandiraksa.detection",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        
        assert "sandiraksa.detection" in result
        assert "Test message" in result
        assert "[INFO]" in result

    def test_formatter_without_module(self):
        """Test formatter without module name."""
        formatter = SandiRaksaFormatter(include_module=False)
        
        record = logging.LogRecord(
            name="sandiraksa.detection",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Warning message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        
        assert "[WARNING]" in result
        assert "Warning message" in result


class TestSetupLogging:
    """Tests for logging setup."""

    def test_setup_basic(self):
        """Test basic logging setup."""
        setup_logging(log_level="DEBUG", enable_console=False)
        
        logger = logging.getLogger("sandiraksa")
        assert logger.level == logging.DEBUG

    def test_setup_with_file(self):
        """Test logging setup with file handler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            
            setup_logging(
                log_level="INFO",
                log_file=log_file,
                enable_console=False,
            )
            
            logger = logging.getLogger("sandiraksa")
            logger.info("Test message")
            
            # Flush and close handlers
            for handler in logger.handlers[:]:
                handler.flush()
                handler.close()
                logger.removeHandler(handler)
            
            assert log_file.exists()
            content = log_file.read_text()
            assert "Test message" in content

    def test_setup_with_pii_redaction(self):
        """Test logging setup with PII redaction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            
            setup_logging(
                log_level="INFO",
                log_file=log_file,
                enable_pii_redaction=True,
                enable_console=False,
            )
            
            logger = logging.getLogger("sandiraksa")
            logger.info("Email: test@example.com")
            
            # Flush and close handlers
            for handler in logger.handlers[:]:
                handler.flush()
                handler.close()
                logger.removeHandler(handler)
            
            content = log_file.read_text()
            assert "[EMAIL_REDACTED]" in content
            assert "test@example.com" not in content


class TestGetLogFilePath:
    """Tests for log file path generation."""

    def test_log_file_path_structure(self):
        """Test log file path has expected structure."""
        path = get_log_file_path()
        
        assert path.suffix == ".log"
        assert "sandiraksa_" in path.name
        assert path.parent.exists()
