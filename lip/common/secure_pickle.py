"""
secure_pickle.py — Integrity-verified pickle loader.

Background
----------
Batch 10 of the 2026-04-08 code review flagged two Critical RCE findings
(B10-01, B10-02): ``pickle.load()`` calls on model artefacts with no
integrity check. An attacker with write access to the model directory
gets arbitrary code execution at load time — pickle's ``__reduce__``
protocol is Turing-complete.

This module is the **only legal pickle loader in the LIP codebase**. All
other ``pickle.load``/``pickle.loads`` calls outside this file are
forbidden by ``lip/tests/test_pickle_ban.py`` (B13-01 regression test).
Adding a new direct ``pickle.load`` call will fail the build.

Design
------
Every secure-pickle artefact is a pair of files::

    model.pkl        # the pickle payload
    model.pkl.sig    # sibling HMAC-SHA256 hex digest over the payload

Verification is constant-time (``hmac.compare_digest`` via
``lip.common.encryption.verify_hmac_sha256``) and happens **before** the
bytes are handed to ``pickle.load``. If the sidecar is missing, empty,
tampered, or the payload bytes differ from what was signed, the loader
raises ``SecurePickleError`` and never invokes the pickle machinery.

The HMAC key is read from the ``LIP_MODEL_HMAC_KEY`` environment variable
at call time (not import time), so rotating the key does not require a
process restart. The key must be at least 32 bytes when decoded. For
local development, a test key can be injected via
``secure_pickle.load(..., hmac_key=b"...")`` — never hardcode a
production key in source or tests.

This is a *gate*, not a replacement for the broader problem that pickle
is a bad serialisation format for untrusted input. The long-term fix is
to migrate C1 LightGBM / C2 ensemble to LightGBM's native text format
(``Booster(model_file=...)``) — tracked as Batch 10 follow-up work. Until
then, this wrapper enforces the "trusted-only" claim the existing
``# noqa: S301`` suppressions made without enforcement.

Usage
-----
Writing::

    from lip.common.secure_pickle import dump
    dump(obj, "model.pkl")   # writes model.pkl + model.pkl.sig

Reading::

    from lip.common.secure_pickle import load
    obj = load("model.pkl")  # raises SecurePickleError on bad sidecar
"""
from __future__ import annotations

import logging
import os
import pickle  # noqa: S403 — this module IS the secure-pickle wrapper
from pathlib import Path

from lip.common.encryption import sign_hmac_sha256, verify_hmac_sha256

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
_HMAC_KEY_ENV = "LIP_MODEL_HMAC_KEY"
_SIG_SUFFIX = ".sig"
_MIN_KEY_LEN = 32  # 256 bits


class SecurePickleError(Exception):
    """Raised when a secure-pickle artefact fails integrity verification.

    All failure modes — missing sidecar, bad hex, HMAC mismatch, missing
    key, unreadable payload — raise this exception. Callers must never
    fall back to direct ``pickle.load``; that defeats the entire purpose
    of this module.
    """


def _resolve_key(hmac_key: bytes | None) -> bytes:
    """Resolve the HMAC key from an explicit argument or the environment.

    Explicit ``hmac_key`` takes precedence. Otherwise the value of
    ``LIP_MODEL_HMAC_KEY`` is read (UTF-8 encoded). If neither is set, or
    if the resolved key is shorter than :data:`_MIN_KEY_LEN` bytes, a
    ``SecurePickleError`` is raised — fail-closed.
    """
    if hmac_key is not None:
        key = hmac_key
    else:
        env_val = os.environ.get(_HMAC_KEY_ENV)
        if not env_val:
            raise SecurePickleError(
                f"HMAC key not available — set the {_HMAC_KEY_ENV} environment "
                f"variable or pass hmac_key= explicitly. Refusing to load any "
                f"pickle artefact without an integrity key (B10-01/B10-02)."
            )
        key = env_val.encode("utf-8")
    if len(key) < _MIN_KEY_LEN:
        raise SecurePickleError(
            f"HMAC key too short ({len(key)} bytes) — minimum is "
            f"{_MIN_KEY_LEN} bytes (256 bits). Refusing to load."
        )
    return key


def _sig_path(path: str | os.PathLike[str]) -> Path:
    """Return the canonical sidecar signature path for a pickle artefact."""
    p = Path(path)
    return p.with_name(p.name + _SIG_SUFFIX)


def load(
    path: str | os.PathLike[str],
    *,
    hmac_key: bytes | None = None,
):
    """Load a pickle artefact after verifying its HMAC sidecar.

    Parameters
    ----------
    path:
        Path to the ``.pkl`` payload. A sidecar at ``<path>.sig``
        containing a 64-character hex HMAC-SHA256 digest is required.
    hmac_key:
        Optional explicit key override (primarily for tests). In
        production, leave this ``None`` and set ``LIP_MODEL_HMAC_KEY``
        in the environment.

    Returns
    -------
    object
        The deserialised pickle payload.

    Raises
    ------
    SecurePickleError
        On any integrity failure: missing file, missing sidecar, bad
        hex, HMAC mismatch, missing key. *Never falls through to
        ``pickle.load`` on failure.*
    """
    key = _resolve_key(hmac_key)

    payload_path = Path(path)
    if not payload_path.is_file():
        raise SecurePickleError(f"Payload not found: {payload_path}")

    sig_path = _sig_path(payload_path)
    if not sig_path.is_file():
        raise SecurePickleError(
            f"Integrity sidecar missing: expected {sig_path}. "
            f"Refusing to load unsigned pickle artefact (B10-01/B10-02)."
        )

    payload_bytes = payload_path.read_bytes()
    signature = sig_path.read_text(encoding="utf-8").strip()
    if not signature:
        raise SecurePickleError(f"Empty signature sidecar: {sig_path}")

    if not verify_hmac_sha256(payload_bytes, signature, key):
        raise SecurePickleError(
            f"HMAC verification failed for {payload_path}. "
            f"Artefact is corrupt, tampered, or signed with a different key. "
            f"Refusing to load."
        )

    logger.info(
        "secure_pickle.load: integrity verified path=%s bytes=%d",
        payload_path,
        len(payload_bytes),
    )
    # Only reached after successful HMAC verification.
    return pickle.loads(payload_bytes)  # noqa: S301 — verified above


def dump(
    obj: object,
    path: str | os.PathLike[str],
    *,
    hmac_key: bytes | None = None,
) -> None:
    """Serialise *obj* to *path* and write the HMAC sidecar atomically.

    Writes ``<path>`` (pickle payload) and ``<path>.sig`` (hex digest).
    Use this instead of calling ``pickle.dump`` directly so every
    artefact in the repo has a verifiable sidecar by construction.

    Parameters
    ----------
    obj:
        Python object to serialise.
    path:
        Destination path for the pickle payload. Directories must exist.
    hmac_key:
        Optional explicit key override (primarily for tests).
    """
    key = _resolve_key(hmac_key)
    payload_path = Path(path)
    payload_bytes = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    signature = sign_hmac_sha256(payload_bytes, key)

    payload_path.write_bytes(payload_bytes)
    _sig_path(payload_path).write_text(signature, encoding="utf-8")
    logger.info(
        "secure_pickle.dump: wrote signed artefact path=%s bytes=%d",
        payload_path,
        len(payload_bytes),
    )
