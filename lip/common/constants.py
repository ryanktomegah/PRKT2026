"""Canonical constants for LIP — Architecture Spec v1.2 Appendix A."""
from decimal import Decimal

# ── Failure-rate assumptions ──────────────────────────────────────────
FAILURE_RATE_CONSERVATIVE = Decimal("0.030")   # 3.0%
FAILURE_RATE_MIDPOINT     = Decimal("0.035")   # 3.5%
FAILURE_RATE_UPSIDE       = Decimal("0.040")   # 4.0%

# ── Credit tier boundaries (annualised fee bps) ──────────────────────
# Used in portfolio_router._tier_from_fee_bps to classify loans by credit tier.
# Tier 1: 300–539 bps  (investment-grade, listed)
# Tier 2: 540–899 bps  (private company, balance-sheet data)
# Tier 3: 900+ bps     (thin file)
CREDIT_TIER_2_MIN_BPS = 540   # lower boundary for Tier 2 (inclusive)
CREDIT_TIER_3_MIN_BPS = 900   # lower boundary for Tier 3 (inclusive)

# ── Fee parameters ────────────────────────────────────────────────────
FEE_FLOOR_BPS              = Decimal("300")    # 300 bps annualized floor (platform minimum - ALL loans)
FEE_FLOOR_PER_7DAY_CYCLE   = Decimal("0.000575")  # 0.0575% per 7-day cycle
# Warehouse eligibility threshold for SPV-funded loans (Phase 2/3). Loans priced below this
# rate are routed to bank balance sheet (BPI earns IP royalty only). Loans at or above
# this rate are warehouse-eligible and generate positive returns for BPI equity.
# At 800 bps minimum, asset yield = 8% annualized, which covers ~7% senior cost
# and leaves ~1% margin for BPI equity (55% share on Phase 2/3 SPV funding).
WAREHOUSE_ELIGIBILITY_FLOOR_BPS = 800    # minimum bps for SPV funding (ensures debt service)
# Maximum multiplier for conformal uncertainty fee adjustment (QUANT sign-off
# required to change). Caps the upward adjustment from prediction interval
# width so economically unreasonable fees are never issued.
CONFORMAL_UNCERTAINTY_MAX_MULTIPLIER = 2.0

# ── Latency targets ───────────────────────────────────────────────────
LATENCY_P50_TARGET_MS = 45   # Architecture Spec v1.2 — p50 inference budget
LATENCY_P99_TARGET_MS = 94   # Architecture Spec v1.2 — canonical end-to-end SLO

# ── C1 failure classifier ─────────────────────────────────────────────
# F2-optimal threshold (τ*) calibrated from 10M corpus retraining.
# Payments with failure_probability >= this threshold are flagged as
# above-threshold and eligible for loan offers.
# QUANT + ARIA must sign off on any change — affects offer volume and risk.
C1_FAILURE_PROBABILITY_THRESHOLD = 0.110

# ── ML performance targets ────────────────────────────────────────────
ML_BASELINE_AUC = Decimal("0.739")
ML_TARGET_AUC   = Decimal("0.850")

# ── C2 model scope limitations (EPG-06, EPG-14) ───────────────────────
# EPG-06: C2 models credit risk (probability of default on bridge loan
# principal) but does NOT model regulatory outcome risk — probability that
# an enforcement action, sanctions designation, or legal hold on borrower
# bank makes the loan uncollectable. Regulatory outcome risk requires a
# separate risk feature sourced from BPI's counterparty risk system; this is
# contractually gated on BPI license agreement amendment.  Until available, C2
# fee-bps should be viewed as a credit-risk floor, not a regulatory-risk price.
#
# EPG-14: C2 prices risk at correspondent bank (BIC) level — legal
# counterparty in MRFA. End-customer (debtor account) level PD is not
# modelled because LIP has no contractual relationship with, or data access to,
# bank's underlying originators.  The AML velocity granularity (EPG-28) was
# fixed independently at composite (BIC, debtor_account) key.
# BIC-level PD is correct by design for current MRFA structure.
#
# ── Dispute classifier targets ────────────────────────────────────────
# FN rate measured on 100-case negation suite (20/category) with real LLM
# backend: qwen/qwen3-32b via Groq API (P6, 2026-03-16).
# MockLLMBackend baseline FN=47.2% (commit 3808a74 negation prefilter).
# Real LLM: FN=0.0% on DISPUTE_CONFIRMED, FP=4.0% on NOT_DISPUTE.
DISPUTE_FN_CURRENT = Decimal("0.0000")  # LLM=qwen/qwen3-32b n=100
DISPUTE_FN_TARGET  = Decimal("0.02")    # target false-negative rate

