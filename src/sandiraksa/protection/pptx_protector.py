"""
PPTX file protection service.

Detects and replaces PII entities in PowerPoint presentations with tokens.
Supports slides, text frames, tables, notes.
"""

from __future__ import annotations

import gc
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from sandiraksa.protection.tokenizer import Tokenizer, TokenizerFactory

logger = logging.getLogger(__name__)


# Matches dates like "14-Feb-1988", "14/02/1988", "1988-02-14"
_DATE_HINT = re.compile(
    r"\d{1,2}[\s\-/][A-Za-z0-9]{1,9}[\s\-/]\d{2,4}"
    r"|\d{4}[\-/]\d{1,2}[\-/]\d{1,2}"
)


def _looks_like_date(text: str) -> bool:
    """Quick check that a value resembles a date."""
    return bool(_DATE_HINT.search(text.strip()))


@dataclass
class DetectedEntity:
    """A detected PII entity in presentation."""
    
    entity_type: str
    value: str
    location: str  # e.g., "slide 1", "notes", "table"
    context: str = ""  # Surrounding text for preview
    confidence: float = 0.8


@dataclass
class PptxProtectionResult:
    """Result of protecting a PPTX file."""
    
    success: bool
    output_path: str | None = None
    error_message: str | None = None
    entities_protected: int = 0
    slides_processed: int = 0
    duration_seconds: float = 0.0


@dataclass
class PptxProtectionProgress:
    """Progress information during protection."""
    
    phase: str = "Initializing"
    entities_found: int = 0
    entities_protected: int = 0
    current_slide: int = 0
    total_slides: int = 0


