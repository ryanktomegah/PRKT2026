"""
test_block_code_drift.py — Cross-language BLOCK-codes drift guard (B13-02).

Single source of truth for the BLOCK-class rejection codes is
``lip/common/block_codes.json``. This test asserts every consumer in the
monorepo (Python loaders, Python call sites, Rust crate, Go consumer)
sees the same set. Adding a new code to the JSON without updating a
consumer — or hand-editing a consumer to drift from the JSON — will fail
this test loudly instead of producing a silent EPG-19 enforcement gap.

History: Before commit 4 of the 2026-04-09 hardening sprint, the BLOCK
list was hand-maintained in five independent locations across three
languages, plus a wholly-incorrect copy in DGEN's c1_generator.py that
trained C1 to bridge EPG-19 compliance holds. The fix consolidated the
list into block_codes.json + a Python loader, and this test is the load
that keeps it consolidated.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ground truth: read the JSON directly, do not import the loader.
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = REPO_ROOT / "lip" / "common" / "block_codes.json"


def _load_ground_truth() -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    """Return (compliance_hold, dispute_fraud, all_block) from the JSON."""
    raw = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    compliance = frozenset(raw["epg19_compliance_hold"])
    fraud = frozenset(raw["dispute_fraud_block"])
    return compliance, fraud, compliance | fraud


GROUND_COMPLIANCE, GROUND_FRAUD, GROUND_ALL = _load_ground_truth()


# ---------------------------------------------------------------------------
# JSON shape — invariants the loader and every consumer rely on.
# ---------------------------------------------------------------------------

def test_json_has_eight_compliance_hold_codes():
    """EPG-19 compliance-hold set is exactly 8 codes."""
    assert len(GROUND_COMPLIANCE) == 8, sorted(GROUND_COMPLIANCE)


def test_json_has_four_dispute_fraud_codes():
    """Dispute/fraud BLOCK set is exactly 4 codes."""
    assert len(GROUND_FRAUD) == 4, sorted(GROUND_FRAUD)


def test_json_subsets_disjoint():
    """Compliance-hold and dispute/fraud sets must not overlap."""
    assert not (GROUND_COMPLIANCE & GROUND_FRAUD)


def test_json_total_is_twelve():
    """Full BLOCK class is exactly 12 codes."""
    assert len(GROUND_ALL) == 12


# ---------------------------------------------------------------------------
# Python loader — lip.common.block_codes
# ---------------------------------------------------------------------------

def test_python_loader_matches_json():
    """The Python loader exposes frozensets equal to the JSON arrays."""
    from lip.common import block_codes  # noqa: PLC0415

    assert block_codes.EPG19_COMPLIANCE_HOLD_CODES == GROUND_COMPLIANCE
    assert block_codes.DISPUTE_FRAUD_BLOCK_CODES == GROUND_FRAUD
    assert block_codes.ALL_BLOCK_CODES == GROUND_ALL


# ---------------------------------------------------------------------------
# Python consumer call sites — every site that uses a BLOCK set must derive
# it from lip.common.block_codes (B6-01) or from the rejection_taxonomy
# canonical mapping. Sets that drift trigger the failure here.
# ---------------------------------------------------------------------------

def test_event_normalizer_block_set_matches_json():
    """C5 event normalizer's BLOCK set must equal the JSON ground truth."""
    from lip.c5_streaming.event_normalizer import _BLOCK_REJECTION_CODES  # noqa: PLC0415

    assert frozenset(_BLOCK_REJECTION_CODES) == GROUND_ALL


def test_telemetry_collector_block_set_matches_json():
    """P10 telemetry collector's BLOCK set must equal the JSON ground truth."""
    from lip.p10_regulatory_data.telemetry_collector import _BLOCK_CODES  # noqa: PLC0415

    assert frozenset(_BLOCK_CODES) == GROUND_ALL


def test_c7_agent_compliance_hold_set_matches_json():
    """C7 ExecutionAgent's compliance-hold set must equal the JSON BLOCK set.

    agent.py derives this from rejection_taxonomy via
    ``get_all_codes_for_class(RejectionClass.BLOCK)``; if either the
    taxonomy or the JSON drifts, this assertion fails.
    """
    from lip.c7_execution_agent import agent  # noqa: PLC0415

    assert frozenset(agent._COMPLIANCE_HOLD_CODES) == GROUND_ALL


def test_rejection_taxonomy_block_class_matches_json():
    """The C3 canonical taxonomy's BLOCK class must equal the JSON ground truth."""
    from lip.c3_repayment_engine.rejection_taxonomy import (  # noqa: PLC0415
        REJECTION_CODE_TAXONOMY,
        RejectionClass,
    )

    derived = frozenset(
        code
        for code, cls in REJECTION_CODE_TAXONOMY.items()
        if cls is RejectionClass.BLOCK
    )
    assert derived == GROUND_ALL


