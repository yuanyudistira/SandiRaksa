"""
Repository pattern implementations for data access.

This module provides type-safe repository classes for each entity type,
abstracting database operations from business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Generic, TypeVar
from uuid import UUID, uuid4

from sandiraksa.storage.database import Database, get_database, utc_now_iso

if TYPE_CHECKING:
    from sqlite3 import Row


T = TypeVar("T")


class RepositoryError(Exception):
    """Base exception for repository operations."""

    pass


class NotFoundError(RepositoryError):
    """Entity not found in repository."""

    pass


class DuplicateError(RepositoryError):
    """Duplicate entity or constraint violation."""

    pass


@dataclass
class ProjectRecord:
    """Database record for a project."""

    id: str
    name_enc: bytes
    description_enc: bytes | None
    profile_id: str
    settings_enc: bytes | None
    reversible_default: bool
    remember_source_paths: bool
    retention_policy: str
    created_at: str
    updated_at: str
    last_opened_at: str | None
    schema_version: int

    @classmethod
    def from_row(cls, row: Row) -> ProjectRecord:
        """Create ProjectRecord from database row."""
        # Handle settings_enc which may not exist in old databases
        settings_enc = None
        try:
            settings_enc = row["settings_enc"]
        except (KeyError, IndexError):
            pass
        
        return cls(
            id=row["id"],
            name_enc=row["name_enc"],
            description_enc=row["description_enc"],
            profile_id=row["profile_id"],
            settings_enc=settings_enc,
            reversible_default=bool(row["reversible_default"]),
            remember_source_paths=bool(row["remember_source_paths"]),
            retention_policy=row["retention_policy"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_opened_at=row["last_opened_at"],
            schema_version=row["schema_version"],
        )


@dataclass
class FileRecord:
    """Database record for a file."""

    id: str
    project_id: str
    filename_enc: bytes
    source_path_enc: bytes | None
    extension: str
    file_size: int | None
    source_sha256: str | None
    latest_output_sha256: str | None
    metadata_enc: bytes | None
    added_at: str
    last_processed_at: str | None
    status: str

    @classmethod
    def from_row(cls, row: Row) -> FileRecord:
        """Create FileRecord from database row."""
        # Handle metadata_enc which may not exist in old databases
        metadata_enc = None
        try:
            metadata_enc = row["metadata_enc"]
        except (KeyError, IndexError):
            pass
        
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            filename_enc=row["filename_enc"],
            source_path_enc=row["source_path_enc"],
            extension=row["extension"],
            file_size=row["file_size"],
            source_sha256=row["source_sha256"],
            latest_output_sha256=row["latest_output_sha256"],
            metadata_enc=metadata_enc,
            added_at=row["added_at"],
            last_processed_at=row["last_processed_at"],
            status=row["status"],
        )


@dataclass
class OperationRecord:
    """Database record for an operation."""

    id: str
    project_id: str
    file_id: str | None
    operation_type: str
    reversible: bool
    profile_id: str | None
    app_version: str
    started_at: str
    completed_at: str | None
    status: str
    findings_total: int
    treated_total: int
    ignored_total: int
    residual_total: int
    warnings_json: str | None
    source_sha256: str | None
    output_sha256: str | None

    @classmethod
    def from_row(cls, row: Row) -> OperationRecord:
        """Create OperationRecord from database row."""
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            file_id=row["file_id"],
            operation_type=row["operation_type"],
            reversible=bool(row["reversible"]),
            profile_id=row["profile_id"],
            app_version=row["app_version"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            status=row["status"],
            findings_total=row["findings_total"],
            treated_total=row["treated_total"],
            ignored_total=row["ignored_total"],
            residual_total=row["residual_total"],
            warnings_json=row["warnings_json"],
            source_sha256=row["source_sha256"],
            output_sha256=row["output_sha256"],
        )


@dataclass
class CustomRuleRecord:
    """Database record for a custom rule."""

    id: str
    project_id: str
    rule_type: str
    entity_type: str
    pattern_enc: bytes
    case_sensitive: bool
    treatment: str
    enabled: bool
    created_at: str

    @classmethod
    def from_row(cls, row: Row) -> CustomRuleRecord:
        """Create CustomRuleRecord from database row."""
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            rule_type=row["rule_type"],
            entity_type=row["entity_type"],
            pattern_enc=row["pattern_enc"],
            case_sensitive=bool(row["case_sensitive"]),
            treatment=row["treatment"],
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
        )


@dataclass
class TokenMappingRecord:
    """Database record for a token mapping."""

    id: str
    project_id: str
    token: str
    entity_type: str
    normalized_hmac: str
    original_value_enc: bytes
    created_at: str
    last_used_at: str
    expires_at: str | None

    @classmethod
    def from_row(cls, row: Row) -> TokenMappingRecord:
        """Create TokenMappingRecord from database row."""
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            token=row["token"],
            entity_type=row["entity_type"],
            normalized_hmac=row["normalized_hmac"],
            original_value_enc=row["original_value_enc"],
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
            expires_at=row["expires_at"],
        )


class ProjectRepository:
    """Repository for project data operations."""

    def __init__(self, db: Database | None = None) -> None:
        self._db = db or get_database()

    def create(
        self,
        name_enc: bytes,
        profile_id: str,
        *,
        description_enc: bytes | None = None,
        reversible_default: bool = True,
        remember_source_paths: bool = False,
        retention_policy: str = "until_deleted",
    ) -> ProjectRecord:
        """Create a new project."""
        project_id = str(uuid4())
        return self.create_with_id(
            project_id=project_id,
            name_enc=name_enc,
            profile_id=profile_id,
            description_enc=description_enc,
            reversible_default=reversible_default,
            remember_source_paths=remember_source_paths,
            retention_policy=retention_policy,
        )

    def create_with_id(
        self,
        project_id: str,
        name_enc: bytes,
        profile_id: str,
        *,
        description_enc: bytes | None = None,
        settings_enc: bytes | None = None,
        reversible_default: bool = True,
        remember_source_paths: bool = False,
        retention_policy: str = "until_deleted",
    ) -> ProjectRecord:
        """Create a new project with a specified ID."""
        now = utc_now_iso()

        with self._db.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO projects (
                    id, name_enc, description_enc, profile_id, settings_enc,
                    reversible_default, remember_source_paths,
                    retention_policy, created_at, updated_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    name_enc,
                    description_enc,
                    profile_id,
                    settings_enc,
                    int(reversible_default),
                    int(remember_source_paths),
                    retention_policy,
                    now,
                    now,
                    1,
                ),
            )

        return self.get_by_id(project_id)

    def get_by_id(self, project_id: str) -> ProjectRecord:
        """Get a project by ID."""
        cursor = self._db.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        )
        row = cursor.fetchone()
        if row is None:
            raise NotFoundError(f"Project not found: {project_id}")
        return ProjectRecord.from_row(row)

    def get_all(self) -> list[ProjectRecord]:
        """Get all projects, ordered by last opened/updated."""
        cursor = self._db.execute(
            """
            SELECT * FROM projects 
            ORDER BY COALESCE(last_opened_at, updated_at) DESC
            """
        )
        return [ProjectRecord.from_row(row) for row in cursor.fetchall()]

    def update(self, project_id: str, **kwargs: Any) -> ProjectRecord:
        """Update project fields."""
        allowed_fields = {
            "name_enc",
            "description_enc",
            "settings_enc",
            "profile_id",
            "reversible_default",
            "remember_source_paths",
            "retention_policy",
            "last_opened_at",
        }

        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return self.get_by_id(project_id)

        updates["updated_at"] = utc_now_iso()

        # Convert bool to int for SQLite
        for key in ["reversible_default", "remember_source_paths"]:
            if key in updates:
                updates[key] = int(updates[key])

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [project_id]

        with self._db.transaction() as cursor:
            cursor.execute(
                f"UPDATE projects SET {set_clause} WHERE id = ?",
                tuple(values),
            )
            if cursor.rowcount == 0:
                raise NotFoundError(f"Project not found: {project_id}")

        return self.get_by_id(project_id)

    def update_last_opened(self, project_id: str) -> None:
        """Update the last opened timestamp."""
        now = utc_now_iso()
        self._db.execute(
            "UPDATE projects SET last_opened_at = ?, updated_at = ? WHERE id = ?",
            (now, now, project_id),
        )

    def delete(self, project_id: str) -> None:
        """Delete a project (cascades to related records)."""
        with self._db.transaction() as cursor:
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            if cursor.rowcount == 0:
                raise NotFoundError(f"Project not found: {project_id}")

    def count(self) -> int:
        """Get total project count."""
        cursor = self._db.execute("SELECT COUNT(*) FROM projects")
        return cursor.fetchone()[0]


class FileRepository:
    """Repository for file data operations."""

    def __init__(self, db: Database | None = None) -> None:
        self._db = db or get_database()

    def create(
        self,
        project_id: str,
        filename_enc: bytes,
        extension: str,
        *,
        source_path_enc: bytes | None = None,
        file_size: int | None = None,
        source_sha256: str | None = None,
        metadata_enc: bytes | None = None,
    ) -> FileRecord:
        """Create a new file record."""
        file_id = str(uuid4())
        now = utc_now_iso()

        with self._db.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO files (
                    id, project_id, filename_enc, source_path_enc,
                    extension, file_size, source_sha256, metadata_enc, added_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    project_id,
                    filename_enc,
                    source_path_enc,
                    extension,
                    file_size,
                    source_sha256,
                    metadata_enc,
                    now,
                    "pending",
                ),
            )

        return self.get_by_id(file_id)

    def get_by_id(self, file_id: str) -> FileRecord:
        """Get a file by ID."""
        cursor = self._db.execute("SELECT * FROM files WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        if row is None:
            raise NotFoundError(f"File not found: {file_id}")
        return FileRecord.from_row(row)

    def get_by_project(self, project_id: str) -> list[FileRecord]:
        """Get all files for a project."""
        cursor = self._db.execute(
            "SELECT * FROM files WHERE project_id = ? ORDER BY added_at DESC",
            (project_id,),
        )
        return [FileRecord.from_row(row) for row in cursor.fetchall()]

    def update(self, file_id: str, **kwargs: Any) -> FileRecord:
        """Update file fields."""
        allowed_fields = {
            "status",
            "latest_output_sha256",
            "last_processed_at",
            "metadata_enc",
        }

        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return self.get_by_id(file_id)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [file_id]

        with self._db.transaction() as cursor:
            cursor.execute(
                f"UPDATE files SET {set_clause} WHERE id = ?",
                tuple(values),
            )

        return self.get_by_id(file_id)

    def delete(self, file_id: str) -> None:
        """Delete a file record."""
        with self._db.transaction() as cursor:
            cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))

    def count_by_project(self, project_id: str) -> int:
        """Get file count for a project."""
        cursor = self._db.execute(
            "SELECT COUNT(*) FROM files WHERE project_id = ?",
            (project_id,),
        )
        return cursor.fetchone()[0]


class OperationRepository:
    """Repository for operation data."""

    def __init__(self, db: Database | None = None) -> None:
        self._db = db or get_database()

    def create(
        self,
        project_id: str,
        operation_type: str,
        app_version: str,
        reversible: bool,
        *,
        file_id: str | None = None,
        profile_id: str | None = None,
        source_sha256: str | None = None,
    ) -> OperationRecord:
        """Create a new operation record."""
        operation_id = str(uuid4())
        now = utc_now_iso()

        with self._db.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO operations (
                    id, project_id, file_id, operation_type,
                    reversible, profile_id, app_version,
                    started_at, status, source_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation_id,
                    project_id,
                    file_id,
                    operation_type,
                    int(reversible),
                    profile_id,
                    app_version,
                    now,
                    "processing",
                    source_sha256,
                ),
            )

        return self.get_by_id(operation_id)

    def get_by_id(self, operation_id: str) -> OperationRecord:
        """Get an operation by ID."""
        cursor = self._db.execute(
            "SELECT * FROM operations WHERE id = ?", (operation_id,)
        )
        row = cursor.fetchone()
        if row is None:
            raise NotFoundError(f"Operation not found: {operation_id}")
        return OperationRecord.from_row(row)

    def get_by_project(
        self, project_id: str, limit: int = 100
    ) -> list[OperationRecord]:
        """Get operations for a project."""
        cursor = self._db.execute(
            """
            SELECT * FROM operations 
            WHERE project_id = ? 
            ORDER BY started_at DESC 
            LIMIT ?
            """,
            (project_id, limit),
        )
        return [OperationRecord.from_row(row) for row in cursor.fetchall()]

    def complete(
        self,
        operation_id: str,
        status: str,
        *,
        findings_total: int = 0,
        treated_total: int = 0,
        ignored_total: int = 0,
        residual_total: int = 0,
        warnings_json: str | None = None,
        output_sha256: str | None = None,
    ) -> OperationRecord:
        """Mark an operation as complete."""
        now = utc_now_iso()

        with self._db.transaction() as cursor:
            cursor.execute(
                """
                UPDATE operations SET
                    status = ?,
                    completed_at = ?,
                    findings_total = ?,
                    treated_total = ?,
                    ignored_total = ?,
                    residual_total = ?,
                    warnings_json = ?,
                    output_sha256 = ?
                WHERE id = ?
                """,
                (
                    status,
                    now,
                    findings_total,
                    treated_total,
                    ignored_total,
                    residual_total,
                    warnings_json,
                    output_sha256,
                    operation_id,
                ),
            )

        return self.get_by_id(operation_id)


class CustomRuleRepository:
    """Repository for custom rules."""

    def __init__(self, db: Database | None = None) -> None:
        self._db = db or get_database()

    def create(
        self,
        project_id: str,
        rule_type: str,
        entity_type: str,
        pattern_enc: bytes,
        *,
        case_sensitive: bool = False,
        treatment: str = "token",
    ) -> CustomRuleRecord:
        """Create a new custom rule."""
        rule_id = str(uuid4())
        now = utc_now_iso()

        with self._db.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO custom_rules (
                    id, project_id, rule_type, entity_type,
                    pattern_enc, case_sensitive, treatment, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule_id,
                    project_id,
                    rule_type,
                    entity_type,
                    pattern_enc,
                    int(case_sensitive),
                    treatment,
                    now,
                ),
            )

        return self.get_by_id(rule_id)

    def get_by_id(self, rule_id: str) -> CustomRuleRecord:
        """Get a rule by ID."""
        cursor = self._db.execute(
            "SELECT * FROM custom_rules WHERE id = ?", (rule_id,)
        )
        row = cursor.fetchone()
        if row is None:
            raise NotFoundError(f"Rule not found: {rule_id}")
        return CustomRuleRecord.from_row(row)

    def get_by_project(
        self, project_id: str, *, enabled_only: bool = True
    ) -> list[CustomRuleRecord]:
        """Get rules for a project."""
        if enabled_only:
            cursor = self._db.execute(
                """
                SELECT * FROM custom_rules 
                WHERE project_id = ? AND enabled = 1
                ORDER BY created_at
                """,
                (project_id,),
            )
        else:
            cursor = self._db.execute(
                "SELECT * FROM custom_rules WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            )
        return [CustomRuleRecord.from_row(row) for row in cursor.fetchall()]

    def update_enabled(self, rule_id: str, enabled: bool) -> None:
        """Enable or disable a rule."""
        self._db.execute(
            "UPDATE custom_rules SET enabled = ? WHERE id = ?",
            (int(enabled), rule_id),
        )

    def delete(self, rule_id: str) -> None:
        """Delete a rule."""
        self._db.execute("DELETE FROM custom_rules WHERE id = ?", (rule_id,))


class TokenMappingRepository:
    """Repository for token mappings."""

    def __init__(self, db: Database | None = None) -> None:
        self._db = db or get_database()

    def create(
        self,
        project_id: str,
        token: str,
        entity_type: str,
        normalized_hmac: str,
        original_value_enc: bytes,
        *,
        expires_at: str | None = None,
    ) -> TokenMappingRecord:
        """Create a new token mapping."""
        mapping_id = str(uuid4())
        now = utc_now_iso()

        with self._db.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO token_mappings (
                    id, project_id, token, entity_type,
                    normalized_hmac, original_value_enc,
                    created_at, last_used_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mapping_id,
                    project_id,
                    token,
                    entity_type,
                    normalized_hmac,
                    original_value_enc,
                    now,
                    now,
                    expires_at,
                ),
            )

        return self.get_by_id(mapping_id)

    def get_by_id(self, mapping_id: str) -> TokenMappingRecord:
        """Get a mapping by ID."""
        cursor = self._db.execute(
            "SELECT * FROM token_mappings WHERE id = ?", (mapping_id,)
        )
        row = cursor.fetchone()
        if row is None:
            raise NotFoundError(f"Mapping not found: {mapping_id}")
        return TokenMappingRecord.from_row(row)

    def find_by_hmac(
        self, project_id: str, entity_type: str, normalized_hmac: str
    ) -> TokenMappingRecord | None:
        """Find mapping by normalized HMAC (for reuse check)."""
        cursor = self._db.execute(
            """
            SELECT * FROM token_mappings 
            WHERE project_id = ? AND entity_type = ? AND normalized_hmac = ?
            """,
            (project_id, entity_type, normalized_hmac),
        )
        row = cursor.fetchone()
        return TokenMappingRecord.from_row(row) if row else None

    def find_by_token(
        self, project_id: str, token: str
    ) -> TokenMappingRecord | None:
        """Find mapping by token (for restoration)."""
        cursor = self._db.execute(
            "SELECT * FROM token_mappings WHERE project_id = ? AND token = ?",
            (project_id, token),
        )
        row = cursor.fetchone()
        return TokenMappingRecord.from_row(row) if row else None

    def get_by_project(self, project_id: str) -> list[TokenMappingRecord]:
        """Get all mappings for a project."""
        cursor = self._db.execute(
            "SELECT * FROM token_mappings WHERE project_id = ? ORDER BY created_at",
            (project_id,),
        )
        return [TokenMappingRecord.from_row(row) for row in cursor.fetchall()]

    def update_last_used(self, mapping_id: str) -> None:
        """Update the last used timestamp."""
        now = utc_now_iso()
        self._db.execute(
            "UPDATE token_mappings SET last_used_at = ? WHERE id = ?",
            (now, mapping_id),
        )

    def delete_expired(self) -> int:
        """Delete all expired mappings. Returns count deleted."""
        now = utc_now_iso()
        with self._db.transaction() as cursor:
            cursor.execute(
                """
                DELETE FROM token_mappings 
                WHERE expires_at IS NOT NULL AND expires_at < ?
                """,
                (now,),
            )
            return cursor.rowcount

    def delete_by_project(self, project_id: str) -> int:
        """Delete all mappings for a project. Returns count deleted."""
        with self._db.transaction() as cursor:
            cursor.execute(
                "DELETE FROM token_mappings WHERE project_id = ?",
                (project_id,),
            )
            return cursor.rowcount

    def count_by_project(self, project_id: str) -> int:
        """Get mapping count for a project."""
        cursor = self._db.execute(
            "SELECT COUNT(*) FROM token_mappings WHERE project_id = ?",
            (project_id,),
        )
        return cursor.fetchone()[0]

    def token_exists(self, project_id: str, token: str) -> bool:
        """Check if a token already exists (for collision detection)."""
        cursor = self._db.execute(
            "SELECT 1 FROM token_mappings WHERE project_id = ? AND token = ?",
            (project_id, token),
        )
        return cursor.fetchone() is not None
