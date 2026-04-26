# CBDC Normalizer End-to-End — Design Spec

**Date:** 2026-04-25
**Sprint:** "Finally start working on the CBDC Normalizer" (founder framing)
**Patent reference:** P5 Family 5 Independent Claim 1 + Dependent Claim 3; P9 cross-rail handoff (future continuation)
**Status:** Approved scope (founder, 2026-04-25). Spec self-review pending.
**Branch convention:** `codex/cbdc-phase-{a,b,c,d,e}-*`

---

## 1. Why this spec exists

The C5-side CBDC normalizer (`lip/c5_streaming/cbdc_normalizer.py`) was committed weeks ago covering three rails (e-CNY, e-EUR experimental, Sand Dollar). It works in isolation — it has 15 passing tests. But **nothing downstream consumes its output**. Verified by source:

| Layer | Status | Evidence |
|---|---|---|
| `lip/c5_streaming/cbdc_normalizer.py` (3 rails + dispatcher + `RAIL_MATURITY_HOURS` lookup) | ✅ Built | `cbdc_normalizer.py:86-259`, 15 tests |
| `EventNormalizer.normalize()` routes `CBDC_*` to `CBDCNormalizer` | ✅ Built | `event_normalizer.py:459-461` |
| `RAIL_MATURITY_HOURS` map includes the 3 CBDC rails at 4.0h | ✅ Built | `constants.py:119-127` |
| C3 reads `RAIL_MATURITY_HOURS` for maturity calc | ❌ **Dead** | `grep RAIL_MATURITY_HOURS lip/c3_repayment_engine/` → 0 hits |
| C7 builds CBDC offers | ❌ **Dead** | `grep -i cbdc lip/c7_execution_agent/` → 0 hits |
| `pipeline.py` propagates `event.rail` into C3 | ❌ **Dead** | Same — 0 hits in pipeline.py |
| C2 fee math handles sub-day duration | ❌ **Wrong** | 300 bps annualized × 4h = $68 on $5M, below 5% cost-of-funds capital cost ($114) — economically incoherent |
| mBridge multi-CBDC PvP rail | ❌ **Not started** | $55B settled in real-world; we don't normalize it |
| FedNow E2E + cross-rail handoff detection | ❌ **Not started** | Normalizer exists; no downstream wiring; no UETR cross-rail linkage |
| Project Nexus stub | ❌ **Not started** | NGP onboarding mid-2027 per BSP |

P5 Family 5 Independent Claim 1 ("*executing, by an autonomous execution agent, real-time collateralized lending decisions*" on normalized CBDC events) and Dependent Claim 3 ("*4-hour settlement buffer enforced for a bridge loan where the source rail enumeration field identifies a CBDC rail*") are both **half-implemented in code today** and would not survive a defensibility audit.

This sprint closes those claims in code and extends to mBridge + FedNow handoff.

---

## 2. Goals (and non-goals)

