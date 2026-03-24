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
| `principal` | Decimal | Bridge loan amount in USD |
| `fee_bps` | int | Annualised fee rate (≥ 300 bps) |
| `maturity_date` | datetime | UTC deadline for repayment |
| `rejection_class` | str | `'A'`, `'B'`, or `'C'` |
| `corridor` | str | Currency pair (e.g., `'EUR_USD'`) |

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

## Spec References

- Architecture Spec v1.2 §4.7 — `SettlementSignal` / `RepaymentConfirmation` schemas
- Architecture Spec v1.2 Claims 5(t–x) — Settlement-confirmation auto-repayment loop
- Patent Claims 3(k–n) — Bridge loan instrument structure
