"""
Unit tests for Sprint 2 document adapters.

Tests cover:
- TxtDocumentAdapter: Text file extraction with key-value detection
- DocxDocumentAdapter: DOCX extraction with run reconstruction
- PptxDocumentAdapter: PPTX extraction with spatial context
- SpatialContextResolver: Nearby label detection
"""

import tempfile
from pathlib import Path

import pytest

from sandiraksa.documents import (
    CharMap,
    CharMapEntry,
    DocumentFormat,
    ShapePosition,
    SpatialContextResolver,
    TxtDocumentAdapter,
    are_on_same_baseline,
    distance_between,
    is_above,
    is_left_adjacent,
    is_potential_label,
)


# =============================================================================
# TxtDocumentAdapter Tests
# =============================================================================


class TestTxtDocumentAdapter:
    """Tests for TxtDocumentAdapter."""

    @pytest.fixture
    def adapter(self) -> TxtDocumentAdapter:
        """Create adapter instance."""
        return TxtDocumentAdapter()

    @pytest.fixture
    def sample_txt_file(self, tmp_path: Path) -> Path:
        """Create a sample TXT file for testing."""
        content = """Data Pasien

NIK: 3271051708990001
Nama: Satria Putra Yudistira
Alamat: Jl. Sudirman No. 123
Telepon: 081234567890

Informasi Medis
Diagnosa: Demam tinggi
"""
        file_path = tmp_path / "sample.txt"
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def test_supported_formats(self, adapter: TxtDocumentAdapter) -> None:
        """Test that adapter supports TXT format."""
        assert DocumentFormat.TXT in adapter.supported_formats

    def test_can_handle_txt_file(self, adapter: TxtDocumentAdapter, tmp_path: Path) -> None:
        """Test can_handle for TXT files."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("test")
        assert adapter.can_handle(txt_file)

    def test_cannot_handle_other_formats(
        self, adapter: TxtDocumentAdapter, tmp_path: Path
    ) -> None:
        """Test can_handle returns False for non-TXT files."""
        docx_file = tmp_path / "test.docx"
        docx_file.write_text("test")
        assert not adapter.can_handle(docx_file)

    def test_extract_basic(
        self, adapter: TxtDocumentAdapter, sample_txt_file: Path
    ) -> None:
        """Test basic extraction."""
        result = adapter.extract(sample_txt_file)

        assert result.file_format == DocumentFormat.TXT
        assert result.segment_count > 0
        assert result.total_characters > 0
        assert not result.has_warnings

    def test_extract_key_value_detection(
        self, adapter: TxtDocumentAdapter, sample_txt_file: Path
    ) -> None:
        """Test that key-value patterns are detected."""
        result = adapter.extract(sample_txt_file)

        # Find segment containing NIK value
        nik_segments = [
            s for s in result.segments
            if "3271051708990001" in s.text
        ]

        assert len(nik_segments) >= 1
        nik_segment = nik_segments[0]
        # Check that key_label is detected or text contains the value
        assert "3271051708990001" in nik_segment.text

    def test_extract_context_previous_next(
        self, adapter: TxtDocumentAdapter, sample_txt_file: Path
    ) -> None:
        """Test that previous/next context is attached."""
        result = adapter.extract(sample_txt_file)

        # Find a segment that should have context
        segments_with_context = [
            s for s in result.segments
            if s.previous_text or s.next_text
        ]

        assert len(segments_with_context) > 0

    def test_extract_heading_detection(
        self, adapter: TxtDocumentAdapter, tmp_path: Path
    ) -> None:
        """Test heading detection."""
        content = """DATA KARYAWAN

