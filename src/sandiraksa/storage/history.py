"""
Operation History.

Tracks operation history without storing raw content.
Generates summaries and provides audit trail.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from sandiraksa.storage.database import Database

logger = logging.getLogger(__name__)


class HistoryEventType(str, Enum):
    """Types of history events."""

    # Project events
    PROJECT_CREATED = "project_created"
    PROJECT_OPENED = "project_opened"
    PROJECT_ARCHIVED = "project_archived"
    PROJECT_DELETED = "project_deleted"

    # File events
    FILE_ADDED = "file_added"
    FILE_REMOVED = "file_removed"
    FILE_SCANNED = "file_scanned"

    # Operation events
    SCAN_STARTED = "scan_started"
    SCAN_COMPLETED = "scan_completed"
    SCAN_FAILED = "scan_failed"

    PROTECTION_STARTED = "protection_started"
    PROTECTION_COMPLETED = "protection_completed"
    PROTECTION_FAILED = "protection_failed"

    RESTORE_STARTED = "restore_started"
    RESTORE_COMPLETED = "restore_completed"
    RESTORE_FAILED = "restore_failed"

    # Review events
    FINDINGS_REVIEWED = "findings_reviewed"
    TREATMENT_APPLIED = "treatment_applied"
    TREATMENT_CHANGED = "treatment_changed"

    # Export events
    FILE_EXPORTED = "file_exported"
    REPORT_GENERATED = "report_generated"


@dataclass
class HistoryEventData:
    """Data associated with a history event (no raw content)."""

    # File info (anonymized)
    file_count: int = 0
    file_format: str | None = None

    # Detection stats
    findings_count: int = 0
    entity_types_found: list[str] = field(default_factory=list)

    # Treatment stats
    tokens_generated: int = 0
    tokens_restored: int = 0

    # Timing
    duration_ms: float = 0.0

    # Errors (sanitized)
    error_type: str | None = None
    error_message: str | None = None

    # Extra metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "file_count": self.file_count,
            "file_format": self.file_format,
            "findings_count": self.findings_count,
            "entity_types_found": self.entity_types_found,
            "tokens_generated": self.tokens_generated,
            "tokens_restored": self.tokens_restored,
            "duration_ms": self.duration_ms,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryEventData:
        """Create from dictionary."""
        return cls(
            file_count=data.get("file_count", 0),
            file_format=data.get("file_format"),
            findings_count=data.get("findings_count", 0),
            entity_types_found=data.get("entity_types_found", []),
            tokens_generated=data.get("tokens_generated", 0),
            tokens_restored=data.get("tokens_restored", 0),
            duration_ms=data.get("duration_ms", 0.0),
            error_type=data.get("error_type"),
            error_message=data.get("error_message"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class HistoryEvent:
    """A single history event."""

    id: str
    project_id: str
    event_type: HistoryEventType
    timestamp: datetime
    data: HistoryEventData
    operation_id: str | None = None

    @classmethod
    def create(
        cls,
        project_id: str,
        event_type: HistoryEventType,
        data: HistoryEventData | None = None,
        operation_id: str | None = None,
    ) -> HistoryEvent:
        """Create a new history event."""
        return cls(
            id=str(uuid4()),
            project_id=project_id,
            event_type=event_type,
            timestamp=datetime.now(UTC),
            data=data or HistoryEventData(),
            operation_id=operation_id,
        )


@dataclass
class OperationSummary:
    """Summary of operations for a project."""

    project_id: str
    total_operations: int = 0
    total_files_processed: int = 0
    total_findings: int = 0
    total_tokens_generated: int = 0
    total_tokens_restored: int = 0

    # Counts by type
    scans_completed: int = 0
    scans_failed: int = 0
    protections_completed: int = 0
    protections_failed: int = 0
    restores_completed: int = 0
    restores_failed: int = 0

    # Timing
    total_processing_time_ms: float = 0.0

    # Entity type distribution
    entity_type_counts: dict[str, int] = field(default_factory=dict)

    # Date range
    first_operation: datetime | None = None
    last_operation: datetime | None = None


class OperationHistory:
    """
    Manages operation history tracking.

    Key principle: NO raw content is ever stored.
    Only metadata, counts, and anonymized statistics.
    """

    def __init__(self, db: Database) -> None:
        """
        Initialize operation history.

        Args:
            db: Database connection.
        """
        self._db = db
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensure history table exists."""
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS operation_history (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                operation_id TEXT,
                data_json TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
            """
        )
        self._db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_history_project 
            ON operation_history(project_id)
            """
        )
        self._db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_history_timestamp 
            ON operation_history(timestamp)
            """
        )

    def record_event(self, event: HistoryEvent) -> None:
        """
        Record a history event.

        Args:
            event: The event to record.
        """
        import json

        self._db.execute(
            """
            INSERT INTO operation_history 
            (id, project_id, event_type, timestamp, operation_id, data_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.project_id,
                event.event_type.value,
                event.timestamp.isoformat(),
                event.operation_id,
                json.dumps(event.data.to_dict()),
            ),
        )
        logger.debug(f"Recorded history event: {event.event_type.value}")

    def record(
        self,
        project_id: str,
        event_type: HistoryEventType,
        data: HistoryEventData | None = None,
        operation_id: str | None = None,
    ) -> HistoryEvent:
        """
        Create and record a history event.

        Args:
            project_id: Project ID.
            event_type: Type of event.
            data: Event data.
            operation_id: Associated operation ID.

        Returns:
            The created event.
        """
        event = HistoryEvent.create(
            project_id=project_id,
            event_type=event_type,
            data=data,
            operation_id=operation_id,
        )
        self.record_event(event)
        return event

    def get_events(
        self,
        project_id: str,
        event_types: list[HistoryEventType] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[HistoryEvent]:
        """
        Get history events for a project.

        Args:
            project_id: Project ID.
            event_types: Filter by event types.
            since: Filter events after this time.
            until: Filter events before this time.
            limit: Maximum events to return.

        Returns:
            List of events.
        """
        import json

        query = "SELECT * FROM operation_history WHERE project_id = ?"
        params: list[Any] = [project_id]

        if event_types:
            placeholders = ",".join("?" * len(event_types))
            query += f" AND event_type IN ({placeholders})"
            params.extend(et.value for et in event_types)

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        if until:
            query += " AND timestamp <= ?"
            params.append(until.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self._db.fetch_all(query, tuple(params))
        events = []

        for row in rows:
            data = HistoryEventData.from_dict(json.loads(row["data_json"]))
            events.append(
                HistoryEvent(
                    id=row["id"],
                    project_id=row["project_id"],
                    event_type=HistoryEventType(row["event_type"]),
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    data=data,
                    operation_id=row["operation_id"],
                )
            )

        return events

    def get_summary(self, project_id: str) -> OperationSummary:
        """
        Get operation summary for a project.

        Args:
            project_id: Project ID.

        Returns:
            Summary statistics.
        """
        import json

        summary = OperationSummary(project_id=project_id)

        # Get all events for project
        rows = self._db.fetch_all(
            """
            SELECT event_type, data_json, timestamp 
            FROM operation_history 
            WHERE project_id = ?
            ORDER BY timestamp ASC
            """,
            (project_id,),
        )

        if not rows:
            return summary

        for row in rows:
            event_type = row["event_type"]
            data = HistoryEventData.from_dict(json.loads(row["data_json"]))
            timestamp = datetime.fromisoformat(row["timestamp"])

            summary.total_operations += 1

            # Track date range
            if summary.first_operation is None:
                summary.first_operation = timestamp
            summary.last_operation = timestamp

            # Aggregate stats
            summary.total_files_processed += data.file_count
            summary.total_findings += data.findings_count
            summary.total_tokens_generated += data.tokens_generated
            summary.total_tokens_restored += data.tokens_restored
            summary.total_processing_time_ms += data.duration_ms

            # Count entity types
            for entity_type in data.entity_types_found:
                summary.entity_type_counts[entity_type] = (
                    summary.entity_type_counts.get(entity_type, 0) + 1
                )

            # Count by operation type
            if event_type == HistoryEventType.SCAN_COMPLETED.value:
                summary.scans_completed += 1
            elif event_type == HistoryEventType.SCAN_FAILED.value:
                summary.scans_failed += 1
            elif event_type == HistoryEventType.PROTECTION_COMPLETED.value:
                summary.protections_completed += 1
            elif event_type == HistoryEventType.PROTECTION_FAILED.value:
                summary.protections_failed += 1
            elif event_type == HistoryEventType.RESTORE_COMPLETED.value:
                summary.restores_completed += 1
            elif event_type == HistoryEventType.RESTORE_FAILED.value:
                summary.restores_failed += 1

        return summary

    def generate_report(
        self,
        project_id: str,
        include_events: bool = False,
    ) -> dict[str, Any]:
        """
        Generate a history report for a project.

        Args:
            project_id: Project ID.
            include_events: Include individual events.

        Returns:
            Report dictionary.
        """
        summary = self.get_summary(project_id)

        report = {
            "project_id": project_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {
                "total_operations": summary.total_operations,
                "total_files_processed": summary.total_files_processed,
                "total_findings": summary.total_findings,
                "total_tokens_generated": summary.total_tokens_generated,
                "total_tokens_restored": summary.total_tokens_restored,
                "total_processing_time_seconds": summary.total_processing_time_ms
                / 1000,
                "operations": {
                    "scans": {
                        "completed": summary.scans_completed,
                        "failed": summary.scans_failed,
                    },
                    "protections": {
                        "completed": summary.protections_completed,
                        "failed": summary.protections_failed,
                    },
                    "restores": {
                        "completed": summary.restores_completed,
                        "failed": summary.restores_failed,
                    },
                },
                "entity_type_distribution": summary.entity_type_counts,
                "date_range": {
                    "first": (
                        summary.first_operation.isoformat()
                        if summary.first_operation
                        else None
                    ),
                    "last": (
                        summary.last_operation.isoformat()
                        if summary.last_operation
                        else None
                    ),
                },
            },
        }

        if include_events:
            events = self.get_events(project_id, limit=1000)
            report["events"] = [
                {
                    "id": e.id,
                    "type": e.event_type.value,
                    "timestamp": e.timestamp.isoformat(),
                    "operation_id": e.operation_id,
                    "data": e.data.to_dict(),
                }
                for e in events
            ]

        return report

    def delete_project_history(self, project_id: str) -> int:
        """
        Delete all history for a project.

        Args:
            project_id: Project ID.

        Returns:
            Number of events deleted.
        """
        # Count first
        row = self._db.fetch_one(
            "SELECT COUNT(*) as count FROM operation_history WHERE project_id = ?",
            (project_id,),
        )
        count = row["count"] if row else 0

        # Delete
        self._db.execute(
            "DELETE FROM operation_history WHERE project_id = ?",
            (project_id,),
        )

        logger.info(f"Deleted {count} history events for project {project_id}")
        return count

    def cleanup_old_events(self, days: int = 90) -> int:
        """
        Remove history events older than specified days.

        Args:
            days: Number of days to keep.

        Returns:
            Number of events deleted.
        """
        from datetime import timedelta

        cutoff = datetime.now(UTC) - timedelta(days=days)

        # Count first
        row = self._db.fetch_one(
            "SELECT COUNT(*) as count FROM operation_history WHERE timestamp < ?",
            (cutoff.isoformat(),),
        )
        count = row["count"] if row else 0

        # Delete
        self._db.execute(
            "DELETE FROM operation_history WHERE timestamp < ?",
            (cutoff.isoformat(),),
        )

        logger.info(f"Cleaned up {count} history events older than {days} days")
        return count
