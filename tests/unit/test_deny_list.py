"""
Tests for the global deny-list (Track A / A3).

Covers:
- Free-text parsing (comments, blanks, normalization, de-dup).
- Store save/load roundtrip (atomic file).
- is_denied matching (exact + all-tokens-denied).
- Integration with the PERSON false-positive filter.
"""

import pytest

from sandiraksa.detection.deny_list import (
    DenyListStore,
    parse_deny_text,
    deny_terms_to_text,
    is_denied,
)


class TestParseDenyText:
    def test_empty_input_returns_empty(self):
        assert parse_deny_text("") == []
        assert parse_deny_text("   \n\t\n") == []

    def test_comments_and_blanks_ignored(self):
        text = "# a comment\n\nserver\n# another\nlog\n"
        assert parse_deny_text(text) == ["server", "log"]

    def test_normalized_lowercase_and_dedup(self):
        text = "Server\nSERVER\n  server  \nLog"
        assert parse_deny_text(text) == ["server", "log"]

    def test_multiword_term_whitespace_collapsed(self):
        assert parse_deny_text("Corporate   Guarantee") == ["corporate guarantee"]


class TestDenyListStore:
    def test_save_and_load_roundtrip(self, tmp_path):
        store = DenyListStore(config_path=tmp_path / "deny.json")
        store.save(["server", "log", "backup"])
        assert store.load() == ["server", "log", "backup"]

    def test_load_missing_file_returns_empty(self, tmp_path):
        store = DenyListStore(config_path=tmp_path / "nope.json")
        assert store.load() == []

    def test_save_from_text(self, tmp_path):
        store = DenyListStore(config_path=tmp_path / "deny.json")
        terms = store.save_from_text("Server\nLOG\n# comment\n")
        assert terms == ["server", "log"]
        assert store.path.exists()

    def test_load_normalizes_hand_edited_file(self, tmp_path):
        # Simulate a hand-edited file with mixed case / duplicates.
        store = DenyListStore(config_path=tmp_path / "deny.json")
        import json
        (tmp_path / "deny.json").write_text(
            json.dumps({"terms": ["Server", "server", "LOG"]}),
            encoding="utf-8",
        )
        assert store.load() == ["server", "log"]


class TestIsDenied:
    def test_empty_list_denies_nothing(self):
        assert is_denied("server", terms=frozenset()) is False

    def test_exact_match(self):
        terms = frozenset({"server", "log"})
        assert is_denied("Server", terms=terms) is True
        assert is_denied("LOG", terms=terms) is True

    def test_non_member_not_denied(self):
        terms = frozenset({"server"})
        assert is_denied("Budi Santoso", terms=terms) is False

    def test_all_tokens_denied(self):
        # Multi-token where every token is a deny term.
        terms = frozenset({"log", "server"})
        assert is_denied("log server", terms=terms) is True

    def test_partial_tokens_not_denied(self):
        terms = frozenset({"server"})
        # Only one token is a deny term -> keep it.
        assert is_denied("server budi", terms=terms) is False


class TestPersonFilterIntegration:
    def test_denied_term_treated_as_false_positive_person(self, monkeypatch):
        import sandiraksa.detection.deny_list as dl
        from sandiraksa.detection.recognizers import person_filter

        # Inject a deny-list without touching disk.
        monkeypatch.setattr(dl, "_cached_terms", frozenset({"jakarta server"}))

        # A term that isn't in COMMON_NON_NAME_TERMS but is now denied.
        assert person_filter.is_false_positive_person("Jakarta Server") is True

    def test_reload_reflects_new_terms(self, tmp_path, monkeypatch):
        import sandiraksa.detection.deny_list as dl

        store = DenyListStore(config_path=tmp_path / "deny.json")
        store.save(["server"])

        # Point the module store at our temp file and reload.
        monkeypatch.setattr(
            dl, "DenyListStore", lambda: DenyListStore(tmp_path / "deny.json")
        )
        terms = dl.reload_global_deny_list()
        assert "server" in terms


class TestRenderHelper:
    def test_terms_to_text_roundtrip(self):
        terms = parse_deny_text("server\nlog\nbackup")
        rendered = deny_terms_to_text(terms)
        assert parse_deny_text(rendered) == terms
