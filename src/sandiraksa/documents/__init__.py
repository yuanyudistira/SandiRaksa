"""Document handlers for various file formats.

This module provides document handling capabilities for SandiRaksa,
including extraction, protection, and format-specific handlers.

Core Models (Sprint 1 - Foundation):
    - DocumentLocation: Precise location within a document
    - DocumentComponent: Types of document components
    - CharMapEntry: Maps logical text positions to source components
    - CharMap: Collection of CharMapEntry for a segment
    - LogicalSegment: Reconstructed text with context for detection
    - DocumentAdapter: Protocol for format-specific handlers
    - Replacement: Represents a protection change to apply

Document Adapters (Sprint 2 & 3):
    - TxtDocumentAdapter: Plain text file handling with key-value detection
    - DocxDocumentAdapter: Word document with run reconstruction
    - PptxDocumentAdapter: PowerPoint with spatial context resolution
    - CsvDocumentAdapter: CSV with column header context (Sprint 3)
    - XlsxDocumentAdapter: Excel with sheet/column context (Sprint 3)
    - SpatialContextResolver: Detects nearby labels in PowerPoint

Legacy Format Handlers:
    - CSVHandler: CSV file handling
    - DOCXHandler: Word document handling (legacy)
    - PPTXHandler: PowerPoint handling (legacy)
    - XLSXHandler: Excel handling
"""

# Core models for unified detection architecture
from sandiraksa.documents.base import (
    BaseDocumentAdapter,
    DocumentAdapter,
    DocumentExtractionError,
    DocumentFormat,
    DocumentProtectionError,
    DocumentValidationError,
    ExtractionResult,
    ProtectionResult,
    Replacement,
    get_adapter_for_format,
    get_adapter_for_path,
)
from sandiraksa.documents.char_map import CharMap, CharMapEntry
from sandiraksa.documents.location import DocumentComponent, DocumentLocation
from sandiraksa.documents.logical_segment import LogicalSegment

# Document Adapters (Sprint 2 - Run Reconstruction)
from sandiraksa.documents.docx_adapter import DocxDocumentAdapter, HEADING_STYLES
from sandiraksa.documents.pptx_adapter import PptxDocumentAdapter
from sandiraksa.documents.spatial_resolver import (
    ShapePosition,
    SpatialContextResolver,
    are_on_same_baseline,
    distance_between,
    extract_shape_positions,
    is_above,
    is_left_adjacent,
    is_potential_label,
)
from sandiraksa.documents.txt_adapter import INDONESIAN_LABELS, TxtDocumentAdapter

# Document Adapters (Sprint 3 - CSV/XLSX)
from sandiraksa.documents.csv_adapter import CsvDocumentAdapter, ENCODING_ATTEMPTS
from sandiraksa.documents.xlsx_adapter import XlsxDocumentAdapter

# Legacy format-specific handlers
from sandiraksa.documents.csv_handler import (
    CSVCell,
    CSVHandler,
    CSVHandlerError,
    CSVMetadata,
    CSVReader,
    CSVWriter,
    DelimiterDetector,
    DelimiterError,
    EncodingDetector,
    EncodingError,
)
from sandiraksa.documents.docx_handler import (
    DOCXHandler,
    DOCXHandlerError,
    DOCXMetadata,
    DOCXReader,
    DOCXWriter,
    DocumentInventory,
    DocumentModificationError,
    DocumentOpenError,
    ParagraphInfo,
    TextRun,
    TextSpan,
)
from sandiraksa.documents.pptx_handler import (
    PPTXHandler,
    PPTXHandlerError,
    PPTXMetadata,
    PPTXReader,
    PPTXWriter,
    PresentationInventory,
    PresentationOpenError,
    ShapeInfo,
    SlideInventory,
    SlideModificationError,
    SlideNotesInfo,
    TableCellInfo,
)
from sandiraksa.documents.xlsx_handler import (
    CellModificationError,
    SheetInventory,
    WorkbookInventory,
    WorkbookOpenError,
    WorksheetError,
    XLSXCell,
    XLSXHandler,
    XLSXHandlerError,
    XLSXMetadata,
    XLSXReader,
    XLSXWriter,
)

__all__ = [
    # Core Models - Foundation (Sprint 1)
    "DocumentLocation",
    "DocumentComponent",
    "CharMapEntry",
    "CharMap",
    "LogicalSegment",
    # Adapter Protocol & Base
    "DocumentAdapter",
    "BaseDocumentAdapter",
    "DocumentFormat",
    "Replacement",
    "ExtractionResult",
    "ProtectionResult",
    # Adapter Factory Functions
    "get_adapter_for_format",
    "get_adapter_for_path",
    # Exceptions
    "DocumentExtractionError",
    "DocumentProtectionError",
    "DocumentValidationError",
    # Document Adapters (Sprint 2 - Run Reconstruction)
    "TxtDocumentAdapter",
    "DocxDocumentAdapter",
    "PptxDocumentAdapter",
    "HEADING_STYLES",
    "INDONESIAN_LABELS",
    # Document Adapters (Sprint 3 - CSV/XLSX)
    "CsvDocumentAdapter",
    "XlsxDocumentAdapter",
    "ENCODING_ATTEMPTS",
    # Spatial Context Resolver
    "SpatialContextResolver",
    "ShapePosition",
    "is_potential_label",
    "is_left_adjacent",
    "is_above",
    "are_on_same_baseline",
    "distance_between",
    "extract_shape_positions",
    # CSV Handler (Legacy)
    "CSVHandler",
    "CSVReader",
    "CSVWriter",
    "CSVMetadata",
    "CSVCell",
    "CSVHandlerError",
    "EncodingError",
    "DelimiterError",
    # Detectors
    "EncodingDetector",
    "DelimiterDetector",
    # XLSX Handler (Legacy)
    "XLSXHandler",
    "XLSXReader",
    "XLSXWriter",
    "XLSXMetadata",
    "XLSXCell",
    "XLSXHandlerError",
    "WorkbookOpenError",
    "WorksheetError",
    "CellModificationError",
    "SheetInventory",
    "WorkbookInventory",
    # DOCX Handler (Legacy)
    "DOCXHandler",
    "DOCXReader",
    "DOCXWriter",
    "DOCXMetadata",
    "DOCXHandlerError",
    "DocumentOpenError",
    "DocumentModificationError",
    "ParagraphInfo",
    "TextRun",
    "TextSpan",
    "DocumentInventory",
    # PPTX Handler (Legacy)
    "PPTXHandler",
    "PPTXReader",
    "PPTXWriter",
    "PPTXMetadata",
    "PPTXHandlerError",
    "PresentationOpenError",
    "SlideModificationError",
    "ShapeInfo",
    "TableCellInfo",
    "SlideNotesInfo",
    "SlideInventory",
    "PresentationInventory",
]
