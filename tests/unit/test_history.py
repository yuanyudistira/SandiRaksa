"""Tests for operation history."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from sandiraksa.storage.history import (
    HistoryEvent,
    HistoryEventData,
    HistoryEventType,
    OperationHistory,
    OperationSummary,
)


class TestHistoryEventData:
    """Tests for HistoryEventData."""

    def test_to_dict(self):
        """Should serialize to dictionary."""
        data = HistoryEventData(
            file_count=5,
            file_format="csv",
            findings_count=10,
            entity_types_found=["PERSON", "EMAIL"],
            tokens_generated=8,
            duration_ms=1500.0,
        )

        result = data.to_dict()

        assert result["file_count"] == 5
        assert result["file_format"] == "csv"
        assert result["findings_count"] == 10
        assert result["entity_types_found"] == ["PERSON", "EMAIL"]
        assert result["tokens_generated"] == 8

    def test_from_dict(self):
        """Should deserialize from dictionary."""
        raw = {
            "file_count": 3,
            "file_format": "xlsx",
            "findings_count": 15,
            "entity_types_found": ["ID_NIK"],
            "tokens_generated": 12,
            "tokens_restored": 0,
            "duration_ms": 2000.0,
        }

        data = HistoryEventData.from_dict(raw)

        assert data.file_count == 3
        assert data.file_format == "xlsx"
        assert data.findings_count == 15
        assert data.tokens_generated == 12


class TestHistoryEvent:
    """Tests for HistoryEvent."""

    def test_create(self):
        """Should create event with generated ID."""
        event = HistoryEvent.create(
            project_id="proj-123",
            event_type=HistoryEventType.SCAN_COMPLETED,
            data=HistoryEventData(findings_count=5),
        )

        assert event.id is not None
        assert event.project_id == "proj-123"
        assert event.event_type == HistoryEventType.SCAN_COMPLETED
        assert event.timestamp is not None
        assert event.data.findings_count == 5


class TestOperationHistory:
    """Tests for OperationHistory."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = MagicMock()
        db.execute = MagicMock()
        db.fetch_all = MagicMock(return_value=[])
        db.fetch_one = MagicMock(return_value={"count": 0})
        return db

    @pytest.fixture
    def history(self, mock_db):
        """Create history instance with mock db."""
        return OperationHistory(mock_db)

    def test_record_event(self, history, mock_db):
        """Should record event to database."""
        event = HistoryEvent.create(
            project_id="proj-1",
            event_type=HistoryEventType.SCAN_STARTED,
        )

        history.record_event(event)

        # Verify insert was called
        assert mock_db.execute.called
        call_args = mock_db.execute.call_args
        assert "INSERT INTO operation_history" in call_args[0][0]

    def test_record_convenience(self, history, mock_db):
        """Should create and record event."""
        event = history.record(
            project_id="proj-2",
            event_type=HistoryEventType.PROTECTION_COMPLETED,
            data=HistoryEventData(tokens_generated=10),
        )

        assert event.project_id == "proj-2"
        assert event.event_type == HistoryEventType.PROTECTION_COMPLETED
        assert event.data.tokens_generated == 10

    def test_get_events_empty(self, history, mock_db):
        """Should return empty list when no events."""
        mock_db.fetch_all.return_value = []

        events = history.get_events("proj-1")

        assert events == []

    def test_get_events_with_data(self, history, mock_db):
        """Should parse events from database."""
        import json

        mock_db.fetch_all.return_value = [
            {
                "id": "evt-1",
                "project_id": "proj-1",
                "event_type": "scan_completed",
                "timestamp": "2024-01-15T10:30:00",
                "operation_id": "op-1",
                "data_json": json.dumps({"findings_count": 5}),
            }
        ]

        events = history.get_events("proj-1")

        assert len(events) == 1
        assert events[0].id == "evt-1"
        assert events[0].event_type == HistoryEventType.SCAN_COMPLETED
        assert events[0].data.findings_count == 5

    def test_get_summary_empty(self, history, mock_db):
        """Should return empty summary for new project."""
        mock_db.fetch_all.return_value = []

        summary = history.get_summary("proj-new")

        assert summary.total_operations == 0
        assert summary.total_findings == 0
        assert summary.first_operation is None

    def test_get_summary_aggregates(self, history, mock_db):
        """Should aggregate statistics."""
        import json

        mock_db.fetch_all.return_value = [
            {
                "event_type": "scan_completed",
                "data_json": json.dumps({
                    "findings_count": 10,
                    "entity_types_found": ["PERSON"],
                    "duration_ms": 1000,
                }),
                "timestamp": "2024-01-15T10:00:00",
            },
            {
                "event_type": "protection_completed",
                "data_json": json.dumps({
                    "tokens_generated": 8,
                    "duration_ms": 500,
                }),
                "timestamp": "2024-01-15T10:05:00",
            },
        ]

        summary = history.get_summary("proj-1")

        assert summary.total_operations == 2
        assert summary.total_findings == 10
        assert summary.total_tokens_generated == 8
        assert summary.scans_completed == 1
        assert summary.protections_completed == 1
        assert summary.total_processing_time_ms == 1500

    def test_generate_report(self, history, mock_db):
        """Should generate report dictionary."""
        mock_db.fetch_all.return_value = []

        report = history.generate_report("proj-1")

        assert "project_id" in report
        assert "generated_at" in report
        assert "summary" in report
        assert "total_operations" in report["summary"]

    def test_generate_report_with_events(self, history, mock_db):
        """Should include events in report when requested."""
        import json

        mock_db.fetch_all.return_value = [
            {
                "id": "evt-1",
                "project_id": "proj-1",
                "event_type": "file_added",
                "timestamp": "2024-01-15T10:00:00",
                "operation_id": None,
                "data_json": json.dumps({"file_count": 1}),
            }
        ]

        report = history.generate_report("proj-1", include_events=True)

        assert "events" in report
        assert len(report["events"]) == 1

    def test_delete_project_history(self, history, mock_db):
        """Should delete all events for project."""
        mock_db.fetch_one.return_value = {"count": 5}

        count = history.delete_project_history("proj-1")

        assert count == 5
        assert mock_db.execute.called

    def test_cleanup_old_events(self, history, mock_db):
        """Should delete events older than threshold."""
        mock_db.fetch_one.return_value = {"count": 10}

        count = history.cleanup_old_events(days=30)

        assert count == 10
        # Verify DELETE was called with timestamp condition
        delete_calls = [
            c for c in mock_db.execute.call_args_list 
            if "DELETE" in str(c)
        ]
        assert len(delete_calls) > 0


class TestOperationSummary:
    """Tests for OperationSummary."""

    def test_default_values(self):
        """Should have sensible defaults."""
        summary = OperationSummary(project_id="proj-1")

        assert summary.total_operations == 0
        assert summary.total_files_processed == 0
        assert summary.entity_type_counts == {}
        assert summary.first_operation is None
