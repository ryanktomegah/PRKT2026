# LIP Test Suite Runner

Run the LIP test suite with coverage reporting. Validates all 8 components.

## Execution Protocol

1. Set `PYTHONPATH` to repo root
2. Run `ruff check lip/` — must be zero errors
3. Run `mypy lip/` — check type safety
4. Run `python -m pytest lip/tests/ --ignore=lip/tests/test_e2e_pipeline.py -v --tb=short --cov=lip --cov-report=term-missing`
5. Report results: pass/fail count, coverage %, any regressions

## Rules
- `test_e2e_pipeline.py` requires live Redis/Kafka — always excluded from local runs
- Coverage target: ≥ 84% (current baseline)
- If coverage drops below 84%, flag which component lost coverage
- If any test fails, investigate the root cause before suggesting fixes
- Run from repo root: `/Users/halil/PRKT2026`

## Component Test Map
| Test File | Component | What It Validates |
|-----------|-----------|-------------------|
| test_c1_classifier.py | C1 | Feature extraction, inference, calibration |
| test_c1_training.py | C1 | Training pipeline, GraphSAGE, TabTransformer |
| test_c2_pd_model.py | C2 | Tiered PD, LGD, fee arithmetic |
| test_c3_repayment.py | C3 | Settlement handlers, UETR mapping |
| test_c4_dispute.py | C4 | Dispute classification, prefilter |
| test_c4_backends.py | C4 | LLM backend integration |
| test_c5_streaming.py | C5 | Event normalization, Kafka config |
| test_c5_kafka_worker.py | C5 | Kafka worker lifecycle |
| test_c6_aml.py | C6 | AML velocity, sanctions, salt rotation |
| test_c7_execution.py | C7 | Kill switch, human override, decision log |
| test_c8_license.py | C8 | HMAC tokens, boot validation |
| test_state_machines.py | Common | Payment + Loan state machines |
| test_fee_arithmetic.py | C2 | Fee floor enforcement, maturity windows |
| test_e2e_*.py | Pipeline | End-to-end integration flows |