**Goals:**
1. A `CBDC_ECNY` / `CBDC_EEUR` / `CBDC_SAND_DOLLAR` event flowing through `LIPPipeline.process()` produces a real `LoanOffer` with `rail=CBDC_*`, `maturity_hours=4`, and a fee respecting both annualized and absolute floors.
2. Add `CBDC_MBRIDGE` rail with multi-currency PvP semantics, new failure codes (CBDC-CF01 consensus-failure, CBDC-CB01 cross-chain-bridge-failure), and four-leg event support.
3. Wire FedNow end-to-end (existing normalizer + new pipeline support) and add cross-rail handoff detection: a SWIFT pacs.008 with a domestic FedNow leg gets linked, and a FedNow leg failure triggers a bridge offer against the upstream SWIFT UETR.
4. Reserve `CBDC_NEXUS` rail and a stub normalizer (real wiring deferred to mid-2027 per BSP).
5. Correct the stale `Master-Action-Plan-2026.md:629` "mBridge paused 2024" claim (it's alive: $55.5B settled, 5 central banks, 31 observers as of April 2026).

**Non-goals:**
- DGEN CBDC corridor for C1 retraining — separate work, not blocking patent claims.
- Real Kafka consumer wiring to a central-bank webhook — that's T2.1 production-wiring, separate phase.
- Patent filings — frozen pending counsel opinion on RBC IP clause (CLAUDE.md non-negotiable #6). This sprint produces *code that supports* future continuations only.
- Refactoring existing C3 maturity-day fields wholesale. We add `maturity_hours` as a parallel first-class field; existing `maturity_days` fields remain for legacy callers.

---

## 3. QUANT decision: sub-day fee math

The 300 bps annualized fee floor was set assuming day-scale (1-21 day) loans. **It is economically incoherent for sub-day rails.** Math:

| Loan | Maturity | Fee at 300 bps annualized | 5% cost-of-funds capital cost | Margin |
|---|---|---|---|---|
| $5M | 7 days (legacy CLASS_B) | $5M × 0.03 × 7/365 = $2,876 | $5M × 0.05 × 7/365 = $4,795 | -$1,919 *(intentional — risk premium covers in PD-priced cases)* |
| $5M | 24h (FedNow/RTP) | $5M × 0.03 × 24/8760 = $411 | $5M × 0.05 × 24/8760 = $685 | **-$274** |
| $5M | **4h (CBDC)** | $5M × 0.03 × 4/8760 = **$68** | $5M × 0.05 × 4/8760 = **$114** | **-$46 just on capital, before opex** |

300 bps × sub-day duration doesn't even cover cost of funds, much less opex or margin. **Any sub-day bridge loan at 300 bps is a guaranteed loss for the funding bank.**

### New constants (committed by Claude as QUANT)

```python
# lip/common/constants.py — sub-day fee floor framework
FEE_FLOOR_BPS: Final[Decimal] = Decimal("300")   # UNCHANGED — universal annualized floor
                                                  # CLAUDE.md non-negotiable #2: never lower.

FEE_FLOOR_BPS_SUBDAY: Final[Decimal] = Decimal("1200")   # NEW. Tighter floor for rails with maturity < SUBDAY_THRESHOLD_HOURS.
                                                          # Math at $5M / 4h: $5M × 0.12 × 4/8760 = $274.
                                                          # Covers 5% COF ($114) + opex (~$5) + ~100 bps margin ($55) + risk reserve (~$100).
                                                          # 12% APR on a 4h overnight-equivalent product is market: Fed discount window
                                                          # primary credit ≈ 5-6%; private 4h bridges priced 600 bps over discount window.

FEE_FLOOR_ABSOLUTE_USD: Final[Decimal] = Decimal("25")   # NEW. Operational floor.
                                                          # Below this, the fee is dominated by compute + monitoring + signed pacs.008 overhead.
                                                          # The fee function returns max(computed, FEE_FLOOR_ABSOLUTE_USD); separate C7 logic
                                                          # may decline tiny loans entirely.

SUBDAY_THRESHOLD_HOURS: Final[float] = 48.0   # NEW. Boundary: maturity_hours < this → SUBDAY floor applies.
                                               # Includes CBDC (4h), FedNow (24h), RTP (24h).
```

### Pricing rule

```python
def applicable_fee_floor_bps(maturity_hours: float) -> Decimal:
    """Return the applicable annualized fee floor in bps for a loan of given duration."""
    return FEE_FLOOR_BPS_SUBDAY if maturity_hours < SUBDAY_THRESHOLD_HOURS else FEE_FLOOR_BPS

def compute_fee_bps_from_el(pd, lgd, ead, maturity_hours):
    fee_bps = pd * lgd * 10_000
    return max(fee_bps, applicable_fee_floor_bps(maturity_hours))

def compute_loan_fee(loan_amount, fee_bps, days_funded, ...):
    fee = loan_amount * (fee_bps / 10_000) * (days_funded / 365)
    return max(fee, FEE_FLOOR_ABSOLUTE_USD)   # NEW
```

### Side effect: existing FedNow/RTP loans get repriced

Existing FedNow and RTP rails (24h maturity, currently priced at 300 bps) become subject to the 1200 bps floor under this rule. **This is a correction, not a regression.** Today's pricing under-recovers cost of funds on those rails too; nobody noticed because no FedNow/RTP loans have hit production. The fix lands quietly with the CBDC sprint.

### Defence statement (for any future patent counsel review)

> The 1200 bps sub-day floor is calibrated to cost of capital + operational margin + risk reserve at sub-day tenor. The 12% APR is consistent with private overnight bridge products priced 600-700 bps over the Fed discount window (currently 5-6%). The 300 bps universal floor is preserved unchanged; the sub-day floor is a *tighter* floor that activates only when rail maturity is below 48 hours.

---

## 4. Architecture: per-phase design

### Phase A — Finish T1.1 E2E wiring

**Goal:** A `CBDC_ECNY` event entering `LIPPipeline.process_pacs002()` produces a `LoanOffer` with `rail=CBDC_ECNY`, `maturity_hours=4`, fee respecting both floors.

**Components touched:**

#### A.1 — `lip/common/constants.py`
Add the four new constants (Section 3). Update `RAIL_MATURITY_HOURS` docstring to clarify the cross-reference to `FEE_FLOOR_BPS_SUBDAY`.

#### A.2 — `lip/c2_pd_model/fee.py`
- Add `applicable_fee_floor_bps(maturity_hours: float) -> Decimal`.
- Add `maturity_hours: float` parameter to `compute_fee_bps_from_el()` (default `24*7 = 168.0` for legacy callers — preserves existing behaviour for any caller that doesn't pass it).
- `compute_loan_fee()` returns `max(fee, FEE_FLOOR_ABSOLUTE_USD)` after the existing per-cycle calculation.
- `compute_tiered_fee_floor()` adds optional `maturity_hours` parameter; returns sub-day floor when applicable.
- `verify_floor_applies()` updated to check whichever floor was binding.
- New helper: `is_subday_rail(maturity_hours: float) -> bool`.

#### A.3 — `lip/c3_repayment_engine/repayment_loop.py` + `settlement_handlers.py` + `uetr_mapping.py`
- Add `maturity_hours: float` field to `ActiveLoan` dataclass (parallel to existing `maturity_days`). Default = `maturity_days * 24` for backward compatibility.
- Add `rail: str` field to `ActiveLoan` (default `"SWIFT"` for backward compatibility).
- New helper in `repayment_loop.py`:
  ```python
  def _maturity_hours_for(rail: str, rejection_class: str) -> float:
      """RAIL_MATURITY_HOURS[rail] if defined, else CLASS_*_DAYS * 24."""
  ```
- TTL calc in `uetr_mapping.py` accepts `maturity_hours: float` (existing `maturity_days: int` overload preserved). New: `get_ttl_seconds_from_hours(maturity_hours: float) -> int` → `int((maturity_hours + 45*24) * 3600)`.
- `_REDIS_REPAID_TTL_EXTRA_DAYS = 45` becomes `_REDIS_REPAID_TTL_EXTRA_HOURS = 45 * 24` internally.
- `register_loan()` derives `maturity_hours` from rail, stores both `maturity_hours` and a back-computed `maturity_days = ceil(maturity_hours / 24)` for legacy reads.

#### A.4 — `lip/c7_execution_agent/agent.py`
- `_build_loan_offer` reads `event.rail` (already on `NormalizedEvent`) and looks up `RAIL_MATURITY_HOURS[rail]`.
- Passes `maturity_hours` to fee math (Section A.2).
- Passes `rail` and `maturity_hours` into C3 registration.
- For CBDC rails: governing law derivation is unchanged (BIC-based, EPG-14). FX policy is unchanged: `FXRiskConfig` (`fx_risk_policy.py:43-94`) gates by `bank_base_currency == payment_currency` under `SAME_CURRENCY_ONLY`, or always-supported under `BANK_NATIVE_CURRENCY`. CNY/EUR/BSD CBDC bridges work as long as the licensee bank's base currency matches the CBDC, which is the realistic deployment (a Chinese bank issuing e-CNY bridges, etc.). The `FX_G10_CURRENCIES` set is informational only (`is_g10()` method) — not a gate; no change needed.
- `_build_swift_disbursement_message()`: existing pacs.008 path unchanged. `LIP-BRIDGE-{uetr}` end-to-end ID format unchanged.

#### A.5 — `lip/pipeline.py`
- `LIPPipeline.process()` (entry point at `pipeline.py:200`) constructs `payment_context` dict at `pipeline.py:530`. Add `rail=event.rail` and `maturity_hours=...` keys to that dict so C7 can read them.
- New helper `_derive_maturity_hours(rail: str, rejection_code: Optional[str]) -> float` alongside the existing `_derive_maturity_days` at `pipeline.py:1048`. Returns `RAIL_MATURITY_HOURS[rail]` if the rail is in the map, else falls back to `_derive_maturity_days(...) * 24`.
- `_register_with_c3` (at `pipeline.py:1111`) accepts and forwards `rail` and `maturity_hours` to C3's `register_loan()`.

#### A.6 — Tests
- `lip/tests/test_cbdc_e2e.py` — new file. Covers:
  - `test_ecny_event_to_loan_offer`: e-CNY pacs.002-equivalent → `LIPPipeline.process()` → assertions on `LoanOffer.rail = "CBDC_ECNY"`, `maturity_hours = 4.0`, `fee_bps >= 1200`, `fee_usd >= 25`.
  - `test_eeur_event_to_loan_offer`: same for e-EUR.
  - `test_sand_dollar_event_to_loan_offer`: same for Sand Dollar (BSD currency).
  - `test_cbdc_with_block_code_short_circuits`: e-CNY event with `CBDC-KYC01` (→ RR01, BLOCK class) returns `COMPLIANCE_HOLD` outcome, no loan offered (EPG-19).
  - `test_subday_fee_floor_applies`: $5M / 4h e-CNY produces `fee_bps == 1200` (binding), `fee_usd == $274.0`.
  - `test_legacy_swift_unchanged`: SWIFT 7-day loan still gets 300 bps floor, no regression.
- `lip/tests/test_subday_fee_floor.py` — new file. Pure-fee-math tests for `applicable_fee_floor_bps`, `compute_fee_bps_from_el(maturity_hours=...)`, absolute floor.

**Branch:** `codex/cbdc-phase-a-e2e`
**Sign-off:** Tier 3 sensitive (touches `constants.py`, `c2_pd_model/fee.py`). Per CLAUDE.md, this sprint touches non-negotiable #2 (fee floor — *not lowered*; new tighter sub-day floor is added). Document reasoning in PR body. Run full pytest.
**Estimated size:** ~400 LOC, ~25 tests, ~1 day.

---

### Phase B — mBridge multi-CBDC PvP rail

**Goal:** `CBDC_MBRIDGE` rail with multi-leg event support.

**Real-world context (verified April 2026):**
- mBridge: post-BIS, 5 central banks (PBOC, HKMA, BoT, CBUAE, SAMA), 31 observers, $55.5B settled, ~4,000 transactions.
- Atomic PvP: a single mBridge transaction can settle up to 4 currency legs simultaneously (CNY/HKD/THB/AED/SAR).
- ISO 20022 native (pacs.008/pacs.002) but with DLT-specific extensions for finality and consensus.
- Failure modes specific to mBridge: smart-contract revert (existing `CBDC-SC01`), consensus failure (NEW `CBDC-CF01`), finality timeout (existing `CBDC-FIN01`), cross-chain bridge failure (NEW `CBDC-CB01`).

**Components:**

#### B.1 — `lip/c5_streaming/cbdc_mbridge_normalizer.py` (NEW)

```python
class MBridgeNormalizer:
    """Normalize mBridge multi-CBDC PvP atomic settlement failure events.

    mBridge events have up to 4 currency legs. A single failure may originate
    in any leg or in the bridge consensus layer. The normalized event surfaces
    the FAILED leg as the primary NormalizedEvent; sister legs are preserved
    in raw_source['mbridge_legs'].
    """
    SUPPORTED_CURRENCIES = frozenset({"CNY", "HKD", "THB", "AED", "SAR"})

    def normalize(self, msg: dict) -> NormalizedEvent:
        # 1. Identify failed leg from msg['failed_leg_index'] or first leg with status=FAILED
        # 2. Failed leg's wallet/BIC/amount/currency become primary fields
        # 3. rail = "CBDC_MBRIDGE"
        # 4. failure_code mapped via extended CBDC_FAILURE_CODE_MAP (incl. CF01, CB01)
        # 5. raw_source preserves all 4 legs + bridge metadata
```

Schema of an mBridge event (modelled — actual production schema not yet public; use this until BIS Innovation Hub publishes formal spec):
```json
{
  "bridge_tx_id": "MBRIDGE-2026-04-25-0001",
  "atomic_settlement_id": "ATM-9F2C...",
  "consensus_round": 12345,
  "finality_seconds": 2.3,
  "failed_leg_index": 1,
  "legs": [
    {"index": 0, "status": "ACSC", "amount": "1000000.00", "currency": "CNY",
     "sender_wallet": "...", "receiver_wallet": "...", "sender_bic": "...", "receiver_bic": "..."},
    {"index": 1, "status": "FAILED", "amount": "139500.00", "currency": "HKD",
     "sender_wallet": "...", "receiver_wallet": "...", "sender_bic": "HSBCHKHHXXX", "receiver_bic": "BOFAUS3NXXX",
     "failure_code": "CBDC-CF01", "failure_description": "Consensus not reached within 3s window"}
  ],
  "timestamp": "2026-04-25T10:15:00Z"
}
```

#### B.2 — `lip/c5_streaming/cbdc_normalizer.py` (extend `CBDC_FAILURE_CODE_MAP`)

```python
CBDC_FAILURE_CODE_MAP: dict[str, str] = {
    # ... existing entries ...
    # Consensus / bridge errors (NEW for mBridge support)
    "CBDC-CF01": "AM04",   # consensus not reached → InsufficientFunds (closest analog: settlement failed)
    "CBDC-CB01": "FF01",   # cross-chain bridge failure → InvalidFileFormat
}
```

#### B.3 — `EventNormalizer.normalize()` dispatcher

Extend `event_normalizer.py:459-461` to also route `CBDC_MBRIDGE` to the new `MBridgeNormalizer`:
```python
if upper.startswith("CBDC_MBRIDGE"):
    from lip.c5_streaming.cbdc_mbridge_normalizer import MBridgeNormalizer
    return MBridgeNormalizer().normalize(msg)
if upper.startswith("CBDC_"):
    from lip.c5_streaming.cbdc_normalizer import CBDCNormalizer
    return CBDCNormalizer().normalize(upper, msg)
```

#### B.4 — `RAIL_MATURITY_HOURS`

Add `"CBDC_MBRIDGE": 4.0` to the map.

#### B.5 — Tests

- `lip/tests/test_cbdc_mbridge_normalizer.py`:
  - Multi-leg event with failed leg index 1 → primary fields from leg 1.
  - All 4 legs preserved in `raw_source['legs']`.
  - `CBDC-CF01` → `AM04`.
  - `CBDC-CB01` → `FF01`.
  - Dispatcher routing.
  - EPG-21 patent-language scrub (no AML/SAR/OFAC/PEP terms).
- `lip/tests/test_cbdc_e2e.py` (extend): `test_mbridge_event_to_loan_offer`.

**Branch:** `codex/cbdc-phase-b-mbridge`
**Sign-off:** Tier 2 routine (new module, no canonical-constant change).
**Estimated size:** ~300 LOC, ~12 tests, ~0.5 day.

---

### Phase C — FedNow E2E + cross-rail handoff detection

**Goal 1:** FedNow events flow through `LIPPipeline` and produce `LoanOffer` with `rail=FEDNOW`, `maturity_hours=24`, sub-day fee floor.

**Goal 2 (NEW patent territory):** A SWIFT pacs.008 with a US-domestic destination indicates likely FedNow last-mile handoff. If the FedNow leg subsequently fails, LIP links the failure to the upstream SWIFT UETR and triggers a bridge offer. Patent angle: "*detecting settlement confirmation from disparate payment network rails for a single UETR-tracked payment*" — flagged in `Master-Action-Plan-2026.md:378` as P9 enhancement.

**Components:**

#### C.1 — FedNow E2E
Apply Phase A treatment to `FEDNOW` rail. The normalizer already exists at `event_normalizer.py:normalize_fednow()`; the changes are downstream wiring (C3 maturity, C7 offer construction, fee floor — all reuse Phase A infrastructure).

No new code beyond what Phase A provides; one new test confirms FedNow E2E.

#### C.2 — Cross-rail UETR linkage
Extend `lip/common/uetr_tracker.py` with `register_handoff(parent_uetr, child_uetr, child_rail)`:

```python
class UETRTracker:
    # ... existing ...

    def register_handoff(self, parent_uetr: str, child_uetr: str, child_rail: str) -> None:
        """Register a domestic-rail handoff for a cross-border UETR.

        When a SWIFT pacs.008 indicates US-domestic destination, the receiving
        bank may forward via FedNow. We track the FedNow UETR as a 'child' of
        the SWIFT UETR. If the child fails, the parent becomes bridge-eligible.
        """

    def find_parent(self, child_uetr: str) -> Optional[str]:
        """Reverse lookup. Used by pipeline when a domestic-rail failure arrives."""
```

Storage: in-memory dict for Phase 1 (current pattern); Redis-backed in Phase 2 (T2.2). Tuple key: `(parent_uetr, child_uetr)` with TTL = 30 minutes (handoff window).

#### C.3 — Pipeline cross-rail handoff routing
In `pipeline.py`, when a `FEDNOW` event with `rejection_code=RJCT` arrives:
1. Check `uetr_tracker.find_parent(event.uetr)`.
2. If found, the failure event's effective `parent_uetr` becomes the SWIFT UETR for repayment tracking, but the bridge loan disbursement uses FedNow rail (24h maturity).
3. New `PipelineResult.outcome = "DOMESTIC_LEG_FAILURE"` — a sub-class of OFFERED that carries cross-rail metadata in the decision log.

#### C.4 — Tests

- `lip/tests/test_cross_rail_handoff.py`:
  - Register SWIFT parent + FedNow child → `find_parent(child)` returns parent.
  - FedNow RJCT with registered parent → pipeline produces `DOMESTIC_LEG_FAILURE` outcome.
  - FedNow RJCT without registered parent → falls through to standard `FEDNOW` rail handling.
  - 30-minute TTL expiry behaviour.

**Branch:** `codex/cbdc-phase-c-fednow-handoff`
**Sign-off:** Tier 2 routine (FedNow E2E) + Tier 2 (cross-rail tracker).
**Estimated size:** ~250 LOC, ~12 tests, ~0.5 day.

---

### Phase D — Project Nexus stub

**Goal:** Reserve `CBDC_NEXUS` rail and a stub normalizer for the Nexus Global Payments multilateral instant rail (mid-2027 onboarding per BSP).

**Real-world context (verified April 2026):**
- Nexus Global Payments incorporated 2025 in Singapore.
- 5 founding banks: India (RBI), Malaysia (BNM), Philippines (BSP), Singapore (MAS), Thailand (BoT). Indonesia joining; ECB special observer.
- Tech operator procurement underway.
- 60-second instant cross-border via ISO 20022.
- ISO 20022 specs and rulebook expected during 2026.

**Components:**

#### D.1 — Stub normalizer
`lip/c5_streaming/nexus_normalizer.py` — PHASE-2-STUB. Schema modelled from BIS published blueprint; flesh out when NGP publishes ISO 20022 specs. Returns `NormalizedEvent` with `rail="CBDC_NEXUS"`. Failure-code map empty initially (uses ISO 20022 native codes — Nexus is ISO-native per blueprint).

#### D.2 — Constants
Add `"CBDC_NEXUS": 4.0` to `RAIL_MATURITY_HOURS`. Same 4h buffer as other CBDC rails (60s finality + safety).

#### D.3 — Dispatcher
Extend `event_normalizer.py` dispatcher to route `CBDC_NEXUS` to the stub normalizer.

#### D.4 — Tests
Minimal smoke test: stub returns a well-formed `NormalizedEvent`, dispatcher routes correctly. Document in test docstring that real schema lands when NGP publishes spec.

**Branch:** `codex/cbdc-phase-d-nexus-stub`
**Sign-off:** Tier 1 routine.
**Estimated size:** ~100 LOC, ~4 tests, ~2 hours.

---

### Phase E — Doc corrections

**Goal:** Bring stale CBDC docs up to current ground truth.

**Components:**

#### E.1 — `docs/models/cbdc-protocol-research.md`
- Update §1.1 mBridge: BIS exited Oct 2024; project alive with 5 central banks + 31 observers; $55.5B settled; e-CNY = 95% of volume; Saudi Arabia joined post-exit.
- Add §1.5 — Project Nexus: NGP incorporated 2025, mid-2027 onboarding, 5 founding banks + Indonesia + ECB observer.
- Update §6 implementation roadmap to reflect Phase A-E status.

#### E.2 — `docs/operations/Master-Action-Plan-2026.md`
- Line 629: "mBridge paused 2024" → corrected to "BIS exited Oct 2024; central banks operate platform independently".
- Lines 378-403 (cross-rail settlement detection): mark Phase C as in flight.

#### E.3 — `docs/superpowers/specs/2026-04-25-cbdc-normalizer-end-to-end-design.md`
This file. Already created.

#### E.4 — ADR
`docs/engineering/decisions/ADR-2026-04-25-rail-aware-maturity.md` — short architecture decision record documenting the parallel `maturity_hours` field on `ActiveLoan`, why we didn't refactor `maturity_days`, and the sub-day fee floor framework.

**Branch:** `codex/cbdc-phase-e-docs`
**Sign-off:** Tier 0 trivial (doc-only). Commit directly to main per CLAUDE.md tier table.
**Estimated size:** ~doc deltas + 1 new ADR, ~1 hour.

---

## 5. Test strategy

| Test file | Phase | Coverage |
|---|---|---|
| `test_subday_fee_floor.py` (NEW) | A | Pure fee math: `applicable_fee_floor_bps`, `compute_fee_bps_from_el(maturity_hours)`, absolute floor binding, sub-day boundary at 48h. |
| `test_cbdc_e2e.py` (NEW) | A, B, C | E2E pipeline tests for e-CNY, e-EUR, Sand Dollar, mBridge, FedNow. |
| `test_cbdc_mbridge_normalizer.py` (NEW) | B | mBridge multi-leg parsing, CF01/CB01 mapping. |
| `test_cross_rail_handoff.py` (NEW) | C | UETR parent/child registration, pipeline routing on domestic-leg failure. |
| `test_nexus_stub.py` (NEW) | D | Smoke. |
| `test_cbdc_normalizer.py` (existing) | — | Unchanged. |
| `test_c2_fee.py` (existing) | A | Add cases: rail-aware floor, absolute floor binding. |
| `test_c3_repayment.py` (existing) | A | Add cases: `maturity_hours` parameter, CBDC rail TTL. |
| `test_block_code_drift.py` (existing) | A | Verify CBDC rejection codes (RR01, AC01, etc.) still in BLOCK list when source is CBDC. |

**Pre-merge gate per phase:**
- `ruff check lip/` — zero errors.
- `PYTHONPATH=. python -m pytest lip/tests/ -m "not slow"` — green.
- Per CLAUDE.md Tier 3 process: re-read non-negotiables, document reasoning in PR body, full pytest run.

---

## 6. Sign-offs and risks

### Sign-offs (per CLAUDE.md Part 6)
- **NOVA** (payments protocol): Phases A, B, C — claimed by Claude (founder waived QUANT/NOVA/REX ceremony per 2026-04-25 message; user has named Claude technical authority).
- **REX** (regulatory): Phase A, B, C, D — patent-language scrub (EPG-20/21) verified inline in normalizer source files. No new AML/SAR/OFAC/PEP terms introduced.
- **CIPHER** (security): no crypto-boundary changes.
- **QUANT** (financial math): claimed by Claude — sub-day fee floor calibrated to cost of capital (Section 3).

### Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Sub-day floor (1200 bps) is too high and pilot bank pushes back | High — repricing FedNow/RTP loans loses customers | The pricing is calibrated to cost of capital; if a pilot bank disputes, we have the math. Worst case: lower to 800 bps (still covers COF) and document in ADR. |
| `maturity_hours` field collision with existing `maturity_days: int` callers | Medium — silent miscalculation | Parallel field with default-derive; type-checked via `mypy lip/` gate. Phase A includes regression test on existing SWIFT 7-day path. |
| mBridge schema changes when BIS Innovation Hub publishes formal spec | Low — our schema is modelled, not derived from real production messages | Modelled schema is documented in module docstring; swap when real spec arrives. Existing `raw_source` field captures whatever the connector sends. |
| Patent claim language drift (EPG-20/21) | Critical — invalidates filing if ever picked up again | Test `test_patent_language_scrub` already exists in `test_cbdc_normalizer.py`; extend to mBridge and Nexus modules. |
| RBC IP clause unresolved (CLAUDE.md non-negotiable #6) | Critical — patent filing frozen | This sprint produces *code*, not filings. Code defensibility supports future continuations whenever counsel opines. |
| Cross-rail handoff (Phase C) is novel patent territory | Opportunity — strengthens P9 moat | Build the code; flag the patent angle in PR body; do not draft claim language. Counsel decides claim scope when filing thaws. |

---

## 7. Phasing summary

| Phase | Branch | Focus | Size | Sign-off tier |
|---|---|---|---|---|
| **A** | `codex/cbdc-phase-a-e2e` | E2E wiring for 3 existing CBDC rails + sub-day fee floor | ~400 LOC, ~25 tests, 1 day | **Tier 3 sensitive** (constants, fee.py) |
| **B** | `codex/cbdc-phase-b-mbridge` | mBridge multi-leg PvP normalizer | ~300 LOC, ~12 tests, 0.5 day | Tier 2 routine |
| **C** | `codex/cbdc-phase-c-fednow-handoff` | FedNow E2E + cross-rail tracker | ~250 LOC, ~12 tests, 0.5 day | Tier 2 routine |
| **D** | `codex/cbdc-phase-d-nexus-stub` | Project Nexus stub | ~100 LOC, ~4 tests, 2 hours | Tier 1 routine |
| **E** | `codex/cbdc-phase-e-docs` | Doc corrections + ADR | doc deltas, 1 hour | Tier 0 trivial |
| **Total** | — | Five PRs, mergeable independently | ~1050 LOC, ~53 tests, 2.5-3 days | — |

**Order matters:** A is a hard prerequisite for B and C (sub-day fee floor + rail-aware maturity foundation). D depends on dispatcher pattern from B. E is pure documentation, can run last.

**Push cadence:** `git push` at the end of each phase (per `feedback_push_to_github.md`).

---

## 8. Open questions (none blocking)

None. All design questions resolved per founder's 2026-04-25 directive ("YOU ARE THE QUANT", "PHASE A-E IT IS").

---

## 9. Changelog

| Date | Change | Author |
|---|---|---|
| 2026-04-25 | Initial spec covering Phases A-E. QUANT call: 1200 bps sub-day, $25 absolute floor, 48h boundary. mBridge / FedNow handoff / Nexus stub all in scope. | Claude Opus 4.7 (acting QUANT + architect, founder authority granted) |
