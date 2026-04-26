"""
c1_generator.py — DGEN: C1 Payment Failure Event Generator
===========================================================
Generates synthetic ISO 20022 pacs.002/RJCT-style payment events calibrated
against BIS CPMI Quarterly Payment Statistics (cpmi.bis.org) and SWIFT GPI
transparency data.

Design principles:
  - Corridor failure rates calibrated to BIS-published STP rates per corridor.
  - BIC pool of 500 synthetic banks with realistic HHI-based concentration.
  - Rejection codes follow ISO 20022 pacs.002 taxonomy (Class A/B/C/BLOCK).
  - Temporal distribution: 18-month spread (2023-07 → 2025-01) for SR 11-7
    out-of-time validation.

BIS CPMI calibration (2024 report):
  EUR/USD: ~85% STP → 15% failure rate
  GBP/USD: ~92% STP → 8% failure rate
  USD/JPY: ~88% STP → 12% failure rate
  Emerging (USD/CNY, USD/INR, etc.): ~72-78% STP → 22-28% failure rate
  Overall weighted average: ~96.5% STP → 3.5% failure rate

All records tagged: corpus_tag = "SYNTHETIC_CORPUS_C1"

CBDC corridor extension (2026-04-26, Phases A-E follow-up):
  - Adds 8 CBDC corridors (e-CNY, e-EUR, Sand Dollar, mBridge multi-CBDC PvP, FedNow/RTP).
  - CBDC-specific failure codes (CBDC-SC01/SC02, CBDC-LIQ01/LIQ02, CBDC-FIN01,
    CBDC-CF01 mBridge consensus, CBDC-CB01 cross-chain, CBDC-NET01) are added
    alongside ISO 20022 codes so C1 sees both during training.
  - Corridor weights are *deliberately small* (~12% combined) — CBDC volume is
    a small fraction of cross-border flow as of 2026-04 (mBridge ~$55.5B
    cumulative across 5 central banks; e-CNY mostly domestic; FedNow
    growing but still <5% of US instant volume).
  - Failure rates calibrated to public reporting where available; modelled
    where not (Nexus stub deferred — onboarding mid-2027).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

import numpy as np

from lip.common.block_codes import ALL_BLOCK_CODES
from lip.common.constants import DGEN_EPOCH_SPAN, DGEN_EPOCH_START
from lip.dgen.bic_pool import BICPool

_CORPUS_TAG = "SYNTHETIC_CORPUS_C1"

# ── BIS-calibrated corridor config ─────────────────────────────────────────────

# (currency_pair, weight_in_volume, failure_rate, rail)
# Weights sum to 1.0; failure rates from BIS CPMI 2024 + SWIFT GPI data.
#
# Rail breakdown (2026-04 baseline):
#   - SWIFT corridors:       ~84% of generated volume  (matches real cross-border share)
#   - FedNow / RTP domestic: ~4%   (US instant rails — 24h maturity, sub-day floor)
#   - CBDC retail:           ~3%   (e-CNY mostly domestic; e-EUR experimental; Sand Dollar small)
#   - CBDC_MBRIDGE wholesale:~9%   (post-BIS-exit; $55.5B cumulative across 5 CBs as of Q1 2026)
#
# Rail field on each generated record drives downstream rail-aware maturity
# (Phase A) and lets C1 learn rail × failure-mode interactions (e.g. mBridge
# consensus failures look different from SWIFT KYC rejections).
#
# Failure rates for CBDC rails are modelled, not measured — public CBDC
# settlement-failure data does not exist at usable granularity. Rates are
# bounded by published rail finality SLAs.
_CORRIDORS = [
    # ── SWIFT cross-border ─────────────────────────────────────────────────
    ("EUR/USD",  0.20,  0.150, "SWIFT"),     # EUR/USD: 85% STP = 15% failure
    ("USD/EUR",  0.13,  0.150, "SWIFT"),
    ("GBP/USD",  0.10,  0.080, "SWIFT"),     # GBP/USD: 92% STP = 8% failure
    ("USD/GBP",  0.07,  0.080, "SWIFT"),
    ("USD/JPY",  0.08,  0.120, "SWIFT"),     # USD/JPY: 88% STP = 12% failure
    ("USD/CHF",  0.03,  0.090, "SWIFT"),
    ("EUR/GBP",  0.05,  0.110, "SWIFT"),
    ("USD/CAD",  0.04,  0.095, "SWIFT"),
    ("USD/CNY",  0.05,  0.260, "SWIFT"),     # Emerging: 74% STP = 26% failure
    ("USD/INR",  0.03,  0.280, "SWIFT"),     # Emerging: 72% STP = 28% failure
    ("USD/SGD",  0.03,  0.180, "SWIFT"),
    ("EUR/CHF",  0.02,  0.085, "SWIFT"),
    # ── FedNow domestic instant (24h maturity, sub-day floor applies) ──────
    ("USD/USD",  0.03,  0.020, "FEDNOW"),    # Domestic: ~98% STP = 2% failure
    # ── RTP domestic instant ────────────────────────────────────────────────
    ("USD/USD",  0.01,  0.020, "RTP"),       # Same currency-pair as FedNow; rail tag distinguishes
    # ── CBDC retail (4h maturity, 1200 bps sub-day floor) ──────────────────
    ("CNY/CNY",  0.015, 0.030, "CBDC_ECNY"),         # PBoC e-CNY — domestic-heavy
    ("EUR/EUR",  0.005, 0.040, "CBDC_EEUR"),         # ECB experimental — small volume
    ("BSD/USD",  0.005, 0.050, "CBDC_SAND_DOLLAR"),  # CBB Sand Dollar
    # ── CBDC mBridge wholesale (5 currencies; PvP atomic settlement) ───────
    # mBridge represents the largest non-SWIFT CBDC volume as of Q1 2026.
    # Failure rates modelled at ~3% (public reporting suggests low single-digit
    # consensus failures + cross-chain bridge failures). Mapped through one
    # primary leg per record (the failed leg) — multi-leg metadata is preserved
    # in raw_source by MBridgeNormalizer at runtime; not needed for C1 training.
    ("CNY/HKD",  0.030, 0.030, "CBDC_MBRIDGE"),  # PBoC ↔ HKMA — largest mBridge corridor
    ("CNY/THB",  0.020, 0.030, "CBDC_MBRIDGE"),
    ("HKD/AED",  0.015, 0.035, "CBDC_MBRIDGE"),
    ("THB/AED",  0.010, 0.035, "CBDC_MBRIDGE"),
    ("AED/SAR",  0.015, 0.030, "CBDC_MBRIDGE"),  # SAMA joined post-BIS-exit
]
_CORRIDOR_PAIRS  = [c[0] for c in _CORRIDORS]
_CORRIDOR_WEIGHTS = np.array([c[1] for c in _CORRIDORS])
_CORRIDOR_WEIGHTS /= _CORRIDOR_WEIGHTS.sum()  # normalise
_CORRIDOR_FAILURE = [c[2] for c in _CORRIDORS]
_CORRIDOR_RAILS   = [c[3] for c in _CORRIDORS]

# ISO 20022 rejection codes with class labels (A=3d, B=7d, C=21d, BLOCK=0d)
# Distribution from SWIFT GPI and LIP architecture spec Appendix B.
# B11-07: Frequency weights are drawn from SWIFT GPI Joint Analytics (CPMI
# Quarterly Payment Statistics 2024) — the Appendix B table uses observed
# proportions across 15 corridors.  These are empirical, not uniform.
# Exact source: "BIS/SWIFT GPI Steering Group — Cross-Border Payments Monitoring
# Dashboard 2024 Q3, Table 4b (rejection reason distribution by code class)."
#
# B11-02: Before this commit, the table tagged RR01/RR02 as Class B, FRAU/LEGL
# as Class C, and NARR/FF01 as BLOCK — opposite to the canonical taxonomy in
# lip/c3_repayment_engine/rejection_taxonomy.py. C1 trained on this corpus
# learned to bridge EPG-19 compliance holds (catastrophic), and the corpus
# contained no examples at all for DNOR, CNOR, RR03, RR04, AG01, DISP, DUPL,
# FRAD. The table is now realigned to the canonical 12-code BLOCK class, with
# the import-time invariant below enforcing parity against
# lip.common.block_codes.ALL_BLOCK_CODES (B6-01 single source of truth).
_REJECTION_CODES = {
    # ── Class A (technical / routing): ~30% of failures ────────────────────
    "AC01": ("A", 0.10),  # Incorrect account number
    "AC04": ("A", 0.07),  # Closed account
    "AC06": ("A", 0.04),  # Blocked account
    "BE04": ("A", 0.05),  # Missing creditor address
    "RC01": ("A", 0.04),  # BIC invalid
    "FF01": ("A", 0.02),  # Invalid file format (was BLOCK in pre-B11-02 table)

    # ── Class B (systemic / processing): ~40% of failures ──────────────────
    "AM04": ("B", 0.13),  # Insufficient funds
    "AM05": ("B", 0.09),  # Duplicate payment
    "CUST": ("B", 0.07),  # Customer decision
    "NARR": ("B", 0.06),  # Narrative (was BLOCK in pre-B11-02 table)
    "AG02": ("B", 0.04),  # Invalid bank operation code

    # ── Class C (investigation / complex): ~12% of failures ────────────────
    "AGNT": ("C", 0.05),  # Incorrect agent
    "INVB": ("C", 0.04),  # Invalid BIC
    "NOAS": ("C", 0.03),  # No answer from customer

    # ── BLOCK (compliance / dispute / legal): ~17% of failures ─────────────
    # EPG-19 compliance hold — 8 codes, REX final authority, never bridgeable.
    "DNOR": ("BLOCK", 0.015),  # DebtorNotAllowedToSend (EPG-02)
    "CNOR": ("BLOCK", 0.015),  # CreditorNotAllowedToReceive (EPG-03)
    "RR01": ("BLOCK", 0.018),  # MissingDebtorAccountOrIdentification (EPG-01)
    "RR02": ("BLOCK", 0.014),  # MissingDebtorNameOrAddress (EPG-01)
    "RR03": ("BLOCK", 0.012),  # MissingCreditorNameOrAddress (EPG-01)
    "RR04": ("BLOCK", 0.014),  # RegulatoryReason (EPG-07)
    "AG01": ("BLOCK", 0.012),  # TransactionForbidden (EPG-08)
    "LEGL": ("BLOCK", 0.018),  # LegalDecision (EPG-08)
    # Dispute / fraud — 4 codes, hard-blocked before C1 in pipeline.py.
    "DISP": ("BLOCK", 0.013),  # DisputedTransaction
    "DUPL": ("BLOCK", 0.011),  # DuplicateDetected
    "FRAD": ("BLOCK", 0.011),  # FraudulentOrigin
    "FRAU": ("BLOCK", 0.018),  # Fraud
}
_REJECTION_CODE_LIST = list(_REJECTION_CODES.keys())
_REJECTION_WEIGHTS = np.array([v[1] for v in _REJECTION_CODES.values()])
_REJECTION_WEIGHTS /= _REJECTION_WEIGHTS.sum()

# ── CBDC-specific rejection codes (P5 patent, normalisation layer) ─────────────
# C5's CBDCNormalizer maps these to ISO 20022 equivalents at runtime
# (see lip/c5_streaming/cbdc_normalizer.py:CBDC_FAILURE_CODE_MAP). For C1
# training we sample the ORIGINAL CBDC code on CBDC rails so the classifier
# learns rail × code pairs (e.g. "CBDC_MBRIDGE + CBDC-CF01 = consensus
# failure" is a different signal than "SWIFT + AM04 = funding shortfall").
#
# Class assignments mirror the ISO mapping:
#   CBDC-SC01..03  → A (smart-contract / account errors)
#   CBDC-KYC01..02 → BLOCK (KYC failure → RR01/RR02 generic, EPG-19 enforced)
#   CBDC-LIQ01..02 → B (liquidity / amount limit)
#   CBDC-FIN01..02 → B (finality / timing)
#   CBDC-INT01..02 → A/C (cross-chain interop)
#   CBDC-CRY01..02 → A (cryptographic)
#   CBDC-NET01     → C (network congestion)
#   CBDC-CF01      → B (mBridge consensus failure)
#   CBDC-CB01      → A (mBridge cross-chain bridge failure)
#
# Weights are evened across CBDC codes — production CBDC rails are too new
# for empirical distribution data. Normalised independently of ISO weights
# so the BLOCK invariant against ALL_BLOCK_CODES (canonical ISO list) does
# not need to know about CBDC codes.
_CBDC_REJECTION_CODES = {
    "CBDC-SC01":  ("A",     0.10),
    "CBDC-SC02":  ("A",     0.05),
    "CBDC-SC03":  ("A",     0.05),
    "CBDC-KYC01": ("BLOCK", 0.05),  # → RR01 (generic KYC, EPG-19)
    "CBDC-KYC02": ("BLOCK", 0.04),  # → RR02
    "CBDC-LIQ01": ("B",     0.18),  # → AM04 (most common CBDC failure)
    "CBDC-LIQ02": ("B",     0.05),
    "CBDC-FIN01": ("B",     0.10),  # mBridge: finality timeout under load
    "CBDC-FIN02": ("B",     0.05),
    "CBDC-INT01": ("A",     0.04),
    "CBDC-INT02": ("C",     0.03),
    "CBDC-CRY01": ("A",     0.04),
    "CBDC-CRY02": ("A",     0.02),
    "CBDC-NET01": ("C",     0.05),
    "CBDC-CF01":  ("B",     0.10),  # mBridge consensus
    "CBDC-CB01":  ("A",     0.05),  # mBridge cross-chain bridge
}
_CBDC_REJECTION_LIST    = list(_CBDC_REJECTION_CODES.keys())
_CBDC_REJECTION_WEIGHTS = np.array([v[1] for v in _CBDC_REJECTION_CODES.values()])
_CBDC_REJECTION_WEIGHTS /= _CBDC_REJECTION_WEIGHTS.sum()

# Rails that should sample CBDC rejection codes (vs ISO 20022).
# FedNow/RTP keep ISO codes since they're domestic instant rails using ISO
# natively (or proprietary codes mapped at the connector layer).
_CBDC_CODE_RAILS = frozenset({
    "CBDC_ECNY", "CBDC_EEUR", "CBDC_SAND_DOLLAR", "CBDC_MBRIDGE", "CBDC_NEXUS",
})

# B11-02 invariant — fail-loud at import if the corpus drifts from the
# canonical BLOCK list. Generating training data with the wrong bridgeability
# label is the exact failure mode the 2026-04-08 review caught, and a silent
# regression here would be hard to spot in metrics.
_DGEN_BLOCK_CODES = {code for code, (cls, _) in _REJECTION_CODES.items() if cls == "BLOCK"}
if _DGEN_BLOCK_CODES != set(ALL_BLOCK_CODES):
    _missing = set(ALL_BLOCK_CODES) - _DGEN_BLOCK_CODES
    _extra = _DGEN_BLOCK_CODES - set(ALL_BLOCK_CODES)
    raise RuntimeError(
        "DGEN c1_generator BLOCK list drifts from lip.common.block_codes. "
        f"Missing from corpus: {sorted(_missing)}. "
        f"Extra in corpus (should not be BLOCK): {sorted(_extra)}. "
        "Update _REJECTION_CODES to match block_codes.json before regenerating."
    )

# B11-10 / B11-11: Canonical BIC pool imported from bic_pool.py.
# Previously c1_generator maintained a separate inline pool of 300 BICs;
# bic_pool.BICPool provides 200 BICs (10 hub + 190 spoke) with hub-and-spoke
# topology and ISO 9362 format compliance — consolidating to one source of truth.
_BIC_POOL = BICPool()
_BICS = _BIC_POOL.all_bics  # 200 BICs (hub + spoke), ISO 9362-compliant

# Amount distribution: log-normal centered at $500K, range $5K–$50M
_AMOUNT_MU = 13.0   # ln(~$440K)
_AMOUNT_SIGMA = 1.5

# B11-06: Temporal spread imported from lip.common.constants (DGEN_EPOCH_START /
# DGEN_EPOCH_SPAN) — 2023-07-01 → 2025-01-01, 18 months, SR 11-7 out-of-time.
_EPOCH_START = DGEN_EPOCH_START
_EPOCH_SPAN  = DGEN_EPOCH_SPAN


def generate_payment_events(n_samples: int = 10_000, seed: int = 42) -> List[dict]:
    """Generate synthetic ISO 20022 RJCT payment events.

    Parameters
    ----------
    n_samples:
        Number of events to generate. All events are payment *failures*
        (RJCT) since LIP only processes rejected payments.
    seed:
        Random seed for reproducibility.

    Returns
    -------
    List[dict]
        Each dict contains: uetr, individual_payment_id, sending_bic,
        receiving_bic, amount_usd, currency_pair, rejection_code,
        rejection_class (A/B/C/BLOCK), corridor_failure_rate, timestamp_unix,
        timestamp_iso, label (always 1 — failed), is_bridgeable (True when
        rejection_class != BLOCK — EPG-12/22 bridgeability label),
        corpus_tag, generation_seed.
    """
    rng = np.random.default_rng(seed)
    ts = datetime.now(tz=timezone.utc).isoformat()

    # Sample corridors (carries rail tag)
    corridor_idx = rng.choice(len(_CORRIDORS), size=n_samples, p=_CORRIDOR_WEIGHTS)
    # Pre-sample BOTH ISO and CBDC code indices; pick at iteration time based on rail
    iso_code_idx  = rng.choice(len(_REJECTION_CODE_LIST), size=n_samples, p=_REJECTION_WEIGHTS)
    cbdc_code_idx = rng.choice(len(_CBDC_REJECTION_LIST), size=n_samples, p=_CBDC_REJECTION_WEIGHTS)
    # Sample BIC pairs (sending != receiving)
    sender_idx = rng.integers(0, len(_BICS), size=n_samples)
    receiver_delta = rng.integers(1, len(_BICS), size=n_samples)
    receiver_idx = (sender_idx + receiver_delta) % len(_BICS)
    # Sample amounts (log-normal)
    amounts = np.exp(rng.normal(_AMOUNT_MU, _AMOUNT_SIGMA, size=n_samples))
    amounts = np.clip(amounts, 5_000, 50_000_000)
    # Sample timestamps
    epoch_offsets = rng.uniform(0, _EPOCH_SPAN, size=n_samples)

    records: List[dict] = []
    for i in range(n_samples):
        corr      = _CORRIDORS[corridor_idx[i]]
        curr_pair = corr[0]
        rail      = corr[3]
        # CBDC rails sample CBDC-specific codes; everything else uses ISO 20022.
        # This lets C1 learn rail × code interaction without forcing CBDC events
        # to wear ISO codes (which would lose the rail-specific failure-mode signal).
        if rail in _CBDC_CODE_RAILS:
            code = _CBDC_REJECTION_LIST[cbdc_code_idx[i]]
            rj_class, _ = _CBDC_REJECTION_CODES[code]
        else:
            code = _REJECTION_CODE_LIST[iso_code_idx[i]]
            rj_class, _ = _REJECTION_CODES[code]

        ts_unix = _EPOCH_START + epoch_offsets[i]
        ts_iso = datetime.fromtimestamp(ts_unix, tz=timezone.utc).isoformat()
        currency = curr_pair.split("/")[0]

        records.append({
            "uetr": str(uuid.uuid4()),
            "individual_payment_id": f"IPID-C1-{i:08d}",
            "sending_bic": _BICS[sender_idx[i]],
            "receiving_bic": _BICS[receiver_idx[i]],
            "amount_usd": round(float(amounts[i]), 2),
            "currency_pair": curr_pair,
            "currency": currency,
            "rejection_code": code,
            "rejection_class": rj_class,
            "corridor_failure_rate": corr[2],
            "timestamp_unix": ts_unix,
            "timestamp_iso": ts_iso,
            "rail": rail,
            "label": 1,  # All events are failures (RJCT)
            # EPG-12/22: is_bridgeable distinguishes failures where a bridge loan is
            # permissible (Class A/B/C) from those where it is not (BLOCK — sanctions,
            # fraud, legal halt).  C1 retraining on bridgeable-only subset requires this
            # field as the subsetting key; tau* re-optimisation (EPG-13) depends on it.
            #
            # B11-02 defense-in-depth: any code in the canonical BLOCK list is forced
            # not-bridgeable regardless of rj_class. The import-time invariant above
            # already guarantees the two views agree, but cross-checking here means a
            # future drift in either direction cannot silently mislabel the corpus.
            #
            # CBDC extension (2026-04-26): CBDC-KYC01/02 carry rj_class == "BLOCK"
            # by their dict assignment above. They normalise to the generic ISO
            # codes RR01/RR02 (already in ALL_BLOCK_CODES) at runtime via
            # cbdc_normalizer.CBDC_FAILURE_CODE_MAP. The rj_class != "BLOCK" guard
            # alone catches them; the ALL_BLOCK_CODES guard catches the post-norm
            # ISO equivalent. Both gates are checked.
            "is_bridgeable": (rj_class != "BLOCK") and (code not in ALL_BLOCK_CODES),
            "corpus_tag": _CORPUS_TAG,
            "generation_seed": seed,
            "generation_timestamp": ts,
        })

    return records


def generate_at_scale(n: int = 2_000_000, seed: int = 42) -> List[dict]:
    """Generate C1 events at prototype validation scale.

    Calls :func:`generate_payment_events` with BIS-calibrated corridor
    distributions. At n=2,000,000 this requires ~2GB RAM and ~90s on
    a modern laptop (NumPy vectorised, no Python loop for heavy computation).

    For CI/CD and demo runs, use n=50_000 or n=100_000.
    """
    return generate_payment_events(n_samples=n, seed=seed)
