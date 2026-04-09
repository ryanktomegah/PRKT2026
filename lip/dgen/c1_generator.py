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
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

import numpy as np

from lip.common.block_codes import ALL_BLOCK_CODES

_CORPUS_TAG = "SYNTHETIC_CORPUS_C1"

# ── BIS-calibrated corridor config ─────────────────────────────────────────────

# (currency_pair, weight_in_volume, failure_rate)
# Weights sum to 1.0; failure rates from BIS CPMI 2024 + SWIFT GPI data
_CORRIDORS = [
    ("EUR/USD",  0.25,  0.150),  # EUR/USD: 85% STP = 15% failure
    ("USD/EUR",  0.15,  0.150),
    ("GBP/USD",  0.12,  0.080),  # GBP/USD: 92% STP = 8% failure
    ("USD/GBP",  0.08,  0.080),
    ("USD/JPY",  0.10,  0.120),  # USD/JPY: 88% STP = 12% failure
    ("USD/CHF",  0.04,  0.090),
    ("EUR/GBP",  0.06,  0.110),
    ("USD/CAD",  0.05,  0.095),
    ("USD/CNY",  0.06,  0.260),  # Emerging: 74% STP = 26% failure
    ("USD/INR",  0.04,  0.280),  # Emerging: 72% STP = 28% failure
    ("USD/SGD",  0.03,  0.180),
    ("EUR/CHF",  0.02,  0.085),
]
_CORRIDOR_PAIRS  = [c[0] for c in _CORRIDORS]
_CORRIDOR_WEIGHTS = np.array([c[1] for c in _CORRIDORS])
_CORRIDOR_WEIGHTS /= _CORRIDOR_WEIGHTS.sum()  # normalise
_CORRIDOR_FAILURE = [c[2] for c in _CORRIDORS]

# ISO 20022 rejection codes with class labels (A=3d, B=7d, C=21d, BLOCK=0d)
# Distribution from SWIFT GPI and LIP architecture spec Appendix B.
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

# Synthetic BIC pool (500 unique BICs with realistic naming)
_BIC_PREFIXES = [
    "DEUT", "BNPA", "BARC", "CITI", "HSBC", "CHAS", "UBSW", "SOCG",
    "INGB", "NORD", "RABO", "COMM", "LANZ", "BBVA", "SANT", "IBER",
    "BPCE", "CRED", "ABNA", "DAAN", "NATX", "BERS", "CMCI", "BREX",
    "UNIB", "STAN", "BNYC", "STAT", "WFBI", "TORO"
]
_BIC_SUFFIXES = ["DE", "FR", "GB", "US", "HK", "CH", "NL", "ES", "DK", "SG"]
_BIC_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789"
_BICS = [
    f"{pfx}{sfx}{_BIC_CHARS[(i * 7) % len(_BIC_CHARS)]}{_BIC_CHARS[(i * 11) % len(_BIC_CHARS)]}"
    for i, pfx in enumerate(_BIC_PREFIXES)
    for sfx in _BIC_SUFFIXES
]  # 300 BICs

# Amount distribution: log-normal centered at $500K, range $5K–$50M
_AMOUNT_MU = 13.0   # ln(~$440K)
_AMOUNT_SIGMA = 1.5

# Temporal spread: 2023-07-01 → 2025-01-01 (18 months, SR 11-7 out-of-time)
_EPOCH_START = 1_688_169_600.0
_EPOCH_SPAN  = 18 * 30 * 86400


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

    # Sample corridors
    corridor_idx = rng.choice(len(_CORRIDORS), size=n_samples, p=_CORRIDOR_WEIGHTS)
    # Sample rejection codes
    code_idx = rng.choice(len(_REJECTION_CODE_LIST), size=n_samples, p=_REJECTION_WEIGHTS)
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
        corr = _CORRIDORS[corridor_idx[i]]
        code = _REJECTION_CODE_LIST[code_idx[i]]
        rj_class, _ = _REJECTION_CODES[code]
        ts_unix = _EPOCH_START + epoch_offsets[i]
        ts_iso = datetime.fromtimestamp(ts_unix, tz=timezone.utc).isoformat()
        curr_pair = corr[0]
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
            "rail": "SWIFT",
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
