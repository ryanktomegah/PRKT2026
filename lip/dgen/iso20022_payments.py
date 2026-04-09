"""
iso20022_payments.py — DGEN: Production ISO 20022 Payment Event Generator (Step 2)
===================================================================================
Generates `payments_synthetic.parquet` — the main training dataset for C1
failure classifier and related ML components.

The corpus is a **mixed** dataset: both successful payments (label=0) and
failed payments / RJCT events (label=1).  This is the correct design for C1
training: the model learns to distinguish failed from succeeded payments, not
to classify failure types (A/B/C — that is C2/C7's job).

Corpus composition (default success_multiplier=4.0):
  - n RJCT records  (label=1) — failed pacs.002 events
  - 4n success records (label=0) — payments that cleared without rejection
  - Total = 5n records, shuffled

Calibration sources:
  - Corridor failure rates: BIS CPMI Quarterly Payment Statistics 2024
  - Rejection code frequencies: BIS/SWIFT GPI Joint Analytics
  - Amount distributions: ECB Annual Payment Statistics (median €6,532, mean €4.3M)
  - Intraday distribution: ECB T2 statistics + NY Fed Fedwire timing paper
  - Settlement time P95: BIS/SWIFT GPI corridor-level analytics
  - Rail distribution: BIS CPMI 2024 Cross-Border Monitoring Survey

Output schema (parquet):
  uetr                  str     — UUID v4 unique identifier
  bic_sender            str     — fictional 8-char BIC
  bic_receiver          str     — fictional 8-char BIC
  corridor              str     — e.g. "USD-EUR"
  label                 int     — 1=RJCT (failed payment), 0=success
  rejection_code        str|NA  — ISO 20022 pacs.002 reason code (null for successes)
  rejection_class       str|NA  — A | B | C (null for successes)
  amount_usd            float   — log-normal, corridor-calibrated
  settlement_time_hours float|NA— lognormal per rejection class, P95-calibrated (NaN for successes)
  is_permanent_failure  int     — 1=Class A RJCT, 0=Class B/C RJCT or success
  timestamp_utc         str     — ISO 8601 UTC string, peaked 06:00-11:00 UTC
  currency_pair         str     — e.g. "USD/EUR"
  rail                  str     — SWIFT | FEDNOW | RTP | SEPA_INSTANT | STATISTICAL

Usage::

    from lip.dgen.iso20022_payments import generate_payments, DEFAULT_PARAMS
    df = generate_payments(n=2_000_000, seed=42)
    df.to_parquet("artifacts/production_data/payments_synthetic.parquet", index=False)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from lip.dgen.bic_pool import BICPool

# ---------------------------------------------------------------------------
# Rejection code taxonomy
# ---------------------------------------------------------------------------
# Source: BIS/SWIFT GPI Joint Analytics + ISO 20022 pacs.002 specification
#
# Class A (permanent, 3-day maturity) — target 35% of failures
#   These codes indicate account/routing issues that are not self-healing.
#
# Class B (systemic/processing delay, 7-day maturity) — target 40% of failures
#   These codes indicate systemic or processing delays that typically resolve.
#
# Class C (liquidity/timing, 21-day maturity) — target 25% of failures
#   These codes indicate operational/liquidity issues that resolve over time.
#
# Frequencies within each class sum to 1.0; cross-class ratios give 35/40/25.
# is_permanent_failure = 1 iff rejection_class == "A".

_REJECTION_CODES: dict[str, tuple[str, float]] = {
    # Class A — 35% total weight
    "AC01": ("A", 0.120),   # Incorrect account number
    "AC04": ("A", 0.080),   # Closed account
    "AG01": ("A", 0.050),   # Transaction forbidden (account restrictions)
    "RC01": ("A", 0.050),   # BIC invalid
    "MD01": ("A", 0.050),   # No mandate (standing instruction not found)
    # Class B — 40% total weight
    "RR01": ("B", 0.100),   # Regulatory requirement (sender-side)
    "RR02": ("B", 0.080),   # Regulatory requirement (creditor-side)
    "RR03": ("B", 0.070),   # Regulatory requirement (debtor-side)
    "RR04": ("B", 0.050),   # Regulatory requirement (reason not specified)
    "FRAU": ("B", 0.050),   # Fraud suspected
    "LEGL": ("B", 0.050),   # Legal decision by court / regulatory authority
    # Class C — 25% total weight
    "AM04": ("C", 0.120),   # Insufficient funds
    "AM05": ("C", 0.070),   # Duplicate payment detected
    "FF01": ("C", 0.030),   # Invalid file format / message structure
    "MS03": ("C", 0.030),   # Not specified reason — catch-all
}

# Verification: class A = 0.35, class B = 0.40, class C = 0.25
_CODE_LIST = list(_REJECTION_CODES.keys())
_CODE_WEIGHTS_RAW = np.array([v[1] for v in _REJECTION_CODES.values()], dtype=np.float64)
_CODE_WEIGHTS = _CODE_WEIGHTS_RAW / _CODE_WEIGHTS_RAW.sum()


# ---------------------------------------------------------------------------
# Corridor configuration
# ---------------------------------------------------------------------------
# Corridor weights from BIS CPMI 2024 global cross-border payment volumes.
# Failure rates from BIS/SWIFT GPI Joint Analytics.

@dataclass
class CorridorConfig:
    """Per-corridor calibration parameters."""

    name: str               # e.g. "EUR/USD"
    volume_weight: float    # share of global cross-border volume
    failure_rate: float     # probability a payment fails (RJCT)
    amount_mu: float        # log-normal μ for amount_usd
    amount_sigma: float     # log-normal σ for amount_usd
    # Rail distribution: {"SWIFT": p, "FEDNOW": p, ...} — must sum to 1.0
    rails: dict[str, float] = field(default_factory=dict)


_CORRIDORS: list[CorridorConfig] = [
    # Major G10 corridors (wholesale, large amounts)
    CorridorConfig("EUR/USD", 0.25, 0.150, 13.5, 1.4,
                   {"SWIFT": 0.70, "SEPA_INSTANT": 0.20, "STATISTICAL": 0.10}),
    CorridorConfig("USD/EUR", 0.15, 0.150, 13.5, 1.4,
                   {"SWIFT": 0.70, "SEPA_INSTANT": 0.20, "STATISTICAL": 0.10}),
    CorridorConfig("GBP/USD", 0.12, 0.080, 13.2, 1.5,
                   {"SWIFT": 0.80, "STATISTICAL": 0.20}),
    CorridorConfig("USD/GBP", 0.08, 0.080, 13.2, 1.5,
                   {"SWIFT": 0.80, "STATISTICAL": 0.20}),
    CorridorConfig("USD/JPY", 0.10, 0.120, 13.0, 1.5,
                   {"SWIFT": 0.80, "STATISTICAL": 0.20}),
    CorridorConfig("USD/CHF", 0.04, 0.090, 13.1, 1.4,
                   {"SWIFT": 0.85, "STATISTICAL": 0.15}),
    CorridorConfig("EUR/GBP", 0.06, 0.110, 13.0, 1.5,
                   {"SWIFT": 0.65, "SEPA_INSTANT": 0.25, "STATISTICAL": 0.10}),
    CorridorConfig("USD/CAD", 0.05, 0.095, 13.0, 1.5,
                   {"SWIFT": 0.60, "FEDNOW": 0.25, "RTP": 0.10, "STATISTICAL": 0.05}),
    # Emerging market corridors (smaller amounts, higher failure rates)
    CorridorConfig("USD/CNY", 0.06, 0.260, 12.0, 1.8,
                   {"SWIFT": 0.80, "STATISTICAL": 0.20}),
    CorridorConfig("USD/INR", 0.04, 0.280, 11.5, 1.8,
                   {"SWIFT": 0.85, "STATISTICAL": 0.15}),
    CorridorConfig("USD/SGD", 0.03, 0.180, 12.5, 1.6,
                   {"SWIFT": 0.80, "STATISTICAL": 0.20}),
    CorridorConfig("EUR/CHF", 0.02, 0.085, 13.0, 1.4,
                   {"SWIFT": 0.60, "SEPA_INSTANT": 0.30, "STATISTICAL": 0.10}),
    # Additional corridors — expand BIC pool coverage to 150+ unique institutions
    CorridorConfig("USD/AUD", 0.03, 0.100, 12.8, 1.5,
                   {"SWIFT": 0.80, "STATISTICAL": 0.20}),
    CorridorConfig("AUD/USD", 0.02, 0.100, 12.8, 1.5,
                   {"SWIFT": 0.80, "STATISTICAL": 0.20}),
    CorridorConfig("USD/HKD", 0.03, 0.130, 12.9, 1.5,
                   {"SWIFT": 0.80, "STATISTICAL": 0.20}),
    CorridorConfig("HKD/USD", 0.02, 0.130, 12.9, 1.5,
                   {"SWIFT": 0.80, "STATISTICAL": 0.20}),
    CorridorConfig("EUR/SEK", 0.02, 0.095, 12.7, 1.5,
                   {"SWIFT": 0.65, "SEPA_INSTANT": 0.25, "STATISTICAL": 0.10}),
    CorridorConfig("USD/KRW", 0.02, 0.220, 11.8, 1.7,
                   {"SWIFT": 0.85, "STATISTICAL": 0.15}),
    CorridorConfig("USD/BRL", 0.02, 0.300, 11.2, 1.9,
                   {"SWIFT": 0.85, "STATISTICAL": 0.15}),
    CorridorConfig("USD/MXN", 0.01, 0.190, 11.5, 1.8,
                   {"SWIFT": 0.70, "FEDNOW": 0.20, "STATISTICAL": 0.10}),
]

_CORRIDOR_NAMES = [c.name for c in _CORRIDORS]
_CORRIDOR_VOLUME_WEIGHTS = np.array([c.volume_weight for c in _CORRIDORS], dtype=np.float64)
_CORRIDOR_VOLUME_WEIGHTS /= _CORRIDOR_VOLUME_WEIGHTS.sum()

# Failure-weighted corridor sampling: RJCT events are sampled proportional to
# failure_rate × volume so that high-failure corridors produce proportionally
# more RJCT records than success records.  Without this, all corridors get the
# same label rate (1/(1+success_multiplier) ≈ 20%), killing all corridor-level
# discriminative signal for C1 training.
_CORRIDOR_FAILURE_WEIGHTS = np.array(
    [c.failure_rate * c.volume_weight for c in _CORRIDORS], dtype=np.float64
)
_CORRIDOR_FAILURE_WEIGHTS /= _CORRIDOR_FAILURE_WEIGHTS.sum()


# ---------------------------------------------------------------------------
# Settlement time parameters (lognormal per rejection class)
# ---------------------------------------------------------------------------
# Source: BIS/SWIFT GPI Joint Analytics — P95 observed settlement delays
#
# P95 of a lognormal(μ, σ) = exp(μ + 1.645 * σ)
#
# Class A (routing/account errors, usually detected quickly):
#   μ=0.8, σ=0.7 → P95 = exp(0.8 + 1.152) = exp(1.952) ≈ 7.0h
#
# Class B (regulatory holds — days to weeks):
#   μ=2.5, σ=0.9 → P95 = exp(2.5 + 1.481) = exp(3.981) ≈ 53.6h
#
# Class C (liquidity/timing — can extend to weeks):
#   μ=3.5, σ=1.0 → P95 = exp(3.5 + 1.645) = exp(5.145) ≈ 171h

_SETTLEMENT_PARAMS: dict[str, tuple[float, float]] = {
    "A": (0.8, 0.7),    # P95 ≈ 7.0h
    "B": (2.5, 0.9),    # P95 ≈ 53.6h
    "C": (3.5, 1.0),    # P95 ≈ 171h
}

# BIS/SWIFT GPI target P95 values (for statistical validation)
SETTLEMENT_P95_TARGETS: dict[str, float] = {
    "A": 7.0,
    "B": 53.6,
    "C": 171.0,
}


# ---------------------------------------------------------------------------
# Intraday distribution (piecewise uniform windows)
# ---------------------------------------------------------------------------
# Source: ECB T2 statistics + NY Fed Fedwire timing paper
# Windows are defined as (start_hour_utc, end_hour_utc, weight)
# The 24h day is covered entirely; weights sum to 1.0.

_INTRADAY_WINDOWS: list[tuple[int, int, float]] = [
    (6, 11, 0.40),   # 06:00–11:00 UTC peak (T2 opening + Asian close)
    (11, 17, 0.35),  # 11:00–17:00 UTC high (European + Americas overlap)
    (17, 22, 0.15),  # 17:00–22:00 UTC medium (Americas close)
    (22, 30, 0.10),  # 22:00–06:00 UTC trough (use 30 as 6+24 for 24h wrap)
]
# 18-month temporal range (SR 11-7 out-of-time validation support)
_EPOCH_START = 1_688_169_600.0   # 2023-07-01 00:00:00 UTC
_EPOCH_SPAN = 18 * 30 * 86_400   # 18 months in seconds


# ---------------------------------------------------------------------------
# SynthesisParameters — full parameter set serialised to synthesis_parameters.json
# ---------------------------------------------------------------------------


@dataclass
class SynthesisParameters:
    """All distribution parameters used by the production pipeline.

    Serialised to synthesis_parameters.json so the generation can be
    reproduced or adjusted without reading the source code.
    """

    schema_version: str = "1.0"
    description: str = "LIP Production Pipeline — ISO 20022 Synthetic Payment Dataset Parameters"
    calibration_date: str = "2024-Q4"

    # Corridor configuration
    corridors: list[dict[str, Any]] = field(default_factory=list)

    # Rejection code frequencies
    rejection_codes: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Class distribution targets (fraction of all rejections)
    class_target_fractions: dict[str, float] = field(
        default_factory=lambda: {"A": 0.35, "B": 0.40, "C": 0.25}
    )

    # Settlement time lognormal parameters per class
    settlement_params: dict[str, dict[str, float]] = field(default_factory=dict)

    # Settlement P95 targets (hours) from BIS/SWIFT GPI
    settlement_p95_targets_hours: dict[str, float] = field(default_factory=dict)

    # Intraday distribution windows
    intraday_windows: list[dict[str, Any]] = field(default_factory=list)

    # Temporal range
    epoch_start_iso: str = "2023-07-01T00:00:00Z"
    epoch_span_months: int = 18

    # Amount calibration (ECB PAY data)
    amount_calibration: dict[str, Any] = field(
        default_factory=lambda: {
            "ecb_median_eur": 6532,
            "ecb_mean_eur": 4_300_000,
            "model": "lognormal_per_corridor",
            "note": "Corridor-specific μ/σ from CorridorConfig.amount_mu/sigma",
        }
    )

    # BIC pool stats
    bic_pool_stats: dict[str, Any] = field(
        default_factory=lambda: {
            "n_hub_banks": 10,
            "n_spoke_banks": 190,
            "hub_volume_weight": 0.60,
            "spoke_volume_weight": 0.40,
            "countries_covered": "30+",
            "risk_tiers": {
                "TIER1_bottom30pct": "multiplier=0.25 (failure_rate ~6%)",
                "TIER2_30_80pct": "multiplier=1.0 (failure_rate ~20%, baseline)",
                "TIER3_80_95pct": "multiplier=5.0 (failure_rate ~56%)",
                "TIER4_top5pct": "multiplier=15.0 (failure_rate ~79%)",
            },
            "note": "Risk tiers assigned by BIC alphabetical order (deterministic). Drives sender_stats.failure_rate discriminative signal for C1.",
        }
    )

    # Sources cited
    calibration_sources: list[str] = field(
        default_factory=lambda: [
            "BIS CPMI Quarterly Payment Statistics 2024",
            "BIS/SWIFT GPI Joint Analytics (corridor settlement times, STP rates)",
            "ECB Annual Report on Payment Statistics 2023 (amounts, T2 timing)",
            "BIS CPMI Brief No.10 (RTGS operating hours, fast payment coverage)",
            "NY Fed EPR Vol.14 No.2 / Afonso & Zimmerman 2008 (Fedwire intraday)",
            "PaySim 2016 (Lopez-Rojas et al.) — graph topology proxy only",
            "IEEE-CIS Fraud Detection Kaggle 2019 — AML flag rate proxy only",
        ]
    )

    def to_json(self) -> str:
        """Serialise to JSON string."""
        return json.dumps(asdict(self), indent=2, default=str)


def build_synthesis_parameters() -> SynthesisParameters:
    """Construct the SynthesisParameters from module-level constants."""
    params = SynthesisParameters()

    params.corridors = [
        {
            "name": c.name,
            "volume_weight": c.volume_weight,
            "failure_rate": c.failure_rate,
            "amount_lognormal_mu": c.amount_mu,
            "amount_lognormal_sigma": c.amount_sigma,
            "rail_distribution": c.rails,
        }
        for c in _CORRIDORS
    ]

    params.rejection_codes = {
        code: {"class": cls, "raw_weight": float(w)}
        for code, (cls, w) in _REJECTION_CODES.items()
    }

    params.settlement_params = {
        cls: {"mu": mu, "sigma": sigma, "p95_hours": SETTLEMENT_P95_TARGETS[cls]}
        for cls, (mu, sigma) in _SETTLEMENT_PARAMS.items()
    }

    params.settlement_p95_targets_hours = SETTLEMENT_P95_TARGETS

    params.intraday_windows = [
        {
            "start_hour_utc": s,
            "end_hour_utc": e % 24,
            "weight": w,
            "description": f"{s:02d}:00–{e%24:02d}:00 UTC",
        }
        for s, e, w in _INTRADAY_WINDOWS
    ]

    return params


# Singleton — built once and reused
DEFAULT_PARAMS: SynthesisParameters = build_synthesis_parameters()


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

def _sample_intraday_hour(rng: np.random.Generator, n: int) -> np.ndarray:
    """Sample hour-of-day (0–23) from the piecewise intraday distribution.

    Returns float array of seconds-within-day (0 to 86399).
    """
    window_weights = np.array([w for _, _, w in _INTRADAY_WINDOWS], dtype=np.float64)
    window_weights /= window_weights.sum()

    window_choices = rng.choice(len(_INTRADAY_WINDOWS), size=n, p=window_weights)

    seconds = np.empty(n, dtype=np.float64)
    for wi, (start_h, end_h, _) in enumerate(_INTRADAY_WINDOWS):
        mask = window_choices == wi
        n_mask = int(mask.sum())
        if n_mask == 0:
            continue
        start_sec = start_h * 3600
        # For the trough window (22:00–06:00), end_h = 30 means 6h next day
        end_sec = end_h * 3600  # may be > 86400 — handled by % 86400 below
        secs = rng.uniform(start_sec, end_sec, size=n_mask)
        secs = secs % 86_400  # wrap 24h for the trough window
        seconds[mask] = secs

    return seconds


def _sample_rail(rng: np.random.Generator, corridor: CorridorConfig, n: int) -> list[str]:
    """Sample payment rail for a corridor, returning n strings."""
    rail_names = list(corridor.rails.keys())
    rail_probs = np.array(list(corridor.rails.values()), dtype=np.float64)
    rail_probs /= rail_probs.sum()
    indices = rng.choice(len(rail_names), size=n, p=rail_probs)
    return [rail_names[i] for i in indices]


def _generate_common_fields(
    chunk_size: int,
    seed: int,
    bic_pool: BICPool,
    corridor_weights: np.ndarray | None = None,
    currency_index: dict | None = None,
) -> tuple:
    """Sample fields common to both RJCT and success records.

    Parameters
    ----------
    corridor_weights:
        Probability weights for corridor sampling.  Defaults to
        ``_CORRIDOR_VOLUME_WEIGHTS`` (volume-proportional).  Pass
        ``_CORRIDOR_FAILURE_WEIGHTS`` for RJCT records so that high-failure
        corridors produce proportionally more failures than successes,
        creating the per-corridor label-rate variation that C1 needs.

    Returns
    -------
    (rng, corridor_idx, senders, receivers, corridors_str, currency_pairs,
     amounts, ts_iso, rails)
    """
    rng = np.random.default_rng(seed)

    # Sample corridors first — drives BIC selection, amounts, and rails
    weights = corridor_weights if corridor_weights is not None else _CORRIDOR_VOLUME_WEIGHTS
    corridor_idx = rng.choice(len(_CORRIDORS), size=chunk_size, p=weights)

    # Sample BIC pairs corridor-aligned
    if currency_index is None:
        currency_index = bic_pool.build_currency_index()
    senders: list[str] = [""] * chunk_size
    receivers: list[str] = [""] * chunk_size
    corridors_str: list[str] = [""] * chunk_size
    currency_pairs: list[str] = [""] * chunk_size

    for ci, corr in enumerate(_CORRIDORS):
        positions = np.where(corridor_idx == ci)[0]
        n_mask = len(positions)
        if n_mask == 0:
            continue
        src_curr, dst_curr = corr.name.split("/")
        s_bics, r_bics = bic_pool.sample_bic_pairs_by_corridor(
            rng, src_curr, dst_curr, n_mask, currency_index
        )
        corridor_label = corr.name.replace("/", "-")
        for j, pos in enumerate(positions):
            senders[pos] = s_bics[j]
            receivers[pos] = r_bics[j]
            corridors_str[pos] = corridor_label
            currency_pairs[pos] = corr.name

    # Sample amounts per corridor (log-normal)
    amounts = np.empty(chunk_size, dtype=np.float64)
    for ci, corr in enumerate(_CORRIDORS):
        mask = corridor_idx == ci
        n_mask = int(mask.sum())
        if n_mask == 0:
            continue
        raw = np.exp(rng.normal(corr.amount_mu, corr.amount_sigma, size=n_mask))
        amounts[mask] = np.clip(raw, 5_000.0, 50_000_000.0)

    # Sample timestamps (day-of-period + intraday seconds)
    day_offsets = rng.uniform(0, _EPOCH_SPAN, size=chunk_size)
    intraday_secs = _sample_intraday_hour(rng, chunk_size)
    day_base = (day_offsets // 86_400) * 86_400
    ts_unix = _EPOCH_START + day_base + intraday_secs
    ts_iso = [
        datetime.fromtimestamp(t, tz=timezone.utc).isoformat(timespec="milliseconds")
        for t in ts_unix
    ]

    # Sample rails per corridor
    rails: list[str] = []
    for ci in corridor_idx:
        corr = _CORRIDORS[ci]
        rail_names = list(corr.rails.keys())
        rail_probs = np.array(list(corr.rails.values()), dtype=np.float64)
        rail_probs /= rail_probs.sum()
        rails.append(rail_names[int(rng.choice(len(rail_names), p=rail_probs))])

    return rng, corridor_idx, senders, receivers, corridors_str, currency_pairs, amounts, ts_iso, rails


def _generate_chunk(
    chunk_size: int,
    seed: int,
    bic_pool: BICPool,
    currency_index: dict | None = None,
) -> pd.DataFrame:
    """Generate one chunk of RJCT (failed payment) records — label=1."""
    rng, corridor_idx, senders, receivers, corridors_str, currency_pairs, amounts, ts_iso, rails = (
        _generate_common_fields(chunk_size, seed, bic_pool, _CORRIDOR_FAILURE_WEIGHTS, currency_index)
    )

    # Sample rejection codes and classes
    code_idx = rng.choice(len(_CODE_LIST), size=chunk_size, p=_CODE_WEIGHTS)
    codes = [_CODE_LIST[i] for i in code_idx]
    classes = [_REJECTION_CODES[c][0] for c in codes]

    # Sample settlement time per rejection class (log-normal)
    settlement_times = np.empty(chunk_size, dtype=np.float64)
    for cls, (mu, sigma) in _SETTLEMENT_PARAMS.items():
        mask = np.array([c == cls for c in classes])
        n_mask = int(mask.sum())
        if n_mask == 0:
            continue
        raw = np.exp(rng.normal(mu, sigma, size=n_mask))
        settlement_times[mask] = np.clip(raw, 0.1, 5000.0)

    # is_permanent_failure = 1 iff Class A
    is_perm = [1 if c == "A" else 0 for c in classes]

    return pd.DataFrame({
        "uetr": [str(uuid.uuid4()) for _ in range(chunk_size)],
        "bic_sender": senders,
        "bic_receiver": receivers,
        "corridor": corridors_str,
        "label": 1,
        "rejection_code": codes,
        "rejection_class": classes,
        "amount_usd": np.round(amounts, 2),
        "settlement_time_hours": np.round(settlement_times, 4),
        "is_permanent_failure": is_perm,
        "timestamp_utc": ts_iso,
        "currency_pair": currency_pairs,
        "rail": rails,
    })


def _generate_success_chunk(
    chunk_size: int,
    seed: int,
    bic_pool: BICPool,
    currency_index: dict | None = None,
) -> pd.DataFrame:
    """Generate one chunk of successful payment records — label=0.

    Success records share the same corridor/BIC/amount/timestamp/rail
    distributions as RJCT records (same underlying payment population).
    Rejection fields are null — these payments cleared without error.
    """
    _rng, _corridor_idx, senders, receivers, corridors_str, currency_pairs, amounts, ts_iso, rails = (
        _generate_common_fields(chunk_size, seed, bic_pool, currency_index=currency_index)
    )

    return pd.DataFrame({
        "uetr": [str(uuid.uuid4()) for _ in range(chunk_size)],
        "bic_sender": senders,
        "bic_receiver": receivers,
        "corridor": corridors_str,
        "label": 0,
        "rejection_code": None,          # no rejection — payment succeeded
        "rejection_class": None,         # no rejection class
        "amount_usd": np.round(amounts, 2),
        "settlement_time_hours": float("nan"),  # not applicable for successful payments
        "is_permanent_failure": 0,
        "timestamp_utc": ts_iso,
        "currency_pair": currency_pairs,
        "rail": rails,
    })


def generate_payments(
    n: int = 2_000_000,
    seed: int = 42,
    chunk_size: int = 500_000,
    success_multiplier: float = 4.0,
) -> pd.DataFrame:
    """Generate the full synthetic ISO 20022 payment events dataset.

    Produces a **mixed corpus**: RJCT failures (label=1) and successful
    payments (label=0).  This is the correct design for C1 training —
    the model learns to separate failures from successes, not to classify
    failure types (A/B/C).

    Generates in chunks to limit peak RAM usage.

    Parameters
    ----------
    n : int
        Number of RJCT (failed) payment events to generate.
    seed : int
        Master random seed. RJCT chunks use seed + i*997; success chunks
        use seed + 1_000_003 + i*997 to ensure independence.
    chunk_size : int
        Records per chunk (reduce if OOM on <8GB RAM machines).
    success_multiplier : float
        Number of success records generated per RJCT record.
        Default 4.0 → 80% successes, 20% RJCT — trainable imbalance that
        approximates typical cross-border payment failure rates (~15–20%).
        Set to 0.0 to produce a RJCT-only corpus (label=1 everywhere,
        degenerate for C1 training — use only for specialised analysis).

    Returns
    -------
    pd.DataFrame with all required output fields, shuffled.
    """
    bic_pool = BICPool()
    _risk_rng = np.random.default_rng(seed + 777_777)
    bic_pool.assign_risk_multipliers(_risk_rng)
    risk_currency_index = bic_pool.build_risk_currency_index()
    normal_currency_index = bic_pool.build_currency_index()

    chunks: list[pd.DataFrame] = []
    n_chunks = (n + chunk_size - 1) // chunk_size  # ceil division

    # ── RJCT chunks (label=1) — senders drawn from risk-weighted BIC distribution ──
    for i in range(n_chunks):
        start = i * chunk_size
        end = min(start + chunk_size, n)
        c_size = end - start
        c_seed = seed + i * 997  # prime offset for statistical independence
        chunks.append(_generate_chunk(c_size, c_seed, bic_pool, currency_index=risk_currency_index))

    # ── Success chunks (label=0) — senders drawn from normal hub/spoke weights ──
    if success_multiplier > 0.0:
        n_success = int(n * success_multiplier)
        n_success_chunks = (n_success + chunk_size - 1) // chunk_size
        for i in range(n_success_chunks):
            start = i * chunk_size
            end = min(start + chunk_size, n_success)
            c_size = end - start
            # Offset by a large prime to avoid any seed overlap with RJCT chunks
            c_seed = seed + 1_000_003 + i * 997
            chunks.append(_generate_success_chunk(c_size, c_seed, bic_pool, currency_index=normal_currency_index))

    df = pd.concat(chunks, ignore_index=True)

    # Inject temporal burst clustering for 30% of RJCT senders — creates genuine
    # 1d/7d/30d failure rate variation so windowed features carry real signal.
    _cluster_rng = np.random.default_rng(seed + 999_997)
    df = _inject_temporal_clustering(df, _cluster_rng)

    # Shuffle to interleave RJCT and success records — models must not exploit
    # positional structure (all failures first, all successes last).
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


def _inject_temporal_clustering(
    df: pd.DataFrame,
    rng: np.random.Generator,
    burst_fraction: float = 0.30,
) -> pd.DataFrame:
    """Concentrate RJCT timestamps for a fraction of BICs into burst windows.

    For ``burst_fraction`` of unique sender BICs, re-samples their RJCT
    timestamps from 2–3 short windows (7–21 days each) distributed randomly
    across the 18-month epoch.  Success records and non-burst BICs are left
    untouched.

    Effect on C1 features:
      - Burst BICs have high failure_rate_1d / failure_rate_7d inside a window
        and near-zero outside — creating genuine 1d/7d vs 30d rate divergence.
      - consecutive_failures spikes during burst windows, returns to 0 outside.
      - The model can learn to use these signals as leading indicators.

    .. note:: Burst windows are placed uniformly across the 18-month epoch with
       no constraint on train/test split boundaries.  If a temporal split is used
       downstream, a burst window may straddle the boundary — this is a known
       limitation.  Current split strategy (stratified random) is unaffected.

    Parameters
    ----------
    burst_fraction:
        Fraction of unique RJCT-sender BICs to assign a burst profile.
        Default 0.30 (30%).  Remainder keep their uniform distribution.
    """
    original_labels = df["label"].to_numpy().copy()

    rjct_mask = df["label"] == 1
    rjct_senders = df.loc[rjct_mask, "bic_sender"].unique()
    if len(rjct_senders) == 0:
        return df

    n_burst = max(1, int(len(rjct_senders) * burst_fraction))
    burst_bics = set(rng.choice(rjct_senders, size=n_burst, replace=False).tolist())

    # Parse existing timestamps to unix seconds for arithmetic
    ts_unix = (
        pd.to_datetime(df["timestamp_utc"], utc=True).astype("int64") // 10**9
    ).to_numpy(dtype=np.float64)
    # Use canonical epoch constants — not data-derived — for reproducibility
    # and robustness against timestamp outliers.
    epoch_start = _EPOCH_START
    epoch_span = float(_EPOCH_SPAN)

    new_ts_unix = ts_unix.copy()
    modified_mask = np.zeros(len(df), dtype=bool)

    for bic in burst_bics:
        bic_mask_arr = rjct_mask.to_numpy() & (df["bic_sender"].to_numpy() == bic)
        n_failures = int(bic_mask_arr.sum())
        if n_failures == 0:
            continue

        # 2–3 burst windows per BIC
        n_windows = int(rng.integers(2, 4))
        max_window_dur = 21 * 86400
        window_starts = rng.uniform(0, epoch_span - max_window_dur, size=n_windows)
        window_durations = rng.uniform(7 * 86400, max_window_dur, size=n_windows)
        window_weights = rng.dirichlet(np.ones(n_windows))

        window_choices = rng.choice(n_windows, size=n_failures, p=window_weights)
        new_ts = np.empty(n_failures, dtype=np.float64)
        for wi in range(n_windows):
            wmask = window_choices == wi
            n_wm = int(wmask.sum())
            if n_wm == 0:
                continue
            new_ts[wmask] = (
                epoch_start + window_starts[wi]
                + rng.uniform(0, window_durations[wi], size=n_wm)
            )
        new_ts_unix[bic_mask_arr] = new_ts
        modified_mask |= bic_mask_arr

    # Only reconvert timestamps that were actually modified — preserve original
    # strings for unmodified rows to avoid format changes (e.g. dropping .000).
    result = df.copy()
    modified_indices = np.where(modified_mask)[0]
    new_timestamps = result["timestamp_utc"].to_numpy().copy()
    for i in modified_indices:
        new_timestamps[i] = datetime.fromtimestamp(
            float(new_ts_unix[i]), tz=timezone.utc
        ).isoformat(timespec="milliseconds")
    result["timestamp_utc"] = new_timestamps

    # Integrity check: labels must never be altered by timestamp resampling.
    assert np.array_equal(original_labels, result["label"].to_numpy()), (
        "BUG: _inject_temporal_clustering corrupted label column"
    )
    return result


def save_parquet(df: pd.DataFrame, output_path: Path) -> None:
    """Save DataFrame to parquet with optimal compression settings."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(
        output_path,
        engine="pyarrow",
        compression="snappy",
        index=False,
    )


def save_csv_sample(df: pd.DataFrame, output_path: Path, n: int = 10_000) -> None:
    """Save a random sample CSV for quick inspection."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sample = df.sample(n=min(n, len(df)), random_state=42)
    sample.to_csv(output_path, index=False)
