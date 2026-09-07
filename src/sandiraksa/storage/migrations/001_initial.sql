-- Migration 001: Initial Schema
-- This file documents the initial schema for reference.
-- Actual creation is handled by database.py._create_schema()

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name_enc BLOB NOT NULL,
    description_enc BLOB,
    profile_id TEXT NOT NULL,
    reversible_default INTEGER NOT NULL DEFAULT 1,
    remember_source_paths INTEGER NOT NULL DEFAULT 0,
    retention_policy TEXT NOT NULL DEFAULT 'until_deleted',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_opened_at TEXT,
    schema_version INTEGER NOT NULL DEFAULT 1
);

-- Files table
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    filename_enc BLOB NOT NULL,
    source_path_enc BLOB,
    extension TEXT NOT NULL,
    file_size INTEGER,
    source_sha256 TEXT,
    latest_output_sha256 TEXT,
    added_at TEXT NOT NULL,
    last_processed_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Operations table
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
);

-- Custom rules table
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
);

-- Token mappings table
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
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_files_project ON files(project_id);
CREATE INDEX IF NOT EXISTS idx_operations_project ON operations(project_id);
CREATE INDEX IF NOT EXISTS idx_operations_file ON operations(file_id);
CREATE INDEX IF NOT EXISTS idx_custom_rules_project ON custom_rules(project_id);
CREATE INDEX IF NOT EXISTS idx_token_mappings_project ON token_mappings(project_id);
CREATE INDEX IF NOT EXISTS idx_token_mappings_lookup ON token_mappings(project_id, entity_type, normalized_hmac);
CREATE INDEX IF NOT EXISTS idx_token_mappings_token ON token_mappings(project_id, token);
CREATE INDEX IF NOT EXISTS idx_token_mappings_expires ON token_mappings(expires_at) WHERE expires_at IS NOT NULL;
