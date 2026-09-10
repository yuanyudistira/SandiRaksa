"""
Protection Pipeline.

Orchestrates the full protection workflow:
1. Scan document for sensitive data
2. Generate treatment plan based on findings
3. Apply treatments and create protected output
4. Validate output is clean
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol, runtime_checkable
from uuid import uuid4

from sandiraksa.detection.context import (
    DetectionConfig,
    DetectionContext,
    DetectionResult,
    TextSegment,
    create_detection_context,
)
from sandiraksa.detection.engine import DetectionEngine, get_detection_engine
from sandiraksa.domain.finding import DocumentLocation, Finding, ReviewAction
from sandiraksa.domain.operation import OperationStatus, OperationType
from sandiraksa.domain.policy import ProtectionPolicy
from sandiraksa.domain.token import Treatment, TreatmentType
from sandiraksa.protection.consistency import ConsistencyManager

if TYPE_CHECKING:
    from sandiraksa.documents.csv_handler import CSVHandler

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Base exception for pipeline errors."""

    pass


class PipelinePhase(str, Enum):
    """Phases of the protection pipeline."""

    INITIALIZING = "initializing"
    SCANNING = "scanning"
    REVIEWING = "reviewing"
    TREATING = "treating"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TreatmentPlan:
    """
    Plan for treating findings in a document.

    Maps finding IDs to their treatments.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    findings: list[Finding] = field(default_factory=list)
    treatments: dict[str, Treatment] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Statistics
    total_findings: int = 0
    findings_to_treat: int = 0
    findings_to_keep: int = 0
    findings_pending: int = 0

    def add_finding(self, finding: Finding) -> None:
        """Add a finding to the plan."""
        self.findings.append(finding)
        self.total_findings += 1

        if finding.review_action == ReviewAction.PENDING:
            self.findings_pending += 1
        elif finding.review_action == ReviewAction.PROTECT:
            self.findings_to_treat += 1
        elif finding.review_action == ReviewAction.ALLOW:
            self.findings_to_keep += 1

    def add_treatment(self, finding_id: str, treatment: Treatment) -> None:
        """Add a treatment for a finding."""
        self.treatments[finding_id] = treatment

    def get_treatment(self, finding_id: str) -> Treatment | None:
        """Get the treatment for a finding."""
        return self.treatments.get(finding_id)

    def get_treatments_by_location(self) -> dict[tuple[int, int], str]:
        """
        Get treatments indexed by location (row, col).

        Used for CSV treatment application.
        """
        result: dict[tuple[int, int], str] = {}

        for treatment in self.treatments.values():
            loc = treatment.location
            if loc and loc.get("row_number") is not None:
                key = (loc["row_number"], loc.get("column_number", 0))
                result[key] = treatment.replacement

        return result

    @property
    def is_complete(self) -> bool:
        """Check if all findings have been reviewed."""
        return self.findings_pending == 0


@dataclass
class PipelineProgress:
    """Progress tracking for pipeline execution."""

    phase: PipelinePhase = PipelinePhase.INITIALIZING
    current_step: int = 0
    total_steps: int = 100
    message: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    # Phase-specific progress
    scan_progress: float = 0.0  # 0.0 - 1.0
    treatment_progress: float = 0.0

    @property
    def overall_progress(self) -> float:
        """Get overall progress as percentage."""
        phase_weights = {
            PipelinePhase.INITIALIZING: 0.0,
            PipelinePhase.SCANNING: 0.4,
            PipelinePhase.REVIEWING: 0.5,
            PipelinePhase.TREATING: 0.85,
            PipelinePhase.VALIDATING: 0.95,
            PipelinePhase.COMPLETED: 1.0,
            PipelinePhase.FAILED: 0.0,
        }
        return phase_weights.get(self.phase, 0.0) * 100

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()


ProgressCallback = Callable[[PipelineProgress], None]


@runtime_checkable
class DocumentHandler(Protocol):
    """Protocol for document handlers."""

    def open(self, file_path: Path, **kwargs: Any) -> Any:
        """Open a document file."""
        ...

    def get_text_segments(self, **kwargs: Any) -> Any:
        """Get text segments for scanning."""
        ...

    def create_treated_file(
        self, output_path: Path, treatments: dict[tuple[int, int], str], **kwargs: Any
    ) -> Path:
        """Create a treated copy of the document."""
        ...

    def close(self) -> None:
        """Close the handler."""
        ...


@dataclass
class PipelineResult:
    """Result of a protection pipeline execution."""

    success: bool
    operation_id: str
    file_id: str
    output_path: Path | None = None

    # Statistics
    findings_count: int = 0
    treatments_applied: int = 0
    tokens_created: int = 0

    # Timing
    scan_duration_ms: float = 0.0
    treatment_duration_ms: float = 0.0
    total_duration_ms: float = 0.0

    # Errors
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)


class ProtectionPipeline:
    """
    Main protection pipeline for processing documents.

    Coordinates detection, treatment planning, and output generation.
    """

    def __init__(
        self,
        project_id: str,
        detection_engine: DetectionEngine | None = None,
        consistency_manager: ConsistencyManager | None = None,
    ) -> None:
        """
        Initialize the protection pipeline.

        Args:
            project_id: The project ID.
            detection_engine: Detection engine to use. If None, uses global.
            consistency_manager: For token consistency. If None, creates new.
        """
        self._project_id = project_id
        self._engine = detection_engine or get_detection_engine()
        self._consistency = consistency_manager or ConsistencyManager(project_id)

        self._progress = PipelineProgress()
        self._progress_callback: ProgressCallback | None = None

        # Current state
        self._handler: DocumentHandler | None = None
        self._detection_context: DetectionContext | None = None
        self._treatment_plan: TreatmentPlan | None = None

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        """Set callback for progress updates."""
        self._progress_callback = callback

    def _update_progress(
        self,
        phase: PipelinePhase | None = None,
        message: str = "",
    ) -> None:
        """Update and report progress."""
        if phase:
            self._progress.phase = phase
        if message:
            self._progress.message = message

        if self._progress_callback:
            try:
                self._progress_callback(self._progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    def scan_document(
        self,
        file_path: Path,
        handler: DocumentHandler,
        policy: ProtectionPolicy | None = None,
        operation_id: str | None = None,
        file_id: str | None = None,
    ) -> TreatmentPlan:
        """
        Scan a document for sensitive data.

        Args:
            file_path: Path to the document.
            handler: Document handler for the file type.
            policy: Protection policy to use.
            operation_id: Operation ID for tracking.
            file_id: File ID for tracking.

        Returns:
            TreatmentPlan with detected findings.
        """
        self._handler = handler
        operation_id = operation_id or str(uuid4())
        file_id = file_id or str(uuid4())

        self._update_progress(PipelinePhase.SCANNING, "Opening document...")

        try:
            # Open the document
            handler.open(file_path)

            # Create detection context
            self._detection_context = create_detection_context(
                operation_id=operation_id,
                file_id=file_id,
                project_id=self._project_id,
                policy=policy,
            )

            # Create treatment plan
            self._treatment_plan = TreatmentPlan()

            # Get text segments and scan
            total_segments = 0
            processed = 0

            for batch in handler.get_text_segments():
                for segment in batch:
                    # Scan segment
                    results = self._engine.analyze_segment(
                        segment, self._detection_context
                    )

                    processed += 1
                    self._progress.scan_progress = min(processed / max(total_segments, 1), 1.0)

                total_segments += len(batch)

            # Convert results to findings
            self._detection_context.convert_to_findings()

            # Add findings to treatment plan
            for finding in self._detection_context.findings:
                self._treatment_plan.add_finding(finding)

            self._update_progress(
                PipelinePhase.REVIEWING,
                f"Found {len(self._treatment_plan.findings)} sensitive items",
            )

            return self._treatment_plan

        except Exception as e:
            logger.error(f"Scan failed: {e}")
            self._update_progress(PipelinePhase.FAILED, str(e))
            raise PipelineError(f"Document scan failed: {e}") from e

    def generate_treatments(
        self,
        plan: TreatmentPlan,
        default_treatment: TreatmentType = TreatmentType.TOKEN,
    ) -> TreatmentPlan:
        """
        Generate treatments for all findings in a plan.

        Args:
            plan: The treatment plan with findings.
            default_treatment: Default treatment type to apply.

        Returns:
            Updated plan with treatments.
        """
        self._update_progress(PipelinePhase.TREATING, "Generating treatments...")

        for i, finding in enumerate(plan.findings):
            # Determine treatment type
            treatment_type = default_treatment

            # Check finding review action
            if finding.review_action == ReviewAction.ALLOW:
                treatment_type = TreatmentType.KEEP

            # Generate treatment using consistency manager
            treatment = self._consistency.process_finding(
                finding=finding,
                original_value=finding.detected_text,
                treatment_type=treatment_type,
            )

            plan.add_treatment(finding.id, treatment)

            # Update progress
            self._progress.treatment_progress = (i + 1) / len(plan.findings)

        return plan

    def apply_treatments(
        self,
        plan: TreatmentPlan,
        output_path: Path,
    ) -> Path:
        """
        Apply treatments and create protected output file.

        Args:
            plan: Treatment plan with treatments.
            output_path: Path for output file.

        Returns:
            Path to the created output file.
        """
        if not self._handler:
            raise PipelineError("No document handler. Call scan_document first.")

        self._update_progress(PipelinePhase.TREATING, "Applying treatments...")

        try:
            # Get treatments indexed by location
            treatments = plan.get_treatments_by_location()

            # Create treated file
            result_path = self._handler.create_treated_file(output_path, treatments)

            self._update_progress(
                PipelinePhase.VALIDATING, "Verifying output..."
            )

            return result_path

        except Exception as e:
            logger.error(f"Treatment application failed: {e}")
            self._update_progress(PipelinePhase.FAILED, str(e))
            raise PipelineError(f"Treatment application failed: {e}") from e

    def execute(
        self,
        file_path: Path,
        output_path: Path,
        handler: DocumentHandler,
        policy: ProtectionPolicy | None = None,
        default_treatment: TreatmentType = TreatmentType.TOKEN,
        auto_accept: bool = True,
    ) -> PipelineResult:
        """
        Execute the full protection pipeline.

        Args:
            file_path: Input file path.
            output_path: Output file path.
            handler: Document handler.
            policy: Protection policy.
            default_treatment: Default treatment type.
            auto_accept: Auto-accept all findings (no review).

        Returns:
            PipelineResult with execution details.
        """
        start_time = datetime.utcnow()
        operation_id = str(uuid4())
        file_id = str(uuid4())

        result = PipelineResult(
            success=False,
            operation_id=operation_id,
            file_id=file_id,
        )

        try:
            # Phase 1: Scan
            scan_start = datetime.utcnow()
            plan = self.scan_document(
                file_path=file_path,
                handler=handler,
                policy=policy,
                operation_id=operation_id,
                file_id=file_id,
            )
            scan_end = datetime.utcnow()
            result.scan_duration_ms = (scan_end - scan_start).total_seconds() * 1000

            result.findings_count = plan.total_findings

            # Phase 2: Auto-accept if enabled
            if auto_accept:
                for finding in plan.findings:
                    finding.review_action = ReviewAction.PROTECT
                    plan.findings_to_treat += 1
                    plan.findings_pending -= 1

            # Phase 3: Generate treatments
            treat_start = datetime.utcnow()
            plan = self.generate_treatments(plan, default_treatment)

            # Phase 4: Apply treatments
            result.output_path = self.apply_treatments(plan, output_path)
            treat_end = datetime.utcnow()
            result.treatment_duration_ms = (treat_end - treat_start).total_seconds() * 1000

            result.treatments_applied = len(plan.treatments)
            result.tokens_created = self._consistency.stats.tokens_created

            # Complete
            self._progress.completed_at = datetime.utcnow()
            self._update_progress(PipelinePhase.COMPLETED, "Protection complete")

            result.success = True

        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            result.error_message = str(e)
            self._update_progress(PipelinePhase.FAILED, str(e))

        finally:
            # Cleanup
            if self._handler:
                try:
                    self._handler.close()
                except Exception:
                    pass

            end_time = datetime.utcnow()
            result.total_duration_ms = (end_time - start_time).total_seconds() * 1000

        return result

    def reset(self) -> None:
        """Reset the pipeline state."""
        self._handler = None
        self._detection_context = None
        self._treatment_plan = None
        self._progress = PipelineProgress()
        self._consistency.reset()


def create_protection_pipeline(project_id: str) -> ProtectionPipeline:
    """Factory function to create a protection pipeline."""
    from sandiraksa.detection.presidio_engine import create_detection_engine

    engine = create_detection_engine(use_presidio=False)  # Use regex fallback
    return ProtectionPipeline(project_id, detection_engine=engine)
