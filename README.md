# LIP — Liquidity Intelligence Platform

[![Tests](https://img.shields.io/badge/tests-1284%20passing-brightgreen)](https://github.com/ryanktomegah/PRKT2026/actions)
[![Coverage](https://img.shields.io/badge/coverage-92%25-brightgreen)](https://github.com/ryanktomegah/PRKT2026/actions)
[![Ruff](https://img.shields.io/badge/ruff-0%20errors-brightgreen)](https://docs.astral.sh/ruff/)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue)](https://python.org)

Real-time payment failure detection and automated bridge lending for correspondent banks. Built by BPI Technology. Patent-pending.

---

## What LIP Does

When a cross-border SWIFT payment fails (ISO 20022 `pacs.002` rejection), LIP detects it in milliseconds, classifies the failure type, assesses the borrowing bank's credit risk, and conditionally offers a short-term bridge loan — all within a 94ms SLO. Banks license LIP as a technology platform; BPI does not hold deposits or make loans directly.

---

## Architecture

```
pacs.002 rejection
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  C5 Streaming          ISO 20022 normalisation, Kafka ingestion (Go)        │
│  C6 AML/Velocity       Sanctions screening, velocity limits (Rust + Python) │
│  C1 Failure Classifier GraphSAGE + TabTransformer + LightGBM failure pred.  │
│  C4 Dispute Classifier LLM-based dispute detection (Qwen3-32B / Groq)       │
│  C2 PD Model           Tiered structural PD + LGD + fee pricing             │
│  C3 Repayment Engine   UETR polling, settlement monitoring (Rust FSM)       │
│  C7 Execution Agent    Loan execution, kill switch, Go gRPC router          │
│  C8 License Manager    HMAC-SHA256 token enforcement (cross-cutting)        │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
  LoanOffer or BLOCKED/DECLINED/COMPLIANCE_HOLD
```

| Component | Purpose | Key Tech |
|-----------|---------|----------|
| C1 — Failure Classifier | Predict payment failure probability | GraphSAGE, TabTransformer, LightGBM |
| C2 — PD Model | Tiered PD/LGD + fee pricing | Merton/KMV, Damodaran, Altman Z' |
| C3 — Repayment Engine | Settlement monitoring + auto-repayment | UETR polling, Rust FSM (PyO3) |
| C4 — Dispute Classifier | Hard-block disputed payments | Qwen3-32B via Groq |
| C5 — Streaming | ISO 20022 normalisation + ingestion | Kafka (Go consumer) |
| C6 — AML/Velocity | OFAC/EU sanctions + velocity limits | Rust velocity counters (PyO3) |
| C7 — Execution Agent | Loan execution with safety controls | Go gRPC offer router, kill switch |
| C8 — License Manager | Technology licensing enforcement | HMAC-SHA256, boot validation |

**Additional modules:** C9 (Settlement Predictor), P5 (Cascade Engine), P10 (Regulatory Data Product)

---

## Canonical Constants

These values are **QUANT-locked** — never change without explicit QUANT sign-off (see `CLAUDE.md`):

| Constant | Value | Location |
|----------|-------|----------|
| Fee floor | 300 bps | `lip/common/constants.py` |
| Maturity CLASS_A | 3 days | `lip/common/constants.py` |
| Maturity CLASS_B | 7 days | `lip/common/constants.py` |
| Maturity CLASS_C | 21 days | `lip/common/constants.py` |
| C1 decision threshold (τ★) | 0.110 | `lip/common/constants.py` |
| Latency SLO | ≤ 94ms | `lip/common/constants.py` |
| UETR TTL buffer | 45 days | `lip/common/constants.py` |

---

## Getting Started

### Prerequisites

- Python 3.13+
- Docker (for local Kafka + Redis)
- Go 1.22+ (for C5/C7 microservices)
- Rust 1.77+ (for C3/C6 PyO3 extensions)

### Local Infrastructure

```bash
# Start Redpanda (Kafka-compatible) + Redis
docker compose up -d

# Initialise Kafka topics (10 topics, 7-year retention on decision log)
bash scripts/init_topics.sh
```

### Install Dependencies

```bash
pip install -r requirements.txt
# ML training only:
pip install -r requirements-ml.txt
```

### Run Tests

```bash
# Fast iteration (excludes slow ML training tests)
PYTHONPATH=. python -m pytest lip/tests/ -m "not slow" -v

# Full suite (~12 min)
PYTHONPATH=. python -m pytest lip/tests/ -v

# Lint (must be zero errors before any commit)
ruff check lip/
```

### Train Models

```bash
PYTHONPATH=. python lip/train_all.py --help
```

---

## Documentation

Documentation is organised by audience:

| Audience | Entry Point |
|----------|-------------|
| All roles | [`docs/INDEX.md`](docs/INDEX.md) — role-based reading paths |
| Engineers | [`docs/engineering/`](docs/engineering/) — architecture, dev guide, specs, review |
| Legal / Compliance | [`docs/legal/`](docs/legal/) — compliance, patent specs, EPG decisions |
| Business / Pilots | [`docs/business/`](docs/business/) — client analysis, RBC pilot kit |
| Operations | [`docs/operations/`](docs/operations/) — deployment, playbooks |
| ML / Models | [`docs/models/`](docs/models/) — model cards, federated learning |

**Quick links:**
- [Architecture](docs/engineering/architecture.md)
- [Developer Guide](docs/engineering/developer-guide.md)
- [API Reference](docs/engineering/api-reference.md)
- [Compliance (SR 11-7, EU AI Act, DORA)](docs/legal/compliance.md)
- [C1 Model Card](docs/models/c1-model-card.md)
- [EPG Decision Register](docs/legal/decisions/)
- [RBC Pilot Kit](docs/business/bank-pilot/)
- [Benchmark Results](docs/engineering/benchmark-results.md)

---

## Repository Layout

```
PRKT2026/
├── README.md                    ← This file
├── CLAUDE.md                    ← Claude Code project configuration
├── PROGRESS.md                  ← Development session tracker
├── docker-compose.yml           ← Local Redpanda + Redis
├── requirements.txt             ← Core Python dependencies
├── requirements-ml.txt          ← ML training dependencies
│
├── lip/                         ← Production Python package
│   ├── pipeline.py              ← Algorithm 1 — main orchestrator (1107 lines)
│   ├── c1_failure_classifier/   ← ML failure prediction
│   ├── c2_pd_model/             ← Structural PD + fee pricing
│   ├── c3_repayment_engine/     ← Settlement monitoring
│   ├── c3/rust_state_machine/   ← Rust FSM (PyO3)
│   ├── c4_dispute_classifier/   ← LLM dispute detection
│   ├── c5_streaming/            ← Kafka ingestion + Go consumer
│   ├── c6_aml_velocity/         ← Sanctions + Rust velocity engine
│   ├── c7_execution_agent/      ← Loan execution + Go gRPC router
│   ├── c8_license_manager/      ← HMAC licensing
│   ├── c9_settlement_predictor/ ← Settlement prediction
│   ├── p5_cascade_engine/       ← Systemic risk propagation
│   ├── p10_regulatory_data/     ← Regulator data product (DP)
│   ├── common/                  ← Schemas, constants, state machines
│   ├── api/                     ← FastAPI application
│   ├── dgen/                    ← Synthetic data generation
│   ├── infrastructure/          ← Docker, Kubernetes, Helm, Grafana
│   ├── integrity/               ← Structural integrity enforcement
│   ├── risk/                    ← Portfolio risk utilities
│   └── tests/                   ← 1284 tests, 92% coverage
│
├── scripts/                     ← Training, benchmarking, validation CLI
│
├── docs/
│   ├── INDEX.md                 ← Role-based entry point
│   ├── engineering/             ← Architecture, specs, developer guides
│   │   ├── specs/               ← BPI_C1-C7 specs + migration specs (22 files)
│   │   ├── blueprints/          ← P3-P10 implementation blueprints
│   │   ├── codebase/            ← Subsystem reference docs (14 files)
│   │   ├── review/              ← Code review reports + architecture audit
│   │   └── research/            ← Academic paper, R&D memos
│   ├── legal/
│   │   ├── patent/              ← Patent specs, claims, counsel briefing
│   │   ├── decisions/           ← EPG decision register (EPG-04 through EPG-21)
│   │   └── governance/          ← Sign-off records, SR 11-7 governance pack
│   ├── business/
│   │   ├── bank-pilot/          ← RBC pilot kit (7 docs)
│   │   └── fundraising/         ← Fundraising materials
│   ├── operations/              ← Deployment, playbooks
│   ├── models/                  ← Model cards, federated learning, CBDC research
│   └── superpowers/             ← Sprint plans and design specs
│
└── .github/workflows/           ← CI/CD, model training, deploy pipelines
```

---

## Patent Coverage

LIP's core patent claim covers the **two-step classification + conditional offer mechanism** for ISO 20022 payment failures — specifically the novel extension to Tier 2/3 private counterparties using Damodaran industry-beta and Altman Z' thin-file models (gap in JPMorgan US7089207B1).

See [`docs/legal/patent/`](docs/legal/patent/) for provisional specifications and patent family architecture.

---

## Key Rules (Non-Negotiable)

- **Never bridge compliance-hold payments** (EPG-19): DNOR, CNOR, RR01-RR04, AG01, LEGL are permanently blocked — AMLD6 Art.10 criminal liability applies.
- **Fee floor is 300 bps** (QUANT authority): No code may produce a fee below this without explicit QUANT sign-off.
- **Never commit AML typology patterns** (`c6_corpus_*.json`): CIPHER rule — generate fresh with dgen.
- **Governing law from BIC, not currency** (EPG-14): `bic_to_jurisdiction()` uses BIC chars 4–5.

---

## License

Proprietary. © BPI Technology. All rights reserved. Patent pending.
