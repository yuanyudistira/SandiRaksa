"""
One-way clipboard text treatment (design 48, 49).

v1 clipboard treatment is one-way and non-reversible - there is no ProjectVault
mapping (design 48). Replacements use contextual redaction labels
(``[NIK_REDACTED]`` etc.) which preserve meaning better than ``****``.

Replacement is applied in reverse span order so earlier offsets stay valid as
later spans are substituted (design 49).
"""

from __future__ import annotations

from sandiraksa.clipboard.models import Finding

# Map recognizer entity types to human-meaningful redaction labels (design 48).
_REPLACEMENTS: dict[str, str] = {
    "ID_NIK": "[NIK_REDACTED]",
    "ID_NPWP": "[NPWP_REDACTED]",
    "ID_KK": "[KK_REDACTED]",
    "ID_PHONE": "[PHONE_REDACTED]",
    "ID_BPJS": "[BPJS_REDACTED]",
    "PHONE_NUMBER": "[PHONE_REDACTED]",
    "EMAIL_ADDRESS": "[EMAIL_REDACTED]",
    "CREDIT_CARD": "[CARD_REDACTED]",
    "IBAN_CODE": "[IBAN_REDACTED]",
    "IP_ADDRESS": "[IP_REDACTED]",
    "URL": "[URL_REDACTED]",
    "PERSON": "[NAME_REDACTED]",
    "DATE_OF_BIRTH": "[DOB_REDACTED]",
    "DATE": "[DATE_REDACTED]",
    "MEDICAL_RECORD": "[MEDICAL_ID_REDACTED]",
    "MEDICAL_INFO": "[MEDICAL_INFO_REDACTED]",
    "ADDRESS": "[ADDRESS_REDACTED]",
}


def replacement_for(entity_type: str) -> str:
    """Return the redaction label for an entity type."""
    return _REPLACEMENTS.get(entity_type, "[REDACTED]")


def protect_text(text: str, findings: list[Finding]) -> str:
    """
    Produce protected text by redacting each finding span (design 49).

    ``findings`` must be non-overlapping (normalized). Replacement runs in
    reverse order so span offsets remain valid during substitution.
    """
    if not findings:
        return text

    output = text
    for f in sorted(findings, key=lambda x: x.start, reverse=True):
        # Defensive bounds check against pathological offsets.
        if not (0 <= f.start < f.end <= len(output)):
            continue
        output = output[: f.start] + replacement_for(f.entity_type) + output[f.end :]
    return output


__all__ = ["protect_text", "replacement_for"]
