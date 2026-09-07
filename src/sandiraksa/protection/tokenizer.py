"""
Token generation and management for reversible pseudonymization.

This module provides:
- Token generation using HMAC-based IDs
- Collision detection and handling
- Value normalization per entity type
- Integration with encrypted vault storage
"""

from __future__ import annotations

import logging
import unicodedata
from typing import TYPE_CHECKING

from sandiraksa.domain.token import (
    MAX_TOKEN_ID_LENGTH,
    MIN_TOKEN_ID_LENGTH,
    Token,
    TokenGenerationRequest,
    TokenLookupResult,
    TokenMapping,
)
from sandiraksa.security.crypto import compute_hmac
from sandiraksa.security.vault import ProjectVault, get_project_vault
from sandiraksa.storage.repositories import (
    TokenMappingRepository,
    NotFoundError,
)

if TYPE_CHECKING:
    from sandiraksa.storage.database import Database

logger = logging.getLogger(__name__)


class TokenizerError(Exception):
    """Base exception for tokenizer errors."""

    pass


class CollisionError(TokenizerError):
    """Token ID collision after maximum retries."""

    pass


class ValueNormalizer:
    """
    Normalizes values for consistent token mapping.

    Different entity types have different normalization rules
    to ensure the same logical value maps to the same token.
    """

    @staticmethod
    def normalize(entity_type: str, value: str) -> str:
        """
        Normalize a value based on entity type.

        Args:
            entity_type: The entity type (PERSON, EMAIL, etc.)
            value: The original value.

        Returns:
            Normalized value for HMAC computation.
        """
        # Basic normalization for all types
        normalized = value.strip()

        # Unicode normalization (NFC form)
        normalized = unicodedata.normalize("NFC", normalized)

        # Type-specific normalization
        if entity_type == "EMAIL":
            normalized = ValueNormalizer._normalize_email(normalized)
        elif entity_type == "PHONE_NUMBER" or entity_type == "ID_PHONE":
            normalized = ValueNormalizer._normalize_phone(normalized)
        elif entity_type in {"PERSON", "ORGANIZATION", "CLIENT_NAME", "SUPPLIER_NAME"}:
            normalized = ValueNormalizer._normalize_name(normalized)
        else:
            # Default: casefold for case-insensitive matching
            normalized = ValueNormalizer._normalize_default(normalized)

        return normalized

    @staticmethod
    def _normalize_email(value: str) -> str:
        """Normalize email address."""
        value = value.lower()

        # Split local and domain
        if "@" in value:
            local, domain = value.rsplit("@", 1)
            # Lowercase domain, keep local as-is (some systems are case-sensitive)
            # But for matching purposes, we lowercase the whole thing
            return f"{local}@{domain}"

        return value

    @staticmethod
    def _normalize_phone(value: str) -> str:
        """Normalize phone number by removing formatting."""
        # Remove common formatting characters
        cleaned = "".join(c for c in value if c.isdigit() or c == "+")

        # Handle Indonesian numbers
        if cleaned.startswith("0"):
            # Convert 08xx to +628xx
            cleaned = "+62" + cleaned[1:]
        elif cleaned.startswith("62"):
            cleaned = "+" + cleaned

        return cleaned

    @staticmethod
    def _normalize_name(value: str) -> str:
        """Normalize person/organization name."""
        # Collapse whitespace
        normalized = " ".join(value.split())

        # Casefold for comparison
        normalized = normalized.casefold()

        return normalized

    @staticmethod
    def _normalize_default(value: str) -> str:
        """Default normalization."""
        # Collapse whitespace and casefold
        normalized = " ".join(value.split())
        return normalized.casefold()


