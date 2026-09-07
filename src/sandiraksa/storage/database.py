"""
SQLite database management for SandiRaksa.

This module provides database connection management, schema initialization,
and migration support with proper security settings.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator

from sandiraksa.config import get_app_paths

if TYPE_CHECKING:
    from sqlite3 import Connection, Cursor

# Current schema version
SCHEMA_VERSION = 1


class DatabaseError(Exception):
    """Base exception for database errors."""

    pass


class MigrationError(DatabaseError):
    """Exception for migration failures."""

    pass


class Database:
    """SQLite database manager with migration support."""

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Initialize database manager.

        Args:
            db_path: Path to database file. If None, uses default from AppPaths.
        """
        self._db_path = db_path or get_app_paths().database_path
        self._connection: Connection | None = None

    @property
    def path(self) -> Path:
        """Get the database file path."""
        return self._db_path

    def _configure_connection(self, conn: Connection) -> None:
        """Apply security and performance settings to connection."""
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
        conn.execute("PRAGMA temp_store = MEMORY")
        # Security: prevent loading extensions
        conn.execute("PRAGMA trusted_schema = OFF")

    def connect(self) -> Connection:
        """
        Get or create database connection.

        Returns:
            SQLite connection object.
        """
        if self._connection is None:
            # Ensure parent directory exists
            self._db_path.parent.mkdir(parents=True, exist_ok=True)

            self._connection = sqlite3.connect(
                str(self._db_path),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                isolation_level=None,  # Autocommit mode, we manage transactions
            )
            self._connection.row_factory = sqlite3.Row
            self._configure_connection(self._connection)

        return self._connection

    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @contextmanager
    def transaction(self) -> Generator[Cursor, None, None]:
        """
        Context manager for database transactions.

        Yields:
            Database cursor.
        """
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN")
            yield cursor
            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            raise
        finally:
            cursor.close()

    @contextmanager
    def cursor(self) -> Generator[Cursor, None, None]:
        """
        Context manager for a simple cursor (no transaction management).

        Yields:
            Database cursor.
        """
        conn = self.connect()
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Cursor:
        """
        Execute a SQL statement.

        Args:
            sql: SQL statement.
            params: Query parameters.

        Returns:
            Cursor with results.
        """
        conn = self.connect()
        return conn.execute(sql, params)

    def executemany(self, sql: str, params_list: list[tuple[Any, ...]]) -> Cursor:
        """
        Execute a SQL statement with multiple parameter sets.

        Args:
            sql: SQL statement.
            params_list: List of parameter tuples.

        Returns:
            Cursor with results.
        """
        conn = self.connect()
        return conn.executemany(sql, params_list)

    def get_schema_version(self) -> int:
        """
        Get the current schema version.

        Returns:
            Schema version number, or 0 if not initialized.
        """
        try:
            cursor = self.execute("PRAGMA user_version")
            row = cursor.fetchone()
            return row[0] if row else 0
        except sqlite3.Error:
            return 0

    def set_schema_version(self, version: int) -> None:
        """Set the schema version."""
        self.execute(f"PRAGMA user_version = {version}")

    def initialize(self) -> None:
        """
        Initialize the database schema.

        Creates all required tables if they don't exist and runs migrations.
        """
        current_version = self.get_schema_version()

        if current_version == 0:
            # Fresh database, create schema
            self._create_schema()
            self.set_schema_version(SCHEMA_VERSION)
        elif current_version < SCHEMA_VERSION:
            # Run migrations
            self._run_migrations(current_version, SCHEMA_VERSION)
            self.set_schema_version(SCHEMA_VERSION)

    def _create_schema(self) -> None:
        """Create the initial database schema."""
        with self.transaction() as cursor:
            # Projects table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name_enc BLOB NOT NULL,
                    description_enc BLOB,
                    profile_id TEXT NOT NULL,
                    settings_enc BLOB,
                    reversible_default INTEGER NOT NULL DEFAULT 1,
                    remember_source_paths INTEGER NOT NULL DEFAULT 0,
                    retention_policy TEXT NOT NULL DEFAULT 'until_deleted',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_opened_at TEXT,
                    schema_version INTEGER NOT NULL DEFAULT 1
                )
            """)

            # Files table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    filename_enc BLOB NOT NULL,
                    source_path_enc BLOB,
                    extension TEXT NOT NULL,
                    file_size INTEGER,
                    source_sha256 TEXT,
                    latest_output_sha256 TEXT,
                    metadata_enc BLOB,
                    added_at TEXT NOT NULL,
                    last_processed_at TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)

            # Operations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    file_id TEXT,
                    operation_type TEXT NOT NULL,
                    reversible INTEGER NOT NULL,
                    profile_id TEXT,
                    app_version TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    findings_total INTEGER NOT NULL DEFAULT 0,
                    treated_total INTEGER NOT NULL DEFAULT 0,
                    ignored_total INTEGER NOT NULL DEFAULT 0,
                    residual_total INTEGER NOT NULL DEFAULT 0,
                    warnings_json TEXT,
                    source_sha256 TEXT,
                    output_sha256 TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE SET NULL
                )
            """)

            # Custom rules table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS custom_rules (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    rule_type TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    pattern_enc BLOB NOT NULL,
                    case_sensitive INTEGER NOT NULL DEFAULT 0,
                    treatment TEXT NOT NULL DEFAULT 'token',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)

            # Token mappings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS token_mappings (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    token TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    normalized_hmac TEXT NOT NULL,
                    original_value_enc BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT NOT NULL,
                    expires_at TEXT,
                    UNIQUE(project_id, token),
                    UNIQUE(project_id, entity_type, normalized_hmac),
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)

            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_files_project 
                ON files(project_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_operations_project 
                ON operations(project_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_operations_file 
                ON operations(file_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_custom_rules_project 
                ON custom_rules(project_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_mappings_project 
                ON token_mappings(project_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_mappings_lookup 
                ON token_mappings(project_id, entity_type, normalized_hmac)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_mappings_token 
                ON token_mappings(project_id, token)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_mappings_expires 
                ON token_mappings(expires_at)
                WHERE expires_at IS NOT NULL
            """)

    def _run_migrations(self, from_version: int, to_version: int) -> None:
        """
        Run database migrations.

        Args:
            from_version: Current schema version.
            to_version: Target schema version.
        """
        # Migrations will be added as schema evolves
        # Each migration should be idempotent where possible

        for version in range(from_version + 1, to_version + 1):
            migration_name = f"_migrate_to_v{version}"
            migration_fn = getattr(self, migration_name, None)

            if migration_fn is not None:
                try:
                    migration_fn()
                except Exception as e:
                    raise MigrationError(
                        f"Migration to v{version} failed: {e}"
                    ) from e

    def vacuum(self) -> None:
        """Run VACUUM to optimize database."""
        self.execute("VACUUM")

    def backup(self, backup_path: Path) -> None:
        """
        Create a backup of the database.

        Args:
            backup_path: Path for the backup file.
        """
        conn = self.connect()
        backup_conn = sqlite3.connect(str(backup_path))
        try:
            conn.backup(backup_conn)
        finally:
            backup_conn.close()

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        cursor = self.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None

    def get_table_info(self, table_name: str) -> list[dict[str, Any]]:
        """Get column information for a table."""
        cursor = self.execute(f"PRAGMA table_info({table_name})")
        return [dict(row) for row in cursor.fetchall()]


# Module-level database instance
_database: Database | None = None


def get_database() -> Database:
    """Get the global database instance."""
    global _database
    if _database is None:
        _database = Database()
        _database.initialize()
    return _database


def reset_database() -> None:
    """Reset the global database instance (for testing)."""
    global _database
    if _database is not None:
        _database.close()
        _database = None


def utc_now_iso() -> str:
    """Get current UTC time as ISO string."""
    return datetime.utcnow().isoformat() + "Z"
