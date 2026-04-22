"""
local_env.py — lightweight repo-local environment loader for dev/test runs.

Loads a gitignored ``.env.local`` file when present, without overriding real
environment variables that are already set by the shell, CI, or container
runtime. Relative ``*_FILE`` values are resolved from the repository root so
file-backed secrets work consistently across pytest, scripts, and app startup.
"""
from __future__ import annotations

import os
from pathlib import Path


def load_repo_env_file() -> None:
    """Load ``.env.local`` into ``os.environ`` when available.

    Behavior:
    - no-op when the file is absent
    - preserves existing environment variables
    - resolves relative ``*_FILE`` values against the repo root
    """
    repo_root = Path(__file__).resolve().parents[2]
    env_path = os.environ.get("LIP_ENV_FILE", "").strip()
    env_file = Path(env_path) if env_path else repo_root / ".env.local"
    if not env_file.is_file():
        return

    try:
        raw_lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    env_base = env_file.parent
    for raw_line in raw_lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if not key or key in os.environ:
            continue

        if key.endswith("_FILE") and value and not os.path.isabs(value):
            value = str((env_base / value).resolve())
        os.environ[key] = value
