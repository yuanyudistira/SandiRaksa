"""
Local NER (Named Entity Recognition) module for Indonesian text.

This module provides local, privacy-preserving NER capabilities
using ONNX models for CPU inference. No cloud/remote inference needed.

Key components:
- NERProvider: Protocol for NER backends
- ONNXNERProvider: ONNX runtime implementation
- NERModelLoader: Lazy model loading
- NERBatchProcessor: Efficient batch processing
- IndonesianNERRecognizer: Presidio-compatible recognizer
"""

from sandiraksa.detection.ner.base import (
    NERProvider,
    NERPrediction,
    NEREntityType,
    NERConfig,
    NERResult,
    BaseNERProvider,
)
from sandiraksa.detection.ner.loader import (
    NERModelLoader,
    get_ner_model,
    is_ner_available,
    unload_ner_model,
)
from sandiraksa.detection.ner.batch import (
    NERBatchProcessor,
    BatchConfig,
    BatchProgress,
)
from sandiraksa.detection.ner.onnx_provider import (
    ONNXNERProvider,
    ONNXModelConfig,
    MockNERProvider,
)
from sandiraksa.detection.ner.recognizer import (
    IndonesianNERRecognizer,
    MockIndonesianNERRecognizer,
    create_indonesian_ner_recognizer,
)

__all__ = [
    # Base
    "NERProvider",
    "NERPrediction",
    "NEREntityType",
    "NERConfig",
    "NERResult",
    "BaseNERProvider",
    # ONNX Provider
    "ONNXNERProvider",
    "ONNXModelConfig",
    "MockNERProvider",
    # Loader
    "NERModelLoader",
    "get_ner_model",
    "is_ner_available",
    "unload_ner_model",
    # Batch
    "NERBatchProcessor",
    "BatchConfig",
    "BatchProgress",
    # Recognizer
    "IndonesianNERRecognizer",
    "MockIndonesianNERRecognizer",
    "create_indonesian_ner_recognizer",
]
