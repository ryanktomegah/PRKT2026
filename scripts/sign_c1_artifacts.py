#!/usr/bin/env python3
"""
sign_c1_artifacts.py — Retroactively HMAC-sign the C1 pickle artefacts.

The C1 training pipeline in ``scripts/train_c1_on_parquet.py`` emits legacy
unsigned pickles (``c1_lgbm_parquet.pkl``, ``c1_calibrator.pkl``,
``c1_scaler.pkl``) alongside the torch ``.pt`` checkpoint. The runtime
pipeline loads these via ``lip.common.secure_pickle.load()`` (B13-01 pickle
ban) so each must ship with a ``.sig`` sidecar containing an HMAC-SHA256
digest over the pickle bytes.

This script reads each ``.pkl`` in the target directory and writes a
``<name>.sig`` file next to it, signed with ``LIP_MODEL_HMAC_KEY``. It does
NOT re-serialise the pickle — the existing bytes are signed in place so
downstream consumers see the same artefact they were tested against.

Usage:
    LIP_MODEL_HMAC_KEY=... PYTHONPATH=. python scripts/sign_c1_artifacts.py
    PYTHONPATH=. python scripts/sign_c1_artifacts.py \\
        --hmac-key-file .secrets/c2_model_hmac_key \\
        --artifacts-dir artifacts/c1_trained
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from lip.common.encryption import sign_hmac_sha256
from lip.common.secure_pickle import _resolve_key, _sig_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path("artifacts/c1_trained"),
        help="Directory holding c1_*.pkl files.",
    )
    parser.add_argument(
        "--hmac-key-file",
        type=Path,
        default=None,
        help="Optional file containing the HMAC key (overrides env var).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be signed without writing sidecars.",
    )
    return parser.parse_args()


def _load_hmac_key(hmac_key_file: Path | None) -> bytes:
    if hmac_key_file is not None:
        key_text = hmac_key_file.read_text(encoding="utf-8").strip()
        os.environ["LIP_MODEL_HMAC_KEY"] = key_text
    return _resolve_key(None)


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    logger = logging.getLogger("sign_c1_artifacts")

    if not args.artifacts_dir.is_dir():
        raise SystemExit(f"Artifacts dir not found: {args.artifacts_dir}")

    key = _load_hmac_key(args.hmac_key_file)

    pkl_files = sorted(args.artifacts_dir.glob("*.pkl"))
    if not pkl_files:
        logger.warning("No .pkl files found in %s", args.artifacts_dir)
        return 0

    for pkl_path in pkl_files:
        sig_path = _sig_path(pkl_path)
        payload_bytes = pkl_path.read_bytes()
        signature = sign_hmac_sha256(payload_bytes, key)
        if args.dry_run:
            logger.info(
                "[dry-run] would sign %s -> %s (bytes=%d)",
                pkl_path,
                sig_path,
                len(payload_bytes),
            )
            continue
        sig_path.write_text(signature, encoding="utf-8")
        logger.info("signed %s -> %s (bytes=%d)", pkl_path, sig_path, len(payload_bytes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
