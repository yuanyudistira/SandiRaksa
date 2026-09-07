"""
Project domain model.

A project is the core organizational unit that contains:
- Project metadata
- Protection policy
- Privacy profile
- Custom confidential terms
- File history
- Operation history
- Token namespace
- Reversible mapping vault
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from sandiraksa.config.settings import RetentionPolicy

if TYPE_CHECKING:
    pass


class ProjectStatus(str, Enum):
    """Project status states."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class Project(BaseModel):
    """
    Domain model for a project.

    A project is the boundary for:
    - Project metadata
    - Protection policy
    - Privacy profile
    - Custom confidential terms
    - File history
    - Operation history
    - Token namespace
    - Reversible mapping vault
    - Retention settings
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    profile_id: str = "standard_pii"
    reversible_default: bool = True
    remember_source_paths: bool = False
    retention_policy: RetentionPolicy = RetentionPolicy.UNTIL_DELETED
    status: ProjectStatus = ProjectStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_opened_at: datetime | None = None

    # Transient fields (not persisted directly)
    file_count: int = 0
    mapping_count: int = 0

    class Config:
        """Pydantic configuration."""

        use_enum_values = True

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()

    def mark_opened(self) -> None:
        """Update the last_opened_at timestamp."""
        self.last_opened_at = datetime.utcnow()
        self.touch()


@dataclass
class ProjectSummary:
    """Lightweight summary for project list display."""

    id: str
    name: str
    description: str
    profile_id: str
    reversible_default: bool
    file_count: int
    mapping_count: int
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime | None

    @property
    def display_date(self) -> datetime:
        """Get the most relevant date for display (last opened or updated)."""
        return self.last_opened_at or self.updated_at


@dataclass
class ProjectCreateRequest:
    """Request data for creating a new project."""

    name: str
    description: str = ""
    profile_id: str = "standard_pii"
    reversible_default: bool = True
    remember_source_paths: bool = False
    retention_policy: RetentionPolicy = RetentionPolicy.UNTIL_DELETED


@dataclass
class ProjectUpdateRequest:
    """Request data for updating a project."""

    name: str | None = None
    description: str | None = None
    profile_id: str | None = None
    reversible_default: bool | None = None
    remember_source_paths: bool | None = None
    retention_policy: RetentionPolicy | None = None
    status: ProjectStatus | None = None
