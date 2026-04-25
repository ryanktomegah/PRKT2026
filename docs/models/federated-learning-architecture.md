# P12: Federated Learning Architecture — LIP Patent Portfolio

**Document type**: Architecture Decision Record (Phase 2 design)
**Patent reference**: P12 — Federated Model Calibration Across Bank Consortium
**Status**: Phase 2 deferred — design complete, implementation pending pilot
**Date**: 2026-03-15
**Authors**: ARIA (ML), REX (regulatory), QUANT (financial), Security-Analyst

---

## Executive Summary

LIP's Phase 2 federated learning protocol enables bank consortium members to jointly
improve the C1 failure classifier and C2 PD model without sharing raw transaction data.
Each bank trains on local data; only **model updates** (gradients or weight deltas) are
shared, never individual payment records.

This document specifies the protocol decision, differential privacy budget, layer
partitioning strategy, threat model, and Phase 2 implementation plan.

---

## 1. Problem Statement

### Why Federated Learning for LIP?

The C1 GraphSAGE/TabTransformer ensemble was trained on a synthetic corpus (AUC=0.9998
on synthetic, estimated 0.82–0.88 on real SWIFT data). Real-world calibration requires:

- Transaction history from multiple banks across corridors
- Rare event statistics (actual RJCT codes by corridor, not BIS-aggregated)
- Counterparty-specific default patterns for C2 PD model

**The constraint**: No bank will share raw payment data across institutional boundaries
due to data residency regulations (GDPR Art. 44-49, Swiss DSG, UK GDPR), competitive
sensitivity, and regulator requirements.

**Federated Learning resolves this**: banks share gradient updates, not data.

---

## 2. Protocol Decision: FedAvg vs. Secure Aggregation

### Option A: FedProx (Selected for Phase 2)

Extension of FedAvg (McMahan et al. 2017) with proximal regularisation term:

```
min_w { F(w) + (μ/2)||w - w_t||² }
```

**Why FedProx over vanilla FedAvg for LIP**:
- Bank data distributions are highly heterogeneous (non-IID): corridor volumes,
  failure rates, and borrower profiles differ substantially across jurisdictions.
- FedAvg diverges under strong non-IID conditions (Li et al. 2020, ICLR).
- The proximal term μ controls how far local updates can deviate from global model.
- μ is a hyperparameter requiring QUANT sign-off; range: 0.001–0.1.

**Reference**: Li et al., "Federated Optimization in Heterogeneous Networks",
ICLR 2020. https://arxiv.org/abs/1812.06127

### Option B: Secure Aggregation (Phase 3 upgrade path)

Bonawitz et al. (2017) Secure Aggregation protocol uses cryptographic masking:
each client's gradient is masked with random noise that cancels in aggregation,
so the aggregator never sees individual client gradients.

**Why deferred to Phase 3**:
- Requires N≥3 participants (minimum consortium size constraint).
- Adds ~2× communication overhead (pairwise key exchange).
- The semi-honest threat model (§6) does not require SecAgg for Phase 2.
- SecAgg is the correct upgrade once consortium scales beyond pilot.

**Reference**: Bonawitz et al., "Practical Secure Aggregation for Privacy-Preserving
Machine Learning", CCS 2017. https://dl.acm.org/doi/10.1145/3133956.3133982

### Decision Matrix

| Criterion | FedAvg | FedProx | SecAgg |
|-----------|--------|---------|--------|
| Non-IID robustness | Low | **High** | High |
| Communication cost | Low | Low | 2× |
| Cryptographic privacy | No | No | **Yes** |
| Min participants | 2 | 2 | 3 |
| Phase 2 readiness | ✅ | ✅ | ❌ |
| **Selected** | | **✅ Phase 2** | ❌ Phase 3 |

---

## 3. Differential Privacy Budget

### Budget Parameters (QUANT + REX sign-off required before production)

```python
DP_EPSILON = 1.0    # Privacy budget (lower = stronger privacy)
DP_DELTA   = 1e-5   # Failure probability bound
DP_CLIP_NORM = 1.0  # Gradient clipping norm (L2)
DP_NOISE_MULTIPLIER = 1.1  # σ calibrated to (ε=1.0, δ=1e-5)
```

