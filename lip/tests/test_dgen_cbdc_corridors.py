"""
test_dgen_cbdc_corridors.py — DGEN C1 CBDC corridor coverage tests (2026-04-26).

After Phases A-E shipped CBDC normalisation end-to-end, the C1 classifier
still trained on a SWIFT-only synthetic corpus. This test suite locks in the
CBDC corridor extension to c1_generator: every supported CBDC rail must
appear in the corpus, CBDC-specific failure codes are sampled on CBDC rails,
and the BLOCK invariant (KYC failures non-bridgeable) holds across both
ISO and CBDC code paths.

Why this matters: pilot bank pushes payment through e-CNY → C1 returns
garbage probability if it never saw CBDC events during training → SR 11-7
ML-model audit flags the model as out-of-distribution.
"""
from __future__ import annotations

from collections import Counter

import pytest

from lip.common.block_codes import ALL_BLOCK_CODES
from lip.dgen import c1_generator

# ── Constants under test ──────────────────────────────────────────────────────

EXPECTED_RAILS_IN_CORPUS = {
    "SWIFT",            # legacy cross-border (majority)
    "FEDNOW",           # US domestic instant
    "RTP",              # TCH instant
    "CBDC_ECNY",        # PBoC retail
    "CBDC_EEUR",        # ECB experimental
    "CBDC_SAND_DOLLAR", # CBB retail
    "CBDC_MBRIDGE",     # BIS multi-CBDC PvP wholesale
}

CBDC_BLOCK_CODES = {"CBDC-KYC01", "CBDC-KYC02"}


# ── Coverage tests ────────────────────────────────────────────────────────────

class TestCBDCRailCoverage:
    """Every supported rail must appear in a meaningful sample."""

    def test_all_expected_rails_present(self):
        """A 5000-event sample must include every rail in EXPECTED_RAILS_IN_CORPUS."""
        records = c1_generator.generate_payment_events(n_samples=5_000, seed=7)
        rails_seen = {r["rail"] for r in records}
        missing = EXPECTED_RAILS_IN_CORPUS - rails_seen
        assert not missing, (
            f"DGEN corpus does not produce events for rails: {sorted(missing)}. "
            "C1 will see out-of-distribution events on these rails in production."
        )

    def test_swift_dominates(self):
        """SWIFT should be the majority rail — CBDC volume is small in 2026."""
        records = c1_generator.generate_payment_events(n_samples=5_000, seed=7)
        rails = Counter(r["rail"] for r in records)
        swift_share = rails["SWIFT"] / 5_000
        assert swift_share > 0.7, (
            f"SWIFT share dropped below 70%: {swift_share:.1%}. "
            "Corridor weights may have drifted toward CBDC."
        )

    def test_cbdc_meaningful_fraction(self):
        """Combined CBDC rails should be 5-25% of corpus — enough for C1 to learn."""
        records = c1_generator.generate_payment_events(n_samples=5_000, seed=7)
        cbdc_count = sum(1 for r in records if r["rail"].startswith("CBDC_"))
        cbdc_share = cbdc_count / 5_000
        assert 0.05 <= cbdc_share <= 0.25, (
            f"CBDC share {cbdc_share:.1%} outside 5%-25% target band. "
            "Either too sparse (C1 won't learn) or unrealistically high vs 2026 reality."
        )

    def test_mbridge_dominates_cbdc_volume(self):
        """mBridge should be the largest CBDC rail — matches Q1 2026 reality
        ($55.5B+ cumulative, 5 CBs, post-BIS-exit)."""
        records = c1_generator.generate_payment_events(n_samples=5_000, seed=7)
        cbdc_records = [r for r in records if r["rail"].startswith("CBDC_")]
        if not cbdc_records:
            pytest.skip("No CBDC records in sample (statistical noise)")
        cbdc_rails = Counter(r["rail"] for r in cbdc_records)
        # mBridge should be at least 50% of CBDC volume
        mbridge_pct = cbdc_rails.get("CBDC_MBRIDGE", 0) / len(cbdc_records)
        assert mbridge_pct > 0.5, (
            f"mBridge share of CBDC volume is {mbridge_pct:.1%} — expected >50%. "
            f"Distribution: {dict(cbdc_rails)}"
        )


