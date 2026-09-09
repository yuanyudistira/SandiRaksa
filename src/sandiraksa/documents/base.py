"""
Base document adapter interfaces for SandiRaksa.

Document adapters are responsible for:
1. Extracting text from documents → LogicalSegments
2. Applying replacements back to source documents
3. Validating document integrity

Key Design Principle:
    Document adapters MUST NOT determine whether content is PII.
    They only extract, reconstruct, and apply changes.

Separation of Concerns:
    Document Adapter -> LogicalSegment -> Detection Engine -> Finding
                                                                  |
    Document Adapter <- Replacement <- Treatment Plan <-----------+
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from sandiraksa.documents.logical_segment import LogicalSegment


class DocumentFormat(str, Enum):
    """Supported document formats."""

    TXT = "txt"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    CSV = "csv"

    @classmethod
    def from_extension(cls, extension: str) -> "DocumentFormat":
        """
        Get format from file extension.

        Args:
            extension: File extension (with or without dot)

        Returns:
            The corresponding DocumentFormat

        Raises:
            ValueError: If extension is not supported
        """
        ext = extension.lower().lstrip(".")
        try:
            return cls(ext)
        except ValueError:
            supported = ", ".join(f.value for f in cls)
            msg = f"Unsupported format: {ext}. Supported: {supported}"
            raise ValueError(msg) from None

    @classmethod
    def from_path(cls, path: Path | str) -> "DocumentFormat":
        """
        Get format from file path.

        Args:
            path: Path to the file

        Returns:
            The corresponding DocumentFormat
        """
        path = Path(path)
        return cls.from_extension(path.suffix)


@dataclass
class Replacement:
    """
    Represents a text replacement to be applied to a document.

    This is the output from the protection/tokenization phase that
    gets passed back to the document adapter for application.

    Attributes:
        segment_id: ID of the LogicalSegment containing this replacement
        logical_start: Start position in the logical text
        logical_end: End position in the logical text
        original_text: The original text being replaced (for verification)
        replacement_text: The replacement text (token or masked value)
        entity_type: Type of entity being protected
        preserve_length: Whether to pad replacement to match original length
    """

    segment_id: str
    logical_start: int
    logical_end: int
    original_text: str
    replacement_text: str
    entity_type: str
    preserve_length: bool = False

    @property
    def original_length(self) -> int:
        """Get length of original text."""
        return len(self.original_text)

    @property
    def replacement_length(self) -> int:
        """Get length of replacement text."""
        return len(self.replacement_text)

    def get_padded_replacement(self) -> str:
        """
        Get replacement text padded to original length if needed.

        Returns:
            Replacement text, possibly padded with spaces
        """
        if not self.preserve_length:
            return self.replacement_text

        if self.replacement_length >= self.original_length:
            return self.replacement_text[: self.original_length]

        padding = " " * (self.original_length - self.replacement_length)
        return self.replacement_text + padding


@dataclass
class ExtractionResult:
    """
    Result of extracting content from a document.

    Contains the extracted segments plus metadata about the extraction.

    Attributes:
        segments: List of extracted LogicalSegments
        file_id: Unique identifier assigned to this file
        file_path: Path to the source file
        file_format: Detected format of the file
        total_characters: Total character count extracted
        extraction_warnings: Any warnings during extraction
        metadata: Additional document metadata
    """

    segments: list[LogicalSegment]
    file_id: str
    file_path: Path
    file_format: DocumentFormat
    total_characters: int = 0
    extraction_warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def segment_count(self) -> int:
        """Get number of segments extracted."""
        return len(self.segments)

    @property
    def has_warnings(self) -> bool:
        """Check if there were any extraction warnings."""
        return bool(self.extraction_warnings)


@dataclass
class ProtectionResult:
    """
    Result of applying protections to a document.

    Attributes:
        output_path: Path to the protected output file
        replacements_applied: Number of replacements successfully applied
        replacements_failed: Number of replacements that failed
        validation_passed: Whether output validation passed
        validation_errors: Any validation errors
    """

    output_path: Path
    replacements_applied: int = 0
    replacements_failed: int = 0
    validation_passed: bool = True
    validation_errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if protection was successful."""
        return self.validation_passed and self.replacements_failed == 0


