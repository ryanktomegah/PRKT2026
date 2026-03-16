"""Canonical constants for LIP — Architecture Spec v1.2 Appendix A."""
from decimal import Decimal

# ── Market sizing (FXC Intelligence 2024) ─────────────────────────────────────
MARKET_SIZE_USD = 31_700_000_000_000          # $31.7T annual cross-border volume

# ── Failure-rate assumptions ──────────────────────────────────────────────────
FAILURE_RATE_CONSERVATIVE = Decimal("0.030")   # 3.0%
FAILURE_RATE_MIDPOINT     = Decimal("0.035")   # 3.5%
FAILURE_RATE_UPSIDE       = Decimal("0.040")   # 4.0%

# ── Fee parameters ────────────────────────────────────────────────────────────
FEE_FLOOR_BPS              = 300               # 300 bps annualized floor
FEE_FLOOR_PER_7DAY_CYCLE   = Decimal("0.000575")  # 0.0575% per 7-day cycle

# ── Latency targets ───────────────────────────────────────────────────────────
LATENCY_P50_TARGET_MS = 45   # Architecture Spec v1.2 — p50 inference budget
LATENCY_P99_TARGET_MS = 94   # Architecture Spec v1.2 — canonical end-to-end SLO

# ── ML performance targets ────────────────────────────────────────────────────
ML_BASELINE_AUC = Decimal("0.739")
ML_TARGET_AUC   = Decimal("0.850")

# ── Dispute classifier targets ────────────────────────────────────────────────
# FN rate measured on 100-case negation suite (20/category) with real LLM
# backend: qwen/qwen3-32b via Groq API (P6, 2026-03-16).
# MockLLMBackend baseline FN=47.2% (commit 3808a74 negation prefilter).
# Real LLM: FN=0.0% on DISPUTE_CONFIRMED, FP=4.0% on NOT_DISPUTE.
DISPUTE_FN_CURRENT = Decimal("0.0000")  # LLM=qwen/qwen3-32b n=100
DISPUTE_FN_TARGET  = Decimal("0.02")    # target false-negative rate

# ── Corridor embedding dimensions ────────────────────────────────────────────
CORRIDOR_EMBEDDING_DIM = 128

# ── Model architecture ────────────────────────────────────────────────────────
GRAPHSAGE_OUTPUT_DIM      = 384
TABTRANSFORMER_OUTPUT_DIM = 88
COMBINED_INPUT_DIM        = GRAPHSAGE_OUTPUT_DIM + TABTRANSFORMER_OUTPUT_DIM  # 472

# ── Training hyper-parameters ─────────────────────────────────────────────────
ASYMMETRIC_BCE_ALPHA   = 0.7            # false negatives more costly
FBETA_BETA             = 2              # F2-optimal threshold
GRAPHSAGE_K_TRAIN      = 10            # neighbors during training
GRAPHSAGE_K_INFER      = 5             # neighbors during inference

# ── Maturity windows (days) by rejection-code class ──────────────────────────
MATURITY_CLASS_A_DAYS  = 3
MATURITY_CLASS_B_DAYS  = 7
MATURITY_CLASS_C_DAYS  = 21

# ── AML velocity limits ───────────────────────────────────────────────────────
AML_DOLLAR_CAP_USD          = 1_000_000     # per entity per 24 hr rolling window
AML_COUNT_CAP               = 100           # transactions per entity per 24 hr
BENEFICIARY_CONCENTRATION   = Decimal("0.80")  # >80% to single beneficiary triggers alert

# ── Retention ─────────────────────────────────────────────────────────────────
DECISION_LOG_RETENTION_YEARS = 7

# ── HPA thresholds ────────────────────────────────────────────────────────────
HPA_SCALE_OUT_QUEUE_DEPTH = 100
HPA_SCALE_IN_QUEUE_DEPTH  = 20

# ── Latency SLO ───────────────────────────────────────────────────────────────
LATENCY_SLO_MS = 94                       # ≤ 94ms end-to-end SLO (Architecture Spec v1.2)

# ── UETR TTL ──────────────────────────────────────────────────────────────────
UETR_TTL_BUFFER_DAYS = 45                 # buffer beyond maturity for UETR deduplication window

# ── Maturity — BLOCK class ────────────────────────────────────────────────────
MATURITY_BLOCK_DAYS = 0                   # BLOCK rejection class: no bridge loan, immediate close

# ── Corridor buffer window ─────────────────────────────────────────────────────
CORRIDOR_BUFFER_WINDOW_DAYS = 90          # rolling window for corridor risk / embedding lookback

# ── Platform royalty (BPI technology licensor fee) ────────────────────────────
PLATFORM_ROYALTY_RATE = Decimal("0.15")   # 15% of fee_repaid_usd → BPI technology licensor

# ── Salt rotation ─────────────────────────────────────────────────────────────
SALT_ROTATION_DAYS = 365                  # full rotation cycle (CIPHER: cross-licensee salts)
SALT_ROTATION_OVERLAP_DAYS = 30           # overlap window — old salt accepted during transition

# ── FX risk policy (GAP-12) ───────────────────────────────────────────────────
FX_G10_CURRENCIES: frozenset[str] = frozenset(
    {"USD", "EUR", "GBP", "JPY", "CAD", "CHF", "AUD", "NZD", "SEK", "NOK"}
)
FX_RISK_POLICY_DEFAULT = "SAME_CURRENCY_ONLY"  # conservative pilot default

# ── Stress regime detection ────────────────────────────────────────────────────
# QUANT sign-off required to change STRESS_REGIME_MULTIPLIER.
# Rationale: 3× baseline is consistent with BIS CPMI alert thresholds for
# corridor-level settlement failure spikes. See P3 design in plan file.
STRESS_REGIME_MULTIPLIER = 3.0   # 1h failure rate must exceed 24h baseline by this factor
STRESS_REGIME_MIN_TXNS   = 20    # minimum 1h transaction count for a valid stress signal
