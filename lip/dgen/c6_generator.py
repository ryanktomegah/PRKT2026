"""
c6_generator.py — DGEN: C6 AML Pattern Corpus Generator
=========================================================
Synthetic AML training data for the C6 Isolation Forest anomaly detector.

CIPHER decision: This corpus is NEVER committed to the repository.
It is generated fresh at training time per environment. Rationale:
  - AML typology patterns teach adversaries the model boundary
  - Even synthetic patterns reveal what "normal" looks like
  - Fully synthetic data can be regenerated deterministically (seed-controlled)

AML Pattern Typologies (FATF-aligned):
  1. NORMAL           — legitimate high-value correspondent banking (~92%)
  2. STRUCTURING      — amounts just below CTR/STR thresholds (~2.5%)
  3. VELOCITY_ABUSE   — >20 transactions in 24h from single entity (~2.5%)
  4. LAYERING         — rapid BIC-to-BIC round-trip chains (~2%)
  5. JURISDICTION     — transactions through high-risk jurisdictions (~1%)

Target: ~8% AML-flagged records overall (CIPHER calibration).
Records are labeled 0=clean, 1=flagged for Isolation Forest training.

All records tagged: corpus_tag = "SYNTHETIC_CORPUS_C6"
NOTE: This file generates training patterns — NOT sanctions screening data.
      Sanctions screening (OFAC/EU/UN) uses a separate deterministic list.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

import numpy as np

_CORPUS_TAG = "SYNTHETIC_CORPUS_C6"

# CTR/STR thresholds (CIPHER: structuring targets amounts just below these)
_CTR_THRESHOLD_USD = 10_000.0
_STR_THRESHOLD_EUR = 10_000.0

# High-risk jurisdiction codes (fictional BIC suffixes for synthetic purposes)
_HIGH_RISK_JURISDICTIONS = [
    "BANKNA00",  # fictional: non-cooperative jurisdiction A
    "FINSTXX0",  # fictional: shell jurisdiction X
    "PAYMBZ00",  # fictional: minimal oversight zone B
    "TRANSC000",  # fictional: pass-through jurisdiction C
]

_STANDARD_BICS = [
    "DEUTDEDB", "BNPAFRPP", "BARCGB22", "CITIUS33", "HSBCHKHH",
    "CHASUS33", "UBSWCHZH", "SOCGFRPP", "INGBNL2A", "NORDDKKK",
    "RBOSGB2L", "ABNAAMST", "CHASDEFX", "COMMDEFF", "DRESDEFF",
]

_CURRENCIES = ["USD", "EUR", "GBP", "CHF", "SGD", "HKD"]

_EPOCH_START = 1_688_169_600.0   # 2023-07-01 UTC
_EPOCH_SPAN  = 18 * 30 * 86400  # 18 months


# ---------------------------------------------------------------------------
# Pattern generators
# ---------------------------------------------------------------------------

def _normal_transaction(rng: np.random.Generator, entity_id: str, ts: float) -> dict:
    """Legitimate high-value correspondent banking transaction."""
    amount = float(np.exp(rng.normal(11.5, 1.8)))  # log-normal, ~$100k median
    amount = float(np.clip(amount, 1_000.0, 50_000_000.0))
    hour = int(rng.integers(7, 19))  # business hours

    return {
        "uetr": str(uuid.uuid4()),
        "entity_id": entity_id,
        "sending_bic": rng.choice(_STANDARD_BICS),
        "receiving_bic": rng.choice(_STANDARD_BICS),
        "amount_usd": amount,
        "currency": rng.choice(_CURRENCIES),
        "timestamp": ts,
        "hour_of_day": hour,
        "transactions_24h": int(rng.integers(1, 8)),
        "transactions_7d": int(rng.integers(5, 40)),
        "transactions_30d": int(rng.integers(15, 150)),
        "amount_7d_total": amount * float(rng.uniform(3.0, 10.0)),
        "amount_30d_total": amount * float(rng.uniform(10.0, 40.0)),
        "unique_counterparties_30d": int(rng.integers(2, 15)),
        "max_amount_24h": amount * float(rng.uniform(1.0, 2.5)),
        "is_round_amount": bool(rng.random() < 0.15),
        "jurisdiction_risk_score": float(rng.beta(1.5, 8)),  # mostly low risk
        "is_high_risk_jurisdiction": False,
        "round_trip_detected": False,
        "aml_flag": 0,
        "flag_reason": "clean",
        "corpus_tag": _CORPUS_TAG,
    }


def _structuring_transaction(rng: np.random.Generator, entity_id: str, ts: float) -> dict:
    """Structuring: amounts clustered just below CTR threshold."""
    # Amounts between $8,500–$9,999 (USD) or €8,500–€9,999 (EUR)
    threshold = rng.choice([_CTR_THRESHOLD_USD, _STR_THRESHOLD_EUR])
    # Cluster tightly below threshold
    amount = float(rng.uniform(threshold * 0.85, threshold * 0.999))

    # Structuring entities make many transactions per day
    txn_24h = int(rng.integers(3, 12))

    return {
        "uetr": str(uuid.uuid4()),
        "entity_id": entity_id,
        "sending_bic": rng.choice(_STANDARD_BICS),
        "receiving_bic": rng.choice(_STANDARD_BICS),
        "amount_usd": amount,
        "currency": rng.choice(["USD", "EUR"]),
        "timestamp": ts,
        "hour_of_day": int(rng.integers(9, 17)),
        "transactions_24h": txn_24h,
        "transactions_7d": int(rng.integers(15, 50)),
        "transactions_30d": int(rng.integers(40, 150)),
        "amount_7d_total": amount * txn_24h * float(rng.uniform(4.0, 7.0)),
        "amount_30d_total": amount * txn_24h * float(rng.uniform(15.0, 25.0)),
        "unique_counterparties_30d": int(rng.integers(1, 4)),  # few counterparties
        "max_amount_24h": amount * float(rng.uniform(1.0, 1.05)),  # amounts are similar
        "is_round_amount": bool(rng.random() < 0.05),  # structuring avoids round amounts
        "jurisdiction_risk_score": float(rng.beta(2, 5)),
        "is_high_risk_jurisdiction": False,
        "round_trip_detected": False,
        "aml_flag": 1,
        "flag_reason": "structuring",
        "corpus_tag": _CORPUS_TAG,
    }


def _velocity_abuse_transaction(rng: np.random.Generator, entity_id: str, ts: float) -> dict:
    """Velocity abuse: >20 transactions in 24h from single entity."""
    amount = float(np.exp(rng.normal(9.5, 1.2)))  # smaller amounts per tx
    amount = float(np.clip(amount, 500.0, 500_000.0))
    txn_24h = int(rng.integers(20, 80))  # way above normal

    return {
        "uetr": str(uuid.uuid4()),
        "entity_id": entity_id,
        "sending_bic": rng.choice(_STANDARD_BICS),
        "receiving_bic": rng.choice(_STANDARD_BICS),
        "amount_usd": amount,
        "currency": rng.choice(_CURRENCIES),
        "timestamp": ts,
        "hour_of_day": int(rng.integers(0, 24)),  # any hour — not business-hours constrained
        "transactions_24h": txn_24h,
        "transactions_7d": txn_24h * int(rng.integers(3, 7)),
        "transactions_30d": txn_24h * int(rng.integers(10, 25)),
        "amount_7d_total": amount * txn_24h * float(rng.uniform(3.0, 7.0)),
        "amount_30d_total": amount * txn_24h * float(rng.uniform(10.0, 25.0)),
        "unique_counterparties_30d": int(rng.integers(10, 50)),  # many counterparties
        "max_amount_24h": amount * float(rng.uniform(1.5, 4.0)),
        "is_round_amount": bool(rng.random() < 0.20),
        "jurisdiction_risk_score": float(rng.beta(2, 4)),
        "is_high_risk_jurisdiction": False,
        "round_trip_detected": False,
        "aml_flag": 1,
        "flag_reason": "velocity_abuse",
        "corpus_tag": _CORPUS_TAG,
    }


def _layering_transaction(rng: np.random.Generator, entity_id: str, ts: float) -> dict:
    """Layering: rapid round-trip BIC chain detected."""
    amount = float(np.exp(rng.normal(12.5, 1.0)))  # larger amounts
    amount = float(np.clip(amount, 50_000.0, 10_000_000.0))

    # Amount slightly reduced each leg (layering fees)
    amount_return = amount * float(rng.uniform(0.93, 0.99))

    return {
        "uetr": str(uuid.uuid4()),
        "entity_id": entity_id,
        "sending_bic": rng.choice(_STANDARD_BICS),
        "receiving_bic": rng.choice(_STANDARD_BICS),
        "amount_usd": amount,
        "currency": rng.choice(["USD", "EUR", "CHF"]),
        "timestamp": ts,
        "hour_of_day": int(rng.integers(8, 18)),
        "transactions_24h": int(rng.integers(2, 8)),
        "transactions_7d": int(rng.integers(8, 30)),
        "transactions_30d": int(rng.integers(20, 80)),
        "amount_7d_total": amount * float(rng.uniform(2.0, 5.0)),
        "amount_30d_total": amount * float(rng.uniform(5.0, 12.0)),
        "unique_counterparties_30d": int(rng.integers(2, 6)),
        "max_amount_24h": amount * 1.05,
        "is_round_amount": bool(rng.random() < 0.30),  # layering often uses round amounts
        "jurisdiction_risk_score": float(rng.beta(3, 4)),
        "is_high_risk_jurisdiction": bool(rng.random() < 0.40),
        "round_trip_detected": True,
        "round_trip_amount": amount_return,
        "round_trip_lag_hours": float(rng.uniform(0.5, 48.0)),
        "aml_flag": 1,
        "flag_reason": "layering",
        "corpus_tag": _CORPUS_TAG,
    }


def _high_risk_jurisdiction_transaction(rng: np.random.Generator, entity_id: str, ts: float) -> dict:
    """Transaction routed through high-risk (synthetic) jurisdiction."""
    amount = float(np.exp(rng.normal(11.0, 1.5)))
    amount = float(np.clip(amount, 5_000.0, 5_000_000.0))

    return {
        "uetr": str(uuid.uuid4()),
        "entity_id": entity_id,
        "sending_bic": rng.choice(_STANDARD_BICS),
        "receiving_bic": rng.choice(_HIGH_RISK_JURISDICTIONS),  # fictional high-risk BIC
        "amount_usd": amount,
        "currency": rng.choice(_CURRENCIES),
        "timestamp": ts,
        "hour_of_day": int(rng.integers(0, 24)),
        "transactions_24h": int(rng.integers(1, 5)),
        "transactions_7d": int(rng.integers(2, 15)),
        "transactions_30d": int(rng.integers(5, 30)),
        "amount_7d_total": amount * float(rng.uniform(1.5, 6.0)),
        "amount_30d_total": amount * float(rng.uniform(4.0, 15.0)),
        "unique_counterparties_30d": int(rng.integers(1, 5)),
        "max_amount_24h": amount * float(rng.uniform(1.0, 2.0)),
        "is_round_amount": bool(rng.random() < 0.25),
        "jurisdiction_risk_score": float(rng.beta(6, 3)),  # HIGH risk score
        "is_high_risk_jurisdiction": True,
        "round_trip_detected": False,
        "aml_flag": 1,
        "flag_reason": "high_risk_jurisdiction",
        "corpus_tag": _CORPUS_TAG,
    }


# ---------------------------------------------------------------------------
# Public API — NOT COMMITTED TO REPO (generated at training time)
# ---------------------------------------------------------------------------

def generate_aml_corpus(
    n_samples: int = 20_000,
    seed: int = 42,
) -> List[dict]:
    """Generate synthetic AML pattern corpus for Isolation Forest training.

    SECURITY NOTE: Do NOT commit the output of this function to the repository.
    Generate fresh per training environment using this function.

    Pattern distribution:
      ~92.0% NORMAL (legitimate)
      ~2.5%  STRUCTURING
      ~2.5%  VELOCITY_ABUSE
      ~2.0%  LAYERING
      ~1.0%  HIGH_RISK_JURISDICTION

    Parameters
    ----------
    n_samples : int
        Total records.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    List of dicts with AML features + aml_flag (0=clean, 1=flagged).
    """
    rng = np.random.default_rng(seed)
    ts_now = datetime.now(tz=timezone.utc).isoformat() + "Z"

    # Pattern weights
    patterns = ["normal", "structuring", "velocity", "layering", "jurisdiction"]
    weights  = [0.920,    0.025,          0.025,       0.020,      0.010]

    pattern_choices = rng.choice(patterns, size=n_samples, p=weights)
    timestamps = rng.uniform(_EPOCH_START, _EPOCH_START + _EPOCH_SPAN, size=n_samples)

    # Entity pool — small set to create entity-level velocity patterns
    n_entities = max(50, n_samples // 200)
    entity_pool = [f"ENTITY_{str(uuid.uuid4())[:8].upper()}" for _ in range(n_entities)]

    records: List[dict] = []
    for i, (pattern, ts) in enumerate(zip(pattern_choices, timestamps)):
        entity_id = rng.choice(entity_pool)

        if pattern == "normal":
            rec = _normal_transaction(rng, entity_id, ts)
        elif pattern == "structuring":
            rec = _structuring_transaction(rng, entity_id, ts)
        elif pattern == "velocity":
            rec = _velocity_abuse_transaction(rng, entity_id, ts)
        elif pattern == "layering":
            rec = _layering_transaction(rng, entity_id, ts)
        else:
            rec = _high_risk_jurisdiction_transaction(rng, entity_id, ts)

        rec["generation_seed"] = seed
        rec["generation_timestamp"] = ts_now
        records.append(rec)

    return records


def generate_at_scale(n: int = 300_000, seed: int = 42) -> List[dict]:
    """Generate C6 AML corpus at prototype validation scale.

    Calls :func:`generate_aml_corpus` with FATF-aligned typology patterns.
    CIPHER rule: output must NOT be committed to the repository — generate
    fresh per training environment.

    For CI/CD and demo runs, use n=5_000 or n=20_000.
    """
    return generate_aml_corpus(n_samples=n, seed=seed)
