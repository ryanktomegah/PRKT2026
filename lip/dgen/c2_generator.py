"""
c2_generator.py — DGEN: C2 PD Model Enhanced Data Generator
=============================================================
Replaces c2_pd_model/synthetic_data.py with QUANT-validated correlated financials.

Key improvement over v1 (QUANT finding):
  v1 drew all financial ratios INDEPENDENTLY → phantom correlations.
  Real borrowers have CORRELATED financials (high DTE → low interest coverage).
  This version uses a multivariate normal with a domain-calibrated covariance
  matrix, then clips to realistic bounds.

Altman Z-score is DERIVED from the financial features (not independently drawn):
  Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
  Where:
    X1 = working_capital / total_assets  ≈ f(current_ratio)
    X2 = retained_earnings / total_assets ≈ f(ROA * age)
    X3 = EBIT / total_assets              ≈ f(EBITDA margin)
    X4 = market_cap / total_debt          ≈ 1 / debt_to_equity
    X5 = revenue / total_assets           ≈ asset_turnover

REX: All records tagged SYNTHETIC_CORPUS_C2 with temporal structure
     (18-month spread) to enable SR 11-7 out-of-time validation splits.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

import numpy as np

from lip.common.constants import DGEN_EPOCH_SPAN, DGEN_EPOCH_START
from lip.dgen.bic_pool import BICPool

_CORPUS_TAG = "SYNTHETIC_CORPUS_C2_V2"

_DEFAULT_RATE_TIER1 = 0.03
_DEFAULT_RATE_TIER2 = 0.06
_DEFAULT_RATE_TIER3 = 0.12

_TIER_WEIGHTS = [0.40, 0.35, 0.25]

_CURRENCIES = [
    "USD/EUR", "USD/GBP", "EUR/GBP", "USD/JPY", "USD/CAD",
    "USD/CHF", "EUR/CHF", "USD/SGD", "USD/HKD", "USD/AUD",
]

# B11-11: Use canonical BIC pool from bic_pool.py instead of inline list.
_BIC_POOL = BICPool()
_BICS = _BIC_POOL.all_bics  # 200 BICs (hub + spoke), ISO 9362-compliant

# B11-06: Base epoch imported from lip.common.constants (DGEN_EPOCH_START /
# DGEN_EPOCH_SPAN) — 2023-07-01 → 2025-01-01, 18 months, SR 11-7 out-of-time.
_EPOCH_START = DGEN_EPOCH_START
_EPOCH_SPAN  = DGEN_EPOCH_SPAN


# ---------------------------------------------------------------------------
# QUANT: Correlated financial ratio generator
# ---------------------------------------------------------------------------

# Feature order for the covariance matrix (Tier-1 only):
#   0: current_ratio       (higher = safer)
#   1: debt_to_equity      (lower = safer)
#   2: interest_coverage   (higher = safer)
#   3: roe                 (higher = safer)
#   4: roa                 (higher = safer)
#   5: ebitda_margin       (higher = safer)
#   6: revenue_growth      (positive = safer)
#   7: cash_ratio          (higher = safer)
#   8: asset_turnover      (higher = safer)
#   9: net_margin          (higher = safer)

# Healthy borrower (label=0) mean vector
_MU_HEALTHY = np.array([2.0, 0.6, 8.0, 0.15, 0.08, 0.20, 0.08, 0.40, 1.2, 0.10])
# Defaulting borrower (label=1) mean vector
_MU_DEFAULT = np.array([0.9, 2.5, 1.5, -0.05, -0.02, 0.02, -0.05, 0.10, 0.6, -0.03])

# Domain-calibrated correlation matrix (QUANT)
# Key relationships:
#   current_ratio ↔ cash_ratio:        +0.72
#   debt_to_equity ↔ interest_coverage: -0.65
#   roe ↔ roa:                         +0.80
#   ebitda_margin ↔ net_margin:        +0.75
#   debt_to_equity ↔ roa:              -0.55
_CORR = np.array([
    # cr     dte    icov   roe    roa    ebitda  rev_g  cash   at     nm
    [ 1.00, -0.45,  0.40,  0.30,  0.35,  0.25,  0.10,  0.72,  0.15,  0.28],  # current_ratio
    [-0.45,  1.00, -0.65, -0.50, -0.55, -0.40, -0.20, -0.38, -0.10, -0.48],  # debt_to_equity
    [ 0.40, -0.65,  1.00,  0.45,  0.50,  0.55,  0.15,  0.30,  0.20,  0.52],  # interest_coverage
    [ 0.30, -0.50,  0.45,  1.00,  0.80,  0.65,  0.35,  0.25,  0.30,  0.70],  # roe
    [ 0.35, -0.55,  0.50,  0.80,  1.00,  0.60,  0.25,  0.30,  0.35,  0.75],  # roa
    [ 0.25, -0.40,  0.55,  0.65,  0.60,  1.00,  0.30,  0.20,  0.15,  0.75],  # ebitda_margin
    [ 0.10, -0.20,  0.15,  0.35,  0.25,  0.30,  1.00,  0.10,  0.20,  0.28],  # revenue_growth
    [ 0.72, -0.38,  0.30,  0.25,  0.30,  0.20,  0.10,  1.00,  0.10,  0.22],  # cash_ratio
    [ 0.15, -0.10,  0.20,  0.30,  0.35,  0.15,  0.20,  0.10,  1.00,  0.20],  # asset_turnover
    [ 0.28, -0.48,  0.52,  0.70,  0.75,  0.75,  0.28,  0.22,  0.20,  1.00],  # net_margin
])

# Standard deviations for each feature
_STD_HEALTHY = np.array([0.40, 0.50, 2.0,  0.08, 0.04, 0.07, 0.10, 0.15, 0.30, 0.05])
_STD_DEFAULT = np.array([0.35, 1.20, 1.5,  0.10, 0.05, 0.08, 0.12, 0.12, 0.25, 0.06])


def _make_cov(std: np.ndarray) -> np.ndarray:
    """Convert correlation matrix + std vector to covariance matrix."""
    D = np.diag(std)
    return D @ _CORR @ D


_COV_HEALTHY = _make_cov(_STD_HEALTHY)
_COV_DEFAULT = _make_cov(_STD_DEFAULT)

# Clip bounds [lo, hi] per feature
_CLIP_BOUNDS = [
    (0.1, 10.0),   # current_ratio
    (0.0, 20.0),   # debt_to_equity
    (-5.0, 50.0),  # interest_coverage
    (-0.5, 0.8),   # roe
    (-0.3, 0.4),   # roa
    (-0.2, 0.8),   # ebitda_margin
    (-0.3, 0.5),   # revenue_growth
    (0.0, 3.0),    # cash_ratio
    (0.1, 5.0),    # asset_turnover
    (-0.5, 0.6),   # net_margin
]


def _derive_altman_z(fs: dict) -> float:
    """Derive Altman Z-score from financial statement ratios.

    Approximation of:
      Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
    mapped to available features (QUANT: internally consistent).
    """
    x1 = (fs["current_ratio"] - 1.0) * 0.15   # working capital / assets proxy
    x2 = max(0.0, fs["roa"]) * 0.80            # retained earnings / assets proxy
    x3 = fs["ebitda_margin"] * 0.60            # EBIT / assets proxy
    x4 = max(0.01, 1.0 / (fs["debt_to_equity"] + 0.01))  # equity / debt proxy
    x5 = fs["asset_turnover"]                  # revenue / assets
    z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
    return float(np.clip(z, -3.0, 10.0))


def _derive_merton_dd(fs: dict, z: float, rng: np.random.Generator) -> float:
    """Distance-to-default proxy derived from Altman Z and leverage.

    Parameters
    ----------
    rng:
        Seeded generator — ensures reproducibility (B11-03: no global np.random).
    """
    dte = fs["debt_to_equity"]
    # Higher Z and lower leverage → higher distance to default
    dd = 0.6 * z + 0.4 * max(0.0, 4.0 - dte)
    return float(np.clip(dd + rng.normal(0, 0.3), -2.0, 8.0))


def _gen_correlated_financials(rng: np.random.Generator, label: int) -> dict:
    """Draw correlated financial ratios from multivariate normal."""
    mu = _MU_HEALTHY if label == 0 else _MU_DEFAULT
    cov = _COV_HEALTHY if label == 0 else _COV_DEFAULT

    raw = rng.multivariate_normal(mu, cov)

    names = [
        "current_ratio", "debt_to_equity", "interest_coverage",
        "roe", "roa", "ebitda_margin", "revenue_growth",
        "cash_ratio", "asset_turnover", "net_margin",
    ]
    fs = {}
    for i, name in enumerate(names):
        lo, hi = _CLIP_BOUNDS[i]
        fs[name] = float(np.clip(raw[i], lo, hi))

    return fs


# ---------------------------------------------------------------------------
# Payment + borrower generators
# ---------------------------------------------------------------------------

def _gen_payment(rng: np.random.Generator, idx: int, epoch_offset: float) -> dict:
    bic_s = rng.choice(_BICS)
    bic_r = rng.choice([b for b in _BICS if b != bic_s])
    amount_usd = float(np.exp(rng.normal(12.0, 1.5)))
    amount_usd = float(np.clip(amount_usd, 5_000.0, 20_000_000.0))
    hour_of_day = int(rng.integers(0, 24))
    day_of_week = int(rng.integers(0, 7))
    timestamp = _EPOCH_START + epoch_offset + idx * 3600

    return {
        "uetr": str(uuid.uuid4()),
        "sending_bic": bic_s,
        "receiving_bic": bic_r,
        "currency_pair": rng.choice(_CURRENCIES),
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


def _gen_tier1_borrower(rng: np.random.Generator, label: int) -> dict:
    fs = _gen_correlated_financials(rng, label)
    z = _derive_altman_z(fs)
    mdd = _derive_merton_dd(fs, z, rng)

    cb_score = int(np.clip(rng.normal(720 if label == 0 else 560, 50), 300, 850))
    ph_score = float(np.clip(rng.normal(0.85 if label == 0 else 0.45, 0.10), 0.0, 1.0))
    avg_days = float(np.clip(rng.normal(28 if label == 0 else 55, 10), 1.0, 120.0))
    delinq   = float(np.clip(rng.beta(1 if label == 0 else 3, 15), 0.0, 0.5))
    n_default = int(rng.choice([0, 0, 0, 1, 2], p=[0.85, 0.07, 0.05, 0.02, 0.01]))
    bankrupt  = bool(rng.random() < (0.01 if label == 0 else 0.08))

    return {
        "has_financial_statements": True,
        "has_transaction_history": True,
        "has_credit_bureau": True,
        "months_history": int(rng.integers(24, 120)),
        "transaction_count": int(rng.integers(100, 1000)),
        "counterparty_age_days": int(rng.integers(365, 3650)),
        "financial_statements": fs,
        "altman_z_score": z,
        "merton_distance_to_default": mdd,
        "credit_bureau": {
            "score": cb_score,
            "age_months": int(rng.integers(24, 120)),
            "payment_history_score": ph_score,
            "avg_days_to_pay": avg_days,
            "delinquency_rate": delinq,
            "default_history_count": n_default,
            "bankruptcy_history": bankrupt,
        },
        "industry_risk_score": float(np.clip(rng.beta(2, 5 if label == 0 else 2), 0.0, 1.0)),
        "corpus_tag": _CORPUS_TAG,
    }


def _gen_tier2_borrower(rng: np.random.Generator, label: int) -> dict:
    avg_pmt = float(np.exp(rng.normal(11.5, 1.2)))
    pmt_std = avg_pmt * float(rng.uniform(0.1, 0.6))
    freq    = float(np.clip(rng.normal(15 if label == 0 else 8, 5), 1.0, 60.0))
    trend   = float(rng.normal(0.02 if label == 0 else -0.05, 0.03))

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
            "counterparty_diversity": float(np.clip(rng.beta(2, 3), 0.0, 1.0)),
            "payment_regularity_score": float(np.clip(
                rng.normal(0.70 if label == 0 else 0.40, 0.15), 0.0, 1.0
            )),
        },
        "corpus_tag": _CORPUS_TAG,
    }


def _gen_tier3_borrower(rng: np.random.Generator, label: int) -> dict:
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

def generate_pd_training_data_v2(
    n_samples: int = 30_000,
    seed: int = 42,
) -> List[dict]:
    """Generate synthetic PD training records with QUANT-validated correlated financials.

    Improvements over v1:
    - Tier-1 financial ratios drawn from correlated multivariate normal
    - Altman Z-score derived from financial features (not independent)
    - Merton distance-to-default derived from Altman Z + leverage
    - Temporal structure: records spread over 18 months (SR 11-7 OOT splits)
    - Data tagged SYNTHETIC_CORPUS_C2_V2

    Each record::

        {
            "label":    int,    # 1 = default, 0 = no-default
            "payment":  dict,
            "borrower": dict,
            "tier":     int,    # 1 / 2 / 3
            "corpus_tag": str,
            "generation_seed": int,
            "generation_timestamp": str,
        }

    Parameters
    ----------
    n_samples : int
        Total records.
    seed : int
        Random seed for reproducibility.
    """
    rng = np.random.default_rng(seed)
    ts = datetime.now(tz=timezone.utc).isoformat() + "Z"

    tier_choices = rng.choice([1, 2, 3], size=n_samples, p=_TIER_WEIGHTS)
    default_rates = {1: _DEFAULT_RATE_TIER1, 2: _DEFAULT_RATE_TIER2, 3: _DEFAULT_RATE_TIER3}

    # Spread records over 18 months for out-of-time validation (REX: SR 11-7)
    epoch_offsets = rng.uniform(0, _EPOCH_SPAN, size=n_samples)

    records: List[dict] = []
    for i, (tier, epoch_offset) in enumerate(zip(tier_choices, epoch_offsets)):
        dr = default_rates[tier]
        label = int(rng.random() < dr)

        # Thin-file: payment corridor risk elevates default probability
        if tier == 3:
            payment = _gen_payment(rng, i, epoch_offset)
            if payment["corridor_failure_rate"] > 0.08:
                label = int(rng.random() < _DEFAULT_RATE_TIER3 * 1.5)
            borrower = _gen_tier3_borrower(rng, label)
        elif tier == 2:
            payment = _gen_payment(rng, i, epoch_offset)
            borrower = _gen_tier2_borrower(rng, label)
        else:
            payment = _gen_payment(rng, i, epoch_offset)
            borrower = _gen_tier1_borrower(rng, label)

        records.append({
            "label": label,
            "payment": payment,
            "borrower": borrower,
            "tier": int(tier),
            "corpus_tag": _CORPUS_TAG,
            "generation_seed": seed,
            "generation_timestamp": ts,
        })

    return records


def generate_at_scale(n: int = 500_000, seed: int = 42) -> List[dict]:
    """Generate C2 PD records at prototype validation scale.

    Calls :func:`generate_pd_training_data_v2` with QUANT-validated correlated
    financials and SR 11-7 temporal structure. At n=500,000 this requires
    approximately 2-3 GB RAM due to the multivariate normal draws per record.

    For CI/CD and demo runs, use n=10_000 or n=30_000.
    """
    return generate_pd_training_data_v2(n_samples=n, seed=seed)
