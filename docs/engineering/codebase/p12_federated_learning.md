# `lip/p12_federated_learning/` — Federated Learning Across Bank Consortium

> **Phase 3 research prototype.** Simulation and client-side plumbing for a bank-consortium federated training setup that jointly improves the C1 failure classifier without any bank ever sharing raw transaction data. **Not wired into the production pipeline.** Not in any staging profile. Do not import on the request path.

**Source:** `lip/p12_federated_learning/`
**Module count:** 8 Python files, 3,343 LoC
**Test files:** 1 (`lip/tests/test_p12_federated_learning/`)
**Architecture doc:** [`../../models/federated-learning-architecture.md`](../../models/federated-learning-architecture.md)
**Patent reference:** Patent Family 4 — Federated Learning Across Bank Consortium

---

## Status disclosure (top of file)

> This module is **research** until the following exist:
> 1. A bank consortium MOU establishing the federated training schedule and participant list
> 2. A Flower aggregator infrastructure (not currently deployed anywhere)
> 3. QUANT sign-off on `DP_EPSILON` and `DP_NOISE_MULTIPLIER` (DP privacy budget)
> 4. REX sign-off on `FEDPROX_MU_VALUES` (operating-point range)
> 5. The `flwr` optional dependency installed in the C1 training image (not currently in `Dockerfile.c1`)
>
> Until all five are true, this module exists to (a) validate the architecture against the patent claim, (b) run the μ-sweep simulation to produce convergence plots for the patent filing, and (c) provide client-side code for pilot banks to review during consortium negotiations.

---

## Purpose

C1's accuracy is bottlenecked by training corpus size. A single bank has a few hundred thousand failure events per year; a consortium of 10 banks has a few million. The privacy problem: **no bank will share raw transaction data**, and even masked transaction data risks re-identification through corridor + timestamp joins.

Federated learning is the textbook answer. Each bank trains a local model on its own data; only gradient updates (or, more precisely, gradient deltas with differential-privacy noise) are shared with a central aggregator. The aggregator averages updates across participants and produces a new global model. No raw data ever leaves the bank.

P12 implements this with three layers of privacy:

| Layer | Mechanism | What it protects against |
|-------|-----------|--------------------------|
| 1. FedProx aggregation | `μ`-regularised FedAvg via Flower | Gradient-inversion attacks that try to reconstruct training examples from per-round updates |
| 2. Differential privacy | Gaussian noise with Rényi DP accountant | Membership inference — "was bank X's payment P in the training set?" |
| 3. Communication budget | `COMM_BUDGET_BYTES_PER_ROUND` cap | Side-channel leakage via unbounded gradient size |

---

## Module map

| File | Purpose | LoC |
|------|---------|-----|
| `constants.py` | DP and FL hyperparameters. QUANT+REX sign-off required before any production change. | ~150 |
| `models.py` | `LocalModel`, `SharedModel`, `FederatedModel` — the model-splitting scheme. Local = bank-specific layers; Shared = aggregated across consortium. | 431 |
| `client.py` | `LIPFlowerClient` — implements the `flwr.client.NumPyClient` interface. Runs one round of local training + returns the gradient delta. | ~300 |
| `dp_accountant.py` | `RenyiDPAccountant` — tracks cumulative ε across training rounds. Enforces `DP_CUMULATIVE_EPSILON_MAX` — training halts if budget exhausted. | 407 |
| `privacy_engine.py` | Gaussian noise injection + gradient clipping. Wraps PyTorch autograd so DP is applied per-batch. | 407 |
| `local_ensemble.py` | Coordinates the PyTorch+LightGBM local ensemble — same architecture as C1's production model, but split for FL. | ~450 |
| `synthetic_banks.py` | `SYNTHETIC_BANK_CONFIGS` — 10 simulated banks with non-IID data distributions. Used by `simulation.py`. | 429 |
| `simulation.py` | μ-sweep driver. Runs FedProx with `μ ∈ {0.0, 0.001, 0.01, 0.1, 1.0}` and emits convergence plots + per-bank AUC. | 493 |

---

## Key hyperparameters (`constants.py`)

### DP parameters

```python
DP_EPSILON = 1.0               # per-round ε
DP_DELTA = 1e-5                # per-round δ
DP_CUMULATIVE_EPSILON_MAX = 10.0  # training halts when cumulative ε exceeds this
DP_NOISE_MULTIPLIER = 1.1      # σ / clip_norm ratio; Gaussian mechanism
DP_CLIP_NORM = 1.0             # L2 gradient clip per example
```

These are conservative choices. Textbook DP papers use `ε ∈ [0.1, 10]`; we chose 1.0 as a balance between utility (higher ε = better accuracy) and privacy (lower ε = stronger guarantee). The cumulative cap of 10.0 is the outer privacy guarantee across the full training run.

Any change to these requires:
- QUANT sign-off (utility impact on C1 AUC)
- REX sign-off (regulatory + EU AI Act Art.10 data governance)
- A fresh Rényi DP accounting computation showing the resulting guarantee

### FedProx parameters

```python
FEDPROX_MU_MIN = 0.0           # reduces to FedAvg
FEDPROX_MU_MAX = 1.0
FEDPROX_MU_VALUES = [0.0, 0.001, 0.01, 0.1, 1.0]  # the sweep set
```

