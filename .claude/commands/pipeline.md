# LIP Pipeline Operations

Work on the end-to-end LIP pipeline (Algorithm 1 from Architecture Spec v1.2).

## Pipeline Flow (Algorithm 1)

For each payment event:
1. C5 normalizes raw event → NormalizedEvent
2. C1 extracts features + predicts failure_probability
3. If failure_probability > τ* (0.152):
   a. C4 checks for dispute (hard_block)
   b. C6 checks AML velocity (hard_block)
   c. C2 computes PD + fee_bps (300bps floor)
   d. Decision Engine aggregates signals → LoanOffer
   e. C7 receives offer, applies kill switch / KMS checks
   f. If accepted: FUNDED state, C3 starts settlement monitoring
4. Return PipelineResult with full audit trail

## Three-Entity Model
- **MLO** — Money Lending Organisation (capital provider)
- **MIPLO** — Money In / Payment Lending Organisation (platform operator)
- **ELO** — Execution Lending Organisation (bank-side agent, C7)

## Key Files
- `lip/pipeline.py` — Main pipeline orchestrator
- `lip/pipeline_result.py` — Result dataclass with audit trail
- `lip/common/state_machines.py` — Payment + Loan state machines
- `lip/common/schemas.py` — Pydantic models for all inter-component contracts
- `lip/instrumentation.py` — Latency tracking

## State Machine Transitions
Payment: RECEIVED → SCREENING → CLASSIFIED → OFFERED → FUNDED → MONITORING → SETTLED | FAILED
Loan: PENDING → APPROVED → DISBURSED → MONITORING → REPAID | DEFAULTED | RECOVERED

## Rules
- Pipeline must complete in ≤ 94ms (LATENCY_SLO_MS)
- Hard blocks from C4 (dispute) and C6 (AML) are non-negotiable — no bridge loan issued
- All pipeline results must include complete decision_log for 7-year regulatory retention
- Component dependencies are injected (constructor injection) — enables full mock testing
- Run from repo root: `/Users/halil/PRKT2026`