# ── CBDC code sampling ───────────────────────────────────────────────────────

class TestCBDCCodeSampling:
    """CBDC rails must sample CBDC-specific codes; non-CBDC rails must not."""

    def test_cbdc_rails_only_use_cbdc_codes(self):
        records = c1_generator.generate_payment_events(n_samples=5_000, seed=11)
        for r in records:
            if r["rail"].startswith("CBDC_"):
                assert r["rejection_code"].startswith("CBDC-"), (
                    f"CBDC rail {r['rail']} produced ISO code {r['rejection_code']!r} — "
                    "should always sample CBDC-specific codes."
                )

    def test_non_cbdc_rails_only_use_iso_codes(self):
        records = c1_generator.generate_payment_events(n_samples=5_000, seed=11)
        for r in records:
            if not r["rail"].startswith("CBDC_"):
                assert not r["rejection_code"].startswith("CBDC-"), (
                    f"Non-CBDC rail {r['rail']} produced CBDC code {r['rejection_code']!r} — "
                    "should always sample ISO 20022 codes."
                )

    def test_cbdc_code_distribution_includes_mbridge_signals(self):
        """A 5k sample must include at least one CBDC-CF01 (consensus) and
        at least one CBDC-CB01 (cross-chain bridge) — the signals novel to mBridge."""
        records = c1_generator.generate_payment_events(n_samples=5_000, seed=11)
        codes = {r["rejection_code"] for r in records if r["rail"].startswith("CBDC_")}
        for novel in ("CBDC-CF01", "CBDC-CB01"):
            assert novel in codes, (
                f"CBDC code {novel} (mBridge-novel signal) absent from 5k sample."
            )


# ── BLOCK invariant ──────────────────────────────────────────────────────────

class TestCBDCBlockInvariant:
    """CBDC KYC failures (CBDC-KYC01/02) must be non-bridgeable, even though
    they're not in ALL_BLOCK_CODES (they map to RR01/RR02 at the
    normalisation layer, not in C1 input)."""

    def test_cbdc_kyc_codes_marked_non_bridgeable(self):
        records = c1_generator.generate_payment_events(n_samples=10_000, seed=17)
        cbdc_kyc = [r for r in records if r["rejection_code"] in CBDC_BLOCK_CODES]
        assert len(cbdc_kyc) > 0, (
            "10k sample produced no CBDC-KYC01/02 records — distribution likely broken."
        )
        for r in cbdc_kyc:
            assert r["is_bridgeable"] is False, (
                f"CBDC BLOCK code {r['rejection_code']} on rail {r['rail']} "
                f"marked is_bridgeable=True — EPG-19/22 invariant broken."
            )
            assert r["rejection_class"] == "BLOCK"

    def test_no_cbdc_block_code_in_iso_block_set(self):
        """Sanity: CBDC codes are NOT in ALL_BLOCK_CODES (which is the canonical
        ISO 20022 BLOCK set). They map to RR01/RR02 at C5 normalisation —
        only the *post-normalisation* code is in the ISO BLOCK set."""
        for cbdc_code in CBDC_BLOCK_CODES:
            assert cbdc_code not in ALL_BLOCK_CODES, (
                f"{cbdc_code} should NOT be in ALL_BLOCK_CODES. "
                "It's a CBDC-layer code that NORMALISES to RR01/RR02 (which IS in the set)."
            )


# ── Determinism ──────────────────────────────────────────────────────────────

class TestDeterminism:
    """Seeded generation must be deterministic across calls — required for
    SR 11-7 model-validation reproducibility."""

    def test_same_seed_same_corpus(self):
        a = c1_generator.generate_payment_events(n_samples=500, seed=99)
        b = c1_generator.generate_payment_events(n_samples=500, seed=99)
        # UUID and timestamp_iso fields use module-level randomness/clock and
        # legitimately differ between calls — compare structural fields only.
        for ra, rb in zip(a, b):
            assert ra["rail"] == rb["rail"]
            assert ra["currency_pair"] == rb["currency_pair"]
            assert ra["rejection_code"] == rb["rejection_code"]
            assert ra["amount_usd"] == rb["amount_usd"]
