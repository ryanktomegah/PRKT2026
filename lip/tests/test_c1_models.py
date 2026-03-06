"""
test_c1_models.py — Tests for C1 PyTorch models (models.py).

These tests cover import and stub behaviour when torch is not installed,
and full model tests when torch IS installed.
"""
from __future__ import annotations

import pytest


class TestModelsImport:
    """Test that models.py can be imported without crashing."""

    def test_import_module(self) -> None:
        """Module imports without error (stubs loaded if no torch)."""
        from lip.c1_failure_classifier import models
        assert hasattr(models, "GraphSAGEEncoder")
        assert hasattr(models, "TabTransformerEncoder")
        assert hasattr(models, "C1Model")
        assert hasattr(models, "AsymmetricBCELoss")

    def test_torch_availability_flag(self) -> None:
        """_TORCH_AVAILABLE reflects whether torch is installed."""
        from lip.c1_failure_classifier.models import _TORCH_AVAILABLE
        try:
            import torch
            assert _TORCH_AVAILABLE is True
        except ImportError:
            assert _TORCH_AVAILABLE is False


class TestModelsStubs:
    """Test stub behaviour when torch is not available."""

    def test_stub_raises_on_instantiation(self) -> None:
        """If torch is not available, instantiation raises ImportError."""
        from lip.c1_failure_classifier.models import _TORCH_AVAILABLE
        if _TORCH_AVAILABLE:
            pytest.skip("torch is installed — testing live classes instead")

        from lip.c1_failure_classifier.models import (
            GraphSAGEEncoder, TabTransformerEncoder, C1Model, AsymmetricBCELoss
        )
        with pytest.raises(ImportError):
            GraphSAGEEncoder()
        with pytest.raises(ImportError):
            TabTransformerEncoder()
        with pytest.raises(ImportError):
            C1Model()
        with pytest.raises(ImportError):
            AsymmetricBCELoss()


class TestModelsLive:
    """Test model classes when PyTorch is available."""

    @pytest.fixture(autouse=True)
    def _require_torch(self):
        from lip.c1_failure_classifier.models import _TORCH_AVAILABLE
        if not _TORCH_AVAILABLE:
            pytest.skip("torch not installed")

    def test_graphsage_encoder_forward(self) -> None:
        import torch
        from lip.c1_failure_classifier.models import GraphSAGEEncoder
        model = GraphSAGEEncoder(in_channels=28, hidden_channels=128, out_channels=128, edge_dim=26)
        x = torch.randn(10, 28)
        edge_index = torch.tensor([[0, 1, 2, 3], [1, 2, 3, 0]], dtype=torch.long)
        edge_attr = torch.randn(4, 26)
        node_emb, edge_emb = model(x, edge_index, edge_attr)
        assert node_emb.shape == (10, 128)
        assert edge_emb.shape == (4, 128)

    def test_graphsage_encoder_l2_normalised(self) -> None:
        import torch
        from lip.c1_failure_classifier.models import GraphSAGEEncoder
        model = GraphSAGEEncoder()
        x = torch.randn(5, 28)
        edge_index = torch.tensor([[0, 1], [1, 0]], dtype=torch.long)
        node_emb, _ = model(x, edge_index)
        norms = torch.norm(node_emb, p=2, dim=-1)
        assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)

    def test_tabtransformer_encoder_forward(self) -> None:
        import torch
        from lip.c1_failure_classifier.models import TabTransformerEncoder
        model = TabTransformerEncoder()
        B = 4
        cat_features = {
            "rejection_code": torch.randint(0, 64, (B,)),
            "amount_tier": torch.randint(0, 4, (B,)),
            "currency_pair": torch.randint(0, 128, (B,)),
            "sender_country": torch.randint(0, 64, (B,)),
            "receiver_country": torch.randint(0, 64, (B,)),
            "rejection_code_class": torch.randint(0, 4, (B,)),
            "is_month_end": torch.randint(0, 2, (B,)),
            "is_quarter_end": torch.randint(0, 2, (B,)),
        }
        cont_features = torch.randn(B, 8)
        out = model(cat_features, cont_features)
        assert out.shape == (B, 88)

    def test_c1model_forward(self) -> None:
        import torch
        from lip.c1_failure_classifier.models import C1Model
        model = C1Model(graph_dim=384, tab_dim=88)
        graph_ctx = torch.randn(8, 384)
        tab_out = torch.randn(8, 88)
        prob = model(graph_ctx, tab_out)
        assert prob.shape == (8, 1)
        assert (prob >= 0).all() and (prob <= 1).all()

    def test_asymmetric_bce_loss(self) -> None:
        import torch
        from lip.c1_failure_classifier.models import AsymmetricBCELoss
        loss_fn = AsymmetricBCELoss(alpha=0.7)
        y_pred = torch.tensor([0.9, 0.1, 0.5])
        y_true = torch.tensor([1.0, 0.0, 1.0])
        loss = loss_fn(y_pred, y_true)
        assert loss.item() > 0
        assert loss.dim() == 0  # scalar

    def test_asymmetric_bce_alpha_default(self) -> None:
        from lip.c1_failure_classifier.models import AsymmetricBCELoss
        loss_fn = AsymmetricBCELoss()
        assert loss_fn.alpha == 0.7