# ── Corridor embedding dimensions ────────────────────────────────────
CORRIDOR_EMBEDDING_DIM = 128

# ── Model architecture ────────────────────────────────────────────────
GRAPHSAGE_OUTPUT_DIM      = 384
TABTRANSFORMER_OUTPUT_DIM = 88
COMBINED_INPUT_DIM        = GRAPHSAGE_OUTPUT_DIM + TABTRANSFORMER_OUTPUT_DIM  # 472

# ── Training hyper-parameters ─────────────────────────────────────────
ASYMMETRIC_BCE_ALPHA   = 0.7            # false negatives more costly
FBETA_BETA             = 2              # F2-optimal threshold
GRAPHSAGE_K_TRAIN      = 10            # neighbors during training
GRAPHSAGE_K_INFER      = 5             # neighbors during inference

# ── Maturity windows (days) by rejection-code class ──────────────────
MATURITY_CLASS_A_DAYS  = 3
MATURITY_CLASS_B_DAYS  = 7
MATURITY_CLASS_C_DAYS  = 21

# ── AML velocity limits ───────────────────────────────────────────────
# EPG-16: Default 0 = unlimited (no cap enforced). Retail $1M cap was inoperable
# at correspondent banking scale. Caps are set per-licensee via C8 token.
AML_DOLLAR_CAP_USD          = 0             # 0 = unlimited; set per-licensee via C8 token
AML_COUNT_CAP               = 0             # 0 = unlimited; set per-licensee via C8 token
BENEFICIARY_CONCENTRATION   = Decimal("0.80")  # >80% to single beneficiary triggers alert

# ── Retention ─────────────────────────────────────────────────────────
DECISION_LOG_RETENTION_YEARS = 7

# ── HPA thresholds ───────────────────────────────────────────────────
HPA_SCALE_OUT_QUEUE_DEPTH = 100
HPA_SCALE_IN_QUEUE_DEPTH  = 20

# ── Latency SLO ───────────────────────────────────────────────────────
# Alias for LATENCY_P99_TARGET_MS — kept for backward compatibility.
LATENCY_SLO_MS = LATENCY_P99_TARGET_MS   # ≤ 94ms end-to-end SLO (Architecture Spec v1.2)

# ── UETR TTL ──────────────────────────────────────────────────────────
UETR_TTL_BUFFER_DAYS = 45                 # buffer beyond maturity for UETR deduplication window

# ── Maturity — BLOCK class ────────────────────────────────────────────
MATURITY_BLOCK_DAYS = 0                   # BLOCK rejection class: no bridge loan, immediate close

# ── CBDC rail maturity (P5 patent, differential maturity by rail) ────────────
# CBDC transactions achieve programmatic finality in minutes; the 4-hour buffer
# covers cross-chain interoperability delays and smart contract retry windows.
# Legacy rails use the existing CLASS_A/B/C day-based maturity via UETR TTL.
# NOVA sign-off required to change — affects settlement timing assumptions.
RAIL_MATURITY_HOURS: dict[str, float] = {
    "SWIFT": float(UETR_TTL_BUFFER_DAYS * 24),   # 1080h (45 days)
    "FEDNOW": 24.0,                                # same-day domestic
    "RTP": 24.0,                                   # same-day domestic
    "SEPA": float(UETR_TTL_BUFFER_DAYS * 24),     # 1080h (45 days)
    "CBDC_ECNY": 4.0,                             # PBoC e-CNY
    "CBDC_EEUR": 4.0,                             # ECB experimental e-EUR
    "CBDC_SAND_DOLLAR": 4.0,                      # CBB Sand Dollar
}

# ── Corridor buffer window ─────────────────────────────────────────────────────
CORRIDOR_BUFFER_WINDOW_DAYS = 90          # rolling window for corridor risk / embedding lookback

# ── Platform royalty (BPI technology licensor fee) ────────────────────────────
PLATFORM_ROYALTY_RATE = Decimal("0.30")   # 30% of fee_repaid_usd → BPI technology licensor

