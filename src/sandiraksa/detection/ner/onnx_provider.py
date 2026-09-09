"""
ONNX NER Provider.

Provides NER inference using ONNX Runtime for efficient CPU-based
inference without GPU requirements. Designed for Indonesian NER models.

Model Structure Expected:
    model.onnx          - ONNX model file
    tokenizer.json      - Tokenizers library tokenizer
    config.json         - Model configuration
    labels.json         - Entity label mapping (id -> label)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from sandiraksa.detection.ner.base import (
    BaseNERProvider,
    NERConfig,
    NERPrediction,
    NERResult,
)

logger = logging.getLogger(__name__)


@dataclass
class ONNXModelConfig:
    """Configuration for ONNX model."""

    model_path: Path
    tokenizer_path: Path
    labels_path: Path
    config_path: Path | None = None

    # Model metadata
    model_name: str = "indonesian-ner"
    max_length: int = 512

    # Inference settings
    num_threads: int = 4
    use_gpu: bool = False

    @classmethod
    def from_directory(cls, model_dir: Path) -> "ONNXModelConfig":
        """
        Create config from a model directory.

        Expected structure:
            model_dir/
            ├── model.onnx
            ├── tokenizer.json
            ├── config.json (optional)
            └── labels.json
        """
        model_dir = Path(model_dir)

        model_path = model_dir / "model.onnx"
        tokenizer_path = model_dir / "tokenizer.json"
        labels_path = model_dir / "labels.json"
        config_path = model_dir / "config.json"

        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        if not tokenizer_path.exists():
            raise FileNotFoundError(f"Tokenizer not found: {tokenizer_path}")
        if not labels_path.exists():
            raise FileNotFoundError(f"Labels not found: {labels_path}")

        return cls(
            model_path=model_path,
            tokenizer_path=tokenizer_path,
            labels_path=labels_path,
            config_path=config_path if config_path.exists() else None,
        )


class ONNXNERProvider(BaseNERProvider):
    """
    ONNX-based NER provider.

    Uses ONNX Runtime for efficient CPU inference. Supports
    token classification models (BERT-style).

    Features:
    - CPU-optimized inference
    - Lazy model loading
    - BIO tag decoding
    - Subword token alignment
    """

    def __init__(
        self,
        model_config: ONNXModelConfig | None = None,
        model_dir: Path | str | None = None,
    ):
        """
        Initialize ONNX NER provider.

        Args:
            model_config: Pre-built model configuration
            model_dir: Path to model directory (alternative to config)
        """
        super().__init__(
            name="onnx_ner",
            supported_entities=["PERSON", "ORG", "LOC", "MISC"],
        )

        if model_config:
            self._config = model_config
        elif model_dir:
            self._config = ONNXModelConfig.from_directory(Path(model_dir))
        else:
            self._config = None

        # Model components (loaded lazily)
        self._session = None
        self._tokenizer = None
        self._id2label: dict[int, str] = {}
        self._label2id: dict[str, int] = {}

    def load(self) -> None:
        """Load the ONNX model and tokenizer."""
        if self._loaded:
            return

        if self._config is None:
            raise ValueError("No model configuration provided")

        try:
            self._load_model()
            self._load_tokenizer()
            self._load_labels()
            self._loaded = True
            logger.info(f"Loaded ONNX NER model: {self._config.model_name}")
        except Exception as e:
            logger.error(f"Failed to load ONNX model: {e}")
            raise

    def _load_model(self) -> None:
        """Load ONNX model with ONNX Runtime."""
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError(
                "onnxruntime is required for ONNX inference. "
                "Install with: pip install onnxruntime"
            )

        # Session options
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = self._config.num_threads
        sess_options.inter_op_num_threads = self._config.num_threads
        sess_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        # Execution provider
        if self._config.use_gpu:
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        else:
            providers = ["CPUExecutionProvider"]

        self._session = ort.InferenceSession(
            str(self._config.model_path),
            sess_options=sess_options,
            providers=providers,
        )

        logger.debug(f"ONNX session created with providers: {providers}")

    def _load_tokenizer(self) -> None:
        """Load tokenizer using tokenizers library."""
        try:
            from tokenizers import Tokenizer
        except ImportError:
            raise ImportError(
                "tokenizers is required for tokenization. "
                "Install with: pip install tokenizers"
            )

        self._tokenizer = Tokenizer.from_file(str(self._config.tokenizer_path))

    def _load_labels(self) -> None:
        """Load entity label mapping."""
        with open(self._config.labels_path, "r", encoding="utf-8") as f:
            labels_data = json.load(f)

        # Handle different label file formats
        if isinstance(labels_data, dict):
            if "id2label" in labels_data:
                self._id2label = {int(k): v for k, v in labels_data["id2label"].items()}
            else:
                # Assume it's already id -> label
                self._id2label = {int(k): v for k, v in labels_data.items()}
        elif isinstance(labels_data, list):
            self._id2label = {i: label for i, label in enumerate(labels_data)}

        self._label2id = {v: k for k, v in self._id2label.items()}

        logger.debug(f"Loaded {len(self._id2label)} entity labels")

    def unload(self) -> None:
        """Unload model from memory."""
        self._session = None
        self._tokenizer = None
        self._id2label = {}
        self._label2id = {}
        self._loaded = False
        logger.info("ONNX NER model unloaded")

    def predict(
        self,
        texts: list[str],
        config: NERConfig | None = None,
    ) -> list[NERResult]:
        """
        Perform NER on a list of texts.

        Args:
            texts: List of text strings
            config: Optional configuration

        Returns:
            List of NERResult
        """
        if not self._loaded:
            self.load()

        config = config or NERConfig()
        results = []

        for text in texts:
            start_time = time.perf_counter()

            try:
                predictions = self._predict_single_internal(text, config)
                processing_time = (time.perf_counter() - start_time) * 1000

                result = NERResult(
                    text=text,
                    predictions=predictions,
                    processing_time_ms=processing_time,
                    model_name=self._config.model_name,
                )
            except Exception as e:
                logger.error(f"NER prediction failed: {e}")
                result = NERResult(text=text, predictions=[])

            results.append(result)

        return results

    def _predict_single_internal(
        self,
        text: str,
        config: NERConfig,
    ) -> list[NERPrediction]:
        """Internal prediction for a single text."""
        if not text.strip():
            return []

        # Tokenize
        encoding = self._tokenizer.encode(text)
        tokens = encoding.tokens
        token_ids = encoding.ids
        offsets = encoding.offsets

        # Truncate if needed
        max_len = min(config.max_length, self._config.max_length)
        if len(token_ids) > max_len:
            token_ids = token_ids[:max_len]
            tokens = tokens[:max_len]
            offsets = offsets[:max_len]

        # Prepare inputs
        input_ids = np.array([token_ids], dtype=np.int64)
        attention_mask = np.ones_like(input_ids)

        # Run inference
        inputs = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }

        # Add token_type_ids if model expects it
        input_names = [inp.name for inp in self._session.get_inputs()]
        if "token_type_ids" in input_names:
            inputs["token_type_ids"] = np.zeros_like(input_ids)

        outputs = self._session.run(None, inputs)
        logits = outputs[0]  # Shape: [batch, seq_len, num_labels]

        # Get predictions
        predictions = self._decode_predictions(
            text=text,
            tokens=tokens,
            offsets=offsets,
            logits=logits[0],
            config=config,
        )

        return predictions

    def _decode_predictions(
        self,
        text: str,
        tokens: list[str],
        offsets: list[tuple[int, int]],
        logits: np.ndarray,
        config: NERConfig,
    ) -> list[NERPrediction]:
        """
        Decode model output to NER predictions.

        Handles BIO tag decoding and subword token alignment.
        """
        # Get predicted labels and scores
        probs = self._softmax(logits)
        predicted_ids = np.argmax(logits, axis=-1)
        predicted_scores = np.max(probs, axis=-1)

        # Decode BIO tags to entities
        entities: list[NERPrediction] = []
        current_entity = None

        for i, (token, offset, label_id, score) in enumerate(
            zip(tokens, offsets, predicted_ids, predicted_scores)
        ):
            # Skip special tokens
            if token in ["[CLS]", "[SEP]", "[PAD]", "<s>", "</s>", "<pad>"]:
                continue

            # Skip if offset is invalid
            if offset[0] == offset[1]:
                continue

            label = self._id2label.get(label_id, "O")

            if label == "O":
                # End current entity if any
                if current_entity:
                    entities.append(current_entity)
                    current_entity = None
            elif label.startswith("B-"):
                # Begin new entity
                if current_entity:
                    entities.append(current_entity)

                entity_type = label[2:]
                current_entity = NERPrediction(
                    start=offset[0],
                    end=offset[1],
                    text=text[offset[0]:offset[1]],
                    entity_type=entity_type,
                    score=float(score),
                    source=self._name,
                )
            elif label.startswith("I-"):
                # Continue entity
                entity_type = label[2:]
                if current_entity and current_entity.entity_type == entity_type:
                    # Extend current entity
                    current_entity = NERPrediction(
                        start=current_entity.start,
                        end=offset[1],
                        text=text[current_entity.start:offset[1]],
                        entity_type=entity_type,
                        score=min(current_entity.score, float(score)),
                        source=self._name,
                    )
                else:
                    # Start new entity (orphan I- tag)
                    if current_entity:
                        entities.append(current_entity)
                    current_entity = NERPrediction(
                        start=offset[0],
                        end=offset[1],
                        text=text[offset[0]:offset[1]],
                        entity_type=entity_type,
                        score=float(score),
                        source=self._name,
                    )

        # Don't forget last entity
        if current_entity:
            entities.append(current_entity)

        # Filter by config
        filtered = self._filter_predictions(entities, config)

        # Resolve overlaps
        resolved = self._resolve_overlaps(filtered)

        return resolved

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        """Compute softmax along last axis."""
        exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return exp_x / np.sum(exp_x, axis=-1, keepdims=True)


class MockNERProvider(BaseNERProvider):
    """
    Mock NER provider for testing.

    Returns predefined or pattern-based predictions without
    actual model inference.
    """

    def __init__(
        self,
        predictions_map: dict[str, list[NERPrediction]] | None = None,
    ):
        """
        Initialize mock provider.

        Args:
            predictions_map: Map of text -> predictions for testing
        """
        super().__init__(name="mock_ner")
        self._predictions_map = predictions_map or {}
        self._loaded = True

    def load(self) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def predict(
        self,
        texts: list[str],
        config: NERConfig | None = None,
    ) -> list[NERResult]:
        """Return mock predictions."""
        config = config or NERConfig()
        results = []

        for text in texts:
            predictions = self._predictions_map.get(text, [])
            filtered = self._filter_predictions(predictions, config)

            results.append(
                NERResult(
                    text=text,
                    predictions=filtered,
                    processing_time_ms=1.0,
                    model_name="mock",
                )
            )

        return results

    def add_prediction(
        self,
        text: str,
        start: int,
        end: int,
        entity_type: str,
        score: float = 0.9,
    ) -> None:
        """Add a mock prediction for testing."""
        if text not in self._predictions_map:
            self._predictions_map[text] = []

        self._predictions_map[text].append(
            NERPrediction(
                start=start,
                end=end,
                text=text[start:end],
                entity_type=entity_type,
                score=score,
                source="mock_ner",
            )
        )


__all__ = [
    "ONNXModelConfig",
    "ONNXNERProvider",
    "MockNERProvider",
]
