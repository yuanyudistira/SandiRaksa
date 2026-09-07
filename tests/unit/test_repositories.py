"""Tests for repository classes."""

import tempfile
from pathlib import Path

import pytest

from sandiraksa.storage.database import Database
from sandiraksa.storage.repositories import (
    CustomRuleRepository,
    DuplicateError,
    FileRepository,
    NotFoundError,
    OperationRepository,
    ProjectRepository,
    TokenMappingRepository,
)


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        database = Database(db_path)
        database.initialize()
        yield database
        database.close()


@pytest.fixture
def project_repo(db: Database):
    """Create a project repository."""
    return ProjectRepository(db)


@pytest.fixture
def file_repo(db: Database):
    """Create a file repository."""
    return FileRepository(db)


@pytest.fixture
def operation_repo(db: Database):
    """Create an operation repository."""
    return OperationRepository(db)


@pytest.fixture
def rule_repo(db: Database):
    """Create a custom rule repository."""
    return CustomRuleRepository(db)


@pytest.fixture
def mapping_repo(db: Database):
    """Create a token mapping repository."""
    return TokenMappingRepository(db)


class TestProjectRepository:
    """Tests for ProjectRepository."""

    def test_create_project(self, project_repo: ProjectRepository):
        """Should create a new project."""
        project = project_repo.create(
            name_enc=b"encrypted_name",
            profile_id="standard_pii",
            description_enc=b"encrypted_desc",
        )

        assert project.id is not None
        assert project.name_enc == b"encrypted_name"
        assert project.profile_id == "standard_pii"
        assert project.reversible_default is True

    def test_get_by_id(self, project_repo: ProjectRepository):
        """Should retrieve project by ID."""
        created = project_repo.create(
            name_enc=b"test",
            profile_id="standard_pii",
        )

        retrieved = project_repo.get_by_id(created.id)
        assert retrieved.id == created.id
        assert retrieved.name_enc == created.name_enc

    def test_get_by_id_not_found(self, project_repo: ProjectRepository):
        """Should raise NotFoundError for missing project."""
        with pytest.raises(NotFoundError):
            project_repo.get_by_id("nonexistent-id")

    def test_get_all(self, project_repo: ProjectRepository):
        """Should retrieve all projects."""
        project_repo.create(name_enc=b"proj1", profile_id="standard_pii")
        project_repo.create(name_enc=b"proj2", profile_id="hr")

        projects = project_repo.get_all()
        assert len(projects) == 2

    def test_update_project(self, project_repo: ProjectRepository):
        """Should update project fields."""
        project = project_repo.create(
            name_enc=b"original",
            profile_id="standard_pii",
        )

        updated = project_repo.update(
            project.id,
            name_enc=b"updated",
            reversible_default=False,
        )

        assert updated.name_enc == b"updated"
        assert updated.reversible_default is False

    def test_delete_project(self, project_repo: ProjectRepository):
        """Should delete project."""
        project = project_repo.create(
            name_enc=b"to_delete",
            profile_id="standard_pii",
        )

        project_repo.delete(project.id)

        with pytest.raises(NotFoundError):
            project_repo.get_by_id(project.id)

    def test_count(self, project_repo: ProjectRepository):
        """Should return correct count."""
        assert project_repo.count() == 0

        project_repo.create(name_enc=b"proj1", profile_id="standard_pii")
        assert project_repo.count() == 1

        project_repo.create(name_enc=b"proj2", profile_id="standard_pii")
        assert project_repo.count() == 2


class TestFileRepository:
    """Tests for FileRepository."""

    @pytest.fixture
    def project_id(self, project_repo: ProjectRepository):
        """Create a project and return its ID."""
        project = project_repo.create(
            name_enc=b"test_project",
            profile_id="standard_pii",
        )
        return project.id

    def test_create_file(
        self, file_repo: FileRepository, project_id: str
    ):
        """Should create a new file record."""
        file = file_repo.create(
            project_id=project_id,
            filename_enc=b"document.xlsx",
            extension=".xlsx",
            file_size=1024,
        )

        assert file.id is not None
        assert file.project_id == project_id
        assert file.extension == ".xlsx"
        assert file.status == "pending"

    def test_get_by_project(
        self, file_repo: FileRepository, project_id: str
    ):
        """Should get all files for a project."""
        file_repo.create(
            project_id=project_id,
            filename_enc=b"file1.xlsx",
            extension=".xlsx",
        )
        file_repo.create(
            project_id=project_id,
            filename_enc=b"file2.docx",
            extension=".docx",
        )

        files = file_repo.get_by_project(project_id)
        assert len(files) == 2

    def test_cascade_delete(
        self,
        db: Database,
        project_repo: ProjectRepository,
        file_repo: FileRepository,
    ):
        """Files should be deleted when project is deleted."""
        project = project_repo.create(
            name_enc=b"cascade_test",
            profile_id="standard_pii",
        )
        file = file_repo.create(
            project_id=project.id,
            filename_enc=b"test.csv",
            extension=".csv",
        )

        project_repo.delete(project.id)

        with pytest.raises(NotFoundError):
            file_repo.get_by_id(file.id)


