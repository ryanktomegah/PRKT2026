"""
synthetic_data.py — Synthetic PD training data generator for C2
C2 Spec Section 3: Three-tier framework with realistic borrower financials

Generates {label, payment, borrower} records in the format expected by
PDTrainingPipeline.run().  Records are stratified across tiers:
  ~40% Tier 1 — full financial statements + credit bureau (24+ months history)
  ~35% Tier 2 — transaction history only (6+ months)
  ~25% Tier 3 — thin-file (minimal data)

Default rate: ~5% overall (realistic for institutional bridge lending).
  Tier 1: ~3%  (well-documented borrowers, lower PD)
  Tier 2: ~6%  (transaction-based, moderate risk)
  Tier 3: ~12% (thin-file, highest uncertainty / PD)

All records are explicitly tagged: corpus_tag = "SYNTHETIC_CORPUS_C2"
"""
from __future__ import annotations

import uuid
from typing import List

import numpy as np


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CORPUS_TAG = "SYNTHETIC_CORPUS_C2"

_DEFAULT_RATE_TIER1 = 0.03
_DEFAULT_RATE_TIER2 = 0.06
_DEFAULT_RATE_TIER3 = 0.12

_TIER_WEIGHTS = [0.40, 0.35, 0.25]  # Tier 1 / Tier 2 / Tier 3

_CURRENCIES = ["USD/EUR", "USD/GBP", "EUR/GBP", "USD/JPY", "USD/CAD",
               "USD/CHF", "EUR/CHF", "USD/SGD", "USD/HKD", "USD/AUD"]

_BICS = [
    "DEUTDEDB", "BNPAFRPP", "BARCGB22", "CITIUS33", "HSBCHKHH",
    "CHASUS33", "UBSWCHZH", "SOCGFRPP", "INGBNL2A", "NORDDKKK",
]

# Tier-1 borrower: full financial data
# Has: financial_statements, altman_z_score, merton_distance_to_default, credit_bureau, industry_risk_score
# Tier-2 borrower: transaction history only
# Tier-3 borrower: thin-file, minimal data available


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _uuid() -> str:
    return str(uuid.uuid4())


