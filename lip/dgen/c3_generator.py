"""
c3_generator.py — DGEN: Synthetic repayment scenario corpus for C3
===================================================================
Three-entity role mapping:
  MLO   — Money Lending Organisation
  MIPLO — Monitoring, Intelligence & Processing Lending Operator
  ELO   — Execution Lending Organisation (bank-side agent, C7)

Generates realistic bridge-loan settlement scenarios across all 5 repayment rails
(SWIFT, FedNow, RTP, SEPA, BUFFER) for stress-testing the C3 repayment engine.

Scenario types produced:
  SUCCESS        — settlement arrives before maturity on primary rail
  TIMEOUT        — no settlement signal; buffer repayment triggered at maturity
  PARTIAL        — settlement amount < principal (shortfall scenario)
  RAIL_FALLBACK  — primary rail fails; cascade to next available rail
  EARLY_REPAY    — borrower triggers manual early repayment

Canonical constants used (QUANT sign-off required to change):
  Fee floor:          300 bps
  CLASS_A maturity:   3 days
  CLASS_B maturity:   7 days
  CLASS_C maturity:   21 days
  BLOCK maturity:     0 days (no loan)
  UETR TTL buffer:    45 days

CIPHER NOTE: No PII, no real UETR values — all IDs are synthetic UUIDs.
REX NOTE: corpus_tag = "SYNTHETIC_CORPUS_C3" for EU AI Act Art.10 lineage.
"""
from __future__ import annotations

import hashlib
import math
import time
from decimal import Decimal
from typing import List

import numpy as np

from lip.c2_pd_model.fee import compute_loan_fee
from lip.common.constants import FEE_FLOOR_BPS as _FEE_FLOOR_BPS_DECIMAL

# B11-14: FEE_FLOOR_BPS imported from lip.common.constants (canonical value 300 bps).
# Stored as int for use in max() and int arithmetic in fee computation.
_FEE_FLOOR_BPS = int(_FEE_FLOOR_BPS_DECIMAL)
_MATURITY_DAYS = {"CLASS_A": 3, "CLASS_B": 7, "CLASS_C": 21}
_RAILS = ["SWIFT", "FEDNOW", "RTP", "SEPA", "BUFFER"]
_CORRIDORS = [
    "USD_EUR", "USD_GBP", "USD_JPY", "USD_SGD", "USD_AUD",
    "EUR_GBP", "GBP_USD", "EUR_USD", "JPY_USD", "SGD_USD",
]

# Settlement latency (seconds) per rail — realistic approximations
_RAIL_LATENCY_S = {
    "SWIFT":   {"mean": 86400.0,  "std": 43200.0},   # 1d ± 12h
    "FEDNOW":  {"mean": 5.0,      "std": 2.0},        # ~5s
    "RTP":     {"mean": 8.0,      "std": 3.0},        # ~8s
    "SEPA":    {"mean": 3600.0,   "std": 1800.0},     # 1h ± 30m
    "BUFFER":  {"mean": 300.0,    "std": 60.0},       # 5m ± 1m (internal)
}

# Scenario type weights
_SCENARIO_WEIGHTS = {
    "SUCCESS":      0.65,
    "TIMEOUT":      0.12,
    "PARTIAL":      0.08,
    "RAIL_FALLBACK": 0.08,
    "EARLY_REPAY":  0.04,
    "RECALL_ATTACK": 0.03,  # R&D Upgrade: Adversarial camt.056 simulation
}

# Rejection class distribution (mirrors C1 failure class distribution)
_CLASS_WEIGHTS = {"CLASS_A": 0.45, "CLASS_B": 0.40, "CLASS_C": 0.15}

# Principal amount distribution params (log-normal, amounts in USD)
_PRINCIPAL_LOG_MEAN = math.log(250_000)   # median ~$250k
_PRINCIPAL_LOG_STD = 1.2                  # covers $10k–$5M range

