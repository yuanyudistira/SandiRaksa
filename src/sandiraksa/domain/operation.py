"""
Operation domain model.

Represents a processing operation (scan, protect, restore) on files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass


class OperationType(str, Enum):
    """Types of operations."""

    SCAN = "scan"
    PROTECT = "protect"
    RESTORE = "restore"
    RESCAN = "rescan"


class OperationStatus(str, Enum):
    """Status of an operation."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Operation(BaseModel):
    """
    Domain model for an operation.

    Operations track the processing history without storing
    complete raw file contents.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    file_id: str | None = None
    operation_type: OperationType
    reversible: bool
    profile_id: str | None = None
    app_version: str
    status: OperationStatus = OperationStatus.PENDING
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    # Counts (do not contain raw PII)
    findings_total: int = 0
    treated_total: int = 0
    ignored_total: int = 0
    residual_total: int = 0

    # Warnings stored as JSON (no raw PII values)
    warnings: list[str] = Field(default_factory=list)

    # File hashes for integrity
    source_sha256: str | None = None
    output_sha256: str | None = None

    class Config:
        """Pydantic configuration."""

        use_enum_values = True

    @property
    def is_complete(self) -> bool:
        """Check if operation is complete."""
        return self.status in {
            OperationStatus.COMPLETED,
            OperationStatus.COMPLETED_WITH_WARNINGS,
        }

    @property
    def is_successful(self) -> bool:
        """Check if operation completed successfully."""
        return self.status in {
            OperationStatus.COMPLETED,
            OperationStatus.COMPLETED_WITH_WARNINGS,
        }

    @property
    def duration_seconds(self) -> float | None:
        """Get operation duration in seconds."""
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def complete(
        self,
        *,
        findings_total: int = 0,
        treated_total: int = 0,
        ignored_total: int = 0,
        residual_total: int = 0,
        warnings: list[str] | None = None,
        output_sha256: str | None = None,
    ) -> None:
        """Mark operation as complete."""
        self.completed_at = datetime.utcnow()
        self.findings_total = findings_total
        self.treated_total = treated_total
        self.ignored_total = ignored_total
        self.residual_total = residual_total
        self.output_sha256 = output_sha256

        if warnings:
            self.warnings = warnings

        if residual_total > 0 or warnings:
            self.status = OperationStatus.COMPLETED_WITH_WARNINGS
        else:
            self.status = OperationStatus.COMPLETED

    def fail(self, error_message: str) -> None:
        """Mark operation as failed."""
        self.completed_at = datetime.utcnow()
        self.status = OperationStatus.FAILED
        self.warnings.append(f"Error: {error_message}")

    def cancel(self) -> None:
        """Mark operation as cancelled."""
        self.completed_at = datetime.utcnow()
        self.status = OperationStatus.CANCELLED


@dataclass
class OperationSummary:
    """Lightweight summary for operation history display."""

    id: str
    operation_type: OperationType
    status: OperationStatus
    reversible: bool
    started_at: datetime
    completed_at: datetime | None
    findings_total: int
    treated_total: int
    ignored_total: int
    residual_total: int
    has_warnings: bool

    @property
    def display_status(self) -> str:
        """Get localization-friendly status key."""
        return self.status.value


@dataclass
class OperationProgress:
    """Progress information for an ongoing operation."""

    operation_id: str
    phase: str
    current: int
    total: int
    message: str
    file_id: str | None = None
    component: str | None = None

    @property
    def percentage(self) -> float:
        """Get completion percentage."""
        if self.total == 0:
            return 0.0
        return min(100.0, (self.current / self.total) * 100)

    @property
    def is_indeterminate(self) -> bool:
        """Check if progress is indeterminate."""
        return self.total == 0
