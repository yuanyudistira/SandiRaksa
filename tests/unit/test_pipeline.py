"""Tests for protection pipeline."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sandiraksa.domain.finding import Finding, ReviewAction, DocumentLocation
from sandiraksa.domain.token import TreatmentType
from sandiraksa.protection.pipeline import (
    PipelinePhase,
    PipelineProgress,
    PipelineResult,
    ProtectionPipeline,
    TreatmentPlan,
    create_protection_pipeline,
)


class TestTreatmentPlan:
    """Tests for TreatmentPlan."""

    def test_add_finding(self):
        """Should track findings correctly."""
        plan = TreatmentPlan()

        finding1 = Finding(
            id="f1",
            file_id="file1",
            operation_id="op1",
            entity_type="PERSON",
            original_text="John Doe",
            confidence_score=0.9,
            location=DocumentLocation(element_type="cell", element_id="A1"),
            review_action=ReviewAction.PENDING,
        )
        finding2 = Finding(
            id="f2",
            file_id="file1",
            operation_id="op1",
            entity_type="EMAIL",
            original_text="test@test.com",
            confidence_score=0.95,
            location=DocumentLocation(element_type="cell", element_id="B1"),
            review_action=ReviewAction.ACCEPT,
        )

        plan.add_finding(finding1)
        plan.add_finding(finding2)

        assert plan.total_findings == 2
        assert plan.findings_pending == 1
        assert plan.findings_to_treat == 1

    def test_is_complete(self):
        """Should detect when all findings reviewed."""
        plan = TreatmentPlan()

        finding = Finding(
            id="f1",
            file_id="file1",
            operation_id="op1",
            entity_type="PERSON",
            original_text="John",
            confidence_score=0.9,
            location=DocumentLocation(element_type="cell", element_id="A1"),
            review_action=ReviewAction.PENDING,
        )
        plan.add_finding(finding)

        assert not plan.is_complete

        # Mark as reviewed
        plan.findings_pending = 0
        assert plan.is_complete


class TestPipelineProgress:
    """Tests for PipelineProgress."""

    def test_overall_progress(self):
        """Should calculate overall progress."""
        progress = PipelineProgress()

        progress.phase = PipelinePhase.INITIALIZING
        assert progress.overall_progress == 0.0

        progress.phase = PipelinePhase.SCANNING
        assert progress.overall_progress == 40.0

        progress.phase = PipelinePhase.COMPLETED
        assert progress.overall_progress == 100.0

    def test_elapsed_time(self):
        """Should track elapsed time."""
        progress = PipelineProgress()

        # Should have some elapsed time
        assert progress.elapsed_seconds >= 0


class TestProtectionPipeline:
    """Tests for ProtectionPipeline."""

    @pytest.fixture
    def mock_handler(self):
        """Create a mock document handler."""
        handler = MagicMock()

        # Mock text segments
        from sandiraksa.detection.context import TextSegment
        from sandiraksa.domain.finding import DocumentLocation

        segments = [
            TextSegment(
                text="John Doe",
                location=DocumentLocation(
                    element_type="cell",
                    element_id="A1",
                    row_number=0,
                    column_number=0,
                ),
            ),
            TextSegment(
                text="test@example.com",
                location=DocumentLocation(
                    element_type="cell",
                    element_id="B1",
                    row_number=0,
                    column_number=1,
                ),
            ),
        ]

        handler.get_text_segments.return_value = [segments]
        handler.create_treated_file.return_value = Path("/output/file.csv")

        return handler

    @pytest.fixture
    def mock_engine(self):
        """Create a mock detection engine."""
        from sandiraksa.detection.context import DetectionResult

        engine = MagicMock()
        engine._initialized = True

        # Return detection results
        def analyze_segment(segment, context):
            if "email" in segment.text or "@" in segment.text:
                result = DetectionResult(
                    entity_type="EMAIL_ADDRESS",
                    start=0,
                    end=len(segment.text),
                    text=segment.text,
                    score=0.95,
                )
                result.document_location = segment.location
                context.add_result(result)
                return [result]
            return []

        engine.analyze_segment.side_effect = analyze_segment
        return engine

    def test_scan_document(self, mock_handler, mock_engine):
        """Should scan document and create treatment plan."""
        pipeline = ProtectionPipeline(
            project_id="test-project",
            detection_engine=mock_engine,
        )

        plan = pipeline.scan_document(
            file_path=Path("/test/file.csv"),
            handler=mock_handler,
        )

        assert plan is not None
        assert mock_handler.open.called
        assert mock_handler.get_text_segments.called

    def test_generate_treatments(self, mock_handler, mock_engine):
        """Should generate treatments for findings."""
        pipeline = ProtectionPipeline(
            project_id="test-project",
            detection_engine=mock_engine,
        )

        # Create plan with findings
        plan = TreatmentPlan()
        finding = Finding(
            id="f1",
            file_id="file1",
            operation_id="op1",
            entity_type="EMAIL_ADDRESS",
            original_text="test@test.com",
            confidence_score=0.95,
            location=DocumentLocation(
                element_type="cell",
                element_id="B1",
                row_number=0,
                column_number=1,
            ),
            review_action=ReviewAction.ACCEPT,
        )
        plan.add_finding(finding)

        # Generate treatments
        result_plan = pipeline.generate_treatments(plan)

        assert len(result_plan.treatments) == 1
        assert "f1" in result_plan.treatments

    def test_progress_callback(self, mock_handler, mock_engine):
        """Should call progress callback."""
        pipeline = ProtectionPipeline(
            project_id="test-project",
            detection_engine=mock_engine,
        )

        progress_updates = []

        def on_progress(progress):
            progress_updates.append(progress.phase)

        pipeline.set_progress_callback(on_progress)

        pipeline.scan_document(
            file_path=Path("/test/file.csv"),
            handler=mock_handler,
        )

        assert len(progress_updates) > 0
        assert PipelinePhase.SCANNING in progress_updates


class TestPipelineResult:
    """Tests for PipelineResult."""

    def test_success_result(self):
        """Should create success result."""
        result = PipelineResult(
            success=True,
            operation_id="op1",
            file_id="file1",
            output_path=Path("/output/protected.csv"),
            findings_count=10,
            treatments_applied=8,
        )

        assert result.success
        assert result.findings_count == 10
        assert result.treatments_applied == 8

    def test_failure_result(self):
        """Should create failure result."""
        result = PipelineResult(
            success=False,
            operation_id="op1",
            file_id="file1",
            error_message="File not found",
        )

        assert not result.success
        assert result.error_message == "File not found"


class TestPipelineFactory:
    """Tests for pipeline factory."""

    def test_create_pipeline(self):
        """Should create pipeline with default settings."""
        pipeline = create_protection_pipeline("test-project")

        assert pipeline is not None
        assert pipeline._project_id == "test-project"
