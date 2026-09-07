"""
Logging configuration for SandiRaksa.

Features:
- PII redaction filter to prevent sensitive data in logs
- File and console handlers
- Configurable log levels
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class PIIRedactionFilter(logging.Filter):
    """
    Log filter that redacts potential PII from log messages.

    Patterns redacted:
    - Email addresses
    - Phone numbers
    - Indonesian NIK (16 digits)
    - Indonesian NPWP
    - Credit card numbers
    - IP addresses
    """

    # Patterns to redact
    PATTERNS = [
        # Email
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL_REDACTED]"),
        # Phone numbers (various formats)
        (r"\b(?:\+62|62|0)[\s.-]?\d{2,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4}\b", "[PHONE_REDACTED]"),
        (r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "[PHONE_REDACTED]"),
        # Indonesian NIK (16 digits)
        (r"\b\d{16}\b", "[NIK_REDACTED]"),
        # Indonesian NPWP
        (r"\b\d{2}\.\d{3}\.\d{3}\.\d[-]?\d{3}\.\d{3}\b", "[NPWP_REDACTED]"),
        # Credit card (various formats)
        (r"\b\d{4}[\s.-]?\d{4}[\s.-]?\d{4}[\s.-]?\d{4}\b", "[CC_REDACTED]"),
        # IP addresses
        (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP_REDACTED]"),
        # Potential names (capitalized words, 2+ consecutive)
        # Commented out as too aggressive
        # (r"\b[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", "[NAME_REDACTED]"),
    ]

    def __init__(self, name: str = "") -> None:
        super().__init__(name)
        self._compiled_patterns = [
            (re.compile(pattern), replacement)
            for pattern, replacement in self.PATTERNS
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and redact PII from log record."""
        # Redact from message
        if record.msg:
            record.msg = self._redact(str(record.msg))

        # Redact from args if present
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._redact(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._redact(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )

        return True

    def _redact(self, text: str) -> str:
        """Apply all redaction patterns to text."""
        for pattern, replacement in self._compiled_patterns:
            text = pattern.sub(replacement, text)
        return text


class SandiRaksaFormatter(logging.Formatter):
    """Custom formatter with consistent output."""

    def __init__(self, include_module: bool = True) -> None:
        if include_module:
            fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        else:
            fmt = "%(asctime)s [%(levelname)s] %(message)s"

        super().__init__(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")


def setup_logging(
    log_level: str = "INFO",
    log_file: Path | str | None = None,
    enable_pii_redaction: bool = True,
    enable_console: bool = True,
) -> None:
    """
    Configure application logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional file path for file logging.
        enable_pii_redaction: Enable PII redaction filter.
        enable_console: Enable console output.
    """
    # Get root logger for sandiraksa
    logger = logging.getLogger("sandiraksa")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = SandiRaksaFormatter(include_module=True)

    # PII redaction filter
    pii_filter = PIIRedactionFilter() if enable_pii_redaction else None

    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        if pii_filter:
            console_handler.addFilter(pii_filter)
        logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        if pii_filter:
            file_handler.addFilter(pii_filter)
        logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    for noisy in ["urllib3", "chardet", "PIL"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_log_file_path() -> Path:
    """Get default log file path."""
    from platformdirs import user_log_dir

    log_dir = Path(user_log_dir("SandiRaksa", "SandiRaksa"))
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d")
    return log_dir / f"sandiraksa_{timestamp}.log"


__all__ = [
    "PIIRedactionFilter",
    "SandiRaksaFormatter",
    "setup_logging",
    "get_log_file_path",
]
