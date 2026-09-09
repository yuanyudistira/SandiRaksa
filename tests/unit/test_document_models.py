"""
Unit tests for Sprint 1 document models.

Tests cover:
- DocumentLocation model
- CharMapEntry and CharMap models
- LogicalSegment model
- DocumentAdapter base classes and utilities
"""

from pathlib import Path

import pytest

from sandiraksa.documents import (
    BaseDocumentAdapter,
    CharMap,
    CharMapEntry,
    DocumentComponent,
    DocumentExtractionError,
    DocumentFormat,
    DocumentLocation,
    DocumentProtectionError,
    DocumentValidationError,
    ExtractionResult,
    LogicalSegment,
    ProtectionResult,
    Replacement,
)


# =============================================================================
# DocumentLocation Tests
# =============================================================================


class TestDocumentLocation:
    """Tests for DocumentLocation model."""

    def test_create_basic_location(self) -> None:
        """Test creating a basic location."""
        loc = DocumentLocation(
            component=DocumentComponent.PARAGRAPH,
            file_id="test_file_001",
            file_type="txt",
        )
        assert loc.component == DocumentComponent.PARAGRAPH
        assert loc.file_id == "test_file_001"
        assert loc.file_type == "txt"

    def test_factory_for_txt(self) -> None:
        """Test factory method for TXT files."""
        loc = DocumentLocation.for_txt(
            file_id="txt_001",
            paragraph_index=5,
            char_start=10,
            char_end=25,
        )
        assert loc.component == DocumentComponent.PARAGRAPH
        assert loc.file_type == "txt"
        assert loc.paragraph_index == 5
        assert loc.char_start == 10
        assert loc.char_end == 25

    def test_factory_for_docx_paragraph(self) -> None:
        """Test factory method for DOCX paragraphs."""
        loc = DocumentLocation.for_docx_paragraph(
            file_id="docx_001",
            paragraph_index=3,
            run_indices=[0, 1, 2],
            char_start=0,
            char_end=50,
        )
        assert loc.component == DocumentComponent.DOCX_PARAGRAPH
        assert loc.file_type == "docx"
        assert loc.paragraph_index == 3
        assert loc.run_indices == [0, 1, 2]

    def test_factory_for_docx_table_cell(self) -> None:
        """Test factory method for DOCX table cells."""
        loc = DocumentLocation.for_docx_table_cell(
            file_id="docx_002",
            table_index=0,
            table_row=2,
            table_col=1,
            paragraph_index=0,
        )
        assert loc.component == DocumentComponent.DOCX_TABLE_CELL
        assert loc.table_index == 0
        assert loc.table_row == 2
        assert loc.table_col == 1

    def test_factory_for_pptx_shape(self) -> None:
        """Test factory method for PPTX shapes."""
        loc = DocumentLocation.for_pptx_shape(
            file_id="pptx_001",
            slide=2,
            shape_id="shape_123",
            char_start=5,
            char_end=20,
        )
        assert loc.component == DocumentComponent.PPTX_SHAPE
        assert loc.file_type == "pptx"
        assert loc.slide == 2
        assert loc.shape_id == "shape_123"

    def test_factory_for_pptx_title(self) -> None:
        """Test factory method for PPTX slide title."""
        loc = DocumentLocation.for_pptx_title(
            file_id="pptx_002",
            slide=1,
        )
        assert loc.component == DocumentComponent.PPTX_TITLE
        assert loc.slide == 1

    def test_factory_for_xlsx_cell(self) -> None:
        """Test factory method for XLSX cells."""
        loc = DocumentLocation.for_xlsx_cell(
            file_id="xlsx_001",
            sheet="Sheet1",
            cell="B5",
            row=4,
            column=1,
        )
        assert loc.component == DocumentComponent.XLSX_CELL
        assert loc.file_type == "xlsx"
        assert loc.sheet == "Sheet1"
        assert loc.cell == "B5"
        assert loc.row == 4
        assert loc.column == 1

    def test_factory_for_csv_cell(self) -> None:
        """Test factory method for CSV cells."""
        loc = DocumentLocation.for_csv_cell(
            file_id="csv_001",
            row=10,
            column=2,
        )
        assert loc.component == DocumentComponent.CSV_CELL
        assert loc.file_type == "csv"
        assert loc.row == 10
        assert loc.column == 2

    def test_display_location_xlsx(self) -> None:
        """Test display_location for Excel."""
        loc = DocumentLocation.for_xlsx_cell(
            file_id="test",
            sheet="Data",
            cell="A1",
        )
        display = loc.display_location
        assert "Sheet: Data" in display
        assert "Cell: A1" in display

    def test_display_location_pptx(self) -> None:
        """Test display_location for PowerPoint."""
        loc = DocumentLocation.for_pptx_shape(
            file_id="test",
            slide=3,
            shape_id="s1",
        )
        display = loc.display_location
        assert "Slide: 3" in display

    def test_sort_key(self) -> None:
        """Test sort_key for ordering locations."""
        loc1 = DocumentLocation.for_xlsx_cell(
            file_id="test", sheet="A", cell="A1", row=0, column=0
        )
        loc2 = DocumentLocation.for_xlsx_cell(
            file_id="test", sheet="A", cell="B1", row=0, column=1
        )
        loc3 = DocumentLocation.for_xlsx_cell(
            file_id="test", sheet="A", cell="A2", row=1, column=0
        )

        locations = [loc3, loc1, loc2]
        sorted_locs = sorted(locations, key=lambda x: x.sort_key)
        assert sorted_locs[0] == loc1
        assert sorted_locs[1] == loc2
        assert sorted_locs[2] == loc3

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        loc = DocumentLocation.for_xlsx_cell(
            file_id="test",
            sheet="Sheet1",
            cell="A1",
            row=0,
            column=0,
        )
        d = loc.to_dict()
        assert d["component"] == "xlsx_cell"
        assert d["file_id"] == "test"
        assert d["sheet"] == "Sheet1"
        assert "page" not in d  # None values excluded


