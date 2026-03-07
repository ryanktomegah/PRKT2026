"""
encryption.py — LIP Cryptographic Utilities
Architecture Spec: AES-256-GCM at rest, TLS 1.3 in transit, HMAC-SHA256 log signatures

All functions are stateless and accept explicit key / salt material.
No keys are hardcoded.  Callers are responsible for secure key management (KMS).
"""
import hashlib
import hmac
import os
import secrets

from cryptography.hazmat.primitives import hashes  # noqa: F401 — re-exported for callers
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# ── Constants ─────────────────────────────────────────────────────────────────

_AES_KEY_BYTES: int = 32        # AES-256 requires a 32-byte key
_GCM_NONCE_BYTES: int = 12      # 96-bit nonce recommended by NIST SP 800-38D
_PBKDF2_ITERATIONS: int = 100_000


# ---------------------------------------------------------------------------
# Salt generation
# ---------------------------------------------------------------------------

def generate_salt(length: int = 32) -> bytes:
    """Return *length* cryptographically secure random bytes suitable for use as a salt.

    Parameters
    ----------
    length:
        Number of bytes to generate.  Defaults to 32 (256 bits).

    Returns
    -------
    bytes
        Cryptographically secure random salt.
    """
    if length < 1:
        raise ValueError(f"Salt length must be >= 1, got {length}.")
    return secrets.token_bytes(length)


# ---------------------------------------------------------------------------
# Identifier hashing  (borrower IDs, entity IDs)
# ---------------------------------------------------------------------------

def hash_identifier(value: str, salt: bytes) -> str:
    """Return the SHA-256 hex digest of ``value + salt`` for pseudonymising identifiers.

    The concatenation strategy is:  ``SHA-256(value.encode('utf-8') + salt)``.

    Parameters
    ----------
    value:
        The plaintext identifier to hash (e.g., borrower ID, entity ID).
    salt:
        Per-deployment or per-record salt bytes.  Must not be empty.

    Returns
    -------
    str
        64-character lowercase hex digest.

    Raises
    ------
    ValueError
        If *salt* is empty.
    """
    if not salt:
        raise ValueError("Salt must not be empty.")
    digest = hashlib.sha256(value.encode("utf-8") + salt).hexdigest()
    return digest


# ---------------------------------------------------------------------------
# AES-256-GCM symmetric encryption
# ---------------------------------------------------------------------------

def encrypt_aes_gcm(plaintext: bytes, key: bytes) -> tuple[bytes, bytes]:
    """Encrypt *plaintext* with AES-256-GCM using a fresh random nonce.

    Parameters
    ----------
    plaintext:
        Raw bytes to encrypt.
    key:
        32-byte AES-256 key.  Must not be hardcoded; source from KMS.

    Returns
    -------
    tuple[bytes, bytes]
        ``(nonce, ciphertext)`` where *nonce* is 12 bytes and *ciphertext*
        includes the 16-byte GCM authentication tag appended by the
        ``cryptography`` library.

    Raises
    ------
    ValueError
        If *key* is not exactly 32 bytes.
    """
    if len(key) != _AES_KEY_BYTES:
        raise ValueError(
            f"AES-256 requires a {_AES_KEY_BYTES}-byte key; got {len(key)} bytes."
        )
    nonce = os.urandom(_GCM_NONCE_BYTES)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce, ciphertext


def decrypt_aes_gcm(nonce: bytes, ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt AES-256-GCM *ciphertext* and verify its authentication tag.

    Parameters
    ----------
    nonce:
        12-byte nonce used during encryption.
    ciphertext:
        Encrypted bytes including the appended 16-byte GCM tag.
    key:
        32-byte AES-256 key matching the one used during encryption.

    Returns
    -------
    bytes
        Decrypted plaintext.

    Raises
    ------
    ValueError
        If *key* is not exactly 32 bytes or *nonce* is not exactly 12 bytes.
    cryptography.exceptions.InvalidTag
        If the authentication tag verification fails (tampered ciphertext).
    """
    if len(key) != _AES_KEY_BYTES:
        raise ValueError(
            f"AES-256 requires a {_AES_KEY_BYTES}-byte key; got {len(key)} bytes."
        )
    if len(nonce) != _GCM_NONCE_BYTES:
        raise ValueError(
            f"AES-GCM nonce must be {_GCM_NONCE_BYTES} bytes; got {len(nonce)} bytes."
        )
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


# ---------------------------------------------------------------------------
# HMAC-SHA256 signing  (decision log integrity)
# ---------------------------------------------------------------------------

def sign_hmac_sha256(message: bytes, key: bytes) -> str:
    """Return the HMAC-SHA256 hex digest of *message* using *key*.

    Used to produce the ``entry_signature`` field in ``DecisionLogEntry``
    (Architecture Spec S4.8).

    Parameters
    ----------
    message:
        Canonical serialisation of the payload to sign.
    key:
        HMAC signing key bytes.  Must not be empty.

    Returns
    -------
    str
        64-character lowercase hexadecimal HMAC digest.

    Raises
    ------
    ValueError
        If *key* is empty.
    """
    if not key:
        raise ValueError("HMAC key must not be empty.")
    mac = hmac.new(key, message, hashlib.sha256)
    return mac.hexdigest()


def verify_hmac_sha256(message: bytes, signature: str, key: bytes) -> bool:
    """Verify an HMAC-SHA256 *signature* over *message* using a constant-time comparison.

    Parameters
    ----------
    message:
        The original signed payload bytes.
    signature:
        Hex digest string to verify (as returned by :func:`sign_hmac_sha256`).
    key:
        HMAC signing key bytes used during signing.

    Returns
    -------
    bool
        ``True`` if *signature* matches the recomputed HMAC; ``False`` otherwise.

    Raises
    ------
    ValueError
        If *key* is empty.
    """
    if not key:
        raise ValueError("HMAC key must not be empty.")
    expected = sign_hmac_sha256(message, key)
    # hmac.compare_digest prevents timing-based side-channel attacks.
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

def derive_key_from_passphrase(passphrase: str, salt: bytes) -> bytes:
    """Derive a 32-byte AES-256 key from *passphrase* using PBKDF2-HMAC-SHA256.

    Parameters
    ----------
    passphrase:
        Human-supplied passphrase string.
    salt:
        Per-derivation salt bytes (minimum 16 bytes recommended).
        Must not be empty; use :func:`generate_salt` to produce a fresh salt.

    Returns
    -------
    bytes
        32-byte derived key suitable for use with :func:`encrypt_aes_gcm`.

    Raises
    ------
    ValueError
        If *passphrase* is empty or *salt* is empty.
    """
    if not passphrase:
        raise ValueError("Passphrase must not be empty.")
    if not salt:
        raise ValueError("Salt must not be empty.")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_AES_KEY_BYTES,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))
