# Agent Sign-off Authority Matrix
## Which file changes require which agent approvals

| File / Path | Required Sign-offs | Reason |
|-------------|-------------------|--------|
| `lip/pipeline.py` | NOVA | Pipeline decision gates and state machines |
| `lip/pipeline.py` (AML-related change) | NOVA + CIPHER | AML result handling |
| `lip/pipeline.py` (audit log change) | NOVA + REX | 7-year decision log schema |
| `lip/c7_execution_agent/agent.py` | NOVA | C7 execution authority |
| `lip/c7_execution_agent/agent.py` (_COMPLIANCE_HOLD_CODES) | NOVA + CIPHER + REX | AML + compliance + regulatory |
| `lip/c7_execution_agent/human_override.py` | REX + NOVA | Human oversight (EU AI Act Art.14) |
| `lip/c6_aml_velocity/aml_checker.py` | CIPHER | AML gate authority |
| `lip/c6_aml_velocity/sanctions.py` | CIPHER | Sanctions screening |
| `lip/c6_aml_velocity/velocity.py` | CIPHER | Velocity caps |
| `lip/c6_aml_velocity/*.py` (any) | CIPHER | AML domain |
| `lip/configs/rejection_taxonomy.yaml` | NOVA + REX + QUANT | Maturity windows affect fee math |
| `lip/common/constants.py` (fee math) | QUANT | Fee floor, maturity days, thresholds |
| `lip/common/constants.py` (AML caps) | CIPHER + QUANT | AML velocity limits |
| `lip/common/constants.py` (latency SLO) | FORGE + QUANT | Infrastructure SLO |
| `lip/c1_*/` | ARIA | ML model domain |
| `lip/c2_*/` | QUANT + ARIA | Financial math + ML |
| `lip/c3_*/` | NOVA | Settlement monitoring |
| `lip/c4_*/` | ARIA | Dispute classifier |
| `lip/c5_*/` | NOVA | Streaming ingestion |
| `lip/c8_*/` | CIPHER + FORGE | License enforcement + infra |
| `docs/compliance.md` | REX | Regulatory documentation |
| `lip/dgen/` | DGEN + ARIA | Data generation and ML corpus |
| `lip/tests/test_e2e_*.py` | NOVA + FORGE | End-to-end test coverage |

## EPG-specific sign-off requirements

| EPG | Files changing | Required sign-offs |
|-----|---------------|-------------------|
| EPG-09/10/11 | pipeline.py | NOVA + REX |
| EPG-24 | aml_checker.py | CIPHER |
| EPG-25 | velocity.py | CIPHER + QUANT (throughput) |
| EPG-26 | human_override.py, pipeline.py, uetr_tracker | REX + NOVA + FORGE |
| EPG-27 | pipeline.py (AML section) | CIPHER + FORGE |
| EPG-01/02/03 | agent.py (_COMPLIANCE_HOLD_CODES) | CIPHER + REX |
| EPG-07/08 | rejection_taxonomy.yaml | NOVA + REX + QUANT |
| EPG-28 | velocity.py, C5 normalization | CIPHER + NOVA + QUANT |

## What sign-off means in practice

Each agent has a corresponding file in `.claude/agents/<name>.md`. When the skill reads
that file, it extracts the domain-specific checklist to verify. Sign-off is granted when
all checklist items for that agent's domain pass.

Sign-off is NOT a rubber stamp — if an agent's domain has open violations, those must be
resolved before committing.
