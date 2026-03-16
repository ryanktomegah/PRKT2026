"""
iso20022_payments.py — DGEN: Production ISO 20022 Payment Event Generator (Step 2)
===================================================================================
Generates `payments_synthetic.parquet` — the main 2M+ record training dataset
for C1 failure classifier and related ML components.

All records represent failed payments (pacs.002 RJCT events). The binary
label `is_permanent_failure` distinguishes Class A (permanent, bridge loan
opportunity) from Class B/C (recoverable, lower-priority).

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
  rejection_code        str     — ISO 20022 pacs.002 reason code
  rejection_class       str     — A | B | C
  amount_usd            float   — log-normal, corridor-calibrated
  settlement_time_hours float   — lognormal per rejection class, P95-calibrated
  is_permanent_failure  int     — 1=Class A, 0=Class B/C
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
# Class B (compliance/AML hold, 7-day maturity) — target 40% of failures
#   These codes indicate regulatory holds that may lift with documentation.
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
]

_CORRIDOR_NAMES = [c.name for c in _CORRIDORS]
_CORRIDOR_VOLUME_WEIGHTS = np.array([c.volume_weight for c in _CORRIDORS], dtype=np.float64)
_CORRIDOR_VOLUME_WEIGHTS /= _CORRIDOR_VOLUME_WEIGHTS.sum()


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


def _generate_chunk(
    chunk_size: int,
    seed: int,
    bic_pool: BICPool,
) -> pd.DataFrame:
    """Generate one chunk of synthetic payment events.

    Parameters
    ----------
    chunk_size : int
        Number of records in this chunk.
    seed : int
        Unique seed for this chunk (use chunk_index * prime offset).
    bic_pool : BICPool
        Pre-initialised BIC pool.

    Returns
    -------
    pd.DataFrame with all required output fields.
    """
    rng = np.random.default_rng(seed)

    # Sample corridors
    corridor_idx = rng.choice(len(_CORRIDORS), size=chunk_size, p=_CORRIDOR_VOLUME_WEIGHTS)

    # Sample rejection codes
    code_idx = rng.choice(len(_CODE_LIST), size=chunk_size, p=_CODE_WEIGHTS)
    codes = [_CODE_LIST[i] for i in code_idx]
    classes = [_REJECTION_CODES[c][0] for c in codes]

    # Sample BIC pairs (vectorised)
    senders, receivers = bic_pool.sample_bic_pairs_batch(rng, chunk_size)

    # Derive corridors, currency pairs from BIC geography
    corridors_str = [bic_pool.get_corridor(s, r) for s, r in zip(senders, receivers)]
    currency_pairs = [bic_pool.get_currency_pair(s, r) for s, r in zip(senders, receivers)]

    # Sample amounts per corridor (log-normal)
    amounts = np.empty(chunk_size, dtype=np.float64)
    for ci, corr in enumerate(_CORRIDORS):
        mask = corridor_idx == ci
        n_mask = int(mask.sum())
        if n_mask == 0:
            continue
        raw = np.exp(rng.normal(corr.amount_mu, corr.amount_sigma, size=n_mask))
        amounts[mask] = np.clip(raw, 5_000.0, 50_000_000.0)

    # Sample settlement time per rejection class (log-normal)
    settlement_times = np.empty(chunk_size, dtype=np.float64)
    for cls, (mu, sigma) in _SETTLEMENT_PARAMS.items():
        mask = np.array([c == cls for c in classes])
        n_mask = int(mask.sum())
        if n_mask == 0:
            continue
        raw = np.exp(rng.normal(mu, sigma, size=n_mask))
        settlement_times[mask] = np.clip(raw, 0.1, 5000.0)

    # Sample timestamps (day-of-period + intraday seconds)
    day_offsets = rng.uniform(0, _EPOCH_SPAN, size=chunk_size)  # uniform over 18 months
    intraday_secs = _sample_intraday_hour(rng, chunk_size)
    day_base = (day_offsets // 86_400) * 86_400  # truncate to day boundary
    ts_unix = _EPOCH_START + day_base + intraday_secs
    ts_iso = [
        datetime.fromtimestamp(t, tz=timezone.utc).isoformat()
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

    # is_permanent_failure = 1 iff Class A
    is_perm = [1 if c == "A" else 0 for c in classes]

    df = pd.DataFrame({
        "uetr": [str(uuid.uuid4()) for _ in range(chunk_size)],
        "bic_sender": senders,
        "bic_receiver": receivers,
        "corridor": corridors_str,
        "rejection_code": codes,
        "rejection_class": classes,
        "amount_usd": np.round(amounts, 2),
        "settlement_time_hours": np.round(settlement_times, 4),
        "is_permanent_failure": is_perm,
        "timestamp_utc": ts_iso,
        "currency_pair": currency_pairs,
        "rail": rails,
    })

    return df


def generate_payments(
    n: int = 2_000_000,
    seed: int = 42,
    chunk_size: int = 500_000,
) -> pd.DataFrame:
    """Generate the full synthetic ISO 20022 payment events dataset.

    Generates in chunks to limit peak RAM usage. At n=2,000,000 with
    chunk_size=500,000 the peak memory is approximately 200MB.

    Parameters
    ----------
    n : int
        Total number of payment events to generate (all are RJCT failures).
    seed : int
        Master random seed. Each chunk uses seed + chunk_index * 997 to
        ensure statistical independence between chunks.
    chunk_size : int
        Records per chunk (reduce if OOM on <8GB RAM machines).

    Returns
    -------
    pd.DataFrame with all required output fields.
    """
    bic_pool = BICPool()
    chunks: list[pd.DataFrame] = []
    n_chunks = (n + chunk_size - 1) // chunk_size  # ceil division

    for i in range(n_chunks):
        start = i * chunk_size
        end = min(start + chunk_size, n)
        c_size = end - start
        c_seed = seed + i * 997  # prime offset for statistical independence
        chunk_df = _generate_chunk(c_size, c_seed, bic_pool)
        chunks.append(chunk_df)

    df = pd.concat(chunks, ignore_index=True)
    return df


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