def _clip(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _gen_payment(rng: np.random.Generator, idx: int) -> dict:
    """Generate a synthetic payment dict compatible with UnifiedFeatureEngineer."""
    bic_s = rng.choice(_BICS)
    bic_r = rng.choice([b for b in _BICS if b != bic_s])
    currency_pair = rng.choice(_CURRENCIES)
    amount_usd = float(np.exp(rng.normal(12.0, 1.5)))  # log-normal ~$160k median
    amount_usd = _clip(amount_usd, 5_000.0, 20_000_000.0)
    hour_of_day = int(rng.integers(0, 24))
    day_of_week = int(rng.integers(0, 7))

    # Synthetic timestamp
    _BASE_TS = 1_700_000_000.0
    timestamp = _BASE_TS + day_of_week * 86400 + hour_of_day * 3600 + idx

    return {
        "uetr": _uuid(),
        "sending_bic": bic_s,
        "receiving_bic": bic_r,
        "currency_pair": currency_pair,
        "amount_usd": amount_usd,
        "timestamp": timestamp,
        "hour_of_day": hour_of_day,
        "day_of_week": day_of_week,
        "days_since_last_payment": float(rng.integers(1, 30)),
        "corridor_failure_rate": float(rng.beta(1.5, 30)),
        "corridor_volume_7d": float(rng.lognormal(15.0, 1.0)),
        "n_payments_30d": int(rng.integers(1, 50)),
        "n_failures_30d": int(rng.integers(0, 5)),
        "amount_zscore": float(rng.normal(0, 1)),
        "amount_percentile": float(rng.uniform(0, 1)),
        "payment_velocity_24h": float(rng.integers(0, 20)),
        "large_amount_threshold": 1_000_000.0,
        "currency_risk_score": float(rng.beta(2, 5)),
        "corpus_tag": _CORPUS_TAG,
    }


def _gen_tier1_borrower(rng: np.random.Generator, default_label: int) -> dict:
    """Generate a Tier-1 borrower with full financial statements + credit bureau."""
    # Healthy borrowers (label=0) get better financials on average
    z_mean = 3.5 if default_label == 0 else 1.2  # Altman Z: safe>2.99, distress<1.81
    merton_mean = 3.0 if default_label == 0 else 0.8

    current_ratio = _clip(float(rng.normal(2.0 if default_label == 0 else 1.0, 0.4)), 0.1, 10.0)
    dte = _clip(float(rng.lognormal(0.5 if default_label == 0 else 1.5, 0.5)), 0.0, 20.0)
    interest_cov = _clip(float(rng.normal(8.0 if default_label == 0 else 1.5, 2.0)), -5.0, 50.0)
    roe = _clip(float(rng.normal(0.15 if default_label == 0 else -0.05, 0.08)), -0.5, 0.8)
    roa = _clip(float(rng.normal(0.08 if default_label == 0 else -0.02, 0.04)), -0.3, 0.4)
    ebitda_margin = _clip(float(rng.normal(0.20 if default_label == 0 else 0.02, 0.07)), -0.2, 0.8)
    revenue_growth = float(rng.normal(0.08 if default_label == 0 else -0.05, 0.10))
    cash_ratio = _clip(float(rng.normal(0.4 if default_label == 0 else 0.1, 0.15)), 0.0, 3.0)
    asset_turnover = _clip(float(rng.normal(1.2 if default_label == 0 else 0.6, 0.3)), 0.1, 5.0)
    net_margin = _clip(float(rng.normal(0.10 if default_label == 0 else -0.03, 0.05)), -0.5, 0.6)

    altman_z = _clip(float(rng.normal(z_mean, 0.8)), -2.0, 8.0)
    merton_dd = _clip(float(rng.normal(merton_mean, 0.6)), -2.0, 8.0)

    cb_score = int(_clip(rng.normal(720 if default_label == 0 else 560, 50), 300, 850))
    cb_age_months = int(rng.integers(24, 120))
    ph_score = _clip(float(rng.normal(0.85 if default_label == 0 else 0.45, 0.1)), 0.0, 1.0)
    avg_days_to_pay = _clip(float(rng.normal(28 if default_label == 0 else 55, 10)), 1.0, 120.0)
    delinquency_rate = _clip(float(rng.beta(1 if default_label == 0 else 3, 15)), 0.0, 0.5)
    default_count = int(rng.choice([0, 0, 0, 1, 2], p=[0.85, 0.07, 0.05, 0.02, 0.01]))
    bankruptcy = bool(rng.choice([False, False, False, False, True], p=[0.90, 0.05, 0.02, 0.02, 0.01]))
    industry_risk = _clip(float(rng.beta(2, 5 if default_label == 0 else 2)), 0.0, 1.0)

    return {
        "has_financial_statements": True,
        "has_transaction_history": True,
        "has_credit_bureau": True,
        "months_history": int(rng.integers(24, 120)),
        "transaction_count": int(rng.integers(100, 1000)),
        "counterparty_age_days": int(rng.integers(365, 3650)),
        "financial_statements": {
            "current_ratio": current_ratio,
            "debt_to_equity": dte,
            "interest_coverage": interest_cov,
            "roe": roe,
            "roa": roa,
            "ebitda_margin": ebitda_margin,
            "revenue_growth": revenue_growth,
            "cash_ratio": cash_ratio,
            "asset_turnover": asset_turnover,
            "net_margin": net_margin,
        },
        "altman_z_score": altman_z,
        "merton_distance_to_default": merton_dd,
        "credit_bureau": {
            "score": cb_score,
            "age_months": cb_age_months,
            "payment_history_score": ph_score,
            "avg_days_to_pay": avg_days_to_pay,
            "delinquency_rate": delinquency_rate,
            "default_history_count": default_count,
            "bankruptcy_history": bankruptcy,
        },
        "industry_risk_score": industry_risk,
        "corpus_tag": _CORPUS_TAG,
    }


def _gen_tier2_borrower(rng: np.random.Generator, default_label: int) -> dict:
    """Generate a Tier-2 borrower with transaction history only."""
    avg_pmt = float(np.exp(rng.normal(11.5, 1.2)))
    pmt_std = avg_pmt * float(rng.uniform(0.1, 0.6))
    freq = _clip(float(rng.normal(15 if default_label == 0 else 8, 5)), 1.0, 60.0)
    trend = float(rng.normal(0.02 if default_label == 0 else -0.05, 0.03))

    return {
        "has_financial_statements": False,
        "has_transaction_history": True,
        "has_credit_bureau": False,
        "months_history": int(rng.integers(6, 24)),
        "transaction_count": int(rng.integers(12, 100)),
        "counterparty_age_days": int(rng.integers(180, 1800)),
        "transaction_history": {
            "avg_payment_amount": avg_pmt,
            "payment_amount_std": pmt_std,
            "payment_frequency": freq,
            "recent_trend_slope": trend,
            "largest_payment_30d": avg_pmt * float(rng.uniform(1.5, 4.0)),
            "smallest_payment_30d": avg_pmt * float(rng.uniform(0.1, 0.5)),
            "payment_gap_max_days": float(rng.integers(5, 45)),
            "payment_gap_mean_days": float(rng.integers(1, 15)),
            "counterparty_diversity": _clip(float(rng.beta(2, 3)), 0.0, 1.0),
            "payment_regularity_score": _clip(float(rng.normal(0.70 if default_label == 0 else 0.40, 0.15)), 0.0, 1.0),
        },
        "corpus_tag": _CORPUS_TAG,
    }


def _gen_tier3_borrower(rng: np.random.Generator) -> dict:
    """Generate a Tier-3 thin-file borrower."""
    return {
        "has_financial_statements": False,
        "has_transaction_history": False,
        "has_credit_bureau": False,
        "months_history": int(rng.integers(0, 6)),
        "transaction_count": int(rng.integers(0, 12)),
        "counterparty_age_days": int(rng.integers(30, 365)),
        "jurisdiction_risk_score": float(rng.beta(2, 4)),
        "entity_age_days": float(rng.integers(30, 730)),
        "corpus_tag": _CORPUS_TAG,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_pd_training_data(
    n_samples: int = 1000,
    seed: int = 42,
) -> List[dict]:
    """Generate synthetic PD training records for PDTrainingPipeline.run().

    Each record has the format::

        {
            "label":    int,   # 1 = default, 0 = no-default
            "payment":  dict,  # payment-level dict for UnifiedFeatureEngineer
            "borrower": dict,  # borrower-level dict for UnifiedFeatureEngineer
        }

    Parameters
    ----------
    n_samples:
        Total number of records to generate.
    seed:
        Random seed for reproducibility.

    Returns
    -------
    list of dict
        Training records in {label, payment, borrower} format.
    """
    rng = np.random.default_rng(seed)

    # Sample tier assignments up front
    tier_choices = rng.choice([1, 2, 3], size=n_samples, p=_TIER_WEIGHTS)

    default_rates = {1: _DEFAULT_RATE_TIER1, 2: _DEFAULT_RATE_TIER2, 3: _DEFAULT_RATE_TIER3}

    records: List[dict] = []
    for i, tier in enumerate(tier_choices):
        dr = default_rates[tier]
        label = int(rng.random() < dr)

        payment = _gen_payment(rng, i)

        if tier == 1:
            borrower = _gen_tier1_borrower(rng, label)
        elif tier == 2:
            borrower = _gen_tier2_borrower(rng, label)
        else:
            borrower = _gen_tier3_borrower(rng)
            # Thin-file defaults are driven by payment-level signals; bump if high corridor risk
            if payment["corridor_failure_rate"] > 0.08:
                label = int(rng.random() < _DEFAULT_RATE_TIER3 * 1.5)

        records.append({"label": label, "payment": payment, "borrower": borrower})

    return records
