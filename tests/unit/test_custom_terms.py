"""Tests for custom terms recognizer."""

import pytest

from sandiraksa.detection.recognizers.custom_terms import (
    CustomTerm,
    CustomTermsManager,
    CustomTermsRecognizer,
    MatchType,
)


class TestCustomTerm:
    """Tests for CustomTerm."""

    def test_word_match(self):
        """Should match whole words only."""
        term = CustomTerm(
            id="1",
            pattern="secret",
            match_type=MatchType.WORD,
        )
        pattern = term.compile()

        assert pattern.search("The secret is here")
        assert pattern.search("Tell me the secret")
        assert not pattern.search("secretive behavior")  # Part of word
        assert not pattern.search("top-secret mission")  # Hyphenated

    def test_contains_match(self):
        """Should match substrings."""
        term = CustomTerm(
            id="1",
            pattern="secret",
            match_type=MatchType.CONTAINS,
        )
        pattern = term.compile()

        assert pattern.search("The secret is here")
        assert pattern.search("secretive behavior")  # Part of word
        assert pattern.search("top-secret")  # Hyphenated

    def test_exact_match(self):
        """Should match exact string only."""
        term = CustomTerm(
            id="1",
            pattern="Project Alpha",
            match_type=MatchType.EXACT,
        )
        pattern = term.compile()

        assert pattern.search("Project Alpha")
        assert not pattern.search("The Project Alpha is")
        assert not pattern.search("Project Alpha-2")

    def test_regex_match(self):
        """Should use regex pattern."""
        term = CustomTerm(
            id="1",
            pattern=r"PROJ-\d{4}",
            match_type=MatchType.REGEX,
        )
        pattern = term.compile()

        assert pattern.search("Code: PROJ-1234")
        assert pattern.search("PROJ-5678 complete")
        assert not pattern.search("PROJ-ABC")
        assert not pattern.search("PROJ-12")

    def test_case_insensitive_default(self):
        """Should be case-insensitive by default."""
        term = CustomTerm(
            id="1",
            pattern="Confidential",
            match_type=MatchType.WORD,
        )
        pattern = term.compile()

        assert pattern.search("CONFIDENTIAL document")
        assert pattern.search("confidential info")
        assert pattern.search("Confidential")

    def test_case_sensitive(self):
        """Should respect case_sensitive flag."""
        term = CustomTerm(
            id="1",
            pattern="TopSecret",
            match_type=MatchType.WORD,
            case_sensitive=True,
        )
        pattern = term.compile()

        assert pattern.search("This is TopSecret")
        assert not pattern.search("This is TOPSECRET")
        assert not pattern.search("This is topsecret")