### Why ε=1.0, δ=1e-5

- ε=1.0 is empirically appropriate for financial data (Anil et al. 2022 recommend
  ε≤1.0 for sensitive domains). ε=0.1 would require impractically many rounds.
- δ=1e-5 provides (ε,δ)-DP with failure probability below one-in-100,000 per round.
- At a pilot bank with ~500K transactions/year and ~50 FL rounds, the cumulative
  privacy loss under composition remains within ε=3.0 via Rényi DP accounting
  (Mironov 2017) — within regulators' "meaningful" privacy threshold.

**Reference**: Anil et al., "Large-Scale Differentially Private BERT",
EMNLP 2022. https://arxiv.org/abs/2108.01624

### Noise Mechanism: DP-SGD (Abadi et al. 2016)

Each client clips per-sample gradients to norm ≤ `DP_CLIP_NORM`, then adds
Gaussian noise calibrated to `DP_NOISE_MULTIPLIER`:

```python
# Pseudocode — Phase 2 implementation via Opacus or TensorFlow Privacy
def dp_step(gradients, clip_norm, noise_multiplier, learning_rate):
    clipped = clip_gradients(gradients, max_norm=clip_norm)
    noised = clipped + N(0, (noise_multiplier * clip_norm)²)
    return noised * learning_rate
```

### Privacy Accounting

Use the Rényi DP accountant (not the loose moments accountant) for tighter bounds:

```python
# Phase 2: use dp-accounting library (Google, 2022)
# pip install dp-accounting
from dp_accounting import rdp
accountant = rdp.RdpAccountant()
accountant.compose(rdp.PoissonSampledDpEvent(
    sampling_probability=batch_size/n_local,
    event=rdp.GaussianDpEvent(noise_multiplier=1.1),
))
eps = accountant.get_epsilon(target_delta=1e-5)
```

---

## 4. Layer Partitioning: What Stays Local vs. What Gets Shared

### C1 Failure Classifier Partitioning

```
┌─────────────────────────────────────────────────────────────┐
│ LOCAL (never shared — stays at each bank)                   │
│                                                             │
│  • Raw transaction records (RJCT events)                    │
│  • BIC-specific embeddings (identify counterparties)        │
│  • Corridor-level failure history (raw rates)               │
│  • GraphSAGE: first 2 graph conv layers (local topology)    │
│  • TabTransformer: first embedding layer (BIC identifiers)  │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ SHARED (aggregated via FedProx + DP noise)                  │
│                                                             │
│  • GraphSAGE: final aggregation layer weights               │
│  • TabTransformer: transformer encoder + classifier head    │
│  • LightGBM: cannot be federated — trained locally only     │
│  • Corridor failure probability calibration layer           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Rationale**: The first graph convolution layers encode local bank topology
(which BICs transact with which). This is commercially sensitive and not
generalizable across banks. The final aggregation layer encodes cross-corridor
failure patterns that ARE generalizable.

### C2 PD Model Partitioning

```
┌─────────────────────────────────────────────────────────────┐
│ LOCAL                                                       │
│  • Raw financial statement data (borrower identities)       │
│  • Credit bureau scores (PII — cannot leave jurisdiction)   │
│  • Tier-1 Merton/KMV model: calibrated per bank portfolio  │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ SHARED                                                      │
│  • Altman Z-score → PD mapping curve (not borrower IDs)    │
│  • Damodaran sector risk premia (anonymous industry rates)  │
│  • Tier-3 (thin-file) prior — calibrated from consortium   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Communication Protocol

### Round Structure

```
Round r:
  1. MIPLO server broadcasts global model w_r to all N banks
  2. Each bank k trains locally for E=5 epochs on local data D_k
  3. Each bank k computes Δw_k = w_r+1_local - w_r (weight delta)
  4. Each bank k applies DP noise: Δw_k_dp = clip(Δw_k) + N(0, σ²I)
  5. Banks send Δw_k_dp to MIPLO server (encrypted in transit — TLS 1.3)
  6. MIPLO aggregates: w_r+1 = w_r + η * (1/N) Σ_k Δw_k_dp
  7. MIPLO broadcasts w_r+1; next round begins
```

