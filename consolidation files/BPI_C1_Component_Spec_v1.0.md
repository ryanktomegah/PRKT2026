# BRIDGEPOINT INTELLIGENCE INC.
## COMPONENT 1 — FAILURE PREDICTION CLASSIFIER
## Build Specification v1.0
### Phase 1 Deliverable — Internal Use Only

**Date:** March 4, 2026
**Version:** 1.0
**Lead:** ARIA — ML & AI Engineering
**Support:** NOVA (feature pipeline integration), FORGE (serving infrastructure)
**Status:** ACTIVE BUILD
**Stealth Mode:** Active — Nothing External

---

## TABLE OF CONTENTS

1.  Purpose & Scope
2.  Architecture Overview
3.  Graph Construction Specification
4.  Feature Engineering Specification
5.  GNN Architecture (GraphSAGE)
6.  TabTransformer Architecture
7.  Model Combination & Output Head
8.  Corridor Embedding Pipeline (resolves Architecture Spec S11.1 flag)
9.  Training Data Specification
10. Training Pipeline
11. Validation Requirements (Roadmap Audit Gate 1.1)
12. SHAP Explainability Specification
13. Model Versioning & Registry
14. Known Limitations & Honest Ceiling
15. Audit Gate 1.1 Checklist

---

## 1. PURPOSE & SCOPE

C1 replaces the existing XGBoost baseline classifier (AUC 0.739).
Target: AUC ≥ 0.85 on held-out test set.
ARIA is required to report the honest measured result — not just
whether the target was achieved.

C1 is the first component executed on every payment failure event.
Its failure_probability output drives the decision to generate a
loan offer. False negatives (predicting temporary when permanent)
are more costly than false positives — this asymmetry must be
reflected in the loss function and threshold selection.

C1 scope:
  - Graph construction and maintenance
  - Real-time inference (GPU, p50 <30ms, p99 <50ms at node level)
  - Corridor embedding generation and Redis storage
  - SHAP value computation per inference
  - Model versioning and hot-swap

C1 does NOT:
  - Make credit pricing decisions (C2)
  - Screen for disputes (C4)
  - Screen for AML (C6)

---

## 2. ARCHITECTURE OVERVIEW

```
Input: pacs.002 RJCT event
         |
         | UETR, BIC_sender, BIC_receiver,
         | rejection_code, amount_usd,
         | currency_pair, timestamp_utc
         v
+---------------------------+     +---------------------------+
|   GRAPH CONTEXT           |     |   TABULAR FEATURES        |
|   (Redis lookup)          |     |   (real-time extraction)  |
|                           |     |                           |
|  sender_node_emb [128]    |     |  rejection_code_emb [32]  |
|  receiver_node_emb [128]  |     |  amount_tier_emb [16]     |
|  corridor_edge_emb [128]  |     |  currency_pair_emb [16]   |
|                           |     |  time_features [8]        |
+---------------------------+     |  jurisdiction_emb [16]    |
         |                        +---------------------------+
         |                                   |
         v                                   v
   [GraphSAGE output]               [TabTransformer output]
       [384 dims]                        [88 dims]
         |                                   |
         +-------------------+---------------+
                             |
                    Concatenate [472 dims]
                             |
                    MLP head (3 layers)
                             |
                    failure_probability [0-1]
                    + SHAP values [top 20]
```

---

## 3. GRAPH CONSTRUCTION SPECIFICATION

### 3.1 Graph Definition

The payment network is modeled as a directed multigraph G = (V, E):

  V: Nodes — individual banks, identified by 8-character BIC code
     (BIC8, zero-padding if needed for consistency)

  E: Directed edges — payment corridors between bank pairs
     Edge (u → v) exists if bank u has sent payments to bank v
     in the training period.
     Multiple currency pairs between same bank pair = multiple edges
     (one edge per unique BIC_sender × BIC_receiver × currency_pair)

**Node count estimate:** ~4,000-8,000 nodes (active SWIFT member banks)
**Edge count estimate:** ~50,000-120,000 edges (active corridors)

### 3.2 Node Features

Each node (bank) carries a feature vector built at graph update time:

```
NodeFeatures {
  // Identity
  country_code_emb          : float[16]   // Learned embedding, ISO 3166
  swift_member_category     : float[4]    // DIRECT, INDIRECT, SUB_MEMBER, FIN
  regulatory_tier           : float[4]    // G-SIB, D-SIB, REGIONAL, COMMUNITY

  // Network topology (computed from graph structure)
  in_degree_normalized      : float       // Normalized [0,1] across all nodes
  out_degree_normalized     : float
  betweenness_centrality    : float       // Precomputed, updated weekly
  pagerank_score            : float       // Precomputed, updated weekly

  // Historical behavior (rolling 90-day)
  rejection_rate_as_sender  : float       // Outbound rejections / outbound total
  rejection_rate_as_receiver: float       // Inbound rejections / inbound total
  avg_settlement_hours      : float       // Mean settlement time (outbound)
  p95_settlement_hours      : float       // P95 settlement time (outbound)
  volume_tier               : float       // Log-normalized transaction volume

  TOTAL: ~28 raw features → node_feature_vector [28]
}
```

### 3.3 Edge Features

Each edge (corridor) carries:

```
EdgeFeatures {
  currency_pair_emb         : float[8]    // Learned embedding
  rejection_rate_30d        : float       // Rolling 30-day rejection rate
  rejection_rate_90d        : float       // Rolling 90-day rejection rate
  p50_settlement_hours      : float       // Corridor-specific P50
  p95_settlement_hours      : float       // Corridor-specific P95 (buffer src)
  volume_normalized         : float       // Log-normalized corridor volume
  class_a_rate              : float       // Fraction of rejections: Class A
  class_b_rate              : float
  class_c_rate              : float
  hard_block_rate           : float       // Fraud/sanctions hit rate
  days_active               : float       // Corridor age in days, normalized

  TOTAL: ~18 raw features + 8 currency embedding → [26]
}
```

### 3.4 Graph Update Schedule

**Full rebuild:** Weekly (Sunday 02:00 UTC)
  - Recompute centrality measures (betweenness, PageRank)
  - Rebuild node and edge feature vectors from 90-day history
  - Retrain GraphSAGE layers on updated graph
  - Update all corridor_embeddings in Redis

**Incremental update:** Daily (02:00 UTC)
  - Update rolling rejection_rate, settlement times, volume
  - No retraining of model weights
  - Corridor embeddings updated via forward pass (no retrain)

**Triggered update:** Immediate, event-driven
  - New BIC registered in payment network → add node, zero features
  - New corridor observed → add edge, zero features, Tier 0 bootstrap
  - Node/edge features updated after 100+ observations

### 3.5 Cold Start Handling

New node (bank): Initialize with country and category defaults.
  - rejection_rate_as_sender/receiver = global mean for country
  - settlement hours = global P50/P95 for country
  - topology metrics = 0.0 (no network history)

New edge (corridor): Initialize with currency pair class defaults.
  - Same as Tier 0 corridor bootstrap from Architecture Spec S11.4
  - Corridor embedding initialized to mean of all corridors for
    same currency_pair (not zero — zero vector is anomalous input)

Self-critique: zero-vector initialization for new corridors was
flagged during Architecture Spec sign-off. Currency-pair mean is
the correct fix and is implemented here.

---

## 4. FEATURE ENGINEERING SPECIFICATION

### 4.1 Tabular Feature Set (Real-Time, Per-Payment)

These features are computed at inference time from the incoming
pacs.002 event and Redis lookups. Target: computed in <2ms.

```
TabularFeatures {
  // Rejection code (categorical, 30+ values + UNKNOWN)
  rejection_code_emb        : float[32]   // Learned embedding
                                          // Trained on code × outcome matrix
  rejection_code_class      : float[3]    // One-hot: A, B, C (or BLOCK)

  // Amount features
  amount_usd_log            : float       // log1p(amount_usd)
  amount_tier               : float[4]    // <10K, 10K-100K, 100K-1M, >1M
  amount_percentile_corridor: float       // Percentile within corridor history

  // Time features (cyclical encoding)
  hour_sin                  : float       // sin(2π * hour / 24)
  hour_cos                  : float       // cos(2π * hour / 24)
  day_of_week_sin           : float
  day_of_week_cos           : float
  is_month_end              : float       // 0/1 — elevated rejection risk
  is_quarter_end            : float       // 0/1

  // Jurisdiction
  sender_country_emb        : float[8]    // Derived from BIC
  receiver_country_emb      : float[8]

  // Currency pair
  currency_pair_emb         : float[16]   // Learned embedding

  TOTAL: ~88 features
}
```