@runtime_checkable
class DocumentAdapter(Protocol):
    """
    Protocol defining the interface for document adapters.

    All document format handlers must implement this protocol to work
    with the unified detection pipeline.

    Responsibilities:
        - extract(): Parse document and produce LogicalSegments
        - apply_replacements(): Apply protection changes to document
        - validate(): Verify document integrity after modifications

    Document adapters MUST NOT:
        - Determine whether content is PII
        - Make decisions about what to protect
        - Access the detection engine directly
    """

    @property
    def supported_formats(self) -> list[DocumentFormat]:
        """Get list of formats this adapter supports."""
        ...

    def extract(self, file_path: Path) -> ExtractionResult:
        """
        Extract content from a document into LogicalSegments.

        This is the primary extraction method. It must:
        1. Parse the document structure
        2. Reconstruct logical text (handling split runs, etc.)
        3. Build CharMap for each segment
        4. Attach available context (headers, labels, etc.)
        5. Return segments ready for detection

        Args:
            file_path: Path to the document to extract

        Returns:
            ExtractionResult containing segments and metadata

        Raises:
            DocumentExtractionError: If extraction fails
        """
        ...

    def apply_replacements(
        self,
        file_path: Path,
        output_path: Path,
        replacements: list[Replacement],
        segments: dict[str, LogicalSegment],
    ) -> ProtectionResult:
        """
        Apply replacements to a document and save the result.

        This method must:
        1. Map logical positions back to source components using CharMap
        2. Apply replacements to correct positions
        3. Preserve formatting and structure
        4. Save to output path
        5. Validate the output

        Args:
            file_path: Path to the original document
            output_path: Path for the protected output
            replacements: List of replacements to apply
            segments: Dictionary of segment_id -> LogicalSegment for CharMap lookup

        Returns:
            ProtectionResult with status and any errors

        Raises:
            DocumentProtectionError: If protection fails
        """
        ...

    def validate(self, file_path: Path) -> tuple[bool, list[str]]:
        """
        Validate that a document is intact and readable.

        This should be called after protection to ensure the
        output document is valid.

        Args:
            file_path: Path to the document to validate

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        ...


class BaseDocumentAdapter(ABC):
    """
    Abstract base class for document adapters.

    Provides common functionality and enforces the adapter contract.
    Concrete adapters should inherit from this class.
    """

    @property
    @abstractmethod
    def supported_formats(self) -> list[DocumentFormat]:
        """Get list of formats this adapter supports."""
        ...

    def can_handle(self, file_path: Path) -> bool:
        """
        Check if this adapter can handle the given file.

        Args:
            file_path: Path to check

        Returns:
            True if this adapter supports the file format
        """
        try:
            file_format = DocumentFormat.from_path(file_path)
            return file_format in self.supported_formats
        except ValueError:
            return False

    @abstractmethod
    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract content from a document into LogicalSegments."""
        ...

    @abstractmethod
    def apply_replacements(
        self,
        file_path: Path,
        output_path: Path,
        replacements: list[Replacement],
        segments: dict[str, LogicalSegment],
    ) -> ProtectionResult:
        """Apply replacements to a document and save the result."""
        ...

    @abstractmethod
    def validate(self, file_path: Path) -> tuple[bool, list[str]]:
        """Validate that a document is intact and readable."""
        ...

    def _generate_file_id(self, file_path: Path) -> str:
        """
        Generate a unique file ID.

        Args:
            file_path: Path to the file

        Returns:
            A unique identifier string
        """
        from uuid import uuid4

        return f"{file_path.stem}_{uuid4().hex[:8]}"

    def _count_characters(self, segments: list[LogicalSegment]) -> int:
        """
        Count total characters across all segments.

        Args:
            segments: List of segments

        Returns:
            Total character count
        """
        return sum(len(seg.text) for seg in segments)


class DocumentExtractionError(Exception):
    """Raised when document extraction fails."""

    def __init__(
        self,
        message: str,
        file_path: Path | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message)
        self.file_path = file_path
        self.cause = cause


class DocumentProtectionError(Exception):
    """Raised when document protection fails."""

    def __init__(
        self,
        message: str,
        file_path: Path | None = None,
        failed_replacements: list[Replacement] | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message)
        self.file_path = file_path
        self.failed_replacements = failed_replacements or []
        self.cause = cause


class DocumentValidationError(Exception):
    """Raised when document validation fails."""

    def __init__(
        self,
        message: str,
        file_path: Path | None = None,
        validation_errors: list[str] | None = None,
    ):
        super().__init__(message)
        self.file_path = file_path
        self.validation_errors = validation_errors or []


def get_adapter_for_format(file_format: DocumentFormat) -> type[BaseDocumentAdapter]:
    """
    Get the appropriate adapter class for a document format.

    This is a factory function that will be implemented once
    concrete adapters are created in Sprint 2.

    Args:
        file_format: The document format

    Returns:
        The adapter class for that format

    Raises:
        NotImplementedError: Until adapters are implemented
    """
    # This will be populated in Sprint 2 when concrete adapters are created
    # For now, raise NotImplementedError
    msg = f"Adapter for {file_format.value} not yet implemented"
    raise NotImplementedError(msg)


def get_adapter_for_path(file_path: Path | str) -> type[BaseDocumentAdapter]:
    """
    Get the appropriate adapter class for a file path.

    Args:
        file_path: Path to the file

    Returns:
        The adapter class for that file

    Raises:
        ValueError: If format is not supported
        NotImplementedError: Until adapters are implemented
    """
    path = Path(file_path)
    file_format = DocumentFormat.from_path(path)
    return get_adapter_for_format(file_format)
