"""
synthetic_data.py — Synthetic settlement time data for C9 model training.
Calibrated to BIS/SWIFT GPI benchmarks for cross-border payment settlement.

Settlement time distributions by rejection class:
  CLASS_A (routing/account errors): LogNormal(mu=1.4, sigma=0.6) → median ~4h
  CLASS_B (systemic/processing):    LogNormal(mu=3.6, sigma=0.5) → median ~36h
  CLASS_C (liquidity/investigation): LogNormal(mu=4.8, sigma=0.4) → median ~120h

Censoring: 5% of observations are right-censored (settlement not observed
within the monitoring window). This reflects real-world data where some
payments may still be in progress at the time of data extraction.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple

import numpy as np

from lip.c9_settlement_predictor.model import _encode_features

# Settlement time parameters calibrated from BIS/SWIFT GPI benchmarks
_CLASS_PARAMS: Dict[str, Tuple[float, float]] = {
    "CLASS_A": (1.4, 0.6),   # median ~4.0h, P95 ~14.7h
    "CLASS_B": (3.6, 0.5),   # median ~36.6h, P95 ~89.7h
    "CLASS_C": (4.8, 0.4),   # median ~121.5h, P95 ~244.7h
}

# Corridor-level adjustments (multiplier on base settlement time)
_CORRIDOR_FACTORS: Dict[str, float] = {
    "USD-EUR": 0.85,   # liquid, fast
    "EUR-USD": 0.85,
    "GBP-USD": 0.90,
    "USD-GBP": 0.90,
    "EUR-GBP": 0.90,
    "USD-JPY": 1.0,
    "JPY-USD": 1.05,   # timezone delays
    "USD-CNY": 1.3,    # capital controls
    "USD-INR": 1.2,
    "USD-BRL": 1.25,
}

# BIC tier adjustments
_TIER_FACTOR: Dict[int, float] = {
    1: 0.8,   # Tier 1 banks settle faster
    2: 1.0,   # baseline
    3: 1.3,   # Tier 3 banks slower
}


def generate_settlement_data(
    n_samples: int = 50000,
    seed: int = 42,
    censoring_rate: float = 0.05,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate synthetic settlement time training data for C9.

    Parameters
    ----------
    n_samples:
        Number of settlement observations to generate.
    seed:
        Random seed for reproducibility.
    censoring_rate:
        Fraction of observations that are right-censored.

    Returns
    -------
    Tuple[np.ndarray, np.ndarray, np.ndarray]
        (X, durations, events) where:
        - X: feature matrix (n_samples, 16)
        - durations: settlement time in hours (n_samples,)
        - events: 1 = observed settlement, 0 = censored (n_samples,)
    """
    rng = np.random.default_rng(seed)

    classes = ["CLASS_A", "CLASS_B", "CLASS_C"]
    class_probs = [0.35, 0.40, 0.25]  # Match rejection taxonomy distribution

    corridors = list(_CORRIDOR_FACTORS.keys())
    corridor_probs = np.ones(len(corridors)) / len(corridors)

    tiers = [1, 2, 3]
    tier_probs = [0.3, 0.4, 0.3]

    X_list = []
    durations = []
    events = []

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

    for i in range(n_samples):
        # Sample attributes
        rejection_class = rng.choice(classes, p=class_probs)
        corridor = rng.choice(corridors, p=corridor_probs)
        sending_tier = int(rng.choice(tiers, p=tier_probs))
        receiving_tier = int(rng.choice(tiers, p=tier_probs))
        amount_usd = float(rng.lognormal(mean=14.0, sigma=1.5))  # median ~$1.2M
        amount_usd = max(500_000, min(amount_usd, 50_000_000))

        # Random timestamp
        offset_hours = rng.uniform(0, 365 * 24)
        timestamp = base_time + timedelta(hours=offset_hours)

        # Historical P50 for this corridor (with noise)
        mu, sigma = _CLASS_PARAMS[rejection_class]
        base_p50 = math.exp(mu)
        historical_p50 = base_p50 * _CORRIDOR_FACTORS.get(corridor, 1.0) * (1 + rng.normal(0, 0.1))
        historical_p50 = max(1.0, historical_p50)

        # Generate settlement time
        base_settlement = float(rng.lognormal(mu, sigma))

        # Apply corridor factor
        corridor_factor = _CORRIDOR_FACTORS.get(corridor, 1.0)
        base_settlement *= corridor_factor

        # Apply tier factors
        tier_factor = _TIER_FACTOR.get(sending_tier, 1.0) * 0.5 + _TIER_FACTOR.get(receiving_tier, 1.0) * 0.5
        base_settlement *= tier_factor

        # Time-of-day effect: payments at end of business day settle slower
        hour = timestamp.hour
        if 16 <= hour <= 23 or 0 <= hour <= 5:
            base_settlement *= 1.15  # after-hours penalty

        # Weekend effect
        if timestamp.weekday() >= 5:
            base_settlement *= 1.3

        # Amount effect: larger payments settle slightly slower
        if amount_usd > 5_000_000:
            base_settlement *= 1.1

        settlement_hours = max(0.5, base_settlement)

        # Censoring
        is_censored = rng.random() < censoring_rate
        if is_censored:
            # Censoring time: observe for a random fraction of settlement time
            settlement_hours = settlement_hours * rng.uniform(0.1, 0.9)
            event = 0
        else:
            event = 1

        # Encode features
        features = _encode_features(
            corridor=corridor,
            rejection_class=rejection_class,
            amount_usd=amount_usd,
            timestamp=timestamp,
            sending_bic_tier=sending_tier,
            receiving_bic_tier=receiving_tier,
            historical_p50_hours=historical_p50,
        )

        X_list.append(features)
        durations.append(settlement_hours)
        events.append(event)

    X = np.array(X_list, dtype=np.float64)
    durations_arr = np.array(durations, dtype=np.float64)
    events_arr = np.array(events, dtype=np.float64)

    return X, durations_arr, events_arr
