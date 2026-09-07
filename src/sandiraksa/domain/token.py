"""
Token domain model.

Represents tokens used for reversible pseudonymization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, Pattern
from uuid import uuid4

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass


class TreatmentType(str, Enum):
    """Types of treatment for sensitive data."""

    TOKEN = "token"  # Reversible tokenization
    REDACT = "redact"  # [REDACTED]
    CATEGORY = "category"  # [PERSON], [EMAIL], etc.
    MASK = "mask"  # Partial masking
    GENERALIZE = "generalize"  # Generalization
    PSEUDONYM = "pseudonym"  # Deterministic pseudonym
    KEEP = "keep"  # No treatment


# Token format: [[TYPE_HEXID]]
# Examples: [[PERSON_7F31A2]], [[EMAIL_C83719]], [[ORG_91DC44]]
TOKEN_PATTERN: Pattern[str] = re.compile(
    r"\[\[(?P<type>[A-Z][A-Z0-9_]{1,31})_(?P<id>[A-F0-9]{6,16})\]\]"
)

# Minimum and maximum token ID length (in hex characters)
MIN_TOKEN_ID_LENGTH = 6
MAX_TOKEN_ID_LENGTH = 16


@dataclass(frozen=True)
class Token:
    """Immutable token representation."""

    entity_type: str
    token_id: str

    def __str__(self) -> str:
        """Get the token string representation."""
        return f"[[{self.entity_type}_{self.token_id}]]"

    @classmethod
    def parse(cls, token_str: str) -> Token | None:
        """
        Parse a token string.

        Args:
            token_str: Token string like "[[PERSON_ABC123]]"

        Returns:
            Token instance or None if invalid.
        """
        match = TOKEN_PATTERN.fullmatch(token_str)
        if match:
            return cls(
                entity_type=match.group("type"),
                token_id=match.group("id"),
            )
        return None

    @classmethod
    def find_all(cls, text: str) -> list[tuple[Token, int, int]]:
        """
        Find all tokens in text.

        Returns:
            List of (Token, start, end) tuples.
        """
        results = []
        for match in TOKEN_PATTERN.finditer(text):
            token = cls(
                entity_type=match.group("type"),
                token_id=match.group("id"),
            )
            results.append((token, match.start(), match.end()))
        return results

    @staticmethod
    def is_valid_format(token_str: str) -> bool:
        """Check if a string is a valid token format."""
        return TOKEN_PATTERN.fullmatch(token_str) is not None


class TokenMapping(BaseModel):
    """
    Domain model for a token mapping.

    Maps a token to its original value (encrypted).
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    token: str  # The full token string [[TYPE_ID]]
    entity_type: str
    normalized_hmac: str  # HMAC of normalized value for lookup

    # Original value is stored encrypted in the database
    # This field is only populated when needed and cleared after use
    original_value: str | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None

    class Config:
        """Pydantic configuration."""

        pass

    @property
    def parsed_token(self) -> Token | None:
        """Parse the token string."""
        return Token.parse(self.token)

    @property
    def is_expired(self) -> bool:
        """Check if the mapping has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def touch(self) -> None:
        """Update the last used timestamp."""
        self.last_used_at = datetime.utcnow()


@dataclass
class TokenGenerationRequest:
    """Request to generate a new token."""

    project_id: str
    entity_type: str
    original_value: str
    normalized_value: str


@dataclass
class TokenLookupResult:
    """Result of looking up a token."""

    found: bool
    token: str | None = None
    original_value: str | None = None
    entity_type: str | None = None
    is_expired: bool = False

    @classmethod
    def not_found(cls) -> TokenLookupResult:
        """Create a not-found result."""
        return cls(found=False)

    @classmethod
    def success(
        cls,
        token: str,
        original_value: str,
        entity_type: str,
    ) -> TokenLookupResult:
        """Create a successful lookup result."""
        return cls(
            found=True,
            token=token,
            original_value=original_value,
            entity_type=entity_type,
        )


@dataclass
class Treatment:
    """Represents how a finding should be treated."""

    finding_id: str
    treatment_type: TreatmentType
    replacement: str  # The replacement text (token, [REDACTED], etc.)
    location: dict  # DocumentLocation as dict

    # For reversible treatments
    token: str | None = None
    original_value_encrypted: bytes | None = None

    @property
    def is_reversible(self) -> bool:
        """Check if this treatment is reversible."""
        return self.treatment_type == TreatmentType.TOKEN and self.token is not None
