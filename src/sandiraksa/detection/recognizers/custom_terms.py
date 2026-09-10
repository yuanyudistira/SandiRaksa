"""
Custom Terms Recognizer.

Allows users to define project-specific sensitive terms that
should be detected and protected. Supports:
- Exact match terms (case-insensitive)
- Regex patterns
- Word boundary matching
- Custom entity types per term
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

from sandiraksa.detection.context import DetectionResult
from sandiraksa.detection.engine import BaseRecognizer
from sandiraksa.domain.policy import CustomRule

if TYPE_CHECKING:
    from sandiraksa.storage.repositories import CustomRuleRepository

logger = logging.getLogger(__name__)


class MatchType(str, Enum):
    """Types of matching for custom terms."""

    EXACT = "exact"  # Exact match (case-insensitive)
    WORD = "word"  # Word boundary match
    REGEX = "regex"  # Regular expression
    CONTAINS = "contains"  # Substring match


@dataclass
class CustomTerm:
    """
    A custom term to detect.

    Attributes:
        id: Unique identifier (from database).
        pattern: The pattern or term to match.
        match_type: How to match the pattern.
        entity_type: Entity type to assign to matches.
        score: Confidence score for matches (0.0-1.0).
        case_sensitive: Whether matching is case-sensitive.
        description: Optional description of why this term is sensitive.
    """

    id: str
    pattern: str
    match_type: MatchType = MatchType.WORD
    entity_type: str = "CUSTOM_TERM"
    score: float = 0.9
    case_sensitive: bool = False
    description: str = ""

    # Compiled regex (cached)
    _compiled: re.Pattern | None = field(default=None, repr=False)

    def compile(self) -> re.Pattern:
        """Compile the term to a regex pattern."""
        if self._compiled is not None:
            return self._compiled

        flags = 0 if self.case_sensitive else re.IGNORECASE

        if self.match_type == MatchType.EXACT:
            # Exact match with word boundaries
            escaped = re.escape(self.pattern)
            pattern = f"^{escaped}$"

        elif self.match_type == MatchType.WORD:
            # Word boundary match. Also reject hyphen-adjacency so a term like
            # "secret" does not match inside a hyphenated compound such as
            # "top-secret" (treated as a distinct token).
            escaped = re.escape(self.pattern)
            pattern = rf"(?<![\w-]){escaped}(?![\w-])"

        elif self.match_type == MatchType.CONTAINS:
            # Substring match
            escaped = re.escape(self.pattern)
            pattern = escaped

        elif self.match_type == MatchType.REGEX:
            # User-provided regex
            pattern = self.pattern

        else:
            # Default to word boundary
            escaped = re.escape(self.pattern)
            pattern = rf"\b{escaped}\b"

        try:
            self._compiled = re.compile(pattern, flags)
        except re.error as e:
            logger.error(f"Invalid regex pattern '{self.pattern}': {e}")
            # Fallback to escaped literal
            self._compiled = re.compile(re.escape(self.pattern), flags)

        return self._compiled

    @classmethod
    def from_custom_rule(cls, rule: CustomRule) -> CustomTerm:
        """Create a CustomTerm from a CustomRule domain model."""
        # Map rule type to match type
        match_type_map = {
            "exact": MatchType.EXACT,
            "word": MatchType.WORD,
            "regex": MatchType.REGEX,
            "contains": MatchType.CONTAINS,
        }
        match_type = match_type_map.get(
            rule.pattern_type.lower() if hasattr(rule, "pattern_type") else "word",
            MatchType.WORD,
        )

        return cls(
            id=rule.id,
            pattern=rule.pattern,
            match_type=match_type,
            entity_type=rule.entity_type if rule.entity_type else "CUSTOM_TERM",
            score=rule.confidence if hasattr(rule, "confidence") else 0.9,
            case_sensitive=rule.case_sensitive if hasattr(rule, "case_sensitive") else False,
            description=rule.description if rule.description else "",
        )


class CustomTermsRecognizer(BaseRecognizer):
    """
    Recognizer for user-defined custom terms.

    Can be configured with a list of terms or loaded from database.
    """

    # Maximum number of terms to process (performance limit)
    MAX_TERMS: ClassVar[int] = 1000

    def __init__(
        self,
        terms: list[CustomTerm] | None = None,
        project_id: str | None = None,
    ) -> None:
        """
        Initialize custom terms recognizer.

        Args:
            terms: List of custom terms to detect.
            project_id: Project ID for loading terms from database.
        """
        super().__init__("custom_terms", ["CUSTOM_TERM"])

        self._terms: list[CustomTerm] = terms or []
        self._project_id = project_id
        self._terms_loaded = False

        # Cache entity types from terms
        self._update_supported_entities()

    def _update_supported_entities(self) -> None:
        """Update supported entities based on loaded terms."""
        entity_types = {"CUSTOM_TERM"}  # Always support base type
        for term in self._terms:
            entity_types.add(term.entity_type)
        self._supported_entities = list(entity_types)

    def add_term(self, term: CustomTerm) -> None:
        """Add a custom term."""
        if len(self._terms) >= self.MAX_TERMS:
            logger.warning(f"Maximum term limit ({self.MAX_TERMS}) reached")
            return

        self._terms.append(term)
        self._update_supported_entities()

    def add_terms(self, terms: list[CustomTerm]) -> None:
        """Add multiple custom terms."""
        for term in terms:
            self.add_term(term)

    def remove_term(self, term_id: str) -> None:
        """Remove a custom term by ID."""
        self._terms = [t for t in self._terms if t.id != term_id]
        self._update_supported_entities()

    def clear_terms(self) -> None:
        """Remove all custom terms."""
        self._terms.clear()
        self._update_supported_entities()

    def load_from_rules(self, rules: list[CustomRule]) -> None:
        """Load terms from CustomRule domain objects."""
        self.clear_terms()
        for rule in rules:
            if rule.enabled:
                term = CustomTerm.from_custom_rule(rule)
                self.add_term(term)

    def analyze(
        self,
        text: str,
        entities: list[str],
    ) -> list[DetectionResult]:
        """Analyze text for custom terms."""
        if not text or not self._terms:
            return []

        results: list[DetectionResult] = []

        for term in self._terms:
            # Only include a term when its own entity type was requested.
            # (Previously "CUSTOM_TERM" acted as a wildcard that returned every
            # term regardless of type; that prevented requesting only the base
            # custom terms.)
            if term.entity_type not in entities:
                continue

            # Compile and search
            pattern = term.compile()

            for match in pattern.finditer(text):
                results.append(
                    DetectionResult(
                        entity_type=term.entity_type,
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        score=term.score,
                        recognizer_name="custom_terms",
                        analysis_explanation={
                            "term_id": term.id,
                            "pattern": term.pattern,
                            "match_type": term.match_type.value,
                            "description": term.description,
                        },
                    )
                )

        return results

    @property
    def term_count(self) -> int:
        """Get the number of loaded terms."""
        return len(self._terms)


class CustomTermsManager:
    """
    Manager for custom terms across projects.

    Handles loading, saving, and synchronizing custom terms
    with the database.
    """

    def __init__(self, repository: CustomRuleRepository | None = None) -> None:
        """
        Initialize manager.

        Args:
            repository: Repository for persistence. If None, in-memory only.
        """
        self._repository = repository
        self._recognizers: dict[str, CustomTermsRecognizer] = {}

    def get_recognizer(self, project_id: str) -> CustomTermsRecognizer:
        """
        Get or create a recognizer for a project.

        Args:
            project_id: The project ID.

        Returns:
            Configured CustomTermsRecognizer for the project.
        """
        if project_id not in self._recognizers:
            recognizer = CustomTermsRecognizer(project_id=project_id)

            # Load from database if available
            if self._repository:
                rules = self._repository.list_by_project(project_id)
                recognizer.load_from_rules(rules)

            self._recognizers[project_id] = recognizer

        return self._recognizers[project_id]

    def reload_terms(self, project_id: str) -> None:
        """Reload terms from database for a project."""
        if project_id in self._recognizers and self._repository:
            rules = self._repository.list_by_project(project_id)
            self._recognizers[project_id].load_from_rules(rules)

    def add_term(
        self,
        project_id: str,
        pattern: str,
        match_type: MatchType = MatchType.WORD,
        entity_type: str = "CUSTOM_TERM",
        description: str = "",
        case_sensitive: bool = False,
    ) -> CustomTerm:
        """
        Add a new custom term to a project.

        Args:
            project_id: The project ID.
            pattern: The pattern to match.
            match_type: How to match the pattern.
            entity_type: Entity type for matches.
            description: Description of why this is sensitive.
            case_sensitive: Whether matching is case-sensitive.

        Returns:
            The created CustomTerm.
        """
        from uuid import uuid4

        term = CustomTerm(
            id=str(uuid4()),
            pattern=pattern,
            match_type=match_type,
            entity_type=entity_type,
            description=description,
            case_sensitive=case_sensitive,
        )

        # Save to database if available
        if self._repository:
            self._repository.create(
                project_id=project_id,
                pattern=pattern,
                entity_type=entity_type,
                description=description,
            )

        # Add to recognizer
        recognizer = self.get_recognizer(project_id)
        recognizer.add_term(term)

        return term

    def remove_term(self, project_id: str, term_id: str) -> None:
        """Remove a custom term from a project."""
        if self._repository:
            self._repository.delete(term_id)

        if project_id in self._recognizers:
            self._recognizers[project_id].remove_term(term_id)

    def close_project(self, project_id: str) -> None:
        """Close and cleanup recognizer for a project."""
        if project_id in self._recognizers:
            self._recognizers[project_id].clear_terms()
            del self._recognizers[project_id]


# Global manager instance
_manager: CustomTermsManager | None = None


def get_custom_terms_manager() -> CustomTermsManager:
    """Get the global custom terms manager."""
    global _manager
    if _manager is None:
        _manager = CustomTermsManager()
    return _manager


def initialize_custom_terms_manager(
    repository: CustomRuleRepository | None = None,
) -> CustomTermsManager:
    """Initialize the global custom terms manager with repository."""
    global _manager
    _manager = CustomTermsManager(repository)
    return _manager
