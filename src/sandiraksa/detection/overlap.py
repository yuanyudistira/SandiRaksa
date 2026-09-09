"""
Overlap Resolution for PII Detection.

When multiple recognizers detect overlapping entities, we need to
decide which detection to keep. This module provides strategies
for resolving such conflicts.

Resolution Strategies:
    1. Priority-based: Higher priority recognizer wins
    2. Score-based: Higher confidence wins
    3. Span-based: Longer span wins
    4. Merge: Combine overlapping detections

Example Overlap Cases:
    - NIK recognizer finds "3201234567890123" 
    - Generic number recognizer also finds same span
    → Keep NIK (more specific)

    - Person recognizer finds "John"
    - Person recognizer finds "John Smith" (overlapping)
    → Keep "John Smith" (longer span)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from sandiraksa.detection.unified_finding import UnifiedFinding


class OverlapStrategy(str, Enum):
    """Strategy for resolving overlapping detections."""

    PRIORITY_FIRST = "priority_first"  # Higher priority recognizer wins
    SCORE_FIRST = "score_first"        # Higher score wins
    LONGER_SPAN = "longer_span"        # Longer detection wins
    KEEP_ALL = "keep_all"              # Keep all (no resolution)
    MERGE = "merge"                    # Merge into single finding


@dataclass
class OverlapPair:
    """Represents two overlapping findings."""

    first: "UnifiedFinding"
    second: "UnifiedFinding"
    overlap_start: int
    overlap_end: int

    @property
    def overlap_length(self) -> int:
        """Length of the overlapping region."""
        return self.overlap_end - self.overlap_start

    @property
    def first_length(self) -> int:
        """Length of the first finding."""
        return self.first.end - self.first.start

    @property
    def second_length(self) -> int:
        """Length of the second finding."""
        return self.second.end - self.second.start

    @property
    def is_contained(self) -> bool:
        """Check if one finding is fully contained in the other."""
        first_contains_second = (
            self.first.start <= self.second.start and
            self.first.end >= self.second.end
        )
        second_contains_first = (
            self.second.start <= self.first.start and
            self.second.end >= self.first.end
        )
        return first_contains_second or second_contains_first

    @property
    def overlap_ratio(self) -> float:
        """Ratio of overlap to smaller span."""
        min_length = min(self.first_length, self.second_length)
        if min_length == 0:
            return 0.0
        return self.overlap_length / min_length


def findings_overlap(f1: "UnifiedFinding", f2: "UnifiedFinding") -> bool:
    """
    Check if two findings overlap.

    Args:
        f1: First finding
        f2: Second finding

    Returns:
        True if findings overlap
    """
    # Must be in same segment
    if f1.segment_id != f2.segment_id:
        return False

    # Check position overlap
    return f1.start < f2.end and f2.start < f1.end


def get_overlap_pair(
    f1: "UnifiedFinding", f2: "UnifiedFinding"
) -> OverlapPair | None:
    """
    Get overlap information for two findings.

    Args:
        f1: First finding
        f2: Second finding

    Returns:
        OverlapPair if findings overlap, None otherwise
    """
    if not findings_overlap(f1, f2):
        return None

    overlap_start = max(f1.start, f2.start)
    overlap_end = min(f1.end, f2.end)

    return OverlapPair(
        first=f1,
        second=f2,
        overlap_start=overlap_start,
        overlap_end=overlap_end,
    )


# Priority ordering for entity types (higher = more specific/important)
ENTITY_PRIORITY: dict[str, int] = {
    # Indonesian IDs (most specific)
    "ID_NIK": 90,
    "ID_KK": 90,
    "ID_NPWP": 85,
    "ID_PHONE": 80,
    # Financial
    "CREDIT_CARD": 85,
    "IBAN_CODE": 85,
    "BANK_ACCOUNT": 80,
    # Personal identifiers
    "US_SSN": 85,
    "US_PASSPORT": 80,
    "UK_NHS": 80,
    # Contact
    "EMAIL_ADDRESS": 75,
    "PHONE_NUMBER": 70,
    "IP_ADDRESS": 65,
    "URL": 60,
    # Personal info
    "PERSON": 50,
    "DATE_OF_BIRTH": 50,
    "LOCATION": 45,
    "ADDRESS": 45,
    # Generic
    "DATE": 30,
    "NRP": 40,
    # Custom terms always win
    "CUSTOM": 100,
}


def get_entity_priority(entity_type: str) -> int:
    """Get priority for an entity type."""
    return ENTITY_PRIORITY.get(entity_type, 50)


class OverlapResolver:
    """
    Resolves overlapping PII detections.

    The resolver takes a list of findings and removes or merges
    overlapping detections based on configurable strategies.

    Default strategy:
        1. If one is CUSTOM type, keep it (explicit user term)
        2. If one is more specific (higher entity priority), keep it
        3. If same entity type, keep higher confidence
        4. If still tied, keep longer span
    """

    def __init__(
        self,
        strategy: OverlapStrategy = OverlapStrategy.PRIORITY_FIRST,
        min_overlap_ratio: float = 0.5,
    ) -> None:
        """
        Initialize the resolver.

        Args:
            strategy: Strategy for resolving overlaps
            min_overlap_ratio: Minimum overlap ratio to consider as conflict
        """
        self.strategy = strategy
        self.min_overlap_ratio = min_overlap_ratio

    def resolve(
        self,
        findings: list["UnifiedFinding"],
    ) -> list["UnifiedFinding"]:
        """
        Resolve overlapping findings.

        Args:
            findings: List of findings (may contain overlaps)

        Returns:
            List of findings with overlaps resolved
        """
        if not findings or self.strategy == OverlapStrategy.KEEP_ALL:
            return findings

        # Group by segment
        by_segment: dict[str, list["UnifiedFinding"]] = {}
        for finding in findings:
            if finding.segment_id not in by_segment:
                by_segment[finding.segment_id] = []
            by_segment[finding.segment_id].append(finding)

        # Resolve within each segment
        result: list["UnifiedFinding"] = []
        for segment_id, segment_findings in by_segment.items():
            resolved = self._resolve_segment(segment_findings)
            result.extend(resolved)

        return result

    def _resolve_segment(
        self,
        findings: list["UnifiedFinding"],
    ) -> list["UnifiedFinding"]:
        """Resolve overlaps within a single segment."""
        if len(findings) <= 1:
            return findings

        # Sort by start position, then by score descending
        sorted_findings = sorted(
            findings,
            key=lambda f: (f.start, -f.raw_score),
        )

        result: list["UnifiedFinding"] = []

        for finding in sorted_findings:
            # Check against all kept findings
            should_keep = True
            to_remove: list[int] = []

            for i, kept in enumerate(result):
                pair = get_overlap_pair(finding, kept)
                if pair is None:
                    continue

                # Check if overlap is significant
                if pair.overlap_ratio < self.min_overlap_ratio:
                    continue

                # Decide which to keep
                winner = self._pick_winner(pair)
                if winner is kept:
                    should_keep = False
                    break
                else:
                    # New finding wins, mark old for removal
                    to_remove.append(i)

            # Remove losers
            for i in reversed(to_remove):
                result.pop(i)

            if should_keep:
                result.append(finding)

        return result

    def _pick_winner(self, pair: OverlapPair) -> "UnifiedFinding":
        """
        Pick the winner from an overlapping pair.

        Returns the finding that should be kept.
        """
        f1, f2 = pair.first, pair.second

        # Rule 1: CUSTOM type always wins
        if f1.entity_type == "CUSTOM" and f2.entity_type != "CUSTOM":
            return f1
        if f2.entity_type == "CUSTOM" and f1.entity_type != "CUSTOM":
            return f2

        # Rule 2: Custom terms flag always wins
        if f1.is_from_custom_terms and not f2.is_from_custom_terms:
            return f1
        if f2.is_from_custom_terms and not f1.is_from_custom_terms:
            return f2

        # Rule 3: Higher entity priority wins
        p1 = get_entity_priority(f1.entity_type)
        p2 = get_entity_priority(f2.entity_type)
        if p1 > p2:
            return f1
        if p2 > p1:
            return f2

        # Rule 4: For same entity type or equal priority, use strategy
        if self.strategy == OverlapStrategy.SCORE_FIRST:
            return f1 if f1.raw_score >= f2.raw_score else f2

        elif self.strategy == OverlapStrategy.LONGER_SPAN:
            len1 = f1.end - f1.start
            len2 = f2.end - f2.start
            return f1 if len1 >= len2 else f2

        else:  # PRIORITY_FIRST (default)
            # Use recognizer priority if available
            # Fallback to score
            return f1 if f1.raw_score >= f2.raw_score else f2

    def find_overlaps(
        self,
        findings: list["UnifiedFinding"],
    ) -> list[OverlapPair]:
        """
        Find all overlapping pairs in findings.

        Useful for debugging and analysis.

        Args:
            findings: List of findings

        Returns:
            List of OverlapPair objects
        """
        pairs: list[OverlapPair] = []

        for i, f1 in enumerate(findings):
            for f2 in findings[i + 1:]:
                pair = get_overlap_pair(f1, f2)
                if pair is not None:
                    pairs.append(pair)

        return pairs


def resolve_overlaps(
    findings: list["UnifiedFinding"],
    strategy: OverlapStrategy = OverlapStrategy.PRIORITY_FIRST,
    min_overlap_ratio: float = 0.5,
) -> list["UnifiedFinding"]:
    """
    Convenience function to resolve overlapping findings.

    Args:
        findings: List of findings
        strategy: Resolution strategy
        min_overlap_ratio: Minimum overlap ratio to consider

    Returns:
        List with overlaps resolved
    """
    resolver = OverlapResolver(
        strategy=strategy,
        min_overlap_ratio=min_overlap_ratio,
    )
    return resolver.resolve(findings)


def merge_adjacent_findings(
    findings: list["UnifiedFinding"],
    max_gap: int = 1,
    same_type_only: bool = True,
) -> list["UnifiedFinding"]:
    """
    Merge adjacent findings into single spans.

    Useful when the same entity is detected in pieces
    (e.g., first name and last name separately).

    Args:
        findings: List of findings
        max_gap: Maximum character gap to consider adjacent
        same_type_only: Only merge findings of same entity type

    Returns:
        List with adjacent findings merged
    """
    if not findings:
        return findings

    # Group by segment
    by_segment: dict[str, list["UnifiedFinding"]] = {}
    for f in findings:
        if f.segment_id not in by_segment:
            by_segment[f.segment_id] = []
        by_segment[f.segment_id].append(f)

    result: list["UnifiedFinding"] = []

    for segment_findings in by_segment.values():
        # Sort by position
        sorted_f = sorted(segment_findings, key=lambda f: f.start)

        merged: list["UnifiedFinding"] = []
        current = sorted_f[0]

        for next_f in sorted_f[1:]:
            # Check if adjacent
            gap = next_f.start - current.end
            same_type = current.entity_type == next_f.entity_type

            if gap <= max_gap and (not same_type_only or same_type):
                # Merge: extend current to include next
                # Keep higher confidence
                if next_f.raw_score > current.raw_score:
                    current = UnifiedFinding(
                        segment_id=current.segment_id,
                        entity_type=next_f.entity_type,
                        start=current.start,
                        end=next_f.end,
                        raw_score=next_f.raw_score,
                        confidence_band=next_f.confidence_band,
                        detector=next_f.detector,
                        detected_text=current.detected_text + next_f.detected_text,
                        evidence=current.evidence + next_f.evidence,
                        reason_codes=list(set(current.reason_codes + next_f.reason_codes)),
                    )
                else:
                    # Just extend the span
                    current = UnifiedFinding(
                        segment_id=current.segment_id,
                        entity_type=current.entity_type,
                        start=current.start,
                        end=next_f.end,
                        raw_score=current.raw_score,
                        confidence_band=current.confidence_band,
                        detector=current.detector,
                        detected_text=current.detected_text + next_f.detected_text,
                        evidence=current.evidence + next_f.evidence,
                        reason_codes=list(set(current.reason_codes + next_f.reason_codes)),
                    )
            else:
                # Not adjacent, save current and start new
                merged.append(current)
                current = next_f

        merged.append(current)
        result.extend(merged)

    return result


__all__ = [
    "ENTITY_PRIORITY",
    "OverlapPair",
    "OverlapResolver",
    "OverlapStrategy",
    "findings_overlap",
    "get_entity_priority",
    "get_overlap_pair",
    "merge_adjacent_findings",
    "resolve_overlaps",
]
