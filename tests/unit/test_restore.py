"""Tests for restore pipeline."""

import pytest

from sandiraksa.restore.token_parser import ParsedToken, TokenParser
from sandiraksa.restore.validator import (
    RestoreValidator,
    ValidationError,
    ValidationResult,
    ValidationWarning,
)
from sandiraksa.restore.pipeline import (
    RestorePhase,
    RestorePipeline,
    RestoreProgress,
    RestoreResult,
)
from sandiraksa.domain.token import Token


class TestTokenParser:
    """Tests for TokenParser."""

    @pytest.fixture
    def parser(self):
        return TokenParser()

    def test_parse_single_token(self, parser):
        """Should parse a single token."""
        text = "Contact [[PERSON_ABC123]]"
        tokens = parser.parse(text)

        assert len(tokens) == 1
        assert tokens[0].token_str == "[[PERSON_ABC123]]"
        assert tokens[0].entity_type == "PERSON"
        assert tokens[0].token_id == "ABC123"

    def test_parse_multiple_tokens(self, parser):
        """Should parse multiple tokens."""
        text = "Name: [[PERSON_ABC123]], Email: [[EMAIL_DEF456]]"
        tokens = parser.parse(text)

        assert len(tokens) == 2
        types = {t.entity_type for t in tokens}
        assert "PERSON" in types
        assert "EMAIL" in types

    def test_capture_context(self, parser):
        """Should capture surrounding context."""
        text = "Hello [[PERSON_ABC123]] world"
        tokens = parser.parse(text)

        assert tokens[0].context_before == "Hello "
        assert tokens[0].context_after == " world"

    def test_find_all_unique(self, parser):
        """Should find unique tokens."""
        text = "[[PERSON_ABC123]] and [[PERSON_ABC123]] again, plus [[EMAIL_XYZ789]]"
        unique = parser.find_all_unique(text)

        assert len(unique) == 2
        assert "[[PERSON_ABC123]]" in unique
        assert "[[EMAIL_XYZ789]]" in unique

    def test_count_tokens(self, parser):
        """Should count all token occurrences."""
        text = "[[PERSON_ABC123]] and [[PERSON_ABC123]] again"
        count = parser.count_tokens(text)

        assert count == 2  # Same token appears twice

    def test_has_tokens(self, parser):
        """Should detect if text has tokens."""
        assert parser.has_tokens("Has [[TOKEN_123456]]") is True
        assert parser.has_tokens("No tokens here") is False

    def test_replace_tokens(self, parser):
        """Should replace tokens with values."""
        text = "Name: [[PERSON_ABC123]], Email: [[EMAIL_DEF456]]"
        replacements = {
            "[[PERSON_ABC123]]": "John Doe",
            "[[EMAIL_DEF456]]": "john@example.com",
        }

        result = parser.replace_tokens(text, replacements)

        assert result == "Name: John Doe, Email: john@example.com"
        assert "[[" not in result

    def test_extract_by_type(self, parser):
        """Should filter tokens by entity type."""
        text = "[[PERSON_A12345]] and [[EMAIL_B67890]] and [[PERSON_C11111]]"
        persons = parser.extract_by_type(text, "PERSON")

        assert len(persons) == 2
        assert all(t.entity_type == "PERSON" for t in persons)


class TestRestoreValidator:
    """Tests for RestoreValidator."""

    def test_validate_all_resolved(self):
        """Should pass when all tokens resolved."""
        validator = RestoreValidator()

        tokens = [
            ParsedToken(
                token=Token("PERSON", "ABC123"),
                token_str="[[PERSON_ABC123]]",
                start=0, end=20,
                is_resolved=True,
                original_value="John Doe",
            ),
            ParsedToken(
                token=Token("EMAIL", "DEF456"),
                token_str="[[EMAIL_DEF456]]",
                start=30, end=50,
                is_resolved=True,
                original_value="john@example.com",
            ),
        ]

        result = validator.validate_tokens(tokens)

        assert result.is_valid is True
        assert result.can_proceed is True
        assert result.resolved_tokens == 2
        assert result.unresolved_tokens == 0

    def test_validate_unresolved_strict(self):
        """Should fail when tokens unresolved (strict mode)."""
        validator = RestoreValidator(allow_partial=False)

        tokens = [
            ParsedToken(
                token=Token("PERSON", "ABC123"),
                token_str="[[PERSON_ABC123]]",
                start=0, end=20,
                is_resolved=True,
                original_value="John Doe",
            ),
            ParsedToken(
                token=Token("EMAIL", "MISSING"),
                token_str="[[EMAIL_MISSING]]",
                start=30, end=50,
                is_resolved=False,
                resolution_error="Not found",
            ),
        ]

        result = validator.validate_tokens(tokens)

        assert result.is_valid is False
        assert result.can_proceed is False
        assert result.unresolved_tokens == 1

    def test_validate_allow_partial(self):
        """Should allow partial when configured."""
        validator = RestoreValidator(allow_partial=True, min_resolution_rate=50.0)

        tokens = [
            ParsedToken(
                token=Token("PERSON", "ABC123"),
                token_str="[[PERSON_ABC123]]",
                start=0, end=20,
                is_resolved=True,
                original_value="John Doe",
            ),
            ParsedToken(
                token=Token("EMAIL", "MISSING"),
                token_str="[[EMAIL_MISSING]]",
                start=30, end=50,
                is_resolved=False,
            ),
        ]

        result = validator.validate_tokens(tokens)

        assert result.is_valid is False  # Not fully valid
        assert result.can_proceed is True  # But can proceed (50% resolved)

    def test_validate_pre_restore(self):
        """Should validate before restoration."""
        validator = RestoreValidator()

        text = "[[PERSON_ABC123]] and [[EMAIL_DEF456]]"
        available = {"[[PERSON_ABC123]]"}  # Only one available

        result = validator.validate_pre_restore(text, available)

        assert result.is_valid is False
        assert result.resolved_tokens == 1
        assert result.unresolved_tokens == 1

    def test_validate_post_restore(self):
        """Should validate after restoration."""
        validator = RestoreValidator()

        original = "[[PERSON_ABC123]] and [[EMAIL_DEF456]]"
        restored = "John Doe and [[EMAIL_DEF456]]"  # One still remains

        result = validator.validate_post_restore(original, restored)

        assert result.is_valid is False
        assert result.unresolved_tokens == 1


class TestRestoreProgress:
    """Tests for RestoreProgress."""

    def test_overall_progress(self):
        """Should calculate overall progress."""
        progress = RestoreProgress()

        progress.phase = RestorePhase.INITIALIZING
        assert progress.overall_progress == 0.0

        progress.phase = RestorePhase.RESOLVING
        assert progress.overall_progress == 50.0

        progress.phase = RestorePhase.COMPLETED
        assert progress.overall_progress == 100.0


class TestRestoreResult:
    """Tests for RestoreResult."""

    def test_resolution_rate(self):
        """Should calculate resolution rate."""
        result = RestoreResult(
            success=True,
            operation_id="op1",
            file_id="file1",
            tokens_found=10,
            tokens_restored=8,
            tokens_failed=2,
        )

        assert result.resolution_rate == 80.0

    def test_resolution_rate_no_tokens(self):
        """Should handle no tokens case."""
        result = RestoreResult(
            success=True,
            operation_id="op1",
            file_id="file1",
            tokens_found=0,
        )

        assert result.resolution_rate == 100.0  # No tokens = 100% done
