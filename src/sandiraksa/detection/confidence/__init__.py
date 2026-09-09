"""
Confidence & Explainability module for PII detection.

Provides:
- ConfidenceClassifier: High/Medium/Low confidence bands
- ScanMode: STRICT vs BALANCED detection modes
- EvidenceBuilder: Explanation generation for findings
- ConfidenceFilter: Filtering by confidence/entity type
- LeakageScanner: Post-protection verification
"""

from sandiraksa.detection.confidence.classifier import (
    ConfidenceClassifier,
    ConfidenceBand,
    ConfidenceThresholds,
    EntityThresholds,
)
from sandiraksa.detection.confidence.modes import (
    ScanMode,
    ScanModeConfig,
    get_mode_thresholds,
)
from sandiraksa.detection.confidence.evidence import (
    EvidenceBuilder,
    EvidenceType,
    Evidence,
    ExplanationResult,
)
from sandiraksa.detection.confidence.filtering import (
    ConfidenceFilter,
    FilterCriteria,
)
from sandiraksa.detection.confidence.rescan import (
    LeakageScanner,
    LeakageResult,
    LeakageFinding,
)

__all__ = [
    # Classifier
    "ConfidenceClassifier",
    "ConfidenceBand",
    "ConfidenceThresholds",
    "EntityThresholds",
    # Modes
    "ScanMode",
    "ScanModeConfig",
    "get_mode_thresholds",
    # Evidence
    "EvidenceBuilder",
    "EvidenceType",
    "Evidence",
    "ExplanationResult",
    # Filtering
    "ConfidenceFilter",
    "FilterCriteria",
    # Rescan
    "LeakageScanner",
    "LeakageResult",
    "LeakageFinding",
]
