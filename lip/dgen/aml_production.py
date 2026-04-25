"""
aml_production.py — DGEN: Production AML Synthetic Dataset (Step 3)
====================================================================
Generates `aml_synthetic.parquet` for C6 AML Velocity Module training.

Pattern distribution (FATF-aligned, targets 2.8% overall AML flag rate):
  CLEAN              ~97.2%  — legitimate correspondent banking
  STRUCTURING         ~1.2%  — amounts clustered just below the reporting threshold
  VELOCITY            ~1.1%  — entity transaction count 3–5x above corridor baseline
  SANCTIONS_ADJACENT  ~0.5%  — BIC pair involves a pre-flagged sanctions-adjacent institution

Output schema (parquet):
  uetr               str     — UUID v4 unique identifier
  entity_id          str     — pseudonymous entity identifier
  bic_sender         str     — fictional 8-char BIC
  bic_receiver       str     — fictional 8-char BIC
  amount_usd         float   — transaction amount in USD
  currency           str     — ISO 4217 currency code
  timestamp_utc      str     — ISO 8601 UTC timestamp
  transactions_24h   int     — entity transaction count in 24h window
  transactions_7d    int     — entity transaction count in 7d window
  transactions_30d   int     — entity transaction count in 30d window
  amount_7d_total    float   — entity total USD amount in 7d window
  amount_30d_total   float   — entity total USD amount in 30d window
  unique_counterparties_30d  int   — distinct counterparties in 30d
  max_amount_24h     float   — max single transaction in 24h
  is_round_amount    bool    — True if amount is a round number
  jurisdiction_risk_score float — 0.0–1.0 (higher = riskier)
  is_high_risk_jurisdiction bool
  round_trip_detected bool
  aml_flag           int     — 0=clean, 1=flagged
  aml_type           str     — CLEAN | STRUCTURING | VELOCITY | SANCTIONS_ADJACENT
  corpus_tag         str     — "SYNTHETIC_CORPUS_AML_PROD"

SECURITY NOTE: Do NOT commit the output of this module to the repository.
               Generate fresh per training environment.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import numpy as np

_CORPUS_TAG = "SYNTHETIC_CORPUS_AML_PROD"

# B11-04 CIPHER: AML detection threshold MUST NOT be hardcoded in source.
# Load from environment at generation time. Raises ValueError if unset.
def _load_ctr_threshold() -> float:
    """Load CTR/STR threshold from environment. Raises ValueError if unset."""
    raw = os.environ.get("AML_THRESHOLD_CTR_USD")
    if raw is None:
        raise ValueError(
            "AML_THRESHOLD_CTR_USD environment variable is not set. "
            "Set it before generating the AML production corpus. "
            "Never hardcode threshold values in source (CIPHER rule)."
        )
    return float(raw)

# 18-month temporal range (2023-07-01 → 2025-01-01) for SR 11-7 OOT support
_EPOCH_START = 1_688_169_600.0
_EPOCH_SPAN = 18 * 30 * 86_400

# Standard correspondent bank BICs (fictional, from bic_pool module)
_STANDARD_BICS = [
    "XCAPUS33", "GLOBDE2X", "PONTFR1P", "BRITGB2L", "PACIHK2X",
    "ASICSG1X", "ALPICH2A", "NORTNL2A", "FUIJJP2T", "SINOCN2H",
    "FSTBUS1X", "NTLBDE1X", "CMRBFR1X", "REGBGB1X", "TRSBJP1X",
    "CNTBSG1X", "UNIBHK1X", "CORPNL1X", "CREDFR1X", "SAVBDE1X",
]

# Pre-flagged sanctions-adjacent BICs (fictional — these are NOT real sanctions designations)
_SANCTIONS_ADJACENT_BICS = [
    "RSKBXX1X",  # fictional: flagged jurisdiction A
    "SHLLBX2X",  # fictional: shell entity hub B
    "RISKXX3X",  # fictional: watch-list adjacent C
    "FRSTBX4X",  # fictional: correspondent with restricted access D
    "HRBRBX5X",  # fictional: harbour jurisdiction E
]

_CURRENCIES = ["USD", "EUR", "GBP", "CHF", "SGD", "HKD", "JPY", "CAD"]

# Corridor baselines for velocity detection (normal tx/day per entity per corridor)
_CORRIDOR_BASELINE_TX_24H = {
    "USD/EUR": 8, "EUR/USD": 8, "GBP/USD": 6, "USD/JPY": 6,
    "USD/CHF": 5, "USD/CAD": 5, "USD/SGD": 4, "default": 5,
}


def _baseline_tx_24h(currency: str) -> int:
    key = f"USD/{currency}" if currency != "USD" else "USD/EUR"
    return _CORRIDOR_BASELINE_TX_24H.get(key, _CORRIDOR_BASELINE_TX_24H["default"])


# ---------------------------------------------------------------------------
# Pattern record builders
# ---------------------------------------------------------------------------


def _clean_record(
    rng: np.random.Generator, entity_id: str, ts: float, gen_ts: str
) -> dict[str, Any]:
    """Legitimate high-value correspondent banking transaction."""
    amount = float(np.clip(np.exp(rng.normal(11.5, 1.8)), 1_000.0, 50_000_000.0))
    currency = str(rng.choice(_CURRENCIES))
    baseline = _baseline_tx_24h(currency)

    return {
        "uetr": str(uuid.uuid4()),
        "entity_id": entity_id,
        "bic_sender": str(rng.choice(_STANDARD_BICS)),
        "bic_receiver": str(rng.choice(_STANDARD_BICS)),
        "amount_usd": round(amount, 2),
        "currency": currency,
        "timestamp_utc": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
        "transactions_24h": int(rng.integers(1, baseline + 2)),
        "transactions_7d": int(rng.integers(5, baseline * 7 + 5)),
        "transactions_30d": int(rng.integers(15, baseline * 30 + 10)),
        "amount_7d_total": round(amount * float(rng.uniform(3.0, 10.0)), 2),
        "amount_30d_total": round(amount * float(rng.uniform(10.0, 40.0)), 2),
        "unique_counterparties_30d": int(rng.integers(2, 15)),
        "max_amount_24h": round(amount * float(rng.uniform(1.0, 2.5)), 2),
        "is_round_amount": bool(rng.random() < 0.15),
        "jurisdiction_risk_score": float(rng.beta(1.5, 8)),
        "is_high_risk_jurisdiction": False,
        "round_trip_detected": False,
        "aml_flag": 0,
        "aml_type": "CLEAN",
        "corpus_tag": _CORPUS_TAG,
        "generation_timestamp": gen_ts,
    }


def _structuring_record(
    rng: np.random.Generator,
    entity_id: str,
    ts: float,
    gen_ts: str,
    ctr_threshold: float,
) -> dict[str, Any]:
    """Structuring: amounts clustered just below the reporting threshold.

    Parameters
    ----------
    ctr_threshold:
        Loaded from AML_THRESHOLD_CTR_USD environment variable at generation time.
        Never hardcoded in source (B11-04 CIPHER rule).

    Characteristics:
    - Amount tightly below reporting threshold (85–99.9% of threshold)
    - Many transactions per day from same entity
    - Few unique counterparties (structuring is repetitive)
    - Low round-number rate (intentional to avoid detection)
    """
    amount = float(rng.uniform(ctr_threshold * 0.85, ctr_threshold * 0.999))
    txn_24h = int(rng.integers(4, 15))  # high frequency, below threshold repetition

    return {
        "uetr": str(uuid.uuid4()),
        "entity_id": entity_id,
        "bic_sender": str(rng.choice(_STANDARD_BICS)),
        "bic_receiver": str(rng.choice(_STANDARD_BICS)),
        "amount_usd": round(amount, 2),
        "currency": str(rng.choice(["USD", "EUR"])),
        "timestamp_utc": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
        "transactions_24h": txn_24h,
        "transactions_7d": int(rng.integers(20, txn_24h * 7 + 5)),
        "transactions_30d": int(rng.integers(50, txn_24h * 25 + 10)),
        "amount_7d_total": round(amount * txn_24h * float(rng.uniform(4.0, 7.0)), 2),
        "amount_30d_total": round(amount * txn_24h * float(rng.uniform(15.0, 25.0)), 2),
        "unique_counterparties_30d": int(rng.integers(1, 4)),  # few counterparties
        "max_amount_24h": round(amount * float(rng.uniform(1.0, 1.04)), 2),  # all similar
        "is_round_amount": bool(rng.random() < 0.05),  # deliberately avoids round amounts
        "jurisdiction_risk_score": float(rng.beta(2, 5)),
        "is_high_risk_jurisdiction": False,
        "round_trip_detected": False,
        "aml_flag": 1,
        "aml_type": "STRUCTURING",
        "corpus_tag": _CORPUS_TAG,
        "generation_timestamp": gen_ts,
    }


def _velocity_record(
    rng: np.random.Generator, entity_id: str, ts: float, gen_ts: str
) -> dict[str, Any]:
    """Velocity anomaly: entity transaction count 3–5x above corridor baseline.

    Characteristics:
    - High transactions_24h (3–5x above baseline)
    - Many unique counterparties (not structuring — different entities each time)
    - Smaller amounts per transaction (velocity ≠ large single amounts)
    """
    currency = str(rng.choice(_CURRENCIES))
    baseline = _baseline_tx_24h(currency)
    multiplier = float(rng.uniform(3.0, 5.0))
    txn_24h = int(baseline * multiplier)
    amount = float(np.clip(np.exp(rng.normal(9.5, 1.2)), 500.0, 500_000.0))

    return {
        "uetr": str(uuid.uuid4()),
        "entity_id": entity_id,
        "bic_sender": str(rng.choice(_STANDARD_BICS)),
        "bic_receiver": str(rng.choice(_STANDARD_BICS)),
        "amount_usd": round(amount, 2),
        "currency": currency,
        "timestamp_utc": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
        "transactions_24h": txn_24h,
        "transactions_7d": txn_24h * int(rng.integers(3, 7)),
        "transactions_30d": txn_24h * int(rng.integers(10, 25)),
        "amount_7d_total": round(amount * txn_24h * float(rng.uniform(3.0, 7.0)), 2),
        "amount_30d_total": round(amount * txn_24h * float(rng.uniform(10.0, 25.0)), 2),
        "unique_counterparties_30d": int(rng.integers(15, 60)),  # many counterparties
        "max_amount_24h": round(amount * float(rng.uniform(1.5, 4.0)), 2),
        "is_round_amount": bool(rng.random() < 0.20),
        "jurisdiction_risk_score": float(rng.beta(2, 4)),
        "is_high_risk_jurisdiction": False,
        "round_trip_detected": False,
        "aml_flag": 1,
        "aml_type": "VELOCITY",
        "corpus_tag": _CORPUS_TAG,
        "generation_timestamp": gen_ts,
    }


def _sanctions_adjacent_record(
    rng: np.random.Generator, entity_id: str, ts: float, gen_ts: str
) -> dict[str, Any]:
    """Sanctions-adjacent: BIC pair involves a pre-flagged institution.

    ~0.1% of BIC pairs in the pool are flagged as sanctions-adjacent.
    Characteristics:
    - One party is a fictional sanctions-adjacent institution
    - Otherwise normal-looking transaction (amounts/velocity not anomalous)
    - High jurisdiction risk score
    """
    amount = float(np.clip(np.exp(rng.normal(11.0, 1.5)), 5_000.0, 5_000_000.0))
    # One of sender/receiver is the flagged entity
    if rng.random() < 0.5:
        bic_sender = str(rng.choice(_SANCTIONS_ADJACENT_BICS))
        bic_receiver = str(rng.choice(_STANDARD_BICS))
    else:
        bic_sender = str(rng.choice(_STANDARD_BICS))
        bic_receiver = str(rng.choice(_SANCTIONS_ADJACENT_BICS))
    currency = str(rng.choice(_CURRENCIES))
    baseline = _baseline_tx_24h(currency)

    return {
        "uetr": str(uuid.uuid4()),
        "entity_id": entity_id,
        "bic_sender": bic_sender,
        "bic_receiver": bic_receiver,
        "amount_usd": round(amount, 2),
        "currency": currency,
        "timestamp_utc": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
        "transactions_24h": int(rng.integers(1, baseline + 2)),  # looks normal
        "transactions_7d": int(rng.integers(3, baseline * 7 + 5)),
        "transactions_30d": int(rng.integers(8, baseline * 30 + 5)),
        "amount_7d_total": round(amount * float(rng.uniform(2.0, 7.0)), 2),
        "amount_30d_total": round(amount * float(rng.uniform(5.0, 15.0)), 2),
        "unique_counterparties_30d": int(rng.integers(1, 5)),
        "max_amount_24h": round(amount * float(rng.uniform(1.0, 2.0)), 2),
        "is_round_amount": bool(rng.random() < 0.25),
        "jurisdiction_risk_score": float(rng.beta(6, 3)),  # high risk
        "is_high_risk_jurisdiction": True,
        "round_trip_detected": False,
        "aml_flag": 1,
        "aml_type": "SANCTIONS_ADJACENT",
        "corpus_tag": _CORPUS_TAG,
        "generation_timestamp": gen_ts,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_aml_dataset(
    n_samples: int = 100_000,
    seed: int = 42,
) -> "list[dict[str, Any]]":
    """Generate production AML synthetic dataset as a list of dicts.

    Pattern distribution targets overall AML flag rate of ~2.8%:
      CLEAN              ~97.2%  (legitimate correspondent banking)
      STRUCTURING         ~1.2%  (below-threshold clustering)
      VELOCITY            ~1.1%  (3–5x baseline transaction rate)
      SANCTIONS_ADJACENT  ~0.5%  (sanctions-adjacent BIC pair)

    Parameters
    ----------
    n_samples : int
        Total records to generate.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    list[dict]
        Records with all required fields including aml_flag and aml_type.
    """
    # B11-04 CIPHER: Load threshold from environment — raises ValueError if unset.
    ctr_threshold = _load_ctr_threshold()

    rng = np.random.default_rng(seed)
    gen_ts = datetime.now(tz=timezone.utc).isoformat() + "Z"

    patterns = ["clean", "structuring", "velocity", "sanctions_adjacent"]
    weights = [0.972, 0.012, 0.011, 0.005]
    pattern_choices = rng.choice(patterns, size=n_samples, p=weights)
    timestamps = rng.uniform(_EPOCH_START, _EPOCH_START + _EPOCH_SPAN, size=n_samples)

    # Entity pool: small enough to create intra-entity velocity patterns
    n_entities = max(100, n_samples // 200)
    entity_pool = [f"ENT_{str(uuid.uuid4())[:8].upper()}" for _ in range(n_entities)]

    records: list[dict[str, Any]] = []
    for i in range(n_samples):
        entity_id = str(rng.choice(entity_pool))
        ts = float(timestamps[i])
        pattern = str(pattern_choices[i])

        if pattern == "clean":
            rec = _clean_record(rng, entity_id, ts, gen_ts)
        elif pattern == "structuring":
            rec = _structuring_record(rng, entity_id, ts, gen_ts, ctr_threshold)
        elif pattern == "velocity":
            rec = _velocity_record(rng, entity_id, ts, gen_ts)
        else:
            rec = _sanctions_adjacent_record(rng, entity_id, ts, gen_ts)

        records.append(rec)

    return records