### 4.2 Feature Computation SLA

All tabular features must be computed within 2ms on the critical path.

| Feature Group           | Source              | Latency |
|-------------------------|---------------------|---------|
| rejection_code_emb      | In-memory lookup    | <0.1ms  |
| amount features         | Arithmetic          | <0.1ms  |
| time features           | Arithmetic          | <0.1ms  |
| jurisdiction features   | In-memory BIC table | <0.1ms  |
| currency_pair_emb       | In-memory lookup    | <0.1ms  |
| corridor_embedding      | Redis GET           | ~1ms    |
| sender/receiver node emb| Redis GET           | ~1ms    |

Total: <2.5ms — within the 2ms feature extraction budget (acceptable
with 0.5ms slack; optimize Redis GETs as multi-GET batch to reach <2ms)

### 4.3 Feature Normalization

Continuous features: StandardScaler fit on training data
Amount features: log1p transform before scaling
Time features: cyclical sin/cos encoding (already bounded [-1,1])
Categorical embeddings: L2-normalized at training time

Normalization parameters persisted as part of model artifact.
Inference uses frozen training normalization parameters — no
re-normalization in production.

---

## 5. GNN ARCHITECTURE — GRAPHSAGE

### 5.1 Why GraphSAGE

Three GNN variants considered:

| Variant     | Inductive | Speed   | Scalability | Selected |
|-------------|-----------|---------|-------------|----------|
| GCN         | No        | Fast    | Poor        | No       |
| GAT         | Yes       | Slow    | Medium      | No       |
| GraphSAGE   | Yes       | Medium  | Excellent   | YES      |

GraphSAGE (Hamilton et al., 2017) is selected because:
1. Inductive: handles new banks (nodes) without full graph retraining
2. Scales to 8,000+ nodes / 120,000+ edges without memory issues
3. Neighborhood sampling controls compute per node at inference

### 5.2 GraphSAGE Specification

```
Layers: 2 message-passing layers
Aggregator: MEAN (computationally efficient, empirically strong)
  Alternative: LSTM aggregator tested if MEAN underperforms

Layer 1:
  Input:  node_features [28] + sampled neighbor features
  Output: node_embedding_L1 [128]
  Neighbors sampled: k=10 per node (training), k=5 (inference)

Layer 2:
  Input:  node_embedding_L1 [128] from Layer 1 neighbors
  Output: node_embedding_L2 [128]
  Neighbors sampled: k=10 per node (training), k=5 (inference)

Activation: ReLU
Normalization: L2 normalize output embeddings

Edge representation:
  Concatenate: [source_node_emb_L2, dest_node_emb_L2, edge_features]
               [128] + [128] + [26] = [282]
  Linear projection → corridor_edge_emb [128]

Final graph context vector:
  [sender_node_emb_L2, receiver_node_emb_L2, corridor_edge_emb]
  [128] + [128] + [128] = [384]
```

### 5.3 GraphSAGE Training

Loss: Binary cross-entropy on payment failure labels
Negative sampling ratio: 5:1 (temporary:permanent failure)
  — class imbalance expected; majority of rejections are temporary

Optimizer: Adam, lr=1e-3, weight_decay=1e-4
Scheduler: ReduceLROnPlateau, patience=5, factor=0.5
Batch size: 512 payment events per batch
Max epochs: 100 with early stopping (patience=10 on val AUC)

Hardware: GPU required (T4 minimum)
Estimated training time: 4-8 hours on T4 for full dataset

### 5.4 Inference — Neighborhood Sampling

At inference time (critical path):
- Only 2 hops of neighbors needed
- Pre-compute and cache L2 node embeddings in Redis after weekly rebuild
- Inference uses CACHED embeddings (Redis GET) — no real-time graph traversal
- Real-time graph traversal only for nodes added since last weekly rebuild

This is the key architectural decision that makes inference fast:
- Redis GET for corridor_embedding: ~1ms
- No GNN forward pass at inference time for known corridors
- GNN forward pass only for new/unseen corridors (~5% of volume)

---

## 6. TABTRANSFORMER ARCHITECTURE

### 6.1 Why TabTransformer

Standard MLPs for tabular data ignore feature interactions.
TabTransformer (Huang et al., 2020) applies self-attention over
categorical feature embeddings, allowing the model to learn
complex interactions between rejection codes, currency pairs,
and jurisdictions — the most informative feature group for
payment failure prediction.