# ── Deployment phase fee shares (QUANT authority — do not change without sign-off) ─────────
# Phase 1 (Licensor): bank funds 100%, BPI earns IP royalty — 30% of fee
PHASE_1_BPI_FEE_SHARE              = PLATFORM_ROYALTY_RATE   # alias — canonical value is PLATFORM_ROYALTY_RATE
PHASE_1_INCOME_TYPE                = "ROYALTY"

# Phase 2 (Hybrid): 30% bank / 70% BPI capital. BPI earns co-lending return — 55% of fee
# Bank's 45% decomposes into capital return (30%) + distribution premium (15%)
PHASE_2_BPI_FEE_SHARE              = Decimal("0.55")
PHASE_2_BANK_CAPITAL_RETURN        = Decimal("0.30")   # proportional to bank's 30% capital
PHASE_2_BANK_DISTRIBUTION_PREMIUM  = Decimal("0.15")   # origination, compliance, correspondent
PHASE_2_INCOME_TYPE                = "LENDING_REVENUE"

# Phase 3 (Full MLO): BPI funds 100%. BPI earns gross lending revenue — 80% of fee
# Bank contributes 0% capital → capital return drops to 0%; keeps distribution premium 20%
PHASE_3_BPI_FEE_SHARE              = Decimal("0.80")
PHASE_3_BANK_CAPITAL_RETURN        = Decimal("0")      # bank contributes 0% capital
PHASE_3_BANK_DISTRIBUTION_PREMIUM  = Decimal("0.20")   # origination/compliance value
PHASE_3_INCOME_TYPE                = "LENDING_REVENUE"

# ── Salt rotation ─────────────────────────────────────────────────────
SALT_ROTATION_DAYS = 365                  # full rotation cycle (CIPHER: cross-licensee salts)
SALT_ROTATION_OVERLAP_DAYS = 30           # overlap window — old salt accepted during transition

# ── FX risk policy (GAP-12) ───────────────────────────────────────────
FX_G10_CURRENCIES: frozenset[str] = frozenset(
    {"USD", "EUR", "GBP", "JPY", "CAD", "CHF", "AUD", "NZD", "SEK", "NOK"}
)
FX_RISK_POLICY_DEFAULT = "SAME_CURRENCY_ONLY"  # conservative pilot default

# ── Settlement P95 targets by rejection class (data-derived, 2026-03-16) ──────
# Derived from 2M synthetic records in payments_synthetic.parquet (seed=42).
# Calibration source: BIS/SWIFT GPI Joint Analytics — confirmed at scale.
# These are canonical Tier 0 corridor buffer references (Architecture Spec S11.4).
# QUANT sign-off required before changing.
SETTLEMENT_P95_CLASS_A_HOURS = 7.05    # Routing/account errors          — BIS/SWIFT GPI target 7.0h
# EPG-19 (REX, 2026-03-18): CLASS_B label "Compliance/AML holds" was WRONG.
# CLASS_B covers systemic/processing delays only. Compliance-hold payments
# (DNOR, CNOR, RR01-RR04, AG01, LEGL) are never bridged — they are BLOCK class.
# This constant must NOT be used to calibrate compliance-hold resolution time.
# QUANT + REX must align before this label or value is changed.
SETTLEMENT_P95_CLASS_B_HOURS = 53.58   # Systemic/processing delays      — BIS/SWIFT GPI target 53.6h
SETTLEMENT_P95_CLASS_C_HOURS = 170.67  # Liquidity/sanctions/investigation — BIS/SWIFT GPI target 171.0h

# ── Loan amount thresholds by rejection class (QUANT-controlled) ──────────────
# Class-aware minimums replace to flat MIN_LOAN_AMOUNT_USD gate.
# Rationale (NOVA + QUANT, 2026-03-17):
#   Class A (3d): P95 resolution = 7.05h — loan matures 10x before to problem resolves.
#     Early repayment destroys yield; only large principals generate sufficient fee to
#     cover expected-loss risk. Breakeven at 400bps/3d = $1,520,833 → rounded to $1.5M.
#   Class B (7d): compliance holds run close to full term. Breakeven at 400bps/7d =
#     $651,786 → rounded up to $700K.
#   Class C (21d): liquidity/sanctions holds almost always run to maturity.
#     $500K clears fee floor at 400bps/21d ($1,150+). No change.
MIN_LOAN_AMOUNT_CLASS_A_USD = Decimal("1500000")  # Class A (routing errors, 3-day maturity)
MIN_LOAN_AMOUNT_CLASS_B_USD = Decimal("700000")   # Class B (compliance holds, 7-day maturity)
MIN_LOAN_AMOUNT_CLASS_C_USD = Decimal("500000")   # Class C (liquidity/sanctions, 21-day maturity)
MIN_LOAN_AMOUNT_USD         = Decimal("500000")   # legacy default for backward compatibility only

