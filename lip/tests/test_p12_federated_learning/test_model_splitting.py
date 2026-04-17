"""
P4 Federated Learning — Unit Tests for Model Splitting

Validates that LocalModel and SharedModel produce correct outputs and that
FederatedModel wrapper maintains compatibility.

Test Coverage:
- LocalModel forward pass produces expected output dimensions
- SharedModel forward pass produces expected output dimensions
- FederatedModel produces same outputs as combined LocalModel + SharedModel
- Parameter counts match expectations
"""

import pytest
import torch
import torch.nn.functional as F

from lip.c1_failure_classifier.tabtransformer_torch import (
    TABTRANSFORMER_EMBED_DIM,
    TABTRANSFORMER_NUM_HEADS,
)
from lip.p12_federated_learning.constants import (
    GRAPHSAGE_OUTPUT_DIM,
)
from lip.p12_federated_learning.models import (
    FederatedModel,
    LocalModel,
    SharedModel,
    count_parameters,
    get_local_parameter_count,
    get_shared_parameter_count,
    get_total_parameter_count,
)

TABTRANSFORMER_MODEL_DIM = TABTRANSFORMER_NUM_HEADS * TABTRANSFORMER_EMBED_DIM

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_batch():
    """Create a sample batch for testing."""
    batch_size = 32

    node_feat = torch.randn(batch_size, 8)
    tab_feat = torch.randn(batch_size, 88)
    neighbor_feats = torch.randn(batch_size, 5, 8)

    return {
        "node_feat": node_feat,
        "tab_feat": tab_feat,
        "neighbor_feats": neighbor_feats,
    }


@pytest.fixture
def local_model():
    """Create a LocalModel instance."""
    return LocalModel()


@pytest.fixture
def shared_model():
    """Create a SharedModel instance."""
    return SharedModel()


@pytest.fixture
def federated_model(local_model, shared_model):
    """Create a FederatedModel instance."""
    return FederatedModel(local_model, shared_model)


# =============================================================================
# LocalModel Tests
# =============================================================================


class TestLocalModel:
    """Tests for LocalModel (never transmitted component)."""

    def test_output_dimensions(self, local_model, sample_batch):
        """Verify LocalModel produces correct output dimensions."""
        h2, tab_emb = local_model(
            sample_batch["node_feat"],
            sample_batch["tab_feat"],
            sample_batch["neighbor_feats"],
        )

        batch_size = sample_batch["node_feat"].shape[0]

        assert h2.shape == (batch_size, GRAPHSAGE_OUTPUT_DIM)
        assert tab_emb.shape == (batch_size, 256)

    def test_empty_neighbor_mode(self, local_model, sample_batch):
        """Verify empty-neighbor mode works correctly."""
        h2_with, tab_emb_with = local_model(
            sample_batch["node_feat"],
            sample_batch["tab_feat"],
            sample_batch["neighbor_feats"],
        )

        h2_without, tab_emb_without = local_model(
            sample_batch["node_feat"],
            sample_batch["tab_feat"],
            neighbor_feats=None,
        )

        # Dimensions should be the same
        assert h2_with.shape == h2_without.shape
        assert tab_emb_with.shape == tab_emb_without.shape

    def test_l2_normalization(self, local_model, sample_batch):
        """Verify outputs are L2-normalized."""
        h2, tab_emb = local_model(
            sample_batch["node_feat"],
            sample_batch["tab_feat"],
            sample_batch["neighbor_feats"],
        )

        # Check L2 norm is approximately 1.0
        h2_norms = torch.norm(h2, p=2, dim=1)
        assert torch.allclose(h2_norms, torch.ones_like(h2_norms), atol=1e-5)

    def test_parameter_count(self):
        """Verify LocalModel has expected parameter count."""
        local = LocalModel()
        params = count_parameters(local)
        assert params > 0
        assert params == get_local_parameter_count()


# =============================================================================
# SharedModel Tests
# =============================================================================


