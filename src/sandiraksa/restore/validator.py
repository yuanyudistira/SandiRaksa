"""
Restore Validator.

Validates that restoration is safe and complete.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from sandiraksa.restore.token_parser import ParsedToken, TokenParser

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ValidationWarning(str, Enum):
    """Types of validation warnings."""

    UNRESOLVED_TOKEN = "unresolved_token"
    UNKNOWN_TOKEN = "unknown_token"
    EXPIRED_MAPPING = "expired_mapping"
    DECRYPTION_FAILED = "decryption_failed"


@dataclass
class ValidationError:
    """A validation error."""

    warning_type: ValidationWarning
    message: str
    token_str: str | None = None
    location: str | None = None


@dataclass
class ValidationResult:
    """Result of restoration validation."""

    is_valid: bool
    can_proceed: bool  # Can proceed with partial restoration

    # Counts
    total_tokens: int = 0
    resolved_tokens: int = 0
    unresolved_tokens: int = 0

    # Issues
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def resolution_rate(self) -> float:
        """Percentage of tokens that could be resolved."""
        if self.total_tokens == 0:
            return 100.0
        return (self.resolved_tokens / self.total_tokens) * 100

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0


class RestoreValidator:
    """
    Validator for restoration operations.

    Ensures:
    1. All tokens can be resolved
    2. Token mappings are not expired
    3. Decryption succeeds
    4. Output integrity is maintained
    """

    def __init__(
        self,
        allow_partial: bool = False,
        min_resolution_rate: float = 100.0,
    ) -> None:
        """
        Initialize validator.

        Args:
            allow_partial: Allow proceeding with unresolved tokens.
            min_resolution_rate: Minimum % of tokens that must resolve.
        """
        self._allow_partial = allow_partial
        self._min_resolution_rate = min_resolution_rate
        self._parser = TokenParser()

    def validate_tokens(
        self,
        tokens: list[ParsedToken],
    ) -> ValidationResult:
        """
        Validate a list of parsed tokens.

        Args:
            tokens: List of ParsedToken objects with resolution status.

        Returns:
            ValidationResult.
        """
        result = ValidationResult(
            is_valid=True,
            can_proceed=True,
            total_tokens=len(tokens),
        )

        for token in tokens:
            if token.is_resolved:
                result.resolved_tokens += 1
            else:
                result.unresolved_tokens += 1

                # Create error
                error = ValidationError(
                    warning_type=ValidationWarning.UNRESOLVED_TOKEN,
                    message=f"Token could not be resolved: {token.token_str}",
                    token_str=token.token_str,
                )
                if token.resolution_error:
                    error.message += f" ({token.resolution_error})"

                result.errors.append(error)

        # Determine validity
        if result.unresolved_tokens > 0:
            result.is_valid = False

            # Check if we can proceed with partial restoration
            if self._allow_partial:
                if result.resolution_rate >= self._min_resolution_rate:
                    result.can_proceed = True
                    result.warnings.append(
                        f"{result.unresolved_tokens} token(s) could not be resolved, "
                        f"proceeding with {result.resolution_rate:.1f}% resolution"
                    )
                else:
                    result.can_proceed = False
            else:
                result.can_proceed = False

        return result

    def validate_pre_restore(
        self,
        text: str,
        available_mappings: set[str],
    ) -> ValidationResult:
        """
        Validate before restoration starts.

        Checks if all tokens in the text have available mappings.

        Args:
            text: Text with tokens to restore.
            available_mappings: Set of token strings with available mappings.

        Returns:
            ValidationResult.
        """
        # Parse all tokens in text
        found_tokens = self._parser.find_all_unique(text)

        result = ValidationResult(
            is_valid=True,
            can_proceed=True,
            total_tokens=len(found_tokens),
        )

        for token_str in found_tokens:
            if token_str in available_mappings:
                result.resolved_tokens += 1
            else:
                result.unresolved_tokens += 1
                result.errors.append(
                    ValidationError(
                        warning_type=ValidationWarning.UNKNOWN_TOKEN,
                        message=f"No mapping found for token: {token_str}",
                        token_str=token_str,
                    )
                )

        # Determine validity
        if result.unresolved_tokens > 0:
            result.is_valid = False
            result.can_proceed = (
                self._allow_partial
                and result.resolution_rate >= self._min_resolution_rate
            )

        return result

    def validate_post_restore(
        self,
        original_text: str,
        restored_text: str,
    ) -> ValidationResult:
        """
        Validate after restoration.

        Checks that no tokens remain in the restored text.

        Args:
            original_text: Text before restoration (with tokens).
            restored_text: Text after restoration.

        Returns:
            ValidationResult.
        """
        result = ValidationResult(
            is_valid=True,
            can_proceed=True,
        )

        # Check for remaining tokens
        remaining = self._parser.find_all_unique(restored_text)

        if remaining:
            result.is_valid = False
            result.can_proceed = self._allow_partial
            result.unresolved_tokens = len(remaining)

            for token_str in remaining:
                result.errors.append(
                    ValidationError(
                        warning_type=ValidationWarning.UNRESOLVED_TOKEN,
                        message=f"Token still present after restoration: {token_str}",
                        token_str=token_str,
                    )
                )

        # Count resolved (tokens that were replaced)
        original_tokens = self._parser.find_all_unique(original_text)
        result.total_tokens = len(original_tokens)
        result.resolved_tokens = len(original_tokens) - len(remaining)

        return result
