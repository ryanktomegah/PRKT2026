"""
test_pickle_ban.py — B13-01 regression test.

The 2026-04-08 code review found two Critical RCE findings (B10-01 and
B10-02) caused by direct ``pickle.load`` calls on model artefacts with
no integrity verification. Batch 13 flagged that no regression test
existed to catch future regressions — ``grep pickle`` returned no hits
in ``lip/tests/``.

This test enforces the invariant:

    The ONLY legal site for ``pickle.load``/``pickle.loads`` in the LIP
    codebase is ``lip/common/secure_pickle.py``. All other production
    modules must load pickle artefacts through that wrapper.

If a new ``pickle.load`` call appears anywhere else in ``lip/`` (outside
the test directory), this test fails. That forces the author either to
route through the wrapper or — in the exceptional case where the call
is genuinely trusted — to update the whitelist here with an explicit
justification, forcing CIPHER review.

Scope
-----
* **Scanned**: every ``.py`` file under ``lip/`` except ``lip/tests/``
  and ``lip/common/secure_pickle.py`` itself.
* **Banned tokens** (matched as regex, whole identifiers):
    ``pickle.load``, ``pickle.loads``, ``cPickle.load``, ``cPickle.loads``
* **Allowed**: comments and docstrings that *reference* the banned token
  are permitted — matches inside ``#`` or triple-quoted strings are
  ignored via a simple AST-free heuristic (the production code for
  these modules uses the real call, not a string). To keep the test
  strict and readable we only ignore lines where the match lives after
  a ``#`` comment marker.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# Repo-relative path to the lip/ package root.
_LIP_ROOT = Path(__file__).resolve().parent.parent

# Files that are *explicitly* allowed to contain pickle.load/pickle.loads.
# Adding to this whitelist requires CIPHER sign-off per CLAUDE.md — the
# review explicitly flagged the absence of this gate as a Critical.
_ALLOWED = {
    _LIP_ROOT / "common" / "secure_pickle.py",
}

# The test directory is excluded because tests legitimately need to
# construct and inspect pickle payloads (e.g. the secure_pickle unit
# tests themselves test the wrapper's behaviour on tampered payloads).
# Any pickle usage in tests is bounded by pytest scope and cannot
# affect production integrity.
_EXCLUDED_DIRS = {
    _LIP_ROOT / "tests",
    _LIP_ROOT.parent / "pytest-of-tomegah",
}

_BANNED_PATTERNS = [
    re.compile(r"\bpickle\.load\b"),
    re.compile(r"\bpickle\.loads\b"),
    re.compile(r"\bcPickle\.load\b"),
    re.compile(r"\bcPickle\.loads\b"),
]


def _is_excluded(path: Path) -> bool:
    for parent in _EXCLUDED_DIRS:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            continue
    return path in _ALLOWED


def _line_is_comment(line: str, match: re.Match) -> bool:
    """Is the match inside a ``#`` comment on this physical line?"""
    hash_idx = line.find("#")
    if hash_idx == -1:
        return False
    return match.start() > hash_idx


def _iter_py_files() -> list[Path]:
    return [p for p in _LIP_ROOT.rglob("*.py") if not _is_excluded(p)]


def test_pickle_load_is_banned_outside_secure_pickle():
    """B13-01: no production module may call pickle.load[s] directly."""
    violations: list[tuple[Path, int, str]] = []

    for py_file in _iter_py_files():
        try:
            text = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pat in _BANNED_PATTERNS:
                m = pat.search(line)
                if not m:
                    continue
                if _line_is_comment(line, m):
                    continue
                violations.append((py_file, lineno, line.strip()))

    assert not violations, (
        "B13-01 violation — direct pickle.load[s] calls found outside "
        "lip/common/secure_pickle.py. Route the load through "
        "lip.common.secure_pickle.load() instead:\n\n"
        + "\n".join(
            f"  {p.relative_to(_LIP_ROOT.parent)}:{ln}  {src}"
            for p, ln, src in violations
        )
    )


def test_secure_pickle_wrapper_exists():
    """Sanity: the allowed site must actually exist."""
    allowed_path = _LIP_ROOT / "common" / "secure_pickle.py"
    assert allowed_path.is_file(), (
        "lip/common/secure_pickle.py must exist — it is the only legal "
        "pickle loader. If you deleted or moved it, update this test and "
        "get CIPHER sign-off on the replacement."
    )
    text = allowed_path.read_text(encoding="utf-8")
    assert "pickle.loads" in text, (
        "secure_pickle.py no longer calls pickle.loads — this test now "
        "guards an empty whitelist. Either restore the wrapper or remove "
        "the whitelist entry."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
