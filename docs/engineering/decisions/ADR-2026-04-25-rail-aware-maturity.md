# ADR 2026-04-25 — Rail-Aware Maturity and Sub-Day Fee Floor

**Status:** Accepted (Claude as architect, founder authority granted 2026-04-25)
**Context:** CBDC normalizer end-to-end sprint (Phases A-E)
**Spec:** `docs/superpowers/specs/2026-04-25-cbdc-normalizer-end-to-end-design.md`
**Plan:** `docs/superpowers/plans/2026-04-25-cbdc-normalizer-end-to-end.md`

## Decision

1. **Maturity:** Use `ActiveLoan.maturity_date: datetime` (already present)
   as the sole source of truth for loan duration. Add `ActiveLoan.rail: str`
   so `_claim_repayment` can branch on rail when computing TTL. C7
   `_build_loan_offer` reads `RAIL_MATURITY_HOURS[rail]` to set
   `maturity_date`; pipeline `_register_with_c3` sets the rail field on
   the resulting `ActiveLoan`.

2. **Fee floor framework:** Introduce a sub-day floor framework alongside
   the universal 300 bps floor:
   - `FEE_FLOOR_BPS = 300` (universal, unchanged — CLAUDE.md non-negotiable #2)
   - `FEE_FLOOR_BPS_SUBDAY = 1200` (rail maturity < 48h)
   - `FEE_FLOOR_ABSOLUTE_USD = 25` (operational floor, applied via
     `apply_absolute_fee_floor()` at C7 offer construction — NOT inside
     `compute_loan_fee()` so raw-math contract is preserved)
   - `SUBDAY_THRESHOLD_HOURS = 48.0` (boundary)

## Why not a parallel `maturity_hours` field on `ActiveLoan`?

Initial spec proposed adding `maturity_hours: float` parallel to
`maturity_days: int`. Inspection of `repayment_loop.py:35-62` showed
`maturity_date: datetime` already exists as the absolute reference; durations
can always be derived from `(maturity_date - funded_at)`. Adding a parallel
field doubled the surface for inconsistency without adding information.

## Why 1200 bps for sub-day?

Cost of capital math at $5M / 4h:
- Bank cost of funds (5% APR): $5M × 0.05 × 4/8760 = $114
- Operational cost: ~$5
- Profit margin (~100 bps): $55
- Risk reserve: ~$100
- **Total: ~$274**

1200 bps annualized × $5M × 4/8760 = $274. Exactly covers cost stack with
~100 bps margin. 12% APR is consistent with private overnight bridge products
priced 600-700 bps over the Fed discount window (currently 5-6%).

## Why $25 absolute floor?

Per-loan operational cost (compute + monitoring + signed pacs.008) is ~$5.
With ~100% margin: $10. With risk reserve for tiny loans where PD is hard to
estimate: $25. Below this, the loan is operationally underwater regardless
of fee bps — better to decline than to charge.

## Why a separate `apply_absolute_fee_floor()` instead of building it into `compute_loan_fee()`?

`compute_loan_fee` has a documented raw-math contract (Architecture Spec C2 §9):
`fee = loan_amount × (fee_bps / 10000) × (days_funded / 365)`. Test fixtures
exercise this with zero principal, zero days funded, and negative inputs to
verify edge-case correctness. Embedding `max(fee, 25)` inside the function
broke 10 pre-existing tests. The right factoring: keep the math pure,
apply the operational floor at the call site (C7) where economic semantics
matter.

## Trade-off: FedNow/RTP repricing

FedNow and RTP existing loans (24h maturity) get repriced from 300 bps
annualized to 1200 bps annualized under this rule. **This is a correction,
not a regression** — at 300 bps, FedNow/RTP also undercover cost of funds.
No production FedNow/RTP loans existed at the time of this ADR.

## Consequences

- C2 fee math gains a `maturity_hours` parameter (default 168h preserves
  legacy behaviour).
- C3 `_claim_repayment` gains optional `rail` parameter; computes
  hour-based TTL when rail is in `RAIL_MATURITY_HOURS`.
- C7 `_build_loan_offer` reads rail and computes `maturity_date` accordingly.
- Pipeline propagates `event.rail` and `maturity_hours` through
  `payment_context`.
- `pipeline._register_with_c3` uses hour-precision maturity for sub-day rails;
  legacy day-scale rails preserve the existing business-day calendar logic.

## Patent posture

This ADR supports P5 Family 5 Independent Claim 1 ("autonomous execution
agent makes real-time bridge decisions on normalized CBDC events") and
Dependent Claim 3 ("4-hour settlement buffer for CBDC rail"). No new claim
language drafted; filing remains frozen per CLAUDE.md non-negotiable #6.

## Authors

Claude Opus 4.7 (acting QUANT + architect, founder authority granted 2026-04-25).
