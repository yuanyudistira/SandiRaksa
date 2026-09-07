"""Tests for cryptographic utilities."""

import pytest

from sandiraksa.security.crypto import (
    CRYPTO_VERSION,
    KEY_SIZE,
    NONCE_SIZE,
    CryptoEngine,
    CryptoError,
    DecryptionError,
    EncryptedData,
    EncryptionError,
    compute_hmac,
    compute_hmac_hex,
    derive_key,
    generate_key,
    hash_bytes,
    secure_compare,
)


class TestGenerateKey:
    """Tests for key generation."""

    def test_key_length(self):
        """Generated key should be 256 bits."""
        key = generate_key()
        assert len(key) == KEY_SIZE

    def test_keys_are_unique(self):
        """Each generated key should be unique."""
        keys = [generate_key() for _ in range(100)]
        assert len(set(keys)) == 100


class TestDeriveKey:
    """Tests for password-based key derivation."""

    def test_derive_key_with_password(self):
        """Should derive a key from password."""
        key, salt = derive_key("test_password")
        assert len(key) == KEY_SIZE
        assert len(salt) > 0

    def test_same_password_same_salt_same_key(self):
        """Same password and salt should produce same key."""
        key1, salt = derive_key("my_password")
        key2, _ = derive_key("my_password", salt)
        assert key1 == key2

    def test_different_passwords_different_keys(self):
        """Different passwords should produce different keys."""
        key1, salt = derive_key("password1")
        key2, _ = derive_key("password2", salt)
        assert key1 != key2

    def test_different_salts_different_keys(self):
        """Different salts should produce different keys."""
        key1, salt1 = derive_key("same_password")
        key2, salt2 = derive_key("same_password")
        # New salt is generated each time
        assert salt1 != salt2
        assert key1 != key2


class TestEncryptedData:
    """Tests for EncryptedData serialization."""

    def test_to_bytes_and_back(self):
        """Should serialize and deserialize correctly."""
        original = EncryptedData(
            version=CRYPTO_VERSION,
            nonce=b"0" * NONCE_SIZE,
            ciphertext=b"test_ciphertext_with_tag",
        )

        serialized = original.to_bytes()
        restored = EncryptedData.from_bytes(serialized)

        assert restored.version == original.version
        assert restored.nonce == original.nonce
        assert restored.ciphertext == original.ciphertext

    def test_invalid_data_too_short(self):
        """Should reject data that's too short."""
        with pytest.raises(DecryptionError, match="too short"):
            EncryptedData.from_bytes(b"short")

    def test_unsupported_version(self):
        """Should reject unsupported crypto versions."""
        # Create data with version 99
        data = bytes([99]) + b"0" * NONCE_SIZE + b"0" * 20
        with pytest.raises(DecryptionError, match="Unsupported"):
            EncryptedData.from_bytes(data)


