"""Tests for database module."""

import tempfile
from pathlib import Path

import pytest

from sandiraksa.storage.database import (
    Database,
    SCHEMA_VERSION,
    utc_now_iso,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        db.initialize()
        yield db
        db.close()


class TestDatabase:
    """Tests for Database class."""

    def test_create_database(self):
        """Database should be created and initialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            db.initialize()

            assert db_path.exists()
            assert db.get_schema_version() == SCHEMA_VERSION

            db.close()

    def test_tables_created(self, temp_db: Database):
        """All required tables should be created."""
        required_tables = [
            "projects",
            "files",
            "operations",
            "custom_rules",
            "token_mappings",
        ]

        for table in required_tables:
            assert temp_db.table_exists(table), f"Table {table} not found"

    def test_foreign_keys_enabled(self, temp_db: Database):
        """Foreign keys should be enabled."""
        cursor = temp_db.execute("PRAGMA foreign_keys")
        row = cursor.fetchone()
        assert row[0] == 1

    def test_wal_mode_enabled(self, temp_db: Database):
        """WAL journal mode should be enabled."""
        cursor = temp_db.execute("PRAGMA journal_mode")
        row = cursor.fetchone()
        assert row[0].upper() == "WAL"

    def test_transaction_commit(self, temp_db: Database):
        """Transaction should commit changes."""
        with temp_db.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO projects (
                    id, name_enc, profile_id, reversible_default,
                    retention_policy, created_at, updated_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("test-id", b"encrypted", "standard_pii", 1,
                 "until_deleted", "2024-01-01", "2024-01-01", 1),
            )

        # Should persist after transaction
        cursor = temp_db.execute("SELECT * FROM projects WHERE id = ?", ("test-id",))
        row = cursor.fetchone()
        assert row is not None
        assert row["id"] == "test-id"

    def test_transaction_rollback(self, temp_db: Database):
        """Transaction should rollback on error."""
        try:
            with temp_db.transaction() as cursor:
                cursor.execute(
                    """
                    INSERT INTO projects (
                        id, name_enc, profile_id, reversible_default,
                        retention_policy, created_at, updated_at, schema_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("rollback-id", b"encrypted", "standard_pii", 1,
                     "until_deleted", "2024-01-01", "2024-01-01", 1),
                )
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should not persist after rollback
        cursor = temp_db.execute(
            "SELECT * FROM projects WHERE id = ?", ("rollback-id",)
        )
        row = cursor.fetchone()
        assert row is None

    def test_backup(self, temp_db: Database):
        """Database backup should work."""
        # Insert some data
        with temp_db.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO projects (
                    id, name_enc, profile_id, reversible_default,
                    retention_policy, created_at, updated_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("backup-test", b"encrypted", "standard_pii", 1,
                 "until_deleted", "2024-01-01", "2024-01-01", 1),
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            backup_path = Path(tmpdir) / "backup.db"
            temp_db.backup(backup_path)

            # Verify backup
            backup_db = Database(backup_path)
            cursor = backup_db.execute(
                "SELECT * FROM projects WHERE id = ?", ("backup-test",)
            )
            row = cursor.fetchone()
            assert row is not None
            backup_db.close()

    def test_schema_version_persistence(self, temp_db: Database):
        """Schema version should persist."""
        version = temp_db.get_schema_version()
        assert version == SCHEMA_VERSION

        # Close and reopen
        temp_db.close()
        temp_db2 = Database(temp_db.path)
        assert temp_db2.get_schema_version() == SCHEMA_VERSION
        temp_db2.close()


class TestUtcNowIso:
    """Tests for utc_now_iso function."""

    def test_format(self):
        """Should return ISO format with Z suffix."""
        result = utc_now_iso()
        assert result.endswith("Z")
        assert "T" in result

    def test_parseable(self):
        """Should be parseable as datetime."""
        from datetime import datetime

        result = utc_now_iso()
        # Remove Z suffix for parsing
        parsed = datetime.fromisoformat(result[:-1])
        assert parsed is not None
