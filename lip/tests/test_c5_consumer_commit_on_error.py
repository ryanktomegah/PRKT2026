"""
test_c5_consumer_commit_on_error.py — B6-02 grep guard for the Go consumer.

Before the 2026-04-09 hardening sprint, `processMessage` in
`lip/c5_streaming/go_consumer/consumer.go` called `commitOffset(msg)` on
every code path, including normalization, fan-out, and produce errors.
Transient C1/C2 fan-out errors committed the Kafka offset anyway, so the
message was never reprocessed and was silently lost (assuming DLQ routing
also succeeded — and if it didn't, the message was lost outright).

The fix extracted the commit decision into a single central point
(`workerLoop`) driven by `processMessageResult.shouldCommit()`, and
removed every direct `commitOffset` call from `processMessage`.

This test enforces both invariants at the source-text level so a future
refactor that silently reintroduces the bug fails the Python test suite
even if the Go tests are not run. Pair with the Go-side unit tests in
`consumer_test.go` for the semantic coverage of `shouldCommit`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONSUMER_GO = REPO_ROOT / "lip" / "c5_streaming" / "go_consumer" / "consumer.go"


def _read_consumer() -> str:
    if not CONSUMER_GO.exists():
        pytest.skip("Go consumer source not present")
    return CONSUMER_GO.read_text(encoding="utf-8")


def _extract_function(src: str, signature_prefix: str) -> str:
    """Return the body of the first function whose signature starts with prefix.

    Go functions are balanced-brace blocks; a naive line scan is enough for
    this monorepo's style (no nested funcs with mismatched braces inside
    string literals). If the signature cannot be located the test fails.
    """
    start = src.find(signature_prefix)
    if start == -1:
        raise AssertionError(
            f"Could not locate function starting with {signature_prefix!r}. "
            "If the function was renamed, update this test."
        )
    # Find the opening brace of the function body.
    brace = src.find("{", start)
    assert brace != -1, "malformed Go source — no opening brace after signature"

    depth = 0
    i = brace
    while i < len(src):
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[brace : i + 1]
        i += 1
    raise AssertionError("unbalanced braces — could not extract function body")


def test_process_message_does_not_commit_offset():
    """B6-02: `processMessage` must never call `commitOffset` itself.

    The commit decision now lives in `workerLoop`, which calls commitOffset
    iff `processMessageResult.shouldCommit()` returns true. If a future
    refactor moves the commit back into processMessage, this test fails and
    blocks the commit.
    """
    src = _read_consumer()
    body = _extract_function(
        src, "func (c *Consumer) processMessage(ctx context.Context, msg *kafka.Message)"
    )

    # Allow the word to appear in comments (e.g. "does NOT commitOffset").
    # We strip single-line // comments and inspect what remains.
    stripped = re.sub(r"//[^\n]*", "", body)
    assert "commitOffset" not in stripped, (
        "processMessage in consumer.go calls commitOffset — B6-02 regression. "
        "The commit decision must live in workerLoop, not processMessage."
    )


def test_worker_loop_commits_via_should_commit_only():
    """B6-02: `workerLoop` must gate its commitOffset call on shouldCommit()."""
    src = _read_consumer()
    body = _extract_function(src, "func (c *Consumer) workerLoop(ctx context.Context)")

    # Strip line comments so the regex only inspects real code.
    stripped = re.sub(r"//[^\n]*", "", body)

    assert "shouldCommit()" in stripped, (
        "workerLoop must call result.shouldCommit() to decide whether to "
        "advance the Kafka offset; the guard is missing. B6-02 regression."
    )
    # The commit call must be gated by the shouldCommit check — verify by
    # ensuring the commitOffset token appears AFTER the shouldCommit token in
    # the (comment-stripped) body.
    sc_pos = stripped.find("shouldCommit()")
    co_pos = stripped.find("commitOffset")
    assert sc_pos != -1 and co_pos != -1 and sc_pos < co_pos, (
        "workerLoop calls commitOffset without first checking shouldCommit(). "
        "B6-02 regression: commit must be conditional on successful outcome."
    )


def test_process_message_returns_result_enum():
    """The B6-02 fix hinges on processMessage returning processMessageResult.

    If the return type is dropped (e.g. reverted to a void method), the
    central commit decision in workerLoop breaks. Enforce the signature.
    """
    src = _read_consumer()
    sig_re = re.compile(
        r"func\s*\(\s*c\s*\*Consumer\s*\)\s*processMessage\s*\([^)]*\)\s*processMessageResult",
        re.DOTALL,
    )
    assert sig_re.search(src), (
        "processMessage must return processMessageResult; the signature was "
        "changed. B6-02 regression — the exactly-once commit path depends on "
        "this return type."
    )


def test_known_result_enum_values_present():
    """Every enum value referenced by the Go tests must exist in consumer.go."""
    src = _read_consumer()
    for name in (
        "resultSuccess",
        "resultNullValue",
        "resultNormalizeError",
        "resultFanOutError",
        "resultProduceError",
    ):
        assert name in src, (
            f"processMessageResult enum value {name} is missing from consumer.go. "
            "B6-02 regression — the commit-decision enum has been truncated."
        )