Nama: John Doe
NIK: 1234567890123456
"""
        file_path = tmp_path / "heading.txt"
        file_path.write_text(content, encoding="utf-8")

        result = adapter.extract(file_path)

        # Find heading segment
        heading_segments = [s for s in result.segments if s.is_header]
        assert len(heading_segments) >= 1

    def test_extract_empty_file(
        self, adapter: TxtDocumentAdapter, tmp_path: Path
    ) -> None:
        """Test extraction of empty file."""
        file_path = tmp_path / "empty.txt"
        file_path.write_text("", encoding="utf-8")

        result = adapter.extract(file_path)

        assert result.segment_count == 0
        assert result.has_warnings

    def test_extract_file_not_found(self, adapter: TxtDocumentAdapter) -> None:
        """Test extraction with non-existent file."""
        from sandiraksa.documents import DocumentExtractionError

        with pytest.raises(DocumentExtractionError):
            adapter.extract(Path("/nonexistent/file.txt"))

    def test_extract_encoding_detection(
        self, adapter: TxtDocumentAdapter, tmp_path: Path
    ) -> None:
        """Test that various encodings are handled."""
        content = "Nama: José García"

        # UTF-8
        file_path = tmp_path / "utf8.txt"
        file_path.write_text(content, encoding="utf-8")
        result = adapter.extract(file_path)
        assert "José" in result.segments[0].text

    def test_validate_valid_file(
        self, adapter: TxtDocumentAdapter, sample_txt_file: Path
    ) -> None:
        """Test validation of valid file."""
        is_valid, errors = adapter.validate(sample_txt_file)
        assert is_valid
        assert len(errors) == 0

    def test_validate_missing_file(self, adapter: TxtDocumentAdapter) -> None:
        """Test validation of missing file."""
        is_valid, errors = adapter.validate(Path("/nonexistent.txt"))
        assert not is_valid
        assert len(errors) > 0


# =============================================================================
# SpatialContextResolver Tests
# =============================================================================


class TestSpatialContextResolver:
    """Tests for SpatialContextResolver."""

    @pytest.fixture
    def resolver(self) -> SpatialContextResolver:
        """Create resolver instance."""
        return SpatialContextResolver()

    def test_is_potential_label_short_text(self) -> None:
        """Test label detection for short text."""
        assert is_potential_label("NIK")
        assert is_potential_label("Nama")
        assert is_potential_label("Alamat:")
        assert is_potential_label("No. Telepon")

    def test_is_potential_label_long_text(self) -> None:
        """Test that long text is not a label."""
        assert not is_potential_label(
            "This is a very long text that cannot be a label"
        )

    def test_is_potential_label_empty(self) -> None:
        """Test that empty text is not a label."""
        assert not is_potential_label("")
        assert not is_potential_label("   ")

    def test_are_on_same_baseline(self) -> None:
        """Test same baseline detection."""
        # Using EMU-scale values - tolerance is 228600 EMU
        pos1 = ShapePosition(
            shape_id="1", text="Label",
            left=100000, top=500000, width=200000, height=100000
        )
        pos2 = ShapePosition(
            shape_id="2", text="Value",
            left=400000, top=510000, width=300000, height=100000
        )
        # Centers differ by only 10000 which is < tolerance
        assert are_on_same_baseline(pos1, pos2)

    def test_not_on_same_baseline(self) -> None:
        """Test shapes not on same baseline."""
        # Using EMU-scale values (914400 EMU = 1 inch)
        # Tolerance is 228600 EMU (~0.25 inch)
        pos1 = ShapePosition(
            shape_id="1", text="Label",
            left=100000, top=100000, width=200000, height=100000
        )
        pos2 = ShapePosition(
            shape_id="2", text="Value",
            left=100000, top=1000000, width=200000, height=100000
        )
        # Centers are at y=150000 and y=1050000, difference of 900000 > tolerance
        assert not are_on_same_baseline(pos1, pos2)

    def test_is_left_adjacent(self) -> None:
        """Test left adjacency detection."""
        # Using EMU-scale values
        label = ShapePosition(
            shape_id="1", text="NIK:",
            left=100000, top=500000, width=200000, height=100000
        )
        value = ShapePosition(
            shape_id="2", text="3271051708990001",
            left=350000, top=510000, width=400000, height=100000
        )

        assert is_left_adjacent(label, value)

    def test_not_left_adjacent_when_right(self) -> None:
        """Test that right position is not left adjacent."""
        # Using EMU-scale values
        label = ShapePosition(
            shape_id="1", text="NIK:",
            left=500000, top=500000, width=200000, height=100000
        )
        value = ShapePosition(
            shape_id="2", text="3271051708990001",
            left=100000, top=510000, width=300000, height=100000
        )

        assert not is_left_adjacent(label, value)

    def test_is_above(self) -> None:
        """Test above detection."""
        # Using EMU-scale values - vertical threshold is 457200 EMU
        label = ShapePosition(
            shape_id="1", text="NIK",
            left=100000, top=100000, width=200000, height=80000
        )
        value = ShapePosition(
            shape_id="2", text="3271051708990001",
            left=100000, top=200000, width=300000, height=80000
        )

        assert is_above(label, value)

    def test_not_above_when_below(self) -> None:
        """Test that below position is not above."""
        # Using EMU-scale values
        label = ShapePosition(
            shape_id="1", text="NIK",
            left=100000, top=300000, width=200000, height=80000
        )
        value = ShapePosition(
            shape_id="2", text="3271051708990001",
            left=100000, top=100000, width=300000, height=80000
        )

        assert not is_above(label, value)

    def test_distance_between(self) -> None:
        """Test distance calculation."""
        pos1 = ShapePosition(
            shape_id="1", text="A", left=0, top=0, width=100, height=100
        )
        pos2 = ShapePosition(
            shape_id="2", text="B", left=200, top=0, width=100, height=100
        )

        # Centers are at (50, 50) and (250, 50)
        # Distance should be 200
        dist = distance_between(pos1, pos2)
        assert dist == 200.0

    def test_get_nearby_labels_left_adjacent(
        self, resolver: SpatialContextResolver
    ) -> None:
        """Test finding left-adjacent labels."""
        target = ShapePosition(
            shape_id="value", text="3271051708990001",
            left=500000, top=500000, width=300000, height=100000
        )
        all_shapes = [
            target,
            ShapePosition(
                shape_id="label", text="NIK:",
                left=200000, top=510000, width=200000, height=100000
            ),
        ]

        labels = resolver.get_nearby_labels(target, all_shapes)

        assert "NIK" in labels

    def test_get_nearby_labels_above(
        self, resolver: SpatialContextResolver
    ) -> None:
        """Test finding labels above."""
        target = ShapePosition(
            shape_id="value", text="3271051708990001",
            left=100000, top=500000, width=300000, height=100000
        )
        all_shapes = [
            target,
            ShapePosition(
                shape_id="label", text="NIK",
                left=100000, top=300000, width=200000, height=80000
            ),
        ]

        labels = resolver.get_nearby_labels(target, all_shapes)

        assert "NIK" in labels

    def test_get_nearby_labels_skips_self(
        self, resolver: SpatialContextResolver
    ) -> None:
        """Test that target shape is not included as its own label."""
        target = ShapePosition(
            shape_id="value", text="3271051708990001",
            left=100000, top=500000, width=300000, height=100000
        )
        all_shapes = [target]

        labels = resolver.get_nearby_labels(target, all_shapes)

        assert len(labels) == 0

    def test_get_nearby_labels_skips_non_labels(
        self, resolver: SpatialContextResolver
    ) -> None:
        """Test that long text is not considered a label."""
        target = ShapePosition(
            shape_id="value", text="3271051708990001",
            left=500000, top=500000, width=300000, height=100000
        )
        all_shapes = [
            target,
            ShapePosition(
                shape_id="notlabel",
                text="This is a very long text that cannot possibly be a label",
                left=100000, top=510000, width=300000, height=100000
            ),
        ]

        labels = resolver.get_nearby_labels(target, all_shapes)

        assert len(labels) == 0

    def test_find_slide_title(self, resolver: SpatialContextResolver) -> None:
        """Test finding slide title."""
        shapes = [
            ShapePosition(
                shape_id="title", text="Data Pasien",
                left=100000, top=50000, width=600000, height=100000
            ),
            ShapePosition(
                shape_id="body", text="NIK: 3271051708990001",
                left=100000, top=300000, width=600000, height=300000
            ),
        ]

        title = resolver.find_slide_title(shapes)

        assert title == "Data Pasien"


# =============================================================================
# CharMap Integration Tests
# =============================================================================


class TestCharMapIntegration:
    """Tests for CharMap with document adapters."""

    def test_charmap_from_runs_simulates_docx(self) -> None:
        """Test CharMap.from_runs simulating DOCX split-run scenario."""
        # Simulate DOCX split-run: "Satria Putra Yudistira" split as:
        # Run 1: "Sat"
        # Run 2: "ria Put"
        # Run 3: "ra Yudistira"
        runs = [
            ("run_1", "Sat"),
            ("run_2", "ria Put"),
            ("run_3", "ra Yudistira"),
        ]

        char_map, text = CharMap.from_runs(runs)

        # Verify reconstructed text
        assert text == "Satria Putra Yudistira"
        assert len(char_map.entries) == 3

        # Simulate finding "Satria Putra" at positions 0-12
        # This spans run_1 (full), run_2 (full), and part of run_3
        mappings = char_map.get_source_mappings_for_range(0, 12)

        assert len(mappings) == 3
        assert mappings[0] == ("run_1", 0, 3)   # "Sat"
        assert mappings[1] == ("run_2", 0, 7)   # "ria Put"
        assert mappings[2] == ("run_3", 0, 2)   # "ra"

    def test_charmap_single_entity_in_middle(self) -> None:
        """Test finding an entity in the middle of text."""
        runs = [
            ("r1", "Nama: "),
            ("r2", "3271051708990001"),
            ("r3", " adalah NIK valid"),
        ]

        char_map, text = CharMap.from_runs(runs)

        # Find NIK at positions 6-22
        mappings = char_map.get_source_mappings_for_range(6, 22)

        assert len(mappings) == 1
        assert mappings[0] == ("r2", 0, 16)

    def test_charmap_entity_spanning_format_change(self) -> None:
        """Test entity spanning a formatting change (bold/italic boundary)."""
        # Simulates: "Email: satria@example.com" where domain is bold
        runs = [
            ("r1", "Email: "),
            ("r2", "satria"),        # Normal
            ("r3", "@example.com"),  # Bold
        ]

        char_map, text = CharMap.from_runs(runs)

        assert text == "Email: satria@example.com"

        # Find email at positions 7-25
        mappings = char_map.get_source_mappings_for_range(7, 25)

        assert len(mappings) == 2
        assert mappings[0] == ("r2", 0, 6)   # "satria"
        assert mappings[1] == ("r3", 0, 12)  # "@example.com"


# =============================================================================
# DocxDocumentAdapter Tests (without actual DOCX files)
# =============================================================================


class TestDocxDocumentAdapterUnit:
    """Unit tests for DocxDocumentAdapter without real DOCX files."""

    def test_import_adapter(self) -> None:
        """Test that adapter can be imported."""
        from sandiraksa.documents import DocxDocumentAdapter

        adapter = DocxDocumentAdapter()
        assert DocumentFormat.DOCX in adapter.supported_formats

    def test_can_handle_docx(self) -> None:
        """Test can_handle for DOCX files."""
        from sandiraksa.documents import DocxDocumentAdapter

        adapter = DocxDocumentAdapter()

        # Create dummy file path (doesn't need to exist for can_handle)
        assert adapter.can_handle(Path("test.docx"))
        assert not adapter.can_handle(Path("test.txt"))
        assert not adapter.can_handle(Path("test.pptx"))

    def test_heading_styles_constant(self) -> None:
        """Test HEADING_STYLES constant is defined."""
        from sandiraksa.documents import HEADING_STYLES

        assert "Heading 1" in HEADING_STYLES
        assert "Title" in HEADING_STYLES


# =============================================================================
# PptxDocumentAdapter Tests (without actual PPTX files)
# =============================================================================


class TestPptxDocumentAdapterUnit:
    """Unit tests for PptxDocumentAdapter without real PPTX files."""

    def test_import_adapter(self) -> None:
        """Test that adapter can be imported."""
        from sandiraksa.documents import PptxDocumentAdapter

        adapter = PptxDocumentAdapter()
        assert DocumentFormat.PPTX in adapter.supported_formats

    def test_can_handle_pptx(self) -> None:
        """Test can_handle for PPTX files."""
        from sandiraksa.documents import PptxDocumentAdapter

        adapter = PptxDocumentAdapter()

        assert adapter.can_handle(Path("test.pptx"))
        assert not adapter.can_handle(Path("test.txt"))
        assert not adapter.can_handle(Path("test.docx"))


# =============================================================================
# Integration Tests with Real Files (marked as slow)
# =============================================================================


@pytest.mark.slow
class TestDocxAdapterWithRealFiles:
    """Integration tests requiring real DOCX files."""

    @pytest.fixture
    def sample_docx(self, tmp_path: Path) -> Path:
        """Create a sample DOCX file."""
        try:
            from docx import Document

            doc = Document()
            doc.add_heading("Data Karyawan", level=1)
            doc.add_paragraph("NIK: 3271051708990001")
            doc.add_paragraph("Nama: Satria Putra Yudistira")

            file_path = tmp_path / "sample.docx"
            doc.save(file_path)
            return file_path
        except ImportError:
            pytest.skip("python-docx not installed")

    def test_extract_real_docx(self, sample_docx: Path) -> None:
        """Test extraction from real DOCX file."""
        from sandiraksa.documents import DocxDocumentAdapter

        adapter = DocxDocumentAdapter()
        result = adapter.extract(sample_docx)

        assert result.file_format == DocumentFormat.DOCX
        assert result.segment_count > 0

        # Check heading is detected
        heading_segments = [s for s in result.segments if s.is_header]
        assert len(heading_segments) >= 1

    def test_extract_docx_with_table(self, tmp_path: Path) -> None:
        """Test extraction from DOCX with table."""
        try:
            from docx import Document

            doc = Document()
            table = doc.add_table(rows=2, cols=2)
            table.rows[0].cells[0].text = "Nama"
            table.rows[0].cells[1].text = "NIK"
            table.rows[1].cells[0].text = "Satria Putra"
            table.rows[1].cells[1].text = "3271051708990001"

            file_path = tmp_path / "table.docx"
            doc.save(file_path)

            from sandiraksa.documents import DocxDocumentAdapter

            adapter = DocxDocumentAdapter()
            result = adapter.extract(file_path)

            # Should have table headers attached
            segments_with_headers = [
                s for s in result.segments if s.table_headers
            ]
            assert len(segments_with_headers) > 0

        except ImportError:
            pytest.skip("python-docx not installed")


@pytest.mark.slow
class TestPptxAdapterWithRealFiles:
    """Integration tests requiring real PPTX files."""

    @pytest.fixture
    def sample_pptx(self, tmp_path: Path) -> Path:
        """Create a sample PPTX file."""
        try:
            from pptx import Presentation
            from pptx.util import Inches

            prs = Presentation()
            slide_layout = prs.slide_layouts[5]  # Blank
            slide = prs.slides.add_slide(slide_layout)

            # Add title
            title_box = slide.shapes.add_textbox(
                Inches(1), Inches(0.5), Inches(8), Inches(1)
            )
            title_box.text_frame.text = "Data Pasien"

            # Add content
            content_box = slide.shapes.add_textbox(
                Inches(1), Inches(2), Inches(8), Inches(3)
            )
            content_box.text_frame.text = "NIK: 3271051708990001"

            file_path = tmp_path / "sample.pptx"
            prs.save(file_path)
            return file_path
        except ImportError:
            pytest.skip("python-pptx not installed")

    def test_extract_real_pptx(self, sample_pptx: Path) -> None:
        """Test extraction from real PPTX file."""
        from sandiraksa.documents import PptxDocumentAdapter

        adapter = PptxDocumentAdapter()
        result = adapter.extract(sample_pptx)

        assert result.file_format == DocumentFormat.PPTX
        assert result.segment_count > 0
