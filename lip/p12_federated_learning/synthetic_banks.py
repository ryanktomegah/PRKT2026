"""
P4 Federated Learning — Synthetic Bank Data Generation

Generates synthetic payment failure data for federated learning simulation.

Each synthetic bank has:
- Different data volume (high volume vs low volume vs niche)
- Different failure rates (representing non-IID distributions)
- Different payment corridors (representing geographic/jurisdictional differences)
- Random seed for reproducibility

This non-IID data generation validates that FedProx outperforms FedAvg,
as FedProx is designed to handle heterogeneous data distributions.

Reference:
- Li et al. 2020, "Federated Optimization in Heterogeneous Networks," ICLR
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from lip.p12_federated_learning.constants import SYNTHETIC_BANK_CONFIGS

# =============================================================================
# Data Classes
# =============================================================================


@dataclasses.dataclass
class SyntheticBank:
    """
    Synthetic bank configuration for federated learning simulation.

    Attributes
    ----------
    bank_id:
        Unique identifier for the bank (e.g., "EU_high_volume").
    n_samples:
        Number of synthetic samples to generate for this bank.
    failure_rate:
        Base failure probability for this bank's data distribution.
        Different banks have different rates → non-IID data.
    corridors:
        List of payment corridors this bank operates in.
    seed:
        Random seed for reproducibility.
    """

    bank_id: str
    n_samples: int
    failure_rate: float
    corridors: list[str]
    seed: int

    def __post_init__(self) -> None:
        """Validate synthetic bank configuration."""
        if self.n_samples <= 0:
            raise ValueError(f"n_samples must be positive, got {self.n_samples}")
        if not (0.0 <= self.failure_rate <= 1.0):
            raise ValueError(
                f"failure_rate must be in [0, 1], got {self.failure_rate}"
            )
        if not self.corridors:
            raise ValueError(f"corridors must be non-empty, got {self.corridors}")


@dataclasses.dataclass
class SyntheticBankData:
    """
    Synthetic bank data for training/testing.

    Attributes
    ----------
    bank_id:
        Bank identifier.
    node_feat:
        Node features (BIC embeddings), shape (n_samples, 8).
    tab_feat:
        Tabular features, shape (n_samples, 88).
    neighbor_feats:
        Neighbor features for GraphSAGE, shape (n_samples, k, 8).
        Can be None for empty-neighbor training mode.
    labels:
        Binary labels (1 = failure, 0 = success), shape (n_samples,).
    """

    bank_id: str
    node_feat: np.ndarray
    tab_feat: np.ndarray
    neighbor_feats: np.ndarray | None
    labels: np.ndarray


# =============================================================================
# Synthetic Data Generation Functions
# =============================================================================


def generate_synthetic_banks(
    configs: list[dict] | None = None,
) -> list[SyntheticBank]:
    """
    Generate synthetic bank configurations.

    Parameters
    ----------
    configs:
        List of bank configuration dicts. If None, uses default
        SYNTHETIC_BANK_CONFIGS from constants.

    Returns
    -------
    list[SyntheticBank]
        List of synthetic bank configurations.
    """
    if configs is None:
        configs = SYNTHETIC_BANK_CONFIGS

    banks = [
        SyntheticBank(
            bank_id=config["bank_id"],
            n_samples=config["n_samples"],
            failure_rate=config["failure_rate"],
            corridors=config["corridors"],
            seed=config["seed"],
        )
        for config in configs
    ]

    total_samples = sum(b.n_samples for b in banks)
    print(
        f"Generated {len(banks)} synthetic banks with "
        f"{total_samples:,} total samples"
    )

    for bank in banks:
        print(
            f"  {bank.bank_id}: {bank.n_samples:,} samples, "
            f"failure_rate={bank.failure_rate:.3f}, "
            f"corridors={bank.corridors}"
        )

    return banks


def generate_synthetic_bank_data(
    bank: SyntheticBank,
    k_neighbors: int = 5,
) -> SyntheticBankData:
    """
    Generate synthetic training data for a single bank.

    Generates synthetic node features (8-dim BIC embeddings), tabular features
    (88-dim), neighbor features for GraphSAGE, and binary labels based on the
    bank's configured failure rate.

    Data generation follows these principles:
    - Node features: Random BIC embeddings (simulating counterparty identity)
    - Tabular features: Mix of categorical and continuous features
    - Neighbor features: k nearest neighbors in counterparty graph
    - Labels: Bernoulli with bank's failure_rate as success probability

    Parameters
    ----------
    bank:
        SyntheticBank configuration.
    k_neighbors:
        Number of neighbors to generate for GraphSAGE (default 5).
        Set to 0 for empty-neighbor mode.

    Returns
    -------
    SyntheticBankData
        Generated synthetic data.
    """
    rng = np.random.default_rng(bank.seed)
    n_samples = bank.n_samples

    # === Node Features (8-dim BIC embeddings) ===
    # Simulate BIC embedding space: different regions have different patterns
    # We use the bank_id seed to ensure reproducibility
    node_feat = rng.normal(size=(n_samples, 8), scale=0.5)

    # Normalize node features to unit sphere
    node_feat = node_feat / np.linalg.norm(node_feat, axis=1, keepdims=True)

    # === Tabular Features (88-dim) ===
    # First 8 dims are node features (consistent with existing code)
    # Remaining 80 dims: mix of categorical (one-hot) and continuous features
    tab_feat_remaining = rng.random(size=(n_samples, 80))
    tab_feat = np.concatenate([node_feat, tab_feat_remaining], axis=1)

    # === Neighbor Features (k x 8-dim) ===
    if k_neighbors > 0:
        # Generate k random neighbors for each sample
        # In real data, these would be actual counterparty neighbors
        neighbor_feats = rng.normal(
            size=(n_samples, k_neighbors, 8),
            scale=0.3,
        )
        # Normalize each neighbor
        neighbor_feats = neighbor_feats / np.linalg.norm(
            neighbor_feats, axis=2, keepdims=True
        )
    else:
        neighbor_feats = None  # Empty-neighbor mode

    # === Labels (Bernoulli with bank's failure_rate) ===
    labels = rng.random(n_samples) < bank.failure_rate
    labels = labels.astype(np.float32)

    # NOTE: Non-IID property is achieved via SYNTHETIC_BANK_CONFIGS
    # which define different failure_rates per bank. No corridor-specific
    # bias is applied here to ensure the configured failure_rate is respected.

    return SyntheticBankData(
        bank_id=bank.bank_id,
        node_feat=node_feat,
        tab_feat=tab_feat,
        neighbor_feats=neighbor_feats,
        labels=labels,
    )


# =============================================================================
# PyTorch Dataset and DataLoader
# =============================================================================


class SyntheticBankDataset(Dataset):
    """
    PyTorch Dataset for synthetic bank data.

    Converts SyntheticBankData to PyTorch tensors for training.
    """

    def __init__(
        self,
        bank_data: SyntheticBankData,
        transform: Any | None = None,
    ):
        self.bank_data = bank_data
        self.transform = transform

    def __len__(self) -> int:
        return len(self.bank_data.labels)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, ...]:
        """
        Get a single sample.

        Returns
        -------
        tuple
            (node_feat, tab_feat, neighbor_feats, label)
        """
        node_feat = torch.tensor(
            self.bank_data.node_feat[idx],
            dtype=torch.float32,
        )
        tab_feat = torch.tensor(
            self.bank_data.tab_feat[idx],
            dtype=torch.float32,
        )
        label = torch.tensor(
            self.bank_data.labels[idx],
            dtype=torch.float32,
        )

        if self.bank_data.neighbor_feats is not None:
            neighbor_feats = torch.tensor(
                self.bank_data.neighbor_feats[idx],
                dtype=torch.float32,
            )
        else:
            neighbor_feats = None

        if self.transform is not None:
            node_feat, tab_feat, neighbor_feats, label = self.transform(
                node_feat, tab_feat, neighbor_feats, label
            )

        return node_feat, tab_feat, neighbor_feats, label


def create_dataloader(
    bank_data: SyntheticBankData,
    batch_size: int = 256,
    shuffle: bool = True,
    num_workers: int = 0,
) -> DataLoader:
    """
    Create a DataLoader for synthetic bank data.

    Parameters
    ----------
    bank_data:
        SyntheticBankData.
    batch_size:
        Batch size (default 256).
    shuffle:
        Whether to shuffle data (default True).
    num_workers:
        Number of workers for data loading (default 0 for simplicity).

    Returns
    -------
    DataLoader
        PyTorch DataLoader.
    """
    dataset = SyntheticBankDataset(bank_data)

    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
    )


# =============================================================================
# Utility Functions
# =============================================================================


def get_bank_distribution_stats(bank_data: SyntheticBankData) -> dict[str, Any]:
    """
    Get statistics about a bank's data distribution.

    Parameters
    ----------
    bank_data:
        SyntheticBankData.

    Returns
    -------
    dict
        Statistics including failure rate, feature means/stds, etc.
    """
    labels = bank_data.labels
    node_feat = bank_data.node_feat
    tab_feat = bank_data.tab_feat

    stats = {
        "bank_id": bank_data.bank_id,
        "n_samples": len(labels),
        "failure_rate": float(labels.mean()),
        "node_feat_mean": node_feat.mean(axis=0).tolist(),
        "node_feat_std": node_feat.std(axis=0).tolist(),
        "tab_feat_mean": tab_feat.mean(axis=0).tolist(),
        "tab_feat_std": tab_feat.std(axis=0).tolist(),
    }

    return stats


def print_distribution_comparison(banks_data: list[SyntheticBankData]) -> None:
    """
    Print comparison of data distributions across banks.

    Useful for verifying non-IID property (banks should have different
    feature distributions and failure rates).

    Parameters
    ----------
    banks_data:
        List of SyntheticBankData for each bank.
    """
    print("\n" + "=" * 60)
    print("BANK DISTRIBUTION COMPARISON")
    print("=" * 60)

    for bank_data in banks_data:
        stats = get_bank_distribution_stats(bank_data)

        print(f"\n{stats['bank_id']}:")
        print(f"  Samples: {stats['n_samples']:,}")
        print(f"  Failure Rate: {stats['failure_rate']:.3f}")
        print(f"  Node Feature Mean: [{', '.join(f'{x:.3f}' for x in stats['node_feat_mean'][:3])}, ...]")
        print(f"  Tab Feature Mean: [{', '.join(f'{x:.3f}' for x in stats['tab_feat_mean'][:3])}, ...]")

    print("\n" + "=" * 60)


def verify_non_iid_property(banks_data: list[SyntheticBankData]) -> dict[str, Any]:
    """
    Verify that banks have non-IID data distributions.

    Parameters
    ----------
    banks_data:
        List of SyntheticBankData for each bank.

    Returns
    -------
    dict
        Verification results including failure rate variance,
        feature distribution distances, etc.
    """
    failure_rates = [data.labels.mean() for data in banks_data]
    failure_rate_variance = np.var(failure_rates)

    # Compute pairwise Euclidean distance between node feature means
    node_means = [data.node_feat.mean(axis=0) for data in banks_data]
    distances = []
    for i in range(len(node_means)):
        for j in range(i + 1, len(node_means)):
            dist = np.linalg.norm(node_means[i] - node_means[j])
            distances.append(dist)

    avg_distance = np.mean(distances) if distances else 0.0

    return {
        "failure_rates": failure_rates,
        "failure_rate_variance": float(failure_rate_variance),
        "pairwise_feature_distances": distances,
        "avg_pairwise_distance": float(avg_distance),
        "is_non_iid": (
            failure_rate_variance > 0.01 and avg_distance > 0.1
        ),  # Empirical thresholds
    }
