# C3: Repayment Engine

## Role in Pipeline

C3 takes over after a bridge loan is funded. It monitors SWIFT settlement signals (camt.054 / MT202 / pacs.009) for the underlying payment via UETR polling, automatically triggers repayment when settlement is confirmed, and calculates the BPI platform royalty on collected fees.

## Algorithm 1 Position

```
C7 (FUNDED) → [C3: settlement monitoring loop]
                  │
                  ├─ settlement confirmed → auto-repay → C3 closes loan
                  ├─ partial settlement → buffer-repay
                  └─ maturity exceeded → default
```

C3 runs **after** Algorithm 1 completes — it manages the funded loan lifecycle asynchronously.

## Key Classes

| Class / Function | File | Description |
|-----------------|------|-------------|
| `SettlementMonitor` | `repayment_loop.py` | UETR polling loop; registers / closes loans |
| `ActiveLoan` | `repayment_loop.py` | Dataclass representing a funded bridge loan |
| `RepaymentCalculator` | `repayment_loop.py` | Computes principal + fee + royalty splits |
| `RejectionTaxonomy` | `rejection_taxonomy.py` | Maps ISO 20022 codes to Classes A/B/C |
| `CorridorBuffer` | `corridor_buffers.py` | Rolling corridor risk and buffer windows |

## Inputs / Outputs

**Input** (`ActiveLoan` fields registered by `LIPPipeline._register_with_c3`):

| Field | Type | Description |
|-------|------|-------------|
| `loan_id` | str | Unique loan identifier (defaults to UETR) |
| `uetr` | str | ISO 20022 UETR of the funded payment |
| `individual_payment_id` | str | Payment-leg identifier (e.g. RTP EndToEndId, mBridge atomic_settlement_id) |
| `principal` | Decimal | Bridge loan amount in USD |
| `fee_bps` | int | Annualised fee rate (≥ 300 bps universal floor; ≥ 1200 bps when rail is sub-day) |
| `maturity_date` | datetime | UTC deadline for repayment (computed from rail's maturity_hours by C7) |
| `rejection_class` | str | `'CLASS_A'`, `'CLASS_B'`, `'CLASS_C'`, or `'BLOCK'` |
| `corridor` | str | Currency pair (e.g., `'EUR_USD'`) |
| `funded_at` | datetime | UTC datetime when the loan was funded |
| `licensee_id` | str | C8 licensee identifier (multi-tenant) |
| `deployment_phase` | str | `'LICENSOR'` / `'PHASE_2'` / `'PHASE_3'` |
| `rail` | str | **Phase A**: drives rail-aware TTL. Values: `SWIFT`, `SEPA`, `FEDNOW`, `RTP`, `CBDC_ECNY`, `CBDC_EEUR`, `CBDC_SAND_DOLLAR`, `CBDC_MBRIDGE`, `CBDC_NEXUS`. Default `"SWIFT"` for backward compat. |

### Rail-aware TTL (Phase A, 2026-04-25)

`RepaymentLoop._claim_repayment(uetr, maturity_days, tenant_id, rail=...)` computes the Redis SETNX TTL based on rail:

```
if rail in RAIL_MATURITY_HOURS:
    ttl_seconds = int(RAIL_MATURITY_HOURS[rail] * 3600 + 45 * 86_400)
else:
    ttl_seconds = (maturity_days + 45) * 86_400  # legacy day-scale
```

Sub-day rails (CBDC at 4h) get hour-precision TTL without losing information in the day-int representation. Legacy rails preserve the existing day-based path.

**Output** — `RepaymentConfirmation` schema (see `common/schemas.py §4.7`):

| Field | Description |
|-------|-------------|
| `principal_repaid_usd` | Principal component repaid |
| `fee_repaid_usd` | Fee component repaid |
| `platform_royalty_usd` | `30% × fee_repaid_usd` → BPI |
| `net_fee_to_entities_usd` | `70% × fee_repaid_usd` → MLO/MIPLO/ELO |
| `repayment_type` | `'FULL'`, `'BUFFER'`, or `'DEFAULT'` |

## Canonical Constants Used

| Constant | Value | Significance |
|----------|-------|-------------|
| `PLATFORM_ROYALTY_RATE` | **0.30** | 30% of `fee_repaid_usd` to BPI — **QUANT sign-off required** |
| `UETR_TTL_BUFFER_DAYS` | **45** | Buffer beyond maturity for UETR deduplication — **QUANT sign-off required** |
| `CORRIDOR_BUFFER_WINDOW_DAYS` | 90 | Rolling window for corridor risk lookback |
| `MATURITY_CLASS_A_DAYS` | 3 | Rejection Class A maturity |
| `MATURITY_CLASS_B_DAYS` | 7 | Rejection Class B maturity (default) |
| `MATURITY_CLASS_C_DAYS` | 21 | Rejection Class C maturity |
| `RAIL_MATURITY_HOURS` | dict | Rail-keyed maturity buffer in hours. SWIFT/SEPA = 1080h (45d), FEDNOW/RTP = 24h, CBDC_* = 4h. |

## Spec References

- Architecture Spec v1.2 §4.7 — `SettlementSignal` / `RepaymentConfirmation` schemas
- Architecture Spec v1.2 Claims 5(t–x) — Settlement-confirmation auto-repayment loop
- Patent Claims 3(k–n) — Bridge loan instrument structure
- ADR-2026-04-25-rail-aware-maturity.md — `ActiveLoan.rail` field, hour-precision TTL design
