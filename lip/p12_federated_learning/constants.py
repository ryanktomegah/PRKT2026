"""
P4 Federated Learning — Constants and Hyperparameters

QUANT + REX sign-off required before production use for:
- DP_EPSILON (privacy budget per round)
- DP_NOISE_MULTIPLIER (Gaussian noise calibration)
- FEDPROX_MU_VALUES (proximal coefficient range for production)

Patent Reference: Patent Family 4 — Federated Learning Across Bank Consortium (P12)
Architecture Doc: docs/models/federated-learning-architecture.md
"""

from decimal import Decimal

# ===========================================================================
# Differential Privacy Parameters (Abadi et al. 2016, DP-SGD)
# ===========================================================================

# Privacy budget per round (lower = stronger privacy)
# QUANT + REX must sign off on any change to this value
# Reference: Anil et al. 2022 recommend ε≤1.0 for sensitive domains
DP_EPSILON: Decimal = Decimal("1.0")

# Failure probability bound per round (one-in-100,000 per round)
DP_DELTA: Decimal = Decimal("1e-5")

# Gradient clipping norm (L2 norm of per-sample gradients)
DP_CLIP_NORM: float = 1.0

# Gaussian noise multiplier calibrated to achieve (ε=1.0, δ=1e-5)
# σ = noise_multiplier * clip_norm
DP_NOISE_MULTIPLIER: float = 1.1

# ===========================================================================
# FedProx Proximal Coefficient (Li et al. 2020)
# ===========================================================================

# Minimum proximal coefficient (near-FedAvg)
FEDPROX_MU_MIN: float = 0.001

# Maximum proximal coefficient (strong regularization)
FEDPROX_MU_MAX: float = 0.1

# μ sweep values for experiments and QUANT sign-off
# μ=0 corresponds to vanilla FedAvg (baseline comparison)
FEDPROX_MU_VALUES: list[float] = [0.0, 0.001, 0.01, 0.1]

# ===========================================================================
# Training Hyperparameters
# ===========================================================================

# Local training epochs per FL round
LOCAL_EPOCHS: int = 5

# Total number of federated learning rounds
NUM_ROUNDS: int = 50

# Number of random seeds for reproducibility in experiments
NUM_SEEDS: int = 3

# Learning rate for local training
LEARNING_RATE: float = 0.001

# ===========================================================================
# Model Architecture Dimensions
# ===========================================================================

# GraphSAGE layer dimensions (from c1_failure_classifier/graphsage_torch.py)
GRAPHSAGE_INPUT_DIM: int = 8
GRAPHSAGE_HIDDEN_DIM: int = 256
GRAPHSAGE_OUTPUT_DIM: int = 384

# TabTransformer dimensions (from c1_failure_classifier/tabtransformer_torch.py)
TABTRANSFORMER_INPUT_DIM: int = 88
TABTRANSFORMER_NUM_LAYERS: int = 4
TABTRANSFORMER_NUM_HEADS: int = 8
TABTRANSFORMER_EMBED_DIM: int = 32
TABTRANSFORMER_MODEL_DIM: int = TABTRANSFORMER_NUM_HEADS * TABTRANSFORMER_EMBED_DIM  # 256

# Combined dimensions (from c1_failure_classifier/model_torch.py)
COMBINED_INPUT_DIM: int = GRAPHSAGE_OUTPUT_DIM + TABTRANSFORMER_INPUT_DIM  # 472

# ===========================================================================
# Communication Budget Constraints
# ===========================================================================

# Per-round communication budget in bytes per bank
# Based on architecture doc estimate: ~10 MB per round per bank
COMM_BUDGET_BYTES_PER_ROUND: int = 10 * 1024 * 1024  # 10 MB

# ===========================================================================
# DP Cumulative Budget Targets
# ===========================================================================

# Maximum cumulative ε across all rounds for production use
# Via Rényi DP accounting (Mironov 2017)
DP_CUMULATIVE_EPSILON_MAX: Decimal = Decimal("3.0")

# ===========================================================================
# Synthetic Bank Data Configuration
# ===========================================================================

# Number of synthetic banks for simulation
NUM_SYNTHETIC_BANKS: int = 3

# Synthetic bank configurations (non-IID distributions)
# Each bank has different volume, failure rate, and corridors
SYNTHETIC_BANK_CONFIGS: list[dict] = [
    {
        "bank_id": "EU_high_volume",
        "n_samples": 500_000,
        "failure_rate": 0.02,
        "corridors": ["EUR-GBP", "EUR-USD"],
        "seed": 42,
    },
    {
        "bank_id": "APAC_low_volume",
        "n_samples": 80_000,
        "failure_rate": 0.05,
        "corridors": ["SGD-INR", "HKD-CNY"],
        "seed": 123,
    },
    {
        "bank_id": "EM_niche",
        "n_samples": 30_000,
        "failure_rate": 0.12,
        "corridors": ["BRL-USD", "MXN-USD"],
        "seed": 456,
    },
]

# ===========================================================================
# LightGBM Ensemble Configuration
# ===========================================================================

# Ensemble blending weights (PyTorch : LightGBM)
ENSEMBLE_PYTORCH_WEIGHT: float = 0.5
ENSEMBLE_LGBM_WEIGHT: float = 0.5

# LightGBM hyperparameters for local training
LGBM_NUM_LEAVES: int = 100
LGBM_LEARNING_RATE: float = 0.05
LGBM_MAX_DEPTH: int = 6
LGBM_FORCE_COL_WISE: bool = True

# ===========================================================================
# Flower Configuration
# ===========================================================================

# Minimum number of clients required for aggregation
MIN_FIT_CLIENTS: int = 2

# Fraction of clients to sample per round (if more than min available)
SAMPLE_FRACTION: float = 1.0

# Client timeout for each round (seconds)
CLIENT_TIMEOUT: int = 300