def get_min_loan_amount(loan_class: str) -> Decimal:
    """Return the minimum loan amount for *loan_class*.

    Raises ValueError for unknown classes — silently defaulting to lowest
    tier would allow sub-threshold loans to slip through for unrecognised
    rejection classes.

    Parameters
    ----------
    loan_class:
        One of ``"A"``, ``"B"``, or ``"C"`` (case-sensitive).

    Raises
    ------
    ValueError
        If *loan_class* is not a recognised class.
    """
    _CLASS_MAP: dict = {
        "A": MIN_LOAN_AMOUNT_CLASS_A_USD,
        "B": MIN_LOAN_AMOUNT_CLASS_B_USD,
        "C": MIN_LOAN_AMOUNT_CLASS_C_USD,
    }
    if loan_class not in _CLASS_MAP:
        raise ValueError(
            f"Unknown loan class {loan_class!r}; expected one of {list(_CLASS_MAP)}. "
            "Silently defaulting to lowest tier is not permitted."
        )
    return _CLASS_MAP[loan_class]

# MIN_CASH_FEE_USD: coherent safety net at Class A boundary value.
# $500K × 400bps × 3/365 = $164.38 → rounded down to $150 with ~9% headroom.
# This is no longer to primary exclusion mechanism for Class A (the class-aware
# loan minimum handles that); it remains as a last-resort arithmetic guard.
MIN_CASH_FEE_USD            = Decimal("150")      # absolute minimum cash fee per cycle

# ── Tiered fee floors by principal (QUANT-controlled) ─────────────────
# Brackets: < $500K → 500 bps  | $500K–$2M → 400 bps  | ≥ $2M → 300 bps
# The ≥$2M tier uses to canonical FEE_FLOOR_BPS (300); no separate constant needed.
FEE_FLOOR_TIER_SMALL_BPS   = Decimal("500")   # principal < MIN_LOAN_AMOUNT_USD
FEE_FLOOR_TIER_MID_BPS     = Decimal("400")   # MIN_LOAN_AMOUNT_USD ≤ principal < FEE_TIER_MID_THRESHOLD_USD
FEE_TIER_MID_THRESHOLD_USD = Decimal("2000000")  # boundary: mid tier → canonical 300 bps floor

# ── Stress regime detection ────────────────────────────────────────────
# QUANT sign-off required to change STRESS_REGIME_MULTIPLIER.
# Rationale: 3× baseline is consistent with BIS CPMI alert thresholds for
# corridor-level settlement failure spikes. See P3 design in plan file.
STRESS_REGIME_MULTIPLIER = 3.0   # 1h failure rate must exceed 24h baseline by this factor
STRESS_REGIME_MIN_TXNS   = 20    # minimum 1h transaction count for a valid stress signal

# ── Partial settlement threshold (QUANT sign-off required) ──────────────────
# Below this fraction of principal, a partial settlement is treated as noise
# regardless of policy. Default: 10%.
PARTIAL_SETTLEMENT_MIN_PCT = Decimal("0.10")  # QUANT sign-off: 2026-03-21

# ── Amount validation tolerance (QUANT sign-off required) ───────────────────
# GAP-17: loan_amount vs original_payment_amount_usd comparison tolerance.
# Covers FX rounding in cross-currency corridors.
AMOUNT_VALIDATION_TOLERANCE_USD = Decimal("0.01")  # QUANT sign-off: 2026-03-21

