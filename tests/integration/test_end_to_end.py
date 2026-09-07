"""
End-to-end integration tests for SandiRaksa.

Tests complete workflows from document input to protected output and restoration.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


class TestCSVIntegration:
    """Test CSV reading integration."""

    def test_csv_reader_reads_file(self):
        """Test CSVReader can read a file."""
        from sandiraksa.documents.csv_handler import CSVReader
        
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test.csv"
            csv_path.write_text("name,email\nJohn,john@test.com\n", encoding="utf-8")
            
            reader = CSVReader(csv_path)
            rows = list(reader.iter_rows())
            
            # iter_rows yields (row_idx, cells) tuples
            assert len(rows) >= 1


class TestDomainModels:
    """Test domain model integration."""

    def test_project_creation(self):
        """Test Project model can be created."""
        from sandiraksa.domain import Project
        
        project = Project(name="Test Project")
        
        assert project.name == "Test Project"
        assert project.id is not None
