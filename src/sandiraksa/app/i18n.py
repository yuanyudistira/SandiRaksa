"""
Internationalization (i18n) support for SandiRaksa.

Provides localized strings with fallback support.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class Language(str, Enum):
    """Supported languages."""

    INDONESIAN = "id_ID"
    ENGLISH = "en_US"

    @property
    def display_name(self) -> str:
        """Get human-readable name."""
        names = {
            Language.INDONESIAN: "Bahasa Indonesia",
            Language.ENGLISH: "English",
        }
        return names.get(self, self.value)


def _get_i18n_dir() -> Path:
    """Get the i18n directory path."""
    return Path(__file__).parent.parent / "resources" / "i18n"


class Translator(QObject):
    """
    Translator for UI strings.

    Emits signal when language changes so UI can update.
    """

    language_changed = Signal(str)

    _instance: Translator | None = None

    def __init__(self) -> None:
        super().__init__()
        self._current_language = Language.INDONESIAN
        self._strings: dict[str, Any] = {}
        self._fallback_strings: dict[str, Any] = {}
        self._load_fallback()
        self._load_language(self._current_language)

    @classmethod
    def instance(cls) -> Translator:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = Translator()
        return cls._instance

    @property
    def current_language(self) -> Language:
        """Get current language."""
        return self._current_language

    def _load_fallback(self) -> None:
        """Load English as fallback."""
        try:
            path = _get_i18n_dir() / f"{Language.ENGLISH.value}.json"
            with open(path, encoding="utf-8") as f:
                self._fallback_strings = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load fallback language: {e}")
            self._fallback_strings = {}

    def _load_language(self, language: Language) -> None:
        """Load language strings from JSON file."""
        try:
            path = _get_i18n_dir() / f"{language.value}.json"
            with open(path, encoding="utf-8") as f:
                self._strings = json.load(f)
            logger.info(f"Loaded language: {language.value}")
        except FileNotFoundError:
            logger.warning(f"Language file not found: {language.value}, using fallback")
            self._strings = self._fallback_strings.copy()
        except Exception as e:
            logger.error(f"Failed to load language {language.value}: {e}")
            self._strings = self._fallback_strings.copy()

    def set_language(self, language: Language) -> None:
        """
        Change the current language.

        Args:
            language: New language to use.
        """
        if language != self._current_language:
            self._current_language = language
            self._load_language(language)
            self.language_changed.emit(language.value)
            logger.info(f"Language changed to: {language.value}")

    def get(self, key: str, **kwargs: Any) -> str:
        """
        Get translated string by dot-notation key.

        Args:
            key: Key in dot notation (e.g., "menu.file")
            **kwargs: Format arguments for string interpolation

        Returns:
            Translated string, or key if not found.
        """
        value = self._resolve_key(key, self._strings)
        if value is None:
            # Try fallback
            value = self._resolve_key(key, self._fallback_strings)
        if value is None:
            logger.warning(f"Missing translation: {key}")
            return key

        # Apply format arguments
        if kwargs:
            try:
                # Support both {key} and {count} style placeholders
                value = value.format(**kwargs)
            except KeyError as e:
                logger.warning(f"Missing format key {e} for {key}")

        return value

    def _resolve_key(self, key: str, strings: dict[str, Any]) -> str | None:
        """Resolve a dot-notation key to its value."""
        parts = key.split(".")
        current: Any = strings
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current if isinstance(current, str) else None

    def get_all(self, prefix: str) -> dict[str, str]:
        """
        Get all strings under a prefix.

        Args:
            prefix: Key prefix (e.g., "entity_types")

        Returns:
            Dictionary of key -> translated string
        """
        result = {}
        data = self._resolve_key_data(prefix, self._strings)
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str):
                    result[k] = v
        return result

    def _resolve_key_data(self, key: str, strings: dict[str, Any]) -> Any:
        """Resolve a dot-notation key to its data (dict or string)."""
        parts = key.split(".")
        current: Any = strings
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current


# Convenience function
def tr(key: str, **kwargs: Any) -> str:
    """
    Translate a string.

    Shorthand for Translator.instance().get(key, **kwargs)

    Args:
        key: Translation key in dot notation.
        **kwargs: Format arguments.

    Returns:
        Translated string.
    """
    return Translator.instance().get(key, **kwargs)


def get_translator() -> Translator:
    """Get the translator instance."""
    return Translator.instance()


__all__ = [
    "Language",
    "Translator",
    "get_translator",
    "tr",
]
