"""
Restore Pipeline.

Orchestrates the restoration (de-tokenization) workflow:
1. Parse tokens from protected document
2. Look up original values from vault
3. Replace tokens with original values
4. Validate output
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from sandiraksa.domain.finding import DocumentLocation
from sandiraksa.protection.tokenizer import Tokenizer, TokenizerFactory
from sandiraksa.restore.token_parser import ParsedToken, TokenParser
from sandiraksa.restore.validator import RestoreValidator, ValidationResult

if TYPE_CHECKING:
    from sandiraksa.protection.pipeline import DocumentHandler

logger = logging.getLogger(__name__)


class RestoreError(Exception):
    """Error during restoration."""

    pass


class RestorePhase(str, Enum):
    """Phases of restore pipeline."""

    INITIALIZING = "initializing"
    PARSING = "parsing"
    RESOLVING = "resolving"
    REPLACING = "replacing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RestoreProgress:
    """Progress tracking for restoration."""

    phase: RestorePhase = RestorePhase.INITIALIZING
    current_step: int = 0
    total_steps: int = 100
    message: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    @property
    def overall_progress(self) -> float:
        """Get overall progress percentage."""
        phase_weights = {
            RestorePhase.INITIALIZING: 0.0,
            RestorePhase.PARSING: 0.2,
            RestorePhase.RESOLVING: 0.5,
            RestorePhase.REPLACING: 0.8,
            RestorePhase.VALIDATING: 0.9,
            RestorePhase.COMPLETED: 1.0,
            RestorePhase.FAILED: 0.0,
        }
        return phase_weights.get(self.phase, 0.0) * 100

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time."""
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()


ProgressCallback = Callable[[RestoreProgress], None]


@dataclass
class RestoreResult:
    """Result of a restoration operation."""

    success: bool
    operation_id: str
    file_id: str
    output_path: Path | None = None

    # Statistics
    tokens_found: int = 0
    tokens_restored: int = 0
    tokens_failed: int = 0

    # Timing
    parse_duration_ms: float = 0.0
    resolve_duration_ms: float = 0.0
    total_duration_ms: float = 0.0

    # Validation
    validation: ValidationResult | None = None

    # Errors
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def resolution_rate(self) -> float:
        """Percentage of tokens successfully restored."""
        if self.tokens_found == 0:
            return 100.0
        return (self.tokens_restored / self.tokens_found) * 100