# =============================================================================
# CharMapEntry Tests
# =============================================================================


class TestCharMapEntry:
    """Tests for CharMapEntry model."""

    def test_create_entry(self) -> None:
        """Test creating a basic entry."""
        entry = CharMapEntry(
            logical_start=0,
            logical_end=10,
            source_component_id="run_001",
            source_start=0,
            source_end=10,
        )
        assert entry.logical_start == 0
        assert entry.logical_end == 10
        assert entry.logical_length == 10
        assert entry.source_length == 10

    def test_contains_logical_position(self) -> None:
        """Test position containment check."""
        entry = CharMapEntry(
            logical_start=5,
            logical_end=15,
            source_component_id="r1",
            source_start=0,
            source_end=10,
        )
        assert entry.contains_logical_position(5)
        assert entry.contains_logical_position(10)
        assert entry.contains_logical_position(14)
        assert not entry.contains_logical_position(4)
        assert not entry.contains_logical_position(15)

    def test_overlaps_logical_range(self) -> None:
        """Test range overlap detection."""
        entry = CharMapEntry(
            logical_start=10,
            logical_end=20,
            source_component_id="r1",
            source_start=0,
            source_end=10,
        )
        # Overlap cases
        assert entry.overlaps_logical_range(5, 15)   # Partial left
        assert entry.overlaps_logical_range(15, 25)  # Partial right
        assert entry.overlaps_logical_range(12, 18)  # Inside
        assert entry.overlaps_logical_range(5, 25)   # Contains

        # No overlap
        assert not entry.overlaps_logical_range(0, 10)   # Adjacent left
        assert not entry.overlaps_logical_range(20, 30)  # Adjacent right
        assert not entry.overlaps_logical_range(0, 5)    # Before
        assert not entry.overlaps_logical_range(25, 30)  # After

    def test_logical_to_source(self) -> None:
        """Test converting logical position to source position."""
        entry = CharMapEntry(
            logical_start=10,
            logical_end=20,
            source_component_id="r1",
            source_start=5,
            source_end=15,
        )
        assert entry.logical_to_source(10) == 5
        assert entry.logical_to_source(15) == 10
        assert entry.logical_to_source(19) == 14
        assert entry.logical_to_source(5) is None  # Out of range
        assert entry.logical_to_source(20) is None  # End is exclusive

    def test_get_source_range_for_logical(self) -> None:
        """Test getting source range for a logical span."""
        entry = CharMapEntry(
            logical_start=10,
            logical_end=20,
            source_component_id="r1",
            source_start=0,
            source_end=10,
        )
        # Full overlap
        assert entry.get_source_range_for_logical(10, 20) == (0, 10)

        # Partial overlap left
        assert entry.get_source_range_for_logical(5, 15) == (0, 5)

        # Partial overlap right
        assert entry.get_source_range_for_logical(15, 25) == (5, 10)

        # Inside
        assert entry.get_source_range_for_logical(12, 18) == (2, 8)

        # No overlap
        assert entry.get_source_range_for_logical(0, 10) is None

    def test_validation_invalid_ranges(self) -> None:
        """Test validation rejects invalid ranges."""
        with pytest.raises(ValueError, match="logical_start"):
            CharMapEntry(
                logical_start=20,
                logical_end=10,  # Invalid: start > end
                source_component_id="r1",
                source_start=0,
                source_end=10,
            )

        with pytest.raises(ValueError, match="source_start"):
            CharMapEntry(
                logical_start=0,
                logical_end=10,
                source_component_id="r1",
                source_start=10,
                source_end=5,  # Invalid: start > end
            )