μ is the proximal coefficient in FedProx — higher values pull each client's local optimum closer to the global model, which helps when clients have very heterogeneous data. For LIP the inter-bank heterogeneity is substantial (different BIC footprints, different corridor mixes), so a non-zero μ is expected to help.

### Training hyperparameters

```python
LEARNING_RATE = 1e-3           # client-side local optimiser
LOCAL_EPOCHS = 5               # epochs per FL round, per client
NUM_ROUNDS = 50                # total FL rounds
NUM_SEEDS = 3                  # repetitions for confidence intervals in plots
```

50 rounds × 10 clients × 5 local epochs = 2500 effective training epochs across the consortium. Single-bank training would be ~20 epochs — the FL setup trades compute for data diversity.

---

## The model-splitting scheme (`models.py`)

Not every layer is federated. The model is split into:

| Layer | Federated? | Rationale |
|-------|-----------|-----------|
| Bank-specific input embeddings | NO (local-only) | Each bank has a different BIC set; forcing shared embeddings would require coordinating on BIC coverage across the consortium |
| GraphSAGE graph-convolutional layers | YES (shared) | Graph topology of correspondent banking is largely consortium-common |
| TabTransformer attention | YES (shared) | Tabular feature interactions generalise across banks |
| LightGBM boosting | NO (local-only) | Tree ensembles don't aggregate cleanly under FedAvg |
| Final prediction head | YES (shared) | Calibration benefits from consortium scale |

The `SharedModel` has `COMBINED_INPUT_DIM = 200` dimensions out of a ~350-dim full model. Only the 200 shared dims get federated updates; the 150 local-only dims stay on-bank.

---

## Simulation (`simulation.py`)

The primary entry point today. Does NOT run against real Flower infrastructure — it simulates federated training in-process:

```bash
PYTHONPATH=. python -m lip.p12_federated_learning.simulation \
    --num-banks 10 \
    --rounds 50 \
    --mu-sweep \
    --output artifacts/p12_simulation
```

Outputs:
- `convergence_{mu}.png` — AUC vs. rounds for each μ
- `per_bank_auc.png` — fairness analysis (no bank is systematically worse than others)
- `dp_budget.json` — cumulative ε after each round
- `comparison.csv` — centralised training baseline vs. federated results

These artifacts feed:
1. The patent filing for Patent Family 4
2. Pilot-bank technical due-diligence reviews (showing that consortium training works without raw data sharing)
3. Regulator conversations (demonstrating DORA Art.10 data minimisation)

---

## Expected production flow (when the prerequisites exist)

```
  ┌─────────────────────────────┐
  │  Bank A on-prem LIP install │ ─┐
  │    LIPFlowerClient          │  │
  └─────────────────────────────┘  │
                                   │  encrypted gradient deltas
  ┌─────────────────────────────┐  │  (each client sees only its own
  │  Bank B on-prem LIP install │ ─┤  raw data; never the aggregate)
  │    LIPFlowerClient          │  │
  └─────────────────────────────┘  │
                                   │
           ... up to 10 banks ...  │
                                   ▼
                    ┌────────────────────────────┐
                    │  Flower Aggregator (BPI)   │
                    │    Secure aggregation +    │
                    │    Rényi DP accounting     │
                    └────────────────────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────┐
                    │  Updated C1 SharedModel    │
                    │  distributed back to all   │
                    │  banks at next round       │
                    └────────────────────────────┘
```

The aggregator is **not yet deployed.** It would run on BPI infrastructure (or a neutral third-party) with:

- TLS + mTLS between all clients and the aggregator
- Aggregator never persists individual gradient deltas (secure aggregation)
- Post-round DP noise injected before re-distribution
- Audit log of cumulative ε + QUANT sign-off on round continuation

---

## Operator caveats

- **Do NOT import `lip.p12_federated_learning.client` in production code.** The Flower client reaches out over network — it has no place in the request path.
- **Do NOT run the simulation on production data** even as a test. The synthetic banks in `synthetic_banks.py` are the only approved inputs until the consortium MOU exists.
- **The `constants.py` values are provisional.** A real consortium will negotiate these — they are starting points for that conversation, not final operational parameters.

---

## Cross-references

- **Architecture doc**: [`../../models/federated-learning-architecture.md`](../../models/federated-learning-architecture.md)
- **Patent reference**: Patent Family 4 — see [`../../legal/patent/`](../../legal/patent/)
- **C1 codebase reference**: [`c1_failure_classifier.md`](c1_failure_classifier.md) — the model that FL updates
- **EPG-20 / EPG-21 language scrub**: [`../../legal/decisions/EPG-20-21_patent_briefing.md`](../../legal/decisions/EPG-20-21_patent_briefing.md) — applies to any outward copy about FL
- **Academic references**:
  - McMahan et al., "Communication-Efficient Learning of Deep Networks from Decentralized Data," AISTATS 2017
  - Li et al., "Federated Optimization in Heterogeneous Networks," ICLR 2020 (FedProx)
  - Abadi et al., "Deep Learning with Differential Privacy," CCS 2016
  - Mironov, "Rényi Differential Privacy," CSF 2017
  - Flower framework: https://flower.dev/
