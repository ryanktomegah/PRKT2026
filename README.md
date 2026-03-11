# LIP — Liquidity Intelligence Platform

![Tests](https://img.shields.io/badge/tests-972%20passed-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-92%25-green)
![Lint](https://img.shields.io/badge/ruff-0%20errors-brightgreen)
![Python](https://img.shields.io/badge/python-3.13%2B-blue)

Patent-backed real-time payment failure detection and automated bridge lending system.

**Technology licensor model**: Banks deploy LIP against their SWIFT payment streams. BPI earns 15% royalty on bridge loan fees collected.

**Patent moat**: JPMorgan US7089207B1 covers Tier 1 (listed counterparties) only. LIP's Tier 2+3 coverage of **private counterparties** (via Damodaran industry-beta and Altman Z' thin-file models) is the core patent contribution and primary competitive differentiator.

---

## Architecture

Eight-component pipeline processing ISO 20022 pacs.002 payment events in ≤ 94ms:

```
pacs.002 stream
     │
     ▼
┌─────────┐    ┌─────────┐    ┌─────────┐
│ C5      │───▶│ C1      │───▶│ Decision │
│ Streaming│    │ Failure  │    │ Engine   │
│ (Kafka)  │    │ Classifier│   │          │
└─────────┘    └─────────┘    └────┬─────┘
                                   │ τ* > 0.152
                          ┌────────┼────────┐
                          ▼        ▼        ▼
                     ┌────────┐ ┌──────┐ ┌──────┐
                     │ C4     │ │ C6   │ │ C2   │
                     │ Dispute│ │ AML  │ │ PD   │
                     │ Check  │ │ Check│ │ Model│
                     └────┬───┘ └──┬───┘ └──┬───┘
                          │ hard   │ hard   │ fee_bps
                          │ block  │ block  │
                          ▼        ▼        ▼
                     ┌─────────────────────────┐
                     │ C7 Execution Agent      │
                     │ (kill switch, KMS, logs) │
                     └────────────┬────────────┘
                                  │ FUNDED
                                  ▼
                     ┌─────────────────────────┐
                     │ C3 Repayment Engine     │
                     │ (UETR polling, auto-    │
                     │  repay on settlement)   │
                     └─────────────────────────┘

C8 License Manager — HMAC token enforcement (cross-cutting)
```

## Documentation

| File | Description |
|------|-------------|
| [`docs/architecture.md`](docs/architecture.md) | Algorithm 1 step-by-step, state machines, canonical constants, Redis/Kafka maps, patent claims |
| [`docs/api-reference.md`](docs/api-reference.md) | All Pydantic schemas (C1–C8), fee formula warning, DecisionLogEntry retention |
| [`docs/compliance.md`](docs/compliance.md) | SR 11-7, EU AI Act Art.9/13/14/17/61, DORA Art.30, AML controls, data privacy |
| [`docs/developer-guide.md`](docs/developer-guide.md) | Setup, test commands, canonical constants table, never-commit list, mock injection |
| [`docs/deployment.md`](docs/deployment.md) | Docker images, K8s manifests, HPA, network policies, secrets, env vars, health checks |
| [`docs/data-pipeline.md`](docs/data-pipeline.md) | dgen generators, training commands, C1 AUC gap, C4 FN gap, artefact policy |

## Components

| ID | Name | Algorithm 1 Step | Purpose | Key Tech | Spec | README |
|----|------|-----------------|---------|----------|------|--------|
| C1 | Failure Classifier | Step 1 | Predict payment failure from pacs.002 features | GraphSAGE + TabTransformer + LightGBM | §4.2 | [C1 README](lip/c1_failure_classifier/README.md) |
| C2 | PD Model | Step 3 | Tiered structural PD + LGD + fee pricing | Merton/KMV, Damodaran, Altman Z' | §4.3 | [C2 README](lip/c2_pd_model/README.md) |
| C3 | Repayment Engine | Post-fund | Settlement monitoring + auto-repayment | UETR polling, corridor buffers | §4.7 | [C3 README](lip/c3_repayment_engine/README.md) |
| C4 | Dispute Classifier | Step 2 (∥C6) | Detect disputed payments (hard block) | LLM-based, multilingual, negation | §4.4 | [C4 README](lip/c4_dispute_classifier/README.md) |
| C5 | Streaming | Pre-Step 1 | Real-time event ingestion + normalization | Kafka, Flink, Redis | §C5 | [C5 README](lip/c5_streaming/README.md) |
| C6 | AML Velocity | Step 2 (∥C4) | Sanctions + velocity + anomaly detection | OFAC/EU lists, cross-licensee salts | §4.5 | [C6 README](lip/c6_aml_velocity/README.md) |
| C7 | Execution Agent | Step 4 | Loan execution with safety controls | Kill switch, human override, degraded mode | §4.6 | [C7 README](lip/c7_execution_agent/README.md) |
| C8 | License Manager | Cross-cutting | Technology licensing enforcement | HMAC-SHA256 tokens, boot validation | §S11 | [C8 README](lip/c8_license_manager/README.md) |

## Canonical Constants

| Parameter | Value | Reference |
|-----------|-------|-----------|
| Failure threshold (τ*) | 0.152 | Architecture Spec v1.2 §3 |
| Fee floor | 300 bps annualized | Canonical Numbers |
| Latency SLO | ≤ 94ms end-to-end | Architecture Spec v1.2 |
| UETR TTL buffer | 45 days | Canonical Numbers |
| Platform royalty | 15% of fee collected | Business Model |

## Development

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e "lip/[all]"

# Lint
ruff check lip/

# Type check
mypy lip/

# Test (unit + integration, excludes E2E requiring live Kafka/Redis)
PYTHONPATH=. python -m pytest lip/tests/ --ignore=lip/tests/test_e2e_pipeline.py -v

# Generate synthetic training data
PYTHONPATH=. python -m lip.dgen.generate_all --output-dir artifacts/synthetic

# Train all models
PYTHONPATH=. python lip/train_all.py --data-dir artifacts/synthetic
```

## Repository Layout

```
PRKT2026/
├── docs/                       ← Architecture, API, compliance, deployment docs
├── lip/                        ← Production Python package
│   ├── c1_failure_classifier/  ← Component 1: ML failure prediction
│   ├── c2_pd_model/            ← Component 2: Structural PD + fee pricing
│   ├── c3_repayment_engine/    ← Component 3: Settlement + auto-repay
│   ├── c4_dispute_classifier/  ← Component 4: LLM dispute detection
│   ├── c5_streaming/           ← Component 5: Kafka/Flink ingestion
│   ├── c6_aml_velocity/        ← Component 6: AML + sanctions
│   ├── c7_execution_agent/     ← Component 7: Loan execution
│   ├── c8_license_manager/     ← Component 8: License enforcement
│   ├── common/                 ← Shared schemas, state machines, crypto
│   ├── configs/                ← YAML configs (canonical numbers, corridors)
│   ├── dgen/                   ← Synthetic data generators
│   ├── infrastructure/         ← Docker, Helm, K8s manifests
│   ├── tests/                  ← Test suite (84% coverage)
│   ├── pipeline.py             ← End-to-end pipeline orchestrator
│   └── pyproject.toml          ← Package configuration
├── consolidation files/        ← Patent specs, architecture docs, governance
├── scripts/                    ← Training + monitoring CLI tools
├── .github/workflows/          ← CI/CD + model training pipelines
└── CLAUDE.md                   ← Claude Code project configuration
```

## Patent Coverage

System and Method for Automated Liquidity Bridging Triggered by Real-Time Payment Network Failure Detection — Provisional Specification v5.2

- **Claims 1(a–h)**: Full pipeline from detection to auto-repayment
- **Claims 2(i–vi)**: System architecture components
- **Claims 3(k–n)**: Bridge loan instrument structure
- **Claims 5(t–x)**: Settlement-confirmation auto-repayment loop
- **Dependent Claims D1–D11**: ISO 20022, F-beta threshold, tiered PD, LGD, UETR tracking

## License

Proprietary — BPI Technology
