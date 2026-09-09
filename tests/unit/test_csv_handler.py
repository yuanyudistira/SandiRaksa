"""Tests for CSV handler."""

import tempfile
from pathlib import Path

import pytest

from sandiraksa.documents.csv_handler import (
    CSVHandler,
    CSVMetadata,
    CSVReader,
    CSVWriter,
    DelimiterDetector,
    EncodingDetector,
)


@pytest.fixture
def sample_csv_path():
    """Create a sample CSV file."""
    content = """name,email,phone
John Doe,john@example.com,08123456789
Jane Smith,jane@test.org,+62-812-345-6789
Bob Wilson,bob@company.co.id,021-1234567
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(content)
        return Path(f.name)


@pytest.fixture
def sample_csv_semicolon():
    """Create a semicolon-delimited CSV file."""
    content = """name;email;amount
John;john@test.com;1000
Jane;jane@test.com;2000
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(content)
        return Path(f.name)


@pytest.fixture
def sample_csv_utf8_bom():
    """Create a UTF-8 with BOM CSV file."""
    content = "name,value\nTest,123\n"
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as f:
        # Write UTF-8 BOM
        f.write(b"\xef\xbb\xbf")
        f.write(content.encode("utf-8"))
        return Path(f.name)


class TestEncodingDetector:
    """Tests for EncodingDetector."""

    def test_detect_utf8(self, sample_csv_path):
        """Should detect UTF-8 encoding."""
        encoding = EncodingDetector.detect(sample_csv_path)
        assert encoding.lower() in {"utf-8", "ascii", "utf-8-sig"}

    def test_detect_utf8_bom(self, sample_csv_utf8_bom):
        """Should detect UTF-8 with BOM."""
        encoding = EncodingDetector.detect(sample_csv_utf8_bom)
        assert encoding == "utf-8-sig"


class TestDelimiterDetector:
    """Tests for DelimiterDetector."""

    def test_detect_comma(self):
        """Should detect comma delimiter."""
        sample = "a,b,c\n1,2,3\n4,5,6"
        delimiter = DelimiterDetector.detect(sample)
        assert delimiter == ","

    def test_detect_semicolon(self):
        """Should detect semicolon delimiter."""
        sample = "a;b;c\n1;2;3\n4;5;6"
        delimiter = DelimiterDetector.detect(sample)
        assert delimiter == ";"

    def test_detect_tab(self):
        """Should detect tab delimiter."""
        sample = "a\tb\tc\n1\t2\t3\n4\t5\t6"
        delimiter = DelimiterDetector.detect(sample)
        assert delimiter == "\t"

    def test_detect_pipe(self):
        """Should detect pipe delimiter."""
        sample = "a|b|c\n1|2|3\n4|5|6"
        delimiter = DelimiterDetector.detect(sample)
        assert delimiter == "|"


class TestCSVReader:
    """Tests for CSVReader."""

    def test_detect_metadata(self, sample_csv_path):
        """Should detect CSV metadata correctly."""
        reader = CSVReader(sample_csv_path)
        metadata = reader.detect_metadata()

        assert metadata.encoding.lower() in {"utf-8", "ascii", "utf-8-sig"}
        assert metadata.delimiter == ","
        assert metadata.has_header is True
        assert metadata.row_count == 4  # Header + 3 data rows
        assert metadata.column_count == 3
        assert metadata.headers == ["name", "email", "phone"]

    def test_detect_semicolon_delimiter(self, sample_csv_semicolon):
        """Should detect semicolon delimiter."""
        reader = CSVReader(sample_csv_semicolon)
        metadata = reader.detect_metadata()

        assert metadata.delimiter == ";"
        assert metadata.headers == ["name", "email", "amount"]

    def test_iter_cells(self, sample_csv_path):
        """Should iterate over cells."""
        reader = CSVReader(sample_csv_path)
        cells = list(reader.iter_cells())

        # 3 rows * 3 columns = 9 cells
        assert len(cells) == 9

        # Check first cell
        assert cells[0].row == 0
        assert cells[0].column == 0
        assert cells[0].column_name == "name"
        assert cells[0].value == "John Doe"

        # Check email column
        emails = [c.value for c in cells if c.column_name == "email"]
        assert "john@example.com" in emails
        assert "jane@test.org" in emails

    def test_iter_cells_filter_columns(self, sample_csv_path):
        """Should filter columns when specified."""
        reader = CSVReader(sample_csv_path)
        cells = list(reader.iter_cells(columns=[1]))  # Only email column

        assert len(cells) == 3
        assert all(c.column == 1 for c in cells)
        assert all(c.column_name == "email" for c in cells)

    def test_iter_rows(self, sample_csv_path):
        """Should iterate over rows."""
        reader = CSVReader(sample_csv_path)
        rows = list(reader.iter_rows())

        assert len(rows) == 3  # 3 data rows (header skipped)

        # Check first row
        row_idx, values = rows[0]
        assert row_idx == 0
        assert values == ["John Doe", "john@example.com", "08123456789"]

    def test_cell_location(self, sample_csv_path):
        """Should generate correct DocumentLocation."""
        reader = CSVReader(sample_csv_path)
        cells = list(reader.iter_cells())

        loc = cells[0].to_location("file1")
        assert loc.component_type == "cell"
        assert loc.cell_address == "R1C1"


