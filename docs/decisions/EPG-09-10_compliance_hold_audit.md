# EPG-09 / EPG-10 — Compliance Hold Audit Trail

**Status:** ✅ Implemented
**Decided:** 2026-03-18
**Decision authority:** REX
**Source rationale:** [`/CLAUDE.md`](../../CLAUDE.md) § EPG-09/10/16/17/18
**Implementation:** commit `0ec874c`
**Related:** [`EPG-19_compliance_hold_bridging.md`](EPG-19_compliance_hold_bridging.md)

---

## Decision

When LIP refuses to bridge a payment because of a compliance hold, the audit log must record a **distinct outcome** from a normal underwriting decline. Two separate fields are required on `PipelineResult`:

| Field | Value | Why |
|-------|-------|-----|
| `outcome` | `"COMPLIANCE_HOLD"` (NOT `"DECLINED"`) | A regulator reading the audit trail must be able to distinguish "we declined this for credit reasons" from "the bank's compliance system blocked this and we honored the block." Conflating them looks like LIP is doing its own compliance screening — which it is not, and must not appear to be doing. |
| `compliance_hold` | `bool` | A typed flag, not derived from string parsing of `outcome`, so downstream code (regulatory reporting, BPI admin dashboard) can filter without brittle string matching. |

## Why this matters

Without this distinction, every audit query that asks "how often did LIP refuse to bridge" produces a single number that mixes credit declines with compliance honoring. Regulators reading that number will assume LIP is making compliance judgments. Regulators are not wrong to be skeptical when a fintech appears to be making compliance judgments without being a regulated compliance entity. The fix is to make it impossible to confuse the two outcomes at the data layer.

## Implementation

Layered with EPG-19's defense-in-depth: when Layer 1 (`rejection_taxonomy.py` BLOCK class) or Layer 2 (`_COMPLIANCE_HOLD_CODES` in `agent.py`) refuses a payment, the resulting `PipelineResult` carries `outcome="COMPLIANCE_HOLD"` and `compliance_hold=True`. Tests in `test_c3_repayment.py` enforce that no other outcome value can co-occur with `compliance_hold=True`.

## Regulatory mapping

This pairs with the DORA / SR 11-7 reporting requirements in `lip/common/regulatory_reporter.py` (see `PROGRESS.md` for the `RegulatoryReporter` class). Compliance-hold outcomes must appear in the DORA audit feed under their own classification, not folded into "model decisions."