### 6.2 TabTransformer Specification

```
Categorical features processed through transformer:
  rejection_code, amount_tier, currency_pair, sender_country,
  receiver_country, rejection_code_class, is_month_end, is_quarter_end

Per categorical feature:
  Embedding dimension: 32
  Total categorical embedding: [32 × 8 features] = [256]

Transformer:
  Layers: 4
  Heads: 8
  FFN dimension: 128
  Dropout: 0.1
  Activation: GELU

Transformer output: [256] → LayerNorm → [256]

Continuous features (amount_usd_log, time sin/cos, amount_percentile):
  Concatenated without transformation: [8]

TabTransformer output:
  Concatenate [transformer_output[256], continuous_features[8]]
  Linear projection → [88]
```

### 6.3 TabTransformer Training

Same training loop as GraphSAGE — both components trained jointly
in the combined model (Section 7).

Categorical embeddings: initialized randomly, learned end-to-end
Pre-training option: if labeled data is sparse, pre-train embeddings
on masked feature prediction (BERT-style) before fine-tuning.
This is an optional step — evaluate if AUC is below 0.80 after
standard training.

---

## 7. MODEL COMBINATION & OUTPUT HEAD

### 7.1 Combination

```
graph_context   = GraphSAGE output [384]
tabular_output  = TabTransformer output [88]

combined = Concatenate(graph_context, tabular_output) [472]
```

### 7.2 MLP Output Head

```
Layer 1: Linear(472 → 256) + ReLU + Dropout(0.2)
Layer 2: Linear(256 → 64)  + ReLU + Dropout(0.2)
Layer 3: Linear(64 → 1)    + Sigmoid

Output: failure_probability ∈ [0, 1]
```

### 7.3 Loss Function

Asymmetric binary cross-entropy:
  loss = -[α * y * log(p) + (1-α) * (1-y) * log(1-p)]

  α = 0.7 (weight on positive class = permanent failure)
  Rationale: false negatives (missing a permanent failure) cost
  more than false positives (unnecessary bridge offer that gets
  declined). α = 0.7 reflects this asymmetry conservatively.
  Calibrate α post-pilot using actual false negative cost data.

### 7.4 Operating Threshold

Default: 0.5
Tuned via: F2 score maximization on validation set
  (F2 = (1 + 4) * precision * recall / (4 * precision + recall))
  F2 weights recall twice as heavily as precision, consistent
  with false-negative-costly objective.

The operating threshold must be documented in the model card
alongside the precision/recall tradeoff curve at all thresholds.
Bank licensees configure their own threshold via ELO admin.
Bridgepoint recommends F2-optimal as the default.

---

## 8. CORRIDOR EMBEDDING PIPELINE

This section resolves the open flag from Architecture Spec
sign-off (ARIA signed with flag: corridor embedding spec missing).

### 8.1 Definition

corridor_embedding = the [128]-dimensional vector representation
of the (BIC_sender, BIC_receiver, currency_pair) corridor,
derived from GraphSAGE edge representation after weekly rebuild.

This is the field `corridor_embedding: float[]` in the
ClassifyRequest API contract (Architecture Spec S4.2).

### 8.2 Generation

After each weekly graph rebuild:

```
For each active corridor (BIC_sender, BIC_receiver, currency_pair):
  1. Run GraphSAGE forward pass on the full graph
  2. Extract corridor_edge_emb [128] for this edge
  3. Write to Redis:
       Key: "corridor:emb:{BIC_sender}_{BIC_receiver}_{currency}"
       Type: Redis HASH (stores float[] as binary blob)
       TTL: 8 days (weekly rebuild + 1 day buffer)
       Value: 128-float vector, packed as float32 binary
```

### 8.3 Cold Start (New Corridor)

If corridor_embedding key not found in Redis at inference time:
  1. Compute mean embedding across all corridors with same currency_pair
     Key: "corridor:emb:mean:{currency_pair}"
     Updated as part of weekly rebuild
  2. Use currency-pair mean as the corridor embedding
  3. Log: classifier_request.corridor_cold_start = true
  4. This triggers Tier 0 bootstrap for buffer (Architecture Spec S11.4)

If currency_pair mean also not available (truly novel currency pair):
  Use global mean embedding across all corridors
  Key: "corridor:emb:mean:global"