# =============================================================================
# CharMap Tests
# =============================================================================


class TestCharMap:
    """Tests for CharMap collection model."""

    def test_create_empty_charmap(self) -> None:
        """Test creating an empty CharMap."""
        cm = CharMap()
        assert cm.entries == []
        assert cm.total_logical_length == 0
        assert cm.source_component_ids == []

    def test_create_charmap_with_entries(self) -> None:
        """Test creating CharMap with entries."""
        entries = [
            CharMapEntry(
                logical_start=0, logical_end=5,
                source_component_id="r1", source_start=0, source_end=5,
            ),
            CharMapEntry(
                logical_start=5, logical_end=12,
                source_component_id="r2", source_start=0, source_end=7,
            ),
        ]
        cm = CharMap(entries=entries)
        assert len(cm.entries) == 2
        assert cm.total_logical_length == 12
        assert cm.source_component_ids == ["r1", "r2"]

    def test_from_runs(self) -> None:
        """Test building CharMap from runs (DOCX split-run scenario)."""
        runs = [
            ("r1", "Sat"),
            ("r2", "ria "),
            ("r3", "Putra"),
        ]
        char_map, text = CharMap.from_runs(runs)

        assert text == "Satria Putra"
        assert len(char_map.entries) == 3
        assert char_map.total_logical_length == 12

        # Verify mappings
        assert char_map.entries[0].logical_start == 0
        assert char_map.entries[0].logical_end == 3
        assert char_map.entries[0].source_component_id == "r1"

        assert char_map.entries[1].logical_start == 3
        assert char_map.entries[1].logical_end == 7
        assert char_map.entries[1].source_component_id == "r2"

        assert char_map.entries[2].logical_start == 7
        assert char_map.entries[2].logical_end == 12
        assert char_map.entries[2].source_component_id == "r3"

    def test_get_entry_at(self) -> None:
        """Test getting entry at a specific position."""
        char_map, _ = CharMap.from_runs([
            ("r1", "Hello"),
            ("r2", " World"),
        ])

        entry = char_map.get_entry_at(0)
        assert entry is not None
        assert entry.source_component_id == "r1"

        entry = char_map.get_entry_at(5)
        assert entry is not None
        assert entry.source_component_id == "r2"

        entry = char_map.get_entry_at(100)
        assert entry is None

    def test_get_entries_for_range(self) -> None:
        """Test getting all entries that span a range."""
        char_map, _ = CharMap.from_runs([
            ("r1", "Nama: "),     # 0-6
            ("r2", "Satria "),    # 6-13
            ("r3", "Putra "),     # 13-19
            ("r4", "Yudistira"),  # 19-28
        ])

        # Range spanning r2 and r3
        entries = char_map.get_entries_for_range(6, 19)
        assert len(entries) == 2
        assert entries[0].source_component_id == "r2"
        assert entries[1].source_component_id == "r3"

        # Range spanning all
        entries = char_map.get_entries_for_range(0, 28)
        assert len(entries) == 4

    def test_get_source_mappings_for_range(self) -> None:
        """Test the key method for protection - getting source ranges."""
        # This simulates DOCX split-run: "Satria Putra Yudistira" split as:
        # Run 1: "Sat" (logical 0-3)
        # Run 2: "ria Put" (logical 3-10)
        # Run 3: "ra Yudistira" (logical 10-22)
        char_map, text = CharMap.from_runs([
            ("run_1", "Sat"),
            ("run_2", "ria Put"),
            ("run_3", "ra Yudistira"),
        ])
        assert text == "Satria Putra Yudistira"

        # Detection found "Satria Putra" at logical 0-12
        # This spans run_1, run_2, and part of run_3
        mappings = char_map.get_source_mappings_for_range(0, 12)

        assert len(mappings) == 3
        assert mappings[0] == ("run_1", 0, 3)   # Full run 1
        assert mappings[1] == ("run_2", 0, 7)   # Full run 2
        assert mappings[2] == ("run_3", 0, 2)   # "ra" from run 3

    def test_append(self) -> None:
        """Test appending entries."""
        cm = CharMap()
        cm.append(CharMapEntry(
            logical_start=0, logical_end=5,
            source_component_id="r1", source_start=0, source_end=5,
        ))
        cm.append(CharMapEntry(
            logical_start=5, logical_end=10,
            source_component_id="r2", source_start=0, source_end=5,
        ))
        assert len(cm.entries) == 2

    def test_append_overlap_raises(self) -> None:
        """Test that appending overlapping entry raises error."""
        cm = CharMap()
        cm.append(CharMapEntry(
            logical_start=0, logical_end=10,
            source_component_id="r1", source_start=0, source_end=10,
        ))
        with pytest.raises(ValueError):
            cm.append(CharMapEntry(
                logical_start=5, logical_end=15,  # Overlaps!
                source_component_id="r2", source_start=0, source_end=10,
            ))

    def test_validation_rejects_overlapping_entries(self) -> None:
        """Test that overlapping entries are rejected on creation."""
        with pytest.raises(ValueError, match="Overlapping"):
            CharMap(entries=[
                CharMapEntry(
                    logical_start=0, logical_end=10,
                    source_component_id="r1", source_start=0, source_end=10,
                ),
                CharMapEntry(
                    logical_start=5, logical_end=15,  # Overlaps!
                    source_component_id="r2", source_start=0, source_end=10,
                ),
            ])


