# LIP — Liquidity Intelligence Platform

Patent-backed real-time payment failure detection and automated bridge lending system.

**Technology licensor model**: Banks deploy LIP against their SWIFT payment streams. BPI earns 15% royalty on bridge loan fees collected.

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

## Components

| ID | Name | Purpose | Key Tech |
|----|------|---------|----------|
| C1 | Failure Classifier | Predict payment failure from pacs.002 features | GraphSAGE + TabTransformer + LightGBM |
| C2 | PD Model | Tiered structural PD + LGD + fee pricing | Merton/KMV, Damodaran, Altman Z' |
| C3 | Repayment Engine | Settlement monitoring + auto-repayment | UETR polling, corridor buffers |
| C4 | Dispute Classifier | Detect disputed payments (hard block) | LLM-based, multilingual, negation |
| C5 | Streaming | Real-time event ingestion + normalization | Kafka, Flink, Redis |
| C6 | AML Velocity | Sanctions + velocity + anomaly detection | OFAC/EU lists, cross-licensee salts |
| C7 | Execution Agent | Loan execution with safety controls | Kill switch, human override, degraded mode |
| C8 | License Manager | Technology licensing enforcement | HMAC-SHA256 tokens, boot validation |

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
