"""Tests for global custom detection patterns."""

from pathlib import Path

import pytest

from sandiraksa.detection.custom_patterns import (
    CustomPattern,
    CustomPatternStore,
    parse_patterns_text,
    patterns_to_text,
    find_custom_matches,
)


class TestParsePatternsText:
    def test_empty_input_returns_empty(self):
        assert parse_patterns_text("") == []
        assert parse_patterns_text("   \n\t\n") == []

    def test_comments_ignored(self):
        text = "# this is a comment\n# another\n"
        assert parse_patterns_text(text) == []

    def test_label_pattern_lines(self):
        text = "MEDICAL_RECORD: MR-\\d{6}\nROOM: (?:Kamar|Room)\\s?\\d+"
        patterns = parse_patterns_text(text)
        assert len(patterns) == 2
        assert patterns[0].label == "MEDICAL_RECORD"
        assert patterns[0].pattern == "MR-\\d{6}"
        assert patterns[1].label == "ROOM"

    def test_line_without_label_defaults_to_custom(self):
        patterns = parse_patterns_text("MR-\\d{6}")
        assert len(patterns) == 1
        assert patterns[0].label == "CUSTOM"

    def test_invalid_regex_skipped(self):
        # Unbalanced parenthesis -> invalid regex -> skipped
        text = "GOOD: MR-\\d{6}\nBAD: (unclosed"
        patterns = parse_patterns_text(text)
        labels = [p.label for p in patterns]
        assert "GOOD" in labels
        assert "BAD" not in labels

    def test_label_normalized_to_upper_snake(self):
        patterns = parse_patterns_text("no kamar: \\d+")
        assert patterns[0].label == "NO_KAMAR"


class TestCustomPatternCompile:
    def test_regex_match_type(self):
        p = CustomPattern(label="MR", pattern="MR-\\d{6}", match_type="regex")
        assert p.compile() is not None
        assert p.is_valid()

    def test_word_match_type(self):
        p = CustomPattern(label="TERM", pattern="rahasia", match_type="word")
        compiled = p.compile()
        assert compiled.search("dokumen rahasia ini")
        assert not compiled.search("kerahasiaan")  # word boundary

    def test_invalid_regex_is_not_valid(self):
        p = CustomPattern(label="BAD", pattern="(unclosed", match_type="regex")
        assert not p.is_valid()


class TestFindCustomMatches:
    def test_finds_matches(self):
        patterns = parse_patterns_text(
            "MEDICAL_RECORD: MR-\\d{6}\nROOM: (?:Kamar|Room)\\s?\\d+"
        )
        text = "Pasien MR-004521 di Kamar 12"
        matches = find_custom_matches(text, patterns)
        labels = {m.label for m in matches}
        assert labels == {"MEDICAL_RECORD", "ROOM"}

    def test_no_patterns_returns_empty(self):
        assert find_custom_matches("MR-004521", []) == []

    def test_matches_sorted_by_position(self):
        patterns = parse_patterns_text("A: foo\nB: bar")
        matches = find_custom_matches("bar then foo", patterns)
        assert [m.start for m in matches] == sorted(m.start for m in matches)


class TestCustomPatternStore:
    def test_save_and_load_roundtrip(self, tmp_path):
        store = CustomPatternStore(config_path=tmp_path / "custom.json")
        patterns = parse_patterns_text("MR: MR-\\d{6}\nEMP: EMP-\\d{4}")
        store.save(patterns)
        loaded = store.load()
        assert len(loaded) == 2
        assert {p.label for p in loaded} == {"MR", "EMP"}

    def test_load_missing_file_returns_empty(self, tmp_path):
        store = CustomPatternStore(config_path=tmp_path / "nonexistent.json")
        assert store.load() == []

    def test_save_from_text(self, tmp_path):
        store = CustomPatternStore(config_path=tmp_path / "custom.json")
        patterns = store.save_from_text("MR: MR-\\d{6}")
        assert len(patterns) == 1
        assert store.path.exists()


class TestPatternsToText:
    def test_roundtrip_text(self):
        text = "MEDICAL_RECORD: MR-\\d{6}\nROOM: Kamar\\s?\\d+"
        patterns = parse_patterns_text(text)
        rendered = patterns_to_text(patterns)
        # Re-parse to confirm stability
        reparsed = parse_patterns_text(rendered)
        assert len(reparsed) == len(patterns)
        assert reparsed[0].label == patterns[0].label
