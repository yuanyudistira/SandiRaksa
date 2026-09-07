"""
Security Hardening Utilities for SandiRaksa.

Provides:
- XML security (XXE prevention)
- ZIP bomb protection
- Input validation
- File security checks
"""

from __future__ import annotations

import logging
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Base security exception."""

    pass


class XMLSecurityError(SecurityError):
    """XML-related security issue detected."""

    pass


class ZipBombError(SecurityError):
    """Potential ZIP bomb detected."""

    pass


class FileSizeError(SecurityError):
    """File exceeds size limits."""

    pass


class FileTypeError(SecurityError):
    """Invalid or dangerous file type."""

    pass


@dataclass
class SecurityConfig:
    """Security configuration."""

    # File size limits (bytes)
    max_file_size: int = 100 * 1024 * 1024  # 100 MB
    max_xml_size: int = 10 * 1024 * 1024  # 10 MB

    # ZIP bomb protection
    max_zip_ratio: float = 100.0  # Compression ratio threshold
    max_zip_files: int = 10000  # Max files in archive
    max_uncompressed_size: int = 500 * 1024 * 1024  # 500 MB uncompressed

    # XML security
    forbid_dtd: bool = True
    forbid_entities: bool = True
    max_xml_depth: int = 100

    # Allowed file extensions
    allowed_extensions: frozenset[str] = frozenset({
        ".csv", ".xlsx", ".xls", ".docx", ".doc", ".pptx", ".ppt",
    })


# Default configuration
DEFAULT_CONFIG = SecurityConfig()


def validate_file_path(
    file_path: Path | str,
    config: SecurityConfig = DEFAULT_CONFIG,
) -> tuple[bool, str]:
    """
    Validate a file path for security issues.

    Args:
        file_path: Path to validate.
        config: Security configuration.

    Returns:
        Tuple of (is_valid, error_message).
    """
    path = Path(file_path)

    # Check existence
    if not path.exists():
        return False, "File does not exist"

    if not path.is_file():
        return False, "Path is not a file"

    # Check extension
    if path.suffix.lower() not in config.allowed_extensions:
        return False, f"File type not allowed: {path.suffix}"

    # Check file size
    try:
        size = path.stat().st_size
        if size > config.max_file_size:
            return False, f"File too large: {size} bytes (max: {config.max_file_size})"
        if size == 0:
            return False, "File is empty"
    except OSError as e:
        return False, f"Cannot read file stats: {e}"

    # Check for path traversal attempts
    try:
        # Resolve to absolute path and check for suspicious patterns
        resolved = path.resolve()
        if ".." in str(path):
            return False, "Path traversal detected"
    except Exception as e:
        return False, f"Invalid path: {e}"

    return True, ""


def check_zip_bomb(
    file_path: Path | str,
    config: SecurityConfig = DEFAULT_CONFIG,
) -> tuple[bool, str]:
    """
    Check if a ZIP file might be a ZIP bomb.

    Args:
        file_path: Path to ZIP/OOXML file.
        config: Security configuration.

    Returns:
        Tuple of (is_safe, warning_message).
    """
    path = Path(file_path)

    try:
        with zipfile.ZipFile(path, "r") as zf:
            # Count files
            file_count = len(zf.namelist())
            if file_count > config.max_zip_files:
                return False, f"Too many files in archive: {file_count}"

            # Calculate total uncompressed size
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > config.max_uncompressed_size:
                return False, f"Uncompressed size too large: {total_uncompressed}"

            # Check compression ratio
            compressed_size = path.stat().st_size
            if compressed_size > 0:
                ratio = total_uncompressed / compressed_size
                if ratio > config.max_zip_ratio:
                    return False, f"Suspicious compression ratio: {ratio:.1f}x"

            return True, ""

    except zipfile.BadZipFile:
        return False, "Invalid or corrupted ZIP file"
    except Exception as e:
        return False, f"Error checking ZIP file: {e}"


def create_secure_xml_parser() -> ET.XMLParser:
    """
    Create a secure XML parser with XXE protection.

    Returns:
        Configured XMLParser instance.
    """
    # Note: Python's ElementTree doesn't support external entities by default,
    # but we explicitly disable them for defense in depth
    parser = ET.XMLParser()

    # Disable DTD processing if using defusedxml
    try:
        import defusedxml.ElementTree as DefusedET
        return DefusedET.DefusedXMLParser()
    except ImportError:
        pass

    return parser


def parse_xml_safely(
    xml_content: str | bytes,
    config: SecurityConfig = DEFAULT_CONFIG,
) -> ET.Element:
    """
    Parse XML content with security protections.

    Args:
        xml_content: XML string or bytes.
        config: Security configuration.

    Returns:
        Parsed XML Element.

    Raises:
        XMLSecurityError: If security issues detected.
    """
    # Check size
    content_size = len(xml_content) if isinstance(xml_content, bytes) else len(xml_content.encode())
    if content_size > config.max_xml_size:
        raise XMLSecurityError(f"XML content too large: {content_size} bytes")

    # Check for suspicious patterns
    content_str = xml_content if isinstance(xml_content, str) else xml_content.decode("utf-8", errors="ignore")

    if config.forbid_dtd and "<!DOCTYPE" in content_str:
        raise XMLSecurityError("DOCTYPE declarations not allowed")

    if config.forbid_entities and "<!ENTITY" in content_str:
        raise XMLSecurityError("ENTITY declarations not allowed")

    # Try to use defusedxml if available
    try:
        import defusedxml.ElementTree as DefusedET
        return DefusedET.fromstring(xml_content)
    except ImportError:
        pass

    # Fall back to standard parser
    try:
        return ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise XMLSecurityError(f"XML parsing error: {e}") from e


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal and invalid characters.

    Args:
        filename: Original filename.

    Returns:
        Sanitized filename.
    """
    # Remove path separators
    filename = filename.replace("/", "_").replace("\\", "_")

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Remove leading/trailing dots and spaces
    filename = filename.strip(". ")

    # Remove or replace dangerous characters
    dangerous_chars = '<>:"|?*'
    for char in dangerous_chars:
        filename = filename.replace(char, "_")

    # Limit length
    max_length = 255
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[: max_length - len(ext)] + ext

    # Ensure filename is not empty
    if not filename:
        filename = "unnamed_file"

    return filename


