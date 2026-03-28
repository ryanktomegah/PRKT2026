# Sprint 3c — C2/C3/C5 Cascade Integration Design Spec

**Status:** Approved (CTO self-review)
**Sprint:** 3c of 23-session build program (Session 8)
**Prerequisites:** Sprint 3b (cascade propagation engine, intervention optimizer)
**Product:** P5 Supply Chain Cascade Detection & Prevention
**Blueprint Reference:** Sections 7.2 (C2), 7.3 (C3), 4.4 (C5 trigger)

---

## Problem Statement

Sprint 3b built the cascade propagation engine (BFS + CVaR) and intervention optimizer. But these components are standalone — they don't yet integrate with the existing LIP pipeline. Sprint 3c creates three integration bridges:

1. **C2 Cascade-Adjusted PD** — reduces bridge loan PD when the intervention prevents a larger cascade (makes coordinated intervention economically rational for the bank)
2. **C3 Cascade Settlement Trigger** — when a high-dependency payment fails in C3, evaluate whether the failure triggers a supply chain cascade
3. **C5 Stress-to-Cascade Bridge** — when C5 detects a corridor stress regime, identify affected corporates and run cascade propagation

---

## Design Principle: Additive, Not Invasive

Each integration is a **new function or class** added alongside existing code. No modifications to `compute_fee_bps_from_el()`, `RepaymentLoop`, or `StressRegimeDetector`. This preserves all 1700+ existing tests.

---

## Component Design

### 1. C2 Cascade-Adjusted PD (`lip/c2_pd_model/fee.py`)

**New function** appended to fee.py — does NOT modify existing functions.

```python
def compute_cascade_adjusted_pd(
    base_pd: Decimal,
    cascade_probability: Decimal,
    cascade_value_prevented: Decimal,
    intervention_cost: Decimal,
) -> CascadeAdjustedPricing:
```

**Formula (blueprint Section 7.2):**
```
cascade_discount = min(CASCADE_DISCOUNT_CAP, cascade_value_prevented / (10 * intervention_cost))
cascade_adjusted_pd = base_pd * (1 - cascade_discount)
cascade_adjusted_fee_bps = max(FEE_FLOOR_BPS, compute_fee_bps_from_el(cascade_adjusted_pd, lgd, ead))
```

**Why the 10x divisor:** Conservative — prevents aggressive discounting on small interventions with large claimed cascade values. QUANT sign-off required.

**Return type: `CascadeAdjustedPricing`** — new dataclass in fee.py:
```python
@dataclass
class CascadeAdjustedPricing:
    base_pd: Decimal
    cascade_adjusted_pd: Decimal
    cascade_discount: Decimal
    base_fee_bps: Decimal
    cascade_adjusted_fee_bps: Decimal
    cascade_value_prevented: Decimal
    intervention_cost: Decimal
```

### 2. C3 Cascade Settlement Trigger (`lip/p5_cascade_engine/cascade_settlement_trigger.py`)

**New class** in P5 module — consumes C3 settlement failure events.

```python
class CascadeSettlementTrigger:
    def __init__(self, cascade_graph: CascadeGraph, bic_to_corporate: Dict[str, str]):
        ...

    def on_settlement_failure(
        self, sending_bic: str, receiving_bic: str, amount_usd: float, dependency_score: float
    ) -> Optional[CascadeAlert]:
        """Evaluate whether a settlement failure should trigger cascade analysis.

        Returns CascadeAlert if:
          1. dependency_score >= CASCADE_ALERT_DEPENDENCY_THRESHOLD (0.50)
          2. Both BICs resolve to known corporates
          3. Total cascade CVaR >= CASCADE_ALERT_THRESHOLD_USD ($1M)
        """
```

**Why in P5, not C3:** C3's responsibility is settlement monitoring and repayment. The cascade evaluation logic belongs in P5. C3 just calls `trigger.on_settlement_failure()` when it detects a failure on a high-dependency edge.

### 3. C5 Stress-to-Cascade Bridge (`lip/p5_cascade_engine/stress_cascade_bridge.py`)

**New class** in P5 module — bridges C5 StressRegimeEvent to P5 propagation.

```python
class StressCascadeBridge:
    def __init__(self, cascade_graph: CascadeGraph, budget_usd: float):
        ...

    def on_stress_regime_event(self, event: StressRegimeEvent) -> List[CascadeAlert]:
        """Triggered by C5 StressRegimeEvent.

        1. Find all corporates with payment volume on the stressed corridor
        2. Run cascade propagation from each affected corporate
        3. Return alerts for corporates where CVaR >= threshold
        """
```

**Integration with CascadeGraph.get_corporates_on_corridor():** Sprint 3a left this as a stub. Sprint 3c implements it — requires storing corridor information on CorporateEdge or deriving it from the BIC graph.

CTO decision: Rather than modifying CorporateEdge (which would break Sprint 3a), the bridge accepts a `corridor_to_corporates` mapping built during entity resolution. This keeps the graph immutable.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `lip/c2_pd_model/fee.py` | Add CascadeAdjustedPricing + compute_cascade_adjusted_pd() |
| Create | `lip/p5_cascade_engine/cascade_settlement_trigger.py` | C3 failure → cascade evaluation |
| Create | `lip/p5_cascade_engine/stress_cascade_bridge.py` | C5 stress → cascade propagation |
| Modify | `lip/p5_cascade_engine/__init__.py` | Export new classes |
| Create | `lip/tests/test_c2_cascade_pricing.py` | Cascade-adjusted PD tests |
| Create | `lip/tests/test_p5_settlement_trigger.py` | Settlement failure trigger tests |
| Create | `lip/tests/test_p5_stress_bridge.py` | Stress-to-cascade bridge tests |

---

## Testing Strategy

- **C2 Cascade PD**: Discount formula, 30% cap, fee floor preserved, zero cascade = no discount, QUANT invariants (Decimal exactness)
- **C3 Settlement Trigger**: Below-threshold filtered, unmapped BIC excluded, alert generated for high-dependency failure, intra-corporate skipped
- **C5 Stress Bridge**: Corridor mapping, multiple corporates on same corridor, empty corridor returns no alerts
- **Regression**: All existing C2/C3/C5/P5 tests pass unchanged

---

## QUANT / CIPHER Review Notes

**QUANT:** Cascade discount formula uses 10x divisor (conservative). Fee floor (300 bps) is NEVER breached — `max(FEE_FLOOR_BPS, adjusted_fee)` enforced. CASCADE_DISCOUNT_CAP (0.30) limits maximum PD reduction. All arithmetic is Decimal with ROUND_HALF_UP.

**CIPHER:** No new PII exposure. Settlement trigger uses opaque corporate_id hashes. Stress bridge uses corridor identifiers (e.g., "EUR_USD"), not transaction-level data.
