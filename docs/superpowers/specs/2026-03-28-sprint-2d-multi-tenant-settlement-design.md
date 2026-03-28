# Sprint 2d — Multi-Tenant Settlement Tracking Design Spec

**Status:** Approved (CTO self-review)
**Sprint:** 2d of 23-session build program
**Prerequisites:** Sprint 2a (C8 processor tokens), 2b (C6 tenant velocity), 2c (C7 MIPLO gateway)
**Product:** P3 Platform Licensing

---

## Problem Statement

C3 settlement tracking is single-tenant by design. The RepaymentLoop, SettlementMonitor, and idempotency claims operate in a global namespace. After Sprints 2a-2c, payments enter the pipeline with TenantContext, get tenant-scoped AML velocity checks (C6), and tenant-tagged decision logs (C7) — but C3 has no tenant awareness. This means:

1. No per-tenant NAV snapshots (required by P3 blueprint §4.3)
2. No tenant-scoped portfolio queries for processor dashboards
3. No settlement→revenue metering link (the `repayment_callback` is a no-op logger)
4. Redis idempotency keys are globally namespaced

## Design Decision: Option C (Query-Time Filtering + Selective Redis Scoping)

**Rationale:** C3's internal data structures (active loan dicts) are keyed by UETR, which is globally unique by SWIFT UUID v4 specification. Full storage repartitioning (Option A) would require refactoring `trigger_repayment()` — the function containing fee waterfall arithmetic — creating regression risk in penny-exact financial math for no real safety gain. Option C adds tenant isolation at the boundaries (Redis keys, query APIs, revenue metering) without touching the fee path.

**What changes:**
- Redis idempotency keys gain tenant prefix
- New NAVEventEmitter background scheduler
- Settlement callback wired to RevenueMetering
- Tenant-scoped MIPLO portfolio endpoints

**What doesn't change:**
- RepaymentLoop._active_loans dict keying (loan_id → ActiveLoan)
- SettlementMonitor._active_loans dict keying (uetr → ActiveLoan)
- CorridorBuffer observations (rail-specific, not tenant-specific)
- UETRMappingTable (payment-specific, not tenant-specific)
- trigger_repayment() fee waterfall logic (QUANT-protected)

---

## Component Design

### 1. Redis Key Scoping (`repayment_loop.py`)

**Change:** `_claim_repayment()` gains optional `tenant_id` parameter.

**Key format:**
- Processor mode: `lip:{tenant_id}:repaid:{uetr}`
- Bank mode (no tenant): `lip:repaid:{uetr}` (unchanged, backward compatible)

**Source of tenant_id:** `loan.licensee_id` (already set on ActiveLoan at registration time via `_register_with_c3`, line 968 of pipeline.py — reads from `self._c7.licensee_id`).

**Call site change in `trigger_repayment()`:** The existing call `self._claim_repayment(loan.uetr, maturity_days)` becomes `self._claim_repayment(loan.uetr, maturity_days, tenant_id=loan.licensee_id)`. This is the only change to `trigger_repayment()` — the fee waterfall logic below is untouched.

**In-memory fallback:** `_repaid_uetrs` stays a flat set. UETR is globally unique — tenant scoping in Redis is defense-in-depth for key namespace hygiene in multi-processor deployments, not collision prevention.

### 2. NAVEventEmitter (`lip/c3_repayment_engine/nav_emitter.py` — new file)

**Responsibility:** Emit per-tenant NAVEvent snapshots every 60 minutes.

**Design:**
```
class NAVEventEmitter:
    def __init__(
        self,
        get_active_loans: Callable[[], List[ActiveLoan]],  # lazy getter, not RepaymentLoop
        nav_callback: Callable[[NAVEvent], None],
        interval_seconds: int = 3600,  # 60 minutes
        metrics_collector: Optional[PrometheusMetricsCollector] = None,
    )
```