def validate_input_text(
    text: str,
    max_length: int = 10000,
    allow_control_chars: bool = False,
) -> tuple[bool, str]:
    """
    Validate input text for security issues.

    Args:
        text: Text to validate.
        max_length: Maximum allowed length.
        allow_control_chars: Allow control characters.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if len(text) > max_length:
        return False, f"Text too long: {len(text)} (max: {max_length})"

    if not allow_control_chars:
        # Check for control characters (except common whitespace)
        for char in text:
            code = ord(char)
            if code < 32 and char not in "\t\n\r":
                return False, f"Invalid control character: \\x{code:02x}"

    return True, ""


def secure_file_operation(func):
    """
    Decorator for secure file operations.

    Validates file paths before operation.
    """
    def wrapper(file_path: Path | str, *args, **kwargs):
        is_valid, error = validate_file_path(file_path)
        if not is_valid:
            raise SecurityError(f"File validation failed: {error}")
        return func(file_path, *args, **kwargs)
    return wrapper


__all__ = [
    # Exceptions
    "SecurityError",
    "XMLSecurityError",
    "ZipBombError",
    "FileSizeError",
    "FileTypeError",
    # Config
    "SecurityConfig",
    "DEFAULT_CONFIG",
    # Functions
    "validate_file_path",
    "check_zip_bomb",
    "create_secure_xml_parser",
    "parse_xml_safely",
    "sanitize_filename",
    "validate_input_text",
    "secure_file_operation",
]