### 8.4 Dimensionality

Fixed at 128 floats. Not configurable without model retraining.
This is a model artifact parameter — version-locked.
Stored in model metadata alongside the model weights.

### 8.5 Embedding Drift Monitoring

Weekly: compute cosine similarity between new embeddings and
previous week's embeddings for each corridor.
Alert if mean cosine similarity < 0.85 across all corridors —
indicates significant graph structure change that may affect
inference quality. ARIA reviews alert before next weekly deploy.

---

## 9. TRAINING DATA SPECIFICATION

### 9.1 Required Dataset Schema

Each training example is one pacs.002 RJCT event with outcome label:

```
TrainingRecord {
  uetr                    : string    // For deduplication only
  rejection_code          : string
  bic_sender              : string    // 8-character BIC
  bic_receiver            : string
  amount_usd              : float
  currency_pair           : string
  timestamp_utc           : int64
  hour_of_day             : int       // 0-23
  day_of_week             : int       // 0-6
  is_month_end            : bool
  is_quarter_end          : bool

  // Label
  outcome                 : int       // 0 = settled (temporary failure)
                                      // 1 = permanent failure (no settlement)

  // Label definition
  // outcome = 1 if no settlement signal received within:
  //   max(corridor_P95 * 1.5, Class_C_buffer = 21 days)
  // outcome = 0 if any settlement signal received before that window
}
```

### 9.2 Label Assignment Rules

Labels are assigned post-hoc from historical data:
  outcome = 1: no settlement signal received within 21 calendar days
  outcome = 0: settlement signal received within 21 calendar days

21 days is used as the universal label window (Class C maximum) to
create a consistent, unambiguous label across all rejection classes.

**Class imbalance expectation:**
  Based on SWIFT STP 3.5% failure rate midpoint:
  - Most pacs.002 RJCT events are temporary delays, not permanent failures
  - Expected class ratio: ~70-85% temporary (outcome=0), ~15-30% permanent (outcome=1)
  - Exact ratio depends on dataset source; must be measured and reported

### 9.3 Minimum Dataset Size

Target: 500,000 labeled examples for initial training
Minimum viable: 100,000 labeled examples

At <100,000 examples: AUC target of 0.85 is unlikely achievable.
ARIA must report actual training set size alongside AUC.

**Data sources (in priority order):**
1. Partner bank historical pacs.002 data (pilot agreement required)
2. SWIFT published synthetic payment failure datasets
3. Synthetic generation via corridor rejection rate distributions
   (label quality is degraded — flag if used as primary source)

### 9.4 Train / Validation / Test Split

Split strategy: TIME-BASED, not random
  - Train:       Oldest 70% of data by timestamp
  - Validation:  Next 15% by timestamp
  - Test (OOT):  Most recent 15% by timestamp

Random splits are NOT acceptable for time-series financial data.
Random splits create look-ahead bias — model can learn patterns
from future events that appear in training set.

Out-of-time (OOT) test set is the primary evaluation split.
The roadmap requires OOT backtesting. This split enforces it.

---

## 10. TRAINING PIPELINE

### 10.1 Pipeline Stages

```
Stage 1: Data Validation
  - Schema check: all required fields present
  - Label check: outcome distribution logged
  - Deduplication: remove duplicate UETRs
  - Outlier detection: flag extreme amounts (>10M USD), log don't remove

Stage 2: Graph Construction
  - Build V and E from training data BIC pairs
  - Compute node features (requires 90-day history window)
  - Compute edge features per corridor
  - Compute centrality metrics (betweenness, PageRank)
  - Persist graph structure as PyG Data object

Stage 3: Feature Engineering
  - Fit normalization parameters on training set ONLY
  - Compute all tabular features
  - Encode categorical features
  - Persist normalization artifact

Stage 4: Joint Training (GraphSAGE + TabTransformer + MLP head)
  - Initialize all weights randomly (or from pretrained embeddings)
  - Train for max 100 epochs with early stopping
  - Log: train_AUC, val_AUC, train_loss, val_loss every epoch
  - Save checkpoint at best val_AUC

Stage 5: Threshold Calibration
  - Compute F2-optimal threshold on validation set
  - Document precision, recall, F1, F2 at operating threshold
  - Document full precision-recall curve

Stage 6: SHAP Computation
  - Compute SHAP values on 1,000-example sample from test set
  - Verify top 20 features are interpretable (no data leakage)
  - Verify SHAP values sum to predicted probability (sanity check)

Stage 7: Validation (OOT test set)
  - AUC on OOT test set (primary metric)
  - Calibration curve
  - Precision/recall at operating threshold
  - Train/val/test AUC gap (must be ≤ 3%)
  - All results logged to model registry

Stage 8: Corridor Embedding Generation
  - Run forward pass on full graph post-training
  - Write all corridor embeddings to Redis (staging)
  - Validate: sample 100 corridor embeddings, verify dimensionality

Stage 9: Integration Test (staging)
  - Feed 100 test pacs.002 events through full pipeline
  - Verify inference latency p50 <30ms, p99 <50ms
  - Verify SHAP output format matches Architecture Spec S4.2
  - Verify corridor_embedding field populated correctly
```