class TestCryptoEngine:
    """Tests for AES-256-GCM encryption engine."""

    @pytest.fixture
    def engine(self):
        """Create a crypto engine with test key."""
        return CryptoEngine(generate_key())

    def test_invalid_key_size(self):
        """Should reject invalid key sizes."""
        with pytest.raises(CryptoError):
            CryptoEngine(b"short_key")

    def test_encrypt_decrypt(self, engine: CryptoEngine):
        """Should encrypt and decrypt correctly."""
        plaintext = b"Hello, World!"
        encrypted = engine.encrypt(plaintext)
        decrypted = engine.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_decrypt_with_aad(self, engine: CryptoEngine):
        """Should work with additional authenticated data."""
        plaintext = b"Sensitive data"
        aad = b"context_info"

        encrypted = engine.encrypt(plaintext, aad)
        decrypted = engine.decrypt(encrypted, aad)
        assert decrypted == plaintext

    def test_aad_mismatch_fails(self, engine: CryptoEngine):
        """Decryption should fail if AAD doesn't match."""
        plaintext = b"Sensitive data"
        encrypted = engine.encrypt(plaintext, b"original_aad")

        with pytest.raises(DecryptionError):
            engine.decrypt(encrypted, b"wrong_aad")

    def test_missing_aad_fails(self, engine: CryptoEngine):
        """Decryption should fail if AAD is missing when expected."""
        plaintext = b"Sensitive data"
        encrypted = engine.encrypt(plaintext, b"some_aad")

        with pytest.raises(DecryptionError):
            engine.decrypt(encrypted, None)

    def test_tampered_ciphertext_fails(self, engine: CryptoEngine):
        """Should detect tampered ciphertext."""
        plaintext = b"Important data"
        encrypted = engine.encrypt(plaintext)

        # Tamper with ciphertext
        tampered = EncryptedData(
            version=encrypted.version,
            nonce=encrypted.nonce,
            ciphertext=encrypted.ciphertext[:-1] + bytes([encrypted.ciphertext[-1] ^ 1]),
        )

        with pytest.raises(DecryptionError):
            engine.decrypt(tampered)

    def test_each_encryption_unique(self, engine: CryptoEngine):
        """Each encryption should produce different ciphertext (unique nonce)."""
        plaintext = b"Same plaintext"
        encrypted1 = engine.encrypt(plaintext)
        encrypted2 = engine.encrypt(plaintext)

        assert encrypted1.nonce != encrypted2.nonce
        assert encrypted1.ciphertext != encrypted2.ciphertext

    def test_encrypt_to_bytes(self, engine: CryptoEngine):
        """Should provide convenient bytes serialization."""
        plaintext = b"Test data"
        encrypted_bytes = engine.encrypt_to_bytes(plaintext)
        decrypted = engine.decrypt_from_bytes(encrypted_bytes)
        assert decrypted == plaintext

    def test_empty_plaintext(self, engine: CryptoEngine):
        """Should handle empty plaintext."""
        encrypted = engine.encrypt(b"")
        decrypted = engine.decrypt(encrypted)
        assert decrypted == b""

    def test_large_plaintext(self, engine: CryptoEngine):
        """Should handle large plaintext."""
        plaintext = b"x" * (1024 * 1024)  # 1 MB
        encrypted = engine.encrypt(plaintext)
        decrypted = engine.decrypt(encrypted)
        assert decrypted == plaintext


class TestHMAC:
    """Tests for HMAC functions."""

    def test_compute_hmac(self):
        """Should compute HMAC correctly."""
        key = b"secret_key"
        data = b"data_to_authenticate"

        hmac1 = compute_hmac(key, data)
        hmac2 = compute_hmac(key, data)

        assert hmac1 == hmac2
        assert len(hmac1) == 32  # SHA-256 output

    def test_different_key_different_hmac(self):
        """Different keys should produce different HMACs."""
        data = b"same_data"
        hmac1 = compute_hmac(b"key1", data)
        hmac2 = compute_hmac(b"key2", data)
        assert hmac1 != hmac2

    def test_compute_hmac_hex(self):
        """Should return hex-encoded HMAC."""
        hmac_hex = compute_hmac_hex(b"key", b"data")
        assert isinstance(hmac_hex, str)
        assert len(hmac_hex) == 64  # 32 bytes as hex


class TestSecureCompare:
    """Tests for constant-time comparison."""

    def test_equal_values(self):
        """Should return True for equal values."""
        assert secure_compare(b"test", b"test") is True

    def test_unequal_values(self):
        """Should return False for unequal values."""
        assert secure_compare(b"test1", b"test2") is False

    def test_different_lengths(self):
        """Should return False for different lengths."""
        assert secure_compare(b"short", b"longer") is False


class TestHashBytes:
    """Tests for hash functions."""

    def test_hash_bytes_sha256(self):
        """Should compute SHA-256 hash."""
        data = b"test data"
        hash_hex = hash_bytes(data)
        assert isinstance(hash_hex, str)
        assert len(hash_hex) == 64

    def test_same_input_same_hash(self):
        """Same input should produce same hash."""
        data = b"reproducible"
        assert hash_bytes(data) == hash_bytes(data)

    def test_different_input_different_hash(self):
        """Different input should produce different hash."""
        assert hash_bytes(b"data1") != hash_bytes(b"data2")
