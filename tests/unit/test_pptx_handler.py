"""Tests for PPTX handler."""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from sandiraksa.documents.pptx_handler import (
    PPTXHandler,
    PPTXReader,
    PPTXWriter,
    PPTXMetadata,
    ShapeInfo,
    TableCellInfo,
    SlideNotesInfo,
    SlideInventory,
    PresentationInventory,
    PPTXHandlerError,
    PresentationOpenError,
)


class TestShapeInfo:
    """Tests for ShapeInfo dataclass."""

    def test_create(self):
        """Should create shape info."""
        shape = ShapeInfo(
            slide_number=1,
            shape_id=12345,
            shape_type="text_box",
            text="Hello World",
        )
        assert shape.slide_number == 1
        assert shape.shape_id == 12345
        assert shape.text == "Hello World"

    def test_to_location(self):
        """Should convert to DocumentLocation."""
        shape = ShapeInfo(
            slide_number=3,
            shape_id=999,
            shape_type="placeholder",
            text="Test",
        )
        loc = shape.to_location("file-123")
        assert loc.file_id == "file-123"
        assert loc.component_type == "shape"
        assert loc.slide_number == 3


class TestTableCellInfo:
    """Tests for TableCellInfo dataclass."""

    def test_to_location(self):
        """Should convert to DocumentLocation."""
        cell = TableCellInfo(
            slide_number=2,
            shape_id=456,
            row_index=1,
            column_index=2,
            text="Cell content",
        )
        loc = cell.to_location()
        assert loc.component_type == "table_cell"
        assert loc.slide_number == 2


class TestSlideNotesInfo:
    """Tests for SlideNotesInfo dataclass."""

    def test_to_location(self):
        """Should convert to DocumentLocation."""
        notes = SlideNotesInfo(
            slide_number=5,
            text="Speaker notes here",
        )
        loc = notes.to_location()
        assert loc.component_type == "notes"
        assert loc.slide_number == 5


class TestPPTXHandler:
    """Tests for high-level PPTXHandler."""

    def test_file_format(self):
        """Should return PPTX format."""
        from sandiraksa.domain.file_record import FileFormat
        
        handler = PPTXHandler(Path("test.pptx"))
        assert handler.file_format == FileFormat.PPTX

    def test_default_output_path(self):
        """Should generate _protected suffix."""
        handler = PPTXHandler(Path("/path/to/presentation.pptx"))
        output = handler._get_default_output_path()
        assert output == Path("/path/to/presentation_protected.pptx")


class TestIntegration:
    """Integration tests requiring actual PPTX files."""

    @pytest.fixture
    def sample_pptx(self):
        """Create a sample PPTX file."""
        try:
            from pptx import Presentation
            from pptx.util import Inches, Pt
        except ImportError:
            pytest.skip("python-pptx not installed")

        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.pptx"
            
            prs = Presentation()
            
            # Slide 1: Title slide
            slide_layout = prs.slide_layouts[0]  # Title slide layout
            slide1 = prs.slides.add_slide(slide_layout)
            title = slide1.shapes.title
            subtitle = slide1.placeholders[1]
            title.text = "John Doe Presentation"
            subtitle.text = "Contact: john@example.com"
            
            # Slide 2: Content with text box
            slide_layout2 = prs.slide_layouts[5]  # Blank layout
            slide2 = prs.slides.add_slide(slide_layout2)
            
            # Add text box
            left = Inches(1)
            top = Inches(1)
            width = Inches(4)
            height = Inches(1)
            txBox = slide2.shapes.add_textbox(left, top, width, height)
            tf = txBox.text_frame
            tf.text = "Phone: +62812345678"
            
            # Slide 3: Table
            slide_layout3 = prs.slide_layouts[5]
            slide3 = prs.slides.add_slide(slide_layout3)
            
            # Add table
            rows, cols = 2, 2
            left = Inches(1)
            top = Inches(1)
            width = Inches(6)
            height = Inches(1)
            table = slide3.shapes.add_table(rows, cols, left, top, width, height).table
            table.cell(0, 0).text = "Name"
            table.cell(0, 1).text = "Email"
            table.cell(1, 0).text = "Jane Smith"
            table.cell(1, 1).text = "jane@example.com"
            
            prs.save(path)
            
            yield path

    def test_read_shapes(self, sample_pptx):
        """Should read shapes from file."""
        handler = PPTXHandler(sample_pptx)
        
        shapes = list(handler.iter_shapes())
        
        # Should have shapes from slides
        assert len(shapes) >= 2
        
        # Check text content
        texts = [s.text for s in shapes]
        assert any("John Doe" in t for t in texts)

    def test_get_inventory(self, sample_pptx):
        """Should get presentation inventory."""
        handler = PPTXHandler(sample_pptx)
        
        inventory = handler.get_inventory()
        
        assert inventory.metadata.slide_count == 3
        assert len(inventory.slides) == 3

    def test_get_metadata(self, sample_pptx):
        """Should get presentation metadata."""
        handler = PPTXHandler(sample_pptx)
        
        metadata = handler.get_metadata()
        
        assert metadata.slide_count == 3

    def test_iter_text_segments(self, sample_pptx):
        """Should iterate text segments."""
        handler = PPTXHandler(sample_pptx)
        
        segments = list(handler.iter_text_segments())
        
        # Should have segments for shapes and table cells
        assert len(segments) >= 4
        
        # Check segment content
        texts = [s.text for s in segments]
        assert any("john@example.com" in t for t in texts)

    def test_apply_treatments(self, sample_pptx):
        """Should apply treatments and save."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.pptx"
            
            # First, find the shape ID for John Doe
            handler = PPTXHandler(sample_pptx)
            shapes = list(handler.iter_shapes())
            
            john_shape = next(
                (s for s in shapes if "John Doe" in s.text),
                None
            )
            assert john_shape is not None
            
            treatments = [
                {
                    "slide_number": john_shape.slide_number,
                    "shape_id": john_shape.shape_id,
                    "old_text": "John Doe",
                    "new_text": "[[PERSON_ABC123]]",
                    "component_type": "shape",
                },
            ]
            
            result_path, modified = handler.apply_treatments(
                treatments,
                output_path=output_path,
            )
            
            assert result_path == output_path
            assert modified == 1
            assert output_path.exists()
            
            # Verify modifications
            from pptx import Presentation
            prs = Presentation(output_path)
            
            # Check that token is in the presentation
            found_token = False
            for slide in prs.slides:
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        if "[[PERSON_ABC123]]" in shape.text_frame.text:
                            found_token = True
                            break
            
            assert found_token, "Token not found in modified presentation"

    def test_read_table_cells(self, sample_pptx):
        """Should read table cells."""
        with PPTXReader(sample_pptx) as reader:
            cells = list(reader.iter_table_cells())
            
            # Should have 4 cells (2x2 table)
            assert len(cells) == 4
            
            # Check content
            texts = [c.text for c in cells]
            assert "Jane Smith" in texts
            assert "jane@example.com" in texts
