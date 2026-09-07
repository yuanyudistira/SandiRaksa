"""
File record domain model.

Represents a file that has been added to a project for processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass


class FileStatus(str, Enum):
    """Status of a file in the processing pipeline."""

    PENDING = "pending"
    VALIDATING = "validating"
    SCANNING = "scanning"
    REVIEW_REQUIRED = "review_required"
    READY_TO_PROTECT = "ready_to_protect"
    PROTECTING = "protecting"
    VALIDATING_OUTPUT = "validating_output"
    READY = "ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    FAILED = "failed"
    RESTORING = "restoring"
    RESTORED = "restored"


class FileFormat(str, Enum):
    """Supported file formats."""

    CSV = "csv"
    XLSX = "xlsx"
    XLSM = "xlsm"
    DOCX = "docx"
    PPTX = "pptx"
    TXT = "txt"
    UNKNOWN = "unknown"

    @classmethod
    def from_extension(cls, extension: str) -> FileFormat:
        """Get format from file extension."""
        ext = extension.lower().lstrip(".")
        mapping = {
            "csv": cls.CSV,
            "xlsx": cls.XLSX,
            "xlsm": cls.XLSM,
            "docx": cls.DOCX,
            "pptx": cls.PPTX,
            "txt": cls.TXT,
        }
        return mapping.get(ext, cls.UNKNOWN)

    @classmethod
    def supported_extensions(cls) -> set[str]:
        """Get set of supported file extensions."""
        return {".csv", ".xlsx", ".docx", ".pptx", ".txt"}


class FileRecord(BaseModel):
    """
    Domain model for a file added to a project.

    Tracks the file's processing status and metadata without
    storing the actual file content.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    filename: str
    extension: str
    format: FileFormat
    file_size: int | None = None
    source_path: str | None = None  # Only if remember_source_paths is True
    source_sha256: str | None = None
    latest_output_sha256: str | None = None
    status: FileStatus = FileStatus.PENDING
    added_at: datetime = Field(default_factory=datetime.utcnow)
    last_processed_at: datetime | None = None

    class Config:
        """Pydantic configuration."""

        use_enum_values = True

    @classmethod
    def from_path(
        cls,
        path: Path,
        project_id: str,
        *,
        remember_source: bool = False,
    ) -> FileRecord:
        """Create a FileRecord from a file path."""
        extension = path.suffix.lower()
        return cls(
            project_id=project_id,
            filename=path.name,
            extension=extension,
            format=FileFormat.from_extension(extension),
            file_size=path.stat().st_size if path.exists() else None,
            source_path=str(path) if remember_source else None,
        )

    @property
    def is_processed(self) -> bool:
        """Check if file has been processed."""
        return self.status in {
            FileStatus.READY,
            FileStatus.READY_WITH_WARNINGS,
            FileStatus.RESTORED,
        }

    @property
    def is_processing(self) -> bool:
        """Check if file is currently being processed."""
        return self.status in {
            FileStatus.VALIDATING,
            FileStatus.SCANNING,
            FileStatus.PROTECTING,
            FileStatus.VALIDATING_OUTPUT,
            FileStatus.RESTORING,
        }

    @property
    def needs_review(self) -> bool:
        """Check if file needs user review."""
        return self.status == FileStatus.REVIEW_REQUIRED


@dataclass
class FileValidationResult:
    """Result of file validation."""

    valid: bool
    format: FileFormat
    file_size: int
    error_code: str | None = None
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)

    @staticmethod
    def success(format: FileFormat, file_size: int) -> FileValidationResult:
        """Create a successful validation result."""
        return FileValidationResult(valid=True, format=format, file_size=file_size)

    @staticmethod
    def failure(
        format: FileFormat,
        file_size: int,
        error_code: str,
        error_message: str,
    ) -> FileValidationResult:
        """Create a failed validation result."""
        return FileValidationResult(
            valid=False,
            format=format,
            file_size=file_size,
            error_code=error_code,
            error_message=error_message,
        )