class Tokenizer:
    """
    Generates and manages tokens for a project.

    Tokens are:
    - Project-scoped (same value in different projects = different token)
    - Entity-type-scoped (same value with different type = different token)
    - Consistent within a project (same value = same token)
    - Non-sequential (IDs derived from HMAC, not counters)
    """

    # Maximum collision retries before error
    MAX_COLLISION_RETRIES = 10

    # Initial token ID length (will extend on collision)
    INITIAL_ID_LENGTH = 6

    def __init__(
        self,
        project_id: str,
        vault: ProjectVault | None = None,
        mapping_repo: TokenMappingRepository | None = None,
    ) -> None:
        """
        Initialize tokenizer for a project.

        Args:
            project_id: The project UUID.
            vault: Project vault for encryption. If None, uses global.
            mapping_repo: Token mapping repository. If None, uses global.
        """
        self._project_id = project_id
        self._vault = vault or get_project_vault(project_id)
        self._mapping_repo = mapping_repo or TokenMappingRepository()

        # Cache for session (avoid repeated DB lookups)
        self._cache: dict[str, TokenMapping] = {}

    def get_or_create_token(
        self,
        entity_type: str,
        original_value: str,
    ) -> str:
        """
        Get existing token or create new one for a value.

        This is the main entry point for tokenization.

        Args:
            entity_type: Entity type (PERSON, EMAIL, etc.)
            original_value: The original sensitive value.

        Returns:
            Token string like "[[PERSON_ABC123]]"

        Raises:
            TokenizerError: If token generation fails.
        """
        # Normalize for lookup
        normalized = ValueNormalizer.normalize(entity_type, original_value)

        # Check cache first
        cache_key = f"{entity_type}|{normalized}"
        if cache_key in self._cache:
            mapping = self._cache[cache_key]
            self._mapping_repo.update_last_used(mapping.id)
            return mapping.token

        # Compute HMAC for DB lookup
        normalized_hmac = self._vault.compute_normalized_hmac(entity_type, normalized)

        # Check if mapping already exists
        existing = self._mapping_repo.find_by_hmac(
            self._project_id, entity_type, normalized_hmac
        )

        if existing:
            # Reuse existing token
            mapping = TokenMapping(
                id=existing.id,
                project_id=existing.project_id,
                token=existing.token,
                entity_type=existing.entity_type,
                normalized_hmac=existing.normalized_hmac,
            )
            self._cache[cache_key] = mapping
            self._mapping_repo.update_last_used(existing.id)
            return existing.token

        # Create new token
        return self._create_new_token(
            entity_type=entity_type,
            original_value=original_value,
            normalized_value=normalized,
            normalized_hmac=normalized_hmac,
        )

    def _create_new_token(
        self,
        entity_type: str,
        original_value: str,
        normalized_value: str,
        normalized_hmac: str,
    ) -> str:
        """Create a new token with collision handling."""
        # Generate token ID from HMAC
        id_length = self.INITIAL_ID_LENGTH

        for attempt in range(self.MAX_COLLISION_RETRIES):
            token_id = self._generate_token_id(
                entity_type, normalized_value, id_length
            )
            token_str = f"[[{entity_type}_{token_id}]]"

            # Check for collision
            if not self._mapping_repo.token_exists(self._project_id, token_str):
                # No collision, create mapping
                return self._store_mapping(
                    token_str=token_str,
                    entity_type=entity_type,
                    original_value=original_value,
                    normalized_value=normalized_value,
                    normalized_hmac=normalized_hmac,
                )

            # Collision - extend ID length and retry
            logger.warning(
                f"Token collision detected for {entity_type}, "
                f"attempt {attempt + 1}, extending ID"
            )
            id_length = min(id_length + 2, MAX_TOKEN_ID_LENGTH)

        raise CollisionError(
            f"Failed to generate unique token after {self.MAX_COLLISION_RETRIES} attempts"
        )

    def _generate_token_id(
        self,
        entity_type: str,
        normalized_value: str,
        length: int,
    ) -> str:
        """
        Generate a token ID using HMAC.

        The ID is derived from the project's HMAC key + entity type + value,
        making it deterministic but not reversible without the key.
        """
        # Get full HMAC
        full_hmac = self._vault.compute_normalized_hmac(entity_type, normalized_value)

        # Take first `length` characters (hex)
        token_id = full_hmac[:length].upper()

        return token_id

    def _store_mapping(
        self,
        token_str: str,
        entity_type: str,
        original_value: str,
        normalized_value: str,
        normalized_hmac: str,
    ) -> str:
        """Store a new token mapping in the database."""
        # Encrypt the original value
        encrypted_value = self._vault.encrypt(
            original_value,
            table="token_mappings",
            row_id=token_str,
            field="original_value",
        )

        # Create database record
        record = self._mapping_repo.create(
            project_id=self._project_id,
            token=token_str,
            entity_type=entity_type,
            normalized_hmac=normalized_hmac,
            original_value_enc=encrypted_value,
        )

        # Cache it
        mapping = TokenMapping(
            id=record.id,
            project_id=record.project_id,
            token=record.token,
            entity_type=record.entity_type,
            normalized_hmac=record.normalized_hmac,
        )
        cache_key = f"{entity_type}|{normalized_value}"
        self._cache[cache_key] = mapping

        logger.debug(f"Created new token mapping: {token_str}")
        return token_str

    def lookup_token(self, token_str: str) -> TokenLookupResult:
        """
        Look up a token and retrieve the original value.

        Used during restoration.

        Args:
            token_str: Token string like "[[PERSON_ABC123]]"

        Returns:
            TokenLookupResult with original value if found.
        """
        # Validate token format
        if not Token.is_valid_format(token_str):
            return TokenLookupResult(
                found=False,
            )

        # Find in database
        record = self._mapping_repo.find_by_token(self._project_id, token_str)

        if record is None:
            return TokenLookupResult.not_found()

        # Decrypt original value
        try:
            original_value = self._vault.decrypt_string(
                record.original_value_enc,
                table="token_mappings",
                row_id=token_str,
                field="original_value",
            )
        except Exception as e:
            logger.error(f"Failed to decrypt token {token_str}: {e}")
            return TokenLookupResult(
                found=True,
                token=token_str,
                entity_type=record.entity_type,
                is_expired=True,  # Treat decryption failure as expired
            )

        # Update last used
        self._mapping_repo.update_last_used(record.id)

        return TokenLookupResult.success(
            token=token_str,
            original_value=original_value,
            entity_type=record.entity_type,
        )

    def get_mapping_count(self) -> int:
        """Get the number of token mappings for this project."""
        return self._mapping_repo.count_by_project(self._project_id)

    def clear_cache(self) -> None:
        """Clear the in-memory cache."""
        self._cache.clear()


class TokenizerFactory:
    """Factory for creating tokenizers with proper dependencies."""

    _instances: dict[str, Tokenizer] = {}

    @classmethod
    def get_tokenizer(cls, project_id: str) -> Tokenizer:
        """
        Get or create a tokenizer for a project.

        Tokenizers are cached per project to maintain session consistency.
        """
        if project_id not in cls._instances:
            cls._instances[project_id] = Tokenizer(project_id)
        return cls._instances[project_id]

    @classmethod
    def close_tokenizer(cls, project_id: str) -> None:
        """Close and remove a tokenizer."""
        if project_id in cls._instances:
            cls._instances[project_id].clear_cache()
            del cls._instances[project_id]

    @classmethod
    def close_all(cls) -> None:
        """Close all tokenizers."""
        for tokenizer in cls._instances.values():
            tokenizer.clear_cache()
        cls._instances.clear()