# Epoch anchor for synthetic timestamps (2024-01-01 UTC)
_EPOCH_ANCHOR = 1_704_067_200


def _synthetic_uetr(rng: np.random.Generator) -> str:
    """Generate a deterministic but realistic-looking UUID4-style UETR."""
    raw = rng.integers(0, 2**64, size=2, dtype=np.uint64)
    h = hashlib.sha256(raw.tobytes()).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-4{h[13:16]}-{h[16:20]}-{h[20:32]}"


def _generate_record(
    rng: np.random.Generator,
    record_idx: int,
) -> dict:
    """Generate one synthetic C3 repayment scenario record."""

    # ── Identifiers ───────────────────────────────────────────────────────────
    uetr = _synthetic_uetr(rng)
    loan_id = f"LOAN-{record_idx:08d}"
    individual_payment_id = f"IPID-{_synthetic_uetr(rng)[:8].upper()}"

    # ── Loan parameters ───────────────────────────────────────────────────────
    rejection_class = rng.choice(
        list(_CLASS_WEIGHTS.keys()),
        p=list(_CLASS_WEIGHTS.values()),
    )
    maturity_days = _MATURITY_DAYS[rejection_class]
    corridor = rng.choice(_CORRIDORS)

    # Principal: log-normal, clipped to realistic range [$5k, $10M]
    principal_usd = float(np.clip(
        np.exp(rng.normal(_PRINCIPAL_LOG_MEAN, _PRINCIPAL_LOG_STD)),
        5_000.0,
        10_000_000.0,
    ))

    # Fee: max(300, PD*LGD*10000) — QUANT canonical formula
    # Simulate PD from a beta distribution (mean ~3.5% for bridge loans)
    pd_estimate = float(np.clip(rng.beta(0.5, 14.0), 0.005, 0.30))
    lgd = 0.45  # Basel III standard LGD
    fee_bps = max(_FEE_FLOOR_BPS, int(pd_estimate * lgd * 10_000))

    # ── Timing ────────────────────────────────────────────────────────────────
    # funded_at: random time over 18-month synthetic window (SR 11-7)
    window_s = int(18 * 30.5 * 86400)
    funded_ts = _EPOCH_ANCHOR + int(rng.integers(0, window_s))
    maturity_ts = funded_ts + maturity_days * 86400
    uetr_expiry_ts = maturity_ts + 45 * 86400   # UETR_TTL_BUFFER_DAYS

    # ── Scenario ──────────────────────────────────────────────────────────────
    scenario = rng.choice(
        list(_SCENARIO_WEIGHTS.keys()),
        p=list(_SCENARIO_WEIGHTS.values()),
    )

    # Primary rail selection — weighted by corridor and amount
    if corridor.startswith("USD_EUR") or corridor.startswith("EUR_"):
        primary_rail_weights = [0.30, 0.10, 0.10, 0.40, 0.10]  # SEPA preferred
    elif corridor in ("USD_GBP", "GBP_USD"):
        primary_rail_weights = [0.40, 0.05, 0.05, 0.40, 0.10]
    else:
        primary_rail_weights = [0.30, 0.25, 0.25, 0.10, 0.10]  # RTP/FedNow for domestic

    primary_rail = str(rng.choice(_RAILS, p=primary_rail_weights))

    # ── Settlement outcome ────────────────────────────────────────────────────
    settlement_rail = primary_rail
    settlement_ts: float | None = None
    settlement_amount_usd: float = 0.0
    fallback_rail: str | None = None
    is_settled = False
    is_timeout = False
    is_partial = False
    is_early = False
    shortfall_usd: float = 0.0
    repayment_triggered_by = "NONE"

    if scenario == "SUCCESS":
        # Settlement arrives before maturity
        lat_params = _RAIL_LATENCY_S[primary_rail]
        latency_s = float(np.clip(
            rng.normal(lat_params["mean"], lat_params["std"]),
            lat_params["mean"] * 0.1,
            (maturity_days * 86400) * 0.90,   # must arrive before maturity
        ))
        settlement_ts = funded_ts + latency_s
        _days_funded = (settlement_ts - funded_ts) / 86400
        settlement_amount_usd = principal_usd + float(compute_loan_fee(Decimal(str(principal_usd)), Decimal(str(fee_bps)), _days_funded))
        is_settled = True
        repayment_triggered_by = f"SETTLEMENT_SIGNAL_{primary_rail}"

    elif scenario == "TIMEOUT":
        # No settlement signal; buffer triggers at maturity
        settlement_rail = "BUFFER"
        settlement_ts = float(maturity_ts) + float(rng.normal(300.0, 60.0))
        settlement_amount_usd = principal_usd + float(compute_loan_fee(Decimal(str(principal_usd)), Decimal(str(fee_bps)), maturity_days))
        is_timeout = True
        is_settled = True
        repayment_triggered_by = "BUFFER_MATURITY_TRIGGER"

    elif scenario == "PARTIAL":
        # Settlement arrived but amount is less than expected
        lat_params = _RAIL_LATENCY_S[primary_rail]
        latency_s = float(np.clip(
            rng.normal(lat_params["mean"], lat_params["std"]),
            lat_params["mean"] * 0.1,
            (maturity_days * 86400) * 0.90,
        ))
        settlement_ts = funded_ts + latency_s
        # Shortfall: 5–40% of expected amount
        shortfall_fraction = float(rng.uniform(0.05, 0.40))
        _days_funded = (settlement_ts - funded_ts) / 86400
        expected = principal_usd + float(compute_loan_fee(Decimal(str(principal_usd)), Decimal(str(fee_bps)), _days_funded))
        shortfall_usd = expected * shortfall_fraction
        settlement_amount_usd = expected - shortfall_usd
        is_partial = True
        is_settled = True   # partial settlement = partially resolved
        repayment_triggered_by = f"PARTIAL_SETTLEMENT_{primary_rail}"

    elif scenario == "RAIL_FALLBACK":
        # Primary rail fails; cascade to next available
        available_fallbacks = [r for r in _RAILS if r != primary_rail]
        fallback_rail = str(rng.choice(available_fallbacks))
        settlement_rail = fallback_rail
        lat_params = _RAIL_LATENCY_S[fallback_rail]
        primary_failure_delay_s = float(rng.uniform(60.0, 3600.0))
        fallback_latency_s = float(np.clip(
            rng.normal(lat_params["mean"], lat_params["std"]),
            lat_params["mean"] * 0.1,
            (maturity_days * 86400) * 0.95,
        ))
        settlement_ts = funded_ts + primary_failure_delay_s + fallback_latency_s
        _days_funded = (settlement_ts - funded_ts) / 86400
        settlement_amount_usd = principal_usd + float(compute_loan_fee(Decimal(str(principal_usd)), Decimal(str(fee_bps)), _days_funded))
        is_settled = True
        repayment_triggered_by = f"SETTLEMENT_SIGNAL_{fallback_rail}_FALLBACK"

    elif scenario == "EARLY_REPAY":
        # Borrower initiates manual early repayment
        # Arrives at a random point within the first 80% of maturity window
        early_fraction = float(rng.uniform(0.05, 0.80))
        settlement_ts = funded_ts + early_fraction * maturity_days * 86400
        _days_funded = (settlement_ts - funded_ts) / 86400
        settlement_amount_usd = principal_usd + float(compute_loan_fee(Decimal(str(principal_usd)), Decimal(str(fee_bps)), _days_funded))
        is_early = True
        is_settled = True
        repayment_triggered_by = "EARLY_REPAY_MANUAL"

    elif scenario == "RECALL_ATTACK":
        # R&D Upgrade: Adversarial camt.056 cancellation
        # Sender issues recall 2-48 hours after disbursement
        recall_delay_s = float(rng.uniform(7200.0, 172800.0))
        settlement_ts = funded_ts + recall_delay_s
        settlement_amount_usd = 0.0
        is_settled = False
        repayment_triggered_by = "CAMT056_RECALL_PENDING"

    # ── Latency SLO check (informational) ────────────────────────────────────
    # Time from funded to first settlement signal received (C5 → C3 handoff)
    c5_handoff_latency_ms = float(rng.exponential(scale=12.0))   # ~12ms mean
    within_slo = c5_handoff_latency_ms <= 94.0                   # LATENCY_SLO_MS

    # ── Label ─────────────────────────────────────────────────────────────────
    # label=1 → problematic outcome (timeout, partial shortfall > 20%, or recall attack)
    label = int(
        is_timeout
        or (is_partial and shortfall_usd / (principal_usd + 1e-9) > 0.20)
        or scenario == "RECALL_ATTACK"
    )

    return {
        # Identifiers
        "loan_id": loan_id,
        "uetr": uetr,
        "individual_payment_id": individual_payment_id,
        # Loan parameters
        "rejection_class": rejection_class,
        "maturity_days": maturity_days,
        "corridor": corridor,
        "principal_usd": round(principal_usd, 2),
        "fee_bps": fee_bps,
        "pd_estimate": round(pd_estimate, 6),
        # Timing (epoch seconds)
        "funded_at": funded_ts,
        "maturity_at": maturity_ts,
        "uetr_expiry_at": uetr_expiry_ts,
        "settlement_at": round(settlement_ts, 3) if settlement_ts is not None else None,
        # Rails
        "primary_rail": primary_rail,
        "settlement_rail": settlement_rail,
        "fallback_rail": fallback_rail,
        # Outcome
        "scenario": scenario,
        "is_settled": is_settled,
        "is_timeout": is_timeout,
        "is_partial": is_partial,
        "is_early_repay": is_early,
        "settlement_amount_usd": round(settlement_amount_usd, 2),
        "shortfall_usd": round(shortfall_usd, 2),
        "repayment_triggered_by": repayment_triggered_by,
        "cancellation_metadata": {
            "is_adversarial": scenario == "RECALL_ATTACK",
            "message_type": "camt.056",
            "reason_code": "CUST"
        } if scenario == "RECALL_ATTACK" else None,
        # Latency
        "c5_handoff_latency_ms": round(c5_handoff_latency_ms, 2),
        "within_slo": within_slo,
        # Label (1 = problematic / write-off risk)
        "label": label,
        # Lineage
        "timestamp": float(funded_ts),
        "corpus_tag": "SYNTHETIC_CORPUS_C3",
        "generation_seed": record_idx,
    }


def generate_repayment_corpus(
    n_samples: int = 25_000,
    seed: int = 42,
) -> List[dict]:
    """Generate a synthetic C3 repayment scenario corpus.

    Parameters
    ----------
    n_samples:
        Number of loan scenarios to generate.  Default 25,000.
    seed:
        NumPy random seed for reproducibility.

    Returns
    -------
    List[dict]
        Each record represents one bridge-loan repayment scenario with
        realistic settlement rail, timing, and outcome labels.
    """
    rng = np.random.default_rng(seed=seed)
    t0 = time.perf_counter()

    records = [_generate_record(rng, i) for i in range(n_samples)]

    elapsed = time.perf_counter() - t0
    positive_count = sum(r["label"] for r in records)
    positive_rate = positive_count / n_samples if n_samples > 0 else 0.0

    # Log summary (matches DGEN format for consistency)
    print(
        f"[C3] Generated {n_samples:,} records in {elapsed:.2f}s "
        f"| positive_rate={positive_rate:.3f} "
        f"| timeout={sum(r['is_timeout'] for r in records):,} "
        f"| partial={sum(r['is_partial'] for r in records):,}"
    )

    return records
