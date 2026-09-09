"""
Enhanced Custom Terms Manager.

Provides project-specific custom terms with:
- Always Protect: Terms that should always be flagged (high confidence)
- Never Protect: Terms that should be excluded (reduce false positives)
- Encrypted local storage for per-project persistence
- Import/Export functionality
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from sandiraksa.detection.unified_finding import (
    ConfidenceBand,
    ConfidenceEvidence,
    EvidenceType,
    UnifiedFinding,
)

if TYPE_CHECKING:
    from sandiraksa.documents.logical_segment import LogicalSegment

logger = logging.getLogger(__name__)


class TermType(str, Enum):
    """Type of custom term."""

    ALWAYS_PROTECT = "always_protect"  # Always flag as PII
    NEVER_PROTECT = "never_protect"    # Exclude from detection


class MatchMode(str, Enum):
    """How to match the term."""

    EXACT = "exact"      # Exact match (case-insensitive by default)
    WORD = "word"        # Word boundary match
    REGEX = "regex"      # Regular expression
    CONTAINS = "contains"  # Substring match


@dataclass
class CustomTermEntry:
    """
    A custom term entry.

    Attributes:
        id: Unique identifier
        term: The term or pattern
        term_type: ALWAYS_PROTECT or NEVER_PROTECT
        match_mode: How to match
        entity_type: Entity type for ALWAYS_PROTECT terms
        case_sensitive: Whether to match case-sensitively
        description: Optional description
        created_at: Creation timestamp
    """

    id: str
    term: str
    term_type: TermType
    match_mode: MatchMode = MatchMode.WORD
    entity_type: str = "CUSTOM"
    case_sensitive: bool = False
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Compiled regex (cached)
    _compiled: re.Pattern | None = field(default=None, repr=False)

    def compile(self) -> re.Pattern:
        """Compile term to regex pattern."""
        if self._compiled is not None:
            return self._compiled

        flags = 0 if self.case_sensitive else re.IGNORECASE

        if self.match_mode == MatchMode.EXACT:
            pattern = f"^{re.escape(self.term)}$"
        elif self.match_mode == MatchMode.WORD:
            pattern = rf"\b{re.escape(self.term)}\b"
        elif self.match_mode == MatchMode.CONTAINS:
            pattern = re.escape(self.term)
        elif self.match_mode == MatchMode.REGEX:
            pattern = self.term
        else:
            pattern = rf"\b{re.escape(self.term)}\b"

        try:
            self._compiled = re.compile(pattern, flags)
        except re.error as e:
            logger.error(f"Invalid regex pattern '{self.term}': {e}")
            self._compiled = re.compile(re.escape(self.term), flags)

        return self._compiled

    def matches(self, text: str) -> list[tuple[int, int, str]]:
        """
        Find all matches in text.

        Returns:
            List of (start, end, matched_text) tuples
        """
        pattern = self.compile()
        return [
            (m.start(), m.end(), m.group())
            for m in pattern.finditer(text)
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "term": self.term,
            "term_type": self.term_type.value,
            "match_mode": self.match_mode.value,
            "entity_type": self.entity_type,
            "case_sensitive": self.case_sensitive,
            "description": self.description,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CustomTermEntry":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            term=data["term"],
            term_type=TermType(data["term_type"]),
            match_mode=MatchMode(data.get("match_mode", "word")),
            entity_type=data.get("entity_type", "CUSTOM"),
            case_sensitive=data.get("case_sensitive", False),
            description=data.get("description", ""),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )


class EncryptedStorage:
    """
    Encrypted local storage for custom terms.

    Uses Fernet symmetric encryption with project-derived key.
    """

    def __init__(self, storage_dir: Path | None = None):
        """
        Initialize storage.

        Args:
            storage_dir: Directory for storage files
        """
        self.storage_dir = storage_dir or self._get_default_storage_dir()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_default_storage_dir(self) -> Path:
        """Get default storage directory."""
        # Use app data directory
        if os.name == "nt":  # Windows
            base = Path(os.environ.get("APPDATA", "~"))
        else:  # Linux/Mac
            base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share"))

        return base.expanduser() / "sandiraksa" / "custom_terms"

    def _derive_key(self, project_id: str) -> bytes:
        """
        Derive encryption key from project ID.

        Uses PBKDF2 with a fixed salt (per-installation).
        """
        # Salt based on machine ID or fixed value
        salt = self._get_salt()

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )

        key = kdf.derive(project_id.encode())
        return base64.urlsafe_b64encode(key)

    def _get_salt(self) -> bytes:
        """Get or create installation salt."""
        salt_file = self.storage_dir / ".salt"
        if salt_file.exists():
            return salt_file.read_bytes()
        else:
            salt = os.urandom(16)
            salt_file.write_bytes(salt)
            return salt

    def _get_file_path(self, project_id: str) -> Path:
        """Get storage file path for a project."""
        # Hash project ID for filename
        hashed = hashlib.sha256(project_id.encode()).hexdigest()[:16]
        return self.storage_dir / f"terms_{hashed}.enc"

    def save(self, project_id: str, data: dict[str, Any]) -> None:
        """
        Save encrypted data for a project.

        Args:
            project_id: Project identifier
            data: Data to encrypt and save
        """
        key = self._derive_key(project_id)
        fernet = Fernet(key)

        json_data = json.dumps(data, indent=2)
        encrypted = fernet.encrypt(json_data.encode())

        file_path = self._get_file_path(project_id)
        file_path.write_bytes(encrypted)
        logger.debug(f"Saved custom terms for project to {file_path}")

    def load(self, project_id: str) -> dict[str, Any] | None:
        """
        Load encrypted data for a project.

        Args:
            project_id: Project identifier

        Returns:
            Decrypted data or None if not found
        """
        file_path = self._get_file_path(project_id)
        if not file_path.exists():
            return None

        try:
            key = self._derive_key(project_id)
            fernet = Fernet(key)

            encrypted = file_path.read_bytes()
            decrypted = fernet.decrypt(encrypted)

            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"Failed to load custom terms: {e}")
            return None

    def delete(self, project_id: str) -> bool:
        """Delete storage for a project."""
        file_path = self._get_file_path(project_id)
        if file_path.exists():
            file_path.unlink()
            return True
        return False


class EnhancedCustomTermsManager:
    """
    Enhanced manager for custom terms per project.

    Features:
    - Always Protect: Terms that always flag as PII
    - Never Protect: Terms to exclude from detection
    - Encrypted persistence
    - Import/Export
    """

    def __init__(
        self,
        project_id: str,
        storage: EncryptedStorage | None = None,
    ):
        """
        Initialize manager for a project.

        Args:
            project_id: Project identifier
            storage: Storage backend (creates default if None)
        """
        self.project_id = project_id
        self.storage = storage or EncryptedStorage()

        # Term collections
        self._always_protect: dict[str, CustomTermEntry] = {}
        self._never_protect: dict[str, CustomTermEntry] = {}

        # Load existing terms
        self._load()

    def _load(self) -> None:
        """Load terms from storage."""
        data = self.storage.load(self.project_id)
        if data:
            for entry_data in data.get("always_protect", []):
                entry = CustomTermEntry.from_dict(entry_data)
                self._always_protect[entry.id] = entry

            for entry_data in data.get("never_protect", []):
                entry = CustomTermEntry.from_dict(entry_data)
                self._never_protect[entry.id] = entry

            logger.debug(
                f"Loaded {len(self._always_protect)} always-protect, "
                f"{len(self._never_protect)} never-protect terms"
            )

    def save(self) -> None:
        """Save terms to storage."""
        data = {
            "project_id": self.project_id,
            "always_protect": [e.to_dict() for e in self._always_protect.values()],
            "never_protect": [e.to_dict() for e in self._never_protect.values()],
            "updated_at": datetime.utcnow().isoformat(),
        }
        self.storage.save(self.project_id, data)

    # =========================================================================
    # Always Protect
    # =========================================================================

    def add_always_protect(
        self,
        term: str,
        entity_type: str = "CUSTOM",
        match_mode: MatchMode = MatchMode.WORD,
        case_sensitive: bool = False,
        description: str = "",
    ) -> CustomTermEntry:
        """
        Add a term to Always Protect list.

        Args:
            term: Term or pattern to match
            entity_type: Entity type for findings
            match_mode: How to match
            case_sensitive: Case sensitivity
            description: Why this term is sensitive

        Returns:
            Created CustomTermEntry
        """
        entry = CustomTermEntry(
            id=str(uuid4()),
            term=term,
            term_type=TermType.ALWAYS_PROTECT,
            match_mode=match_mode,
            entity_type=entity_type,
            case_sensitive=case_sensitive,
            description=description,
        )

        self._always_protect[entry.id] = entry
        self.save()

        logger.info(f"Added always-protect term: '{term}'")
        return entry

    def remove_always_protect(self, term_id: str) -> bool:
        """Remove a term from Always Protect list."""
        if term_id in self._always_protect:
            del self._always_protect[term_id]
            self.save()
            return True
        return False

    def get_always_protect_terms(self) -> list[CustomTermEntry]:
        """Get all Always Protect terms."""
        return list(self._always_protect.values())

    # =========================================================================
    # Never Protect
    # =========================================================================

    def add_never_protect(
        self,
        term: str,
        match_mode: MatchMode = MatchMode.WORD,
        case_sensitive: bool = False,
        description: str = "",
    ) -> CustomTermEntry:
        """
        Add a term to Never Protect list.

        Args:
            term: Term or pattern to exclude
            match_mode: How to match
            case_sensitive: Case sensitivity
            description: Why this term should be excluded

        Returns:
            Created CustomTermEntry
        """
        entry = CustomTermEntry(
            id=str(uuid4()),
            term=term,
            term_type=TermType.NEVER_PROTECT,
            match_mode=match_mode,
            case_sensitive=case_sensitive,
            description=description,
        )

        self._never_protect[entry.id] = entry
        self.save()

        logger.info(f"Added never-protect term: '{term}'")
        return entry

    def remove_never_protect(self, term_id: str) -> bool:
        """Remove a term from Never Protect list."""
        if term_id in self._never_protect:
            del self._never_protect[term_id]
            self.save()
            return True
        return False

    def get_never_protect_terms(self) -> list[CustomTermEntry]:
        """Get all Never Protect terms."""
        return list(self._never_protect.values())

    # =========================================================================
    # Detection
    # =========================================================================

    def detect_always_protect(
        self,
        segment: "LogicalSegment",
    ) -> list[UnifiedFinding]:
        """
        Detect Always Protect terms in a segment.

        Args:
            segment: Segment to analyze

        Returns:
            List of findings for matched terms
        """
        findings: list[UnifiedFinding] = []

        for entry in self._always_protect.values():
            matches = entry.matches(segment.text)
            for start, end, matched_text in matches:
                finding = UnifiedFinding(
                    segment_id=segment.id,
                    entity_type=entry.entity_type,
                    start=start,
                    end=end,
                    raw_score=0.95,  # High confidence for custom terms
                    confidence_band=ConfidenceBand.HIGH,
                    detector="custom_terms",
                    detected_text=matched_text,
                    is_from_custom_terms=True,
                    is_validated=True,
                )

                finding.add_evidence(
                    ConfidenceEvidence(
                        evidence_type=EvidenceType.PATTERN_MATCH,
                        source="custom_terms",
                        weight=0.95,
                        reason_code="always_protect",
                        description=f"Custom term: '{entry.term}'",
                    )
                )

                if entry.description:
                    finding.add_evidence(
                        ConfidenceEvidence(
                            evidence_type=EvidenceType.CONTEXT_POSITIVE,
                            source="custom_terms",
                            weight=0.1,
                            reason_code="custom_description",
                            description=entry.description,
                        )
                    )

                findings.append(finding)

        return findings

    def should_exclude(self, finding: UnifiedFinding, text: str) -> bool:
        """
        Check if a finding should be excluded based on Never Protect list.

        Args:
            finding: The finding to check
            text: The detected text

        Returns:
            True if finding should be excluded
        """
        for entry in self._never_protect.values():
            matches = entry.matches(text)
            if matches:
                # Check if any match covers the finding
                for start, end, matched in matches:
                    if matched.lower() == text.lower():
                        logger.debug(
                            f"Excluding '{text}' due to never-protect: '{entry.term}'"
                        )
                        return True

        return False

    def filter_findings(
        self,
        findings: list[UnifiedFinding],
        segment: "LogicalSegment",
    ) -> list[UnifiedFinding]:
        """
        Filter findings using Never Protect list.

        Args:
            findings: Findings to filter
            segment: Source segment

        Returns:
            Filtered findings (excluding never-protect matches)
        """
        filtered = []
        for finding in findings:
            text = segment.text[finding.start:finding.end]
            if not self.should_exclude(finding, text):
                filtered.append(finding)

        excluded = len(findings) - len(filtered)
        if excluded > 0:
            logger.debug(f"Filtered {excluded} findings via never-protect list")

        return filtered

    # =========================================================================
    # Import/Export
    # =========================================================================

    def export_terms(self) -> dict[str, Any]:
        """
        Export terms for backup or sharing.

        Returns:
            Dictionary with all terms (not encrypted)
        """
        return {
            "version": "1.0",
            "project_id": self.project_id,
            "exported_at": datetime.utcnow().isoformat(),
            "always_protect": [e.to_dict() for e in self._always_protect.values()],
            "never_protect": [e.to_dict() for e in self._never_protect.values()],
        }

    def import_terms(
        self,
        data: dict[str, Any],
        merge: bool = True,
    ) -> tuple[int, int]:
        """
        Import terms from exported data.

        Args:
            data: Exported terms data
            merge: If True, merge with existing; if False, replace

        Returns:
            Tuple of (always_protect_count, never_protect_count) imported
        """
        if not merge:
            self._always_protect.clear()
            self._never_protect.clear()

        ap_count = 0
        np_count = 0

        for entry_data in data.get("always_protect", []):
            entry = CustomTermEntry.from_dict(entry_data)
            # Generate new ID if merging to avoid conflicts
            if merge:
                entry.id = str(uuid4())
            self._always_protect[entry.id] = entry
            ap_count += 1

        for entry_data in data.get("never_protect", []):
            entry = CustomTermEntry.from_dict(entry_data)
            if merge:
                entry.id = str(uuid4())
            self._never_protect[entry.id] = entry
            np_count += 1

        self.save()
        logger.info(f"Imported {ap_count} always-protect, {np_count} never-protect terms")

        return (ap_count, np_count)

    # =========================================================================
    # Stats
    # =========================================================================

    @property
    def always_protect_count(self) -> int:
        """Get count of Always Protect terms."""
        return len(self._always_protect)

    @property
    def never_protect_count(self) -> int:
        """Get count of Never Protect terms."""
        return len(self._never_protect)

    @property
    def total_count(self) -> int:
        """Get total term count."""
        return self.always_protect_count + self.never_protect_count


# =============================================================================
# Global Manager Registry
# =============================================================================

_managers: dict[str, EnhancedCustomTermsManager] = {}
_storage: EncryptedStorage | None = None


def get_enhanced_custom_terms_manager(
    project_id: str,
) -> EnhancedCustomTermsManager:
    """
    Get or create an enhanced custom terms manager for a project.

    Args:
        project_id: Project identifier

    Returns:
        EnhancedCustomTermsManager for the project
    """
    global _managers, _storage

    if project_id not in _managers:
        if _storage is None:
            _storage = EncryptedStorage()
        _managers[project_id] = EnhancedCustomTermsManager(
            project_id=project_id,
            storage=_storage,
        )

    return _managers[project_id]


def close_custom_terms_manager(project_id: str) -> None:
    """Close and cleanup manager for a project."""
    if project_id in _managers:
        del _managers[project_id]


__all__ = [
    "TermType",
    "MatchMode",
    "CustomTermEntry",
    "EncryptedStorage",
    "EnhancedCustomTermsManager",
    "get_enhanced_custom_terms_manager",
    "close_custom_terms_manager",
]
