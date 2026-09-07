"""
Secure vault for project encryption keys and sensitive data.

The vault provides a unified interface for encrypting/decrypting
project-scoped sensitive data using project-specific keys.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sandiraksa.security.crypto import (
    CryptoEngine,
    CryptoError,
    DecryptionError,
    EncryptionError,
    compute_hmac,
    compute_hmac_hex,
)
from sandiraksa.security.key_store import (
    KeyManager,
    KeyStoreError,
    get_key_manager,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class VaultError(Exception):
    """Base exception for vault operations."""

    pass


class VaultLockedError(VaultError):
    """Vault is locked and cannot perform operations."""

    pass


@dataclass
class AADContext:
    """
    Additional Authenticated Data context for encryption.

    AAD binds encrypted data to a specific context, preventing
    ciphertext from being moved between different records.
    """

    project_id: str
    table: str
    row_id: str
    field: str

    def to_bytes(self) -> bytes:
        """Serialize AAD context for use in encryption."""
        return f"{self.project_id}|{self.table}|{self.row_id}|{self.field}".encode(
            "utf-8"
        )


class ProjectVault:
    """
    Manages encryption for a single project.

    Each project has its own encryption key derived from the master key
    or stored separately in the OS credential manager.
    """

    def __init__(
        self,
        project_id: str,
        key_manager: KeyManager | None = None,
    ) -> None:
        """
        Initialize vault for a project.

        Args:
            project_id: The project UUID.
            key_manager: Key manager instance. If None, uses global instance.
        """
        self._project_id = project_id
        self._key_manager = key_manager or get_key_manager()
        self._crypto_engine: CryptoEngine | None = None
        self._hmac_key: bytes | None = None

    def _get_engine(self) -> CryptoEngine:
        """Get or create the crypto engine."""
        if self._crypto_engine is None:
            try:
                key = self._key_manager.get_project_key(self._project_id)
                self._crypto_engine = CryptoEngine(key)
                # Derive HMAC key from encryption key
                self._hmac_key = compute_hmac(key, b"sandiraksa_hmac_key")
            except KeyStoreError as e:
                raise VaultLockedError(f"Cannot access project key: {e}") from e
        return self._crypto_engine

    def _get_hmac_key(self) -> bytes:
        """Get the HMAC key, initializing if needed."""
        if self._hmac_key is None:
            self._get_engine()  # This initializes _hmac_key
        assert self._hmac_key is not None
        return self._hmac_key

    def encrypt(
        self,
        plaintext: bytes | str,
        *,
        table: str = "",
        row_id: str = "",
        field: str = "",
    ) -> bytes:
        """
        Encrypt data with project key and AAD.

        Args:
            plaintext: Data to encrypt (bytes or string).
            table: Table name for AAD context.
            row_id: Row ID for AAD context.
            field: Field name for AAD context.

        Returns:
            Encrypted data as bytes.

        Raises:
            VaultError: If encryption fails.
        """
        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")

        aad = AADContext(
            project_id=self._project_id,
            table=table,
            row_id=row_id,
            field=field,
        )

        try:
            engine = self._get_engine()
            return engine.encrypt_to_bytes(plaintext, aad.to_bytes())
        except (CryptoError, VaultLockedError) as e:
            raise VaultError(f"Encryption failed: {e}") from e

    def decrypt(
        self,
        ciphertext: bytes,
        *,
        table: str = "",
        row_id: str = "",
        field: str = "",
    ) -> bytes:
        """
        Decrypt data with project key and AAD.

        Args:
            ciphertext: Encrypted data.
            table: Table name for AAD context (must match encryption).
            row_id: Row ID for AAD context (must match encryption).
            field: Field name for AAD context (must match encryption).

        Returns:
            Decrypted plaintext.

        Raises:
            VaultError: If decryption fails or AAD doesn't match.
        """
        aad = AADContext(
            project_id=self._project_id,
            table=table,
            row_id=row_id,
            field=field,
        )

        try:
            engine = self._get_engine()
            return engine.decrypt_from_bytes(ciphertext, aad.to_bytes())
        except DecryptionError as e:
            raise VaultError(
                "Decryption failed: data may be corrupted, tampered, "
                "or the context (project/table/row/field) doesn't match"
            ) from e
        except (CryptoError, VaultLockedError) as e:
            raise VaultError(f"Decryption failed: {e}") from e

    def decrypt_string(
        self,
        ciphertext: bytes,
        *,
        table: str = "",
        row_id: str = "",
        field: str = "",
    ) -> str:
        """Decrypt and decode as UTF-8 string."""
        return self.decrypt(
            ciphertext, table=table, row_id=row_id, field=field
        ).decode("utf-8")

    def compute_normalized_hmac(self, entity_type: str, normalized_value: str) -> str:
        """
        Compute HMAC for normalized value lookup.

        This is used to find existing token mappings without storing
        the plaintext normalized value.

        Args:
            entity_type: Entity type (e.g., "PERSON", "EMAIL").
            normalized_value: Normalized entity value.

        Returns:
            Hex-encoded HMAC.
        """
        hmac_key = self._get_hmac_key()
        data = f"{entity_type}|{normalized_value}".encode("utf-8")
        return compute_hmac_hex(hmac_key, data)

    def close(self) -> None:
        """Clear cached keys from memory."""
        self._crypto_engine = None
        self._hmac_key = None


class VaultManager:
    """
    Manages project vaults with caching.

    Provides a central point for accessing project-specific vaults
    and managing their lifecycle.
    """

    def __init__(self, key_manager: KeyManager | None = None) -> None:
        self._key_manager = key_manager or get_key_manager()
        self._vaults: dict[str, ProjectVault] = {}

    def get_vault(self, project_id: str) -> ProjectVault:
        """
        Get or create a vault for a project.

        Args:
            project_id: The project UUID.

        Returns:
            ProjectVault for the project.
        """
        if project_id not in self._vaults:
            self._vaults[project_id] = ProjectVault(
                project_id, self._key_manager
            )
        return self._vaults[project_id]

    def close_vault(self, project_id: str) -> None:
        """Close and remove a project vault."""
        if project_id in self._vaults:
            self._vaults[project_id].close()
            del self._vaults[project_id]

    def close_all(self) -> None:
        """Close all open vaults."""
        for vault in self._vaults.values():
            vault.close()
        self._vaults.clear()

    def delete_project_keys(self, project_id: str) -> None:
        """
        Delete all keys for a project.

        This should be called when a project is deleted.
        """
        self.close_vault(project_id)
        self._key_manager.delete_project_key(project_id)


# Global vault manager instance
_vault_manager: VaultManager | None = None


def get_vault_manager() -> VaultManager:
    """Get the global vault manager instance."""
    global _vault_manager
    if _vault_manager is None:
        _vault_manager = VaultManager()
    return _vault_manager


def get_project_vault(project_id: str) -> ProjectVault:
    """Convenience function to get a project vault."""
    return get_vault_manager().get_vault(project_id)


def reset_vault_manager() -> None:
    """Reset the global vault manager (for testing)."""
    global _vault_manager
    if _vault_manager is not None:
        _vault_manager.close_all()
        _vault_manager = None