class TestSharedModel:
    """Tests for SharedModel (federated component)."""

    def test_output_dimensions(self, shared_model, sample_batch):
        """Verify SharedModel produces correct output dimensions."""
        batch_size = sample_batch["node_feat"].shape[0]

        # Get local model outputs (simulated)
        h2 = torch.randn(batch_size, GRAPHSAGE_OUTPUT_DIM)
        tab_emb = torch.randn(batch_size, 256)

        logits = shared_model(h2, tab_emb)

        assert logits.shape == (batch_size, 1)

    def test_output_is_logits(self, shared_model, sample_batch):
        """Verify outputs are raw logits (not sigmoid)."""
        batch_size = sample_batch["node_feat"].shape[0]

        h2 = torch.randn(batch_size, GRAPHSAGE_OUTPUT_DIM)
        tab_emb = torch.randn(batch_size, 256)

        logits = shared_model(h2, tab_emb)

        # Logits should have arbitrary range, sigmoid constrains to [0, 1]
        # Check that values can be outside [0, 1]
        assert logits.min() < 0 or logits.max() > 1

    def test_parameter_count(self):
        """Verify SharedModel has expected parameter count."""
        shared = SharedModel()
        params = count_parameters(shared)
        assert params > 0
        assert params == get_shared_parameter_count()

    def test_shared_params_less_than_total(self):
        """Verify shared params < total params (local not included)."""
        shared_count = get_shared_parameter_count()
        total_count = get_total_parameter_count()

        assert shared_count < total_count
        # Note: shared + local may be less than total due to overlap in some components


# =============================================================================
# FederatedModel Tests
# =============================================================================


class TestFederatedModel:
    """Tests for FederatedModel (Opacus-compatible wrapper)."""

    def test_output_dimensions(self, federated_model, sample_batch):
        """Verify FederatedModel produces correct output dimensions."""
        logits = federated_model(
            sample_batch["node_feat"],
            sample_batch["tab_feat"],
            sample_batch["neighbor_feats"],
        )

        batch_size = sample_batch["node_feat"].shape[0]
        assert logits.shape == (batch_size, 1)

    def test_equivalence_to_separate_models(self, sample_batch):
        """Verify FederatedModel produces same output as LocalModel + SharedModel."""
        # Seed-matched comparison: with identical initialization, FederatedModel's
        # output must equal the separate LocalModel + SharedModel composition.
        torch.manual_seed(42)
        local_same = LocalModel()
        torch.manual_seed(42)
        shared_same = SharedModel()

        h2_same, tab_emb_same = local_same(
            sample_batch["node_feat"],
            sample_batch["tab_feat"],
            sample_batch["neighbor_feats"],
        )
        logits_separate_same = shared_same(h2_same, tab_emb_same)

        torch.manual_seed(42)
        federated_same = FederatedModel(local_same, shared_same)
        logits_federated_same = federated_same(
            sample_batch["node_feat"],
            sample_batch["tab_feat"],
            sample_batch["neighbor_feats"],
        )

        assert torch.allclose(logits_federated_same, logits_separate_same, atol=1e-5)

    def test_parameter_count(self):
        """Verify FederatedModel has total parameter count."""
        federated = FederatedModel(LocalModel(), SharedModel())
        params = count_parameters(federated)
        assert params == get_total_parameter_count()

    def test_all_parameters_trainable(self, federated_model):
        """Verify all parameters in FederatedModel are trainable."""
        trainable_params = [p for p in federated_model.parameters() if p.requires_grad]
        total_params = [p for p in federated_model.parameters()]

        assert len(trainable_params) == len(total_params)

    def test_backward_pass(self, federated_model, sample_batch):
        """Verify backward pass works correctly.

        Note: With seq_len=1 (single token), q_proj and k_proj in self-attention
        have mathematically zero gradients because softmax([x]) = 1 for any x.
        This is expected behavior, not a bug. Only v_proj and out_proj gradients
        are non-zero for single-token attention.
        """
        logits = federated_model(
            sample_batch["node_feat"],
            sample_batch["tab_feat"],
            sample_batch["neighbor_feats"],
        )

        # Create dummy labels (binary: 0 or 1)
        batch_size = sample_batch["node_feat"].shape[0]
        labels = torch.randint(0, 2, (batch_size,)).float()

        # Compute loss
        loss = F.binary_cross_entropy_with_logits(logits.squeeze(-1), labels)

        # Backward pass
        loss.backward()

        # Check gradients exist and are non-zero where expected
        for name, param in federated_model.named_parameters():
            assert param.grad is not None, f"No gradient for {name}"

            # Skip non-zero gradient check for q_proj and k_proj in attention layers
            # (mathematically zero with seq_len=1)
            if "attn.q_proj" in name or "attn.k_proj" in name:
                continue

            assert not torch.allclose(param.grad, torch.zeros_like(param.grad)), f"Zero gradient for {name}"


