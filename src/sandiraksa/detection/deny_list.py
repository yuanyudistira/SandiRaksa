"""
Global deny-list (kamus pengecualian).

Lets users define terms that must NEVER be reported as PII, even if a recognizer
(or the English-model NLP) flags them. Typical culprits: IT jargon ("server",
"log", "host", "node", "cluster", "backup"), ticket prefixes ("INC", "TKT",
"REQ"), and common medical/document words mislabeled as PERSON.

Storage (mirrors ``custom_patterns.py``):
    <user_config_dir>/deny_list.json

JSON shape::

    {"terms": ["server", "log", "INC", "backup", ...]}

Matching is plain (not regex), case-insensitive, whitespace-normalized. A
detection is denied when its normalized text exactly equals a deny term, or
when every token of the detection is a deny term.

An empty deny-list means normal detection (nothing is dropped).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """Lowercase and collapse internal whitespace (matches person_filter)."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


# ----------------------------------------------------------------------------
# Free-text parsing (one term per line)
# ----------------------------------------------------------------------------

def parse_deny_text(text: str) -> list[str]:
    """
    Parse free-text input into a de-duplicated, normalized list of terms.

    - One term per line.
    - Blank lines and lines starting with '#' are ignored.
    - Terms are normalized (lowercase, collapsed whitespace).
    - Order is preserved; duplicates removed.
    """
    terms: list[str] = []
    seen: set[str] = set()
    if not text:
        return terms

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        norm = _normalize(line)
        if norm and norm not in seen:
            seen.add(norm)
            terms.append(norm)

    return terms


def deny_terms_to_text(terms: list[str]) -> str:
    """Render terms back to editable free-text (one per line)."""
    return "\n".join(terms)


# ----------------------------------------------------------------------------
# Global storage
# ----------------------------------------------------------------------------

class DenyListStore:
    """Loads and saves the global deny-list from the user config directory."""

    FILENAME = "deny_list.json"

    def __init__(self, config_path: Path | None = None) -> None:
        if config_path is not None:
            self._path = config_path
        else:
            from sandiraksa.config.settings import get_app_paths

            self._path = get_app_paths().config_dir / self.FILENAME

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[str]:
        """Load terms from disk. Returns empty list if none/invalid."""
        if not self._path.exists():
            return []
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("terms", []) if isinstance(data, dict) else data
            # Normalize + de-dup defensively (file may be hand-edited).
            out: list[str] = []
            seen: set[str] = set()
            for item in items:
                norm = _normalize(str(item))
                if norm and norm not in seen:
                    seen.add(norm)
                    out.append(norm)
            return out
        except Exception as e:
            logger.warning(f"Failed to load deny-list: {e}")
            return []

    def save(self, terms: list[str]) -> None:
        """Save terms to disk atomically."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"terms": terms}
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp.replace(self._path)

    def save_from_text(self, text: str) -> list[str]:
        """Parse free text, save, and return the resulting terms."""
        terms = parse_deny_text(text)
        self.save(terms)
        return terms


# ----------------------------------------------------------------------------
# Cached global accessor
# ----------------------------------------------------------------------------

_cached_terms: frozenset[str] | None = None


def get_global_deny_list(force_reload: bool = False) -> frozenset[str]:
    """Get the global deny-list as a frozenset (cached)."""
    global _cached_terms
    if _cached_terms is None or force_reload:
        _cached_terms = frozenset(DenyListStore().load())
    return _cached_terms


def reload_global_deny_list() -> frozenset[str]:
    """Force reload the global deny-list from disk."""
    return get_global_deny_list(force_reload=True)


def save_global_deny_list_from_text(text: str) -> frozenset[str]:
    """Save the global deny-list from free text and refresh the cache."""
    global _cached_terms
    store = DenyListStore()
    terms = store.save_from_text(text)
    _cached_terms = frozenset(terms)
    return _cached_terms


# ----------------------------------------------------------------------------
# Matching
# ----------------------------------------------------------------------------

def is_denied(text: str, terms: frozenset[str] | None = None) -> bool:
    """
    Return True if ``text`` should be dropped per the deny-list.

    A detection is denied when:
    - its normalized form exactly matches a deny term, OR
    - it has more than one token and EVERY token is a deny term.

    Args:
        text: The detected text.
        terms: Deny terms to use. If None, loads the cached global list.
    """
    if terms is None:
        terms = get_global_deny_list()
    if not terms or not text:
        return False

    normalized = _normalize(text)
    if not normalized:
        return False

    if normalized in terms:
        return True

    tokens = [t for t in re.split(r"[\s\-]+", normalized) if t]
    if len(tokens) > 1 and all(tok in terms for tok in tokens):
        return True

    return False


__all__ = [
    "DenyListStore",
    "parse_deny_text",
    "deny_terms_to_text",
    "get_global_deny_list",
    "reload_global_deny_list",
    "save_global_deny_list_from_text",
    "is_denied",
]
