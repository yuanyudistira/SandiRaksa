"""
Global custom detection patterns.

Lets users define their own PII patterns (e.g. hospital-specific Medical Record
number formats) that apply across ALL projects. Patterns are stored globally in
the user config directory, not per project.

Storage:
    <user_config_dir>/custom_patterns.json

Each pattern has:
    - label: entity type / token label (e.g. "MEDICAL_RECORD")
    - pattern: a regex OR a plain literal, depending on match_type
    - match_type: "regex" | "word" | "contains" | "exact"
    - description: optional note
    - enabled: whether the pattern is active

Users can also enter patterns as free text (one per line) in the form:
    LABEL: pattern
e.g.
    MEDICAL_RECORD: MR-\\d{6}
    ROOM: (?:Kamar|Room)\\s?\\d+
Lines starting with '#' are treated as comments.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


VALID_MATCH_TYPES = ("regex", "word", "contains", "exact")


@dataclass
class CustomPattern:
    """A single user-defined detection pattern (global)."""

    label: str
    pattern: str
    match_type: str = "regex"
    description: str = ""
    enabled: bool = True

    def __post_init__(self) -> None:
        # Normalize label to a token-friendly form (UPPER_SNAKE)
        self.label = _normalize_label(self.label)
        if self.match_type not in VALID_MATCH_TYPES:
            self.match_type = "regex"

    def compile(self) -> re.Pattern | None:
        """Compile this pattern to a regex, or None if invalid."""
        try:
            if self.match_type == "regex":
                return re.compile(self.pattern, re.IGNORECASE)
            if self.match_type == "word":
                return re.compile(rf"\b{re.escape(self.pattern)}\b", re.IGNORECASE)
            if self.match_type == "exact":
                return re.compile(rf"^{re.escape(self.pattern)}$", re.IGNORECASE)
            # contains
            return re.compile(re.escape(self.pattern), re.IGNORECASE)
        except re.error as e:
            logger.warning(f"Invalid custom pattern '{self.pattern}': {e}")
            return None

    def is_valid(self) -> bool:
        """Check that the pattern compiles and has a label."""
        return bool(self.label) and self.compile() is not None

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "pattern": self.pattern,
            "match_type": self.match_type,
            "description": self.description,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CustomPattern:
        return cls(
            label=data.get("label", "CUSTOM"),
            pattern=data.get("pattern", ""),
            match_type=data.get("match_type", "regex"),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
        )


def _normalize_label(label: str) -> str:
    """Normalize a label to UPPER_SNAKE_CASE token form."""
    label = (label or "").strip()
    if not label:
        return "CUSTOM"
    # Replace non-alphanumeric with underscore, collapse repeats, uppercase
    norm = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_").upper()
    return norm or "CUSTOM"


# ----------------------------------------------------------------------------
# Free-text parsing ("LABEL: pattern" per line)
# ----------------------------------------------------------------------------

def parse_patterns_text(text: str, match_type: str = "regex") -> list[CustomPattern]:
    """
    Parse free-text input into CustomPattern objects.

    Each non-empty, non-comment line should look like:
        LABEL: pattern

    If a line has no ':' separator, the whole line is treated as the pattern
    with a default "CUSTOM" label.

    Args:
        text: Multi-line user input.
        match_type: Match type to apply to all parsed patterns.

    Returns:
        List of valid CustomPattern objects.
    """
    patterns: list[CustomPattern] = []
    if not text:
        return patterns

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" in line:
            label, _, pattern = line.partition(":")
            label = label.strip()
            pattern = pattern.strip()
        else:
            label = "CUSTOM"
            pattern = line

        if not pattern:
            continue

        cp = CustomPattern(
            label=label,
            pattern=pattern,
            match_type=match_type,
        )
        if cp.is_valid():
            patterns.append(cp)
        else:
            logger.warning(f"Skipping invalid custom pattern line: {raw_line!r}")

    return patterns


def patterns_to_text(patterns: list[CustomPattern]) -> str:
    """Render patterns back to editable free-text ("LABEL: pattern" per line)."""
    lines = []
    for p in patterns:
        lines.append(f"{p.label}: {p.pattern}")
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# Global storage
# ----------------------------------------------------------------------------

class CustomPatternStore:
    """Loads and saves global custom patterns from the user config directory."""

    FILENAME = "custom_patterns.json"

    def __init__(self, config_path: Path | None = None) -> None:
        if config_path is not None:
            self._path = config_path
        else:
            from sandiraksa.config.settings import get_app_paths

            self._path = get_app_paths().config_dir / self.FILENAME

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[CustomPattern]:
        """Load patterns from disk. Returns empty list if none/invalid."""
        if not self._path.exists():
            return []
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("patterns", []) if isinstance(data, dict) else data
            return [CustomPattern.from_dict(d) for d in items]
        except Exception as e:
            logger.warning(f"Failed to load custom patterns: {e}")
            return []

    def save(self, patterns: list[CustomPattern]) -> None:
        """Save patterns to disk atomically."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"patterns": [p.to_dict() for p in patterns]}
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp.replace(self._path)

    def save_from_text(self, text: str, match_type: str = "regex") -> list[CustomPattern]:
        """Parse free text, save, and return the resulting patterns."""
        patterns = parse_patterns_text(text, match_type=match_type)
        self.save(patterns)
        return patterns


