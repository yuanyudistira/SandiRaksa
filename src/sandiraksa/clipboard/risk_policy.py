"""
Clipboard risk policy (design 46, 47) and stage entity sets (design 40).

Per-entity thresholds and severities, rather than one global threshold
(design 46). Entity keys use the names the existing recognizers actually emit
(ID_NIK, ID_NPWP, EMAIL_ADDRESS, PERSON, MEDICAL_RECORD, ...).
"""

from __future__ import annotations

from sandiraksa.clipboard.models import ClipboardRiskLevel, Finding

# Per-entity policy: minimum score to accept + severity (design 46).
# Keyed by the entity_type strings the recognizers emit.
ENTITY_POLICY: dict[str, dict] = {
    "ID_NIK": {"min_score": 0.70, "severity": "high"},
    "ID_NPWP": {"min_score": 0.70, "severity": "high"},
    "ID_KK": {"min_score": 0.70, "severity": "high"},
    "ID_PHONE": {"min_score": 0.60, "severity": "medium"},
    "ID_BPJS": {"min_score": 0.70, "severity": "high"},
    "PHONE_NUMBER": {"min_score": 0.60, "severity": "medium"},
    "EMAIL_ADDRESS": {"min_score": 0.75, "severity": "medium"},
    "CREDIT_CARD": {"min_score": 0.70, "severity": "high"},
    "IBAN_CODE": {"min_score": 0.70, "severity": "high"},
    "IP_ADDRESS": {"min_score": 0.60, "severity": "low"},
    "URL": {"min_score": 0.60, "severity": "low"},
    "PERSON": {"min_score": 0.85, "severity": "medium"},
    "DATE_OF_BIRTH": {"min_score": 0.70, "severity": "medium"},
    "DATE": {"min_score": 0.80, "severity": "low"},
    "MEDICAL_RECORD": {"min_score": 0.70, "severity": "critical"},
    "MEDICAL_INFO": {"min_score": 0.70, "severity": "critical"},
    "ADDRESS": {"min_score": 0.70, "severity": "medium"},
}

# Default policy for any entity not explicitly listed.
_DEFAULT_POLICY = {"min_score": 0.80, "severity": "medium"}

# Stage 1 = deterministic recognizers; Stage 2 = contextual/NER (design 40).
STAGE1_ENTITIES: list[str] = [
    "ID_NIK",
    "ID_NPWP",
    "ID_KK",
    "ID_PHONE",
    "ID_BPJS",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "CREDIT_CARD",
    "IBAN_CODE",
    "IP_ADDRESS",
    "URL",
    "MEDICAL_RECORD",
    "MEDICAL_INFO",
]

STAGE2_ENTITIES: list[str] = [
    "PERSON",
    "DATE_OF_BIRTH",
    "ADDRESS",
]

_SEVERITY_TO_RISK = {
    "low": ClipboardRiskLevel.LOW,
    "medium": ClipboardRiskLevel.MEDIUM,
    "high": ClipboardRiskLevel.HIGH,
    "critical": ClipboardRiskLevel.CRITICAL,
}


def policy_for(entity_type: str) -> dict:
    """Return the policy dict for an entity type (default if unlisted)."""
    return ENTITY_POLICY.get(entity_type, _DEFAULT_POLICY)


def severity_for(entity_type: str) -> str:
    """Return the severity label for an entity type."""
    return policy_for(entity_type)["severity"]


def passes_policy(entity_type: str, score: float) -> bool:
    """True if a detection meets its entity's minimum score (design 46)."""
    return score >= policy_for(entity_type)["min_score"]


def min_confidence_floor() -> float:
    """
    Lowest ``min_score`` across all policies.

    Used to set the engine's global floor so no entity is dropped before the
    per-entity policy can evaluate it.
    """
    values = [p["min_score"] for p in ENTITY_POLICY.values()]
    values.append(_DEFAULT_POLICY["min_score"])
    return min(values)


def compute_risk_level(findings: list[Finding]) -> ClipboardRiskLevel:
    """
    Aggregate findings into an overall risk level (design 47).

    Rules:
      * highest single-finding severity dominates;
      * multiple medium-or-higher findings escalate MEDIUM -> HIGH.
    """
    if not findings:
        return ClipboardRiskLevel.LOW

    highest = ClipboardRiskLevel.LOW
    medium_or_higher = 0
    for f in findings:
        level = _SEVERITY_TO_RISK.get(f.severity, ClipboardRiskLevel.MEDIUM)
        if level.rank > highest.rank:
            highest = level
        if level.rank >= ClipboardRiskLevel.MEDIUM.rank:
            medium_or_higher += 1

    # "Multiple medium entities -> HIGH" (design 47).
    if highest == ClipboardRiskLevel.MEDIUM and medium_or_higher >= 2:
        return ClipboardRiskLevel.HIGH

    return highest


__all__ = [
    "ENTITY_POLICY",
    "STAGE1_ENTITIES",
    "STAGE2_ENTITIES",
    "policy_for",
    "severity_for",
    "passes_policy",
    "min_confidence_floor",
    "compute_risk_level",
]