class PptxProtector:
    """
    Protects PPTX files by detecting and replacing PII with tokens.
    
    Features:
    - Scans slides, text frames, tables, notes
    - Auto-detects PII entities using regex patterns
    - Preserves presentation formatting
    - Uses consistent tokenization (same value = same token)
    """
    
    # Regex patterns for common PII types
    PATTERNS = {
        "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "PHONE_NUMBER": r'\b(?:\+62|62|0)[\s.-]?(?:\d{2,4})[\s.-]?(?:\d{3,4})[\s.-]?(?:\d{3,4})\b',
        "ID_NIK": r'\b[1-9]\d{15}\b',
        "ID_NPWP": r'\b\d{2}\.?\d{3}\.?\d{3}\.?\d[-.]?\d{3}\.?\d{3}\b',
        # Credit card: 4 groups of 4 digits with a CONSISTENT separator so
        # NIK-style IDs like "3174-19880214-1001" are not misdetected.
        "CREDIT_CARD": r'\b\d{4}([\s-]?)\d{4}\1\d{4}\1\d{4}\b',
        "IP_ADDRESS": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        "DATE": r'\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b',
        "URL": r'https?://[^\s<>"{}|\\^`\[\]]+',
    }
    
    # Context patterns for names
    CONTEXT_PATTERNS = {
        "PERSON": r'(?:(?:Nama|Name|Pasien|Patient|Dr\.?|Dokter|Bpk\.?|Ibu|Sdr\.?|Sdri\.?)\s*[:\s]\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
    }
    
    def __init__(
        self,
        project_id: str,
        entity_types: list[str] | None = None,
    ) -> None:
        """
        Initialize protector.
        
        Args:
            project_id: Project ID for tokenization context.
            entity_types: List of entity types to detect. If None, detect all.
        """
        self._project_id = project_id
        self._entity_types = entity_types
        self._tokenizer = TokenizerFactory.get_tokenizer(project_id)
    
    def detect_entities(self, file_path: Path | str) -> list[DetectedEntity]:
        """
        Detect PII entities in a PPTX file.
        
        Args:
            file_path: Path to PPTX file.
            
        Returns:
            List of detected entities.
        """
        from pptx import Presentation
        
        gc_was_enabled = gc.isenabled()
        gc.disable()
        
        try:
            file_path = Path(file_path)
            prs = Presentation(file_path)
            entities = []
            
            for slide_num, slide in enumerate(prs.slides, start=1):
                location = f"Slide {slide_num}"
                
                # Scan shapes
                for shape in slide.shapes:
                    shape_entities = self._scan_shape(shape, location)
                    entities.extend(shape_entities)

                # Spatial label pass: match value text frames to nearby labels
                # (e.g. a "NAMA" label above/left of the value shape).
                entities.extend(self._detect_by_spatial_labels(slide, location))
                
                # Scan notes
                if slide.has_notes_slide:
                    notes_frame = slide.notes_slide.notes_text_frame
                    if notes_frame and notes_frame.text.strip():
                        notes_entities = self._detect_in_text(
                            notes_frame.text, 
                            f"Slide {slide_num} notes"
                        )
                        entities.extend(notes_entities)
            
            # Global deny-list: drop user-excluded terms (all entity types).
            try:
                from sandiraksa.detection.deny_list import is_denied

                entities = [e for e in entities if not is_denied(e.value)]
            except Exception as de:
                logger.warning(f"Deny-list filter failed, skipping: {de}")

            # Deduplicate by value
            seen = set()
            unique_entities = []
            for e in entities:
                if e.value not in seen:
                    seen.add(e.value)
                    unique_entities.append(e)
            
            return unique_entities
            
        except Exception as e:
            logger.error(f"Error detecting entities in PPTX: {e}")
            return []
        finally:
            if gc_was_enabled:
                gc.enable()
    
    def _detect_by_spatial_labels(self, slide, location: str) -> list[DetectedEntity]:
        """
        Detect PERSON / DATE_OF_BIRTH values by matching them to a nearby
        label shape (a "profile card" layout common in slides).

        For each text shape whose text maps to a known label (e.g. "NAMA",
        "TANGGAL LAHIR"), find the closest text shape below or to the right and
        treat its content as the labeled entity value.
        """
        from sandiraksa.detection.recognizers.context_classifier import (
            classify_label,
        )

        found: list[DetectedEntity] = []

        # Collect simple text shapes with positions
        shapes = []
        for shape in slide.shapes:
            try:
                if not shape.has_text_frame:
                    continue
                text = shape.text_frame.text.strip()
                if not text:
                    continue
                left = shape.left or 0
                top = shape.top or 0
                shapes.append({"text": text, "left": int(left), "top": int(top)})
            except Exception:
                continue

        # Identify label shapes
        for lbl in shapes:
            entity_type = classify_label(lbl["text"])
            if entity_type not in ("PERSON", "DATE_OF_BIRTH"):
                continue

            # Find the nearest value shape below or to the right of the label
            best = None
            best_dist = None
            for cand in shapes:
                if cand is lbl:
                    continue
                # Candidate should not itself be a known label
                if classify_label(cand["text"]) is not None:
                    continue
                dx = cand["left"] - lbl["left"]
                dy = cand["top"] - lbl["top"]
                # Value is typically directly below (small dx, positive dy)
                if dy < 0 or abs(dx) > 500000:  # ~0.5 inch tolerance (EMU)
                    continue
                dist = abs(dx) + dy
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best = cand

            if best is None:
                continue

            value = best["text"]
            if entity_type == "DATE_OF_BIRTH" and not _looks_like_date(value):
                continue
            if self._entity_types and entity_type not in self._entity_types:
                continue

            found.append(DetectedEntity(
                entity_type=entity_type,
                value=value,
                location=location,
                context=f"{lbl['text']}: {value}",
                confidence=0.9,
            ))

        return found

    def _scan_shape(self, shape, location: str) -> list[DetectedEntity]:
        """Scan a shape for entities."""
        entities = []
        
        # Text frame
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                text = para.text
                if text.strip():
                    para_entities = self._detect_in_text(text, location)
                    entities.extend(para_entities)
        
        # Table - use first row as header context
        if shape.has_table:
            table = shape.table
            rows = list(table.rows)
            if rows:
                headers = [c.text.strip() for c in rows[0].cells]
                for row in rows[1:]:
                    for col_idx, cell in enumerate(row.cells):
                        if cell.text.strip():
                            header = headers[col_idx] if col_idx < len(headers) else ""
                            cell_entities = self._detect_in_cell(
                                cell.text, header, f"{location} table"
                            )
                            entities.extend(cell_entities)
        
        # Group shape - recurse
        if shape.shape_type == 6:  # MSO_SHAPE_TYPE.GROUP
            try:
                for child_shape in shape.shapes:
                    child_entities = self._scan_shape(child_shape, location)
                    entities.extend(child_entities)
            except Exception:
                pass
        
        return entities
    
    def _detect_in_text(self, text: str, location: str) -> list[DetectedEntity]:
        """Detect entities in a text string."""
        entities = []
        
        # Apply standard patterns
        for entity_type, pattern in self.PATTERNS.items():
            if self._entity_types and entity_type not in self._entity_types:
                continue
            
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = match.group(0)
                # Get context (surrounding 30 chars)
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end]
                
                entities.append(DetectedEntity(
                    entity_type=entity_type,
                    value=value,
                    location=location,
                    context=f"...{context}...",
                ))
        
        # Apply context patterns (for names)
        for entity_type, pattern in self.CONTEXT_PATTERNS.items():
            if self._entity_types and entity_type not in self._entity_types:
                continue
            
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = match.group(1)  # Capture group
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 20)
                context = text[start:end]
                
                entities.append(DetectedEntity(
                    entity_type=entity_type,
                    value=value,
                    location=location,
                    context=f"...{context}...",
                ))

        # Context-aware recognizers for names and birth dates
        entities.extend(self._detect_context_aware(text, location))

        # Global user-defined custom patterns (e.g. hospital MR numbers)
        entities.extend(self._detect_custom_patterns(text, location))

        return entities

    def _detect_custom_patterns(self, text: str, location: str) -> list[DetectedEntity]:
        """Detect matches from global user-defined custom patterns."""
        found: list[DetectedEntity] = []
        try:
            from sandiraksa.detection.custom_patterns import find_custom_matches

            for m in find_custom_matches(text):
                found.append(DetectedEntity(
                    entity_type=m.label,
                    value=m.value,
                    location=location,
                    context=text[:60],
                    confidence=0.95,
                ))
        except Exception as e:
            logger.warning(f"Custom pattern detection failed: {e}")
        return found

    def _detect_context_aware(self, text: str, location: str) -> list[DetectedEntity]:
        """Use context-aware recognizers for PERSON and DATE_OF_BIRTH."""
        found: list[DetectedEntity] = []
        try:
            from sandiraksa.detection.recognizers.id_person import (
                IndonesianPersonRecognizer,
            )
            from sandiraksa.detection.recognizers.id_dob import (
                DateOfBirthRecognizer,
            )
            from sandiraksa.detection.recognizers.id_bpjs_legacy import (
                BPJSRecognizerLegacy,
            )

            recognizers = []
            if not self._entity_types or "PERSON" in self._entity_types:
                recognizers.append(IndonesianPersonRecognizer())
            if not self._entity_types or "DATE_OF_BIRTH" in self._entity_types:
                recognizers.append(DateOfBirthRecognizer())
            if not self._entity_types or "ID_BPJS" in self._entity_types:
                recognizers.append(BPJSRecognizerLegacy())

            for rec in recognizers:
                for r in rec.analyze(text, rec.supported_entities):
                    found.append(DetectedEntity(
                        entity_type=r.entity_type,
                        value=r.text,
                        location=location,
                        context=text[:60],
                        confidence=r.score,
                    ))
        except Exception as e:
            logger.warning(f"Context-aware detection failed: {e}")
        return found

    def _detect_in_cell(self, text: str, header: str, location: str) -> list[DetectedEntity]:
        """Detect entities in a table cell using the column header as context."""
        text = text.strip()
        if not text:
            return []

        from sandiraksa.detection.recognizers.context_classifier import (
            classify_label,
        )

        entity_type = classify_label(header) if header else None
        if entity_type and entity_type in ("PERSON", "DATE_OF_BIRTH", "LOCATION"):
            if self._entity_types and entity_type not in self._entity_types:
                return []
            if entity_type == "DATE_OF_BIRTH" and not _looks_like_date(text):
                return []
            return [DetectedEntity(
                entity_type=entity_type,
                value=text,
                location=location,
                context=f"{header}: {text}",
                confidence=0.9,
            )]

        return self._detect_in_text(text, location)
    
    def protect_file(
        self,
        input_path: Path | str,
        output_path: Path | str,
        entities_to_protect: list[DetectedEntity] | None = None,
        progress_callback: Callable[[PptxProtectionProgress], None] | None = None,
    ) -> PptxProtectionResult:
        """
        Protect a PPTX file by replacing detected entities with tokens.
        
        Args:
            input_path: Path to input PPTX file.
            output_path: Path for protected output file.
            entities_to_protect: Specific entities to protect. If None, detect all.
            progress_callback: Optional callback for progress updates.
            
        Returns:
            PptxProtectionResult with status and statistics.
        """
        from pptx import Presentation
        
        gc_was_enabled = gc.isenabled()
        gc.disable()
        
        input_path = Path(input_path)
        output_path = Path(output_path)
        start_time = datetime.now()
        progress = PptxProtectionProgress()
        
        entities_protected = 0
        slides_processed = 0
        
        try:
            # Detect entities if not provided
            if entities_to_protect is None:
                entities_to_protect = self.detect_entities(input_path)
            
            if not entities_to_protect:
                return PptxProtectionResult(
                    success=True,
                    output_path=str(output_path),
                    entities_protected=0,
                    error_message="Tidak ada data sensitif ditemukan",
                )
            
            # Build value -> token map
            value_to_token = {}
            for entity in entities_to_protect:
                if entity.value not in value_to_token:
                    token = self._tokenizer.get_or_create_token(entity.entity_type, entity.value)
                    value_to_token[entity.value] = token
            
            # Load presentation
            progress.phase = "Loading presentation"
            if progress_callback:
                progress_callback(progress)
            
            prs = Presentation(input_path)
            progress.total_slides = len(prs.slides)
            
            # Process slides
            progress.phase = "Processing slides"
            for slide_num, slide in enumerate(prs.slides, start=1):
                progress.current_slide = slide_num
                if progress_callback:
                    progress_callback(progress)
                
                # Process shapes
                for shape in slide.shapes:
                    count = self._replace_in_shape(shape, value_to_token)
                    entities_protected += count
                
                # Process notes
                if slide.has_notes_slide:
                    notes_frame = slide.notes_slide.notes_text_frame
                    if notes_frame:
                        count = self._replace_in_text_frame(notes_frame, value_to_token)
                        entities_protected += count
                
                slides_processed += 1
                progress.entities_protected = entities_protected
            
            # Save presentation
            progress.phase = "Saving presentation"
            if progress_callback:
                progress_callback(progress)
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            prs.save(output_path)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"PPTX protection complete: {entities_protected} entities protected "
                f"in {duration:.2f}s"
            )
            
            return PptxProtectionResult(
                success=True,
                output_path=str(output_path),
                entities_protected=entities_protected,
                slides_processed=slides_processed,
                duration_seconds=duration,
            )
            
        except Exception as e:
            logger.error(f"PPTX protection failed: {e}", exc_info=True)
            return PptxProtectionResult(
                success=False,
                error_message=str(e),
            )
        finally:
            if gc_was_enabled:
                gc.enable()
    
    def _replace_in_shape(self, shape, value_to_token: dict[str, str]) -> int:
        """Replace values in a shape. Returns count of replacements."""
        count = 0
        
        # Text frame
        if shape.has_text_frame:
            count += self._replace_in_text_frame(shape.text_frame, value_to_token)
        
        # Table
        if shape.has_table:
            table = shape.table
            for row in table.rows:
                for cell in row.cells:
                    if cell.text_frame:
                        count += self._replace_in_text_frame(cell.text_frame, value_to_token)
        
        # Group shape - recurse
        if shape.shape_type == 6:  # MSO_SHAPE_TYPE.GROUP
            try:
                for child_shape in shape.shapes:
                    count += self._replace_in_shape(child_shape, value_to_token)
            except Exception:
                pass
        
        return count
    
    def _replace_in_text_frame(self, text_frame, value_to_token: dict[str, str]) -> int:
        """Replace values in a text frame while preserving formatting."""
        count = 0
        
        for para in text_frame.paragraphs:
            for run in para.runs:
                text = run.text
                if not text:
                    continue
                
                new_text = text
                for value, token in value_to_token.items():
                    if value in new_text:
                        new_text = new_text.replace(value, token)
                        count += text.count(value)
                
                if new_text != text:
                    run.text = new_text
        
        return count
