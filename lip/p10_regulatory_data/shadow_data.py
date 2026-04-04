"""
shadow_data.py — Synthetic multi-bank shadow event generator for P10 integration testing.

Generates deterministic NormalizedEvent streams that simulate real bank telemetry
across multiple corridors and failure modes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import numpy as np

from lip.c5_streaming.event_normalizer import NormalizedEvent

# ---------------------------------------------------------------------------
# Corridor metadata: corridor_key → (send_currency, recv_currency, send_cc, recv_cc)
# ---------------------------------------------------------------------------
_CORRIDOR_META: dict[str, tuple[str, str, str, str]] = {
    "EUR-USD": ("EUR", "USD", "DE", "US"),
    "GBP-EUR": ("GBP", "EUR", "GB", "DE"),
    "USD-JPY": ("USD", "JPY", "US", "JP"),
    "EUR-GBP": ("EUR", "GBP", "DE", "GB"),
    "USD-CAD": ("USD", "CAD", "US", "CA"),
    "GBP-USD": ("GBP", "USD", "GB", "US"),
    "EUR-JPY": ("EUR", "JPY", "DE", "JP"),
    "CAD-USD": ("CAD", "USD", "CA", "US"),
}

_DEFAULT_CORRIDORS: list[str] = list(_CORRIDOR_META.keys())

_RAILS: list[str] = ["SWIFT", "FEDNOW", "RTP", "SEPA"]

# Failure code pools by class
_CLASS_A_CODES: list[str] = ["AC01", "AC04", "AC06"]
_CLASS_B_CODES: list[str] = ["CURR", "AM04", "AM05"]
_CLASS_C_CODES: list[str] = ["AGNT", "ARDT"]
_BLOCK_CODES: list[str] = ["DNOR", "CNOR", "RR01", "FRAD"]

_BASE_TIME = datetime(2026, 4, 2, 14, 0, 0, tzinfo=timezone.utc)
_WINDOW_SECONDS = 3600  # 1-hour window


def _pick_rejection_code(rng: np.random.Generator) -> str:
    """Pick a rejection code using the specified class distribution.

    Distribution:
      50% CLASS_A (AC01/AC04/AC06)
      30% CLASS_B (CURR/AM04/AM05)
      15% CLASS_C (AGNT/ARDT)
       5% BLOCK   (DNOR/CNOR/RR01/FRAD)
    """
    roll = rng.random()
    if roll < 0.50:
        idx = int(rng.integers(0, len(_CLASS_A_CODES)))
        return _CLASS_A_CODES[idx]
    elif roll < 0.80:
        idx = int(rng.integers(0, len(_CLASS_B_CODES)))
        return _CLASS_B_CODES[idx]
    elif roll < 0.95:
        idx = int(rng.integers(0, len(_CLASS_C_CODES)))
        return _CLASS_C_CODES[idx]
    else:
        idx = int(rng.integers(0, len(_BLOCK_CODES)))
        return _BLOCK_CODES[idx]


def generate_shadow_events(
    n_banks: int = 5,
    n_events_per_bank: int = 2000,
    corridors: Optional[list[str]] = None,
    failure_rate: float = 0.08,
    stressed_corridor: Optional[str] = "EUR-USD",
    stressed_rate: float = 0.15,
    seed: int = 42,
) -> list[NormalizedEvent]:
    """Generate synthetic multi-bank payment events for P10 shadow pipeline testing.

    Parameters
    ----------
    n_banks:
        Number of synthetic banks to simulate.
    n_events_per_bank:
        Total events per bank (distributed across corridors).
    corridors:
        List of corridor keys to use. Defaults to the 8 standard corridors.
    failure_rate:
        Base probability that a non-stressed event is rejected (0.08 = 8%).
    stressed_corridor:
        Corridor with elevated failure rate. ``None`` disables stressed corridor.
    stressed_rate:
        Failure probability for the stressed corridor (0.15 = 15%).
    seed:
        RNG seed for deterministic generation.

    Returns
    -------
    list[NormalizedEvent]
        All generated events across all banks, in corridor/bank order.
    """
    rng = np.random.default_rng(seed)

    if corridors is None:
        corridors = _DEFAULT_CORRIDORS

    events: list[NormalizedEvent] = []

    for bank_i in range(1, n_banks + 1):
        # Distribute n_events_per_bank across corridors with ±20% random variation.
        # Compute raw weights, then normalise to sum to n_events_per_bank.
        base_per_corridor = n_events_per_bank / len(corridors)
        raw_counts = rng.uniform(
            base_per_corridor * 0.80,
            base_per_corridor * 1.20,
            size=len(corridors),
        )
        # Scale so total equals exactly n_events_per_bank (integer rounding)
        scaled = raw_counts / raw_counts.sum() * n_events_per_bank
        corridor_counts = [int(round(c)) for c in scaled]
        # Correct rounding drift on the last corridor
        diff = n_events_per_bank - sum(corridor_counts)
        corridor_counts[-1] += diff

        for corr_idx, corridor in enumerate(corridors):
            n_corr = corridor_counts[corr_idx]
            meta = _CORRIDOR_META.get(corridor)
            if meta is None:
                # Unknown corridor — skip gracefully
                continue

            send_curr, recv_curr, send_cc, recv_cc = meta

            # BIC construction: embed bank index + country code for uniqueness
            sending_bic = f"BK{bank_i:02d}{send_cc}XXXX"
            receiving_bic = f"RECV{recv_cc}XXXX"

            # Determine failure rate for this corridor
            corr_fail_rate = (
                stressed_rate
                if (stressed_corridor is not None and corridor == stressed_corridor)
                else failure_rate
            )

            for _ in range(n_corr):
                # UETR
                uetr = str(uuid.UUID(bytes=rng.bytes(16), version=4))

                # Individual payment ID
                individual_payment_id = "SHADOW-" + uetr[:8].upper()

                # Amount: log-normal
                raw_amount = rng.lognormal(mean=10.8, sigma=1.5)
                amount = Decimal(str(round(float(raw_amount), 2)))

                # Timestamp: uniform within 1-hour window
                offset_secs = float(rng.uniform(0, _WINDOW_SECONDS))
                timestamp = _BASE_TIME + timedelta(seconds=offset_secs)

                # Rail
                rail_idx = int(rng.integers(0, len(_RAILS)))
                rail = _RAILS[rail_idx]

                # Failure
                is_failed = rng.random() < corr_fail_rate
                rejection_code: Optional[str] = None
                if is_failed:
                    rejection_code = _pick_rejection_code(rng)

                # Telemetry eligibility: ~2% ineligible (independent of failure)
                telemetry_eligible = rng.random() >= 0.02

                events.append(
                    NormalizedEvent(
                        uetr=uetr,
                        individual_payment_id=individual_payment_id,
                        sending_bic=sending_bic,
                        receiving_bic=receiving_bic,
                        amount=amount,
                        currency=send_curr,
                        timestamp=timestamp,
                        rail=rail,
                        rejection_code=rejection_code,
                        telemetry_eligible=telemetry_eligible,
                    )
                )

    return events
