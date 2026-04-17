"""
P4 Federated Learning Module

Phase 3 implementation enabling bank consortium members to jointly improve
the C1 failure classifier without sharing raw transaction data.

Patent Reference: Patent Family 4 — Federated Learning Across Bank Consortium (P12)
Architecture Doc: docs/models/federated-learning-architecture.md

Key Components:
- models.py: LocalModel, SharedModel, FederatedModel (model splitting for FL)
- client.py: LIPFlowerClient (Flower client implementation)
- dp_accountant.py: RenyiDPAccountant (DP budget tracking)
- local_ensemble.py: LocalEnsemble (PyTorch + LightGBM coordination)
- synthetic_banks.py: Synthetic bank data generation
- simulation.py: Federated learning simulation runner with μ sweep
- constants.py: DP and FL hyperparameters

QUANT + REX sign-off required before production use for:
- DP_EPSILON (privacy budget)
- DP_NOISE_MULTIPLIER (noise calibration)
- FEDPROX_MU_VALUES (proximal coefficient range)
"""

from lip.p12_federated_learning.constants import (
    # Flower Configuration
    CLIENT_TIMEOUT,
    # Model Dimensions
    COMBINED_INPUT_DIM,
    # Communication Budget
    COMM_BUDGET_BYTES_PER_ROUND,
    # DP Parameters
    DP_CLIP_NORM,
    DP_CUMULATIVE_EPSILON_MAX,
    DP_DELTA,
    DP_EPSILON,
    DP_NOISE_MULTIPLIER,
    # LightGBM Ensemble
    ENSEMBLE_LGBM_WEIGHT,
    ENSEMBLE_PYTORCH_WEIGHT,
    # FedProx Parameters
    FEDPROX_MU_MAX,
    FEDPROX_MU_MIN,
    FEDPROX_MU_VALUES,
    GRAPHSAGE_HIDDEN_DIM,
    GRAPHSAGE_INPUT_DIM,
    GRAPHSAGE_OUTPUT_DIM,
    # Training Hyperparameters
    LEARNING_RATE,
    LGBM_FORCE_COL_WISE,
    LGBM_LEARNING_RATE,
    LGBM_MAX_DEPTH,
    LGBM_NUM_LEAVES,
    LOCAL_EPOCHS,
    MIN_FIT_CLIENTS,
    NUM_ROUNDS,
    NUM_SEEDS,
    # Synthetic Bank Data
    NUM_SYNTHETIC_BANKS,
    SAMPLE_FRACTION,
    SYNTHETIC_BANK_CONFIGS,
    TABTRANSFORMER_EMBED_DIM,
    TABTRANSFORMER_INPUT_DIM,
    TABTRANSFORMER_MODEL_DIM,
    TABTRANSFORMER_NUM_HEADS,
    TABTRANSFORMER_NUM_LAYERS,
)

__all__ = [
    # DP Parameters
    "DP_CLIP_NORM",
    "DP_DELTA",
    "DP_EPSILON",
    "DP_NOISE_MULTIPLIER",
    "DP_CUMULATIVE_EPSILON_MAX",
    # FedProx Parameters
    "FEDPROX_MU_MAX",
    "FEDPROX_MU_MIN",
    "FEDPROX_MU_VALUES",
    # Training Hyperparameters
    "LEARNING_RATE",
    "LOCAL_EPOCHS",
    "NUM_ROUNDS",
    "NUM_SEEDS",
    # Model Dimensions
    "COMBINED_INPUT_DIM",
    "GRAPHSAGE_HIDDEN_DIM",
    "GRAPHSAGE_INPUT_DIM",
    "GRAPHSAGE_OUTPUT_DIM",
    "TABTRANSFORMER_EMBED_DIM",
    "TABTRANSFORMER_INPUT_DIM",
    "TABTRANSFORMER_MODEL_DIM",
    "TABTRANSFORMER_NUM_HEADS",
    "TABTRANSFORMER_NUM_LAYERS",
    # Communication Budget
    "COMM_BUDGET_BYTES_PER_ROUND",
    # Synthetic Bank Data
    "NUM_SYNTHETIC_BANKS",
    "SYNTHETIC_BANK_CONFIGS",
    # LightGBM Ensemble
    "ENSEMBLE_LGBM_WEIGHT",
    "ENSEMBLE_PYTORCH_WEIGHT",
    "LGBM_FORCE_COL_WISE",
    "LGBM_LEARNING_RATE",
    "LGBM_MAX_DEPTH",
    "LGBM_NUM_LEAVES",
    # Flower Configuration
    "CLIENT_TIMEOUT",
    "MIN_FIT_CLIENTS",
    "SAMPLE_FRACTION",
]