### 10.2 MLflow Tracking

Every training run logged to MLflow:
  - Parameters: all hyperparameters
  - Metrics: AUC (train/val/test), calibration error, latency
  - Artifacts: model weights, normalization params, SHAP sample
  - Tags: model_version, training_data_hash, git_commit

Model registry: Bridgepoint MLflow instance (internal)
Production model: tagged "production" in registry after Audit Gate 1.1

---

## 11. VALIDATION REQUIREMENTS (AUDIT GATE 1.1)

The roadmap specifies 7 required validation outputs.
All 7 must be produced and documented. Targets are targets, not
guarantees — honest actual values are what matters.

### 11.1 AUC on Held-Out OOT Test Set

**Target:** AUC ≥ 0.85
**Honest ceiling (ARIA estimate):** AUC 0.82-0.88
  - Lower bound: GNN adds structural features XGBoost couldn't use;
    even a modest improvement over 0.739 is expected
  - Upper bound: 0.88 is aggressive; payment failure prediction is
    inherently noisy (some rejections have genuinely random causes)
  - Target of 0.85 is achievable but not guaranteed
  - If AUC < 0.80: escalate to full agent review before Phase 2
  - If AUC 0.80-0.84: proceed but document gap from target
  - If AUC ≥ 0.85: target met, document and proceed

### 11.2 Precision/Recall Curves

Produce full precision-recall curve across all threshold values.
Report at operating threshold (F2-optimal):
  - Precision (document actual value)
  - Recall (document actual value)
  - F1, F2 (document actual values)

### 11.3 Calibration Curve

Produce calibration plot: predicted_probability vs. actual_failure_rate
  - Bin predicted probabilities into 10 equal-width buckets
  - Plot mean predicted probability vs. fraction of actual failures per bin
  - Expected Calibration Error (ECE) < 0.05
  - If ECE > 0.05: apply Platt scaling or isotonic regression
    calibration layer on top of sigmoid output

Calibration is mandatory for pricing use. The PD model (C2) uses
C1's failure_probability as a conditioning signal. Miscalibrated
probabilities flow directly into wrong loan pricing.

### 11.4 SHAP Feature Importance

Top 20 features by mean |SHAP value| must be:
  1. Documented (feature name + mean contribution)
  2. Interpretable (ARIA must explain each top feature in plain terms)
  3. Free of data leakage (no feature that encodes the outcome label)

Expected top features (pre-training hypothesis):
  - rejection_code (most predictive single feature)
  - corridor_rejection_rate_90d (BIC-pair history)
  - amount_usd_log (large amounts have different failure dynamics)
  - hour_sin/cos (time-of-day settlement patterns)
  - sender_node betweenness centrality (well-connected banks settle faster)

If corridor_embedding contributions are near-zero, this indicates
the GNN is not contributing meaningful signal — escalate.

### 11.5 False Positive Rate at Operating Threshold

Document:
  - False positive rate = FP / (FP + TN)
  - Capital efficiency impact estimate:
    false_positive_cost = count(FP) * mean_loan_amount * fee_rate
    (revenue from false positives where borrower accepts the offer)
  - False positives generate revenue if the borrower accepts
    (bridge loan funded, original payment eventually settles, repaid)
  - False positive cost = only opportunity cost of capital deployed

### 11.6 Out-of-Time Backtesting