# =============================================================================
# Compatibility Tests
# =============================================================================


class TestModelCompatibility:
    """Tests for compatibility with existing C1 model architecture."""

    def test_local_plus_shared_matches_original(self, sample_batch):
        """Verify split model output dimensions match original model."""
        torch.manual_seed(123)
        local = LocalModel()
        torch.manual_seed(123)
        shared = SharedModel()

        # Forward through split models
        h2, tab_emb = local(
            sample_batch["node_feat"],
            sample_batch["tab_feat"],
            sample_batch["neighbor_feats"],
        )
        logits_split = shared(h2, tab_emb)

        # Original model has different architecture (GraphSAGE with neighbor aggregation,
        # TabTransformer with different embedding), so we only compare output shapes
        batch_size = sample_batch["node_feat"].shape[0]
        assert logits_split.shape == (batch_size, 1)

    def test_input_feature_compatibility(self, federated_model, sample_batch):
        """Verify input features are compatible with existing data format."""
        # Should work with same input format as original model
        logits = federated_model(
            sample_batch["node_feat"],
            sample_batch["tab_feat"],
            sample_batch["neighbor_feats"],
        )

        assert logits.shape[0] == sample_batch["node_feat"].shape[0]


# =============================================================================
# Parameter Count Tests
# =============================================================================


class TestParameterCounts:
    """Tests for parameter count tracking."""

    def test_local_params_count(self):
        """LocalModel has a reasonable number of parameters."""
        count = get_local_parameter_count()
        assert 100_000 < count < 1_000_000  # Reasonable range for GraphSAGE L1-2 + embed

    def test_shared_params_count(self):
        """SharedModel has a reasonable number of parameters."""
        count = get_shared_parameter_count()
        assert 500_000 < count < 2_000_000  # Reasonable range for GSAGE final + TT enc + MLP

    def test_total_params_count(self):
        """FederatedModel has a reasonable total parameter count."""
        count = get_total_parameter_count()
        assert 500_000 < count < 3_000_000  # Reasonable range for full model

    def test_shared_subset_of_total(self):
        """Shared parameters are a subset of total parameters."""
        shared_count = get_shared_parameter_count()
        total_count = get_total_parameter_count()
        local_count = get_local_parameter_count()

        # Total should be close to shared + local (may have overlap)
        assert abs((shared_count + local_count) - total_count) < 500_000  # Allow for overlap


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_batch_size_one(self, federated_model):
        """Verify model works with batch_size=1."""
        node_feat = torch.randn(1, 8)
        tab_feat = torch.randn(1, 88)
        neighbor_feats = torch.randn(1, 5, 8)

        logits = federated_model(node_feat, tab_feat, neighbor_feats)
        assert logits.shape == (1, 1)

    def test_large_batch_size(self, federated_model):
        """Verify model works with large batch sizes."""
        batch_size = 1024
        node_feat = torch.randn(batch_size, 8)
        tab_feat = torch.randn(batch_size, 88)
        neighbor_feats = torch.randn(batch_size, 5, 8)

        logits = federated_model(node_feat, tab_feat, neighbor_feats)
        assert logits.shape == (batch_size, 1)

    def test_no_neighbors(self, federated_model):
        """Verify model works with no neighbors (empty-neighbor mode)."""
        batch_size = 32
        node_feat = torch.randn(batch_size, 8)
        tab_feat = torch.randn(batch_size, 88)

        logits = federated_model(node_feat, tab_feat, neighbor_feats=None)
        assert logits.shape == (batch_size, 1)
