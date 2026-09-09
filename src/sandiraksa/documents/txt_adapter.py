"""
TXT Document Adapter for SandiRaksa.

Extracts text content from plain text files and produces LogicalSegments
for the unified detection pipeline.

Key Features:
- Paragraph-based segmentation
- Key-value pattern detection (e.g., "NIK: 327105...")
- Context from surrounding paragraphs
- Encoding auto-detection
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from sandiraksa.documents.base import (
    BaseDocumentAdapter,
    DocumentExtractionError,
    DocumentFormat,
    DocumentProtectionError,
    ExtractionResult,
    ProtectionResult,
    Replacement,
)
from sandiraksa.documents.char_map import CharMap, CharMapEntry
from sandiraksa.documents.logical_segment import LogicalSegment

logger = logging.getLogger(__name__)


# Common key-value separators in Indonesian documents
KEY_VALUE_SEPARATORS = re.compile(r'^(.{1,30}?)\s*[:=|]\s*(.+)$')

# Common Indonesian labels that indicate PII fields
INDONESIAN_LABELS = {
    'nama', 'nama lengkap', 'nama pasien', 'nama karyawan', 'nama pelanggan',
    'nik', 'no ktp', 'nomor ktp', 'no. ktp',
    'npwp', 'no npwp', 'nomor npwp',
    'kk', 'no kk', 'nomor kk', 'kartu keluarga',
    'alamat', 'address', 'domisili',
    'telepon', 'telp', 'no telp', 'no hp', 'nomor hp', 'phone', 'handphone',
    'email', 'e-mail', 'surel',
    'tanggal lahir', 'tgl lahir', 'ttl', 'tempat lahir',
    'jenis kelamin', 'gender',
    'pekerjaan', 'occupation',
    'agama', 'religion',
    'no rekening', 'nomor rekening', 'bank account',
    'bpjs', 'no bpjs',
    'sim', 'no sim',
    'paspor', 'passport', 'no paspor',
}


class TxtDocumentAdapter(BaseDocumentAdapter):
    """
    Document adapter for plain text (TXT) files.

    Extracts content as LogicalSegments, with each paragraph becoming
    a separate segment. Supports key-value pattern detection to provide
    context for PII detection.

    Example:
        Input text:
            Data Pasien
            NIK: 3271051708990001
            Nama: Satria Putra Yudistira

        Output segments:
            - Segment 1: "Data Pasien" (heading hint)
            - Segment 2: "3271051708990001" (key_label="NIK")
            - Segment 3: "Satria Putra Yudistira" (key_label="Nama")
    """

    # Supported encodings in order of preference
    ENCODINGS = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']

    @property
    def supported_formats(self) -> list[DocumentFormat]:
        """Get list of formats this adapter supports."""
        return [DocumentFormat.TXT]

    def extract(self, file_path: Path) -> ExtractionResult:
        """
        Extract content from a TXT file into LogicalSegments.

        Args:
            file_path: Path to the TXT file

        Returns:
            ExtractionResult containing segments and metadata

        Raises:
            DocumentExtractionError: If extraction fails
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise DocumentExtractionError(
                f"File not found: {file_path}",
                file_path=file_path,
            )

        file_id = self._generate_file_id(file_path)
        warnings: list[str] = []

        try:
            # Detect encoding and read file
            encoding = self._detect_encoding(file_path)
            logger.debug(f"Reading TXT file with encoding: {encoding}")

            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()

            if not content.strip():
                return ExtractionResult(
                    segments=[],
                    file_id=file_id,
                    file_path=file_path,
                    file_format=DocumentFormat.TXT,
                    total_characters=0,
                    extraction_warnings=["File is empty"],
                )

            # Segment the content
            segments = self._segment_content(content, file_id)

            total_chars = sum(len(seg.text) for seg in segments)

            logger.info(
                f"Extracted {len(segments)} segments from TXT "
                f"({total_chars} chars)"
            )

            return ExtractionResult(
                segments=segments,
                file_id=file_id,
                file_path=file_path,
                file_format=DocumentFormat.TXT,
                total_characters=total_chars,
                extraction_warnings=warnings,
                metadata={
                    "encoding": encoding,
                    "line_count": content.count('\n') + 1,
                },
            )

        except UnicodeDecodeError as e:
            raise DocumentExtractionError(
                f"Failed to decode file: {e}",
                file_path=file_path,
                cause=e,
            ) from e
        except OSError as e:
            raise DocumentExtractionError(
                f"Failed to read file: {e}",
                file_path=file_path,
                cause=e,
            ) from e

    def _detect_encoding(self, file_path: Path) -> str:
        """
        Detect file encoding by trying common encodings.

        Args:
            file_path: Path to the file

        Returns:
            Detected encoding name
        """
        for encoding in self.ENCODINGS:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read(4096)  # Read a sample
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue

        return 'utf-8'  # Default fallback

    def _segment_content(
        self,
        content: str,
        file_id: str,
    ) -> list[LogicalSegment]:
        """
        Segment content into LogicalSegments.

        Strategy:
        1. Split by blank lines into paragraphs
        2. For each paragraph, detect key-value patterns
        3. Add context from previous/next paragraphs

        Args:
            content: The full text content
            file_id: File identifier

        Returns:
            List of LogicalSegments
        """
        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')

        # Split into paragraphs (separated by blank lines)
        paragraphs = self._split_paragraphs(content)

        if not paragraphs:
            return []

        segments: list[LogicalSegment] = []

        for i, (para_text, para_start) in enumerate(paragraphs):
            if not para_text.strip():
                continue

            # Get previous/next context
            prev_text = paragraphs[i - 1][0] if i > 0 else None
            next_text = paragraphs[i + 1][0] if i < len(paragraphs) - 1 else None

            # Detect key-value patterns
            key_value = self._detect_key_value(para_text)

            if key_value:
                # This is a key-value line - create segment for the value
                key, value, value_start = key_value
                segment = self._create_value_segment(
                    value=value,
                    key_label=key,
                    file_id=file_id,
                    paragraph_index=i,
                    para_start=para_start,
                    value_offset=value_start,
                    previous_text=prev_text,
                    next_text=next_text,
                )
            else:
                # Regular paragraph
                segment = self._create_paragraph_segment(
                    text=para_text,
                    file_id=file_id,
                    paragraph_index=i,
                    para_start=para_start,
                    previous_text=prev_text,
                    next_text=next_text,
                )

            segments.append(segment)

        # Detect potential headings and mark them
        self._detect_headings(segments)

        return segments

    def _split_paragraphs(self, content: str) -> list[tuple[str, int]]:
        """
        Split content into paragraphs with their starting positions.

        Args:
            content: Full text content

        Returns:
            List of (paragraph_text, start_position) tuples
        """
        paragraphs: list[tuple[str, int]] = []

        # Split by one or more blank lines
        para_pattern = re.compile(r'(?:\n\s*\n|\n{2,})')
        parts = para_pattern.split(content)

        pos = 0
        for part in parts:
            part_stripped = part.strip()
            if part_stripped:
                # Find actual start position
                actual_start = content.find(part_stripped, pos)
                if actual_start >= 0:
                    paragraphs.append((part_stripped, actual_start))
                    pos = actual_start + len(part_stripped)

        # If no paragraphs found (single block), split by lines
        if len(paragraphs) <= 1 and content.strip():
            paragraphs = []
            pos = 0
            for line in content.split('\n'):
                line_stripped = line.strip()
                if line_stripped:
                    actual_start = content.find(line_stripped, pos)
                    if actual_start >= 0:
                        paragraphs.append((line_stripped, actual_start))
                        pos = actual_start + len(line_stripped)

        return paragraphs

    def _detect_key_value(
        self, text: str
    ) -> tuple[str, str, int] | None:
        """
        Detect key-value pattern in text.

        Args:
            text: Text to analyze

        Returns:
            Tuple of (key, value, value_start_offset) or None
        """
        # Try to match key:value or key=value pattern
        match = KEY_VALUE_SEPARATORS.match(text)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()

            # Check if key looks like a label
            key_lower = key.lower()
            if key_lower in INDONESIAN_LABELS or len(key) <= 25:
                value_start = match.start(2)
                return key, value, value_start

        return None

    def _create_value_segment(
        self,
        value: str,
        key_label: str,
        file_id: str,
        paragraph_index: int,
        para_start: int,
        value_offset: int,
        previous_text: str | None,
        next_text: str | None,
    ) -> LogicalSegment:
        """
        Create a LogicalSegment for a key-value's value portion.

        Args:
            value: The value text
            key_label: The key/label that precedes this value
            file_id: File identifier
            paragraph_index: Index of the paragraph
            para_start: Start position of paragraph in file
            value_offset: Offset of value within paragraph
            previous_text: Previous paragraph text
            next_text: Next paragraph text

        Returns:
            Configured LogicalSegment
        """
        # Build char map
        char_map = CharMap(
            entries=[
                CharMapEntry(
                    logical_start=0,
                    logical_end=len(value),
                    source_component_id=f"para_{paragraph_index}_value",
                    source_start=para_start + value_offset,
                    source_end=para_start + value_offset + len(value),
                    source_type="text",
                )
            ]
        ) if value else CharMap()

        return LogicalSegment(
            text=value,
            file_id=file_id,
            file_type="txt",
            location=self._create_location(file_id, paragraph_index),
            previous_text=previous_text,
            next_text=next_text,
            key_label=key_label,
            is_value_of_key=True,
            char_map=char_map,
            language_hint="id",
        )

    def _create_paragraph_segment(
        self,
        text: str,
        file_id: str,
        paragraph_index: int,
        para_start: int,
        previous_text: str | None,
        next_text: str | None,
    ) -> LogicalSegment:
        """
        Create a LogicalSegment for a regular paragraph.

        Args:
            text: The paragraph text
            file_id: File identifier
            paragraph_index: Index of the paragraph
            para_start: Start position in file
            previous_text: Previous paragraph text
            next_text: Next paragraph text

        Returns:
            Configured LogicalSegment
        """
        # Build char map
        char_map = CharMap(
            entries=[
                CharMapEntry(
                    logical_start=0,
                    logical_end=len(text),
                    source_component_id=f"para_{paragraph_index}",
                    source_start=para_start,
                    source_end=para_start + len(text),
                    source_type="paragraph",
                )
            ]
        ) if text else CharMap()

        return LogicalSegment(
            text=text,
            file_id=file_id,
            file_type="txt",
            location=self._create_location(file_id, paragraph_index),
            previous_text=previous_text,
            next_text=next_text,
            char_map=char_map,
            language_hint="id",
        )

    def _create_location(
        self,
        file_id: str,
        paragraph_index: int,
    ) -> Any:
        """Create DocumentLocation for a TXT segment."""
        from sandiraksa.documents.location import DocumentLocation

        return DocumentLocation.for_txt(
            file_id=file_id,
            paragraph_index=paragraph_index,
        )

    def _detect_headings(self, segments: list[LogicalSegment]) -> None:
        """
        Detect and mark potential headings.

        Heuristics:
        - Short text (< 50 chars)
        - No punctuation at end
        - Followed by content
        - All caps or Title Case

        Args:
            segments: List of segments to analyze (modified in place)
        """
        for i, segment in enumerate(segments):
            text = segment.text
            if len(text) > 50:
                continue

            # Check if looks like heading
            is_heading = False

            # All caps
            if text.isupper() and len(text) > 3:
                is_heading = True
            # Title case and short
            elif text.istitle() and len(text.split()) <= 5:
                is_heading = True
            # Ends without period and is short
            elif not text.endswith('.') and len(text) <= 40:
                # Has next segment that's longer
                if i < len(segments) - 1:
                    next_seg = segments[i + 1]
                    if len(next_seg.text) > len(text) * 2:
                        is_heading = True

            if is_heading:
                segment.is_header = True
                # Use this as heading context for next segment
                if i < len(segments) - 1:
                    segments[i + 1].heading = text

    def apply_replacements(
        self,
        file_path: Path,
        output_path: Path,
        replacements: list[Replacement],
        segments: dict[str, LogicalSegment],
    ) -> ProtectionResult:
        """
        Apply replacements to a TXT file and save the result.

        Args:
            file_path: Path to the original TXT file
            output_path: Path for the protected output
            replacements: List of replacements to apply
            segments: Dictionary of segment_id -> LogicalSegment

        Returns:
            ProtectionResult with status
        """
        file_path = Path(file_path)
        output_path = Path(output_path)

        try:
            # Read original content
            encoding = self._detect_encoding(file_path)
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()

            # Sort replacements by position (descending) to apply from end
            sorted_replacements = sorted(
                replacements,
                key=lambda r: self._get_file_position(r, segments),
                reverse=True,
            )

            # Apply replacements
            applied = 0
            failed = 0

            for replacement in sorted_replacements:
                try:
                    segment = segments.get(replacement.segment_id)
                    if not segment:
                        logger.warning(
                            f"Segment not found: {replacement.segment_id}"
                        )
                        failed += 1
                        continue

                    # Get source position from char_map
                    mappings = segment.get_source_mappings_for_span(
                        replacement.logical_start,
                        replacement.logical_end,
                    )

                    if not mappings:
                        logger.warning(
                            f"No mappings for replacement in segment "
                            f"{replacement.segment_id}"
                        )
                        failed += 1
                        continue

                    # For TXT, there should be exactly one mapping
                    comp_id, source_start, source_end = mappings[0]

                    # Verify the text matches
                    original = content[source_start:source_end]
                    if original != replacement.original_text:
                        logger.warning(
                            f"Text mismatch at {source_start}-{source_end}: "
                            f"expected '{replacement.original_text}', "
                            f"found '{original}'"
                        )
                        failed += 1
                        continue

                    # Apply replacement
                    rep_text = replacement.get_padded_replacement()
                    content = content[:source_start] + rep_text + content[source_end:]
                    applied += 1

                except Exception as e:
                    logger.error(f"Failed to apply replacement: {e}")
                    failed += 1

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write output
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # Validate output
            is_valid, errors = self.validate(output_path)

            return ProtectionResult(
                output_path=output_path,
                replacements_applied=applied,
                replacements_failed=failed,
                validation_passed=is_valid,
                validation_errors=errors,
            )

        except Exception as e:
            raise DocumentProtectionError(
                f"Failed to protect TXT file: {e}",
                file_path=file_path,
                cause=e,
            ) from e

    def _get_file_position(
        self,
        replacement: Replacement,
        segments: dict[str, LogicalSegment],
    ) -> int:
        """Get the file position for a replacement."""
        segment = segments.get(replacement.segment_id)
        if not segment:
            return 0

        mappings = segment.get_source_mappings_for_span(
            replacement.logical_start,
            replacement.logical_end,
        )
        if mappings:
            return mappings[0][1]  # source_start
        return 0

    def validate(self, file_path: Path) -> tuple[bool, list[str]]:
        """
        Validate that a TXT file is readable.

        Args:
            file_path: Path to the file to validate

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors: list[str] = []

        try:
            if not file_path.exists():
                errors.append(f"File does not exist: {file_path}")
                return False, errors

            # Try to read the file
            encoding = self._detect_encoding(file_path)
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()

            # Basic validation - file should be readable
            if not isinstance(content, str):
                errors.append("File content is not valid text")
                return False, errors

            return True, []

        except UnicodeDecodeError as e:
            errors.append(f"Encoding error: {e}")
            return False, errors
        except OSError as e:
            errors.append(f"File read error: {e}")
            return False, errors


__all__ = [
    "TxtDocumentAdapter",
    "INDONESIAN_LABELS",
]