**Why a lazy getter instead of RepaymentLoop:** Avoids a circular init dependency in app.py — RepaymentLoop requires the bridge as its callback, and the bridge requires the emitter. By accepting `repayment_loop.get_active_loans` (a bound method), the emitter can be constructed before RepaymentLoop exists, then wired via `repayment_loop.get_active_loans` after RepaymentLoop is constructed. See Section 6 for wiring order.

**Algorithm:**
1. Read `get_active_loans()` — snapshot all active loans
2. Group by `loan.licensee_id` — skip loans with empty licensee_id (bank-mode)
3. For each tenant:
   - `active_loans` = count of loans
   - `total_exposure_usd` = sum of principals
   - `settled_last_60min` = count from internal settlement history deque
   - `settled_amount_last_60min_usd` = sum from settlement history
   - `trailing_loss_rate_30d` = defaults written from settlement history (initially Decimal("0"))
4. Construct `NAVEvent` (frozen Pydantic model from schemas.py)
5. Invoke `nav_callback(nav_event)`
6. Update metrics: `METRIC_TENANT_ACTIVE_LOANS`, `METRIC_TENANT_EXPOSURE_USD`

**Settlement history tracking:**
- `record_settlement(tenant_id, amount, timestamp)` — called by settlement callback bridge
- Internal deque with 30-day rolling window, protected by `threading.Lock` (producer-consumer: bridge writes on RepaymentLoop thread, emitter reads on its own daemon thread)
- Used to compute `settled_last_60min` and `trailing_loss_rate_30d`
- `trailing_loss_rate_30d` initially returns `Decimal("0")` — real loss-rate computation requires default/loss event tracking which is out of scope for this sprint (Sprint 5 infrastructure)

**Threading:** Daemon thread with `threading.Event` for clean shutdown (same pattern as RepaymentLoop.run_monitoring_loop). Emitter's `stop()` method must be added to `_shutdown_hooks` in app.py for graceful shutdown.

### 3. Settlement Callback Bridge (`lip/c3_repayment_engine/settlement_bridge.py` — new file)

**Responsibility:** Replace the no-op repayment callback with a bridge that routes settlement events to:
1. `BPIRoyaltySettlement.record_repayment()` (existing — records BPI royalty share)
2. `RevenueMetering.record_transaction()` (new — records processor revenue split)
3. `NAVEventEmitter.record_settlement()` (new — feeds settlement history for NAV)

**Design:**
```
class SettlementCallbackBridge:
    def __init__(
        self,
        royalty_settlement: BPIRoyaltySettlement,
        revenue_metering: Optional[RevenueMetering] = None,
        nav_emitter: Optional[NAVEventEmitter] = None,
        platform_take_rate_pct: Optional[Decimal] = None,
    )

    def __call__(self, repayment_record: dict) -> None:
        # Always: record BPI royalty
        self.royalty_settlement.record_repayment(repayment_record)

        # Processor mode only: record revenue metering
        if self.revenue_metering and self.platform_take_rate_pct:
            tenant_id = repayment_record.get("licensee_id", "")
            if tenant_id:
                self.revenue_metering.record_transaction(
                    tenant_id=tenant_id,
                    uetr=repayment_record["uetr"],
                    gross_fee_usd=Decimal(repayment_record["fee"]),
                    platform_take_rate_pct=self.platform_take_rate_pct,
                )

        # NAV history tracking
        if self.nav_emitter:
            tenant_id = repayment_record.get("licensee_id", "")
            if tenant_id:
                self.nav_emitter.record_settlement(
                    tenant_id=tenant_id,
                    amount=Decimal(repayment_record["settlement_amount"]),
                    timestamp=datetime.fromisoformat(repayment_record["repaid_at"]),
                )
```

**Callable protocol:** The bridge implements `__call__` so it can be passed directly as RepaymentLoop's `repayment_callback` parameter.

### 4. Tenant-Scoped Portfolio Queries (`portfolio_router.py` extension)

**Change:** Add `get_tenant_nav()` method to `PortfolioReporter`.