Mandatory. The OOT test set (most recent 15% of data by time)
serves as the backtest. Additionally:
  - If training data spans >12 months: run rolling-window backtest
    Train on months 1-6, test on month 7; train on 1-7, test on 8; etc.
  - Plot AUC over time to detect model decay
  - If AUC declines >3% over the backtest window, flag for ARIA review

### 11.7 Train/Validation/Test AUC Gap

Roadmap requirement: AUC gap ≤ 3% across all three splits.
  - train_AUC - val_AUC ≤ 0.03
  - val_AUC - test_AUC ≤ 0.03

If gap > 0.03: overfitting. Apply additional regularization:
  - Increase dropout (0.2 → 0.3)
  - Add L2 weight decay
  - Reduce model depth
  - Increase training data (most effective fix)

### 11.8 Negation / Edge Case Testing

Not in the roadmap for C1 but added by ARIA based on known failure modes:

Test suite: 500 manually constructed edge cases:
  - Payments from new BICs (cold start corridors)
  - Extreme amounts (>$10M)
  - Sanctions-adjacent rejection codes (should NOT be classified as
    temporary — they're hard blocks downstream, but C1 should predict
    high failure_probability for them)
  - Month-end / quarter-end payments
  - Weekend / holiday payments

All 500 cases must produce interpretable SHAP values.
Any case where top SHAP feature is a leakage feature = model defect.

---

## 12. SHAP EXPLAINABILITY SPECIFICATION

### 12.1 SHAP Method

Method: TreeExplainer is NOT applicable (deep learning model).
Use: GradientExplainer (backpropagation-based SHAP for PyTorch)
  - Faster than KernelExplainer
  - Exact for gradient-based models
  - Works with the combined GNN + TabTransformer architecture

Background dataset: 500 randomly sampled training examples
  (stored as part of model artifact — must be reproducible)

### 12.2 Production SHAP Computation

At inference time: compute SHAP values for the 20 most important
features identified at training time (not all features).
  - Precompute feature importance ranking from training SHAP
  - At inference: GradientExplainer on top 20 features only
  - Latency target for SHAP: <5ms additional on GPU
  - If SHAP adds >5ms: reduce top-N to 10 features

SHAP values persisted in DecisionLogEntry (Architecture Spec S4.8):
  - Format: List[ShapValue{feature_name, contribution}]
  - Top 20 features by |contribution|

### 12.3 EU AI Act Art.13 Compliance

SHAP values in the decision log satisfy Art.13 transparency
requirements. Each automated lending decision is:
  - Explainable: top 20 features and their direction of contribution
  - Reproducible: model_version + UETR + SHAP values = full audit trail
  - Human-reviewable: ELO operator can see why C1 flagged a payment

---

## 13. MODEL VERSIONING & REGISTRY

### 13.1 Version Format

semantic versioning: C1_v{MAJOR}.{MINOR}.{PATCH}
  - MAJOR: architecture change (new model family)
  - MINOR: retraining with new data, same architecture
  - PATCH: threshold or calibration update, no weight changes

First production model: C1_v1.0.0

### 13.2 Model Artifact Contents

Each model version is a self-contained artifact:
```
C1_v1.0.0/
  model_weights.pt         # GraphSAGE + TabTransformer + MLP weights
  normalization_params.pkl # Fit on training data
  categorical_encoders.pkl # Rejection code, currency pair mappings
  shap_background.pkl      # 500-example background dataset
  feature_importance.json  # Top 20 features by mean |SHAP|
  corridor_embeddings/     # All corridor embeddings at training time
                           # (Redis is primary; this is backup)
  model_card.md            # Performance metrics, training data info,
                           # known limitations, operating threshold
  graph_metadata.json      # Node count, edge count, graph build date
```

### 13.3 Hot-Swap Protocol

When a new model version is deployed:
  1. Load new model weights on 1 GPU inference node (canary)
  2. Route 5% of traffic to canary for 1 hour
  3. Monitor: AUC (proxy via label feedback), latency, error rate
  4. If canary clean: roll out to all nodes
  5. If canary fails: rollback to previous version (30-second rollback)
  6. Previous version retained in registry for 90 days

---

## 14. KNOWN LIMITATIONS & HONEST CEILING

ARIA documents these before any number is produced. These are
structural limitations, not implementation bugs.