class TestCSVWriter:
    """Tests for CSVWriter."""

    def test_write_basic(self, sample_csv_path):
        """Should write CSV file."""
        reader = CSVReader(sample_csv_path)

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            output_path = Path(f.name)

        writer = CSVWriter(output_path)
        rows_written = writer.write_from_reader(reader)

        assert rows_written == 4  # Header + 3 data rows
        assert output_path.exists()

        # Verify content
        with open(output_path) as f:
            content = f.read()
        assert "John Doe" in content
        assert "john@example.com" in content

    def test_write_with_transform(self, sample_csv_path):
        """Should apply transformation during write."""
        reader = CSVReader(sample_csv_path)

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            output_path = Path(f.name)

        # Transform: replace email column
        def transform(row, col, value):
            if col == 1 and row > 0:  # Skip header row
                return "[REDACTED]"
            return value

        writer = CSVWriter(output_path)
        writer.write_from_reader(reader, transform)

        # Verify transformation
        with open(output_path) as f:
            content = f.read()

        assert "[REDACTED]" in content
        assert "john@example.com" not in content


class TestCSVHandler:
    """Tests for CSVHandler high-level API."""

    def test_open_and_get_segments(self, sample_csv_path):
        """Should open file and get text segments."""
        handler = CSVHandler()
        metadata = handler.open(sample_csv_path)

        assert metadata.row_count == 4
        assert metadata.column_count == 3

        # Get all segments
        all_segments = []
        for batch in handler.get_text_segments(batch_size=100):
            all_segments.extend(batch)

        # Should have 9 cells (3 rows * 3 columns)
        assert len(all_segments) == 9

        # Verify segment content
        texts = [s.text for s in all_segments]
        assert "John Doe" in texts
        assert "john@example.com" in texts

        handler.close()

    def test_create_treated_file(self, sample_csv_path):
        """Should create treated file with replacements."""
        handler = CSVHandler()
        handler.open(sample_csv_path)

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            output_path = Path(f.name)

        # Replace specific cells
        treatments = {
            (0, 1): "[[EMAIL_ABC123]]",  # Replace john@example.com
            (1, 1): "[[EMAIL_DEF456]]",  # Replace jane@test.org
        }

        result_path = handler.create_treated_file(output_path, treatments)

        # Verify
        with open(result_path) as f:
            content = f.read()

        assert "[[EMAIL_ABC123]]" in content
        assert "[[EMAIL_DEF456]]" in content
        assert "john@example.com" not in content
        assert "Jane Smith" in content  # Name should be preserved

        handler.close()

    def test_is_csv_file(self):
        """Should identify CSV files."""
        assert CSVHandler.is_csv_file("data.csv") is True
        assert CSVHandler.is_csv_file("data.CSV") is True
        assert CSVHandler.is_csv_file("data.tsv") is True
        assert CSVHandler.is_csv_file("data.txt") is True
        assert CSVHandler.is_csv_file("data.xlsx") is False
        assert CSVHandler.is_csv_file("data.docx") is False

    def test_batch_processing(self, sample_csv_path):
        """Should yield batches correctly."""
        handler = CSVHandler()
        handler.open(sample_csv_path)

        # Small batch size to test batching
        batches = list(handler.get_text_segments(batch_size=2))

        # 9 cells with batch size 2 = 5 batches
        assert len(batches) == 5
        assert len(batches[0]) == 2
        assert len(batches[-1]) == 1  # Last batch has 1 cell

        handler.close()