```
def get_tenant_nav(self, tenant_id: str) -> dict:
    """Return NAVEvent-shaped data for a single tenant (synchronous query)."""
    loans = [l for l in self._loop.get_active_loans() if l.licensee_id == tenant_id]
    return {
        "tenant_id": tenant_id,
        "active_loans": len(loans),
        "total_exposure_usd": str(sum(l.principal for l in loans)),
        ...
    }
```

### 5. MIPLO Portfolio Endpoints (`miplo_router.py` + `miplo_service.py` extension)

**New endpoints** on existing `/miplo` prefix:
- `GET /miplo/portfolio/loans` — active loans for this processor's tenant
- `GET /miplo/portfolio/exposure` — exposure breakdown for this tenant
- `GET /miplo/portfolio/nav` — latest NAV snapshot

**Tenant isolation:** All endpoints read `tenant_id` from `MIPLOService` (set at boot from C8 token). No tenant_id parameter exposed to the caller — the gateway enforces isolation. All endpoints use the same `auth_dependency` as the existing MIPLO process/status endpoints.

**MIPLOService constructor change:** Add `portfolio_reporter: Optional[PortfolioReporter] = None` parameter. Portfolio delegation methods (`get_portfolio_loans()`, `get_portfolio_exposure()`, `get_portfolio_nav()`) delegate to the reporter with the tenant's `licensee_id` filter. The reporter is constructed in app.py with `licensee_id=processor_context.licensee_id` before being passed to MIPLOService.

### 6. App Wiring (`app.py` changes)

**Bank mode (no processor_context):**
```python
bridge = SettlementCallbackBridge(royalty_settlement=royalty_settlement)
repayment_loop = RepaymentLoop(monitor=settlement_monitor, repayment_callback=bridge)
```

**Processor mode (processor_context provided):**

Wiring order resolves the circular dependency: NAVEventEmitter accepts a lazy getter (`get_active_loans` bound method), so it can be constructed after RepaymentLoop. The bridge is constructed last.

```python
revenue_metering = RevenueMetering()

# Step 1: NAVEventEmitter without RepaymentLoop reference (gets wired after)
nav_emitter = NAVEventEmitter(
    get_active_loans=lambda: [],  # placeholder, replaced below
    nav_callback=...,
    metrics_collector=metrics_collector,
)

# Step 2: Bridge with all downstream services
bridge = SettlementCallbackBridge(
    royalty_settlement=royalty_settlement,
    revenue_metering=revenue_metering,
    nav_emitter=nav_emitter,
    platform_take_rate_pct=Decimal(str(processor_context.platform_take_rate_pct)),
)

# Step 3: RepaymentLoop with real bridge callback
repayment_loop = RepaymentLoop(monitor=settlement_monitor, repayment_callback=bridge)

# Step 4: Wire NAVEventEmitter to RepaymentLoop's get_active_loans
nav_emitter._get_active_loans = repayment_loop.get_active_loans

# Step 5: Register shutdown hook
_shutdown_hooks.append(nav_emitter.stop)

# Step 6: PortfolioReporter with tenant filter for MIPLO
miplo_portfolio_reporter = PortfolioReporter(
    repayment_loop=repayment_loop,
    royalty_settlement=royalty_settlement,
    licensee_id=processor_context.licensee_id,
    risk_engine=risk_engine,
)
```

**Known limitation:** `platform_take_rate_pct` is baked at boot time from the C8 token. Dynamic rate changes require container restart. This is consistent with MIPLOService's existing pattern of capturing processor_context at construction time.

---

## Data Flow

