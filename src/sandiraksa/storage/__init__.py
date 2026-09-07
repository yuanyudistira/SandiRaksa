"""Storage layer for database and encrypted vault."""

from sandiraksa.storage.database import (
    Database,
    DatabaseError,
    MigrationError,
    SCHEMA_VERSION,
    get_database,
    reset_database,
    utc_now_iso,
)
from sandiraksa.storage.history import (
    HistoryEvent,
    HistoryEventData,
    HistoryEventType,
    OperationHistory,
    OperationSummary,
)
from sandiraksa.storage.repositories import (
    CustomRuleRecord,
    CustomRuleRepository,
    DuplicateError,
    FileRecord,
    FileRepository,
    NotFoundError,
    OperationRecord,
    OperationRepository,
    ProjectRecord,
    ProjectRepository,
    RepositoryError,
    TokenMappingRecord,
    TokenMappingRepository,
)

__all__ = [
    # Database
    "Database",
    "DatabaseError",
    "MigrationError",
    "SCHEMA_VERSION",
    "get_database",
    "reset_database",
    "utc_now_iso",
    # History
    "OperationHistory",
    "OperationSummary",
    "HistoryEvent",
    "HistoryEventData",
    "HistoryEventType",
    # Repository errors
    "RepositoryError",
    "NotFoundError",
    "DuplicateError",
    # Records
    "ProjectRecord",
    "FileRecord",
    "OperationRecord",
    "CustomRuleRecord",
    "TokenMappingRecord",
    # Repositories
    "ProjectRepository",
    "FileRepository",
    "OperationRepository",
    "CustomRuleRepository",
    "TokenMappingRepository",
]
