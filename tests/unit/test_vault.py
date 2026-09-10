"""Tests for vault module."""

import pytest

from sandiraksa.security.crypto import generate_key
from sandiraksa.security.key_store import KeyManager, KeyStoreStatus
from sandiraksa.security.vault import (
    AADContext,
    ProjectVault,
    VaultError,
    VaultManager,
)


class MockKeyStore:
    """Mock key store for testing without OS credential manager."""

    def __init__(self):
        self._keys: dict[str, bytes] = {}

    def get_status(self) -> KeyStoreStatus:
        return KeyStoreStatus.AVAILABLE

    def store_key(self, key_id: str, key: bytes) -> None:
        self._keys[key_id] = key

    def retrieve_key(self, key_id: str) -> bytes:
        if key_id not in self._keys:
            raise KeyError(key_id)
        return self._keys[key_id]

    def delete_key(self, key_id: str) -> None:
        self._keys.pop(key_id, None)

    def key_exists(self, key_id: str) -> bool:
        return key_id in self._keys


class MockKeyManager(KeyManager):
    """Mock key manager for testing."""

    def __init__(self):
        self._keys: dict[str, bytes] = {}

    @property
    def is_secure_storage_available(self) -> bool:
        return True

    def get_project_key(self, project_id: str) -> bytes:
        key_id = f"project_{project_id}"
        if key_id not in self._keys:
            self._keys[key_id] = generate_key()
        return self._keys[key_id]

    def delete_project_key(self, project_id: str) -> None:
        key_id = f"project_{project_id}"
        self._keys.pop(key_id, None)


@pytest.fixture
def mock_key_manager():
    """Create a mock key manager."""
    return MockKeyManager()


@pytest.fixture
def vault(mock_key_manager):
    """Create a test vault."""
    return ProjectVault("test-project-id", mock_key_manager)


class TestAADContext:
    """Tests for AADContext."""

    def test_to_bytes(self):
        """Should serialize context to bytes."""
        aad = AADContext(
            project_id="proj-123",
            table="token_mappings",
            row_id="row-456",
            field="original_value",
        )

        result = aad.to_bytes()
        assert b"proj-123" in result
        assert b"token_mappings" in result
        assert b"row-456" in result
        assert b"original_value" in result

    def test_different_contexts_different_bytes(self):
        """Different contexts should produce different bytes."""
        aad1 = AADContext("proj1", "table", "row", "field")
        aad2 = AADContext("proj2", "table", "row", "field")
        assert aad1.to_bytes() != aad2.to_bytes()


class TestProjectVault:
    """Tests for ProjectVault."""

    def test_encrypt_decrypt(self, vault: ProjectVault):
        """Should encrypt and decrypt data."""
        plaintext = b"Sensitive information"

        encrypted = vault.encrypt(plaintext)
        decrypted = vault.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_string(self, vault: ProjectVault):
        """Should handle string input."""
        plaintext = "Text to encrypt"

        encrypted = vault.encrypt(plaintext)
        decrypted = vault.decrypt_string(encrypted)

        assert decrypted == plaintext

    def test_encrypt_with_context(self, vault: ProjectVault):
        """Should bind encryption to context."""
        plaintext = b"Contextual data"

        encrypted = vault.encrypt(
            plaintext,
            table="token_mappings",
            row_id="mapping-123",
            field="original_value",
        )

        # Should decrypt with same context
        decrypted = vault.decrypt(
            encrypted,
            table="token_mappings",
            row_id="mapping-123",
            field="original_value",
        )
        assert decrypted == plaintext

    def test_context_mismatch_fails(self, vault: ProjectVault):
        """Should fail if decryption context doesn't match."""
        plaintext = b"Protected data"

        encrypted = vault.encrypt(
            plaintext,
            table="table1",
            row_id="row1",
            field="field1",
        )

        # Wrong table
        with pytest.raises(VaultError):
            vault.decrypt(
                encrypted,
                table="wrong_table",
                row_id="row1",
                field="field1",
            )

    def test_compute_normalized_hmac(self, vault: ProjectVault):
        """Should compute consistent HMACs for lookups."""
        hmac1 = vault.compute_normalized_hmac("PERSON", "john smith")
        hmac2 = vault.compute_normalized_hmac("PERSON", "john smith")
        hmac3 = vault.compute_normalized_hmac("EMAIL", "john smith")

        # Same inputs = same HMAC
        assert hmac1 == hmac2

        # Different entity type = different HMAC
        assert hmac1 != hmac3

    def test_close_clears_keys(self, vault: ProjectVault):
        """Close should clear cached keys."""
        # Force key loading
        vault.encrypt(b"test")

        vault.close()

        assert vault._crypto_engine is None
        assert vault._hmac_key is None


class TestVaultManager:
    """Tests for VaultManager."""

    @pytest.fixture
    def manager(self, mock_key_manager):
        """Create a vault manager with mock key manager."""
        return VaultManager(mock_key_manager)

    def test_get_vault(self, manager: VaultManager):
        """Should create and cache vaults."""
        vault1 = manager.get_vault("project-1")
        vault2 = manager.get_vault("project-1")
        vault3 = manager.get_vault("project-2")

        assert vault1 is vault2  # Same project = same vault
        assert vault1 is not vault3  # Different project = different vault

    def test_close_vault(self, manager: VaultManager):
        """Should close and remove vault."""
        vault = manager.get_vault("project-1")
        manager.close_vault("project-1")

        # Getting again should create new vault
        new_vault = manager.get_vault("project-1")
        assert new_vault is not vault

    def test_close_all(self, manager: VaultManager):
        """Should close all vaults."""
        manager.get_vault("project-1")
        manager.get_vault("project-2")
        manager.get_vault("project-3")

        manager.close_all()

        assert len(manager._vaults) == 0

    def test_delete_project_keys(self, manager: VaultManager, mock_key_manager):
        """Should delete project keys."""
        project_id = "delete-test"
        vault = manager.get_vault(project_id)

        # The vault fetches the key lazily, so trigger key creation with an
        # encrypt operation before asserting the key exists.
        vault.encrypt("x", table="t", row_id="1", field="f")
        assert f"project_{project_id}" in mock_key_manager._keys

        manager.delete_project_keys(project_id)

        # Key deleted
        assert f"project_{project_id}" not in mock_key_manager._keys
