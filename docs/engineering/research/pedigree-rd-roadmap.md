# LIP Pedigree R&D Roadmap: Algorithmic Moats & Institutional Expertise
**Status:** CONFIDENTIAL R&D STRATEGY — BACKBONE ONLY
**Version:** 1.0
**Date:** March 13, 2026

## 1. Philosophical Foundation: "The Pedigree"
Our objective is to move beyond standard software engineering into high-pedigree algorithmic research. The platform must reflect a deep understanding of market microstructure, credit theory, and network topology. Expertise should be self-evident in the precision of our solvers, the robustness of our simulations, and the auditability of our decisions.

## 2. Tier 1 R&D: Foundational Mathematical Rigor

### 2.1 Merton-KMV Iterative Solvers (C2 Upgrade)
*   **Current State:** Linear approximation or simple numpy-based solver.
*   **Pedigree Goal:** Implement a robust Newton-Raphson iterative procedure to back out implied asset value ($V_A$) and asset volatility ($\sigma_A$) from observable equity data.
*   **Expertise Marker:** Graceful handling of edge cases (e.g., zero-debt, extreme equity volatility) using barrier-method constraints.

### 2.2 Isotonic Calibration (C1 Precision)
*   **Current State:** Raw classifier outputs.
*   **Pedigree Goal:** Implement a calibration layer using Isotonic Regression to ensure failure probabilities reflect true posterior frequencies.
*   **Expertise Marker:** Reporting Expected Calibration Error (ECE) in every inference response, ensuring the score is "pricing-ready."

## 3. Tier 2 R&D: Adversarial Resilience & Game Theory

### 3.1 Adversarial Cancellation Detection (camt.056)
*   **Innovation:** Detection of the "Recall Attack" where a sender cancels a payment *after* a bridge loan is disbursed but before final settlement.
*   **Pedigree Goal:** Build a dual-stream intent classifier that distinguishes legitimate error correction from adversarial "double-spend" attempts using temporal and behavioral feature sets.
*   **Simulation Requirement:** Update `dgen` to model camt.056/pacs.004 return loops.

## 4. Tier 3 R&D: Network Topology & Cascade Risk

### 4.1 Supply Chain Cascade Propagation (P5) — ✅ COMPLETE
*   **Innovation:** Modeling the SWIFT network not just as BICs, but as a directed graph of business dependencies.
*   **Implemented:** Bayesian smoothing (k=5 prior weight) eliminates first-payment score over-inflation in `graph_builder.py`. `get_cascade_risk()` returns `(at_risk_bics, CascadeConfidence)` with confidence intervals.
*   **Expertise Marker:** Graph-centrality-weighted risk scores that identify "Super-Spreaders" of payment failure.

## 5. Horizon R&D: Future Infrastructure

### 5.1 CBDC Bridging & Smart Contract Finality (P9) — ✅ COMPLETE (Research Phase)
*   **Focus:** Mapping ISO 20022 rejection codes to CBDC smart-contract execution errors.
*   **Delivered:** `docs/cbdc-protocol-research.md` — BIS mBridge (MVP 2024), ECB DLT pilot, FedNow analysis. CBDC failure code taxonomy, `normalize_cbdc()` handler shape, `SettlementRail.CBDC` stub for C3. 4 patent claims documented. Phase 2 implementation pending pilot.

### 5.2 Federated Learning Privacy Proxy (P12) — ✅ COMPLETE (Architecture Phase)
*   **Focus:** Training global failure classifiers across multiple banks without moving raw transaction data.
*   **Delivered:** `docs/federated-learning-architecture.md` — FedProx selected (non-IID robustness), DP-SGD (ε=1.0, δ=1e-5), Flower + Opacus framework, layer partitioning (local: BIC embeddings; shared: final aggregation layers). 4 patent claims documented. Phase 2 pending pilot bank onboarding.

## 6. Execution Mandates
1.  **Simulation First:** No model is "expert" if the world it was trained in is naive. Simulations must include "Black Swan" events and adversarial behavior.
2.  **Audit Trail:** Every algorithmic decision must be decomposeable via SHAP or similar attribution methods.
3.  **Numerical Stability:** Prefer `Decimal` and robust solvers over standard library defaults for all financial arithmetic.