# ── Conformal prediction (QUANT sign-off required) ─────────────────────────
# Default coverage level for split conformal prediction intervals.
# 90% = 1 in 10 observations may fall outside of interval.
CONFORMAL_COVERAGE_LEVEL = 0.90
# Fee uncertainty scaling factor: wider interval → higher fee (economically correct).
# adjusted_fee = baseline_fee * (1 + interval_width * UNCERTAINTY_SCALE_FACTOR)
CONFORMAL_UNCERTAINTY_SCALE_FACTOR = 0.5  # QUANT sign-off: 2026-03-26

# ── Portfolio risk thresholds (QUANT sign-off required) ─────────────────────
# HHI concentration limit (2500 = highly concentrated per DOJ/FTC guidelines)
PORTFOLIO_MAX_HHI = Decimal("2500")
# Single-name exposure limit (25% of total portfolio)
PORTFOLIO_MAX_SINGLE_NAME_PCT = Decimal("0.25")
# VaR confidence level
PORTFOLIO_VAR_CONFIDENCE = 0.99
# VaR horizon in days
PORTFOLIO_VAR_HORIZON_DAYS = 10

# ── Settlement time prediction (QUANT sign-off required) ───────────────────
# Safety margin applied to predicted settlement time for dynamic maturity
SETTLEMENT_SAFETY_MARGIN = 1.5
# Minimum dynamic maturity in hours
SETTLEMENT_MIN_MATURITY_HOURS = 12.0

# ── Cancellation detection (CIPHER sign-off required) ──────────────────────
# Window after funding within which a camt.056 recall is flagged as suspicious
CANCELLATION_SUSPICION_WINDOW_SECONDS = 300  # 5 minutes
# Sender recall frequency threshold (per 24h) for behavioral alert
CANCELLATION_SENDER_RECALL_THRESHOLD = 3

# ── P3 Platform Licensing — Processor constants (QUANT sign-off required) ───
# Take rate bounds: processor retains 15-30% of BPI's gross per-transaction fee
PROCESSOR_TAKE_RATE_MIN_PCT = Decimal("0.15")       # 15% floor
PROCESSOR_TAKE_RATE_MAX_PCT = Decimal("0.30")       # 30% ceiling
PROCESSOR_TAKE_RATE_WALKAWAY_PCT = Decimal("0.35")  # >35% = economics unviable

# Annual minimum per processor per year (P3 blueprint §3.2)
PROCESSOR_ANNUAL_MINIMUM_FLOOR_USD = Decimal("500000")    # $500K
PROCESSOR_ANNUAL_MINIMUM_CEILING_USD = Decimal("2000000")  # $2M

# Performance premium bounds (P3 blueprint §3.2)
PROCESSOR_PERFORMANCE_PREMIUM_MIN_PCT = Decimal("0.10")  # 10%
PROCESSOR_PERFORMANCE_PREMIUM_MAX_PCT = Decimal("0.25")  # 25%
PROCESSOR_PERFORMANCE_BASELINE_PCT = Decimal("0.80")     # 80% of projected annual volume

# Container lifecycle intervals (P3 blueprint §2.5)
CONTAINER_HEARTBEAT_INTERVAL_SECONDS = 60   # heartbeat to BPI telemetry endpoint
REVENUE_METERING_SYNC_INTERVAL_SECONDS = 300  # 5-minute revenue sync

# ── DGEN temporal spread (SR 11-7 out-of-time validation, B11-06) ────────────
# 18-month window: 2023-07-01 00:00:00 UTC → 2025-01-01 (approx).
# Named constant replaces magic literals across all DGEN generators.
DGEN_EPOCH_START: float = 1_688_169_600.0  # 2023-07-01 00:00:00 UTC
DGEN_EPOCH_SPAN: float = 18 * 30 * 86_400  # ~18 months in seconds

# ── C3 PaymentWatchdog stuck-payment detection ─────────────────────────────────
# Fallback TTL (seconds) for non-terminal states not listed in the per-state
# TTL dict. Equals 2× Class B 7-day maturity window.
# QUANT + NOVA sign-off required to change — affects PagerDuty alert volume.
C3_WATCHDOG_FALLBACK_TTL_SECONDS: float = 14 * 86_400  # 14 days

# Revenue shortfall alerting
REVENUE_SHORTFALL_ALERT_PCT = Decimal("0.50")  # alert when trailing 90d < 50% of annualized min

