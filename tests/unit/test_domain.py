"""Tests for domain models."""

import pytest

from sandiraksa.domain import (
    ConfidenceBand,
    DocumentLocation,
    FileFormat,
    FileRecord,
    FileStatus,
    Finding,
    Operation,
    OperationStatus,
    OperationType,
    Project,
    ProjectStatus,
    ReviewAction,
    Token,
    TokenMapping,
    TreatmentType,
)


class TestProject:
    """Tests for Project model."""

    def test_create_project(self):
        """Should create project with defaults."""
        project = Project(name="Test Project")
        
        assert project.id is not None
        assert project.name == "Test Project"
        assert project.reversible_default is True
        assert project.profile_id == "standard_pii"
        assert project.status == ProjectStatus.ACTIVE

    def test_touch_updates_timestamp(self):
        """touch() should update updated_at."""
        project = Project(name="Test")
        original = project.updated_at
        
        # Need small delay to ensure timestamp changes
        import time
        time.sleep(0.01)
        
        project.touch()
        assert project.updated_at > original


class TestFileRecord:
    """Tests for FileRecord model."""

    def test_file_format_from_extension(self):
        """Should correctly identify file formats."""
        assert FileFormat.from_extension(".xlsx") == FileFormat.XLSX
        assert FileFormat.from_extension(".XLSX") == FileFormat.XLSX
        assert FileFormat.from_extension("csv") == FileFormat.CSV
        assert FileFormat.from_extension(".unknown") == FileFormat.UNKNOWN

    def test_supported_extensions(self):
        """Should return correct supported extensions."""
        extensions = FileFormat.supported_extensions()
        assert ".csv" in extensions
        assert ".xlsx" in extensions
        assert ".docx" in extensions
        assert ".pptx" in extensions

    def test_file_status_processing(self):
        """Should correctly identify processing states."""
        file = FileRecord(
            project_id="proj-1",
            filename="test.xlsx",
            extension=".xlsx",
            format=FileFormat.XLSX,
            status=FileStatus.SCANNING,
        )
        
        assert file.is_processing is True
        assert file.is_processed is False
        
        file.status = FileStatus.READY
        assert file.is_processing is False
        assert file.is_processed is True


class TestOperation:
    """Tests for Operation model."""

    def test_create_operation(self):
        """Should create operation with defaults."""
        op = Operation(
            project_id="proj-1",
            operation_type=OperationType.SCAN,
            reversible=True,
            app_version="0.1.0",
        )
        
        assert op.id is not None
        assert op.status == OperationStatus.PENDING
        assert op.findings_total == 0

    def test_complete_operation(self):
        """complete() should update status and counts."""
        op = Operation(
            project_id="proj-1",
            operation_type=OperationType.PROTECT,
            reversible=True,
            app_version="0.1.0",
        )
        
        op.complete(
            findings_total=100,
            treated_total=95,
            ignored_total=5,
            residual_total=0,
        )
        
        assert op.status == OperationStatus.COMPLETED
        assert op.findings_total == 100
        assert op.completed_at is not None

    def test_complete_with_warnings(self):
        """Should set status to completed_with_warnings if residuals exist."""
        op = Operation(
            project_id="proj-1",
            operation_type=OperationType.PROTECT,
            reversible=True,
            app_version="0.1.0",
        )
        
        op.complete(
            findings_total=100,
            treated_total=90,
            residual_total=5,
        )
        
        assert op.status == OperationStatus.COMPLETED_WITH_WARNINGS

    def test_fail_operation(self):
        """fail() should set status and record error."""
        op = Operation(
            project_id="proj-1",
            operation_type=OperationType.PROTECT,
            reversible=True,
            app_version="0.1.0",
        )
        
        op.fail("File not found")
        
        assert op.status == OperationStatus.FAILED
        assert "File not found" in op.warnings[0]