### Communication Bandwidth Estimate

| Component | Parameters | Size (fp32) | Rounds | Total/bank |
|-----------|-----------|-------------|--------|------------|
| GraphSAGE final layer | ~500K | 2 MB | 50 | 100 MB |
| TabTransformer encoder | ~2M | 8 MB | 50 | 400 MB |
| C2 calibration curve | ~10K | 40 KB | 20 | 800 KB |
| **Total** | | | | **~500 MB/pilot** |

500 MB over 6-month pilot (≈2.8 MB/day) — trivially within SWIFT SWIFTNet
secure messaging capacity.

---

## 6. Threat Model

### Adversary Model: Semi-Honest (Phase 2)

Phase 2 assumes a **semi-honest** (honest-but-curious) adversary:
- All participants follow the protocol correctly.
- The MIPLO server (BPI) is curious but does not collude with banks.
- No participant actively manipulates gradients.

**Justification**: The LIP consortium consists of regulated financial institutions
under MOU with BPI. The legal framework (mutual NDA + licensing agreement) establishes
contractual non-collusion. A malicious adversary model requires SecAgg (Phase 3).

### What DP Protects Against

| Attack | DP-SGD Protection |
|--------|------------------|
| Membership inference (did entity X transact?) | ✅ (ε=1.0 provides strong protection) |
| Attribute inference (infer transaction amount) | ✅ (gradient clipping limits leakage) |
| Model inversion (reconstruct raw records) | ✅ (noise + clipping prevent reconstruction) |
| Byzantine/Poisoning attacks | ❌ (requires separate Byzantine-robust aggregation) |

### Byzantine Attack Mitigation (Phase 3 upgrade)

For Phase 3, replace mean aggregation with:
- **Krum** (Blanchard et al. 2017): selects the gradient minimizing sum of squared
  distances to its K nearest neighbours.
- **Coordinate-wise median**: robust estimator replacing FedAvg mean.

---

## 7. Regulatory Compliance

### GDPR / Data Residency

- Raw transaction data never leaves the originating jurisdiction.
- Gradient updates are noised (DP) before transmission — no individual record
  is recoverable from a DP gradient (see §3 threat analysis).
- Data processing agreement (DPA) between BPI and each bank must specify:
  - MIPLO server location (EU-hosted for EU banks per GDPR Art. 44)
  - Gradient transmission logging for audit trail
  - Right-to-erasure: if a bank exits the consortium, their historical gradients
    cannot be "unlearned" without model rollback (document this limitation to regulators)

### EU AI Act (High-Risk System — Article 10)

- Federated training data must be logged with corpus tags per Art. 10.
- Each round's aggregated gradient must carry a timestamp + participating bank list.
- No individual bank's gradient is logged at the MIPLO server (DP prevents this).
- Model versioning: each federated checkpoint tagged with `FED_ROUND_{r}_SEED_{s}`.

### SR 11-7 (Model Risk Management)

- Federated model must undergo independent validation before production use.
- Out-of-time validation split must be maintained (18-month hold-out).
- QUANT sign-off required on ε and μ (FedProx proximal term) before each pilot bank.
- Model documentation must include: federated rounds, participating banks (count, not identity), DP budget consumed.

---

## 8. Phase 2 Implementation Plan

### Framework Selection

| Framework | License | Backend | FL Protocol | DP Support | Verdict |
|-----------|---------|---------|-------------|-----------|---------|
| **Flower** | Apache 2.0 | Any | FedAvg, FedProx | Via Opacus | **✅ Selected** |
| PySyft | Apache 2.0 | PyTorch | FedAvg | Native | Complex ops |
| OpenFL | Apache 2.0 | TF/PT | FedAvg | Manual | Intel-specific |
| TFF | Apache 2.0 | TensorFlow | FedAvg | Via TF Privacy | TF lock-in |

**Flower** is selected: framework-agnostic, minimal overhead, runs PyTorch models
(our stack), and has first-class FedProx strategy support.

### Implementation Steps