# =============================================================================
# LogicalSegment Tests
# =============================================================================


class TestLogicalSegment:
    """Tests for LogicalSegment model."""

    def test_create_basic_segment(self) -> None:
        """Test creating a basic segment."""
        seg = LogicalSegment(
            text="Test content",
            file_id="test_001",
            file_type="txt",
            location=DocumentLocation.for_txt(
                file_id="test_001",
                paragraph_index=0,
            ),
        )
        assert seg.text == "Test content"
        assert seg.text_length == 12
        assert seg.file_id == "test_001"
        assert seg.file_type == "txt"

    def test_factory_for_txt_paragraph(self) -> None:
        """Test factory for TXT paragraphs."""
        seg = LogicalSegment.for_txt_paragraph(
            text="NIK: 3271051708990001",
            file_id="txt_001",
            paragraph_index=0,
            previous_text="Data Pasien",
            next_text="Nama: Satria",
            key_label="NIK",
        )
        assert seg.text == "NIK: 3271051708990001"
        assert seg.file_type == "txt"
        assert seg.previous_text == "Data Pasien"
        assert seg.next_text == "Nama: Satria"
        assert seg.key_label == "NIK"
        assert seg.is_value_of_key is True
        assert seg.is_text_file is True

    def test_factory_for_docx_paragraph(self) -> None:
        """Test factory for DOCX paragraphs."""
        char_map, text = CharMap.from_runs([
            ("r1", "Nama: "),
            ("r2", "Satria"),
        ])
        seg = LogicalSegment.for_docx_paragraph(
            text=text,
            file_id="docx_001",
            paragraph_index=5,
            char_map=char_map,
            heading="Data Karyawan",
        )
        assert seg.text == "Nama: Satria"
        assert seg.file_type == "docx"
        assert seg.heading == "Data Karyawan"
        assert seg.is_document is True
        assert len(seg.char_map.entries) == 2

    def test_factory_for_pptx_shape(self) -> None:
        """Test factory for PPTX shapes."""
        char_map, text = CharMap.from_runs([
            ("r1", "3271051708990001"),
        ])
        seg = LogicalSegment.for_pptx_shape(
            text=text,
            file_id="pptx_001",
            slide=3,
            shape_id="shape_456",
            char_map=char_map,
            slide_title="Data Pasien",
            nearby_labels=["NIK", "Nama"],
        )
        assert seg.text == "3271051708990001"
        assert seg.file_type == "pptx"
        assert seg.slide_title == "Data Pasien"
        assert seg.nearby_labels == ["NIK", "Nama"]
        assert seg.is_presentation is True

    def test_factory_for_xlsx_cell(self) -> None:
        """Test factory for XLSX cells."""
        seg = LogicalSegment.for_xlsx_cell(
            text="satria@example.com",
            file_id="xlsx_001",
            sheet="Contacts",
            cell="C5",
            row=4,
            column=2,
            table_headers=["Name", "Phone", "Email"],
        )
        assert seg.text == "satria@example.com"
        assert seg.file_type == "xlsx"
        assert seg.table_headers == ["Name", "Phone", "Email"]
        assert seg.column_index == 2
        assert seg.is_spreadsheet is True

    def test_factory_for_csv_cell(self) -> None:
        """Test factory for CSV cells."""
        seg = LogicalSegment.for_csv_cell(
            text="081234567890",
            file_id="csv_001",
            row=10,
            column=3,
            table_headers=["ID", "Name", "Address", "Phone"],
        )
        assert seg.text == "081234567890"
        assert seg.file_type == "csv"
        assert seg.table_headers == ["ID", "Name", "Address", "Phone"]
        assert seg.is_spreadsheet is True

    def test_has_context(self) -> None:
        """Test context detection."""
        seg_no_context = LogicalSegment.for_txt_paragraph(
            text="Some text",
            file_id="test",
            paragraph_index=0,
        )
        assert seg_no_context.has_context is False

        seg_with_context = LogicalSegment.for_xlsx_cell(
            text="value",
            file_id="test",
            sheet="Sheet1",
            cell="A1",
            table_headers=["Column1"],
        )
        assert seg_with_context.has_context is True

    def test_context_labels(self) -> None:
        """Test aggregation of context labels."""
        seg = LogicalSegment.for_pptx_shape(
            text="3271051708990001",
            file_id="test",
            slide=1,
            shape_id="s1",
            char_map=CharMap(),
            slide_title="Patient Data",
            nearby_labels=["NIK", "Name"],
        )
        labels = seg.context_labels
        assert "Patient Data" in labels
        assert "NIK" in labels
        assert "Name" in labels

    def test_get_source_mappings_for_span(self) -> None:
        """Test getting source mappings for a detected span."""
        char_map, text = CharMap.from_runs([
            ("r1", "Email: "),
            ("r2", "satria@example.com"),
        ])
        seg = LogicalSegment.for_docx_paragraph(
            text=text,
            file_id="test",
            paragraph_index=0,
            char_map=char_map,
        )

        # Detected "satria@example.com" at positions 7-25
        mappings = seg.get_source_mappings_for_span(7, 25)
        assert len(mappings) == 1
        assert mappings[0] == ("r2", 0, 18)

    def test_get_text_slice(self) -> None:
        """Test getting a text slice."""
        seg = LogicalSegment.for_txt_paragraph(
            text="NIK: 3271051708990001",
            file_id="test",
            paragraph_index=0,
        )
        assert seg.get_text_slice(5, 21) == "3271051708990001"

    def test_get_context_window(self) -> None:
        """Test getting context around a span."""
        seg = LogicalSegment.for_txt_paragraph(
            text="Nama Lengkap: Satria Putra Yudistira adalah karyawan",
            file_id="test",
            paragraph_index=0,
        )
        before, after = seg.get_context_window(14, 36, window_size=10)
        assert before == " Lengkap: "  # 10 chars before position 14 (includes space)
        assert after == " adalah ka"   # 10 chars after position 36

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        seg = LogicalSegment.for_xlsx_cell(
            text="test@example.com",
            file_id="xlsx_001",
            sheet="Data",
            cell="B2",
            table_headers=["Name", "Email"],
        )
        d = seg.to_dict()
        assert d["text"] == "test@example.com"
        assert d["file_id"] == "xlsx_001"
        assert d["file_type"] == "xlsx"
        assert d["table_headers"] == ["Name", "Email"]
        assert "location" in d


