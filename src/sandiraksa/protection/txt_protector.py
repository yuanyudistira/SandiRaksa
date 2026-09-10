"""
TXT file protection service.

Detects and replaces PII entities in plain text files with tokens.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from sandiraksa.protection.tokenizer import Tokenizer, TokenizerFactory

logger = logging.getLogger(__name__)


@dataclass
class DetectedEntity:
    """A detected PII entity in text."""
    
    entity_type: str
    value: str
    start: int
    end: int
    confidence: float = 0.8


@dataclass
class TxtProtectionResult:
    """Result of protecting a TXT file."""
    
    success: bool
    output_path: str | None = None
    error_message: str | None = None
    entities_protected: int = 0
    total_characters: int = 0
    duration_seconds: float = 0.0


@dataclass
class TxtProtectionProgress:
    """Progress information during protection."""
    
    phase: str = "Initializing"
    entities_found: int = 0
    entities_protected: int = 0


class TxtProtector:
    """
    Protects TXT files by detecting and replacing PII with tokens.
    
    Features:
    - Auto-detects PII entities using regex patterns
    - Preserves original text structure and formatting
    - Uses consistent tokenization (same value = same token)
    - Supports Indonesian PII types (NIK, NPWP, phone, etc.)
    """
    
    # Regex patterns for common PII types
    PATTERNS = {
        "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "PHONE_NUMBER": r'\b(?:\+62|62|0)[\s.-]?(?:\d{2,4})[\s.-]?(?:\d{3,4})[\s.-]?(?:\d{3,4})\b',
        "ID_NIK": r'\b[1-9]\d{15}\b',  # 16-digit starting with non-zero
        "ID_NPWP": r'\b\d{2}\.?\d{3}\.?\d{3}\.?\d[-.]?\d{3}\.?\d{3}\b',
        "ID_KK": r'\b[1-9]\d{15}\b',  # Same format as NIK
        # Credit card: 4 groups of 4 digits with a CONSISTENT separator so
        # NIK-style IDs like "3174-19880214-1001" are not misdetected.
        "CREDIT_CARD": r'\b\d{4}([\s-]?)\d{4}\1\d{4}\1\d{4}\b',
        "IP_ADDRESS": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        # Date formats: DD/MM/YYYY, YYYY-MM-DD, DD-Mon-YYYY, etc.
        "DATE": r'\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)[-/]\d{2,4})\b',
        "URL": r'https?://[^\s<>"{}|\\^`\[\]]+',
    }
    
    # Patterns that need special handling (capture groups for the actual value)
    CONTEXT_PATTERNS = {
        # Person name after keywords - name must be on same line, 2-4 words starting with capital
        "PERSON": r'(?:Nama\s*(?:Pasien)?|Pasien|Dokter|Dr\.|Perawat|Pengirim|Penerima|Kepada|Dari|Attn|PIC)[\s:]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})(?=\s*[\|\n\r,;]|$)',
    }
    
    def __init__(
        self,
        project_id: str,
        tokenizer: Tokenizer | None = None,
        entity_types: list[str] | None = None,
    ) -> None:
        """
        Initialize TXT protector.
        
        Args:
            project_id: Project ID for token scoping.
            tokenizer: Optional tokenizer instance.
            entity_types: List of entity types to detect. If None, detects all.
        """
        self._project_id = project_id
        self._tokenizer = tokenizer or TokenizerFactory.get_tokenizer(project_id)
        # Combine standard and context pattern entity types.
        # PERSON comes from context recognizers; DATE_OF_BIRTH is handled by the
        # context-aware date recognizer (context-gated, avoids visit dates).
        all_types = (
            list(self.PATTERNS.keys())
            + list(self.CONTEXT_PATTERNS.keys())
            + ["DATE_OF_BIRTH", "ID_BPJS"]
        )
        self._entity_types = entity_types or all_types
    
    def detect_entities(self, text: str) -> list[DetectedEntity]:
        """
        Detect PII entities in text.
        
        Args:
            text: The text to scan.
            
        Returns:
            List of detected entities sorted by position.
        """
        entities: list[DetectedEntity] = []
        
        # Standard patterns (full match)
        for entity_type in self._entity_types:
            pattern = self.PATTERNS.get(entity_type)
            if not pattern:
                continue
            
            try:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    value = match.group()
                    if self._validate_entity(entity_type, value):
                        entities.append(DetectedEntity(
                            entity_type=entity_type,
                            value=value,
                            start=match.start(),
                            end=match.end(),
                        ))
            except re.error as e:
                logger.warning(f"Invalid regex pattern for {entity_type}: {e}")
        
        # Context patterns (capture group for actual value)
        for entity_type, pattern in self.CONTEXT_PATTERNS.items():
            if entity_type not in self._entity_types:
                continue
            
            try:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    # Use group(1) - the captured name, not the full match
                    if match.lastindex and match.lastindex >= 1:
                        value = match.group(1)
                        # Calculate position of captured group
                        start = match.start(1)
                        end = match.end(1)
                        
                        if self._validate_entity(entity_type, value):
                            entities.append(DetectedEntity(
                                entity_type=entity_type,
                                value=value,
                                start=start,
                                end=end,
                            ))
            except re.error as e:
                logger.warning(f"Invalid context pattern for {entity_type}: {e}")
        
        # Context-aware recognizers for names and birth dates (handles patterns
        # the regex above misses, e.g. EMR-style rows "[EMR-XXX] Nama | ...").
        entities.extend(self._detect_context_aware(text))

        # Global user-defined custom patterns (e.g. hospital MR numbers)
        entities.extend(self._detect_custom_patterns(text))

        # Sort by position (start offset)
        entities.sort(key=lambda e: e.start)
        
        # Remove overlapping entities (keep longer match)
        return self._remove_overlaps(entities)

    def _detect_custom_patterns(self, text: str) -> list[DetectedEntity]:
        """Detect matches from global user-defined custom patterns."""
        found: list[DetectedEntity] = []
        try:
            from sandiraksa.detection.custom_patterns import find_custom_matches

            for m in find_custom_matches(text):
                found.append(DetectedEntity(
                    entity_type=m.label,
                    value=m.value,
                    start=m.start,
                    end=m.end,
                    confidence=0.95,
                ))
        except Exception as e:
            logger.warning(f"Custom pattern detection failed: {e}")
        return found

    def _detect_context_aware(self, text: str) -> list[DetectedEntity]:
        """
        Use context-aware recognizers for PERSON and DATE_OF_BIRTH.

        These recognizers understand Indonesian document structure (labels,
        EMR rows) and reject common false positives, complementing the plain
        regex patterns above.
        """
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
            from sandiraksa.detection.recognizers.person_filter import (
                is_false_positive_person,
            )

            recognizers = []
            if "PERSON" in self._entity_types:
                recognizers.append(IndonesianPersonRecognizer())
            # DATE_OF_BIRTH detection is opt-in via entity_types; if the caller
            # detects all types, include it too.
            if "DATE_OF_BIRTH" in self._entity_types:
                recognizers.append(DateOfBirthRecognizer())
            # BPJS (13-digit, context-gated) — legacy-contract recognizer.
            if "ID_BPJS" in self._entity_types:
                recognizers.append(BPJSRecognizerLegacy())

            for rec in recognizers:
                for r in rec.analyze(text, rec.supported_entities):
                    # Extra guard against false-positive names
                    if r.entity_type == "PERSON" and is_false_positive_person(r.text):
                        continue
                    found.append(DetectedEntity(
                        entity_type=r.entity_type,
                        value=r.text,
                        start=r.start,
                        end=r.end,
                        confidence=r.score,
                    ))
        except Exception as e:
            logger.warning(f"Context-aware detection failed: {e}")
        return found
    
    def _validate_entity(self, entity_type: str, value: str) -> bool:
        """Validate a detected entity value."""
        if entity_type == "ID_NIK":
            # Basic NIK validation: 16 digits, valid province code
            digits = re.sub(r'\D', '', value)
            if len(digits) != 16:
                return False
            # Province code check (01-99)
            province = int(digits[:2])
            return 1 <= province <= 99
        
        if entity_type == "IP_ADDRESS":
            # Validate IP octets
            parts = value.split('.')
            return all(0 <= int(p) <= 255 for p in parts)
        
        if entity_type == "EMAIL":
            # Basic email validation
            return '@' in value and '.' in value.split('@')[-1]
        
        if entity_type == "CREDIT_CARD":
            # Credit card must be 13-19 digits (standard range)
            digits = re.sub(r'\D', '', value)
            if not (13 <= len(digits) <= 19):
                return False
            # Check format - should be 4-4-4-4 or similar, not date-like
            # Reject if looks like date pattern (year in middle)
            if re.search(r'\d{4}[-/]\d{6,8}[-/]\d{4}', value):
                return False
            # First digit check: Visa(4), MC(5), Amex(3), Discover(6)
            if digits[0] not in '3456':
                return False
            return True
        
        if entity_type == "PERSON":
            # Name should have at least 2 words and not be common words
            words = value.split()
            if len(words) < 2:
                return False
            # Filter out common false positives
            skip_words = {'data', 'file', 'mock', 'test', 'nama', 'pasien', 'dokter'}
            if any(w.lower() in skip_words for w in words):
                return False
            return True
        
        return True
    
    # Priority for resolving overlaps (higher = preferred). More specific
    # entity types win over generic ones (DATE_OF_BIRTH over DATE).
    _ENTITY_PRIORITY = {
        "DATE_OF_BIRTH": 10,
        "ID_NIK": 9,
        "ID_NPWP": 9,
        "ID_KK": 9,
        "CREDIT_CARD": 8,
        "EMAIL": 8,
        "PHONE_NUMBER": 7,
        "PERSON": 6,
        "DATE": 2,
    }

    def _priority(self, entity: DetectedEntity) -> int:
        return self._ENTITY_PRIORITY.get(entity.entity_type, 5)

    def _remove_overlaps(self, entities: list[DetectedEntity]) -> list[DetectedEntity]:
        """
        Remove overlapping entities.

        Resolution order:
        1. Higher entity-type priority wins (DATE_OF_BIRTH over generic DATE).
        2. Then longer match wins.
        """
        if not entities:
            return []

        # Global deny-list: drop user-excluded terms across ALL entity types.
        try:
            from sandiraksa.detection.deny_list import is_denied

            entities = [e for e in entities if not is_denied(e.value)]
        except Exception as e:
            logger.warning(f"Deny-list filter failed, skipping: {e}")

        result: list[DetectedEntity] = []
        
        for entity in entities:
            # Check if overlaps with last added entity
            if result and entity.start < result[-1].end:
                prev = result[-1]
                # Prefer higher priority
                if self._priority(entity) > self._priority(prev):
                    result[-1] = entity
                elif self._priority(entity) == self._priority(prev):
                    # Same priority -> keep the longer match
                    if (entity.end - entity.start) > (prev.end - prev.start):
                        result[-1] = entity
            else:
                result.append(entity)
        
        return result
    
    def protect_text(
        self,
        text: str,
        entities: list[DetectedEntity] | None = None,
    ) -> tuple[str, int]:
        """
        Replace detected entities with tokens.
        
        Args:
            text: Original text.
            entities: Pre-detected entities, or None to detect.
            
        Returns:
            Tuple of (protected_text, count_of_entities_protected).
        """
        if entities is None:
            entities = self.detect_entities(text)
        
        if not entities:
            return text, 0
        
        # Build protected text by replacing entities from end to start
        # (to preserve positions)
        protected = text
        count = 0
        
        for entity in reversed(entities):
            token = self._tokenizer.get_or_create_token(
                entity.entity_type,
                entity.value,
            )
            protected = protected[:entity.start] + token + protected[entity.end:]
            count += 1
        
        return protected, count
    
    def protect_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
        progress_callback: Callable[[TxtProtectionProgress], None] | None = None,
    ) -> TxtProtectionResult:
        """
        Protect a TXT file by tokenizing detected PII.
        
        Args:
            input_path: Path to input TXT file.
            output_path: Path where protected file will be saved.
            progress_callback: Optional callback for progress updates.
            
        Returns:
            TxtProtectionResult with status and statistics.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        
        start_time = datetime.now()
        progress = TxtProtectionProgress()
        
        try:
            # Read file
            progress.phase = "Membaca file"
            if progress_callback:
                progress_callback(progress)
            
            encoding = self._detect_encoding(input_path)
            logger.info(f"Loading TXT: {input_path} (encoding={encoding})")
            
            with open(input_path, 'r', encoding=encoding) as f:
                text = f.read()
            
            if not text.strip():
                return TxtProtectionResult(
                    success=False,
                    error_message="File kosong",
                )
            
            # Detect entities
            progress.phase = "Mendeteksi data sensitif"
            if progress_callback:
                progress_callback(progress)
            
            entities = self.detect_entities(text)
            progress.entities_found = len(entities)
            
            if progress_callback:
                progress_callback(progress)
            
            # Protect text
            progress.phase = "Melindungi data"
            if progress_callback:
                progress_callback(progress)
            
            protected_text, count = self.protect_text(text, entities)
            progress.entities_protected = count
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write protected file
            progress.phase = "Menyimpan file"
            if progress_callback:
                progress_callback(progress)
            
            logger.info(f"Saving protected file: {output_path}")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(protected_text)
            
            # Final progress
            progress.phase = "Selesai"
            if progress_callback:
                progress_callback(progress)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"TXT protection complete: {count} entities protected "
                f"in {duration:.2f}s"
            )
            
            return TxtProtectionResult(
                success=True,
                output_path=str(output_path),
                entities_protected=count,
                total_characters=len(text),
                duration_seconds=duration,
            )
            
        except Exception as e:
            logger.error(f"TXT protection failed: {e}", exc_info=True)
            return TxtProtectionResult(
                success=False,
                error_message=str(e),
            )
    
    def _detect_encoding(self, path: Path) -> str:
        """Detect file encoding."""
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    f.read(1024)
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        return 'utf-8'  # Default


def generate_txt_output_path(
    input_path: str | Path,
    output_dir: str | Path | None = None,
    suffix: str = "_protected",
) -> Path:
    """
    Generate output path for protected TXT file.
    
    Args:
        input_path: Original file path.
        output_dir: Output directory. If None, uses same dir as input.
        suffix: Suffix to add before extension.
        
    Returns:
        Path for output file.
    """
    input_path = Path(input_path)
    
    if output_dir is None:
        output_dir = input_path.parent
    else:
        output_dir = Path(output_dir)
    
    stem = input_path.stem
    ext = input_path.suffix or '.txt'
    
    # Generate unique name if file exists
    output_path = output_dir / f"{stem}{suffix}{ext}"
    counter = 1
    
    while output_path.exists():
        output_path = output_dir / f"{stem}{suffix}_{counter}{ext}"
        counter += 1
    
    return output_path


__all__ = [
    "DetectedEntity",
    "TxtProtectionProgress",
    "TxtProtectionResult",
    "TxtProtector",
    "generate_txt_output_path",
]
