"""
Token Parser.

Parses and extracts tokens from protected documents.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sandiraksa.domain.token import TOKEN_PATTERN, Token

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class TokenParserError(Exception):
    """Error during token parsing."""

    pass


@dataclass
class ParsedToken:
    """A token found during parsing."""

    token: Token
    token_str: str  # Full token string [[TYPE_ID]]
    start: int  # Start offset in text
    end: int  # End offset in text

    # Parsing context
    context_before: str = ""  # Text before token (for debugging)
    context_after: str = ""  # Text after token

    # Resolution state
    original_value: str | None = None
    is_resolved: bool = False
    resolution_error: str | None = None

    @property
    def entity_type(self) -> str:
        """Get the entity type from the token."""
        return self.token.entity_type

    @property
    def token_id(self) -> str:
        """Get the token ID."""
        return self.token.token_id


class TokenParser:
    """
    Parser for extracting tokens from text.

    Finds all [[TYPE_HEXID]] tokens and provides context.
    """

    # Amount of surrounding text to capture
    CONTEXT_SIZE = 20

    def __init__(self) -> None:
        self._stats = {
            "tokens_found": 0,
            "unique_tokens": 0,
        }

    def parse(self, text: str) -> list[ParsedToken]:
        """
        Parse text and extract all tokens.

        Args:
            text: Text to parse.

        Returns:
            List of ParsedToken objects.
        """
        tokens: list[ParsedToken] = []
        seen: set[str] = set()

        for match in TOKEN_PATTERN.finditer(text):
            token_str = match.group()
            token = Token.parse(token_str)

            if token is None:
                logger.warning(f"Failed to parse token: {token_str}")
                continue

            # Extract context
            start = match.start()
            end = match.end()

            context_start = max(0, start - self.CONTEXT_SIZE)
            context_end = min(len(text), end + self.CONTEXT_SIZE)

            parsed = ParsedToken(
                token=token,
                token_str=token_str,
                start=start,
                end=end,
                context_before=text[context_start:start],
                context_after=text[end:context_end],
            )
            tokens.append(parsed)

            if token_str not in seen:
                seen.add(token_str)

        self._stats["tokens_found"] = len(tokens)
        self._stats["unique_tokens"] = len(seen)

        return tokens

    def find_all_unique(self, text: str) -> set[str]:
        """
        Find all unique token strings in text.

        Args:
            text: Text to search.

        Returns:
            Set of unique token strings.
        """
        return {match.group() for match in TOKEN_PATTERN.finditer(text)}

    def count_tokens(self, text: str) -> int:
        """
        Count total tokens in text.

        Args:
            text: Text to search.

        Returns:
            Number of tokens found.
        """
        return len(list(TOKEN_PATTERN.finditer(text)))

    def has_tokens(self, text: str) -> bool:
        """
        Check if text contains any tokens.

        Args:
            text: Text to check.

        Returns:
            True if tokens found.
        """
        return TOKEN_PATTERN.search(text) is not None

    def extract_by_type(
        self, text: str, entity_type: str
    ) -> list[ParsedToken]:
        """
        Extract tokens of a specific entity type.

        Args:
            text: Text to parse.
            entity_type: Entity type to filter by.

        Returns:
            List of matching ParsedToken objects.
        """
        all_tokens = self.parse(text)
        return [t for t in all_tokens if t.entity_type == entity_type]

    def replace_tokens(
        self,
        text: str,
        replacements: dict[str, str],
    ) -> str:
        """
        Replace tokens in text with their replacements.

        Args:
            text: Text with tokens.
            replacements: Dict mapping token string to replacement.

        Returns:
            Text with tokens replaced.
        """
        result = text

        # Sort by length descending to avoid partial replacements
        sorted_tokens = sorted(
            replacements.keys(),
            key=len,
            reverse=True,
        )

        for token_str in sorted_tokens:
            if token_str in result:
                result = result.replace(token_str, replacements[token_str])

        return result

    @property
    def stats(self) -> dict[str, int]:
        """Get parsing statistics."""
        return self._stats.copy()