# ── P10 Regulatory Data Product — Privacy Architecture ───────────────────
# QUANT + CIPHER sign-off required to change any P10 privacy constant.
# Rationale: Dwork & Roth (2014) differential privacy; Sweeney (2002) k-anonymity.
P10_K_ANONYMITY_THRESHOLD = 5                      # minimum distinct banks per corridor/time-bucket
P10_DIFFERENTIAL_PRIVACY_EPSILON = Decimal("0.5")  # per-query privacy loss (Laplace mechanism)
P10_PRIVACY_BUDGET_PER_CYCLE = Decimal("5.0")      # total epsilon budget per 30-day cycle
P10_PRIVACY_BUDGET_CYCLE_DAYS = 30                 # budget reset interval
P10_TIMESTAMP_BUCKET_HOURS = 1                     # timestamp rounding granularity
P10_AMOUNT_BUCKETS = ("0-10K", "10K-100K", "100K-1M", "1M-10M", "10M+")  # amount tier labels
P10_AMOUNT_BUCKET_THRESHOLDS = (                   # upper bounds in USD for each bucket
    Decimal("10000"),
    Decimal("100000"),
    Decimal("1000000"),
    Decimal("10000000"),
)

# ── P10 Systemic Risk Engine — Contagion & Concentration ────────────────
# QUANT sign-off required to change any contagion/concentration constant.
P10_CONTAGION_PROPAGATION_DECAY = Decimal("0.7")    # per-hop stress multiplier
P10_CONTAGION_MAX_HOPS = 5                           # BFS depth limit
P10_CONTAGION_STRESS_THRESHOLD = Decimal("0.05")     # minimum stress to propagate
P10_HHI_CONCENTRATION_THRESHOLD = Decimal("0.25")    # "highly concentrated" marker
P10_TREND_RISING_THRESHOLD = Decimal("0.10")         # 10% relative increase = RISING
P10_TREND_WINDOW_PERIODS = 3                          # periods for trend comparison
P10_MAX_HISTORY_PERIODS = 720                         # 30 days × 24 hours

# ── P10 Sprint 6: Telemetry eligibility + circular exposure (QUANT sign-off) ─
P10_TELEMETRY_MIN_AMOUNT_USD = Decimal("1000")        # noise reduction: sub-$1K events excluded from P10 telemetry
P10_CIRCULAR_EXPOSURE_MIN_WEIGHT = Decimal("0.3")     # min dependency_score for circular exposure edge
P10_CIRCULAR_EXPOSURE_MAX_LENGTH = 5                   # max cycle hops (matches P10_CONTAGION_MAX_HOPS)

# ── Funding routing logic ─────────────────────────────────────────────────
# Determines whether a loan should be funded via SPV warehouse (Phase 2/3)
# based on fee rate and current deployment phase.
# Phase 1 (Licensor): All loans are bank-funded regardless of fee.
# Phase 2 (Hybrid): Loans >= 800 bps are SPV-warehouse-eligible.
# Phase 3 (Securitized): All loans are SPV-funded regardless of fee.
def is_spv_warehouse_eligible(fee_bps: Decimal, phase: str) -> bool:
    """
    Determine if a loan is eligible for SPV warehouse funding (Phase 2/3).

    Warehouse eligibility requires fee >= WAREHOUSE_ELIGIBILITY_FLOOR_BPS (800 bps).
    This ensures every warehouse-funded loan generates sufficient yield
    to service the SPV capital structure (senior ~7% + BPI equity share ~1%).

    Phase 1 (Licensor): Always returns False (bank funds all loans).
    Phase 2 (Hybrid): Returns True only when fee >= 800 bps.
    Phase 3 (Securitized): Always returns True (SPV funds all loans).

    Parameters
    ----------
    fee_bps : Annualized fee rate in basis points.
    phase : Current deployment phase ("phase_1", "phase_2", "phase_3").

    Returns
    -------
    bool : True if loan is SPV warehouse-eligible, False otherwise.
    """
    from decimal import Decimal

    fee_bps = Decimal(str(fee_bps))
    floor = Decimal(str(WAREHOUSE_ELIGIBILITY_FLOOR_BPS))

    if phase == "phase_1":
        return False  # Bank funds all loans in Phase 1

    # Phase 2 and 3 use SPV warehouse
    if phase in ("phase_2", "phase_3"):
        return fee_bps >= floor

    raise ValueError(f"Unknown phase: {phase}")
