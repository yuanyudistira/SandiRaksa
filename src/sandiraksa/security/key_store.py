"""
Secure key storage using OS credential managers.

This module provides secure storage for encryption keys using:
- Windows: Credential Manager
- macOS: Keychain
- Linux: Secret Service / Keyring

Falls back to user password derivation if secure storage is unavailable.
"""

from __future__ import annotations

import base64
import logging
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING

import keyring
from keyring.errors import KeyringError, NoKeyringError, PasswordDeleteError

from sandiraksa.security.crypto import (
    CryptoError,
    derive_key,
    generate_key,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Keyring service name
SERVICE_NAME = "SandiRaksa"


class KeyStoreStatus(Enum):
    """Status of the key store backend."""

    AVAILABLE = auto()
    UNAVAILABLE = auto()
    LOCKED = auto()
    ERROR = auto()


class KeyStoreError(Exception):
    """Base exception for key store operations."""

    pass


class KeyNotFoundError(KeyStoreError):
    """Key not found in store."""

    pass


class KeyStoreUnavailableError(KeyStoreError):
    """Secure key store is not available."""

    pass


class KeyStore(ABC):
    """Abstract base class for key storage backends."""

    @abstractmethod
    def get_status(self) -> KeyStoreStatus:
        """Check the status of the key store."""
        ...

    @abstractmethod
    def store_key(self, key_id: str, key: bytes) -> None:
        """Store a key."""
        ...

    @abstractmethod
    def retrieve_key(self, key_id: str) -> bytes:
        """Retrieve a key."""
        ...

    @abstractmethod
    def delete_key(self, key_id: str) -> None:
        """Delete a key."""
        ...

    @abstractmethod
    def key_exists(self, key_id: str) -> bool:
        """Check if a key exists."""
        ...


class OSKeyStore(KeyStore):
    """
    Key store using OS credential manager via keyring library.

    Keys are base64-encoded before storage since keyring expects strings.
    """

    def __init__(self, service_name: str = SERVICE_NAME) -> None:
        self._service = service_name
        self._backend_checked = False
        self._backend_available = False

    def _check_backend(self) -> bool:
        """Check if a secure keyring backend is available."""
        if self._backend_checked:
            return self._backend_available

        self._backend_checked = True

        try:
            backend = keyring.get_keyring()
            backend_name = type(backend).__name__.lower()

            # Check for known insecure/null backends
            insecure_backends = [
                "null",
                "fail",
                "chainer",
                "plaintextkey",
            ]

            if any(insecure in backend_name for insecure in insecure_backends):
                logger.warning(
                    f"Keyring backend '{backend_name}' is not secure. "
                    "Secure key storage will be unavailable."
                )
                self._backend_available = False
            else:
                # Try a test operation
                try:
                    test_key = "__sandiraksa_test__"
                    keyring.set_password(self._service, test_key, "test")
                    keyring.delete_password(self._service, test_key)
                    self._backend_available = True
                    logger.info(f"Using keyring backend: {backend_name}")
                except Exception as e:
                    logger.warning(f"Keyring test failed: {e}")
                    self._backend_available = False

        except Exception as e:
            logger.warning(f"Keyring check failed: {e}")
            self._backend_available = False

        return self._backend_available

    def get_status(self) -> KeyStoreStatus:
        """Check the status of the OS key store."""
        if not self._check_backend():
            return KeyStoreStatus.UNAVAILABLE

        try:
            # Try to access keyring
            keyring.get_keyring()
            return KeyStoreStatus.AVAILABLE
        except NoKeyringError:
            return KeyStoreStatus.UNAVAILABLE
        except KeyringError:
            return KeyStoreStatus.ERROR
        except Exception:
            return KeyStoreStatus.ERROR

    def store_key(self, key_id: str, key: bytes) -> None:
        """Store a key in the OS credential manager."""
        if not self._check_backend():
            raise KeyStoreUnavailableError("No secure keyring backend available")

        try:
            # Base64 encode for storage as string
            encoded = base64.b64encode(key).decode("ascii")
            keyring.set_password(self._service, key_id, encoded)
        except KeyringError as e:
            raise KeyStoreError(f"Failed to store key: {e}") from e

    def retrieve_key(self, key_id: str) -> bytes:
        """Retrieve a key from the OS credential manager."""
        if not self._check_backend():
            raise KeyStoreUnavailableError("No secure keyring backend available")

        try:
            encoded = keyring.get_password(self._service, key_id)
            if encoded is None:
                raise KeyNotFoundError(f"Key not found: {key_id}")
            return base64.b64decode(encoded)
        except KeyringError as e:
            raise KeyStoreError(f"Failed to retrieve key: {e}") from e

    def delete_key(self, key_id: str) -> None:
        """Delete a key from the OS credential manager."""
        if not self._check_backend():
            raise KeyStoreUnavailableError("No secure keyring backend available")

        try:
            keyring.delete_password(self._service, key_id)
        except PasswordDeleteError:
            pass  # Key didn't exist, that's OK
        except KeyringError as e:
            raise KeyStoreError(f"Failed to delete key: {e}") from e

    def key_exists(self, key_id: str) -> bool:
        """Check if a key exists in the credential manager."""
        if not self._check_backend():
            return False

        try:
            return keyring.get_password(self._service, key_id) is not None
        except KeyringError:
            return False


class PasswordDerivedKeyStore(KeyStore):
    """
    Fallback key store that derives keys from a user password.

    This is used when OS secure storage is unavailable.
    Keys are not persisted - they must be derived each session.
    """

    def __init__(self) -> None:
        self._password: str | None = None
        self._salt: bytes | None = None
        self._derived_keys: dict[str, bytes] = {}

    def set_password(self, password: str, salt: bytes) -> None:
        """Set the master password for key derivation."""
        self._password = password
        self._salt = salt
        self._derived_keys.clear()

    def is_unlocked(self) -> bool:
        """Check if the store is unlocked with a password."""
        return self._password is not None and self._salt is not None

    def get_status(self) -> KeyStoreStatus:
        """Check if the store is unlocked."""
        if self.is_unlocked():
            return KeyStoreStatus.AVAILABLE
        return KeyStoreStatus.LOCKED

    def store_key(self, key_id: str, key: bytes) -> None:
        """Store a key (in-memory only for this session)."""
        self._derived_keys[key_id] = key

    def retrieve_key(self, key_id: str) -> bytes:
        """Retrieve a key."""
        if key_id in self._derived_keys:
            return self._derived_keys[key_id]

        if not self.is_unlocked():
            raise KeyStoreError("Key store is locked")

        # Derive a key specific to this key_id
        assert self._password is not None
        assert self._salt is not None

        combined_salt = self._salt + key_id.encode("utf-8")
        key, _ = derive_key(self._password, combined_salt)
        self._derived_keys[key_id] = key
        return key

    def delete_key(self, key_id: str) -> None:
        """Remove a key from memory."""
        self._derived_keys.pop(key_id, None)

    def key_exists(self, key_id: str) -> bool:
        """Check if a key exists or can be derived."""
        return key_id in self._derived_keys or self.is_unlocked()

    def lock(self) -> None:
        """Lock the store, clearing password and derived keys."""
        self._password = None
        # Note: salt is kept for re-unlock
        self._derived_keys.clear()


class KeyManager:
    """
    Manages encryption keys with fallback support.

    Prefers OS credential manager but falls back to password derivation
    if secure storage is unavailable.
    """

    # Key identifiers
    APP_MASTER_KEY = "master_key"

    def __init__(self) -> None:
        self._os_store = OSKeyStore()
        self._password_store = PasswordDerivedKeyStore()
        self._use_os_store = self._os_store.get_status() == KeyStoreStatus.AVAILABLE

    @property
    def is_secure_storage_available(self) -> bool:
        """Check if OS secure storage is available."""
        return self._use_os_store

    def get_or_create_master_key(self) -> bytes:
        """
        Get the application master key, creating it if needed.

        Returns:
            The master encryption key.

        Raises:
            KeyStoreError: If key cannot be retrieved or created.
        """
        if self._use_os_store:
            try:
                return self._os_store.retrieve_key(self.APP_MASTER_KEY)
            except KeyNotFoundError:
                # Create new master key
                key = generate_key()
                self._os_store.store_key(self.APP_MASTER_KEY, key)
                return key
        else:
            raise KeyStoreUnavailableError(
                "Secure key storage unavailable. "
                "Please unlock with password or configure a secure keyring."
            )

    def unlock_with_password(self, password: str, salt: bytes) -> None:
        """
        Unlock key store using a password (fallback mode).

        Args:
            password: User password.
            salt: Salt for key derivation.
        """
        self._password_store.set_password(password, salt)

    def lock(self) -> None:
        """Lock the password-derived key store."""
        self._password_store.lock()

    def get_project_key(self, project_id: str) -> bytes:
        """
        Get or derive a project-specific encryption key.

        Args:
            project_id: The project UUID.

        Returns:
            Project encryption key.
        """
        key_id = f"project_{project_id}"

        if self._use_os_store:
            try:
                return self._os_store.retrieve_key(key_id)
            except KeyNotFoundError:
                # Generate and store new project key
                key = generate_key()
                self._os_store.store_key(key_id, key)
                return key
        else:
            # Use password-derived key
            return self._password_store.retrieve_key(key_id)

    def delete_project_key(self, project_id: str) -> None:
        """Delete a project's encryption key."""
        key_id = f"project_{project_id}"

        if self._use_os_store:
            self._os_store.delete_key(key_id)
        self._password_store.delete_key(key_id)

    def get_status(self) -> dict[str, KeyStoreStatus]:
        """Get status of all key stores."""
        return {
            "os_store": self._os_store.get_status(),
            "password_store": self._password_store.get_status(),
        }


# Global instance
_key_manager: KeyManager | None = None


def get_key_manager() -> KeyManager:
    """Get the global key manager instance."""
    global _key_manager
    if _key_manager is None:
        _key_manager = KeyManager()
    return _key_manager


def reset_key_manager() -> None:
    """Reset the global key manager (for testing)."""
    global _key_manager
    _key_manager = None