class RestorePipeline:
    """
    Main restoration pipeline.

    Coordinates token lookup and document restoration.
    """

    def __init__(
        self,
        project_id: str,
        tokenizer: Tokenizer | None = None,
        allow_partial: bool = False,
    ) -> None:
        """
        Initialize restore pipeline.

        Args:
            project_id: The project ID.
            tokenizer: Tokenizer for lookups. If None, uses factory.
            allow_partial: Allow partial restoration on failures.
        """
        self._project_id = project_id
        self._tokenizer = tokenizer or TokenizerFactory.get_tokenizer(project_id)
        self._allow_partial = allow_partial

        self._parser = TokenParser()
        self._validator = RestoreValidator(allow_partial=allow_partial)

        self._progress = RestoreProgress()
        self._progress_callback: ProgressCallback | None = None

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        """Set progress callback."""
        self._progress_callback = callback

    def _update_progress(
        self,
        phase: RestorePhase | None = None,
        message: str = "",
    ) -> None:
        """Update and report progress."""
        if phase:
            self._progress.phase = phase
        if message:
            self._progress.message = message

        if self._progress_callback:
            try:
                self._progress_callback(self._progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    def restore_text(
        self,
        text: str,
    ) -> tuple[str, list[ParsedToken]]:
        """
        Restore tokens in a text string.

        Args:
            text: Text with tokens.

        Returns:
            Tuple of (restored_text, parsed_tokens).
        """
        self._update_progress(RestorePhase.PARSING, "Parsing tokens...")

        # Parse tokens
        tokens = self._parser.parse(text)

        if not tokens:
            return text, []

        self._update_progress(RestorePhase.RESOLVING, f"Resolving {len(tokens)} tokens...")

        # Resolve each token
        replacements: dict[str, str] = {}

        for i, token in enumerate(tokens):
            # Look up original value
            result = self._tokenizer.lookup_token(token.token_str)

            if result.found and result.original_value:
                token.original_value = result.original_value
                token.is_resolved = True
                replacements[token.token_str] = result.original_value
            else:
                token.is_resolved = False
                if result.is_expired:
                    token.resolution_error = "Token mapping expired"
                else:
                    token.resolution_error = "Token not found"

        self._update_progress(RestorePhase.REPLACING, "Replacing tokens...")

        # Replace tokens with original values
        restored = self._parser.replace_tokens(text, replacements)

        return restored, tokens

    def restore_document(
        self,
        file_path: Path,
        output_path: Path,
        handler: Any,  # DocumentHandler
    ) -> RestoreResult:
        """
        Restore a protected document.

        Args:
            file_path: Path to protected document.
            output_path: Path for restored output.
            handler: Document handler.

        Returns:
            RestoreResult.
        """
        start_time = datetime.utcnow()
        operation_id = str(uuid4())
        file_id = str(uuid4())

        result = RestoreResult(
            success=False,
            operation_id=operation_id,
            file_id=file_id,
        )

        try:
            self._update_progress(RestorePhase.PARSING, "Opening document...")

            # Open document
            handler.open(file_path)

            # Collect all text and their locations
            all_tokens: list[ParsedToken] = []
            replacements: dict[tuple[int, int], str] = {}

            parse_start = datetime.utcnow()

            # Parse all segments
            for batch in handler.get_text_segments():
                for segment in batch:
                    # Parse tokens in this segment
                    tokens = self._parser.parse(segment.text)
                    all_tokens.extend(tokens)

            parse_end = datetime.utcnow()
            result.parse_duration_ms = (parse_end - parse_start).total_seconds() * 1000
            result.tokens_found = len(all_tokens)

            self._update_progress(
                RestorePhase.RESOLVING,
                f"Found {len(all_tokens)} tokens, resolving...",
            )

            # Resolve all unique tokens
            resolve_start = datetime.utcnow()
            unique_tokens = {t.token_str for t in all_tokens}
            resolution_map: dict[str, str] = {}

            for token_str in unique_tokens:
                lookup = self._tokenizer.lookup_token(token_str)
                if lookup.found and lookup.original_value:
                    resolution_map[token_str] = lookup.original_value
                    result.tokens_restored += 1
                else:
                    result.tokens_failed += 1
                    result.warnings.append(f"Could not resolve: {token_str}")

            resolve_end = datetime.utcnow()
            result.resolve_duration_ms = (resolve_end - resolve_start).total_seconds() * 1000

            # Mark tokens as resolved
            for token in all_tokens:
                if token.token_str in resolution_map:
                    token.original_value = resolution_map[token.token_str]
                    token.is_resolved = True

            # Validate
            self._update_progress(RestorePhase.VALIDATING, "Validating...")
            validation = self._validator.validate_tokens(all_tokens)
            result.validation = validation

            if not validation.can_proceed:
                raise RestoreError(
                    f"Validation failed: {validation.unresolved_tokens} tokens unresolved"
                )

            # Create output file with replacements
            self._update_progress(RestorePhase.REPLACING, "Creating restored file...")

            # Build location-based replacements
            # Re-open and process with replacements
            handler.close()
            handler.open(file_path)

            for batch in handler.get_text_segments():
                for segment in batch:
                    loc = segment.location
                    if loc and loc.row_number is not None:
                        # Restore the text
                        restored_text = self._parser.replace_tokens(
                            segment.text, resolution_map
                        )
                        if restored_text != segment.text:
                            key = (loc.row_number, loc.column_number or 0)
                            replacements[key] = restored_text

            # Create restored file
            result.output_path = handler.create_treated_file(output_path, replacements)

            # Complete
            self._progress.completed_at = datetime.utcnow()
            self._update_progress(RestorePhase.COMPLETED, "Restoration complete")
            result.success = True

        except Exception as e:
            logger.error(f"Restoration failed: {e}")
            result.error_message = str(e)
            self._update_progress(RestorePhase.FAILED, str(e))

        finally:
            try:
                handler.close()
            except Exception:
                pass

            end_time = datetime.utcnow()
            result.total_duration_ms = (end_time - start_time).total_seconds() * 1000

        return result

    def execute(
        self,
        input_path: Path,
        output_path: Path,
        handler: Any,
    ) -> RestoreResult:
        """
        Execute the full restoration pipeline.

        Alias for restore_document().
        """
        return self.restore_document(input_path, output_path, handler)


def create_restore_pipeline(
    project_id: str,
    allow_partial: bool = False,
) -> RestorePipeline:
    """Factory function to create a restore pipeline."""
    return RestorePipeline(project_id, allow_partial=allow_partial)