class TestCustomTermsRecognizer:
    """Tests for CustomTermsRecognizer."""

    @pytest.fixture
    def recognizer(self):
        """Create recognizer with sample terms."""
        terms = [
            CustomTerm(id="1", pattern="confidential", match_type=MatchType.WORD),
            CustomTerm(id="2", pattern="internal only", match_type=MatchType.WORD),
            CustomTerm(
                id="3",
                pattern="patient",
                match_type=MatchType.WORD,
                entity_type="MEDICAL_INFO",
            ),
        ]
        return CustomTermsRecognizer(terms=terms)

    def test_detect_single_term(self, recognizer):
        """Should detect a single custom term."""
        text = "This document is confidential."
        results = recognizer.analyze(text, ["CUSTOM_TERM"])

        assert len(results) == 1
        assert results[0].text == "confidential"
        assert results[0].entity_type == "CUSTOM_TERM"

    def test_detect_multiple_terms(self, recognizer):
        """Should detect multiple custom terms."""
        text = "This confidential document is internal only."
        results = recognizer.analyze(text, ["CUSTOM_TERM"])

        assert len(results) == 2
        texts = {r.text for r in results}
        assert "confidential" in texts
        assert "internal only" in texts

    def test_detect_custom_entity_type(self, recognizer):
        """Should detect terms with custom entity types."""
        text = "The patient record shows..."
        results = recognizer.analyze(text, ["MEDICAL_INFO"])

        assert len(results) == 1
        assert results[0].entity_type == "MEDICAL_INFO"

    def test_filter_by_entity_type(self, recognizer):
        """Should only return requested entity types."""
        text = "The patient confidential data"

        # Only request MEDICAL_INFO
        results = recognizer.analyze(text, ["MEDICAL_INFO"])
        assert len(results) == 1
        assert results[0].entity_type == "MEDICAL_INFO"

        # Request CUSTOM_TERM (should include confidential)
        results = recognizer.analyze(text, ["CUSTOM_TERM"])
        assert len(results) == 1
        assert results[0].text == "confidential"

    def test_add_term(self, recognizer):
        """Should add new terms dynamically."""
        new_term = CustomTerm(id="4", pattern="restricted", match_type=MatchType.WORD)
        recognizer.add_term(new_term)

        text = "This is restricted information"
        results = recognizer.analyze(text, ["CUSTOM_TERM"])

        texts = {r.text for r in results}
        assert "restricted" in texts

    def test_remove_term(self, recognizer):
        """Should remove terms."""
        recognizer.remove_term("1")  # Remove "confidential"

        text = "This document is confidential."
        results = recognizer.analyze(text, ["CUSTOM_TERM"])

        assert len(results) == 0

    def test_clear_terms(self, recognizer):
        """Should clear all terms."""
        recognizer.clear_terms()

        text = "This confidential document is internal only."
        results = recognizer.analyze(text, ["CUSTOM_TERM"])

        assert len(results) == 0
        assert recognizer.term_count == 0

    def test_empty_text(self, recognizer):
        """Should handle empty text."""
        results = recognizer.analyze("", ["CUSTOM_TERM"])
        assert results == []

    def test_no_terms(self):
        """Should handle no terms configured."""
        recognizer = CustomTermsRecognizer()
        results = recognizer.analyze("Some text here", ["CUSTOM_TERM"])
        assert results == []


class TestCustomTermsManager:
    """Tests for CustomTermsManager."""

    def test_get_recognizer_creates_new(self):
        """Should create new recognizer for unknown project."""
        manager = CustomTermsManager()

        rec1 = manager.get_recognizer("project-1")
        rec2 = manager.get_recognizer("project-2")

        assert rec1 is not rec2

    def test_get_recognizer_returns_cached(self):
        """Should return same recognizer for same project."""
        manager = CustomTermsManager()

        rec1 = manager.get_recognizer("project-1")
        rec2 = manager.get_recognizer("project-1")

        assert rec1 is rec2

    def test_add_term_via_manager(self):
        """Should add term through manager."""
        manager = CustomTermsManager()

        term = manager.add_term(
            project_id="project-1",
            pattern="secret code",
            match_type=MatchType.WORD,
        )

        recognizer = manager.get_recognizer("project-1")
        assert recognizer.term_count == 1

        results = recognizer.analyze("The secret code is here", ["CUSTOM_TERM"])
        assert len(results) == 1

    def test_remove_term_via_manager(self):
        """Should remove term through manager."""
        manager = CustomTermsManager()

        term = manager.add_term(
            project_id="project-1",
            pattern="secret",
            match_type=MatchType.WORD,
        )

        manager.remove_term("project-1", term.id)

        recognizer = manager.get_recognizer("project-1")
        assert recognizer.term_count == 0

    def test_close_project(self):
        """Should cleanup when closing project."""
        manager = CustomTermsManager()

        manager.add_term(
            project_id="project-1",
            pattern="secret",
            match_type=MatchType.WORD,
        )

        manager.close_project("project-1")

        # Should create fresh recognizer
        recognizer = manager.get_recognizer("project-1")
        assert recognizer.term_count == 0
