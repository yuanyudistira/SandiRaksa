"""
Cryptographic utilities for SandiRaksa.

This module provides authenticated encryption (AES-256-GCM) for protecting
sensitive data like token mappings and custom rules.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from sandiraksa.config import get_app_config

if TYPE_CHECKING:
    pass

# Constants
CRYPTO_VERSION = 1
NONCE_SIZE = 12  # 96 bits recommended for GCM
KEY_SIZE = 32  # 256 bits
TAG_SIZE = 16  # 128 bits authentication tag
SALT_SIZE = 16  # 128 bits for KDF salt


class CryptoError(Exception):
    """Base exception for cryptographic operations."""

    pass


class EncryptionError(CryptoError):
    """Error during encryption."""

    pass


class DecryptionError(CryptoError):
    """Error during decryption (including authentication failure)."""

    pass


class KeyDerivationError(CryptoError):
    """Error during key derivation."""

    pass


@dataclass(frozen=True)
class EncryptedData:
    """Container for encrypted data with metadata."""

    version: int
    nonce: bytes
    ciphertext: bytes  # Includes authentication tag

    def to_bytes(self) -> bytes:
        """Serialize to bytes for storage."""
        # Format: version (1 byte) + nonce (12 bytes) + ciphertext (variable)
        return struct.pack("B", self.version) + self.nonce + self.ciphertext

    @classmethod
    def from_bytes(cls, data: bytes) -> EncryptedData:
        """Deserialize from bytes."""
        if len(data) < 1 + NONCE_SIZE + TAG_SIZE:
            raise DecryptionError("Invalid encrypted data: too short")

        version = struct.unpack("B", data[:1])[0]
        if version != CRYPTO_VERSION:
            raise DecryptionError(f"Unsupported crypto version: {version}")

        nonce = data[1 : 1 + NONCE_SIZE]
        ciphertext = data[1 + NONCE_SIZE :]

        return cls(version=version, nonce=nonce, ciphertext=ciphertext)


class CryptoEngine:
    """
    Provides AES-256-GCM authenticated encryption.

    All encryption operations use a fresh random nonce.
    The authentication tag is included in the ciphertext.
    """

    def __init__(self, key: bytes) -> None:
        """
        Initialize with an encryption key.

        Args:
            key: 256-bit (32 bytes) encryption key.

        Raises:
            CryptoError: If key is not 32 bytes.
        """
        if len(key) != KEY_SIZE:
            raise CryptoError(f"Key must be {KEY_SIZE} bytes, got {len(key)}")
        self._aesgcm = AESGCM(key)
        self._key = key

    def encrypt(
        self,
        plaintext: bytes,
        associated_data: bytes | None = None,
    ) -> EncryptedData:
        """
        Encrypt data with AES-256-GCM.

        Args:
            plaintext: Data to encrypt.
            associated_data: Additional authenticated data (not encrypted but
                verified during decryption).

        Returns:
            EncryptedData containing nonce and ciphertext.

        Raises:
            EncryptionError: If encryption fails.
        """
        try:
            nonce = os.urandom(NONCE_SIZE)
            ciphertext = self._aesgcm.encrypt(nonce, plaintext, associated_data)
            return EncryptedData(
                version=CRYPTO_VERSION,
                nonce=nonce,
                ciphertext=ciphertext,
            )
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}") from e

    def decrypt(
        self,
        encrypted: EncryptedData,
        associated_data: bytes | None = None,
    ) -> bytes:
        """
        Decrypt data with AES-256-GCM.

        Args:
            encrypted: EncryptedData to decrypt.
            associated_data: Must match the AAD used during encryption.

        Returns:
            Decrypted plaintext.

        Raises:
            DecryptionError: If decryption or authentication fails.
        """
        try:
            return self._aesgcm.decrypt(
                encrypted.nonce, encrypted.ciphertext, associated_data
            )
        except Exception as e:
            raise DecryptionError(
                "Decryption failed: data may be corrupted or tampered"
            ) from e

    def encrypt_to_bytes(
        self,
        plaintext: bytes,
        associated_data: bytes | None = None,
    ) -> bytes:
        """Encrypt and return serialized bytes."""
        encrypted = self.encrypt(plaintext, associated_data)
        return encrypted.to_bytes()

    def decrypt_from_bytes(
        self,
        data: bytes,
        associated_data: bytes | None = None,
    ) -> bytes:
        """Decrypt from serialized bytes."""
        encrypted = EncryptedData.from_bytes(data)
        return self.decrypt(encrypted, associated_data)


def generate_key() -> bytes:
    """Generate a random 256-bit encryption key."""
    return secrets.token_bytes(KEY_SIZE)


def derive_key(
    password: str,
    salt: bytes | None = None,
    iterations: int | None = None,
) -> tuple[bytes, bytes]:
    """
    Derive a key from a password using PBKDF2.

    Args:
        password: User password.
        salt: Salt for derivation. If None, generates a new random salt.
        iterations: Number of iterations. If None, uses config default.

    Returns:
        Tuple of (derived_key, salt).

    Raises:
        KeyDerivationError: If derivation fails.
    """
    if salt is None:
        salt = os.urandom(SALT_SIZE)

    if iterations is None:
        iterations = get_app_config().security.pbkdf2_iterations

    try:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=salt,
            iterations=iterations,
        )
        key = kdf.derive(password.encode("utf-8"))
        return key, salt
    except Exception as e:
        raise KeyDerivationError(f"Key derivation failed: {e}") from e


def compute_hmac(key: bytes, data: bytes) -> bytes:
    """
    Compute HMAC-SHA256.

    Args:
        key: HMAC key.
        data: Data to authenticate.

    Returns:
        HMAC digest (32 bytes).
    """
    return hmac.new(key, data, hashlib.sha256).digest()


def compute_hmac_hex(key: bytes, data: bytes) -> str:
    """Compute HMAC-SHA256 and return as hex string."""
    return compute_hmac(key, data).hex()


def secure_compare(a: bytes, b: bytes) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    return hmac.compare_digest(a, b)


def hash_file(filepath: str, algorithm: str = "sha256") -> str:
    """
    Compute hash of a file.

    Args:
        filepath: Path to the file.
        algorithm: Hash algorithm (default: sha256).

    Returns:
        Hex-encoded hash digest.
    """
    h = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_bytes(data: bytes, algorithm: str = "sha256") -> str:
    """
    Compute hash of bytes.

    Args:
        data: Data to hash.
        algorithm: Hash algorithm (default: sha256).

    Returns:
        Hex-encoded hash digest.
    """
    return hashlib.new(algorithm, data).hexdigest()
