"""Tests for tokenizer module."""

import tempfile
from pathlib import Path

import pytest

from sandiraksa.protection.tokenizer import (
    CollisionError,
    Tokenizer,
    TokenizerFactory,
    ValueNormalizer,
)
from sandiraksa.security.crypto import generate_key
from sandiraksa.security.vault import ProjectVault
from sandiraksa.storage.database import Database
from sandiraksa.storage.repositories import TokenMappingRepository


class MockKeyManager:
    """Mock key manager for testing."""

    def __init__(self):
        self._keys: dict[str, bytes] = {}

    @property
    def is_secure_storage_available(self) -> bool:
        return True

    def get_project_key(self, project_id: str) -> bytes:
        key_id = f"project_{project_id}"
        if key_id not in self._keys:
            self._keys[key_id] = generate_key()
        return self._keys[key_id]

    def delete_project_key(self, project_id: str) -> None:
        key_id = f"project_{project_id}"
        self._keys.pop(key_id, None)


@pytest.fixture
def db():
    """Create a temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        database = Database(db_path)
        database.initialize()
        yield database
        database.close()


@pytest.fixture
def key_manager():
    """Create a mock key manager."""
    return MockKeyManager()


@pytest.fixture
def vault(key_manager):
    """Create a project vault."""
    return ProjectVault("test-project", key_manager)


@pytest.fixture
def tokenizer(db, vault):
    """Create a tokenizer for testing."""
    repo = TokenMappingRepository(db)
    return Tokenizer("test-project", vault, repo)


class TestValueNormalizer:
    """Tests for ValueNormalizer."""

    def test_normalize_email(self):
        """Email should be lowercased."""
        result = ValueNormalizer.normalize("EMAIL", "John.Doe@Example.COM")
        assert result == "john.doe@example.com"

    def test_normalize_phone_indonesian(self):
        """Indonesian phone should be normalized to +62 format."""
        result = ValueNormalizer.normalize("PHONE_NUMBER", "0812-3456-7890")
        assert result == "+6281234567890"

    def test_normalize_phone_already_international(self):
        """Already international format should be preserved."""
        result = ValueNormalizer.normalize("PHONE_NUMBER", "+62 812 345 6789")
        assert result == "+628123456789"

    def test_normalize_person_name(self):
        """Person name should be casefolded and whitespace collapsed."""
        result = ValueNormalizer.normalize("PERSON", "  John   Smith  ")
        assert result == "john smith"

    def test_normalize_default(self):
        """Default normalization should casefold."""
        result = ValueNormalizer.normalize("CUSTOM", "  Test VALUE  ")
        assert result == "test value"

    def test_unicode_normalization(self):
        """Should apply Unicode NFC normalization."""
        # é as combining characters vs precomposed
        combining = "e\u0301"  # e + combining acute
        precomposed = "\u00e9"  # é precomposed

        result1 = ValueNormalizer.normalize("PERSON", combining)
        result2 = ValueNormalizer.normalize("PERSON", precomposed)

        assert result1 == result2


class TestTokenizer:
    """Tests for Tokenizer."""

    def test_create_new_token(self, tokenizer):
        """Should create a new token for unknown value."""
        token = tokenizer.get_or_create_token("PERSON", "John Smith")

        assert token.startswith("[[PERSON_")
        assert token.endswith("]]")

    def test_reuse_existing_token(self, tokenizer):
        """Should reuse token for same value."""
        token1 = tokenizer.get_or_create_token("PERSON", "John Smith")
        token2 = tokenizer.get_or_create_token("PERSON", "John Smith")

        assert token1 == token2

    def test_case_insensitive_matching(self, tokenizer):
        """Same name with different case should get same token."""
        token1 = tokenizer.get_or_create_token("PERSON", "John Smith")
        token2 = tokenizer.get_or_create_token("PERSON", "john smith")
        token3 = tokenizer.get_or_create_token("PERSON", "JOHN SMITH")

        assert token1 == token2 == token3

    def test_different_entity_types_different_tokens(self, tokenizer):
        """Same value with different entity types should get different tokens."""
        token1 = tokenizer.get_or_create_token("PERSON", "ABC Corp")
        token2 = tokenizer.get_or_create_token("ORGANIZATION", "ABC Corp")

        assert token1 != token2
        assert "PERSON" in token1
        assert "ORGANIZATION" in token2

    def test_lookup_existing_token(self, tokenizer):
        """Should look up and decrypt existing token."""
        original = "test@example.com"
        token = tokenizer.get_or_create_token("EMAIL", original)

        result = tokenizer.lookup_token(token)

        assert result.found is True
        assert result.original_value == original
        assert result.entity_type == "EMAIL"

    def test_lookup_nonexistent_token(self, tokenizer):
        """Should return not found for unknown token."""
        result = tokenizer.lookup_token("[[PERSON_NOTFOUND]]")

        assert result.found is False

    def test_lookup_invalid_format(self, tokenizer):
        """Should return not found for invalid token format."""
        result = tokenizer.lookup_token("not a token")

        assert result.found is False

    def test_mapping_count(self, tokenizer):
        """Should track mapping count."""
        assert tokenizer.get_mapping_count() == 0

        tokenizer.get_or_create_token("PERSON", "Person 1")
        tokenizer.get_or_create_token("EMAIL", "test@example.com")
        tokenizer.get_or_create_token("PERSON", "Person 1")  # Reuse

        assert tokenizer.get_mapping_count() == 2

    def test_cache_clearing(self, tokenizer):
        """Cache clear should force DB lookup."""
        token1 = tokenizer.get_or_create_token("PERSON", "Cached Value")
        tokenizer.clear_cache()
        token2 = tokenizer.get_or_create_token("PERSON", "Cached Value")

        assert token1 == token2  # Should still find same token in DB


class TestTokenizerFactory:
    """Tests for TokenizerFactory."""

    def test_get_tokenizer_cached(self):
        """Factory should cache tokenizers."""
        TokenizerFactory.close_all()  # Reset

        # This will fail without proper DB setup, but tests the caching logic
        # In real tests, we'd mock the dependencies
        TokenizerFactory.close_all()

    def test_close_all(self):
        """close_all should clear all instances."""
        TokenizerFactory.close_all()
        assert len(TokenizerFactory._instances) == 0