```
Settlement Signal (SWIFT/FedNow/RTP/SEPA)
    │
    ▼
SettlementMonitor.process_signal()  ── matches UETR ──▶ ActiveLoan
    │
    ▼
RepaymentLoop.trigger_repayment()
    │
    ├── _claim_repayment(uetr, maturity_days, tenant_id=loan.licensee_id)
    │       └── Redis key: lip:{tenant_id}:repaid:{uetr}
    │
    ├── fee waterfall (UNTOUCHED — QUANT protected)
    │
    └── SettlementCallbackBridge(repayment_record)
            │
            ├── BPIRoyaltySettlement.record_repayment()     [existing]
            ├── RevenueMetering.record_transaction()         [processor mode]
            └── NAVEventEmitter.record_settlement()          [processor mode]

Background (every 60 min):
    NAVEventEmitter
        ├── Groups active loans by licensee_id
        ├── Computes per-tenant: active_loans, exposure, settled_last_60min
        ├── Emits NAVEvent per tenant via callback
        └── Updates METRIC_TENANT_ACTIVE_LOANS, METRIC_TENANT_EXPOSURE_USD
```

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `lip/c3_repayment_engine/repayment_loop.py` | Add tenant_id to _claim_repayment() Redis key |
| Create | `lip/c3_repayment_engine/nav_emitter.py` | Per-tenant NAVEvent emission (60-min scheduler) |
| Create | `lip/c3_repayment_engine/settlement_bridge.py` | Settlement callback → royalty + revenue + NAV routing |
| Modify | `lip/c3_repayment_engine/__init__.py` | Export NAVEventEmitter, SettlementCallbackBridge |
| Modify | `lip/api/portfolio_router.py` | Add get_tenant_nav() to PortfolioReporter |
| Modify | `lip/api/miplo_router.py` | Add /miplo/portfolio/* tenant-scoped endpoints |
| Modify | `lip/api/miplo_service.py` | Add portfolio query methods (delegate to PortfolioReporter) |
| Modify | `lip/api/app.py` | Wire SettlementCallbackBridge, NAVEventEmitter, RevenueMetering |
| Create | `lip/tests/test_settlement_bridge.py` | TDD: bridge routing, revenue metering, NAV history |
| Create | `lip/tests/test_nav_emitter.py` | TDD: per-tenant NAV emission, settlement history |
| Create | `lip/tests/test_miplo_portfolio.py` | TDD: tenant-scoped portfolio endpoints |

---

## Testing Strategy

- **TDD throughout**: Tests written first, then implementation
- **NAVEventEmitter**: Mock RepaymentLoop with multi-tenant ActiveLoan sets, verify correct grouping and NAVEvent field computation
- **SettlementCallbackBridge**: Mock all 3 downstream services, fire repayment records, verify correct routing (bank-mode = royalty only, processor-mode = royalty + revenue + NAV)
- **Redis key scoping**: Verify `lip:{tenant_id}:repaid:{uetr}` format with tenant, `lip:repaid:{uetr}` without
- **MIPLO portfolio**: Multi-tenant loan set, query via tenant A's endpoint, confirm only tenant A's data
- **Regression**: All existing C3 and C8 tests pass (backward compat)

---

## CIPHER / QUANT Review Notes

**QUANT:** No changes to fee waterfall in trigger_repayment(). Revenue metering uses the same Decimal arithmetic pattern established in Sprint 2a. The bridge passes `Decimal(repayment_record["fee"])` — string→Decimal conversion is safe because trigger_repayment() always writes `str(fee)` where fee is already a Decimal. Both settlement-confirmed AND maturity-triggered repayments flow through the bridge — the fee economics are identical (fee computed on principal × bps × days_funded) regardless of trigger type. This is correct: the processor earns its take rate on all repayments, not just rail-settled ones.

**CIPHER:** Redis key scoping follows the same defense-in-depth pattern as Sprint 2b (C6 velocity). tenant_id comes from loan.licensee_id which is set from C7.licensee_id which is set from the C8 boot-validated token. Chain of trust: C8 HMAC → boot validator → C7 agent → ActiveLoan → Redis key.

---

## Out of Scope

- Kafka NAV event emission (Sprint 5 — infrastructure)
- CorridorBuffer tenant scoping (settlement latency is rail-specific)
- UETRMappingTable tenant scoping (payment-specific, not tenant-specific)
- Full C3 storage repartitioning (Option A — rejected per design decision above)