# ----------------------------------------------------------------------------
# Matching against text
# ----------------------------------------------------------------------------

@dataclass
class CustomMatch:
    """A single custom-pattern match in text."""

    label: str
    value: str
    start: int
    end: int


def find_custom_matches(
    text: str,
    patterns: list[CustomPattern] | None = None,
) -> list[CustomMatch]:
    """
    Find all custom-pattern matches in a text string.

    Args:
        text: The text to scan.
        patterns: Patterns to use. If None, loads global patterns from disk.

    Returns:
        List of CustomMatch (deduplicated by span), sorted by position.
    """
    if patterns is None:
        patterns = get_global_patterns()

    if not text or not patterns:
        return []

    matches: list[CustomMatch] = []
    seen_spans: set[tuple[int, int]] = set()

    for p in patterns:
        if not p.enabled:
            continue
        compiled = p.compile()
        if compiled is None:
            continue
        for m in compiled.finditer(text):
            span = (m.start(), m.end())
            if span in seen_spans or m.start() == m.end():
                continue
            seen_spans.add(span)
            matches.append(CustomMatch(
                label=p.label,
                value=m.group(),
                start=m.start(),
                end=m.end(),
            ))

    matches.sort(key=lambda x: x.start)
    return matches


# ----------------------------------------------------------------------------
# Cached global accessor
# ----------------------------------------------------------------------------

_cached_patterns: list[CustomPattern] | None = None


def get_global_patterns(force_reload: bool = False) -> list[CustomPattern]:
    """Get the global custom patterns (cached)."""
    global _cached_patterns
    if _cached_patterns is None or force_reload:
        _cached_patterns = CustomPatternStore().load()
    return _cached_patterns


def reload_global_patterns() -> list[CustomPattern]:
    """Force reload the global patterns from disk."""
    return get_global_patterns(force_reload=True)


def save_global_patterns_from_text(text: str, match_type: str = "regex") -> list[CustomPattern]:
    """Save global patterns from free text and refresh the cache."""
    global _cached_patterns
    store = CustomPatternStore()
    patterns = store.save_from_text(text, match_type=match_type)
    _cached_patterns = patterns
    return patterns


__all__ = [
    "CustomPattern",
    "CustomMatch",
    "CustomPatternStore",
    "parse_patterns_text",
    "patterns_to_text",
    "find_custom_matches",
    "get_global_patterns",
    "reload_global_patterns",
    "save_global_patterns_from_text",
]
