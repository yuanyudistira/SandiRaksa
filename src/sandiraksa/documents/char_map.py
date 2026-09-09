"""
CharMapEntry model for SandiRaksa.

Provides offset mapping between logical (reconstructed) text and source
document components. This is critical for DOCX/PPTX where text may be
split across multiple runs.

Example Problem:
    Visible text: "Nama: Satria Putra Yudistira"

    Internal DOCX storage:
        Run 1: "Nama: "
        Run 2: "Sat"
        Run 3: "ria Put"
        Run 4: "ra Yudistira"

    Detection finds PERSON at logical positions 6-28.
    CharMap enables mapping back to Runs 2, 3, 4 for replacement.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class CharMapEntry(BaseModel):
    """
    Maps a range of characters in logical text to their source location.

    This is the core mechanism for handling DOCX/PPTX split-run issues.
    When text is reconstructed from multiple runs, CharMapEntry tracks
    which characters came from which source component.

    Attributes:
        logical_start: Starting position in reconstructed text (0-indexed, inclusive)
        logical_end: Ending position in reconstructed text (0-indexed, exclusive)
        source_component_id: Identifier of the source component (run ID, shape ID, etc.)
        source_start: Starting position within the source component (0-indexed)
        source_end: Ending position within the source component (0-indexed)
        source_type: Type of source (e.g., "run", "shape", "cell")

    Example:
        For DOCX text "Satria Putra" split as:
            Run "r1": "Sat" (chars 0-2)
            Run "r2": "ria Put" (chars 3-9)
            Run "r3": "ra" (chars 10-11)

        CharMap would be:
            CharMapEntry(logical_start=0, logical_end=3, source_component_id="r1", ...)
            CharMapEntry(logical_start=3, logical_end=10, source_component_id="r2", ...)
            CharMapEntry(logical_start=10, logical_end=12, source_component_id="r3", ...)
    """

    logical_start: int = Field(
        ge=0,
        description="Starting position in reconstructed text (0-indexed, inclusive)",
    )
    logical_end: int = Field(
        ge=0,
        description="Ending position in reconstructed text (0-indexed, exclusive)",
    )
    source_component_id: str = Field(
        description="Identifier of the source component (run ID, shape ID, cell ref)",
    )
    source_start: int = Field(
        ge=0,
        description="Starting position within the source component (0-indexed)",
    )
    source_end: int = Field(
        ge=0,
        description="Ending position within the source component (0-indexed)",
    )
    source_type: str = Field(
        default="run",
        description="Type of source component (run, shape, cell, paragraph)",
    )

    # Optional metadata for complex cases
    parent_id: str | None = Field(
        default=None,
        description="Parent container ID (e.g., paragraph ID for runs)",
    )
    formatting_preserved: bool = Field(
        default=True,
        description="Whether formatting should be preserved during replacement",
    )

    model_config = {"frozen": False, "extra": "forbid"}

    @model_validator(mode="after")
    def validate_ranges(self) -> "CharMapEntry":
        """Validate that start positions are less than end positions."""
        if self.logical_start > self.logical_end:
            msg = (
                f"logical_start ({self.logical_start}) must be <= "
                f"logical_end ({self.logical_end})"
            )
            raise ValueError(msg)
        if self.source_start > self.source_end:
            msg = (
                f"source_start ({self.source_start}) must be <= "
                f"source_end ({self.source_end})"
            )
            raise ValueError(msg)
        return self

    @property
    def logical_length(self) -> int:
        """Get the length of the mapped text in logical space."""
        return self.logical_end - self.logical_start

    @property
    def source_length(self) -> int:
        """Get the length of the text in source component."""
        return self.source_end - self.source_start

    def contains_logical_position(self, position: int) -> bool:
        """
        Check if a logical position falls within this mapping.

        Args:
            position: A position in the logical text

        Returns:
            True if the position is within [logical_start, logical_end)
        """
        return self.logical_start <= position < self.logical_end

    def overlaps_logical_range(self, start: int, end: int) -> bool:
        """
        Check if a logical range overlaps with this mapping.

        Args:
            start: Start of the range to check
            end: End of the range to check

        Returns:
            True if there is any overlap
        """
        return self.logical_start < end and start < self.logical_end

    def logical_to_source(self, logical_position: int) -> int | None:
        """
        Convert a logical position to a source position.

        Args:
            logical_position: Position in the logical text

        Returns:
            Corresponding position in source component, or None if out of range
        """
        if not self.contains_logical_position(logical_position):
            return None

        offset = logical_position - self.logical_start
        return self.source_start + offset

    def get_source_range_for_logical(
        self, logical_start: int, logical_end: int
    ) -> tuple[int, int] | None:
        """
        Get the source range that corresponds to a logical range.

        Args:
            logical_start: Start of logical range
            logical_end: End of logical range

        Returns:
            Tuple of (source_start, source_end) for the overlapping portion,
            or None if no overlap
        """
        if not self.overlaps_logical_range(logical_start, logical_end):
            return None

        # Clamp to this entry's range
        clamped_start = max(logical_start, self.logical_start)
        clamped_end = min(logical_end, self.logical_end)

        # Convert to source positions
        source_start = self.source_start + (clamped_start - self.logical_start)
        source_end = self.source_start + (clamped_end - self.logical_start)

        return (source_start, source_end)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "logical_start": self.logical_start,
            "logical_end": self.logical_end,
            "source_component_id": self.source_component_id,
            "source_start": self.source_start,
            "source_end": self.source_end,
            "source_type": self.source_type,
        }
        if self.parent_id:
            result["parent_id"] = self.parent_id
        if not self.formatting_preserved:
            result["formatting_preserved"] = False
        return result


class CharMap(BaseModel):
    """
    Collection of CharMapEntry objects for a logical segment.

    Provides utilities for looking up source components for any
    position or range in the logical text.

    Example usage:
        char_map = CharMap(entries=[...])

        # Find all source components affected by a finding
        affected = char_map.get_entries_for_range(6, 28)

        # Convert logical position to source
        for entry in affected:
            source_range = entry.get_source_range_for_logical(6, 28)
    """

    entries: list[CharMapEntry] = Field(
        default_factory=list,
        description="List of character mapping entries, should be non-overlapping and sorted",
    )

    model_config = {"frozen": False, "extra": "forbid"}

    @model_validator(mode="after")
    def validate_entries(self) -> "CharMap":
        """Validate that entries are sorted and non-overlapping."""
        if len(self.entries) <= 1:
            return self

        # Sort by logical_start
        sorted_entries = sorted(self.entries, key=lambda e: e.logical_start)

        # Check for overlaps
        for i in range(len(sorted_entries) - 1):
            current = sorted_entries[i]
            next_entry = sorted_entries[i + 1]
            if current.logical_end > next_entry.logical_start:
                msg = (
                    f"Overlapping entries: entry ending at {current.logical_end} "
                    f"overlaps with entry starting at {next_entry.logical_start}"
                )
                raise ValueError(msg)

        # Store sorted
        self.entries = sorted_entries
        return self

    @property
    def total_logical_length(self) -> int:
        """Get the total length of logical text covered by this map."""
        if not self.entries:
            return 0
        return self.entries[-1].logical_end

    @property
    def source_component_ids(self) -> list[str]:
        """Get list of unique source component IDs in order."""
        seen: set[str] = set()
        result: list[str] = []
        for entry in self.entries:
            if entry.source_component_id not in seen:
                seen.add(entry.source_component_id)
                result.append(entry.source_component_id)
        return result

    def get_entry_at(self, logical_position: int) -> CharMapEntry | None:
        """
        Get the entry that contains a specific logical position.

        Args:
            logical_position: Position in logical text

        Returns:
            The CharMapEntry containing this position, or None
        """
        for entry in self.entries:
            if entry.contains_logical_position(logical_position):
                return entry
        return None

    def get_entries_for_range(self, start: int, end: int) -> list[CharMapEntry]:
        """
        Get all entries that overlap with a logical range.

        Args:
            start: Start of the range
            end: End of the range

        Returns:
            List of CharMapEntry objects that overlap with the range
        """
        return [entry for entry in self.entries if entry.overlaps_logical_range(start, end)]

    def get_source_mappings_for_range(
        self, logical_start: int, logical_end: int
    ) -> list[tuple[str, int, int]]:
        """
        Get all source component mappings for a logical range.

        This is the key method for applying replacements. Given a finding
        at logical positions, it returns all the source components and
        their ranges that need to be modified.

        Args:
            logical_start: Start of the logical range
            logical_end: End of the logical range

        Returns:
            List of tuples: (source_component_id, source_start, source_end)

        Example:
            For a finding spanning logical chars 6-28 across 3 runs:
            [
                ("run_2", 0, 3),    # "Sat" in run 2
                ("run_3", 0, 7),    # "ria Put" in run 3
                ("run_4", 0, 12),   # "ra Yudistira" in run 4
            ]
        """
        result: list[tuple[str, int, int]] = []

        for entry in self.get_entries_for_range(logical_start, logical_end):
            source_range = entry.get_source_range_for_logical(logical_start, logical_end)
            if source_range:
                result.append((entry.source_component_id, source_range[0], source_range[1]))

        return result

    def append(self, entry: CharMapEntry) -> None:
        """
        Append a new entry to the map.

        Args:
            entry: The CharMapEntry to add

        Raises:
            ValueError: If the entry overlaps with existing entries
        """
        if self.entries:
            last = self.entries[-1]
            if entry.logical_start < last.logical_end:
                msg = (
                    f"New entry starts at {entry.logical_start} but "
                    f"last entry ends at {last.logical_end}"
                )
                raise ValueError(msg)
        self.entries.append(entry)

    @classmethod
    def from_runs(
        cls,
        runs: list[tuple[str, str]],
        source_type: str = "run",
        parent_id: str | None = None,
    ) -> tuple["CharMap", str]:
        """
        Build a CharMap from a list of runs and return the concatenated text.

        This is a convenience method for the common case of building
        a CharMap while concatenating text from multiple OOXML runs.

        Args:
            runs: List of (run_id, run_text) tuples
            source_type: Type of source components
            parent_id: Optional parent container ID

        Returns:
            Tuple of (CharMap, concatenated_text)

        Example:
            runs = [("r1", "Sat"), ("r2", "ria Put"), ("r3", "ra")]
            char_map, text = CharMap.from_runs(runs)
            # text == "Satria Putra"
            # char_map has 3 entries mapping back to r1, r2, r3
        """
        entries: list[CharMapEntry] = []
        logical_text = ""
        logical_pos = 0

        for run_id, run_text in runs:
            if not run_text:
                continue

            text_len = len(run_text)
            entries.append(
                CharMapEntry(
                    logical_start=logical_pos,
                    logical_end=logical_pos + text_len,
                    source_component_id=run_id,
                    source_start=0,
                    source_end=text_len,
                    source_type=source_type,
                    parent_id=parent_id,
                )
            )
            logical_text += run_text
            logical_pos += text_len

        return cls(entries=entries), logical_text
