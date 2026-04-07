# `lip/configs/` — Canonical Configuration

> **The operative parameters of the platform.** Every locked constant in LIP — fee floor, latency SLO, failure thresholds, rejection-code taxonomy, corridor defaults — is sourced from this directory. Any change to these files requires QUANT or REX sign-off depending on which file you touch.

**Source:** `lip/configs/`
**File count:** 3 YAML files

---

## Files

### 1. `canonical_numbers.yaml` — Architecture Spec v1.2 Appendix A

The single source of truth for every numeric constant in the LIP platform. Mirrored at runtime by `lip/common/constants.py` for code that cannot read YAML at startup.

**Sections (excerpt):**

| Section | Key constants | Authority |
|---------|---------------|-----------|
| `market_sizing` | `market_size_usd: 31.7T` (FXC Intelligence 2024 cross-border B2B annual volume) | DGEN / strategy |
| `failure_rates` | `conservative: 0.030`, `midpoint: 0.035`, `upside: 0.040` (3.0%–4.0% of cross-border transactions fail) | DGEN |
| `fee_parameters` | `fee_floor_bps: 300`, `fee_floor_per_7day_cycle: 0.000575`, formula: `fee = loan_amount * (fee_bps/10000) * (days_funded/365)`, **warning: do not apply `fee_bps` as a flat per-cycle rate** | **QUANT** |
| `latency_targets_ms` | `p50: 45`, `p99: 94` | **QUANT (sign-off required)** |
| `ml_performance` | `baseline_auc: 0.739` (XGBoost), `target_auc: 0.850` (GraphSAGE + TabTransformer) | ARIA |
| `dispute_classifier` | `false_negative_rate_current: 0.0` (100-case negation suite, qwen/qwen3-32b via Groq, 2026-03-16), target FN 2% | ARIA |

**Authority rule.** Any change to `canonical_numbers.yaml` requires sign-off from all team agents whose domain is touched. The header comment states this explicitly: *"All values are normative; changes require sign-off from all agents."* In practice, the gating authority is QUANT for any fee-, PD-, or latency-related value, REX for any compliance- or model-governance value, and DGEN for any data-distribution value.

### 2. `rejection_taxonomy.yaml` — Architecture Spec v1.2 Section S8

The full SWIFT / ISO 20022 rejection-code taxonomy mapping every code to one of four classes. This is the source data for `lip/c3_repayment_engine/rejection_taxonomy.py`, which carries the runtime classification function.

**Class structure:**

| Class | Maturity | Meaning |
|-------|----------|---------|
| `CLASS_A` | 3 days | Temporary / technical failures (AC01, AC04, AC06, AM01–AM12, BE01, BE05, DT01, ED01, etc.) |
| `CLASS_B` | 7 days | Systemic / processing failures — **currently block-all in production** until pilot bank License Agreement carries `hold_bridgeable` API obligation. See [`../decisions/EPG-19_compliance_hold_bridging.md`](../decisions/EPG-19_compliance_hold_bridging.md) and [`../OPEN_BLOCKERS.md`](../OPEN_BLOCKERS.md). |
| `CLASS_C` | 21 days | Investigation / complex cases |
| `BLOCK` | 0 days (no bridge) | Dispute / legal block / compliance hold — DNOR, CNOR, RR01–RR04, AG01, LEGL. Promoted to BLOCK class as defense Layer 1 of EPG-19. |

**Authority rule.** Any change to a code's class assignment requires REX sign-off, because the BLOCK list IS the operative compliance policy. Promoting a code out of BLOCK without re-running the EPG-19 deliberation is a refusal-grade error.

**Cross-reference:** the BLOCK list must NEVER appear enumerated in any published patent claim — see [`../decisions/EPG-20-21_patent_briefing.md`](../decisions/EPG-20-21_patent_briefing.md). Maintain this YAML, but do not paste it into outward-facing documents that get filed with the patent office.

### 3. `corridor_defaults.yaml` — currency-pair corridor parameters

Default settlement parameters per currency corridor (e.g. USD/EUR, USD/GBP, USD/JPY, USD/AUD, USD/HKD, EUR/SEK, USD/KRW, USD/BRL, USD/MXN, plus reverses). Each corridor carries observed failure rates and settlement-time distributions used by C2 (PD pricing) and C3 (settlement monitoring window calibration).

**Authority rule.** New corridors require DGEN validation (realistic failure rates and settlement parameters). Eight corridors were added in commit `7ff74dd` — USD/AUD, AUD/USD, USD/HKD, HKD/USD, EUR/SEK, USD/KRW, USD/BRL, USD/MXN.

---

## How configs are loaded

- **Startup**: `lip/api/app.py` reads canonical numbers via `lip/common/constants.py` (which mirrors the YAML)
- **C8 license validation**: license tokens carry their own per-licensee overrides (AML caps per EPG-16/17), validated against the canonical defaults at boot
- **Tests**: tests import from `lip.common.constants` directly so test runs are deterministic against the locked values
- **Operations**: changes to YAML require a redeploy (no hot reload) — this is intentional, to keep operative constants under change control

## Why configs live in `lip/configs/` and not `/etc/lip/`

These are not deployment-time tunables; they are **canonical platform constants** that ship with the package. Putting them in `/etc/lip/` would invite ad-hoc edits per environment, which is precisely the failure mode the locking rules exist to prevent. Deployment-time configuration (Redis URLs, Kafka topics, K8s resource limits) lives in Helm values under `lip/infrastructure/`, not here.

## Cross-references

- **Runtime mirror**: `lip/common/constants.py`
- **Authority documentation**: [`/CLAUDE.md`](../../CLAUDE.md) § Canonical Constants
- **EPG decisions that lock these values**: EPG-19 (BLOCK class), EPG-16/17 (AML caps default 0 / explicit at boot), EPG-23 (`class_b_eligible=False` pre-wired)
- **Pipeline consumer**: `lip/pipeline.py` reads `FAILURE_PROBABILITY_THRESHOLD = 0.110` directly; see [`pipeline.md`](pipeline.md)