def test_synthetic_data_block_set_matches_json():
    """C1 synthetic data generator's BLOCK set must equal the JSON ground truth."""
    from lip.c1_failure_classifier import synthetic_data  # noqa: PLC0415

    assert frozenset(synthetic_data._BLOCK_CODES) == GROUND_ALL


# ---------------------------------------------------------------------------
# DGEN c1_generator — the original B11-02 bug (table tagged BLOCK codes
# as Class B/C and BLOCK as A/B). Verify every BLOCK code is present and
# tagged BLOCK, and verify is_bridgeable is False on every BLOCK record.
# ---------------------------------------------------------------------------

def test_dgen_c1_generator_block_codes_match_json():
    """DGEN's _REJECTION_CODES dict tags exactly the JSON BLOCK codes as BLOCK."""
    from lip.dgen import c1_generator  # noqa: PLC0415

    dgen_block = frozenset(
        code for code, (cls, _) in c1_generator._REJECTION_CODES.items() if cls == "BLOCK"
    )
    assert dgen_block == GROUND_ALL


def test_dgen_generated_block_records_not_bridgeable():
    """Every generated record carrying a BLOCK code must have is_bridgeable=False.

    This is the load-bearing check for B11-02: it would have caught the
    historical RR01-as-Class-B mislabel because the generator emitted
    `is_bridgeable=True` for those records.
    """
    from lip.dgen import c1_generator  # noqa: PLC0415

    records = c1_generator.generate_payment_events(n_samples=2_000, seed=11)
    seen_block_codes: set[str] = set()
    for r in records:
        if r["rejection_code"] in GROUND_ALL:
            assert r["is_bridgeable"] is False, (
                f"BLOCK code {r['rejection_code']} marked is_bridgeable=True — "
                "B11-02 regression."
            )
            seen_block_codes.add(r["rejection_code"])

    # At 2k samples with ~17% BLOCK weighting we expect to hit at least
    # half of the 12 BLOCK codes; if zero are present the corpus is broken.
    assert len(seen_block_codes) >= 6, (
        f"Sampled too few distinct BLOCK codes ({sorted(seen_block_codes)}) — "
        "DGEN distribution likely regressed."
    )


# ---------------------------------------------------------------------------
# Rust crate — text-parse the source to confirm it loads via include_str!
# rather than hand-maintaining a parallel const list. We don't shell out to
# cargo here (too slow for the unit suite); the Rust unit tests in
# lip/c3/rust_state_machine/src/taxonomy.rs cover the runtime behaviour.
# ---------------------------------------------------------------------------

RUST_TAXONOMY_PATH = REPO_ROOT / "lip" / "c3" / "rust_state_machine" / "src" / "taxonomy.rs"


def test_rust_taxonomy_loads_block_codes_from_json():
    """Rust crate must include_str! the shared JSON, not embed a literal list."""
    src = RUST_TAXONOMY_PATH.read_text(encoding="utf-8")

    assert 'include_str!("../../../common/block_codes.json")' in src, (
        "Rust taxonomy.rs must load the BLOCK list from the shared JSON via "
        "include_str!. Found no include_str reference."
    )

    # Guard against any future re-introduction of a hand-maintained const.
    forbidden_pattern = re.compile(
        r'(?:pub\s+)?const\s+\w*BLOCK\w*\s*:\s*&\[&str\]\s*='
    )
    assert not forbidden_pattern.search(src), (
        "Rust taxonomy.rs reintroduced a hand-maintained BLOCK code constant. "
        "Load via include_str!(block_codes.json) instead."
    )


# ---------------------------------------------------------------------------
# Go consumer — text-parse the source. The go_consumer module has its own
# go.mod, so go:embed across module boundaries is unworkable; until Phase 2
# vendors the JSON into the module, this test is the drift guard.
# ---------------------------------------------------------------------------

GO_NORMALIZER_PATH = (
    REPO_ROOT / "lip" / "c5_streaming" / "go_consumer" / "normalizer.go"
)


def test_go_normalizer_block_codes_match_json():
    """Parse the Go literal map and verify its key set equals the JSON ground truth."""
    if not GO_NORMALIZER_PATH.exists():
        pytest.skip("Go consumer source not present")

    src = GO_NORMALIZER_PATH.read_text(encoding="utf-8")

    # Find: blockRejectionCodes = map[string]bool{ "DNOR": true, ... }
    block_map_re = re.compile(
        r"blockRejectionCodes\s*=\s*map\[string\]bool\s*\{([^}]+)\}",
        re.DOTALL,
    )
    m = block_map_re.search(src)
    assert m is not None, (
        "Could not find blockRejectionCodes literal map in normalizer.go. "
        "If the variable was renamed, update this drift test."
    )

    body = m.group(1)
    keys = set(re.findall(r'"([A-Z0-9]+)"\s*:\s*true', body))
    assert keys == GROUND_ALL, (
        f"Go normalizer BLOCK map drifted from block_codes.json. "
        f"Missing in Go: {sorted(GROUND_ALL - keys)}. "
        f"Extra in Go: {sorted(keys - GROUND_ALL)}."
    )