class TestToken:
    """Tests for Token model."""

    def test_token_str(self):
        """Token should render correctly."""
        token = Token(entity_type="PERSON", token_id="ABC123")
        assert str(token) == "[[PERSON_ABC123]]"

    def test_parse_valid_token(self):
        """Should parse valid token strings."""
        token = Token.parse("[[EMAIL_7F31A2]]")
        assert token is not None
        assert token.entity_type == "EMAIL"
        assert token.token_id == "7F31A2"

    def test_parse_invalid_token(self):
        """Should return None for invalid tokens."""
        assert Token.parse("not a token") is None
        assert Token.parse("[[invalid]]") is None
        assert Token.parse("[[PERSON123]]") is None  # Missing underscore
        assert Token.parse("[[person_123456]]") is None  # Lowercase type

    def test_find_all_tokens(self):
        """Should find all tokens in text."""
        text = "Hello [[PERSON_ABC123]], your email is [[EMAIL_DEF456]]."
        results = Token.find_all(text)
        
        assert len(results) == 2
        assert results[0][0].entity_type == "PERSON"
        assert results[1][0].entity_type == "EMAIL"

    def test_is_valid_format(self):
        """Should validate token format."""
        assert Token.is_valid_format("[[PERSON_ABC123]]") is True
        assert Token.is_valid_format("[[NIK_1234567890ABCDEF]]") is True
        assert Token.is_valid_format("invalid") is False


class TestFinding:
    """Tests for Finding model."""

    def test_create_finding(self):
        """Should create finding with defaults."""
        finding = Finding(
            entity_type="PERSON",
            detector="presidio",
            file_id="file-1",
            location={"component_type": "cell"},
        )
        
        assert finding.id is not None
        assert finding.review_action == ReviewAction.PENDING
        assert finding.is_pending is True

    def test_apply_decision(self):
        """apply_decision should update finding state."""
        finding = Finding(
            entity_type="PERSON",
            detector="presidio",
            file_id="file-1",
            location={},
        )
        
        finding.apply_decision(ReviewAction.PROTECT)
        
        assert finding.review_action == ReviewAction.PROTECT
        assert finding.should_protect is True

    def test_entity_type_override(self):
        """effective_entity_type should use override when set."""
        finding = Finding(
            entity_type="PERSON",
            detector="presidio",
            file_id="file-1",
            location={},
        )
        
        assert finding.effective_entity_type == "PERSON"
        
        finding.apply_decision(
            ReviewAction.PROTECT,
            entity_type_override="ORGANIZATION",
        )
        
        assert finding.effective_entity_type == "ORGANIZATION"


class TestDocumentLocation:
    """Tests for DocumentLocation model."""

    def test_xlsx_location(self):
        """Should format XLSX location correctly."""
        loc = DocumentLocation(
            file_id="file-1",
            component_type="cell",
            sheet_name="Sheet1",
            cell_address="A1",
        )
        
        assert "Sheet1" in loc.display_location
        assert "A1" in loc.display_location

    def test_pptx_location(self):
        """Should format PPTX location correctly."""
        loc = DocumentLocation(
            file_id="file-1",
            component_type="text_box",
            slide_number=3,
        )
        
        assert "Slide: 3" in loc.display_location

    def test_to_dict(self):
        """Should serialize to dict without None values."""
        loc = DocumentLocation(
            file_id="file-1",
            component_type="cell",
            sheet_name="Sheet1",
        )
        
        d = loc.to_dict()
        assert "file_id" in d
        assert "component_type" in d
        assert "sheet_name" in d
        assert "slide_number" not in d  # None values excluded


class TestTreatmentType:
    """Tests for TreatmentType enum."""

    def test_treatment_types(self):
        """Should have all required treatment types."""
        assert TreatmentType.TOKEN.value == "token"
        assert TreatmentType.REDACT.value == "redact"
        assert TreatmentType.CATEGORY.value == "category"
        assert TreatmentType.MASK.value == "mask"
        assert TreatmentType.KEEP.value == "keep"