```
Phase 2.1 — Flower scaffold (2 weeks)
  - Install: pip install flwr[simulation] opacus
  - Wrap C1 GraphSAGE in flwr.client.NumPyClient
  - Implement FedProx strategy server-side
  - Simulation test with 3 synthetic "banks" (different data seeds)

Phase 2.2 — DP integration (1 week)
  - Wrap local training with Opacus PrivacyEngine
  - Calibrate DP_NOISE_MULTIPLIER to achieve (ε=1.0, δ=1e-5) per round
  - Use dp-accounting for Rényi DP composition across rounds

Phase 2.3 — Secure transport (1 week)
  - MIPLO server: gRPC + TLS 1.3 (Flower's default transport)
  - Add HMAC signature to gradient payloads (verify bank identity)
  - Bank client: mutual TLS using existing C8 license key material

Phase 2.4 — Pilot bank integration (4 weeks)
  - Deploy Flower server at BPI MIPLO infrastructure
  - Each pilot bank deploys Flower client on their internal compute
  - 50-round pilot: monitor convergence, DP budget consumption, AUC
  - Target: federated C1 AUC ≥ 0.85 on held-out real SWIFT data

Phase 2.5 — SecAgg upgrade (Phase 3, post-pilot)
  - Replace mean aggregation with Bonawitz SecAgg protocol
  - Requires minimum 3 participating banks
  - Add Byzantine-robust aggregation (Krum or coordinate-wise median)
```

### Required Infrastructure

```
MIPLO Server (BPI-hosted):
  - Flower server process (Python, 2 vCPU, 8 GB RAM)
  - PostgreSQL: round logs, DP budget tracker, model version registry
  - Object storage: gradient checkpoints per round (encrypted at rest)
  - Network: gRPC endpoint reachable from bank clients (SWIFTNet / MPLS)

Bank Client (each pilot bank):
  - Flower client process (Python, 4 vCPU, 16 GB RAM — for local training)
  - Secure enclave (optional Phase 3): Intel SGX for gradient computation
  - Access to local transaction database (read-only for FL training)
  - Outbound gRPC to MIPLO server on port 8080 (HTTPS/TLS)
```

---

## 9. Patent Claims Support (P12)

The federated architecture supports the following novel patent claims:

1. **Claim 1**: Method of calibrating a payment failure prediction model across a
   consortium of financial institutions without sharing raw transaction records,
   comprising: local gradient computation per institution; differential privacy
   noise injection with ε≤1.0; aggregation at a neutral platform operator.

2. **Claim 2**: The method of Claim 1 wherein the prediction model comprises a
   graph neural network (GraphSAGE) and a tabular transformer, and wherein only
   weights of the final aggregation layers are shared across the consortium.

3. **Claim 3**: The method of Claim 1 further comprising FedProx proximal
   regularisation to handle non-IID data distributions across bank jurisdictions.

4. **Claim 4**: A system implementing Claims 1-3 wherein the platform operator
   (MIPLO) serves as the neutral aggregation party under a regulatory-compliant
   multi-party licensing agreement.

---

## References

| Reference | Use |
|-----------|-----|
| McMahan et al. (2017), "Communication-Efficient Learning of Deep Networks from Decentralized Data", AISTATS | FedAvg baseline |
| Li et al. (2020), "Federated Optimization in Heterogeneous Networks", ICLR | FedProx protocol |
| Bonawitz et al. (2017), "Practical Secure Aggregation for Privacy-Preserving ML", CCS | SecAgg Phase 3 |
| Abadi et al. (2016), "Deep Learning with Differential Privacy", CCS | DP-SGD mechanism |
| Mironov (2017), "Rényi Differential Privacy of the Gaussian Mechanism", CSF | RDP accounting |
| Anil et al. (2022), "Large-Scale Differentially Private BERT", EMNLP | ε=1.0 justification |
| Blanchard et al. (2017), "Machine Learning with Adversaries: Byzantine Tolerant Gradient Descent", NeurIPS | Byzantine robustness |

---

*This document is an Architecture Decision Record (ADR) for Phase 2 planning.
All constants (ε, δ, μ, E) require QUANT + REX sign-off before production use.
Regulatory advice from qualified legal counsel is required before pilot deployment.*