1. **Graph topology assumption:** GraphSAGE assumes the BIC-pair
   payment network is relatively stable week-to-week. Bank mergers,
   new correspondent agreements, or sanctions-driven routing changes
   can significantly alter the graph structure. The weekly rebuild
   catches most changes, but a sudden routing shift mid-week may
   degrade performance until the next rebuild.

2. **Label quality:** Labels are assigned based on settlement signal
   presence/absence within 21 days. If a settlement signal was
   transmitted but not received (Kafka gap, parsing error), a
   temporary failure gets labeled as permanent. Label noise is
   expected to be ~1-3% of training data. This sets a practical
   AUC ceiling: with ~2% label noise, AUC above ~0.92 is likely
   due to overfitting, not genuine predictive power.

3. **Rare rejection code coverage:** Some SWIFT rejection codes appear
   <100 times in any realistic training dataset. The learned embedding
   for rare codes will be poorly calibrated. The rejection_code_class
   (A/B/C/BLOCK) feature provides a backstop for rare codes, but
   individual code embeddings for rare codes are unreliable.

4. **Cold start corridors:** New corridors use currency-pair mean
   embeddings as a proxy. Performance on new corridors is expected
   to be lower than on established corridors. This is unavoidable
   and is acceptable — the corridor bootstrap protocol (S11.4)
   manages the bridge risk side of this limitation.

5. **AUC ceiling estimate:** ARIA's honest pre-training estimate
   is AUC 0.82-0.88. The target of 0.85 is achievable but not
   certain. Payment failure prediction is inherently noisy — some
   failures are effectively random events (network partitions, edge
   cases in correspondent bank systems) with no predictive signal
   in any observable feature. A hard ceiling likely exists around
   AUC 0.88-0.90 for this problem domain.

---

## 15. AUDIT GATE 1.1 CHECKLIST

Gate passes when ALL items are checked. ARIA signs off.

**Model Performance:**
  [ ] AUC on OOT test set: reported (target ≥ 0.85, honest actual)
  [ ] Precision/recall curve produced and documented
  [ ] Operating threshold set and documented (F2-optimal)
  [ ] Calibration curve produced, ECE < 0.05 (or calibration applied)
  [ ] False positive rate at operating threshold documented
  [ ] Capital efficiency impact of false positives estimated

**Overfitting:**
  [ ] Train AUC documented
  [ ] Validation AUC documented
  [ ] OOT test AUC documented
  [ ] All gaps ≤ 3% (train-val, val-test)

**Backtesting:**
  [ ] Out-of-time backtest completed (most recent 15% of data)
  [ ] Rolling-window backtest completed (if data spans >12 months)
  [ ] AUC decay over time plotted and reviewed

**Explainability:**
  [ ] Top 20 SHAP features documented
  [ ] Each top feature explained in plain language (ARIA sign-off)
  [ ] No data leakage features in top 20
  [ ] SHAP format matches Architecture Spec S4.2 schema
  [ ] SHAP computation adds <5ms to inference latency

**Infrastructure:**
  [ ] Inference p50 <30ms on GPU (T4 minimum) at batch size 32
  [ ] Inference p99 <50ms on GPU at batch size 32
  [ ] Corridor embeddings generated and loaded into Redis (staging)
  [ ] Cold start behavior validated (new corridor uses mean embedding)
  [ ] Embedding drift monitoring active

**Model Artifact:**
  [ ] All artifact files present and complete
  [ ] model_card.md written with all required fields
  [ ] Model registered in MLflow as C1_v1.0.0
  [ ] Model tagged "staging" (not "production" until gate passes)
  [ ] Hot-swap protocol tested (canary rollout + rollback)

**Edge Cases:**
  [ ] 500 edge case test suite run, results documented
  [ ] Cold start corridors tested
  [ ] Extreme amount handling validated
  [ ] Month-end / quarter-end behavior validated

**SR 11-7 Compliance:**
  [ ] Model card includes: purpose, methodology, training data,
      known limitations, failure modes, performance benchmarks
  [ ] Training data provenance documented (source, date range, size)
  [ ] Independent validation pathway documented

**Gate Outcome:**
  [ ] ARIA signs off: AUC honest ceiling documented + gate passed
  [ ] NOVA confirms: corridor embedding API contract satisfied
  [ ] FORGE confirms: latency targets met on target hardware

---

*Internal document. Stealth mode active. Nothing external.*
*Last updated: March 4, 2026*
*Status: ACTIVE BUILD — Phase 1, Component 1*