# =============================================================================
# DocumentFormat Tests
# =============================================================================


class TestDocumentFormat:
    """Tests for DocumentFormat enum."""

    def test_from_extension(self) -> None:
        """Test getting format from extension."""
        assert DocumentFormat.from_extension("txt") == DocumentFormat.TXT
        assert DocumentFormat.from_extension(".docx") == DocumentFormat.DOCX
        assert DocumentFormat.from_extension("XLSX") == DocumentFormat.XLSX

    def test_from_extension_invalid(self) -> None:
        """Test that invalid extension raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported format"):
            DocumentFormat.from_extension("pdf")

    def test_from_path(self) -> None:
        """Test getting format from path."""
        assert DocumentFormat.from_path(Path("test.docx")) == DocumentFormat.DOCX
        assert DocumentFormat.from_path("data.csv") == DocumentFormat.CSV


# =============================================================================
# Replacement Tests
# =============================================================================


class TestReplacement:
    """Tests for Replacement dataclass."""

    def test_create_replacement(self) -> None:
        """Test creating a replacement."""
        rep = Replacement(
            segment_id="seg_001",
            logical_start=5,
            logical_end=21,
            original_text="3271051708990001",
            replacement_text="[NIK_001]",
            entity_type="NIK",
        )
        assert rep.original_length == 16
        assert rep.replacement_length == 9

    def test_get_padded_replacement(self) -> None:
        """Test getting padded replacement."""
        rep = Replacement(
            segment_id="seg_001",
            logical_start=0,
            logical_end=16,
            original_text="3271051708990001",
            replacement_text="[NIK]",
            entity_type="NIK",
            preserve_length=True,
        )
        padded = rep.get_padded_replacement()
        assert len(padded) == 16
        assert padded == "[NIK]           "

    def test_no_padding_when_not_requested(self) -> None:
        """Test that padding is not applied when not requested."""
        rep = Replacement(
            segment_id="seg_001",
            logical_start=0,
            logical_end=16,
            original_text="3271051708990001",
            replacement_text="[NIK]",
            entity_type="NIK",
            preserve_length=False,
        )
        assert rep.get_padded_replacement() == "[NIK]"


# =============================================================================
# ExtractionResult and ProtectionResult Tests
# =============================================================================


class TestExtractionResult:
    """Tests for ExtractionResult dataclass."""

    def test_create_extraction_result(self) -> None:
        """Test creating an extraction result."""
        segments = [
            LogicalSegment.for_txt_paragraph(
                text="Line 1", file_id="test", paragraph_index=0
            ),
            LogicalSegment.for_txt_paragraph(
                text="Line 2", file_id="test", paragraph_index=1
            ),
        ]
        result = ExtractionResult(
            segments=segments,
            file_id="test_001",
            file_path=Path("test.txt"),
            file_format=DocumentFormat.TXT,
            total_characters=12,
        )
        assert result.segment_count == 2
        assert result.has_warnings is False

    def test_extraction_result_with_warnings(self) -> None:
        """Test extraction result with warnings."""
        result = ExtractionResult(
            segments=[],
            file_id="test",
            file_path=Path("test.docx"),
            file_format=DocumentFormat.DOCX,
            extraction_warnings=["Skipped hidden content"],
        )
        assert result.has_warnings is True


class TestProtectionResult:
    """Tests for ProtectionResult dataclass."""

    def test_protection_success(self) -> None:
        """Test successful protection result."""
        result = ProtectionResult(
            output_path=Path("output.docx"),
            replacements_applied=5,
            replacements_failed=0,
            validation_passed=True,
        )
        assert result.success is True

    def test_protection_failure(self) -> None:
        """Test failed protection result."""
        result = ProtectionResult(
            output_path=Path("output.docx"),
            replacements_applied=3,
            replacements_failed=2,
            validation_passed=True,
        )
        assert result.success is False

    def test_protection_validation_failure(self) -> None:
        """Test protection with validation failure."""
        result = ProtectionResult(
            output_path=Path("output.docx"),
            replacements_applied=5,
            replacements_failed=0,
            validation_passed=False,
            validation_errors=["Document corrupted"],
        )
        assert result.success is False


# =============================================================================
# Exception Tests
# =============================================================================


class TestDocumentExceptions:
    """Tests for document-related exceptions."""

    def test_extraction_error(self) -> None:
        """Test DocumentExtractionError."""
        error = DocumentExtractionError(
            "Failed to read file",
            file_path=Path("test.docx"),
        )
        assert "Failed to read file" in str(error)
        assert error.file_path == Path("test.docx")

    def test_protection_error(self) -> None:
        """Test DocumentProtectionError."""
        failed = [
            Replacement(
                segment_id="s1",
                logical_start=0,
                logical_end=10,
                original_text="test",
                replacement_text="[TOKEN]",
                entity_type="TEST",
            )
        ]
        error = DocumentProtectionError(
            "Failed to apply replacement",
            failed_replacements=failed,
        )
        assert len(error.failed_replacements) == 1

    def test_validation_error(self) -> None:
        """Test DocumentValidationError."""
        error = DocumentValidationError(
            "Invalid document",
            validation_errors=["Missing content", "Corrupted XML"],
        )
        assert len(error.validation_errors) == 2
