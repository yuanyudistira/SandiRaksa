"""
NER Model Loader with Lazy Loading Singleton.

Provides centralized model management with:
- Lazy loading (load only when needed)
- Singleton pattern (one instance per model)
- Automatic model discovery
- Memory management (unload when not needed)
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sandiraksa.detection.ner.base import NERProvider

logger = logging.getLogger(__name__)

# Default model locations to search
DEFAULT_MODEL_PATHS = [
    # Project-local models
    Path("models/ner"),
    Path("data/models/ner"),
    # User-level models
    Path.home() / ".sandiraksa" / "models" / "ner",
    # System-level models
    Path("/usr/local/share/sandiraksa/models/ner"),
    Path("C:/ProgramData/SandiRaksa/models/ner"),
]

# Environment variable for custom model path
MODEL_PATH_ENV = "SANDIRAKSA_NER_MODEL_PATH"


class NERModelLoader:
    """
    Singleton loader for NER models.

    Handles lazy loading, caching, and lifecycle management
    of NER providers. Thread-safe.

    Usage:
        loader = NERModelLoader.get_instance()
        if loader.is_available():
            provider = loader.get_provider()
            result = provider.predict_single("Budi tinggal di Jakarta")
    """

    _instance: "NERModelLoader | None" = None
    _lock = threading.Lock()

    def __init__(self):
        """Initialize loader (use get_instance() instead)."""
        self._provider: "NERProvider | None" = None
        self._provider_lock = threading.Lock()
        self._model_path: Path | None = None
        self._initialized = False
        self._available: bool | None = None  # None = not checked yet

    @classmethod
    def get_instance(cls) -> "NERModelLoader":
        """
        Get the singleton instance.

        Returns:
            NERModelLoader instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset the singleton instance.

        Useful for testing or when model path changes.
        """
        with cls._lock:
            if cls._instance is not None:
                cls._instance.unload()
                cls._instance = None

    def is_available(self) -> bool:
        """
        Check if NER model is available.

        Searches for model files without loading them.

        Returns:
            True if model files are found
        """
        if self._available is not None:
            return self._available

        self._model_path = self._find_model_path()
        self._available = self._model_path is not None

        if self._available:
            logger.info(f"NER model found at: {self._model_path}")
        else:
            logger.debug("No NER model found in search paths")

        return self._available

    def _find_model_path(self) -> Path | None:
        """
        Find the NER model directory.

        Searches in order:
        1. Environment variable
        2. Default paths

        Returns:
            Path to model directory or None
        """
        # Check environment variable first
        env_path = os.environ.get(MODEL_PATH_ENV)
        if env_path:
            path = Path(env_path)
            if self._is_valid_model_dir(path):
                return path
            logger.warning(
                f"Model path from {MODEL_PATH_ENV} is invalid: {env_path}"
            )

        # Search default paths
        for search_path in DEFAULT_MODEL_PATHS:
            if self._is_valid_model_dir(search_path):
                return search_path

            # Also check for named model subdirectories
            if search_path.exists():
                for subdir in search_path.iterdir():
                    if subdir.is_dir() and self._is_valid_model_dir(subdir):
                        return subdir

        return None

    def _is_valid_model_dir(self, path: Path) -> bool:
        """
        Check if path contains a valid NER model.

        Required files:
        - model.onnx
        - tokenizer.json
        - labels.json
        """
        if not path.exists() or not path.is_dir():
            return False

        required_files = ["model.onnx", "tokenizer.json", "labels.json"]
        return all((path / f).exists() for f in required_files)

    def get_provider(self) -> "NERProvider":
        """
        Get the NER provider, loading if necessary.

        Returns:
            NERProvider instance

        Raises:
            RuntimeError: If no model is available
        """
        if not self.is_available():
            raise RuntimeError(
                "NER model not available. "
                f"Set {MODEL_PATH_ENV} environment variable or "
                "place model in one of the default locations."
            )

        with self._provider_lock:
            if self._provider is None:
                self._load_provider()

        return self._provider

    def _load_provider(self) -> None:
        """Load the NER provider."""
        from sandiraksa.detection.ner.onnx_provider import (
            ONNXModelConfig,
            ONNXNERProvider,
        )

        logger.info(f"Loading NER model from: {self._model_path}")

        config = ONNXModelConfig.from_directory(self._model_path)
        self._provider = ONNXNERProvider(model_config=config)
        self._provider.load()

        logger.info("NER model loaded successfully")

    def unload(self) -> None:
        """
        Unload the NER model from memory.

        Frees resources. Model will be reloaded on next get_provider().
        """
        with self._provider_lock:
            if self._provider is not None:
                self._provider.unload()
                self._provider = None
                logger.info("NER model unloaded")

    def reload(self) -> None:
        """Reload the NER model."""
        self.unload()
        self._available = None
        self._model_path = None
        if self.is_available():
            self.get_provider()

    @property
    def model_path(self) -> Path | None:
        """Get the current model path."""
        return self._model_path

    @property
    def is_loaded(self) -> bool:
        """Check if the model is currently loaded."""
        return self._provider is not None and self._provider.is_loaded

    def set_model_path(self, path: Path | str) -> None:
        """
        Set a custom model path.

        Args:
            path: Path to model directory

        Raises:
            ValueError: If path is invalid
        """
        path = Path(path)
        if not self._is_valid_model_dir(path):
            raise ValueError(f"Invalid model directory: {path}")

        # Unload current model if any
        self.unload()

        self._model_path = path
        self._available = True
        logger.info(f"NER model path set to: {path}")


# Module-level convenience functions

def get_ner_model() -> "NERProvider":
    """
    Get the NER model provider.

    Convenience function that wraps NERModelLoader.

    Returns:
        NERProvider instance

    Raises:
        RuntimeError: If no model is available
    """
    return NERModelLoader.get_instance().get_provider()


def is_ner_available() -> bool:
    """
    Check if NER model is available.

    Convenience function that wraps NERModelLoader.

    Returns:
        True if NER model is available
    """
    return NERModelLoader.get_instance().is_available()


def unload_ner_model() -> None:
    """
    Unload the NER model from memory.

    Convenience function for memory management.
    """
    NERModelLoader.get_instance().unload()


__all__ = [
    "NERModelLoader",
    "get_ner_model",
    "is_ner_available",
    "unload_ner_model",
    "MODEL_PATH_ENV",
    "DEFAULT_MODEL_PATHS",
]
