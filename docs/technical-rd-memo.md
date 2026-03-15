# LIP Technical R&D Memo: specialised Logic & Architectural Pedigree
**Status:** INTERNAL R&D — ACTIVE BACKBONE
**Date:** March 13, 2026

## 1. Executive Summary
This memo documents the current specialised R&D state of the Liquidity Intelligence Platform (LIP). We have moved beyond basic payment monitoring into a patent-backed, multi-model AI architecture designed for institutional-grade reliability and regulatory compliance (SR 11-7, EU AI Act). The platform's "pedigree" is defined by its deep integration of graph-theory-based risk scoring, LLM-driven dispute detection, and a three-entity capital model.

## 2. Specialised Component R&D

### C1: Neural Payment Network Analysis
*   **Architecture:** GraphSAGE (GNN) + TabTransformer.
*   **Innovation:** We model the SWIFT network as a dynamic multigraph. BIC nodes encode topological features (Betweenness Centrality, PageRank) while TabTransformer handles the heterogeneous ISO 20022 message metadata.
*   **Current Pedigree:** Real-time neighborhood sampling (k=5) ensures inference within a 30ms budget while capturing network-level contagion risks.

### C2: Multi-Tiered Credit Pricing
*   **Architecture:** 5x LightGBM Ensemble with learned feature masking.
*   **Innovation:** A unified model that replaces rigid routing. It distinguishes listed corporates (Merton structural models) from thin-file SMEs by learning the "pattern of missingness" in financial data.
*   **Governance:** Mandatory Platt scaling for probability calibration, ensuring `fee_bps` (floor 300 bps) reflects absolute risk, not just relative ranking.

### C4: Adversarial Dispute Detection
*   **Architecture:** Fast-path Keyword Prefilter + Async LLM (Fine-tuned Llama-3 8B).
*   **Innovation:** Logit-constrained output ensures the LLM acts as a high-precision classifier, not a generative agent. Dedicated "negation suite" R&D prevents false-positives on phrases like "no dispute confirmed."

### C7: Safe Execution & Human-in-the-Loop
*   **Architecture:** HMAC-signed Immutable Decision Logs + Art.14 Override Workflow.
*   **Innovation:** Every AI decision is stamped with SHAP values (feature importance) and signed to prevent tampering. This satisfies the EU AI Act's transparency requirements for high-risk financial AI.

## 3. Business Logic "Pedigree"
*   **Three-Entity Model:** Clear separation of MLO (Capital), MIPLO (Technology/BPI), and ELO (Execution/Bank).
*   **Royalty Engine:** Automated 15% technology licensor royalty calculation integrated into the repayment loop.
*   **Portfolio Reporting:** Real-time API for capital providers showing aggregate exposure by corridor, tier, and yield.

## 4. Current R&D Roadmap (Backbone Priority)
1.  **Supply Chain Cascade Propagation:** Implementing P5 (Supply Chain Patent) logic to predict downstream failures from upstream rejections.
2.  **Cross-Network Interoperability (P9):** Researching inter-rail failure modes between SWIFT gpi and emerging CBDC networks.
3.  **Federated Learning (P12):** Investigating privacy-preserving model updates across multiple bank licensees without raw data sharing.

## 5. Architectural Mandates for Sub-Agents
*   **Precision over Simplicity:** Use `Decimal` for all math. Use `datetime` with `timezone.utc`.
*   **Auditability:** Every new logic gate must produce a `DecisionLogEntry` record.
*   **Numerical Stability:** Implement robust solvers for Merton-type calculations; handle zero-volatility and zero-debt regimes gracefully.
