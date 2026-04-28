# LIP — Liquidity Intelligence Platform

[![LIP CI](https://github.com/ryanktomegah/PRKT2026/actions/workflows/ci.yml/badge.svg)](https://github.com/ryanktomegah/PRKT2026/actions/workflows/ci.yml)
[![Ruff](https://img.shields.io/badge/ruff-enforced-blue)](https://docs.astral.sh/ruff/)
[![Python](https://img.shields.io/badge/python-3.10--3.12-blue)](https://python.org)

Real-time payment failure detection and automated bridge lending for correspondent banks. Built by BPI Technology. Patent-pending.

---

## Current State

For the canonical 2026-04-28 status, read [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md). The latest signed staging RC is documented in [`docs/operations/releases/staging-rc-2026-04-24.md`](docs/operations/releases/staging-rc-2026-04-24.md). Older model cards, research papers, and governance packs preserve dated baseline evidence and should be interpreted through that current-state file.

---

## What LIP Does

When a cross-border payment fails on **any supported rail** (ISO 20022 `pacs.002` rejection on SWIFT/SEPA, proprietary status on FedNow/RTP, or CBDC-specific failure events), LIP detects it in milliseconds, normalises the failure into the canonical ISO 20022 taxonomy, classifies the exception, assesses the borrowing bank's credit risk, and conditionally offers a short-term bridge loan — all within a 94ms SLO. Banks license LIP as a technology platform; BPI does not hold deposits or make loans directly.

The Nexus-world product pivot is implemented as **Exception OS v1**: every `PipelineResult` now carries `exception_assessment`, a rail-agnostic response recommendation across SWIFT, SEPA, FedNow/RTP, CBDC, mBridge, and Nexus. Bridge lending is one recommended response (`OFFER_BRIDGE`); the same layer can also recommend `HOLD`, `DECLINE`, `HUMAN_REVIEW`, `GUARANTEE_CANDIDATE`, `RETRY`, or `TELEMETRY_ONLY` without changing the existing financial gates.

**Supported rails** (`lip/common/constants.py:RAIL_MATURITY_HOURS`):

| Rail | Maturity buffer | Notes |
|---|---|---|
| `SWIFT` | 1080h (45 days) | Primary cross-border rail |
| `SEPA` | 1080h (45 days) | EUR cross-border |
| `FEDNOW` | 24h | US domestic instant — sub-day floor applies |
| `RTP` | 24h | TCH instant — sub-day floor applies |
| `CBDC_ECNY` | 4h | PBoC e-CNY |
| `CBDC_EEUR` | 4h | ECB experimental e-EUR |
| `CBDC_SAND_DOLLAR` | 4h | CBB Sand Dollar |
| `CBDC_MBRIDGE` | 4h | BIS mBridge multi-CBDC PvP (5 currencies, atomic settlement) |
| `CBDC_NEXUS` | 4h | NGP multilateral instant rail (PHASE-2-STUB; mid-2027 onboarding) |

---

## Architecture

```
pacs.002 / FedNow / RTP / SEPA / CBDC event
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  C5 Streaming          Multi-rail normalisation + Kafka ingestion           │
│                          - EventNormalizer (SWIFT/FedNow/RTP/SEPA)          │
│                          - CBDCNormalizer (e-CNY/e-EUR/Sand Dollar)         │
│                          - MBridgeNormalizer (multi-leg PvP)                │
│                          - NexusNormalizer (PHASE-2-STUB)                   │
│  C6 AML/Velocity       Sanctions screening, velocity limits (Rust + Python) │
│  C1 Failure Classifier GraphSAGE + TabTransformer + LightGBM failure pred.  │
│  C4 Dispute Classifier LLM-based dispute detection (Qwen3-32B / Groq)       │
│  C2 PD Model           Tiered structural PD + LGD + rail-aware fee pricing  │
│  C3 Repayment Engine   Rail-aware TTL, UETR polling, settlement (Rust FSM)  │
│  C7 Execution Agent    Loan execution, kill switch, Go gRPC router          │
│  Exception OS v1       Cross-rail exception type + response recommendation  │
│  C8 License Manager    HMAC-SHA256 token enforcement (cross-cutting)        │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
  PipelineResult.outcome ∈ {
      OFFERED,                  // C7 produced a bridge offer; ELO must accept
                                //   to transition BRIDGE_OFFERED → FUNDED (async).
      FUNDED,                   // post-acceptance state; C3 monitors repayment.
      DISPUTE_BLOCKED,          // C4 hard-blocked.
      AML_BLOCKED,              // C6 hard-blocked.
      COMPLIANCE_HOLD,          // EPG-19 BLOCK code (DNOR, CNOR, RR01-RR04, AG01, LEGL).
      DECLINED,                 // pricing or eligibility refusal.
      BELOW_THRESHOLD,          // C1 failure probability < τ★.
      HALT,                     // pipeline kill switch engaged.
      PENDING_HUMAN_REVIEW,     // EPG-26 human-oversight gate.
      RETRY_BLOCKED,            // C7 retry-budget exhausted.
      AML_CHECK_UNAVAILABLE,    // C6 unavailable / fail-closed.
      SYSTEM_ERROR,             // unhandled exception.
      DOMESTIC_LEG_FAILURE,     // Phase C: FedNow/RTP/SEPA leg failed with a
                                //   registered upstream SWIFT parent UETR.
                                //   Bridge offer issued + parent_uetr field
                                //   added to loan_offer for cross-rail audit.
  }
  PipelineResult.exception_assessment = {
      exception_type, recommended_action, reason_code, reason,
      rail, maturity_hours, is_subday, confidence, signals
  }
       │ (only if FUNDED)
       ▼
  C3 Repayment Engine: UETR polling, settlement monitoring, repayment / default

Source of truth for outcome strings: lip/pipeline_result.py:23-44
Source of truth for state machine: lip/common/state_machines.py:91-148
```

| Component | Purpose | Key Tech |
|-----------|---------|----------|
| C1 — Failure Classifier | Predict payment failure probability | GraphSAGE, TabTransformer, LightGBM |
| C2 — PD Model | Tiered PD/LGD + rail-aware fee pricing (sub-day floor) | Merton/KMV, Damodaran, Altman Z' |
| C3 — Repayment Engine | Rail-aware TTL, settlement monitoring, auto-repayment | UETR polling, Rust FSM (PyO3) |
| C4 — Dispute Classifier | Hard-block disputed payments | Qwen3-32B via Groq |
| C5 — Streaming | Multi-rail (SWIFT/SEPA/FedNow/RTP/5 CBDC) normalisation + Kafka ingest | Kafka (Go consumer) |
| C6 — AML/Velocity | OFAC/EU sanctions + velocity limits | Rust velocity counters (PyO3) |
| C7 — Execution Agent | Rail-aware loan execution + cross-rail handoff detection | Go gRPC offer router, kill switch |
| Exception OS v1 | Rail-agnostic exception classification and response recommendation | Deterministic rules |
| C8 — License Manager | Technology licensing enforcement | HMAC-SHA256, boot validation |

**Additional modules:** C9 (Settlement Predictor), P5 (Cascade Engine), P10 (Regulatory Data Product)

---

## Canonical Constants

These values are **QUANT-locked** — never change without explicit QUANT sign-off (see `CLAUDE.md`):

| Constant | Value | Location |
|----------|-------|----------|
| Fee floor (universal) | 300 bps | `lip/common/constants.py:FEE_FLOOR_BPS` |
| Fee floor (sub-day rails) | 1200 bps | `lip/common/constants.py:FEE_FLOOR_BPS_SUBDAY` |
| Operational fee floor (absolute) | $25 | `lip/common/constants.py:FEE_FLOOR_ABSOLUTE_USD` |
| Sub-day rail boundary | < 48h maturity | `lip/common/constants.py:SUBDAY_THRESHOLD_HOURS` |
| Maturity CLASS_A | 3 days | `lip/common/constants.py` |
| Maturity CLASS_B | 7 days | `lip/common/constants.py` |
| Maturity CLASS_C | 21 days | `lip/common/constants.py` |
| CBDC rail maturity | 4 hours | `lip/common/constants.py:RAIL_MATURITY_HOURS` |
| C1 decision threshold (τ★) | 0.110 | `lip/common/constants.py` |
| Latency SLO | ≤ 94ms | `lip/common/constants.py` |
| UETR TTL buffer | 45 days | `lip/common/constants.py` |

**Rail-aware fee floor framework** (`docs/engineering/decisions/ADR-2026-04-25-rail-aware-maturity.md`): 300 bps annualised × 4h on $5M = $68, below 5% cost-of-funds capital cost ($114). The 1200 bps sub-day floor is calibrated to cost of capital + opex margin + risk reserve. Universal 300 bps floor is preserved unchanged; the sub-day floor is a *tighter, additive* floor that activates only when the rail's maturity is below 48h.

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

### Deploy the Staging Slice

```bash
# Generate the signed C2 artifact (artifacts/ is gitignored)
PYTHONPATH=. python scripts/generate_c2_artifact.py \
    --hmac-key-file .secrets/c2_model_hmac_key

# One-command staging deploy against a self-hosted kubeconfig
LIP_API_IMAGE=lip-api:local LIP_C2_IMAGE=lip-c2:local \
LIP_C4_IMAGE=lip-c4:local LIP_C6_IMAGE=lip-c6:local \
./scripts/deploy_staging_self_hosted.sh --profile local-core
```

The staging `lip-api` runs the **real runtime pipeline** (`LIP_API_ENABLE_REAL_PIPELINE=true`) with the Torch C1 artifact, the signed C2 pickle, and Groq-backed C4 dispute classification. See [`docs/operations/deployment.md`](docs/operations/deployment.md) for profiles, env vars, and model-source verification.

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
│   └── tests/                   ← 2,750 fast tests passing, 92% coverage
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
- **Universal 300 bps fee floor** (QUANT authority): No code may produce a fee below 300 bps annualised. Sub-day rails (CBDC, FedNow, RTP) are subject to a *tighter* additional 1200 bps floor calibrated to cost of capital — see `ADR-2026-04-25-rail-aware-maturity.md`.
- **Never commit AML typology patterns** (`c6_corpus_*.json`): CIPHER rule — generate fresh with dgen.
- **Governing law from BIC, not currency** (EPG-14): `bic_to_jurisdiction()` uses BIC chars 4–5.
- **Patent filing frozen** (CLAUDE.md non-negotiable #6): all P5/P9 continuation hooks are in code only, not filed, until counsel opines on RBC IP-assignment clause.

---

## License

Proprietary. © BPI Technology. All rights reserved. Patent pending.
