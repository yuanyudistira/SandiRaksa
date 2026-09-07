"""
Referential consistency management for token mappings.

Ensures that the same entity value maps to the same token
throughout a project, across multiple files and operations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sandiraksa.domain.finding import Finding
from sandiraksa.domain.token import Treatment, TreatmentType
from sandiraksa.protection.tokenizer import Tokenizer, TokenizerFactory, ValueNormalizer

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class ConsistencyStats:
    """Statistics about token consistency in an operation."""

    total_findings: int = 0
    tokens_reused: int = 0
    tokens_created: int = 0
    values_ignored: int = 0
    unique_values: int = 0

    @property
    def reuse_rate(self) -> float:
        """Percentage of tokens that were reused."""
        total = self.tokens_reused + self.tokens_created
        if total == 0:
            return 0.0
        return (self.tokens_reused / total) * 100


@dataclass
class ValueTracker:
    """
    Tracks unique values seen during an operation.

    Used to apply "same value in project" decisions consistently.
    """

    # Mapping from (entity_type, normalized_value) to first finding ID
    _value_to_finding: dict[tuple[str, str], str] = field(default_factory=dict)

    # Mapping from finding ID to (entity_type, normalized_value)
    _finding_to_value: dict[str, tuple[str, str]] = field(default_factory=dict)

    def track(self, finding: Finding, original_value: str) -> bool:
        """
        Track a finding's value.

        Args:
            finding: The finding to track.
            original_value: The detected value.

        Returns:
            True if this is a new unique value, False if seen before.
        """
        normalized = ValueNormalizer.normalize(
            finding.effective_entity_type, original_value
        )
        key = (finding.effective_entity_type, normalized)

        self._finding_to_value[finding.id] = key

        if key not in self._value_to_finding:
            self._value_to_finding[key] = finding.id
            return True

        return False

    def get_first_finding_id(self, entity_type: str, normalized_value: str) -> str | None:
        """Get the ID of the first finding with this value."""
        key = (entity_type, normalized_value)
        return self._value_to_finding.get(key)

    def get_all_with_same_value(
        self, finding: Finding
    ) -> list[str]:
        """Get all finding IDs with the same value as the given finding."""
        if finding.id not in self._finding_to_value:
            return []

        key = self._finding_to_value[finding.id]
        result = []

        for fid, fkey in self._finding_to_value.items():
            if fkey == key:
                result.append(fid)

        return result

    @property
    def unique_value_count(self) -> int:
        """Number of unique values tracked."""
        return len(self._value_to_finding)


class ConsistencyManager:
    """
    Manages referential consistency for token mappings.

    Ensures:
    - Same value → same token within a project
    - Consistent token reuse across files added later
    - Proper handling of "apply to all" decisions
    """

    def __init__(self, project_id: str) -> None:
        self._project_id = project_id
        self._tokenizer = TokenizerFactory.get_tokenizer(project_id)
        self._value_tracker = ValueTracker()
        self._stats = ConsistencyStats()

        # Cache of decisions to apply to same values
        self._value_decisions: dict[tuple[str, str], Treatment] = {}

    @property
    def stats(self) -> ConsistencyStats:
        """Get current consistency statistics."""
        return self._stats

    def process_finding(
        self,
        finding: Finding,
        original_value: str,
        treatment_type: TreatmentType,
    ) -> Treatment:
        """
        Process a finding and generate its treatment.

        Handles token reuse and consistency tracking.

        Args:
            finding: The finding to process.
            original_value: The detected sensitive value.
            treatment_type: How to treat this finding.

        Returns:
            Treatment object with token/replacement.
        """
        self._stats.total_findings += 1

        # Check for ignored findings
        if treatment_type == TreatmentType.KEEP:
            self._stats.values_ignored += 1
            return Treatment(
                finding_id=finding.id,
                treatment_type=TreatmentType.KEEP,
                replacement=original_value,
                location=finding.location,
            )

        # Track unique values
        entity_type = finding.effective_entity_type
        normalized = ValueNormalizer.normalize(entity_type, original_value)
        is_new = self._value_tracker.track(finding, original_value)

        if is_new:
            self._stats.unique_values += 1

        # Check if we have a cached decision for this value
        value_key = (entity_type, normalized)
        if value_key in self._value_decisions:
            cached = self._value_decisions[value_key]
            self._stats.tokens_reused += 1
            return Treatment(
                finding_id=finding.id,
                treatment_type=cached.treatment_type,
                replacement=cached.replacement,
                location=finding.location,
                token=cached.token,
            )

        # Generate treatment based on type
        treatment = self._generate_treatment(
            finding, original_value, entity_type, treatment_type
        )

        # Cache for future same-value findings
        self._value_decisions[value_key] = treatment

        return treatment

    def _generate_treatment(
        self,
        finding: Finding,
        original_value: str,
        entity_type: str,
        treatment_type: TreatmentType,
    ) -> Treatment:
        """Generate the actual treatment (token/redaction/etc)."""
        if treatment_type == TreatmentType.TOKEN:
            # Get or create token
            token = self._tokenizer.get_or_create_token(entity_type, original_value)

            # Check if this was a reuse
            # (We can detect this by checking if token existed before this call)
            # For simplicity, we count new tokens in the factory
            self._stats.tokens_created += 1

            return Treatment(
                finding_id=finding.id,
                treatment_type=TreatmentType.TOKEN,
                replacement=token,
                location=finding.location,
                token=token,
            )

        elif treatment_type == TreatmentType.REDACT:
            return Treatment(
                finding_id=finding.id,
                treatment_type=TreatmentType.REDACT,
                replacement="[REDACTED]",
                location=finding.location,
            )

        elif treatment_type == TreatmentType.CATEGORY:
            return Treatment(
                finding_id=finding.id,
                treatment_type=TreatmentType.CATEGORY,
                replacement=f"[{entity_type}]",
                location=finding.location,
            )

        elif treatment_type == TreatmentType.MASK:
            # Partial masking - show first and last chars
            masked = self._mask_value(original_value)
            return Treatment(
                finding_id=finding.id,
                treatment_type=TreatmentType.MASK,
                replacement=masked,
                location=finding.location,
            )

        elif treatment_type == TreatmentType.GENERALIZE:
            # Generalization depends on entity type
            generalized = self._generalize_value(entity_type, original_value)
            return Treatment(
                finding_id=finding.id,
                treatment_type=TreatmentType.GENERALIZE,
                replacement=generalized,
                location=finding.location,
            )

        elif treatment_type == TreatmentType.PSEUDONYM:
            # Deterministic pseudonym without storing original
            pseudonym = self._generate_pseudonym(entity_type, original_value)
            return Treatment(
                finding_id=finding.id,
                treatment_type=TreatmentType.PSEUDONYM,
                replacement=pseudonym,
                location=finding.location,
            )

        else:
            # Default: category replacement
            return Treatment(
                finding_id=finding.id,
                treatment_type=TreatmentType.CATEGORY,
                replacement=f"[{entity_type}]",
                location=finding.location,
            )

    def _mask_value(self, value: str) -> str:
        """Create a masked version of a value."""
        if len(value) <= 4:
            return "*" * len(value)

        # Show first 2 and last 2 characters
        return value[:2] + "*" * (len(value) - 4) + value[-2:]

    def _generalize_value(self, entity_type: str, value: str) -> str:
        """Generalize a value based on entity type."""
        if entity_type == "DATE_OF_BIRTH":
            # Just show year if it looks like a date
            if len(value) >= 4:
                return value[:4]
            return "[DATE]"

        if entity_type == "ADDRESS":
            # Remove specific details, keep city/region if identifiable
            return "[ADDRESS]"

        if entity_type in {"SALARY", "TRANSACTION_VALUE", "PRICING"}:
            # Round to order of magnitude
            try:
                num = float("".join(c for c in value if c.isdigit() or c == "."))
                if num >= 1_000_000_000:
                    return "[BILLIONS]"
                elif num >= 1_000_000:
                    return "[MILLIONS]"
                elif num >= 1_000:
                    return "[THOUSANDS]"
                else:
                    return "[AMOUNT]"
            except (ValueError, TypeError):
                return "[AMOUNT]"

        return f"[{entity_type}]"

    def _generate_pseudonym(self, entity_type: str, value: str) -> str:
        """
        Generate a deterministic pseudonym.

        Uses the same HMAC approach as tokens but formatted differently.
        Does NOT store the original value - non-reversible.
        """
        normalized = ValueNormalizer.normalize(entity_type, value)
        hmac_hex = self._tokenizer._vault.compute_normalized_hmac(
            entity_type, normalized
        )

        # Format based on entity type
        if entity_type == "PERSON":
            return f"Person_{hmac_hex[:8].upper()}"
        elif entity_type == "EMAIL":
            return f"user_{hmac_hex[:8].lower()}@redacted.local"
        elif entity_type == "ORGANIZATION":
            return f"Org_{hmac_hex[:8].upper()}"
        else:
            return f"{entity_type}_{hmac_hex[:8].upper()}"

    def apply_bulk_decision(
        self,
        entity_type: str,
        normalized_value: str,
        treatment: Treatment,
    ) -> None:
        """
        Apply a decision to all instances of a value.

        Used when user selects "apply to all same values".
        """
        value_key = (entity_type, normalized_value)
        self._value_decisions[value_key] = treatment

    def reset(self) -> None:
        """Reset the manager for a new operation."""
        self._value_tracker = ValueTracker()
        self._stats = ConsistencyStats()
        self._value_decisions.clear()