class TestOperationRepository:
    """Tests for OperationRepository."""

    @pytest.fixture
    def project_id(self, project_repo: ProjectRepository):
        """Create a project and return its ID."""
        project = project_repo.create(
            name_enc=b"test_project",
            profile_id="standard_pii",
        )
        return project.id

    def test_create_operation(
        self, operation_repo: OperationRepository, project_id: str
    ):
        """Should create a new operation."""
        operation = operation_repo.create(
            project_id=project_id,
            operation_type="protect",
            app_version="0.1.0",
            reversible=True,
        )

        assert operation.id is not None
        assert operation.status == "processing"
        assert operation.reversible is True

    def test_complete_operation(
        self, operation_repo: OperationRepository, project_id: str
    ):
        """Should complete an operation with results."""
        operation = operation_repo.create(
            project_id=project_id,
            operation_type="protect",
            app_version="0.1.0",
            reversible=True,
        )

        completed = operation_repo.complete(
            operation.id,
            status="completed",
            findings_total=100,
            treated_total=95,
            ignored_total=5,
            residual_total=0,
        )

        assert completed.status == "completed"
        assert completed.findings_total == 100
        assert completed.treated_total == 95
        assert completed.completed_at is not None


class TestCustomRuleRepository:
    """Tests for CustomRuleRepository."""

    @pytest.fixture
    def project_id(self, project_repo: ProjectRepository):
        """Create a project and return its ID."""
        project = project_repo.create(
            name_enc=b"test_project",
            profile_id="standard_pii",
        )
        return project.id

    def test_create_rule(
        self, rule_repo: CustomRuleRepository, project_id: str
    ):
        """Should create a custom rule."""
        rule = rule_repo.create(
            project_id=project_id,
            rule_type="exact",
            entity_type="BUSINESS_CONFIDENTIAL",
            pattern_enc=b"encrypted_pattern",
        )

        assert rule.id is not None
        assert rule.entity_type == "BUSINESS_CONFIDENTIAL"
        assert rule.enabled is True

    def test_get_enabled_only(
        self, rule_repo: CustomRuleRepository, project_id: str
    ):
        """Should filter by enabled status."""
        rule1 = rule_repo.create(
            project_id=project_id,
            rule_type="exact",
            entity_type="TYPE1",
            pattern_enc=b"pattern1",
        )
        rule2 = rule_repo.create(
            project_id=project_id,
            rule_type="exact",
            entity_type="TYPE2",
            pattern_enc=b"pattern2",
        )

        rule_repo.update_enabled(rule2.id, False)

        enabled_rules = rule_repo.get_by_project(project_id, enabled_only=True)
        all_rules = rule_repo.get_by_project(project_id, enabled_only=False)

        assert len(enabled_rules) == 1
        assert len(all_rules) == 2


class TestTokenMappingRepository:
    """Tests for TokenMappingRepository."""

    @pytest.fixture
    def project_id(self, project_repo: ProjectRepository):
        """Create a project and return its ID."""
        project = project_repo.create(
            name_enc=b"test_project",
            profile_id="standard_pii",
        )
        return project.id

    def test_create_mapping(
        self, mapping_repo: TokenMappingRepository, project_id: str
    ):
        """Should create a token mapping."""
        mapping = mapping_repo.create(
            project_id=project_id,
            token="[[PERSON_ABC123]]",
            entity_type="PERSON",
            normalized_hmac="hmac_value",
            original_value_enc=b"encrypted_original",
        )

        assert mapping.id is not None
        assert mapping.token == "[[PERSON_ABC123]]"
        assert mapping.entity_type == "PERSON"

    def test_find_by_hmac(
        self, mapping_repo: TokenMappingRepository, project_id: str
    ):
        """Should find mapping by HMAC for token reuse."""
        mapping_repo.create(
            project_id=project_id,
            token="[[PERSON_ABC123]]",
            entity_type="PERSON",
            normalized_hmac="unique_hmac",
            original_value_enc=b"encrypted",
        )

        found = mapping_repo.find_by_hmac(
            project_id, "PERSON", "unique_hmac"
        )
        assert found is not None
        assert found.token == "[[PERSON_ABC123]]"

        not_found = mapping_repo.find_by_hmac(
            project_id, "PERSON", "different_hmac"
        )
        assert not_found is None

    def test_find_by_token(
        self, mapping_repo: TokenMappingRepository, project_id: str
    ):
        """Should find mapping by token for restoration."""
        mapping_repo.create(
            project_id=project_id,
            token="[[EMAIL_DEF456]]",
            entity_type="EMAIL",
            normalized_hmac="email_hmac",
            original_value_enc=b"encrypted_email",
        )

        found = mapping_repo.find_by_token(project_id, "[[EMAIL_DEF456]]")
        assert found is not None
        assert found.entity_type == "EMAIL"

    def test_token_exists(
        self, mapping_repo: TokenMappingRepository, project_id: str
    ):
        """Should check token existence for collision detection."""
        mapping_repo.create(
            project_id=project_id,
            token="[[UNIQUE_TOKEN]]",
            entity_type="PERSON",
            normalized_hmac="hmac",
            original_value_enc=b"encrypted",
        )

        assert mapping_repo.token_exists(project_id, "[[UNIQUE_TOKEN]]") is True
        assert mapping_repo.token_exists(project_id, "[[OTHER_TOKEN]]") is False

    def test_count_by_project(
        self, mapping_repo: TokenMappingRepository, project_id: str
    ):
        """Should count mappings for a project."""
        assert mapping_repo.count_by_project(project_id) == 0

        mapping_repo.create(
            project_id=project_id,
            token="[[T1]]",
            entity_type="PERSON",
            normalized_hmac="h1",
            original_value_enc=b"e1",
        )
        mapping_repo.create(
            project_id=project_id,
            token="[[T2]]",
            entity_type="EMAIL",
            normalized_hmac="h2",
            original_value_enc=b"e2",
        )

        assert mapping_repo.count_by_project(project_id) == 2
